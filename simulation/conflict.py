from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from .reservations import ReservationTable
from .robot import RobotMode, RobotStatus
from .task import TaskPhase
from .warehouse import CellType

if TYPE_CHECKING:
    from .robot import Robot
    from .simulation import Simulation


class ConflictManager(Protocol):
    """Conflict-resolution plugin interface.

    Existing reactive methods remain for occupied-cell conflicts.
    New proactive methods allow zone locking and reservation-based denial
    before the occupied-cell check.
    """

    def handle_blocked_robot(
        self,
        robot: "Robot",
        next_cell: tuple[int, int],
    ) -> None:
        raise NotImplementedError

    def advance_replanning_robot(
        self,
        robot: "Robot",
        occupied: set[tuple[int, int]],
    ) -> None:
        raise NotImplementedError

    def release_conflict(self, robot: "Robot") -> None:
        raise NotImplementedError

    def clear_conflicts_for_robot(self, robot: "Robot") -> None:
        raise NotImplementedError

    def reset(self) -> None:
        raise NotImplementedError

    def tick(self, current_tick: int, robots: list["Robot"]) -> None:
        raise NotImplementedError

    def allow_step(
        self,
        robot: "Robot",
        next_cell: tuple[int, int],
        occupied: set[tuple[int, int]],
    ) -> bool:
        raise NotImplementedError

    def release_robot(self, robot_id: str) -> None:
        raise NotImplementedError

    @property
    def active_conflicts(self) -> int:
        raise NotImplementedError


class LocalYieldConflictManager:
    """Baseline conflict manager.

    This preserves the existing local deadlock recovery behavior.
    It adds no proactive restrictions.
    """

    def __init__(self, sim: "Simulation") -> None:
        self._sim = sim
        self._active_conflict_yielder: dict[frozenset[str], str] = {}

    @property
    def active_conflicts(self) -> int:
        return len(self._active_conflict_yielder)

    def reset(self) -> None:
        self._active_conflict_yielder.clear()

    def tick(self, current_tick: int, robots: list["Robot"]) -> None:
        return None

    def allow_step(
        self,
        robot: "Robot",
        next_cell: tuple[int, int],
        occupied: set[tuple[int, int]],
    ) -> bool:
        return True

    def release_robot(self, robot_id: str) -> None:
        return None

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

    def _select_yielding_robot(
        self,
        robot: "Robot",
        blocker: "Robot",
    ) -> "Robot":
        robot_score = self._yield_score(robot)
        blocker_score = self._yield_score(blocker)

        if robot_score != blocker_score:
            return robot if robot_score > blocker_score else blocker

        if robot.blocked_ticks != blocker.blocked_ticks:
            return (
                robot
                if robot.blocked_ticks > blocker.blocked_ticks
                else blocker
            )

        return robot if robot.id < blocker.id else blocker

    def _yield_score(self, robot: "Robot") -> int:
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
                    distance = (
                        abs(neighbor[0] - goal[0])
                        + abs(neighbor[1] - goal[1])
                    )

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
                toward_goal = (
                    abs(cell[0] - goal[0])
                    + abs(cell[1] - goal[1])
                )
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


class ZoneLockConflictManager(LocalYieldConflictManager):
    """Intersection zone-lock conflict manager.

    This keeps the existing local yield behavior for occupied-cell conflicts
    and adds a proactive rule:

    - INTERSECTION cells are lockable zones.
    - A robot currently on an intersection locks it.
    - A robot whose immediate next target is an intersection claims it.
    - Robots are processed deterministically by robot id when claiming.
    - If another robot already owns the lock, entry is denied temporarily.

    If a robot is denied for too long, it is allowed to fall back to the
    normal occupied/local-yield system to avoid starvation.
    """

    def __init__(self, sim: "Simulation") -> None:
        super().__init__(sim)
        self._locks: dict[tuple[int, int], str] = {}

    def reset(self) -> None:
        super().reset()
        self._locks.clear()

    def _is_intersection(self, cell: tuple[int, int]) -> bool:
        warehouse = self._sim._warehouse

        if not warehouse.in_bounds(*cell):
            return False

        return warehouse.cell_type(*cell) == CellType.INTERSECTION

    def tick(self, current_tick: int, robots: list["Robot"]) -> None:
        super().tick(current_tick, robots)

        self._locks.clear()

        # Deterministic claim order.
        for robot in sorted(robots, key=lambda r: r.id):
            mode = getattr(robot, "mode", RobotMode.IDLE)

            # Failed and repairing robots are handled by occupied-cell logic.
            if mode in (RobotMode.FAILED, RobotMode.REPAIRING):
                continue

            current = (robot.x, robot.y)

            if self._is_intersection(current):
                self._locks.setdefault(current, robot.id)

            next_cell = getattr(robot, "current_target", None)

            if next_cell is not None and self._is_intersection(next_cell):
                self._locks.setdefault(next_cell, robot.id)

    def allow_step(
        self,
        robot: "Robot",
        next_cell: tuple[int, int],
        occupied: set[tuple[int, int]],
    ) -> bool:
        if not super().allow_step(robot, next_cell, occupied):
            return False

        # Fallback to avoid starvation.
        if (
            robot.blocked_ticks
            >= self._sim._blocked_replan_threshold_ticks * 2
        ):
            return True

        if not self._is_intersection(next_cell):
            return True

        owner = self._locks.get(next_cell)

        if owner is None or owner == robot.id:
            return True

        return False

    def release_robot(self, robot_id: str) -> None:
        super().release_robot(robot_id)

        for cell in list(self._locks.keys()):
            if self._locks[cell] == robot_id:
                del self._locks[cell]


