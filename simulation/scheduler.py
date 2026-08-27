from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .pathfinding import BFSPathPlanner, PathPlanner
from .robot import Robot, RobotStatus
from .task import Task
from .warehouse import Warehouse


@dataclass(frozen=True)
class Assignment:
    task_id: str
    robot_id: str
    cost: int
    path: list[tuple[int, int]]


class Scheduler(Protocol):
    def select_assignments(
        self,
        pending_tasks: list[Task],
        robots: list[Robot],
        warehouse: Warehouse,
        blocked_cells: set[tuple[int, int]] | None = None,
    ) -> list[Assignment]:
        raise NotImplementedError


def _available_robots(robots: list[Robot]) -> list[Robot]:
    """Return robots that are allowed to accept a new task.

    This preserves the v0.4 compatibility guard:
    a robot may have status Idle while mode is Charging, Waiting, Failed, etc.
    Such robots must not receive tasks.
    """
    available: list[Robot] = []

    for robot in robots:
        if robot.status != RobotStatus.IDLE:
            continue

        if robot.current_task_id is not None:
            continue

        mode = getattr(robot, "mode", None)
        mode_value = getattr(mode, "value", mode)

        if mode_value not in (None, "Idle"):
            continue

        available.append(robot)

    return available


class BaseScheduler:
    """Common helper methods for scheduler plugins."""

    def __init__(self, path_planner: PathPlanner | None = None) -> None:
        self._path_planner = path_planner or BFSPathPlanner()

    def _path_for_robot(
        self,
        warehouse: Warehouse,
        robot: Robot,
        target: tuple[int, int],
        blocked: set[tuple[int, int]],
    ) -> list[tuple[int, int]] | None:
        other_blocked = set(blocked)
        other_blocked.discard((robot.x, robot.y))

        path = self._path_planner.find_path(
            warehouse,
            (robot.x, robot.y),
            target,
            blocked_cells=other_blocked,
        )

        if path is not None:
            return path

        return self._path_planner.find_path(
            warehouse,
            (robot.x, robot.y),
            target,
        )

    def _path_distance(
        self,
        warehouse: Warehouse,
        start: tuple[int, int],
        goal: tuple[int, int],
        blocked: set[tuple[int, int]],
    ) -> int | None:
        path = self._path_planner.find_path(
            warehouse,
            start,
            goal,
            blocked_cells=blocked,
        )

        if path is None:
            path = self._path_planner.find_path(
                warehouse,
                start,
                goal,
            )

        if path is None:
            return None

        return len(path)

    def _task_endpoints(
        self,
        warehouse: Warehouse,
        task: Task,
    ) -> tuple[tuple[int, int], tuple[int, int]] | None:
        try:
            pickup = warehouse.resolve(task.pickup)
            dropoff = warehouse.resolve(task.dropoff)
        except KeyError:
            return None

        return pickup, dropoff

    def _pickup_to_dropoff_cost(
        self,
        warehouse: Warehouse,
        pickup: tuple[int, int],
        dropoff: tuple[int, int],
        blocked: set[tuple[int, int]],
    ) -> int | None:
        return self._path_distance(
            warehouse,
            pickup,
            dropoff,
            blocked,
        )


