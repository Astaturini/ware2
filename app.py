from __future__ import annotations

from flask import Flask, Response, jsonify, render_template

from simulation.robot import Robot
from simulation.simulation import Simulation
from simulation.task import Task
from simulation.warehouse import Warehouse


WAREHOUSE_LAYOUT = [
    "E" * 20,
    "RRa###a###a###aPPaSS",
    "RRa###a###a###aPPaSS",
    "RRa###a###a###aPPaSS",
    "RRa###a###a###aPPaSS",
    "MMIMMMIMMMIMMMIMMIMM",
    "EEa###a###a###aEEaSS",
    "EEa###a###a###aEEaSS",
    "EEa###a###a###aEEaSS",
    "EEa###a###a###aEEaSS",
    "CC" + "a" * 13 + "EEaSS",
    "CC" + "E" * 18,
]


def create_initial_warehouse() -> Warehouse:
    """Create the tile-based warehouse.

    Pickup is in RECEIVING.
    Dropoff is in PACKING.
    """
    return Warehouse(
        layout=WAREHOUSE_LAYOUT,
        pickup=(1, 2),
        dropoff=(15, 2),
    )


def create_initial_robots() -> list[Robot]:
    """Create robots on passable cells."""
    return [
        Robot(id="R1", x=1, y=5, color="#ef4444"),
        Robot(id="R2", x=6, y=10, color="#3b82f6"),
    ]


def create_initial_tasks(warehouse: Warehouse) -> list[Task]:
    """Create simple transport tasks from receiving to packing."""
    return [
        Task(
            id="T1",
            name="Inbound A to Packing",
            pickup=warehouse.pickup,
            dropoff=warehouse.dropoff,
        ),
        Task(
            id="T2",
            name="Inbound B to Packing",
            pickup=warehouse.pickup,
            dropoff=warehouse.dropoff,
        ),
        Task(
            id="T3",
            name="Inbound C to Packing",
            pickup=warehouse.pickup,
            dropoff=warehouse.dropoff,
        ),
        Task(
            id="T4",
            name="Inbound D to Packing",
            pickup=warehouse.pickup,
            dropoff=warehouse.dropoff,
        ),
    ]


def create_default_simulation() -> Simulation:
    warehouse = create_initial_warehouse()
    robots = create_initial_robots()
    tasks = create_initial_tasks(warehouse)

    return Simulation(
        warehouse=warehouse,
        robots=robots,
        tasks=tasks,
        tick_interval=0.35,
    )


def create_app(
    simulation: Simulation | None = None,
    start_simulation: bool = True,
) -> Flask:
    if simulation is None:
        simulation = create_default_simulation()

    app = Flask(__name__)

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.get("/api/state")
    def get_state() -> Response:
        return jsonify(simulation.get_state())

    @app.post("/api/pause")
    def pause() -> Response:
        simulation.pause()
        return jsonify({"status": "paused"})

    @app.post("/api/resume")
    def resume() -> Response:
        simulation.resume()
        return jsonify({"status": "running"})

    @app.post("/api/reset")
    def reset() -> Response:
        simulation.reset()
        return jsonify({"status": "reset"})

    if start_simulation:
        simulation.start()

    return app


if __name__ == "__main__":
    simulation = create_default_simulation()
    app = create_app(simulation, start_simulation=True)

    try:
        app.run(
            host="127.0.0.1",
            port=5000,
            debug=False,
            use_reloader=False,
            threaded=True,
        )
    finally:
        simulation.stop()