from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from simulation.warehouse import (
    LAYOUT_SYMBOLS,
    CellType,
    Location,
    Warehouse,
)
from simulation.warehouse_layout import build_warehouse


LAYOUT_PRESET_CHOICES = {
    "default",
    "high_density",
    "one_way_aisles",
}


@dataclass(frozen=True)
class LayoutLocation:
    cell: tuple[int, int]
    access: tuple[int, int]


@dataclass(frozen=True)
class LayoutConfig:
    name: str
    layout: tuple[str, ...]
    locations: Mapping[str, LayoutLocation]
    description: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LayoutConfig":
        if not isinstance(data, Mapping):
            raise TypeError("layout data must be a mapping")

        name = str(data.get("name", "custom")).strip()
        if not name:
            raise ValueError("layout name must be a non-empty string")

        description = str(data.get("description", "")).strip()

        layout_raw = data.get("layout", [])
        if not isinstance(layout_raw, list):
            raise ValueError("layout must be a list of row strings")

        layout = tuple(str(row) for row in layout_raw)

        locations_raw = data.get("locations", {})
        if not isinstance(locations_raw, Mapping):
            raise ValueError("locations must be a mapping")

        locations: dict[str, LayoutLocation] = {}

        for raw_name, raw_location in locations_raw.items():
            location_name = str(raw_name).strip()
            if not location_name:
                raise ValueError("location names must be non-empty strings")

            if not isinstance(raw_location, Mapping):
                raise ValueError(f"location {location_name!r} must be a mapping")

            cell = _as_coord(raw_location.get("cell"), f"{location_name}.cell")
            access = _as_coord(raw_location.get("access"), f"{location_name}.access")

            locations[location_name] = LayoutLocation(cell=cell, access=access)

        return cls(
            name=name,
            layout=layout,
            locations=locations,
            description=description,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "layout": list(self.layout),
            "locations": {
                name: {
                    "cell": list(location.cell),
                    "access": list(location.access),
                }
                for name, location in self.locations.items()
            },
        }


def validate_layout_config(config: LayoutConfig) -> None:
    if not config.layout:
        raise ValueError("layout must contain at least one row")

    width = len(config.layout[0])
    if width <= 0:
        raise ValueError("layout rows must not be empty")

    grid: list[list[CellType]] = []

    for y, row in enumerate(config.layout):
        if len(row) != width:
            raise ValueError(
                f"layout row {y} has length {len(row)}, expected {width}"
            )

        row_types: list[CellType] = []

        for x, symbol in enumerate(row):
            if symbol not in LAYOUT_SYMBOLS:
                raise ValueError(
                    f"Unknown layout symbol {symbol!r} at x={x}, y={y}. "
                    f"Valid symbols: {sorted(LAYOUT_SYMBOLS.keys())}"
                )

            row_types.append(LAYOUT_SYMBOLS[symbol])

        grid.append(row_types)

    height = len(grid)

    cell_counts = Counter(cell_type for row in grid for cell_type in row)

    if cell_counts.get(CellType.CHARGING, 0) < 1:
        raise ValueError("layout must contain at least one CHARGING cell")

    if cell_counts.get(CellType.MAINTENANCE, 0) < 1:
        raise ValueError("layout must contain at least one MAINTENANCE cell")

    required_cell_types = (
        CellType.SHELF,
        CellType.RECEIVING,
        CellType.SHIPPING,
        CellType.PACKING,
        CellType.PICK_STATION,
    )

    for cell_type in required_cell_types:
        if cell_counts.get(cell_type, 0) < 1:
            raise ValueError(
                f"layout must contain at least one {cell_type.value} cell"
            )

    if not config.locations:
        raise ValueError("layout must define at least one named location")

    located_cell_types: set[CellType] = set()

    for name, location in config.locations.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("location names must be non-empty strings")

        x, y = location.cell
        access_x, access_y = location.access

        if not (0 <= x < width and 0 <= y < height):
            raise ValueError(f"location {name!r} cell is out of bounds")

        if not (0 <= access_x < width and 0 <= access_y < height):
            raise ValueError(f"location {name!r} access cell is out of bounds")

        cell_type = grid[y][x]
        access_type = grid[access_y][access_x]

        if access_type == CellType.SHELF:
            raise ValueError(
                f"location {name!r} access cell must be passable, not SHELF"
            )

        located_cell_types.add(cell_type)

        distance = abs(x - access_x) + abs(y - access_y)

        if cell_type == CellType.SHELF:
            if distance != 1:
                raise ValueError(
                    f"location {name!r}: SHELF access must be orthogonally "
                    "adjacent to the shelf cell"
                )
        else:
            if distance > 1:
                raise ValueError(
                    f"location {name!r}: access must be the same cell or "
                    "orthogonally adjacent to the location cell"
                )

    for cell_type in required_cell_types:
        if cell_type not in located_cell_types:
            raise ValueError(
                f"At least one named location must be placed on a "
                f"{cell_type.value} cell"
            )


