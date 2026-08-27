from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .robot import Robot
    from .simulation import Simulation


class ConflictManager(Protocol):
    def handle_blocked_robot(self, robot: "Robot", next_cell: tuple[int, int]) -> None: ...
    def advance_replanning_robot(self, robot: "Robot", occupied: set[tuple[int, int]]) -> None: ...
    def release_conflict(self, robot: "Robot") -> None: ...
    def clear_conflicts_for_robot(self, robot: "Robot") -> None: ...
    def reset(self) -> None: ...
    
    @property
    def active_conflicts(self) -> int: ...


class LocalYieldConflictManager:
    """Manages local deadlock recovery via yielding and backtracking."""

    def __init__(self, sim: "Simulation") -> None:
        self._sim = sim
        self._active_conflict_yielder: dict[frozenset[str], str] = {}

    @property
    def active_conflicts(self) -> int:
        return len(self._active_conflict_yielder)

    def reset(self) -> None:
        self._active_conflict_yielder.clear()

    def handle_blocked_robot(
        self,
        robot: "Robot",
        next_cell: tuple[int, int],
    ) -> None:
        sim = self._sim
        blocker = sim._robot_at(next_cell, exclude_robot_id=robot.id)
        if blocker is None:
            robot.blocked_ticks += 1
            sim._metrics.record_blocked(robot)
            if (
                robot.blocked_ticks >= sim._blocked_replan_threshold_ticks
                and robot.replan_cooldown == 0
            ):
                sim._attempt_resume_route(robot)
            return

        pair_key = frozenset({robot.id, blocker.id})
        active_yielder = self._active_conflict_yielder.get(pair_key)

        robot.blocked_ticks += 1
        sim._metrics.record_blocked(robot)

        if active_yielder is not None:
            if active_yielder == robot.id:
                if not robot.replanning:
                    self._active_conflict_yielder.pop(pair_key, None)
                    if self._can_yield(robot):
                        self._make_robot_yield(robot, blocker, pair_key)
                return

            yielder_robot = sim._robots.get(active_yielder)
            if yielder_robot is not None:
                if (
                    robot.blocked_ticks >= sim._blocked_replan_threshold_ticks * 3
                    and not yielder_robot.replanning
                    and self._can_yield(robot)
                ):
                    self._active_conflict_yielder.pop(pair_key, None)
                    self._make_robot_yield(robot, blocker, pair_key)
                return

            self._active_conflict_yielder.pop(pair_key, None)

        if robot.blocked_ticks < sim._blocked_replan_threshold_ticks:
            return

        preferred_yielder = self._select_yielding_robot(robot, blocker)

        if preferred_yielder.id == blocker.id:
            if (
                not blocker.path
                or blocker.blocked_ticks >= sim._blocked_replan_threshold_ticks
            ) and self._can_yield(blocker):
                if self._make_robot_yield(blocker, robot, pair_key):
                    return
            if self._can_yield(robot) and (
                not blocker.path
                or blocker.replan_cooldown > 0
                or robot.blocked_ticks >= sim._blocked_replan_threshold_ticks + 2
            ):
                self._make_robot_yield(robot, blocker, pair_key)
            return

        if self._can_yield(robot):
            self._make_robot_yield(robot, blocker, pair_key)

    def _make_robot_yield(
        self,
        robot: "Robot",
        blocker: "Robot",
        pair_key: frozenset[str],
    ) -> bool:
        sim = self._sim
        if not self._can_yield(robot):
            return False

        occupied = sim._occupied_cells(exclude_robot_id=robot.id)
        step = self._choose_yield_step(robot, blocker, occupied)
        if step is None:
            robot.replan_cooldown = 1
            return False

        self._active_conflict_yielder[pair_key] = robot.id
        robot.replanning = True
        robot.yielding_to = blocker.id
        robot.set_path([step])
        robot.blocked_ticks = 0
        robot.replan_cooldown = sim._replan_cooldown_ticks

        sim._metrics.record_replan(robot)
        sim._metrics.record_deadlock_resolution()
        sim._check_battery_for_active_task(robot)
        return True

    def _select_yielding_robot(self, robot: "Robot", blocker: "Robot") -> "Robot":
        robot_score = self._yield_score(robot)
        blocker_score = self._yield_score(blocker)

        if robot_score != blocker_score:
            return robot if robot_score > blocker_score else blocker

        if robot.blocked_ticks != blocker.blocked_ticks:
            return robot if robot.blocked_ticks > blocker.blocked_ticks else blocker

        return robot if robot.id < blocker.id else blocker

    def _yield_score(self, robot: "Robot") -> int:
        from .robot import RobotMode
        sim = self._sim
        mode = getattr(robot, "mode", RobotMode.IDLE)

        if mode in (
            RobotMode.FAILED,
            RobotMode.REPAIRING,
            RobotMode.CHARGING,
        ):
            return -1_000_000

        if robot.current_task_id is None:
            score = 10_000
        else:
            task = sim._tasks.get(robot.current_task_id)
            if task is None:
                score = 10_000
            else:
                priority = int(getattr(task, "priority", 0) or 0)
                score = max(0, min(priority, 10)) * 20

        blocked_pressure = min(robot.blocked_ticks, 20) * 10
        score += blocked_pressure

        cfg = sim._battery_cfg
        battery = float(getattr(robot, "battery", cfg.capacity))

        if battery <= cfg.critical_battery:
            score -= 12_000
        elif battery <= cfg.critical_battery + cfg.safety_margin:
            deficit = cfg.critical_battery + cfg.safety_margin - battery
            score -= int(5_000 + deficit * 200)
        elif battery <= cfg.opportunistic_charge_threshold:
            deficit = cfg.opportunistic_charge_threshold - battery
            score -= int(deficit * 25)

        if (
            mode in (RobotMode.TO_CHARGER, RobotMode.WAITING_FOR_CHARGER)
            and battery <= cfg.critical_battery
        ):
            score -= 1_000

        return score

    def _robot_is_in_active_conflict(self, robot_id: str) -> bool:
        for pair_key in self._active_conflict_yielder.keys():
            if robot_id in pair_key:
                return True
        return False

    def _can_yield(self, robot: "Robot") -> bool:
        from .robot import RobotMode
        mode = getattr(robot, "mode", RobotMode.IDLE)
        if mode in (
            RobotMode.FAILED,
            RobotMode.REPAIRING,
            RobotMode.CHARGING,
        ):
            return False

        return (
            not robot.replanning
            and robot.replan_cooldown == 0
            and not self._robot_is_in_active_conflict(robot.id)
        )

    def _choose_yield_step(
        self,
        robot: "Robot",
        blocker: "Robot",
        occupied: set[tuple[int, int]],
    ) -> tuple[int, int] | None:
        sim = self._sim
        current = (robot.x, robot.y)
        claimed = sim._claimed_cells(exclude_robot_id=robot.id)
        blocked = occupied | claimed
        blocked.discard(current)

        safe_neighbors: list[tuple[int, int]] = []
        for neighbor in (
            (robot.x + 1, robot.y),
            (robot.x - 1, robot.y),
            (robot.x, robot.y + 1),
            (robot.x, robot.y - 1),
        ):
            if not sim._warehouse.in_bounds(*neighbor):
                continue
            if sim._warehouse.is_blocked(*neighbor):
                continue
            if neighbor in blocked:
                continue
            safe_neighbors.append(neighbor)

        if not safe_neighbors:
            return None

        goal = robot.route_goal

        if goal is not None and goal != current and goal not in blocked:
            best_neighbor = None
            best_distance = None

            for neighbor in safe_neighbors:
                path = sim._path_planner.find_path(
                    sim._warehouse,
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

        safe_set = set(safe_neighbors)
        history = robot.travel_history[-32:]

        for target in reversed(history):
            if target == current:
                continue
            if target in blocked:
                continue
            if not sim._warehouse.in_bounds(*target):
                continue
            if sim._warehouse.is_blocked(*target):
                continue

            if target in safe_set:
                return target

            path = sim._path_planner.find_path(
                sim._warehouse,
                current,
                target,
                blocked_cells=blocked - {current},
            )

            if path and path[0] in safe_set:
                return path[0]

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

    def advance_replanning_robot(
        self,
        robot: "Robot",
        occupied: set[tuple[int, int]],
    ) -> None:
        sim = self._sim
        if not robot.path:
            self._complete_yield(robot)
            return

        next_cell = robot.current_target
        if next_cell is None:
            self._complete_yield(robot)
            return

        if next_cell in occupied:
            robot.blocked_ticks += 1
            sim._metrics.record_blocked(robot)

            if robot.blocked_ticks >= 2 and robot.replan_cooldown == 0:
                blocker = None
                if robot.yielding_to is not None:
                    blocker = sim._robots.get(robot.yielding_to)
                if blocker is None:
                    self._complete_yield(robot)
                    return

                step = self._choose_yield_step(robot, blocker, occupied)
                if step is not None:
                    robot.set_path([step])
                    robot.blocked_ticks = 0
                    robot.replan_cooldown = sim._replan_cooldown_ticks
                    sim._check_battery_for_active_task(robot)
                    return
            return

        sim._step_robot_forward(robot, occupied)
        if not robot.path:
            self._complete_yield(robot)
        else:
            sim._check_battery_for_active_task(robot)

    def _complete_yield(self, robot: "Robot") -> None:
        sim = self._sim
        from .robot import RobotMode, RobotStatus
        self.release_conflict(robot)
        robot.replanning = False
        robot.set_path([])
        mode = getattr(robot, "mode", RobotMode.IDLE)

        if robot.current_task_id is not None:
            robot.status = RobotStatus.MOVING
            if mode not in (
                RobotMode.TO_CHARGER,
                RobotMode.WAITING_FOR_CHARGER,
                RobotMode.CHARGING,
                RobotMode.FAILED,
                RobotMode.REPAIRING,
            ):
                robot.mode = RobotMode.MOVING

        if robot.route_goal is not None and (
            robot.current_task_id is not None
            or mode in (RobotMode.TO_CHARGER, RobotMode.MOVING)
        ):
            sim._attempt_resume_route(robot)

    def release_conflict(self, robot: "Robot") -> None:
        if robot.yielding_to is None:
            return
        pair_key = frozenset({robot.id, robot.yielding_to})
        if self._active_conflict_yielder.get(pair_key) == robot.id:
            del self._active_conflict_yielder[pair_key]
        robot.replanning = False
        robot.yielding_to = None

    def clear_conflicts_for_robot(self, robot: "Robot") -> None:
        sim = self._sim
        for pair_key, yielder_id in list(self._active_conflict_yielder.items()):
            if robot.id not in pair_key:
                continue
            self._active_conflict_yielder.pop(pair_key, None)
            if yielder_id == robot.id:
                robot.replanning = False
                robot.yielding_to = None
            else:
                other = sim._robots.get(yielder_id)
                if other is not None and not other.path:
                    other.replanning = False
                    other.yielding_to = None