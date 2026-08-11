# API Surface

This document lists the important names used by the warehouse simulator.
If code and documentation disagree, the code is the source of truth, but this file should be updated immediately.

## Breaking Changes From v0.2.0

- `Warehouse` constructor: `pickup` / `dropoff` arguments removed; replaced by a `locations` mapping.
- `warehouse.pickup` / `warehouse.dropoff` attributes removed.
- `Task.pickup` / `Task.dropoff` changed from `tuple[int, int]` to `str` (location names).
- Warehouse JSON: `pickup` / `dropoff` keys removed; `locations` and `racks` keys added.
- Task JSON: `pickup` / `dropoff` values are now strings.

## Coordinate System

Coordinates are `(x, y)`.
`x` increases to the right.
`y` increases downward.
Origin is top-left.

## Naming Rules

### Python
Classes use `PascalCase`.
Functions and variables use `snake_case`.
Private methods start with `_`.
Enum members use `UPPER_SNAKE_CASE`.

### JSON
JSON keys use `camelCase`.

### JavaScript
Functions and variables use `camelCase`.
DOM element variables usually end with `El`.

## Python Modules

### `simulation/warehouse.py`

#### `CellType`
```python
class CellType(str, Enum)

Members:

    EMPTY
    SHELF
    AISLE
    MAIN_AISLE
    PACKING
    RECEIVING
    SHIPPING
    CHARGING
    INTERSECTION
    BUFFER
    PICK_STATION
    CONSOLIDATION
    STAGING
    MAINTENANCE

Values are the same as member names:
CellType.EMPTY.value == "EMPTY"
CellType.SHELF.value == "SHELF"
LAYOUT_SYMBOLS

LAYOUT_SYMBOLS: dict[str, CellType]

Supported layout symbols:

    . EMPTY
    E EMPTY
    # SHELF
    a AISLE
    M MAIN_AISLE
    P PACKING
    R RECEIVING
    S SHIPPING
    C CHARGING
    I INTERSECTION
    B BUFFER
    K PICK_STATION
    O CONSOLIDATION
    G STAGING
    X MAINTENANCE

Location

@dataclass(frozen=True)
class Location

Fields:

    location.name: str
    location.cell: tuple[int, int]
    location.access: tuple[int, int]

Meaning:
cell is the physical cell the location represents (a shelf cell for storage locations, the station cell for work stations).
access is the passable cell an AMR actually drives to.

Warehouse
class Warehouse

Constructor:
Warehouse(
    layout: Iterable[str],
    locations: Mapping[str, Location] | None = None,
)

