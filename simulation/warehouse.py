from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping


class CellType(str, Enum):
    EMPTY = "EMPTY"
    SHELF = "SHELF"
    AISLE = "AISLE"
    MAIN_AISLE = "MAIN_AISLE"
    PACKING = "PACKING"
    RECEIVING = "RECEIVING"
    SHIPPING = "SHIPPING"
    CHARGING = "CHARGING"
    INTERSECTION = "INTERSECTION"
    BUFFER = "BUFFER"
    PICK_STATION = "PICK_STATION"
    CONSOLIDATION = "CONSOLIDATION"
    STAGING = "STAGING"
    MAINTENANCE = "MAINTENANCE"


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
    "B": CellType.BUFFER,
    "K": CellType.PICK_STATION,
    "O": CellType.CONSOLIDATION,
    "G": CellType.STAGING,
    "X": CellType.MAINTENANCE,
}


@dataclass(frozen=True)
class Location:
    """A named point in the warehouse.

    ``cell``   -> the physical cell the location represents (a shelf cell for
                  storage, the station cell itself for work stations).
    ``access`` -> the passable cell an AMR actually drives to.
    """
    name: str
    cell: tuple[int, int]
    access: tuple[int, int]


class Warehouse:
    def __init__(
        self,
        layout: Iterable[str],
        locations: Mapping[str, Location] | None = None,
    ) -> None:
        self.layout: list[list[CellType]] = self._parse_layout(layout)
        self.height: int = len(self.layout)
        self.width: int = len(self.layout[0]) if self.layout else 0
        self.locations: dict[str, Location] = dict(locations) if locations else {}
        self._validate()

    @staticmethod
    def _parse_layout(layout: Iterable[str]) -> list[list[CellType]]:
        rows: list[list[CellType]] = []
        for line in layout:
            row = []
            for ch in line:
                if ch not in LAYOUT_SYMBOLS:
                    raise ValueError(f"Unknown layout symbol: {ch!r}")
                row.append(LAYOUT_SYMBOLS[ch])
            rows.append(row)
        return rows

    def _validate(self) -> None:
        if not self.layout:
            raise ValueError("Warehouse layout is empty")
        widths = {len(row) for row in self.layout}
        if len(widths) != 1:
            raise ValueError("Warehouse rows have inconsistent widths")
        for loc in self.locations.values():
            for point in (loc.cell, loc.access):
                if not self.in_bounds(*point):
                    raise ValueError(f"Location {loc.name!r} is out of bounds")
            if self.is_blocked(*loc.access):
                raise ValueError(f"Location {loc.name!r} access point is blocked")

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def cell_type(self, x: int, y: int) -> CellType:
        return self.layout[y][x]

    def is_blocked(self, x: int, y: int) -> bool:
        if not self.in_bounds(x, y):
            return True
        return self.cell_type(x, y) is CellType.SHELF

    @property
    def obstacles(self) -> frozenset[tuple[int, int]]:
        blocked = {
            (x, y)
            for y, row in enumerate(self.layout)
            for x, cell in enumerate(row)
            if cell is CellType.SHELF
        }
        return frozenset(blocked)

    def resolve(self, name: str) -> tuple[int, int]:
        """Return the AMR target (access) coordinate for a named location."""
        try:
            return self.locations[name].access
        except KeyError:
            raise KeyError(f"Unknown location: {name!r}") from None

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "layout": [[cell.value for cell in row] for row in self.layout],
            "obstacles": [[x, y] for (x, y) in sorted(self.obstacles)],
            "locations": {
                name: {"cell": list(loc.cell), "access": list(loc.access)}
                for name, loc in self.locations.items()
            },
            "racks": self._rack_anchors(),
        }

    def _rack_anchors(self) -> dict[str, list[int]]:
        """One anchor cell per rack letter, for map labels ('B', not 'B-02')."""
        anchors: dict[str, list[int]] = {}
        for loc in self.locations.values():
            if self.cell_type(*loc.cell) is not CellType.SHELF:
                continue
            rack = loc.name.split("-")[0]
            anchors.setdefault(rack, list(loc.cell))
        return anchors