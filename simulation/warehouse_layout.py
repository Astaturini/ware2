from .warehouse import Location, Warehouse

def build_warehouse() -> Warehouse:
    """Build the layout grid and the named locations together so they match."""
    width, height = 26, 21
    grid = [["."] * width for _ in range(height)]
    locations: dict[str, Location] = {}
    ACCESS_ROW = 4

    def paint(x0: int, y0: int, x1: int, y1: int, ch: str) -> None:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                grid[y][x] = ch

    def add_rack(letter: str, col: int, top: int, bottom: int) -> None:
        paint(col, top, col + 3, bottom, "#")
        idx = 1
        for y in (top, bottom):
            for x in range(col, col + 4):
                name = f"{letter}-{idx:02d}"
                locations[name] = Location(name, (x, y), (x, ACCESS_ROW))
                idx += 1

    paint(0, 0, 5, 1, "R")
    paint(8, 0, 19, 0, "B")
    locations["RECV"] = Location("RECV", (2, 1), (2, 1))
    locations["BUFFER"] = Location("BUFFER", (12, 0), (12, 0))

    rack_cols = {"A": 2, "B": 8, "C": 14, "D": 20}
    lower = {"A": "E", "B": "F", "C": "G", "D": "H"}
    for letter, col in rack_cols.items():
        add_rack(letter, col, 2, 3)
        add_rack(lower[letter], col, 5, 6)
        paint(col, ACCESS_ROW, col + 3, ACCESS_ROW, "a")

    paint(0, ACCESS_ROW, width - 1, ACCESS_ROW, "a")
    for x0, x1 in ((0, 1), (6, 7), (12, 13), (18, 19), (24, 25)):
        paint(x0, 2, x1, 6, "a")

    paint(0, 7, width - 1, 7, "M")

    for name, col in {"PICK-1": 4, "PICK-2": 12, "PICK-3": 20}.items():
        paint(col, 8, col + 1, 9, "K")
        locations[name] = Location(name, (col, 8), (col, 8))

    paint(10, 10, 15, 11, "O")
    locations["CONSOL"] = Location("CONSOL", (12, 10), (12, 10))

    paint(9, 12, 11, 13, "P")
    paint(14, 12, 16, 13, "P")
    locations["PACK-1"] = Location("PACK-1", (10, 12), (10, 12))
    locations["PACK-2"] = Location("PACK-2", (15, 12), (15, 12))

    paint(10, 14, 15, 14, "G")
    locations["STAGING"] = Location("STAGING", (12, 14), (12, 14))

    paint(10, 15, 11, 16, "S")
    paint(14, 15, 15, 16, "S")
    locations["DOCK-1"] = Location("DOCK-1", (10, 15), (10, 15))
    locations["DOCK-2"] = Location("DOCK-2", (14, 15), (14, 15))

    paint(1, 18, 3, 20, "C")
    for i, x in enumerate((1, 2, 3), start=1):
        locations[f"CHG-{i}"] = Location(f"CHG-{i}", (x, 18), (x, 18))

    paint(14, 18, 19, 20, "X")
    locations["MAINT"] = Location("MAINT", (16, 18), (16, 18))

    layout = ["".join(row) for row in grid]
    return Warehouse(layout=layout, locations=locations)