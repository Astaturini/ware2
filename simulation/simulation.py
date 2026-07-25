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
        blocked_replan_seconds: float = 0.7,
        replan_cooldown_ticks: int = 7,
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

        self._active_conflict_yielder: dict[frozenset[str], str] = {}

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

            self._tick_count = 0
            self._active_conflict_yielder.clear()

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
        self._advance_robots()
        self._metrics.record_tick(list(self._robots.values()))
        
        self._prune_old_tasks()

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

        self._clear_conflicts_for_robot(robot)
        self._metrics.record_assigned(task, self._tick_count)
        self._route_robot_to(robot, task, robot.route_goal)

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

            if robot.replanning:
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

            previous_cell = (robot.x, robot.y)
            arrived = robot.advance()

            robot.travel_history.append(previous_cell)
            robot.blocked_ticks = 0

            occupied.discard(previous_cell)
            occupied.add((robot.x, robot.y))

            self._metrics.record_robot_move(robot)
            self._release_conflict(robot)

            if arrived:
                self._handle_arrival(robot)

    def _advance_replanning_robot(
        self,
        robot: Robot,
        occupied: set[tuple[int, int]],
    ) -> None:
        if not robot.path:
            self._complete_yield(robot)
            return

        next_cell = robot.current_target
        if next_cell is None:
            self._complete_yield(robot)
            return

        if next_cell in occupied:
            robot.blocked_ticks += 1
            self._metrics.record_blocked(robot)

            # If the temporary yield step is blocked, try another one quickly.
            if robot.blocked_ticks >= 2 and robot.replan_cooldown == 0:
                blocker = None

                if robot.yielding_to is not None:
                    blocker = self._robots.get(robot.yielding_to)

                if blocker is None:
                    self._complete_yield(robot)
                    return

                step = self._choose_yield_step(robot, blocker, occupied)

                if step is not None:
                    robot.set_path([step])
                    robot.blocked_ticks = 0
                    robot.replan_cooldown = self._replan_cooldown_ticks
                    return

            return

        previous_cell = (robot.x, robot.y)
        robot.advance()

        robot.travel_history.append(previous_cell)
        robot.blocked_ticks = 0

        occupied.discard(previous_cell)
        occupied.add((robot.x, robot.y))

        self._metrics.record_robot_move(robot)
        self._release_conflict(robot)

        if not robot.path:
            self._complete_yield(robot)

    def _complete_yield(self, robot: Robot) -> None:
        self._release_conflict(robot)

        robot.replanning = False
        robot.set_path([])

        if robot.current_task_id is not None:
            robot.status = RobotStatus.MOVING

        if robot.current_task_id is not None and robot.route_goal is not None:
            self._attempt_resume_route(robot)

    # ------------------------------------------------------------------
    # Blocking / conflict handling
    # ------------------------------------------------------------------

    def _handle_blocked_robot(
        self,
        robot: Robot,
        next_cell: tuple[int, int],
    ) -> None:
        blocker = self._robot_at(next_cell, exclude_robot_id=robot.id)

        if blocker is None:
            robot.blocked_ticks += 1
            self._metrics.record_blocked(robot)

            if (
                robot.blocked_ticks >= self._blocked_replan_threshold_ticks
                and robot.replan_cooldown == 0
            ):
                self._attempt_resume_route(robot)

            return

        pair_key = frozenset({robot.id, blocker.id})
        active_yielder = self._active_conflict_yielder.get(pair_key)

        robot.blocked_ticks += 1
        self._metrics.record_blocked(robot)

        if active_yielder is not None:
            # This robot is already the selected yielder.
            if active_yielder == robot.id:
                if not robot.replanning:
                    self._active_conflict_yielder.pop(pair_key, None)

                    if self._can_yield(robot):
                        self._make_robot_yield(robot, blocker, pair_key)

                return

            # The other robot is the selected yielder.
            yielder_robot = self._robots.get(active_yielder)

            if yielder_robot is not None:
                # If the selected yielder appears inactive for too long,
                # let this robot take over to avoid a long deadlock.
                if (
                    robot.blocked_ticks >= self._blocked_replan_threshold_ticks * 3
                    and not yielder_robot.replanning
                    and self._can_yield(robot)
                ):
                    self._active_conflict_yielder.pop(pair_key, None)
                    self._make_robot_yield(robot, blocker, pair_key)

                return

            # Stale record.
            self._active_conflict_yielder.pop(pair_key, None)

        if robot.blocked_ticks < self._blocked_replan_threshold_ticks:
            return

        preferred_yielder = self._select_yielding_robot(robot, blocker)

        # The other robot should yield.
        if preferred_yielder.id == blocker.id:
            # If the blocker is stationary or already blocked enough, force it to yield.
            if (
                not blocker.path
                or blocker.blocked_ticks >= self._blocked_replan_threshold_ticks
            ) and self._can_yield(blocker):
                if self._make_robot_yield(blocker, robot, pair_key):
                    return

            # Fallback: if the blocker cannot or will not yield quickly enough,
            # this robot yields to avoid a long deadlock.
            if self._can_yield(robot) and (
                not blocker.path
                or blocker.replan_cooldown > 0
                or robot.blocked_ticks >= self._blocked_replan_threshold_ticks + 2
            ):
                self._make_robot_yield(robot, blocker, pair_key)

            return

        # This robot is the preferred yielder.
        if self._can_yield(robot):
            self._make_robot_yield(robot, blocker, pair_key)

    def _make_robot_yield(
        self,
        robot: Robot,
        blocker: Robot,
        pair_key: frozenset[str],
    ) -> bool:
        if not self._can_yield(robot):
            return False

        occupied = self._occupied_cells(exclude_robot_id=robot.id)

        step = self._choose_yield_step(robot, blocker, occupied)

        if step is None:
            # Small delay to avoid repeatedly trying impossible local moves.
            robot.replan_cooldown = 1
            return False

        self._active_conflict_yielder[pair_key] = robot.id

        robot.replanning = True
        robot.yielding_to = blocker.id

        robot.set_path([step])
        robot.blocked_ticks = 0
        robot.replan_cooldown = self._replan_cooldown_ticks

        self._metrics.record_replan(robot)
        self._metrics.record_deadlock_resolution()

        return True

    # ------------------------------------------------------------------
    # Priority-based yielding
    # ------------------------------------------------------------------

    def _select_yielding_robot(self, robot: Robot, blocker: Robot) -> Robot:
        robot_score = self._yield_score(robot)
        blocker_score = self._yield_score(blocker)

        # Higher score means more willing to yield.
        if robot_score != blocker_score:
            return robot if robot_score > blocker_score else blocker

        # If priority scoring cannot decide, use blocked time.
        if robot.blocked_ticks != blocker.blocked_ticks:
            return robot if robot.blocked_ticks > blocker.blocked_ticks else blocker

        # Final deterministic tie-break.
        return robot if robot.id < blocker.id else blocker

    def _yield_score(self, robot: Robot) -> int:
        """Return how willing this robot is to yield.

        Higher score = more willing to yield.

        Priority convention:
        - Lower task.priority value = higher urgency.
        - Therefore larger priority numbers yield more easily.
        """

        if robot.current_task_id is None:
            return 10_000

        task = self._tasks.get(robot.current_task_id)
        if task is None:
            return 10_000

        priority = int(getattr(task, "priority", 0) or 0)

        # One priority level is worth 20 points.
        priority_pressure = max(0, min(priority, 10)) * 20

        # One blocked tick is worth 10 points.
        # Two blocked ticks can overcome one priority level.
        blocked_pressure = min(robot.blocked_ticks, 20) * 10

        return priority_pressure + blocked_pressure

    def _robot_is_in_active_conflict(self, robot_id: str) -> bool:
        for pair_key in self._active_conflict_yielder.keys():
            if robot_id in pair_key:
                return True

        return False

    def _can_yield(self, robot: Robot) -> bool:
        return (
            not robot.replanning
            and robot.replan_cooldown == 0
            and not self._robot_is_in_active_conflict(robot.id)
        )

    # ------------------------------------------------------------------
    # Local yield-step selection
    # ------------------------------------------------------------------

    def _choose_yield_step(
        self,
        robot: Robot,
        blocker: Robot,
        occupied: set[tuple[int, int]],
    ) -> tuple[int, int] | None:
        current = (robot.x, robot.y)

        claimed = self._claimed_cells(exclude_robot_id=robot.id)
        blocked = occupied | claimed
        blocked.discard(current)

        safe_neighbors: list[tuple[int, int]] = []

        for neighbor in (
            (robot.x + 1, robot.y),
            (robot.x - 1, robot.y),
            (robot.x, robot.y + 1),
            (robot.x, robot.y - 1),
        ):
            if not self._warehouse.in_bounds(*neighbor):
                continue

            if self._warehouse.is_blocked(*neighbor):
                continue

            if neighbor in blocked:
                continue

            safe_neighbors.append(neighbor)

        if not safe_neighbors:
            return None

        goal = robot.route_goal

        # 1. Prefer a local step that still allows reaching the current goal.
        if goal is not None and goal != current and goal not in blocked:
            best_neighbor = None
            best_distance = None

            for neighbor in safe_neighbors:
                path = find_shortest_path(
                    self._warehouse,
                    neighbor,
                    goal,
                    blocked_cells=blocked - {neighbor},
                )

                if path is not None:
                    distance = abs(neighbor[0] - goal[0]) + abs(neighbor[1] - goal[1])

                    if best_distance is None or distance < best_distance:
                        best_neighbor = neighbor
                        best_distance = distance

            if best_neighbor is not None:
                return best_neighbor

        # 2. Prefer backtracking through recently visited cells.
        safe_set = set(safe_neighbors)
        history = robot.travel_history[-32:]

        for target in reversed(history):
            if target == current:
                continue

            if target in blocked:
                continue

            if not self._warehouse.in_bounds(*target):
                continue

            if self._warehouse.is_blocked(*target):
                continue

            if target in safe_set:
                return target

            path = find_shortest_path(
                self._warehouse,
                current,
                target,
                blocked_cells=blocked - {current},
            )

            if path and path[0] in safe_set:
                return path[0]

        # 3. Last resort: escape locally, preferably away from the blocker.
        blocker_position = (blocker.x, blocker.y)

        def escape_score(cell: tuple[int, int]) -> tuple[int, int]:
            away_from_blocker = -(
                abs(cell[0] - blocker_position[0])
                + abs(cell[1] - blocker_position[1])
            )

            if goal is not None:
                toward_goal = abs(cell[0] - goal[0]) + abs(cell[1] - goal[1])
            else:
                toward_goal = 0

            return toward_goal, away_from_blocker

        safe_neighbors.sort(key=escape_score)
        return safe_neighbors[0]

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

        path = find_shortest_path(
            self._warehouse,
            current,
            goal,
            blocked_cells=blocked,
        )

        # If claims make the route temporarily impossible, try again using only
        # physically occupied cells. The first step is still rejected if claimed.
        if path is None or (path and path[0] in claimed):
            fallback = find_shortest_path(
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

            self._clear_conflicts_for_robot(robot)
            robot.set_path([])
            return

        robot.set_path(path)
        robot.replanning = False
        robot.yielding_to = None

        if not robot.path:
            self._handle_arrival(robot)

    def _handle_arrival(self, robot: Robot) -> None:
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

            self._clear_conflicts_for_robot(robot)

            robot.travel_history = []
            robot.set_path([])
            return

        robot.current_task_id = None
        robot.route_goal = None
        robot.blocked_ticks = 0
        robot.replan_cooldown = 0

        self._clear_conflicts_for_robot(robot)

        robot.travel_history = []
        robot.set_path([])

    # ------------------------------------------------------------------
    # Conflict state helpers
    # ------------------------------------------------------------------

    def _release_conflict(self, robot: Robot) -> None:
        if robot.yielding_to is None:
            return

        pair_key = frozenset({robot.id, robot.yielding_to})

        if self._active_conflict_yielder.get(pair_key) == robot.id:
            del self._active_conflict_yielder[pair_key]

        robot.replanning = False
        robot.yielding_to = None

    def _clear_conflicts_for_robot(self, robot: Robot) -> None:
        for pair_key, yielder_id in list(self._active_conflict_yielder.items()):
            if robot.id not in pair_key:
                continue

            self._active_conflict_yielder.pop(pair_key, None)

            if yielder_id == robot.id:
                robot.replanning = False
                robot.yielding_to = None
            else:
                other = self._robots.get(yielder_id)

                # If the other yielder has no temporary movement left, clear it.
                # If it still has a path, let it finish that local maneuver.
                if other is not None and not other.path:
                    other.replanning = False
                    other.yielding_to = None

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
    
    # prune older than last 100 tasks
    def _prune_old_tasks(self) -> None:
        """Remove completed or failed tasks older than 100 ticks
            to prevent memory/UI bloat."""
        current_tick = self._tick_count
        max_age = 100  # Keep completed tasks in UI for ~30 seconds (at 0.3s/tick)
        
        to_delete = [
            task_id for task_id, task in self._tasks.items()
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
            and task.completed_at is not None
            and (current_tick - task.completed_at) > max_age
        ]
        
        for task_id in to_delete:
            del self._tasks[task_id]
    