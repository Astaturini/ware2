import copy
import threading
import time
from typing import Any

from .metrics import Metrics
from .scheduler import CostBasedScheduler, Scheduler
from .pathfinding import find_shortest_path
from .robot import Robot, RobotStatus
from .task import Task, TaskPhase, TaskStatus
from .task_generator import TaskGenerator
from .warehouse import Warehouse


class Simulation:
    """Thread-safe simulation engine.

    This class owns the simulation state and advances it using a fixed tick.
    It does not depend on Flask.
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
        blocked_replan_seconds: float = 2.0,
        replan_cooldown_ticks: int = 5,
    ) -> None:
        self._warehouse = warehouse
        self._tick_interval = tick_interval
        self._scheduler = scheduler or CostBasedScheduler()
        self._task_generator = task_generator
        self._metrics = metrics or Metrics()

        self._blocked_replan_threshold_ticks = max(
            1,
            int(round(blocked_replan_seconds / tick_interval)),
        )
        self._replan_cooldown_ticks = max(1, replan_cooldown_ticks)

        # If a conflict remains active for too long, swap the yielding robot.
        # This prevents two robots from waiting forever when the first yielder
        # has no useful local move.
        self._max_conflict_age_ticks = max(
            20,
            self._blocked_replan_threshold_ticks * 4,
        )

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

        # Active conflict records.
        #
        # key: frozenset({robot_id_a, robot_id_b})
        # value:
        # {
        #     "yielder": robot_id,
        #     "blocker": robot_id,
        #     "created_tick": int,
        #     "last_tick": int,
        #     "replan_counted": bool,
        # }
        self._active_conflicts: dict[frozenset[str], dict[str, Any]] = {}

        self.reset()

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

            for robot in self._robots.values():
                robot.blocked_ticks = 0
                robot.replan_cooldown = 0
                robot.replanning = False
                robot.yielding_to = None
                robot.travel_history = []
                robot.temporary_path = False

            self._tick_count = 0
            self._active_conflicts.clear()

            self._metrics.reset()
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
            return {
                "paused": self.is_paused,
                "tick": self._tick_count,
                "warehouse": self._warehouse.to_dict(),
                "robots": [robot.to_dict() for robot in self._robots.values()],
                "tasks": [task.to_dict() for task in self._tasks.values()],
                "metrics": self._metrics.to_dict(self._tick_interval),
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
        if self._task_generator is not None:
            new_tasks = self._task_generator.step(self._tick_count)
            for task in new_tasks:
                self._tasks[task.id] = task
                self._metrics.record_generated(task)

        self._assign_pending_tasks()

        # Watchdog for conflicts that have lived too long.
        self._watchdog_conflicts()

        self._advance_robots()
        self._metrics.record_tick(list(self._robots.values()))

        self._tick_count += 1

    # ------------------------------------------------------------------
    # Task assignment
    # ------------------------------------------------------------------

    def _assign_pending_tasks(self) -> None:
        pending_tasks = [
            task for task in self._tasks.values() if task.status == TaskStatus.PENDING
        ]

        if not pending_tasks:
            return

        assignments = self._scheduler.select_assignments(
            pending_tasks,
            list(self._robots.values()),
            self._warehouse,
            blocked_cells=self._occupied_cells(),
        )

        for assignment in assignments:
            task = self._tasks.get(assignment.task_id)
            robot = self._robots.get(assignment.robot_id)

            if task is None or robot is None:
                continue

            if task.status != TaskStatus.PENDING:
                continue

            if robot.status != RobotStatus.IDLE or robot.current_task_id is not None:
                continue

            self._begin_task(robot, task)

    def _begin_task(self, robot: Robot, task: Task) -> None:
        task.status = TaskStatus.ASSIGNED
        task.assigned_robot_id = robot.id
        task.phase = TaskPhase.TO_PICKUP

        robot.current_task_id = task.id
        robot.travel_history = []
        robot.route_goal = self._warehouse.resolve(task.pickup)

        robot.replanning = False
        robot.yielding_to = None
        robot.blocked_ticks = 0
        robot.temporary_path = False

        self._clear_conflicts_for_robot(robot)
        self._metrics.record_assigned(task, self._tick_count)
        self._route_robot_to(robot, task, robot.route_goal)

    # ------------------------------------------------------------------
    # Robot movement
    # ------------------------------------------------------------------

    def _advance_robots(self) -> None:
        occupied = self._occupied_cells()

        # Yielding/replanning robots move first so that frozen blocker robots
        # can immediately use cells that were just cleared.
        ordered_robots = sorted(
            self._robots.values(),
            key=lambda robot: (0 if (robot.replanning or robot.temporary_path) else 1, robot.id),
        )

        for robot in ordered_robots:
            if robot.replan_cooldown > 0:
                robot.replan_cooldown -= 1

            if robot.replanning or robot.temporary_path:
                if not robot.replanning:
                    robot.replanning = True

                self._advance_replanning_robot(robot, occupied)
                continue

            if not robot.path:
                if robot.current_task_id is not None and robot.route_goal is not None:
                    self._attempt_resume_route(robot)
                continue

            next_cell = robot.current_target
            if next_cell is None:
                continue

            if next_cell in occupied:
                self._handle_blocked_robot(robot, next_cell)
                continue

            arrived = self._move_robot(robot, occupied)

            # If this robot was the frozen blocker in an active conflict,
            # the conflict is now resolved because it has moved.
            self._release_blocker_conflicts(robot)

            if arrived:
                self._handle_arrival(robot)

    def _move_robot(self, robot: Robot, occupied: set[tuple[int, int]]) -> bool:
        previous_cell = (robot.x, robot.y)

        arrived = robot.advance()

        robot.travel_history.append(previous_cell)
        if len(robot.travel_history) > 256:
            robot.travel_history.pop(0)

        robot.blocked_ticks = 0

        occupied.discard(previous_cell)
        occupied.add((robot.x, robot.y))

        self._metrics.record_robot_move(robot)
        return arrived

    def _advance_replanning_robot(
        self,
        robot: Robot,
        occupied: set[tuple[int, int]],
    ) -> None:
        if not robot.path:
            if not self._try_assign_yield_path_from_active_conflict(robot):
                self._complete_yield(robot)
                return

        next_cell = robot.current_target
        if next_cell is None:
            self._complete_yield(robot)
            return

        if next_cell in occupied:
            robot.blocked_ticks += 1
            self._metrics.record_blocked(robot)

            # If the temporary yield move is already blocked, try another
            # local move after a very short retry delay.
            if robot.blocked_ticks >= 2 and robot.replan_cooldown == 0:
                blocker = None
                if robot.yielding_to is not None:
                    blocker = self._robots.get(robot.yielding_to)

                if blocker is not None and self._choose_and_assign_yield_step(robot, blocker):
                    next_cell = robot.current_target

                    if next_cell is None:
                        self._complete_yield(robot)
                        return

                    if next_cell in occupied:
                        return
                else:
                    return
            else:
                return

        arrived = self._move_robot(robot, occupied)

        # A yielding robot may also be the blocker in another conflict.
        self._release_blocker_conflicts(robot)

        if arrived or not robot.path:
            self._complete_yield(robot)

    # ------------------------------------------------------------------
    # Blocking / conflict handling
    # ------------------------------------------------------------------

    def _handle_blocked_robot(
        self,
        robot: Robot,
        next_cell: tuple[int, int],
    ) -> None:
        blocker = self._robot_at(next_cell, exclude_robot_id=robot.id)

        robot.blocked_ticks += 1
        self._metrics.record_blocked(robot)

        if blocker is None:
            # Blocked by something other than another robot. This should be
            # rare, but attempt a normal route refresh after the timeout.
            if (
                robot.blocked_ticks >= self._blocked_replan_threshold_ticks
                and robot.replan_cooldown == 0
            ):
                self._attempt_resume_route(robot)
            return

        # If this robot is currently frozen as the blocker in another active
        # conflict, do not allow it to replan here.
        if self._robot_is_blocker(robot.id):
            return

        pair_key = frozenset({robot.id, blocker.id})
        info = self._active_conflicts.get(pair_key)

        if info is not None:
            info["last_tick"] = self._tick_count

            # Frozen blocker: do not replan.
            if info["blocker"] == robot.id:
                return

            # This robot is the active yielder.
            robot.replanning = True
            robot.yielding_to = blocker.id

            if robot.replan_cooldown > 0:
                return

            # If the yielder's current next move is still blocked, choose a
            # different local yield move.
            current_target = robot.current_target
            if current_target is None or current_target in self._occupied_cells(
                exclude_robot_id=robot.id
            ):
                self._choose_and_assign_yield_step(robot, blocker)

            return

        # No active conflict for this pair yet.
        preferred_yielder = self._select_yielding_robot(robot, blocker)

        # Only the selected robot may start yielding. The other robot waits.
        if preferred_yielder.id != robot.id:
            return

        if robot.replan_cooldown > 0:
            return

        if robot.blocked_ticks < self._blocked_replan_threshold_ticks:
            return

        self._make_robot_yield(robot, blocker)

    def _select_yielding_robot(self, robot: Robot, blocker: Robot) -> Robot:
        # Prefer yielding robots without tasks if one robot is idle.
        if robot.current_task_id is None and blocker.current_task_id is not None:
            return robot

        if blocker.current_task_id is None and robot.current_task_id is not None:
            return blocker

        # Prefer the robot that has been blocked longer.
        if robot.blocked_ticks != blocker.blocked_ticks:
            return robot if robot.blocked_ticks > blocker.blocked_ticks else blocker

        # Deterministic tie-break.
        return robot if robot.id < blocker.id else blocker

    def _robot_is_blocker(self, robot_id: str) -> bool:
        return any(
            info.get("blocker") == robot_id
            for info in self._active_conflicts.values()
        )

    def _make_robot_yield(self, robot: Robot, blocker: Robot) -> bool:
        pair_key = self._register_conflict(robot, blocker)

        robot.replanning = True
        robot.yielding_to = blocker.id

        success = self._choose_and_assign_yield_step(robot, blocker)

        if success:
            robot.replan_cooldown = self._replan_cooldown_ticks

            info = self._active_conflicts.get(pair_key)
            if info is not None and not info.get("replan_counted", False):
                self._metrics.record_replan(robot)
                info["replan_counted"] = True

        return success

    def _force_yield(self, robot: Robot, blocker: Robot) -> bool:
        """Used by the watchdog to swap yielder roles after a long deadlock."""
        pair_key = self._register_conflict(robot, blocker)

        robot.replanning = True
        robot.yielding_to = blocker.id
        robot.blocked_ticks = 0

        success = self._choose_and_assign_yield_step(robot, blocker)

        robot.replan_cooldown = self._replan_cooldown_ticks

        info = self._active_conflicts.get(pair_key)
        if info is not None and success and not info.get("replan_counted", False):
            self._metrics.record_replan(robot)
            info["replan_counted"] = True

        return success

    def _register_conflict(self, yielder: Robot, blocker: Robot) -> frozenset[str]:
        pair_key = frozenset({yielder.id, blocker.id})

        info = self._active_conflicts.get(pair_key)
        if info is not None:
            info["yielder"] = yielder.id
            info["blocker"] = blocker.id
            info["last_tick"] = self._tick_count
            return pair_key

        self._active_conflicts[pair_key] = {
            "yielder": yielder.id,
            "blocker": blocker.id,
            "created_tick": self._tick_count,
            "last_tick": self._tick_count,
            "replan_counted": False,
        }

        return pair_key

    def _watchdog_conflicts(self) -> None:
        for pair_key, info in list(self._active_conflicts.items()):
            created_tick = info.get("created_tick", self._tick_count)

            if self._tick_count - created_tick < self._max_conflict_age_ticks:
                continue

            yielder_id = info.get("yielder")
            blocker_id = info.get("blocker")
            if not isinstance(yielder_id, str) or not isinstance(blocker_id, str):
                self._clear_conflict(pair_key, resume_yielder=True)
                continue

            yielder = self._robots.get(yielder_id)
            blocker = self._robots.get(blocker_id)

            if yielder is None or blocker is None:
                self._clear_conflict(pair_key, resume_yielder=True)
                continue

            # Stop the old yielder.
            self._clear_conflict(pair_key, resume_yielder=False)

            yielder.replanning = False
            yielder.yielding_to = None
            yielder.temporary_path = False
            yielder.set_path([])

            if yielder.current_task_id is not None and yielder.route_goal is not None:
                self._attempt_resume_route(yielder)

            # Swap roles: the old blocker now yields.
            self._force_yield(blocker, yielder)

    # ------------------------------------------------------------------
    # Local yield path selection
    # ------------------------------------------------------------------

    def _try_assign_yield_path_from_active_conflict(self, robot: Robot) -> bool:
        for info in self._active_conflicts.values():
            if info.get("yielder") != robot.id:
                continue

            blocker_id = info.get("blocker")
            if not isinstance(blocker_id, str):
                continue

            blocker = self._robots.get(blocker_id)
            if blocker is None:
                continue

            robot.yielding_to = blocker.id
            return self._choose_and_assign_yield_step(robot, blocker)

        return False

    def _choose_and_assign_yield_step(self, robot: Robot, blocker: Robot) -> bool:
        blocked = self._local_blocked_cells(robot)
        current = (robot.x, robot.y)

        safe_neighbors: list[tuple[int, int]] = []

        for neighbor in self._neighbors(current):
            if neighbor in blocked:
                continue

            if not self._warehouse.in_bounds(*neighbor):
                continue

            if self._warehouse.is_blocked(*neighbor):
                continue

            safe_neighbors.append(neighbor)

        if not safe_neighbors:
            return False

        goal = robot.route_goal

        # 1. Prefer a local move that still allows reaching the current goal.
        #
        # This checks the next move first, then verifies that a path exists
        # from that next cell to the task destination.
        if goal is not None and goal != current and goal not in blocked:
            def goal_distance(cell: tuple[int, int]) -> int:
                return abs(cell[0] - goal[0]) + abs(cell[1] - goal[1])

            for neighbor in sorted(safe_neighbors, key=goal_distance):
                path = find_shortest_path(
                    self._warehouse,
                    neighbor,
                    goal,
                    blocked_cells=blocked - {neighbor},
                )

                if path is not None:
                    robot.set_temporary_path([neighbor])
                    robot.replanning = True
                    robot.temporary_path = True
                    robot.blocked_ticks = 0
                    return True

        # 2. Backtrack toward a previously visited cell.
        backtrack_step = self._choose_backtrack_step(robot, safe_neighbors, blocked)
        if backtrack_step is not None:
            robot.set_temporary_path([backtrack_step])
            robot.replanning = True
            robot.temporary_path = True
            robot.blocked_ticks = 0
            return True

        # 3. Last resort: any locally safe neighbor, preferably away from the
        # blocker and still biased toward the goal.
        blocker_position = (blocker.x, blocker.y)

        def last_resort_score(cell: tuple[int, int]) -> tuple[int, int]:
            if goal is not None:
                toward_goal = abs(cell[0] - goal[0]) + abs(cell[1] - goal[1])
            else:
                toward_goal = 0

            away_from_blocker = -(
                abs(cell[0] - blocker_position[0])
                + abs(cell[1] - blocker_position[1])
            )

            return toward_goal, away_from_blocker

        for neighbor in sorted(safe_neighbors, key=last_resort_score):
            robot.set_temporary_path([neighbor])
            robot.replanning = True
            robot.temporary_path = True
            robot.blocked_ticks = 0
            return True

        return False

    def _choose_backtrack_step(
        self,
        robot: Robot,
        safe_neighbors: list[tuple[int, int]],
        blocked: set[tuple[int, int]],
    ) -> tuple[int, int] | None:
        current = (robot.x, robot.y)
        safe_set = set(safe_neighbors)

        # Recent history first.
        history = robot.travel_history[-48:]

        for target in reversed(history):
            if target == current:
                continue

            if target in blocked:
                continue

            if not self._warehouse.in_bounds(*target):
                continue

            if self._warehouse.is_blocked(*target):
                continue

            # Direct adjacent backtrack move.
            if target in safe_set:
                return target

            # Otherwise, take the first step toward a reachable historical cell.
            path = find_shortest_path(
                self._warehouse,
                current,
                target,
                blocked_cells=blocked - {current},
            )

            if not path:
                continue

            first_step = path[0]
            if first_step in safe_set:
                return first_step

        return None

    def _local_blocked_cells(self, robot: Robot) -> set[tuple[int, int]]:
        """Cells treated as blocked for local yield-step validation."""
        blocked = self._occupied_cells(exclude_robot_id=robot.id)

        # Also avoid cells that other robots are about to enter.
        for other in self._robots.values():
            if other.id == robot.id:
                continue

            target = other.current_target
            if target is not None:
                blocked.add(target)

        blocked.discard((robot.x, robot.y))
        return blocked

    def _neighbors(self, cell: tuple[int, int]) -> tuple[tuple[int, int], ...]:
        x, y = cell
        return (
            (x + 1, y),
            (x - 1, y),
            (x, y + 1),
            (x, y - 1),
        )

    # ------------------------------------------------------------------
    # Conflict clearing
    # ------------------------------------------------------------------

    def _clear_conflict(
        self,
        pair_key: frozenset[str],
        resume_yielder: bool = False,
    ) -> None:
        info = self._active_conflicts.pop(pair_key, None)
        if info is None:
            return

        self._metrics.record_deadlock_resolution()

        yielder_id = info.get("yielder")
        if not isinstance(yielder_id, str):
            return

        yielder = self._robots.get(yielder_id)
        if yielder is not None:
            yielder.yielding_to = None

            if resume_yielder and not yielder.path:
                yielder.replanning = False
                yielder.temporary_path = False

                if (
                    yielder.current_task_id is not None
                    and yielder.route_goal is not None
                ):
                    self._attempt_resume_route(yielder)

    def _clear_conflicts_where_yielder(self, robot: Robot) -> None:
        for pair_key, info in list(self._active_conflicts.items()):
            if info.get("yielder") == robot.id:
                self._clear_conflict(pair_key, resume_yielder=False)

    def _release_blocker_conflicts(self, robot: Robot) -> None:
        for pair_key, info in list(self._active_conflicts.items()):
            if info.get("blocker") == robot.id:
                self._clear_conflict(pair_key, resume_yielder=True)

    def _clear_conflicts_for_robot(self, robot: Robot) -> None:
        for pair_key, info in list(self._active_conflicts.items()):
            if robot.id in (info.get("yielder"), info.get("blocker")):
                self._clear_conflict(pair_key, resume_yielder=False)

    # Kept for compatibility with older internal call sites.
    def _release_conflict(self, robot: Robot) -> None:
        self._clear_conflicts_for_robot(robot)

    def _complete_yield(self, robot: Robot) -> None:
        self._clear_conflicts_where_yielder(robot)

        robot.replanning = False
        robot.yielding_to = None
        robot.temporary_path = False
        robot.set_path([])

        if robot.current_task_id is not None:
            robot.status = RobotStatus.MOVING

            if robot.route_goal is not None:
                self._attempt_resume_route(robot)
        else:
            robot.status = RobotStatus.IDLE

    # ------------------------------------------------------------------
    # Routing
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

        path = find_shortest_path(
            self._warehouse,
            current,
            goal,
            blocked_cells=blocked,
        )

        # If claims make the route temporarily impossible, try again using only
        # physically occupied cells. The first step is still rejected if it is
        # claimed by another robot.
        if path is None:
            path = find_shortest_path(
                self._warehouse,
                current,
                goal,
                blocked_cells=occupied,
            )

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
        robot.temporary_path = False
        robot.blocked_ticks = 0

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

        path = find_shortest_path(
            self._warehouse,
            (robot.x, robot.y),
            destination,
            blocked_cells=blocked_cells,
        )

        if path is None:
            path = find_shortest_path(
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
            robot.replanning = False
            robot.yielding_to = None
            robot.temporary_path = False

            self._clear_conflicts_for_robot(robot)
            robot.set_path([])
            return

        robot.set_path(path)
        robot.replanning = False
        robot.yielding_to = None
        robot.temporary_path = False

        if not robot.path:
            self._handle_arrival(robot)

    def _handle_arrival(self, robot: Robot) -> None:
        robot.temporary_path = False
        robot.replanning = False
        robot.yielding_to = None

        self._clear_conflicts_for_robot(robot)

        if robot.current_task_id is None:
            robot.set_path([])
            return

        task = self._tasks.get(robot.current_task_id)

        if task is None:
            robot.current_task_id = None
            robot.set_path([])
            return

        if task.phase == TaskPhase.TO_PICKUP:
            task.phase = TaskPhase.TO_DROPOFF

            robot.blocked_ticks = 0
            robot.travel_history = []

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

            self._metrics.record_completed(task, self._tick_count)

            robot.current_task_id = None
            robot.route_goal = None
            robot.blocked_ticks = 0
            robot.replan_cooldown = 0
            robot.travel_history = []
            robot.temporary_path = False

            self._clear_conflicts_for_robot(robot)
            robot.set_path([])
            return

        robot.current_task_id = None
        robot.route_goal = None
        robot.blocked_ticks = 0
        robot.replan_cooldown = 0
        robot.travel_history = []
        robot.temporary_path = False

        self._clear_conflicts_for_robot(robot)
        robot.set_path([])

    # ------------------------------------------------------------------
    # Geometry / occupancy helpers
    # ------------------------------------------------------------------

    def _occupied_cells(self, exclude_robot_id: str | None = None) -> set[tuple[int, int]]:
        return {
            (robot.x, robot.y)
            for robot in self._robots.values()
            if robot.id != exclude_robot_id
        }

    def _claimed_cells(self, exclude_robot_id: str | None = None) -> set[tuple[int, int]]:
        claimed: set[tuple[int, int]] = set()

        for robot in self._robots.values():
            if robot.id == exclude_robot_id:
                continue

            target = robot.current_target
            if target is not None:
                claimed.add(target)

        return claimed

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

    # Kept for possible future priority-aware logic.
    def _task_priority(self, task_id: str | None) -> int:
        if task_id is None:
            return -1

        task = self._tasks.get(task_id)
        if task is None:
            return -1

        return task.priority