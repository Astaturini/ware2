from collections.abc import Iterable
from enum import Enum
from typing import Any


class CellType(str, Enum):
    """Warehouse tile types.

    Version 0.2 layout extension:
    These are semantic cell types. Only SHELF is blocked in this version.
    """

    EMPTY = "EMPTY"
    SHELF = "SHELF"
    AISLE = "AISLE"
    MAIN_AISLE = "MAIN_AISLE"
    PACKING = "PACKING"
    RECEIVING = "RECEIVING"
    SHIPPING = "SHIPPING"
    CHARGING = "CHARGING"
    INTERSECTION = "INTERSECTION"


LAYOUT_SYMBOLS: dict[str, CellType] = {
    ".": CellType.EMPTY,
    "E": CellType.EMPTY,
    "#": CellType.SHELF,
    "a": CellType.AISLE,
    "M": CellType.MAIN_AISLE,
    "P": CellType.PACKING,
    "R": CellType.RECEIVING,
    "S": CellType.SHIPPING,
    "C": CellType.CHARGING,
    "I": CellType.INTERSECTION,
}


class Warehouse:
    """Tile-based warehouse layout.

    The layout is defined as a list of equal-length strings.
    Each character represents one warehouse cell.
    """

    def __init__(
        self,
        layout: Iterable[str],
        pickup: tuple[int, int],
        dropoff: tuple[int, int],
    ) -> None:
        rows = list(layout)

        if not rows:
            raise ValueError("Warehouse layout cannot be empty.")

        self.height = len(rows)
        self.width = len(rows[0])

        if self.width <= 0 or self.height <= 0:
            raise ValueError("Warehouse layout must have positive width and height.")

        self.layout: list[list[CellType]] = []

        for y, row in enumerate(rows):
            if len(row) != self.width:
                raise ValueError(
                    f"Layout row {y} has length {len(row)}, expected {self.width}."
                )

            parsed_row: list[CellType] = []

            for x, symbol in enumerate(row):
                cell = LAYOUT_SYMBOLS.get(symbol)

                if cell is None:
                    raise ValueError(
                        f"Unknown layout symbol '{symbol}' at ({x}, {y})."
                    )

                parsed_row.append(cell)

            self.layout.append(parsed_row)

        self.pickup = pickup
        self.dropoff = dropoff

        self._validate()

    def _validate(self) -> None:
        for x, y in (self.pickup, self.dropoff):
            if not self.in_bounds(x, y):
                raise ValueError(
                    f"Station location ({x}, {y}) is outside warehouse bounds."
                )

            if self.is_blocked(x, y):
                raise ValueError(
                    f"Station location ({x}, {y}) is blocked."
                )

    def in_bounds(self, x: int, y: int) -> bool:
        """Return True if the coordinate is inside the warehouse."""
        return 0 <= x < self.width and 0 <= y < self.height

    def cell_type(self, x: int, y: int) -> CellType:
        """Return the cell type at the given coordinate."""
        if not self.in_bounds(x, y):
            raise ValueError(f"Location ({x}, {y}) is outside warehouse bounds.")

        return self.layout[y][x]

    def is_blocked(self, x: int, y: int) -> bool:
        """Return True if a robot cannot occupy this cell.

        Extension point:
        Add WALL, CLOSED_AISLE, CONGESTED, or RESERVED cells later.
        """
        if not self.in_bounds(x, y):
            return True

        return self.layout[y][x] == CellType.SHELF

    @property
    def obstacles(self) -> frozenset[tuple[int, int]]:
        """Return shelf cells.

        Kept for backward compatibility with older rendering/debug code.
        """
        return frozenset(
            (x, y)
            for y, row in enumerate(self.layout)
            for x, cell in enumerate(row)
            if cell == CellType.SHELF
        )

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-serializable warehouse state."""
        return {
            "width": self.width,
            "height": self.height,
            "layout": [[cell.value for cell in row] for row in self.layout],
            "obstacles": sorted(self.obstacles),
            "pickup": self.pickup,
            "dropoff": self.dropoff,
        }