from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChargingStation:
    """
    Finite-capacity charging resource.

    active robots are actively charging and occupy capacity.
    reserved robots are traveling to a reserved charging cell.
    waiting robots are queued separately and do not occupy capacity.
    """

    capacity: int
    charge_duration_ticks: int

    # robot_id -> remaining charging ticks
    active: dict[str, int] = field(default_factory=dict)

    # robot_id -> charging cell currently occupied by that robot
    active_cells: dict[str, tuple[int, int]] = field(default_factory=dict)

    # robot_id -> charging cell reserved while robot is moving to charge
    reserved_cells: dict[str, tuple[int, int]] = field(default_factory=dict)

    # robot ids waiting for a charger slot
    waiting: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.capacity = max(0, int(self.capacity))
        self.charge_duration_ticks = max(1, int(self.charge_duration_ticks))

    @property
    def occupancy(self) -> int:
        return len(self.active)

    @property
    def has_capacity(self) -> bool:
        """
        True if there is capacity for another robot to begin or reserve charging.
        """
        return len(self.active) + len(self.reserved_cells) < self.capacity

    def is_charging(self, robot_id: str) -> bool:
        return robot_id in self.active

    def is_waiting(self, robot_id: str) -> bool:
        return robot_id in self.waiting

    def add_waiting(self, robot_id: str) -> None:
        self.waiting.add(robot_id)

    def remove_waiting(self, robot_id: str) -> None:
        self.waiting.discard(robot_id)

    def reserve(self, robot_id: str, cell: tuple[int, int]) -> bool:
        if robot_id in self.active:
            return True

        if robot_id in self.reserved_cells:
            self.reserved_cells[robot_id] = cell
            self.waiting.discard(robot_id)
            return True

        if not self.has_capacity:
            return False

        self.reserved_cells[robot_id] = cell
        self.waiting.discard(robot_id)
        return True

    def release_reservation(self, robot_id: str) -> None:
        self.reserved_cells.pop(robot_id, None)

    def begin_charging(self, robot_id: str, cell: tuple[int, int]) -> bool:
        if robot_id in self.active:
            return True

        had_reservation = robot_id in self.reserved_cells

        if len(self.active) >= self.capacity:
            return False

        # If the robot does not have a reservation, do not allow it to take
        # a slot that is already reserved for another incoming robot.
        if not had_reservation:
            if len(self.active) + len(self.reserved_cells) >= self.capacity:
                return False

        self.reserved_cells.pop(robot_id, None)
        self.active[robot_id] = self.charge_duration_ticks
        self.active_cells[robot_id] = cell
        self.waiting.discard(robot_id)
        return True

    def release(self, robot_id: str) -> None:
        self.active.pop(robot_id, None)
        self.active_cells.pop(robot_id, None)
        self.reserved_cells.pop(robot_id, None)
        self.waiting.discard(robot_id)

    def is_cell_active(self, cell: tuple[int, int]) -> bool:
        return cell in self.active_cells.values()

    def is_cell_reserved(self, cell: tuple[int, int]) -> bool:
        return cell in self.reserved_cells.values()

    def tick(self) -> list[str]:
        """
        Advance charging timers by one tick.

        Returns robot ids that finished charging during this tick.
        """

        finished: list[str] = []

        for robot_id in list(self.active.keys()):
            self.active[robot_id] -= 1
            if self.active[robot_id] <= 0:
                finished.append(robot_id)
                self.release(robot_id)

        return finished