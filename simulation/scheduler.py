from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .pathfinding import find_shortest_path
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


class CostBasedScheduler:
    """Simple centralized task scheduler used as the v0.3 baseline."""

    def select_assignments(
        self,
        pending_tasks: list[Task],
        robots: list[Robot],
        warehouse: Warehouse,
        blocked_cells: set[tuple[int, int]] | None = None,
    ) -> list[Assignment]:
        available_robots: list[Robot] = []

        for robot in robots:
            if robot.status != RobotStatus.IDLE:
                continue

            if robot.current_task_id is not None:
                continue

            # v0.4 compatibility:
            # A robot may be status Idle while charging or waiting for charger.
            # If the robot has the new mode field, require mode Idle.
            mode = getattr(robot, "mode", None)
            mode_value = getattr(mode, "value", mode)

            if mode_value not in (None, "Idle"):
                continue

            available_robots.append(robot)

        if not pending_tasks or not available_robots:
            return []

        blocked = set(blocked_cells or set())
        assignments: list[Assignment] = []

        for task in sorted(
            pending_tasks,
            key=lambda item: (-item.priority, item.created_at, item.id),
        ):
            chosen_robot: Robot | None = None
            chosen_path: list[tuple[int, int]] | None = None
            chosen_cost: int | None = None

            target = warehouse.resolve(task.pickup)

            for robot in available_robots:
                path = self._path_for_robot(warehouse, robot, target, blocked)
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

            if chosen_robot is None or chosen_path is None or chosen_cost is None:
                continue

            assignments.append(
                Assignment(
                    task_id=task.id,
                    robot_id=chosen_robot.id,
                    cost=chosen_cost,
                    path=chosen_path,
                )
            )

            available_robots.remove(chosen_robot)
            blocked.add((chosen_robot.x, chosen_robot.y))

        return assignments

    @staticmethod
    def _path_for_robot(
        warehouse: Warehouse,
        robot: Robot,
        target: tuple[int, int],
        blocked: set[tuple[int, int]],
    ) -> list[tuple[int, int]] | None:
        other_blocked = set(blocked)
        other_blocked.discard((robot.x, robot.y))

        path = find_shortest_path(
            warehouse,
            (robot.x, robot.y),
            target,
            blocked_cells=other_blocked,
        )

        if path is not None:
            return path

        return find_shortest_path(warehouse, (robot.x, robot.y), target)