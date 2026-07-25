from flask import Flask, jsonify, render_template

from simulation.robot import Robot, RobotStatus
from simulation.scheduler import CostBasedScheduler
from simulation.simulation import Simulation
from simulation.task import Task, TaskType
from simulation.task_generator import TaskGenerator
from simulation.metrics import Metrics
from simulation.warehouse import Location, Warehouse

from simulation.warehouse_layout import build_warehouse

def create_initial_warehouse() -> Warehouse:
    return build_warehouse()


def create_initial_robots() -> list[Robot]:
    return [
        Robot(id="R1", x=1, y=7, color="#ef4444", status=RobotStatus.IDLE, path=[], current_task_id=None),
        Robot(id="R2", x=9, y=7, color="#3b82f6", status=RobotStatus.IDLE, path=[], current_task_id=None),
        Robot(id="R3", x=17, y=7, color="#10b981", status=RobotStatus.IDLE, path=[], current_task_id=None),
        Robot(id="R4", x=24, y=7, color="#f59e0b", status=RobotStatus.IDLE, path=[], current_task_id=None),
        Robot(id="R5", x=1, y=20, color="#8b5cf6", status=RobotStatus.IDLE, path=[], current_task_id=None),
        Robot(id="R6", x=9, y=20, color="#2a7016", status=RobotStatus.IDLE, path=[], current_task_id=None),
        Robot(id="R7", x=17, y=20, color="#14b8a6", status=RobotStatus.IDLE, path=[], current_task_id=None),
        Robot(id="R8", x=24, y=20, color="#f97316", status=RobotStatus.IDLE, path=[], current_task_id=None),
        Robot(id="R9", x=1, y=0, color="#e11d48", status=RobotStatus.IDLE, path=[], current_task_id=None),
        Robot(id="R10", x=9, y=0, color="#2563eb", status=RobotStatus.IDLE, path=[], current_task_id=None),
        Robot(id="R11", x=17, y=0, color="#22c55e", status=RobotStatus.IDLE, path=[], current_task_id=None),
        #Robot(id="R12", x=12, y=1, color="#983084", status=RobotStatus.IDLE, path=[], current_task_id=None),
        #Robot(id="R13", x=13, y=0, color="#63431b", status=RobotStatus.IDLE, path=[], current_task_id=None),
        
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
        task_generator=TaskGenerator(warehouse, seed=731),
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