class NearestPickupScheduler(BaseScheduler):
    """Assigns tasks by choosing the nearest feasible robot to each pickup.

    This is the generic nearest-pickup dispatcher. Subclasses only change
    the task ordering.
    """

    def _task_sort_key(self, task: Task) -> tuple[int, int, str]:
        # Correct convention:
        # lower task.priority value = higher urgency.
        return (task.priority, task.created_at, task.id)

    def select_assignments(
        self,
        pending_tasks: list[Task],
        robots: list[Robot],
        warehouse: Warehouse,
        blocked_cells: set[tuple[int, int]] | None = None,
    ) -> list[Assignment]:
        available = _available_robots(robots)

        if not pending_tasks or not available:
            return []

        blocked = set(blocked_cells or ())
        assignments: list[Assignment] = []

        for task in sorted(pending_tasks, key=self._task_sort_key):
            try:
                target = warehouse.resolve(task.pickup)
            except KeyError:
                continue

            chosen_robot: Robot | None = None
            chosen_path: list[tuple[int, int]] | None = None
            chosen_cost: int | None = None

            for robot in available:
                path = self._path_for_robot(
                    warehouse,
                    robot,
                    target,
                    blocked,
                )

                if path is None:
                    continue

                cost = len(path)

                if (
                    chosen_cost is None
                    or cost < chosen_cost
                    or (
                        cost == chosen_cost
                        and robot.id < (chosen_robot.id if chosen_robot else "")
                    )
                ):
                    chosen_robot = robot
                    chosen_path = path
                    chosen_cost = cost

            if (
                chosen_robot is None
                or chosen_path is None
                or chosen_cost is None
            ):
                continue

            assignments.append(
                Assignment(
                    task_id=task.id,
                    robot_id=chosen_robot.id,
                    cost=chosen_cost,
                    path=chosen_path,
                )
            )

            available.remove(chosen_robot)
            blocked.add((chosen_robot.x, chosen_robot.y))

        return assignments


class CostBasedScheduler(NearestPickupScheduler):
    """Legacy v0.5 baseline scheduler.

    IMPORTANT:
    This preserves the old v0.5 sorting behavior exactly:

        -task.priority

    If lower priority value means higher urgency, that old behavior is
    inverted. It is preserved here so v0.6 regression comparisons against
    v0.5 remain unchanged.
    """

    def _task_sort_key(self, task: Task) -> tuple[int, int, str]:
        return (-task.priority, task.created_at, task.id)


class PriorityScheduler(NearestPickupScheduler):
    """Nearest-pickup dispatcher with correct priority ordering.

    Lower task.priority value is treated as more urgent.
    """

    # Uses BaseScheduler/NearestPickupScheduler correct key:
    # (task.priority, task.created_at, task.id)
    pass


class FIFOScheduler(NearestPickupScheduler):
    """Nearest-pickup dispatcher that processes oldest tasks first."""

    def _task_sort_key(self, task: Task) -> tuple[int, int, str]:
        return (task.created_at, task.priority, task.id)


class TotalCostScheduler(BaseScheduler):
    """Battery/energy-aware scheduler.

    The previous total-cost implementation was effectively equivalent to
    nearest-pickup assignment because pickup->dropoff distance is constant
    for a given task and therefore does not affect robot selection.

    This version adds robot-specific battery risk, so different robots can
    produce different assignment costs even for the same task.
    """

    def __init__(
        self,
        path_planner: PathPlanner | None = None,
        empty_move_energy: float = 0.7,
        loaded_move_energy: float = 1.0,
        safety_margin: float = 5.0,
        critical_battery: float = 20.0,
    ) -> None:
        super().__init__(path_planner=path_planner)

        if empty_move_energy < 0:
            raise ValueError("empty_move_energy must be >= 0.")

        if loaded_move_energy < 0:
            raise ValueError("loaded_move_energy must be >= 0.")

        self._empty_move_energy = float(empty_move_energy)
        self._loaded_move_energy = float(loaded_move_energy)
        self._safety_margin = float(safety_margin)
        self._critical_battery = float(critical_battery)

    def _task_sort_key(self, task: Task) -> tuple[int, int, str]:
        return (task.priority, task.created_at, task.id)

    def select_assignments(
        self,
        pending_tasks: list[Task],
        robots: list[Robot],
        warehouse: Warehouse,
        blocked_cells: set[tuple[int, int]] | None = None,
    ) -> list[Assignment]:
        available = _available_robots(robots)

        if not pending_tasks or not available:
            return []

        blocked = set(blocked_cells or ())
        assignments: list[Assignment] = []

        for task in sorted(pending_tasks, key=self._task_sort_key):
            endpoints = self._task_endpoints(warehouse, task)

            if endpoints is None:
                continue

            pickup, dropoff = endpoints

            loaded_distance = self._pickup_to_dropoff_cost(
                warehouse,
                pickup,
                dropoff,
                blocked,
            )

            if loaded_distance is None:
                continue

            loaded_energy = loaded_distance * self._loaded_move_energy

            chosen_robot: Robot | None = None
            chosen_path: list[tuple[int, int]] | None = None
            chosen_cost: int | None = None

            for robot in available:
                path = self._path_for_robot(
                    warehouse,
                    robot,
                    pickup,
                    blocked,
                )

                if path is None:
                    continue

                empty_distance = len(path)
                empty_energy = empty_distance * self._empty_move_energy
                required_energy = empty_energy + loaded_energy

                battery = float(getattr(robot, "battery", 100.0))

                battery_penalty = 0

                shortfall = (
                    required_energy
                    + self._safety_margin
                    - battery
                )

                if shortfall > 0:
                    battery_penalty += int(shortfall * 100)

                if battery <= self._critical_battery:
                    battery_penalty += 10_000

                # Small preference for robots with more remaining battery.
                # This keeps the scheduler from being purely distance-based.
                battery_preference = int(max(0.0, 100.0 - battery))

                cost = (
                    empty_distance
                    + loaded_distance
                    + battery_penalty
                    + battery_preference
                )

                if (
                    chosen_cost is None
                    or cost < chosen_cost
                    or (
                        cost == chosen_cost
                        and robot.id < (chosen_robot.id if chosen_robot else "")
                    )
                ):
                    chosen_robot = robot
                    chosen_path = path
                    chosen_cost = cost

            if (
                chosen_robot is None
                or chosen_path is None
                or chosen_cost is None
            ):
                continue

            assignments.append(
                Assignment(
                    task_id=task.id,
                    robot_id=chosen_robot.id,
                    cost=chosen_cost,
                    path=chosen_path,
                )
            )

            available.remove(chosen_robot)
            blocked.add((chosen_robot.x, chosen_robot.y))

        return assignments

