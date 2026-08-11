import copy
import threading
import time
from typing import Any

from .pathfinding import find_shortest_path
from .robot import Robot, RobotStatus
from .task import Task, TaskPhase, TaskStatus
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
    ) -> None:
        self._warehouse = warehouse
        self._tick_interval = tick_interval

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

        self.reset()

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
                    raise ValueError(f"Task {task.id} has a location outside bounds.")

                if self._warehouse.is_blocked(*point):
                    raise ValueError(f"Task {task.id} has a blocked location.")

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
            self._tick_count = 0

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
            }

    def _run(self) -> None:
        while not self._stop_event.is_set():
            if self._running_event.is_set():
                with self._lock:
                    self._tick()

                time.sleep(self._tick_interval)
            else:
                time.sleep(0.05)

    def _tick(self) -> None:
        # Extension point: replace direct assignment with a scheduling strategy.
        self._assign_pending_tasks()

        # Extension point: add collision avoidance or reservation checks here.
        for robot in list(self._robots.values()):
            if robot.path:
                arrived = robot.advance()

                if arrived:
                    self._handle_arrival(robot)

        self._assign_pending_tasks()
        self._tick_count += 1

    def _assign_pending_tasks(self) -> None:
        pending_tasks = [
            task for task in self._tasks.values() if task.status == TaskStatus.PENDING
        ]

        if not pending_tasks:
            return

        pending_iterator = iter(pending_tasks)

        for robot in self._robots.values():
            if robot.status != RobotStatus.IDLE:
                continue

            if robot.current_task_id is not None:
                continue

            try:
                task = next(pending_iterator)
            except StopIteration:
                break

            self._begin_task(robot, task)

    def _begin_task(self, robot: Robot, task: Task) -> None:
        task.status = TaskStatus.ASSIGNED
        task.assigned_robot_id = robot.id
        task.phase = TaskPhase.TO_PICKUP
        robot.current_task_id = task.id

        self._route_robot_to(robot, task, self._warehouse.resolve(task.pickup))

    def _route_robot_to(
        self,
        robot: Robot,
        task: Task,
        destination: tuple[int, int],
    ) -> None:
        path = find_shortest_path(self._warehouse, (robot.x, robot.y), destination)

        if path is None:
            # Extension point: handle unreachable tasks more gracefully.
            task.status = TaskStatus.FAILED
            task.phase = TaskPhase.DONE
            robot.current_task_id = None
            robot.set_path([])
            return

        robot.set_path(path)

        if not robot.path:
            self._handle_arrival(robot)

    def _handle_arrival(self, robot: Robot) -> None:
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
            self._route_robot_to(robot, task, self._warehouse.resolve(task.dropoff))
            return

        if task.phase == TaskPhase.TO_DROPOFF:
            task.status = TaskStatus.COMPLETED
            task.phase = TaskPhase.DONE
            robot.current_task_id = None
            robot.set_path([])
            return

        robot.current_task_id = None
        robot.set_path([])