class PrioritizedReservationConflictManager(LocalYieldConflictManager):
    """Approximate prioritized reservation conflict manager.

    This rebuilds short-horizon vertex reservations every tick from each
    robot's current path.

    Robots are sorted by a priority score. Higher-priority robots reserve
    their future cells first. Lower-priority robots cannot reserve cells
    already reserved by higher-priority robots.

    This is not full space-time MAPF. It is a practical proactive traffic
    manager for experimentation.
    """

    def __init__(
        self,
        sim: "Simulation",
        horizon: int = 32,
    ) -> None:
        super().__init__(sim)

        if horizon < 1:
            raise ValueError("Reservation horizon must be >= 1.")

        self._horizon = horizon
        self._table = ReservationTable()

    def reset(self) -> None:
        super().reset()
        self._table.reset()

    def _robot_priority(self, robot: "Robot") -> int:
        """Higher score means higher reservation priority."""
        sim = self._sim
        mode = getattr(robot, "mode", RobotMode.IDLE)

        if mode in (
            RobotMode.FAILED,
            RobotMode.REPAIRING,
            RobotMode.CHARGING,
        ):
            return -1_000_000

        score = 0

        cfg = getattr(sim, "_battery_cfg", None)
        critical_battery = (
            getattr(cfg, "critical_battery", 20.0)
            if cfg is not None
            else 20.0
        )
        capacity = (
            getattr(cfg, "capacity", 100.0)
            if cfg is not None
            else 100.0
        )

        battery = float(getattr(robot, "battery", capacity))

        # Critical charging movement gets very high priority.
        if mode == RobotMode.TO_CHARGER:
            score += 800_000

            if battery <= critical_battery:
                score += 400_000

        task_id = getattr(robot, "current_task_id", None)

        if task_id is not None:
            task = sim._tasks.get(task_id)

            if task is not None:
                # Loaded robots are protected.
                if getattr(task, "phase", None) == TaskPhase.TO_DROPOFF:
                    score += 500_000

                # Lower task.priority value means higher urgency.
                priority = int(getattr(task, "priority", 3) or 3)
                score -= priority * 10_000
        else:
            # Empty idle robots yield to task-carrying robots.
            score -= 100_000

        # Robots that have already been blocked for a while get pressure.
        blocked_pressure = min(int(getattr(robot, "blocked_ticks", 0)), 20) * 100
        score += blocked_pressure

        # Low battery increases urgency.
        if battery <= critical_battery:
            score += 200_000

        # Small tie pressure: preserve higher battery robots slightly.
        score += int(max(0.0, capacity - battery))

        return score

    def tick(self, current_tick: int, robots: list["Robot"]) -> None:
        super().tick(current_tick, robots)

        self._table.reset()

        active_robots: list["Robot"] = []

        for robot in robots:
            mode = getattr(robot, "mode", RobotMode.IDLE)

            if mode in (
                RobotMode.FAILED,
                RobotMode.REPAIRING,
                RobotMode.CHARGING,
            ):
                continue

            active_robots.append(robot)

        # High priority first. Tie-break by robot id for determinism.
        active_robots.sort(
            key=lambda r: (-self._robot_priority(r), r.id)
        )

        for robot in active_robots:
            current = (robot.x, robot.y)

            # Reserve current position at current tick.
            self._table.reserve(robot.id, current, current_tick)

            path = getattr(robot, "path", None) or []

            if not path:
                continue

            for offset, cell in enumerate(path[: self._horizon], start=1):
                tick = current_tick + offset

                if not self._table.reserve(robot.id, cell, tick):
                    # If this robot cannot reserve its next planned step,
                    # do not reserve further future cells for this path.
                    break

    def allow_step(
        self,
        robot: "Robot",
        next_cell: tuple[int, int],
        occupied: set[tuple[int, int]],
    ) -> bool:
        if not super().allow_step(robot, next_cell, occupied):
            return False

        # Fallback to avoid starvation.
        if (
            robot.blocked_ticks
            >= self._sim._blocked_replan_threshold_ticks * 2
        ):
            return True

        next_tick = self._sim._tick_count + 1

        owner = self._table.owner(next_cell, next_tick)

        if owner is None or owner == robot.id:
            return True

        return False

    def release_robot(self, robot_id: str) -> None:
        super().release_robot(robot_id)
        self._table.release_robot(robot_id)