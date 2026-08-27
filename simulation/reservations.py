from __future__ import annotations


class ReservationTable:
    """Simple vertex reservation table.

    This tracks which robot intends to occupy which cell at which tick.

    This version intentionally does not track edge reservations.
    Edge reservations are needed to prevent all swap collisions, but that
    is a later extension.
    """

    def __init__(self) -> None:
        # cell -> tick -> robot_id
        self._vertex_reservations: dict[
            tuple[int, int],
            dict[int, str],
        ] = {}

        # robot_id -> set of reserved (cell, tick) pairs
        self._robot_reservations: dict[
            str,
            set[tuple[tuple[int, int], int]],
        ] = {}

    def reset(self) -> None:
        self._vertex_reservations.clear()
        self._robot_reservations.clear()

    def reserve(
        self,
        robot_id: str,
        cell: tuple[int, int],
        tick: int,
    ) -> bool:
        owners = self._vertex_reservations.setdefault(cell, {})

        existing_owner = owners.get(tick)

        if existing_owner is not None and existing_owner != robot_id:
            return False

        owners[tick] = robot_id
        self._robot_reservations.setdefault(robot_id, set()).add((cell, tick))
        return True

    def owner(
        self,
        cell: tuple[int, int],
        tick: int,
    ) -> str | None:
        owners = self._vertex_reservations.get(cell)

        if owners is None:
            return None

        return owners.get(tick)

    def is_free(
        self,
        cell: tuple[int, int],
        tick: int,
        robot_id: str,
    ) -> bool:
        owner = self.owner(cell, tick)
        return owner is None or owner == robot_id

    def release_robot(self, robot_id: str) -> None:
        reserved = self._robot_reservations.pop(robot_id, set())

        for cell, tick in reserved:
            owners = self._vertex_reservations.get(cell)

            if owners is None:
                continue

            if owners.get(tick) == robot_id:
                owners.pop(tick, None)

            if not owners:
                self._vertex_reservations.pop(cell, None)

    def prune(self, current_tick: int) -> None:
        """Remove reservations older than current_tick."""
        for cell in list(self._vertex_reservations.keys()):
            owners = self._vertex_reservations[cell]

            for tick in list(owners.keys()):
                if tick < current_tick:
                    robot_id = owners.pop(tick, None)

                    if robot_id is not None:
                        robot_set = self._robot_reservations.get(robot_id)

                        if robot_set is not None:
                            robot_set.discard((cell, tick))

            if not owners:
                self._vertex_reservations.pop(cell, None)