def create_warehouse_from_layout_config(config: LayoutConfig) -> Warehouse:
    validate_layout_config(config)

    locations = {
        name: Location(
            name=name,
            cell=location.cell,
            access=location.access,
        )
        for name, location in config.locations.items()
    }

    return Warehouse(
        layout=list(config.layout),
        locations=locations,
    )


def load_layout_config(path: str | Path) -> LayoutConfig:
    layout_path = Path(path)

    with layout_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    return LayoutConfig.from_dict(data)


def create_warehouse_from_preset(name: str) -> Warehouse:
    if name == "default":
        return build_warehouse()

    try:
        preset_data = PRESET_LAYOUTS[name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown layout preset: {name!r}. "
            f"Expected one of: {sorted(LAYOUT_PRESET_CHOICES)}"
        ) from exc

    return create_warehouse_from_layout_config(LayoutConfig.from_dict(preset_data))


def create_warehouse_for_experiment(
    layout_preset: str,
    layout_file: str | None,
) -> Warehouse:
    if layout_file is not None and str(layout_file).strip():
        config = load_layout_config(layout_file)
        return create_warehouse_from_layout_config(config)

    preset = layout_preset if layout_preset else "default"
    return create_warehouse_from_preset(preset)


def _as_coord(value: Any, context: str) -> tuple[int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{context} must be a two-element coordinate")

    raw_x, raw_y = value

    if isinstance(raw_x, bool) or isinstance(raw_y, bool):
        raise ValueError(f"{context} coordinates must not be booleans")

    if isinstance(raw_x, float) and not raw_x.is_integer():
        raise ValueError(f"{context} x coordinate must be an integer")

    if isinstance(raw_y, float) and not raw_y.is_integer():
        raise ValueError(f"{context} y coordinate must be an integer")

    try:
        x = int(raw_x)
        y = int(raw_y)
    except Exception as exc:
        raise ValueError(f"{context} coordinates must be integers") from exc

    return (x, y)


PRESET_LAYOUTS: dict[str, dict[str, Any]] = {
    "high_density": {
        "name": "high_density",
        "description": (
            "Higher rack density with three horizontal shelf blocks and a "
            "single perimeter service corridor."
        ),
        "layout": [
            "R..C.....X..S",
            ".###########.",
            ".a.........a.",
            ".###########.",
            ".a.........a.",
            ".###########.",
            ".a.........a.",
            ".K....P....G.",
            ".............",
        ],
        "locations": {
            "RECEIVING-1": {"cell": [0, 0], "access": [0, 0]},
            "SHIPPING-1": {"cell": [12, 0], "access": [12, 0]},
            "CHARGING-1": {"cell": [3, 0], "access": [3, 0]},
            "MAINTENANCE-1": {"cell": [9, 0], "access": [9, 0]},
            "PICK-1": {"cell": [1, 7], "access": [1, 7]},
            "PACK-1": {"cell": [6, 7], "access": [6, 7]},
            "STAGING-1": {"cell": [11, 7], "access": [11, 7]},
            "A-01": {"cell": [2, 1], "access": [2, 2]},
            "B-01": {"cell": [2, 3], "access": [2, 2]},
            "C-01": {"cell": [2, 5], "access": [2, 6]},
        },
    },
    "one_way_aisles": {
        "name": "one_way_aisles",
        "description": (
            "Narrow single-cell aisle geometry. This changes physical "
            "constraints only. It does not enforce directional traffic rules."
        ),
        "layout": [
            "R..C.....X..S",
            ".#.#.#.#.#.#.",
            ".a.a.a.a.a.a.",
            ".#.#.#.#.#.#.",
            ".a.a.a.a.a.a.",
            ".#.#.#.#.#.#.",
            ".a.a.a.a.a.a.",
            ".K....P....G.",
            ".............",
        ],
        "locations": {
            "RECEIVING-1": {"cell": [0, 0], "access": [0, 0]},
            "SHIPPING-1": {"cell": [12, 0], "access": [12, 0]},
            "CHARGING-1": {"cell": [3, 0], "access": [3, 0]},
            "MAINTENANCE-1": {"cell": [9, 0], "access": [9, 0]},
            "PICK-1": {"cell": [1, 7], "access": [1, 7]},
            "PACK-1": {"cell": [6, 7], "access": [6, 7]},
            "STAGING-1": {"cell": [11, 7], "access": [11, 7]},
            "A-01": {"cell": [1, 1], "access": [1, 2]},
            "B-01": {"cell": [3, 1], "access": [3, 2]},
            "C-01": {"cell": [1, 3], "access": [1, 2]},
        },
    },
}