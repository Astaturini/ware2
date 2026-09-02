from __future__ import annotations

import copy
import random
import threading
import time
from typing import Any

from .charging import ChargingStation
from .config import BatteryConfig, ChargingConfig, FailureConfig
from .conflict import ConflictManager, LocalYieldConflictManager
from .metrics import Metrics
from .pathfinding import BFSPathPlanner, PathPlanner
from .robot import Robot, RobotMode, RobotStatus
from .scheduler import CostBasedScheduler, Scheduler
from .task import LoadState, Task, TaskPhase, TaskStatus
from .task_generator import TaskGenerator
from .warehouse import CellType, Location, Warehouse

INTERRUPTED_TASK_STATUS = getattr(TaskStatus, "INTERRUPTED", TaskStatus.PENDING)


class Simulation:
    """Thread-safe simulation engine.

    v0.4 adds battery/charging, task interruption/recovery, failures,
    maintenance relocation, and congestion metrics while preserving the
    v0.3.1 traffic/conflict behavior.
    
    v0.6 extracts path planning and conflict resolution into injectable plugins.
    """

    def __init__(
        self,
        warehouse: Warehouse,
        robots: list[Robot],
        tasks: list[Task],
        tick_interval: float = 0.3,
        scheduler: Scheduler | None = None,
        task_generator: TaskGenerator | None = None,
        metrics: Metrics | None = None,
        blocked_replan_seconds: float = 0.7,
        replan_cooldown_ticks: int = 7,
        *,
        battery_config: BatteryConfig | None = None,
        charging_config: ChargingConfig | None = None,
        failure_config: FailureConfig | None = None,
        seed: int | None = None,
        path_planner: PathPlanner | None = None,
    ) -> None:
        self._warehouse = warehouse
        self._tick_interval = tick_interval
        self._scheduler = scheduler or CostBasedScheduler()
        self._path_planner = path_planner or BFSPathPlanner()
        self._task_generator = task_generator
        self._metrics = metrics or Metrics()

        # v0.4 configuration.
        self._battery_cfg = battery_config or BatteryConfig()
        self._charging_cfg = charging_config or ChargingConfig()
        self._failure_cfg = failure_config or FailureConfig()

        self._charging_station = ChargingStation(
            capacity=self._charging_cfg.capacity,
            charge_duration_ticks=self._charging_cfg.charge_duration_ticks,
        )
        self._charging_cells = self._scan_cells(CellType.CHARGING)
        self._maintenance_cells = self._scan_cells(CellType.MAINTENANCE)

        self._failure_seed = seed if seed is not None else self._failure_cfg.seed
        self._failure_rng = random.Random(self._failure_seed)

        # Dynamic resume locations created for interrupted loaded tasks.
        self._dynamic_location_names: set[str] = set()

        self._blocked_replan_threshold_ticks = max(
            1,
            int(round(blocked_replan_seconds / tick_interval)),
        )
        self._replan_cooldown_ticks = max(1, replan_cooldown_ticks)

        self._validate_initial_state(robots, tasks)

        self._initial_robots = [copy.deepcopy(robot) for robot in robots]
        self._initial_tasks = [copy.deepcopy(task) for task in tasks]

        self._robots: dict[str, Robot] = {}
        self._tasks: dict[str, Task] = {}
        self._tick_count = 0

        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._running_event = threading.Event()
        self._thread: threading.Thread | None = None
        
        # v0.6 plugin architecture
        self._conflict_manager: ConflictManager = LocalYieldConflictManager(self)

        self.reset()

    def set_conflict_manager(self, manager: ConflictManager) -> None:
        """Inject a different conflict resolution strategy."""
        self._conflict_manager = manager
        if hasattr(self._conflict_manager, "_sim"):
            setattr(self._conflict_manager, "_sim", self)

    # ------------------------------------------------------------------
    # Safe metric helper
    # ------------------------------------------------------------------

    def _safe_metric(self, method_name: str, *args: Any) -> None:
        method = getattr(self._metrics, method_name, None)
        if callable(method):
            method(*args)

    # ------------------------------------------------------------------
    # Initialization / lifecycle
    # ------------------------------------------------------------------

    def _validate_initial_state(self, robots: list[Robot], tasks: list[Task]) -> None:
        if len({robot.id for robot in robots}) != len(robots):
            raise ValueError("Robot ids must be unique.")

        if len({task.id for task in tasks}) != len(tasks):
            raise ValueError("Task ids must be unique.")

        for robot in robots:
            if not self._warehouse.in_bounds(robot.x, robot.y):
                raise ValueError(f"Robot {robot.id} starts outside warehouse bounds.")
            if self._warehouse.is_blocked(robot.x, robot.y):
                raise ValueError(f"Robot {robot.id} starts inside an obstacle.")

        for task in tasks:
            for name in (task.pickup, task.dropoff):
                try:
                    point = self._warehouse.resolve(name)
                except KeyError:
                    raise ValueError(
                        f"Task {task.id} references unknown location {name!r}."
                    ) from None

                if not self._warehouse.in_bounds(*point):
                    raise ValueError(
                        f"Task {task.id} has a location outside bounds."
                    )

                if self._warehouse.is_blocked(*point):
                    raise ValueError(
                        f"Task {task.id} has a blocked location."
                    )

    @property
    def is_paused(self) -> bool:
        return self._stop_event.is_set() or not self._running_event.is_set()

    def start(self) -> None:
        """Start the background simulation loop."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return

            self._stop_event.clear()
            self._running_event.set()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def pause(self) -> None:
        """Pause simulation ticking."""
        self._running_event.clear()

    def resume(self) -> None:
        """Resume simulation ticking."""
        self._running_event.set()

    def reset(self) -> None:
        """Reset robots and tasks to their initial state."""
        with self._lock:
            self._robots = {
                robot.id: copy.deepcopy(robot) for robot in self._initial_robots
            }
            self._tasks = {
                task.id: copy.deepcopy(task) for task in self._initial_tasks
            }

            # Remove dynamic resume locations from previous runs.
            for name in list(self._dynamic_location_names):
                self._warehouse.locations.pop(name, None)
            self._dynamic_location_names.clear()

            for robot in self._robots.values():
                robot.blocked_ticks = 0
                robot.replan_cooldown = 0
                robot.replanning = False
                robot.yielding_to = None
                robot.travel_history = []
                robot.set_path([])
                robot.current_task_id = None
                robot.route_goal = None

                # v0.4 robot state.
                robot.battery = self._battery_cfg.capacity
                robot.mode = RobotMode.IDLE
                robot.idle_ticks = 0
                robot.charger_wait_ticks = 0
                robot.interrupted_task_id = None
                robot.charge_target = None
                robot.charge_start_battery = None
                robot.repair_remaining_ticks = 0

            self._tick_count = 0
            self._conflict_manager.reset()

            self._charging_station = ChargingStation(
                capacity=self._charging_cfg.capacity,
                charge_duration_ticks=self._charging_cfg.charge_duration_ticks,
            )
            self._failure_rng = random.Random(self._failure_seed)

            self._metrics.reset()

            # If upgraded metrics exist, set battery capacity.
            if hasattr(self._metrics, "battery_capacity"):
                self._metrics.battery_capacity = self._battery_cfg.capacity

            for robot in self._robots.values():
                self._metrics.register_robot(robot)

            if self._task_generator is not None:
                self._task_generator.reset()

    def stop(self) -> None:
        """Stop the background simulation loop."""
        self._stop_event.set()
        self._running_event.set()

        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def get_state(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot of the simulation."""
        with self._lock:
            warehouse_dict = self._warehouse.to_dict()

            # Do not expose temporary RESUME-* locations to the UI.
            if self._dynamic_location_names:
                warehouse_dict["locations"] = {
                    name: location
                    for name, location in warehouse_dict["locations"].items()
                    if name not in self._dynamic_location_names
                }

            metrics_dict = self._metrics.to_dict(self._tick_interval)
            metrics_dict["congestion"] = self._congestion_snapshot()

            return {
                "paused": self.is_paused,
                "tick": self._tick_count,
                "warehouse": warehouse_dict,
                "robots": [robot.to_dict() for robot in self._robots.values()],
                "tasks": [task.to_dict() for task in self._tasks.values()],
                "metrics": metrics_dict,
            }

    # ------------------------------------------------------------------
    # Congestion snapshot
    # ------------------------------------------------------------------

    def _congestion_snapshot(self) -> dict[str, Any]:
        robots = list(self._robots.values())
        robot_count = len(robots)

        blocked_robots = sum(1 for robot in robots if robot.blocked_ticks > 0)
        waiting_for_charger = sum(
            1
            for robot in robots
            if getattr(robot, "mode", RobotMode.IDLE) == RobotMode.WAITING_FOR_CHARGER
        )
        charging = sum(
            1
            for robot in robots
            if getattr(robot, "mode", RobotMode.IDLE) == RobotMode.CHARGING
        )
        to_charger = sum(
            1
            for robot in robots
            if getattr(robot, "mode", RobotMode.IDLE) == RobotMode.TO_CHARGER
        )
        failed = sum(
            1
            for robot in robots
            if getattr(robot, "mode", RobotMode.IDLE)
            in (RobotMode.FAILED, RobotMode.REPAIRING)
        )
        replanning = sum(1 for robot in robots if robot.replanning)
        
        active_conflicts = self._conflict_manager.active_conflicts

        total_blocked_ticks = sum(robot.blocked_ticks for robot in robots)
        average_blocked_ticks = (
            total_blocked_ticks / robot_count if robot_count else 0.0
        )

        robots_by_row: dict[str, int] = {}
        for robot in robots:
            key = f"row-{robot.y:02d}"
            robots_by_row[key] = robots_by_row.get(key, 0) + 1

        return {
            "blockedRobots": blocked_robots,
            "waitingForChargerRobots": waiting_for_charger,
            "chargingRobots": charging,
            "toChargerRobots": to_charger,
            "failedRobots": failed,
            "replanningRobots": replanning,
            "activeConflicts": active_conflicts,
            "chargerOccupancy": self._charging_station.occupancy,
            "chargerWaiting": len(self._charging_station.waiting),
            "averageBlockedTicks": average_blocked_ticks,
            "robotsByRow": robots_by_row,
        }

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        while not self._stop_event.is_set():
            if self._running_event.is_set():
                with self._lock:
                    self._tick()

                time.sleep(self._tick_interval)
            else:
                time.sleep(0.05)

    def _tick(self) -> None:
        # v0.4 failure/repair first.
        self._update_failures_and_repairs()

        # v0.4 charging progression and waiting dispatch.
        self._update_charging_station()

        if self._task_generator is not None:
            new_tasks = self._task_generator.step(self._tick_count)
            for task in new_tasks:
                self._tasks[task.id] = task
                self._metrics.record_generated(task)

        self._assign_pending_tasks()
        self._update_battery_checks()
        self._update_idle_and_opportunistic_charging()

        # Proactive conflict layer syncs before movement.
        self._conflict_manager.tick(
            self._tick_count,
            list(self._robots.values()),
        )

        self._advance_robots()

        self._metrics.record_tick(list(self._robots.values()))

        # Optional battery sampling if upgraded metrics exist.
        for robot in self._robots.values():
            self._safe_metric("record_battery_sample", robot)

        self._prune_old_tasks()

        self._tick_count += 1

    # ------------------------------------------------------------------
    # Task assignment
    # ------------------------------------------------------------------

    def _assign_pending_tasks(self) -> None:
        pending_tasks = [
            task
            for task in self._tasks.values()
            if task.status in (TaskStatus.PENDING, INTERRUPTED_TASK_STATUS)
        ]

        if not pending_tasks:
            return

        eligible_robots = [
            robot
            for robot in self._robots.values()
            if self._robot_can_accept_task(robot)
        ]

        if not eligible_robots:
            return

        assignments = self._scheduler.select_assignments(
            pending_tasks,
            eligible_robots,
            self._warehouse,
            blocked_cells=self._occupied_cells(),
        )

        for assignment in assignments:
            task = self._tasks.get(assignment.task_id)
            robot = self._robots.get(assignment.robot_id)

            if task is None or robot is None:
                continue

            if task.status not in (TaskStatus.PENDING, INTERRUPTED_TASK_STATUS):
                continue

            if not self._robot_can_accept_task(robot):
                continue

            if not self._battery_feasible_for_new_task(robot, task):
                if self._battery_cfg.is_critical(robot.battery):
                    self._enter_charging(robot, reason="critical_battery")
                continue

            self._begin_task(robot, task)

    def _robot_can_accept_task(self, robot: Robot) -> bool:
        if robot.current_task_id is not None:
            return False

        if robot.status != RobotStatus.IDLE:
            return False

        mode = getattr(robot, "mode", RobotMode.IDLE)
        if mode != RobotMode.IDLE:
            return False

        if self._charging_station.is_charging(robot.id):
            return False

        if self._charging_station.is_waiting(robot.id):
            return False

        battery = float(getattr(robot, "battery", self._battery_cfg.capacity))
        if self._battery_cfg.is_critical(battery):
            return False

        return True

    def _begin_task(self, robot: Robot, task: Task) -> None:
        previous_robot_id = getattr(task, "last_assigned_robot_id", None)

        task.status = TaskStatus.ASSIGNED
        task.assigned_robot_id = robot.id
        task.phase = TaskPhase.TO_PICKUP

        # v0.4 task attributes.
        task.last_assigned_robot_id = robot.id
        if not hasattr(task, "interruption_count"):
            task.interruption_count = 0
        if not hasattr(task, "load_state"):
            task.load_state = LoadState.ON_SHELF

        robot.current_task_id = task.id
        robot.travel_history = []
        robot.route_goal = self._warehouse.resolve(task.pickup)
        robot.replanning = False
        robot.yielding_to = None
        robot.blocked_ticks = 0
        robot.mode = RobotMode.MOVING
        robot.idle_ticks = 0
        robot.interrupted_task_id = None

        self._conflict_manager.clear_conflicts_for_robot(robot)

        if (
            getattr(task, "interruption_count", 0) > 0
            and previous_robot_id is not None
            and previous_robot_id != robot.id
        ):
            self._safe_metric("record_task_reassignment")

        self._metrics.record_assigned(task, self._tick_count)

        self._route_robot_to(robot, task, robot.route_goal)

        # Initial route is a significant route change.
        if robot.current_task_id == task.id:
            self._check_battery_for_active_task(robot)

    # ------------------------------------------------------------------
    # Robot movement
    # ------------------------------------------------------------------

    def _advance_robots(self) -> None:
        occupied = self._occupied_cells()

        ordered_robots = sorted(
            self._robots.values(),
            key=lambda robot: (0 if robot.replanning else 1, robot.id),
        )

        for robot in ordered_robots:
            if robot.replan_cooldown > 0:
                robot.replan_cooldown -= 1

            mode = getattr(robot, "mode", RobotMode.IDLE)

            # Failed, repairing, and actively charging robots do not move.
            if mode in (
                RobotMode.FAILED,
                RobotMode.REPAIRING,
                RobotMode.CHARGING,
            ):
                continue

            if robot.replanning:
                self._conflict_manager.advance_replanning_robot(robot, occupied)
                continue

            if not robot.path:
                if robot.route_goal is not None and (
                    robot.current_task_id is not None
                    or mode in (RobotMode.TO_CHARGER, RobotMode.MOVING)
                ):
                    self._attempt_resume_route(robot)
                continue

            next_cell = robot.current_target
            if next_cell is None:
                continue

                next_cell = robot.current_target
            if next_cell is None:
                continue

            # Proactive conflict managers can deny a step before the
            # occupied-cell check. Replanning/yield robots above are NOT
            # gated, so deadlock escape still works.
            if not self._conflict_manager.allow_step(robot, next_cell, occupied):
                robot.blocked_ticks += 1
                self._metrics.record_blocked(robot)
                continue

            if next_cell in occupied:
                self._conflict_manager.handle_blocked_robot(robot, next_cell)
                continue        
            arrived = self._step_robot_forward(robot, occupied)

            if arrived:
                self._handle_arrival(robot)
            else:
                self._check_battery_for_active_task(robot)
    
    def _step_robot_forward(
        self,
        robot: Robot,
        occupied: set[tuple[int, int]],
    ) -> bool:
        previous_cell = (robot.x, robot.y)
        arrived = robot.advance()
        robot.travel_history.append(previous_cell)
        robot.blocked_ticks = 0

        occupied.discard(previous_cell)
        occupied.add((robot.x, robot.y))

        self._consume_move_energy(robot)
        self._metrics.record_robot_move(robot)
        self._conflict_manager.release_conflict(robot)

        return arrived

    # ------------------------------------------------------------------
    # Routing / route recovery
    # ------------------------------------------------------------------

    def _attempt_resume_route(self, robot: Robot) -> bool:
        if robot.route_goal is None:
            return False

        current = (robot.x, robot.y)
        goal = robot.route_goal

        if current == goal:
            self._handle_arrival(robot)
            return True

        occupied = self._occupied_cells(exclude_robot_id=robot.id)
        claimed = self._claimed_cells(exclude_robot_id=robot.id)

        blocked = occupied | claimed
        blocked.discard(current)

        path = self._path_planner.find_path(
            self._warehouse,
            current,
            goal,
            blocked_cells=blocked,
        )

        # If claims make the route temporarily impossible, try again using only
        # physically occupied cells. The first step is still rejected if claimed.
        if path is None or (path and path[0] in claimed):
            fallback = self._path_planner.find_path(
                self._warehouse,
                current,
                goal,
                blocked_cells=occupied,
            )

            if fallback is not None:
                path = fallback

        if path is None:
            return False

        if not path:
            self._handle_arrival(robot)
            return True

        first_step = path[0]

        if first_step in occupied or first_step in claimed:
            return False

        robot.set_path(path)
        robot.replanning = False
        robot.yielding_to = None
        robot.blocked_ticks = 0

        # Route resumption is a significant route change.
        self._check_battery_for_active_task(robot)
        return True

    def _route_robot_to(
        self,
        robot: Robot,
        task: Task,
        destination: tuple[int, int],
    ) -> None:
        robot.route_goal = destination

        blocked_cells = self._occupied_cells()
        blocked_cells.discard((robot.x, robot.y))

        path = self._path_planner.find_path(
            self._warehouse,
            (robot.x, robot.y),
            destination,
            blocked_cells=blocked_cells,
        )

        if path is None:
            path = self._path_planner.find_path(
                self._warehouse,
                (robot.x, robot.y),
                destination,
            )

        if path is None:
            # Extension point: handle unreachable tasks more gracefully.
            task.status = TaskStatus.FAILED
            task.phase = TaskPhase.DONE
            task.completed_at = self._tick_count

            self._metrics.record_failed(task, self._tick_count)

            robot.current_task_id = None
            robot.route_goal = None

            self._conflict_manager.clear_conflicts_for_robot(robot)
            robot.set_path([])
            return

        robot.set_path(path)
        robot.replanning = False
        robot.yielding_to = None

        if not robot.path:
            self._handle_arrival(robot)

    def _route_robot_to_cell(
        self,
        robot: Robot,
        destination: tuple[int, int],
    ) -> bool:
        """Route a robot to a cell without requiring a task."""
        robot.route_goal = destination

        blocked_cells = self._occupied_cells(exclude_robot_id=robot.id)
        blocked_cells.discard((robot.x, robot.y))

        path = self._path_planner.find_path(
            self._warehouse,
            (robot.x, robot.y),
            destination,
            blocked_cells=blocked_cells,
        )

        if path is None:
            path = self._path_planner.find_path(
                self._warehouse,
                (robot.x, robot.y),
                destination,
            )

        if path is None:
            robot.set_path([])
            return False

        robot.set_path(path)
        robot.replanning = False
        robot.yielding_to = None
        return True

    def _handle_arrival(self, robot: Robot) -> None:
        self._conflict_manager.clear_conflicts_for_robot(robot)

        # v0.4: taskless charging arrival.
        if robot.current_task_id is None:
            if (
                robot.route_goal is not None
                and robot.route_goal in self._charging_cells
            ):
                self._handle_charging_arrival(robot)
                return

            robot.set_path([])

            mode = getattr(robot, "mode", RobotMode.IDLE)
            if mode not in (
                RobotMode.WAITING_FOR_CHARGER,
                RobotMode.CHARGING,
                RobotMode.FAILED,
                RobotMode.REPAIRING,
            ):
                robot.mode = RobotMode.IDLE

            robot.route_goal = None
            return

        task = self._tasks.get(robot.current_task_id)

        if task is None:
            robot.current_task_id = None
            robot.set_path([])
            robot.mode = RobotMode.IDLE
            robot.route_goal = None
            return

        if task.phase == TaskPhase.TO_PICKUP:
            task.phase = TaskPhase.TO_DROPOFF

            if hasattr(task, "load_state"):
                task.load_state = LoadState.CARRIED

            robot.blocked_ticks = 0
            robot.mode = RobotMode.MOVING

            # Remaining route changed from pickup leg to dropoff leg.
            self._check_battery_for_active_task(robot)

            # If battery interruption occurred, do not route to dropoff.
            if robot.current_task_id != task.id:
                return

            self._route_robot_to(
                robot,
                task,
                self._warehouse.resolve(task.dropoff),
            )
            return

        if task.phase == TaskPhase.TO_DROPOFF:
            task.status = TaskStatus.COMPLETED
            task.phase = TaskPhase.DONE
            task.completed_at = self._tick_count

            if hasattr(task, "load_state"):
                task.load_state = LoadState.DELIVERED

            self._metrics.record_completed(task, self._tick_count)

            robot.current_task_id = None
            robot.route_goal = None
            robot.blocked_ticks = 0
            robot.replan_cooldown = 0
            robot.mode = RobotMode.IDLE
            robot.idle_ticks = 0
            robot.interrupted_task_id = None

            self._conflict_manager.clear_conflicts_for_robot(robot)

            robot.travel_history = []
            robot.set_path([])
            return

        robot.current_task_id = None
        robot.route_goal = None
        robot.blocked_ticks = 0
        robot.replan_cooldown = 0
        robot.mode = RobotMode.IDLE
        robot.idle_ticks = 0

        self._conflict_manager.clear_conflicts_for_robot(robot)

        robot.travel_history = []
        robot.set_path([])

    def _claimed_cells(self, exclude_robot_id: str | None = None) -> set[tuple[int, int]]:
        claimed: set[tuple[int, int]] = set()

        for robot in self._robots.values():
            if robot.id == exclude_robot_id:
                continue

            next_cell = robot.current_target
            if next_cell is not None:
                claimed.add(next_cell)

        return claimed

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    def _occupied_cells(self, exclude_robot_id: str | None = None) -> set[tuple[int, int]]:
        return {
            (robot.x, robot.y)
            for robot in self._robots.values()
            if robot.id != exclude_robot_id
        }

    def _robot_at(
        self,
        cell: tuple[int, int],
        exclude_robot_id: str | None = None,
    ) -> Robot | None:
        for robot in self._robots.values():
            if robot.id == exclude_robot_id:
                continue

            if (robot.x, robot.y) == cell:
                return robot

        return None

    def _task_priority(self, task_id: str | None) -> int:
        if task_id is None:
            return -1

        task = self._tasks.get(task_id)
        if task is None:
            return -1

        return task.priority

    # ------------------------------------------------------------------
    # Task pruning
    # ------------------------------------------------------------------

    def _prune_old_tasks(self) -> None:
        """Remove completed or failed tasks older than 100 ticks."""
        current_tick = self._tick_count
        max_age = 100

        to_delete = [
            task_id
            for task_id, task in self._tasks.items()
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
            and task.completed_at is not None
            and (current_tick - task.completed_at) > max_age
        ]

        for task_id in to_delete:
            del self._tasks[task_id]

    # ------------------------------------------------------------------
    # v0.4 cell scanning / relocation helpers
    # ------------------------------------------------------------------

    def _scan_cells(self, cell_type: CellType) -> list[tuple[int, int]]:
        cells: list[tuple[int, int]] = []

        for y in range(self._warehouse.height):
            for x in range(self._warehouse.width):
                if self._warehouse.cell_type(x, y) == cell_type:
                    cells.append((x, y))

        return cells

    def _nearest_passable_cell(
        self,
        robot: Robot,
        forbidden_cell_types: set[CellType],
    ) -> tuple[int, int] | None:
        occupied = self._occupied_cells(exclude_robot_id=robot.id)
        forbidden = set(forbidden_cell_types)

        best_cell: tuple[int, int] | None = None
        best_score: int | None = None

        for y in range(self._warehouse.height):
            for x in range(self._warehouse.width):
                cell = (x, y)

                if self._warehouse.is_blocked(x, y):
                    continue

                if self._warehouse.cell_type(x, y) in forbidden:
                    continue

                if cell in occupied:
                    continue

                score = abs(x - robot.x) + abs(y - robot.y)

                if best_score is None or score < best_score:
                    best_score = score
                    best_cell = cell

        return best_cell

    def _relocate_robot_to_maintenance(self, robot: Robot) -> None:
        if not getattr(self._failure_cfg, "relocate_to_maintenance", True):
            return

        if not self._maintenance_cells:
            return

        occupied = self._occupied_cells(exclude_robot_id=robot.id)

        candidates = [
            cell
            for cell in self._maintenance_cells
            if cell not in occupied
        ]

        if not candidates:
            return

        candidates.sort(
            key=lambda cell: abs(cell[0] - robot.x) + abs(cell[1] - robot.y)
        )

        robot.x, robot.y = candidates[0]
        robot.set_path([])
        robot.route_goal = None
        robot.travel_history = []

        self._conflict_manager.release_robot(robot.id)


    def _relocate_waiting_robot_off_charger(self, robot: Robot) -> None:
        if (robot.x, robot.y) not in self._charging_cells:
            return

        target = self._nearest_passable_cell(robot, {CellType.CHARGING})
        if target is None:
            return

        robot.x, robot.y = target
        robot.set_path([])
        robot.route_goal = None
        robot.travel_history = []

    def _try_exit_maintenance(self, robot: Robot) -> None:
        if (robot.x, robot.y) not in self._maintenance_cells:
            return

        target = self._nearest_passable_cell(robot, {CellType.MAINTENANCE})
        if target is None:
            return

        robot.mode = RobotMode.MOVING
        robot.route_goal = target
        self._route_robot_to_cell(robot, target)

        if not robot.path:
            robot.mode = RobotMode.IDLE
            robot.route_goal = None

    # ------------------------------------------------------------------
    # v0.4 battery helpers
    # ------------------------------------------------------------------

    def _robot_is_loaded(self, robot: Robot) -> bool:
        if robot.current_task_id is None:
            return False

        task = self._tasks.get(robot.current_task_id)
        if task is None:
            return False

        return task.phase == TaskPhase.TO_DROPOFF

    def _consume_move_energy(self, robot: Robot) -> None:
        loaded = self._robot_is_loaded(robot)
        cost = self._battery_cfg.move_cost(loaded)
        battery = float(getattr(robot, "battery", self._battery_cfg.capacity))

        robot.battery = max(0.0, battery - cost)

        if hasattr(robot, "idle_ticks"):
            robot.idle_ticks = 0

    def _failed_robot_cells(
        self,
        exclude_robot_id: str | None = None,
    ) -> set[tuple[int, int]]:
        return {
            (robot.x, robot.y)
            for robot in self._robots.values()
            if robot.id != exclude_robot_id
            and getattr(robot, "mode", RobotMode.IDLE)
            in (RobotMode.FAILED, RobotMode.REPAIRING)
        }

    def _path_distance(
        self,
        start: tuple[int, int],
        goal: tuple[int, int],
        blocked_cells: set[tuple[int, int]] | None = None,
    ) -> int | None:
        blocked = set(blocked_cells or ())

        if goal in blocked:
            return None

        path = self._path_planner.find_path(
            self._warehouse,
            start,
            goal,
            blocked_cells=blocked,
        )

        if path is None:
            return None

        return len(path)

    def _remaining_task_energy(
        self,
        robot: Robot,
        task: Task,
    ) -> float | None:
        cfg = self._battery_cfg
        blocked = self._failed_robot_cells(exclude_robot_id=robot.id)

        try:
            pickup = self._warehouse.resolve(task.pickup)
            dropoff = self._warehouse.resolve(task.dropoff)
        except KeyError:
            return None

        if task.phase == TaskPhase.TO_PICKUP:
            d_to_pickup = self._path_distance((robot.x, robot.y), pickup, blocked)
            d_pickup_to_dropoff = self._path_distance(pickup, dropoff, blocked)

            if d_to_pickup is None or d_pickup_to_dropoff is None:
                return None

            empty_cost = d_to_pickup * cfg.empty_move_energy
            loaded_cost = d_pickup_to_dropoff * cfg.loaded_move_energy

            return empty_cost + loaded_cost

        if task.phase == TaskPhase.TO_DROPOFF:
            d_to_dropoff = self._path_distance((robot.x, robot.y), dropoff, blocked)

            if d_to_dropoff is None:
                return None

            return d_to_dropoff * cfg.loaded_move_energy

        return 0.0

    def _battery_feasible_for_new_task(self, robot: Robot, task: Task) -> bool:
        cfg = self._battery_cfg
        battery = float(getattr(robot, "battery", cfg.capacity))

        if cfg.is_critical(battery):
            return False

        energy = self._remaining_task_energy(robot, task)
        if energy is None:
            return False

        required = energy + cfg.safety_margin
        return battery >= required

    def _update_battery_checks(self) -> None:
        for robot in list(self._robots.values()):
            mode = getattr(robot, "mode", RobotMode.IDLE)

            if mode in (
                RobotMode.FAILED,
                RobotMode.REPAIRING,
                RobotMode.CHARGING,
            ):
                continue

            battery = float(getattr(robot, "battery", self._battery_cfg.capacity))

            if battery <= 0.0:
                self._handle_battery_depleted(robot)
                continue

            if mode in (
                RobotMode.WAITING_FOR_CHARGER,
                RobotMode.TO_CHARGER,
            ):
                continue

            if robot.current_task_id is not None:
                self._check_battery_for_active_task(robot)
            elif self._battery_cfg.is_critical(battery):
                self._enter_charging(robot, reason="critical_battery")

    def _check_battery_for_active_task(self, robot: Robot) -> None:
        if robot.current_task_id is None:
            return

        task = self._tasks.get(robot.current_task_id)
        if task is None:
            robot.current_task_id = None
            return

        battery = float(getattr(robot, "battery", self._battery_cfg.capacity))

        if battery <= 0.0:
            self._handle_battery_depleted(robot)
            return

        cfg = self._battery_cfg

        # If the robot is already at dropoff, allow completion instead of
        # interrupting on the final cell.
        if task.phase == TaskPhase.TO_DROPOFF:
            try:
                dropoff = self._warehouse.resolve(task.dropoff)
                if (robot.x, robot.y) == dropoff:
                    return
            except KeyError:
                pass

        if cfg.is_critical(battery):
            self._interrupt_current_task(robot, reason="critical_battery")
            self._enter_charging(robot, reason="critical_battery")
            return

        energy = self._remaining_task_energy(robot, task)
        if energy is None:
            self._interrupt_current_task(robot, reason="no_feasible_route")
            self._enter_charging(robot, reason="no_feasible_route")
            return

        required = energy + cfg.safety_margin
        if battery < required:
            self._interrupt_current_task(robot, reason="insufficient_for_task")
            self._enter_charging(robot, reason="insufficient_for_task")

    def _handle_battery_depleted(self, robot: Robot) -> None:
        mode = getattr(robot, "mode", RobotMode.IDLE)

        if mode in (
            RobotMode.FAILED,
            RobotMode.REPAIRING,
            RobotMode.CHARGING,
        ):
            return

        if robot.current_task_id is not None:
            self._interrupt_current_task(robot, reason="empty_battery")

        robot.battery = 0.0
        robot.mode = RobotMode.FAILED
        robot.status = RobotStatus.IDLE
        robot.set_path([])
        robot.route_goal = None
        robot.replanning = False
        robot.yielding_to = None
        robot.replan_cooldown = 0
        robot.blocked_ticks = 0

        robot.repair_remaining_ticks = max(
            1,
            int(self._battery_cfg.empty_battery_recovery_ticks),
        )

        self._charging_station.release(robot.id)
        self._conflict_manager.clear_conflicts_for_robot(robot)
        self._safe_metric("record_failed_robot_event")
        self._relocate_robot_to_maintenance(robot)
        self._conflict_manager.release_robot(robot.id)

    # ------------------------------------------------------------------
    # v0.4 task interruption / recovery
    # ------------------------------------------------------------------

    def _add_resume_location(
        self,
        task: Task,
        cell: tuple[int, int],
    ) -> str:
        name = f"RESUME-{task.id}"

        self._warehouse.locations[name] = Location(
            name=name,
            cell=cell,
            access=cell,
        )
        self._dynamic_location_names.add(name)
        task.resume_location_name = name
        return name

    def _interrupt_current_task(self, robot: Robot, reason: str) -> None:
        task_id = robot.current_task_id
        if task_id is None:
            return

        task = self._tasks.get(task_id)
        if task is None:
            robot.current_task_id = None
            return

        robot.interrupted_task_id = task.id

        if not hasattr(task, "interruption_count"):
            task.interruption_count = 0
        if not hasattr(task, "load_state"):
            task.load_state = LoadState.ON_SHELF

        task.last_assigned_robot_id = robot.id

        # Preserve logical load state.
        if task.phase == TaskPhase.TO_DROPOFF or task.load_state == LoadState.CARRIED:
            resume_name = self._add_resume_location(task, (robot.x, robot.y))
            task.pickup = resume_name
            task.load_state = LoadState.STAGED
        elif task.load_state == LoadState.STAGED:
            resume_name = getattr(task, "resume_location_name", None)
            if resume_name is not None and resume_name in self._warehouse.locations:
                task.pickup = resume_name
            else:
                resume_name = self._add_resume_location(task, (robot.x, robot.y))
                task.pickup = resume_name
            task.load_state = LoadState.STAGED
        else:
            task.load_state = LoadState.ON_SHELF

        task.status = INTERRUPTED_TASK_STATUS
        task.phase = TaskPhase.TO_PICKUP
        task.assigned_robot_id = None
        task.interruption_count += 1

        # Compatibility marker if TaskStatus.INTERRUPTED does not exist.
        setattr(task, "interrupted", True)

        robot.current_task_id = None
        robot.set_path([])
        robot.route_goal = None
        robot.replanning = False
        robot.yielding_to = None
        robot.blocked_ticks = 0
        robot.replan_cooldown = 0

        self._conflict_manager.clear_conflicts_for_robot(robot)

        if reason in (
            "critical_battery",
            "insufficient_for_task",
            "no_feasible_route",
            "empty_battery",
        ):
            self._safe_metric("record_battery_task_interruption")
        elif reason == "failure":
            self._safe_metric("record_failure_task_interruption")

    def _try_reclaim_interrupted_task(self, robot: Robot) -> None:
        task_id = getattr(robot, "interrupted_task_id", None)
        robot.interrupted_task_id = None

        if task_id is None:
            return

        task = self._tasks.get(task_id)
        if task is None:
            return

        if task.status != INTERRUPTED_TASK_STATUS:
            return

        if getattr(task, "interruption_count", 0) <= 0:
            return

        if task.assigned_robot_id is not None:
            return

        if not self._robot_can_accept_task(robot):
            return

        if not self._battery_feasible_for_new_task(robot, task):
            return

        self._begin_task(robot, task)

    # ------------------------------------------------------------------
    # v0.4 charging behavior
    # ------------------------------------------------------------------

    def _enter_charging(self, robot: Robot, reason: str) -> None:
        robot.current_task_id = None
        robot.set_path([])
        robot.replanning = False
        robot.yielding_to = None
        robot.blocked_ticks = 0
        robot.replan_cooldown = 0

        self._conflict_manager.clear_conflicts_for_robot(robot)

        station = self._charging_station
        station.release_reservation(robot.id)
        station.remove_waiting(robot.id)

        battery = float(getattr(robot, "battery", self._battery_cfg.capacity))

        if battery >= self._battery_cfg.capacity:
            robot.mode = RobotMode.IDLE
            robot.route_goal = None
            robot.charge_target = None
            return

        if station.has_capacity:
            cell = self._choose_free_charging_cell(robot)

            if cell is not None and station.reserve(robot.id, cell):
                robot.charge_target = cell
                robot.mode = RobotMode.TO_CHARGER

                if self._route_robot_to_cell(robot, cell):
                    if not robot.path:
                        self._handle_arrival(robot)
                    return

                station.release_reservation(robot.id)

        robot.mode = RobotMode.WAITING_FOR_CHARGER
        robot.status = RobotStatus.IDLE
        robot.route_goal = None
        robot.charge_target = None

        if not station.is_waiting(robot.id):
            station.add_waiting(robot.id)
            self._safe_metric("record_charger_wait_start")

        self._relocate_waiting_robot_off_charger(robot)

    def _enter_waiting_without_reservation(self, robot: Robot) -> None:
        robot.mode = RobotMode.WAITING_FOR_CHARGER
        robot.status = RobotStatus.IDLE
        robot.set_path([])
        robot.route_goal = None
        robot.charge_target = None

        station = self._charging_station
        if not station.is_waiting(robot.id):
            station.add_waiting(robot.id)
            self._safe_metric("record_charger_wait_start")

        self._relocate_waiting_robot_off_charger(robot)

    def _choose_free_charging_cell(
        self,
        robot: Robot,
    ) -> tuple[int, int] | None:
        station = self._charging_station
        occupied = self._occupied_cells(exclude_robot_id=robot.id)
        active_cells = set(station.active_cells.values())
        reserved_cells = set(station.reserved_cells.values())

        candidates = sorted(
            self._charging_cells,
            key=lambda cell: abs(cell[0] - robot.x) + abs(cell[1] - robot.y),
        )

        for cell in candidates:
            if cell in occupied:
                continue
            if cell in active_cells:
                continue
            if cell in reserved_cells:
                continue

            return cell

        return None

    def _handle_charging_arrival(self, robot: Robot) -> None:
        cell = robot.route_goal or (robot.x, robot.y)
        robot.set_path([])

        station = self._charging_station

        if cell not in self._charging_cells:
            station.release_reservation(robot.id)
            robot.mode = RobotMode.IDLE
            robot.route_goal = None
            robot.charge_target = None
            return

        occupied = self._occupied_cells(exclude_robot_id=robot.id)

        if cell in occupied:
            station.release_reservation(robot.id)
            self._enter_waiting_without_reservation(robot)
            return

        if station.begin_charging(robot.id, cell):
            robot.mode = RobotMode.CHARGING
            robot.status = RobotStatus.IDLE
            robot.charge_target = cell
            robot.charge_start_battery = robot.battery
            robot.route_goal = cell
            self._safe_metric("record_charging_start")
            return

        station.release_reservation(robot.id)
        self._enter_waiting_without_reservation(robot)

    def _update_charging_station(self) -> None:
        cfg = self._battery_cfg
        station = self._charging_station
        duration = station.charge_duration_ticks

        # Clean stale reservations.
        for robot_id in list(station.reserved_cells.keys()):
            robot = self._robots.get(robot_id)
            if robot is None:
                station.release_reservation(robot_id)
                continue

            mode = getattr(robot, "mode", RobotMode.IDLE)
            if mode not in (
                RobotMode.TO_CHARGER,
                RobotMode.WAITING_FOR_CHARGER,
            ):
                station.release_reservation(robot_id)

        # Progress active charging.
        for robot_id, remaining in list(station.active.items()):
            self._safe_metric("record_charging_tick")

            robot = self._robots.get(robot_id)
            if robot is None:
                continue

            start = getattr(robot, "charge_start_battery", None)
            if start is None:
                start = float(getattr(robot, "battery", cfg.capacity))

            elapsed = duration - remaining + 1
            progress = elapsed / duration

            robot.battery = min(
                cfg.capacity,
                start + (cfg.capacity - start) * progress,
            )

        finished_robot_ids = station.tick()

        for robot_id in finished_robot_ids:
            robot = self._robots.get(robot_id)
            if robot is None:
                continue

            robot.battery = cfg.capacity
            robot.mode = RobotMode.IDLE
            robot.status = RobotStatus.IDLE
            robot.charge_target = None
            robot.charge_start_battery = None
            robot.route_goal = None
            robot.idle_ticks = 0

            self._try_reclaim_interrupted_task(robot)

        self._update_charger_waiting()

    def _update_charger_waiting(self) -> None:
        station = self._charging_station

        for robot in sorted(self._robots.values(), key=lambda r: r.id):
            if getattr(robot, "mode", RobotMode.IDLE) != RobotMode.WAITING_FOR_CHARGER:
                continue

            # If a waiting robot is stood on a charging cell, try to charge
            # it immediately if possible. Otherwise move it off the cell.
            if (robot.x, robot.y) in self._charging_cells:
                if self._try_dispatch_waiting_robot(robot):
                    continue

                self._relocate_waiting_robot_off_charger(robot)

            robot.charger_wait_ticks = getattr(robot, "charger_wait_ticks", 0) + 1
            self._safe_metric("record_charger_wait_tick")

            if station.has_capacity:
                self._try_dispatch_waiting_robot(robot)

    def _try_dispatch_waiting_robot(self, robot: Robot) -> bool:
        station = self._charging_station
        if not station.has_capacity:
            return False

        current = (robot.x, robot.y)
        occupied = self._occupied_cells(exclude_robot_id=robot.id)

        # If the robot is already on a free charging cell, start charging now.
        if (
            current in self._charging_cells
            and current not in occupied
            and not station.is_cell_active(current)
        ):
            if station.begin_charging(robot.id, current):
                robot.mode = RobotMode.CHARGING
                robot.status = RobotStatus.IDLE
                robot.charge_target = current
                robot.charge_start_battery = robot.battery
                robot.route_goal = current
                station.remove_waiting(robot.id)
                self._safe_metric("record_charging_start")
                return True

        # Otherwise reserve a free charging cell and route to it.
        cell = self._choose_free_charging_cell(robot)
        if cell is None:
            return False

        if not station.reserve(robot.id, cell):
            return False

        station.remove_waiting(robot.id)
        robot.charge_target = cell
        robot.mode = RobotMode.TO_CHARGER

        if not self._route_robot_to_cell(robot, cell):
            station.release_reservation(robot.id)
            station.add_waiting(robot.id)
            robot.mode = RobotMode.WAITING_FOR_CHARGER
            robot.status = RobotStatus.IDLE
            robot.charge_target = None
            return False

        if not robot.path:
            self._handle_arrival(robot)

        return True

    def _update_idle_and_opportunistic_charging(self) -> None:
        cfg = self._battery_cfg
        station = self._charging_station

        for robot in list(self._robots.values()):
            if robot.current_task_id is not None:
                robot.idle_ticks = 0
                continue

            if robot.status != RobotStatus.IDLE:
                continue

            mode = getattr(robot, "mode", RobotMode.IDLE)
            if mode != RobotMode.IDLE:
                continue

            if station.is_charging(robot.id):
                continue

            if station.is_waiting(robot.id):
                continue

            robot.idle_ticks = getattr(robot, "idle_ticks", 0) + 1
            battery = float(getattr(robot, "battery", cfg.capacity))

            if (
                robot.idle_ticks >= cfg.idle_ticks_before_opportunistic_charge
                and cfg.is_opportunistic_candidate(battery)
                and station.has_capacity
                and self._choose_free_charging_cell(robot) is not None
            ):
                self._enter_charging(robot, reason="opportunistic")

    # ------------------------------------------------------------------
    # v0.4 failures / repairs
    # ------------------------------------------------------------------

    def _update_failures_and_repairs(self) -> None:
        self._update_robot_repairs()

        cfg = self._failure_cfg
        if not cfg.enabled or cfg.mtbf_ticks <= 0:
            return

        probability = 1.0 / max(1.0, float(cfg.mtbf_ticks))

        for robot in list(self._robots.values()):
            mode = getattr(robot, "mode", RobotMode.IDLE)

            if mode in (RobotMode.FAILED, RobotMode.REPAIRING):
                continue

            if self._failure_rng.random() < probability:
                self._fail_robot(robot)

    def _fail_robot(self, robot: Robot) -> None:
        if robot.current_task_id is not None:
            self._interrupt_current_task(robot, reason="failure")

        robot.mode = RobotMode.FAILED
        robot.status = RobotStatus.IDLE
        robot.set_path([])
        robot.route_goal = None
        robot.replanning = False
        robot.yielding_to = None
        robot.replan_cooldown = 0
        robot.blocked_ticks = 0

        robot.repair_remaining_ticks = max(
            1,
            int(self._failure_cfg.mttr_ticks),
        )

        self._charging_station.release(robot.id)
        self._conflict_manager.clear_conflicts_for_robot(robot)
        self._safe_metric("record_failed_robot_event")
        self._relocate_robot_to_maintenance(robot)
        self._conflict_manager.release_robot(robot.id)

    def _update_robot_repairs(self) -> None:
        for robot in list(self._robots.values()):
            if getattr(robot, "mode", RobotMode.IDLE) != RobotMode.FAILED:
                continue

            robot.repair_remaining_ticks = getattr(robot, "repair_remaining_ticks", 1) - 1
            self._safe_metric("record_failure_downtime_tick")

            if robot.repair_remaining_ticks <= 0:
                if float(getattr(robot, "battery", 0.0)) <= 0.0:
                    robot.battery = self._battery_cfg.capacity

                robot.mode = RobotMode.IDLE
                robot.status = RobotStatus.IDLE
                robot.repair_remaining_ticks = 0
                robot.idle_ticks = 0
                robot.set_path([])
                robot.route_goal = None

                self._try_reclaim_interrupted_task(robot)

                if (
                    getattr(robot, "mode", RobotMode.IDLE) == RobotMode.IDLE
                    and robot.status == RobotStatus.IDLE
                ):
                    self._try_exit_maintenance(robot)
