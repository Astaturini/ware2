from flask import Flask, jsonify, render_template

from simulation.robot import Robot, RobotStatus
from simulation.scheduler import CostBasedScheduler
from simulation.simulation import Simulation
from simulation.task import Task, TaskType
from simulation.task_generator import TaskGenerator
from simulation.metrics import Metrics
from simulation.warehouse import Location, Warehouse


def _build_warehouse() -> tuple[list[str], dict[str, Location]]:
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

    # Receiving + QC / put-away buffer
    paint(0, 0, 5, 1, "R")
    paint(8, 0, 19, 0, "B")
    locations["RECV"] = Location("RECV", (2, 1), (2, 1))
    locations["BUFFER"] = Location("BUFFER", (12, 0), (12, 0))

    # Racks A-D (top), E-H (bottom); shared access aisle on ACCESS_ROW
    rack_cols = {"A": 2, "B": 8, "C": 14, "D": 20}
    lower = {"A": "E", "B": "F", "C": "G", "D": "H"}
    for letter, col in rack_cols.items():
        add_rack(letter, col, 2, 3)
        add_rack(lower[letter], col, 5, 6)
        paint(col, ACCESS_ROW, col + 3, ACCESS_ROW, "a")
    
    #continuous travel corridors: full width access aisle + vertical aisles
    paint(0, ACCESS_ROW, width - 1, ACCESS_ROW, "a")
    for x0, x1 in ((0, 1), (6, 7), (12, 13), (18, 19), (24, 25)):
        paint(x0, 2, x1, 6, "a")

    # Main AMR cross-aisle
    paint(0, 7, width - 1, 7, "M")

    # Pick stations
    for name, col in {"PICK-1": 4, "PICK-2": 12, "PICK-3": 20}.items():
        paint(col, 8, col + 1, 9, "K")
        locations[name] = Location(name, (col, 8), (col, 8))

    
    # Consolidation
    paint(10, 10, 15, 11, "O")
    locations["CONSOL"] = Location("CONSOL", (12, 10), (12, 10))

    # Packing
    paint(9, 12, 11, 13, "P")
    paint(14, 12, 16, 13, "P")
    locations["PACK-1"] = Location("PACK-1", (10, 12), (10, 12))
    locations["PACK-2"] = Location("PACK-2", (15, 12), (15, 12))

    # Outbound staging
    paint(10, 14, 15, 14, "G")
    locations["STAGING"] = Location("STAGING", (12, 14), (12, 14))

    # Shipping docks
    paint(10, 15, 11, 16, "S")
    paint(14, 15, 15, 16, "S")
    locations["DOCK-1"] = Location("DOCK-1", (10, 15), (10, 15))
    locations["DOCK-2"] = Location("DOCK-2", (14, 15), (14, 15))

    # Charging bays + maintenance
    paint(1, 18, 3, 20, "C")
    for i, x in enumerate((1, 2, 3), start=1):
        locations[f"CHG-{i}"] = Location(f"CHG-{i}", (x, 18), (x, 18))
    paint(14, 18, 19, 20, "X")
    locations["MAINT"] = Location("MAINT", (16, 18), (16, 18))

    return ["".join(row) for row in grid], locations


WAREHOUSE_LAYOUT, WAREHOUSE_LOCATIONS = _build_warehouse()


def create_initial_warehouse() -> Warehouse:
    return Warehouse(layout=WAREHOUSE_LAYOUT, locations=WAREHOUSE_LOCATIONS)


def create_initial_robots() -> list[Robot]:
    return [
        Robot(id="R1", x=1, y=7, color="#ef4444", status=RobotStatus.IDLE, path=[], current_task_id=None),
        Robot(id="R2", x=9, y=7, color="#3b82f6", status=RobotStatus.IDLE, path=[], current_task_id=None),
        Robot(id="R3", x=17, y=7, color="#10b981", status=RobotStatus.IDLE, path=[], current_task_id=None),
        Robot(id="R4", x=24, y=7, color="#f59e0b", status=RobotStatus.IDLE, path=[], current_task_id=None),
        Robot(id="R5", x=1, y=20, color="#8b5cf6", status=RobotStatus.IDLE, path=[], current_task_id=None),
        Robot(id="R6", x=9, y=20, color="#ec4899", status=RobotStatus.IDLE, path=[], current_task_id=None),
        Robot(id="R7", x=17, y=20, color="#14b8a6", status=RobotStatus.IDLE, path=[], current_task_id=None),
        Robot(id="R8", x=24, y=20, color="#f97316", status=RobotStatus.IDLE, path=[], current_task_id=None),
        Robot(id="R9", x=1, y=0, color="#e11d48", status=RobotStatus.IDLE, path=[], current_task_id=None),
        Robot(id="R10", x=9, y=0, color="#2563eb", status=RobotStatus.IDLE, path=[], current_task_id=None),
    ]


def create_initial_tasks(warehouse: Warehouse) -> list[Task]:
    """Legacy compatibility demo tasks.

    The v0.3 default simulation no longer starts with these tasks, but keeping
    the helper avoids breaking callers that still expect the old demo dataset.
    """
    specs = [
        ("T1", "Inbound putaway A", "RECV", "A-03", TaskType.PUTAWAY),
        ("T2", "Inbound putaway C", "BUFFER", "C-01", TaskType.PUTAWAY),
        ("T3", "Pick order 1", "B-02", "PICK-1", TaskType.PICK),
        ("T4", "Pick order 2", "F-05", "PICK-2", TaskType.PICK),
        ("T5", "Move to packing", "CONSOL", "PACK-1", TaskType.PACK),
        ("T6", "Ship outbound", "PACK-2", "DOCK-1", TaskType.SHIP),
    ]
    return [
        Task(
            id=tid,
            name=name,
            pickup=pickup,
            dropoff=dropoff,
            task_type=task_type,
        )
        for (tid, name, pickup, dropoff, task_type) in specs
    ]


def create_default_simulation() -> Simulation:
    warehouse = create_initial_warehouse()
    robots = create_initial_robots()
    return Simulation(
        warehouse=warehouse,
        robots=robots,
        tasks=[],
        scheduler=CostBasedScheduler(),
        task_generator=TaskGenerator(warehouse, seed=42),
        metrics=Metrics(),
    )


def create_app(
    simulation: Simulation | None = None,
    start_simulation: bool = True,
) -> Flask:
    if simulation is None:
        simulation = create_default_simulation()

    app = Flask(__name__)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/state")
    def state():
        return jsonify(simulation.get_state())

    @app.post("/api/pause")
    def pause():
        simulation.pause()
        return jsonify({"paused": simulation.is_paused})

    @app.post("/api/resume")
    def resume():
        simulation.resume()
        return jsonify({"paused": simulation.is_paused})

    @app.post("/api/reset")
    def reset():
        simulation.reset()
        return jsonify({"paused": simulation.is_paused})

    if start_simulation:
        simulation.start()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=False)