class AuctionScheduler(BaseScheduler):
    """Centralized first-price auction approximation.

    Each remaining task receives bids from each remaining robot.
    The lowest total bid wins.

    Bid cost =
        distance from robot to pickup
      + distance from pickup to dropoff

    This is still centralized, but it behaves more like a market-based
    dispatcher than a sequential nearest-pickup rule.
    """

    def _task_sort_key(self, task: Task) -> tuple[int, int, str]:
        return (task.priority, task.created_at, task.id)

    def select_assignments(
        self,
        pending_tasks: list[Task],
        robots: list[Robot],
        warehouse: Warehouse,
        blocked_cells: set[tuple[int, int]] | None = None,
    ) -> list[Assignment]:
        available = _available_robots(robots)

        if not pending_tasks or not available:
            return []

        blocked = set(blocked_cells or ())
        remaining_tasks = sorted(pending_tasks, key=self._task_sort_key)
        assignments: list[Assignment] = []

        while remaining_tasks and available:
            best_key: tuple[int, tuple[int, int, str], str] | None = None
            best_task: Task | None = None
            best_robot: Robot | None = None
            best_path: list[tuple[int, int]] | None = None
            best_cost: int | None = None

            for task in remaining_tasks:
                endpoints = self._task_endpoints(warehouse, task)

                if endpoints is None:
                    continue

                pickup, dropoff = endpoints

                loaded_leg_cost = self._pickup_to_dropoff_cost(
                    warehouse,
                    pickup,
                    dropoff,
                    blocked,
                )

                if loaded_leg_cost is None:
                    continue

                for robot in available:
                    path = self._path_for_robot(
                        warehouse,
                        robot,
                        pickup,
                        blocked,
                    )

                    if path is None:
                        continue

                    bid = len(path) + loaded_leg_cost

                    candidate_key = (
                        bid,
                        self._task_sort_key(task),
                        robot.id,
                    )

                    if best_key is None or candidate_key < best_key:
                        best_key = candidate_key
                        best_task = task
                        best_robot = robot
                        best_path = path
                        best_cost = bid

            if (
                best_task is None
                or best_robot is None
                or best_path is None
                or best_cost is None
            ):
                break

            assignments.append(
                Assignment(
                    task_id=best_task.id,
                    robot_id=best_robot.id,
                    cost=best_cost,
                    path=best_path,
                )
            )

            available.remove(best_robot)
            remaining_tasks.remove(best_task)
            blocked.add((best_robot.x, best_robot.y))

        return assignments