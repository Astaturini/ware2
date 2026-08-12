# API Surface

This document lists the important names used by the warehouse simulator.
If code and documentation disagree, the code is the source of truth, but this file should be updated immediately.

## Breaking Changes From v0.2.0

- `Warehouse` constructor: `pickup` / `dropoff` arguments were removed and replaced with a `locations` mapping.
- `warehouse.pickup` and `warehouse.dropoff` attributes were removed.
- `Task.pickup` and `Task.dropoff` changed from `tuple[int, int]` to `str` (location names).
- `Task` gained `task_type`, `priority`, `created_at`, and `completed_at`.
- Warehouse JSON: `pickup` / `dropoff` keys were removed; `locations` and `racks` were added.
- Task JSON: `pickup` / `dropoff` values are now strings.
- `/api/state` now includes a `metrics` object with aggregate operational data.

## Coordinate System

- Coordinates are `(x, y)`.
- `x` increases to the right.
- `y` increases downward.
- Origin is the top-left corner.

## Naming Rules

### Python

- Classes use `PascalCase`.
- Functions and variables use `snake_case`.
- Private methods start with `_`.
- Enum members use `UPPER_SNAKE_CASE`.

### JSON

- JSON keys use `camelCase`.

### JavaScript

- Functions and variables use `camelCase`.
- DOM element variables usually end with `El`.

## Python Modules

### `simulation/warehouse.py`

#### `CellType`

```python
class CellType(str, Enum)
```

Members:

- `EMPTY`
- `SHELF`
- `AISLE`
- `MAIN_AISLE`
- `PACKING`
- `RECEIVING`
- `SHIPPING`
- `CHARGING`
- `INTERSECTION`
- `BUFFER`
- `PICK_STATION`
- `CONSOLIDATION`
- `STAGING`
- `MAINTENANCE`

Values are the same as the member names:

```python
CellType.EMPTY.value == "EMPTY"
CellType.SHELF.value == "SHELF"
```

`LAYOUT_SYMBOLS`

```python
LAYOUT_SYMBOLS: dict[str, CellType]
```

Supported layout symbols:

- `.` → `EMPTY`
- `E` → `EMPTY`
- `#` → `SHELF`
- `a` → `AISLE`
- `M` → `MAIN_AISLE`
- `P` → `PACKING`
- `R` → `RECEIVING`
- `S` → `SHIPPING`
- `C` → `CHARGING`
- `I` → `INTERSECTION`
- `B` → `BUFFER`
- `K` → `PICK_STATION`
- `O` → `CONSOLIDATION`
- `G` → `STAGING`
- `X` → `MAINTENANCE`

#### `Location`

```python
@dataclass(frozen=True)
class Location
```

Fields:

- `location.name: str`
- `location.cell: tuple[int, int]`
- `location.access: tuple[int, int]`

Meaning:

- `cell` is the physical cell the location represents (a shelf cell for storage locations, or the station cell for work stations).
- `access` is the passable cell an AMR actually drives to.

#### `Warehouse`

```python
class Warehouse
```

Constructor:

```python
Warehouse(
    layout: Iterable[str],
    locations: Mapping[str, Location] | None = None,
)
```

Public attributes:

- `warehouse.width: int`
- `warehouse.height: int`
- `warehouse.layout: list[list[CellType]]`
- `warehouse.locations: dict[str, Location]`

Public methods:

- `warehouse.in_bounds(x: int, y: int) -> bool`
- `warehouse.cell_type(x: int, y: int) -> CellType`
- `warehouse.is_blocked(x: int, y: int) -> bool`
- `warehouse.resolve(name: str) -> tuple[int, int]`
- `warehouse.to_dict() -> dict[str, Any]`

Property:

- `warehouse.obstacles -> frozenset[tuple[int, int]]`

Private methods:

- `warehouse._parse_layout(layout) -> list[list[CellType]]` (static)
- `warehouse._validate() -> None`
- `warehouse._rack_anchors() -> dict[str, list[int]]`

Important behavior:

- `is_blocked()` returns `True` for out-of-bounds cells.
- `is_blocked()` returns `True` for `SHELF` cells.
- All other cell types are currently passable.
- `resolve()` returns the location's access coordinate and raises `KeyError` for unknown names.
- `_validate()` checks that every location's cell and access are in bounds and that access is not blocked.
- `_rack_anchors()` returns one anchor cell per rack letter, used for map labels (`"B"`, not `"B-02"`).

### `simulation/robot.py`

#### `RobotStatus`

```python
class RobotStatus(str, Enum)
```

Members:

- `IDLE = "Idle"`
- `MOVING = "Moving"`

#### `Robot`

```python
@dataclass
class Robot
```

Fields:

- `robot.id: str`
- `robot.x: int`
- `robot.y: int`
- `robot.color: str`
- `robot.status: RobotStatus`
- `robot.path: list[tuple[int, int]]`
- `robot.current_task_id: str | None`

Property:

- `robot.current_target -> tuple[int, int] | None`

Public methods:

- `robot.set_path(path: list[tuple[int, int]]) -> None`
- `robot.advance() -> bool`
- `robot.to_dict() -> dict[str, Any]`

Important behavior:

- `set_path()` expects a path excluding the robot's current cell.
- `advance()` moves the robot one cell.
- `advance()` returns `True` when the robot reaches the end of its path.

### `simulation/task.py`

#### `TaskType`

```python
class TaskType(str, Enum)
```

Members:

- `PUTAWAY`
- `PICK`
- `PACK`
- `SHIP`
- `LEGACY`

#### `TaskStatus`

```python
class TaskStatus(str, Enum)
```

Members:

- `PENDING = "Pending"`
- `ASSIGNED = "Assigned"`
- `COMPLETED = "Completed"`
- `FAILED = "Failed"`

#### `TaskPhase`

```python
class TaskPhase(str, Enum)
```

Members:

- `TO_PICKUP = "To pickup"`
- `TO_DROPOFF = "To dropoff"`
- `DONE = "Done"`

#### `Task`

```python
@dataclass
class Task
```

Fields:

- `task.id: str`
- `task.name: str`
- `task.pickup: str`
- `task.dropoff: str`
- `task.task_type: TaskType`
- `task.priority: int`
- `task.created_at: int`
- `task.completed_at: int | None`
- `task.status: TaskStatus`
- `task.assigned_robot_id: str | None`
- `task.phase: TaskPhase`

Public methods:

- `task.to_dict() -> dict[str, Any]`

Important behavior:

- `pickup` and `dropoff` are location names, resolved to coordinates via `warehouse.resolve()`.

### `simulation/task_generator.py`

#### `TaskGenerator`

```python
class TaskGenerator
```

Constructor:

```python
TaskGenerator(warehouse: Warehouse, start_tick: int = 2)
```

Public methods:

- `task_generator.step(tick: int) -> list[Task]`
- `task_generator.reset() -> None`

Important behavior:

- Generates tasks during the simulation instead of seeding all work at startup.
- Emits a light stream of `PUTAWAY`, `PICK`, `PACK`, and `SHIP` tasks using the existing named locations.
- Uses the warehouse layout to pick reasonable pickup and dropoff names.

### `simulation/scheduler.py`

#### `Assignment`

```python
@dataclass(frozen=True)
class Assignment
```

Fields:

- `assignment.task_id: str`
- `assignment.robot_id: str`
- `assignment.cost: int`
- `assignment.path: list[tuple[int, int]]`

#### `CostBasedScheduler`

```python
class CostBasedScheduler
```

Public methods:

- `select_assignments(pending_tasks, robots, warehouse, blocked_cells=None) -> list[Assignment]`

Important behavior:

- Centralized baseline scheduler used by v0.3.
- Chooses the idle robot with the shortest feasible path to each pending task pickup.
- Is structured so a different scheduling strategy can be swapped in later.

### `simulation/metrics.py`

#### `Metrics`

```python
class Metrics
```

Public methods:

- `record_generated(task) -> None`
- `record_assigned(task, tick) -> None`
- `record_completed(task, tick) -> None`
- `record_failed(task, tick) -> None`
- `record_robot_move(robot, distance=1) -> None`
- `record_tick(robots) -> None`
- `to_dict(tick_interval) -> dict[str, Any]`

Important behavior:

- Tracks task throughput, wait time, completion time, robot distance, busy
  time, and utilization.

### `simulation/pathfinding.py`

#### `find_shortest_path`

```python
find_shortest_path(
    warehouse: Warehouse,
    start: tuple[int, int],
    goal: tuple[int, int],
  blocked_cells: Iterable[tuple[int, int]] | None = None,
) -> list[tuple[int, int]] | None
```

Return meaning:

- `[]` — already at the goal
- `[...]` — path cells after `start`
- `None` — no path found

Important behavior:

- Uses BFS.
- Avoids blocked cells.
- Currently treats all non-shelf cells as passable.
- May optionally avoid additional occupied cells supplied by the caller.

### `simulation/simulation.py`

#### `Simulation`

```python
class Simulation
```

Constructor:

```python
Simulation(
    warehouse: Warehouse,
    robots: list[Robot],
    tasks: list[Task],
    tick_interval: float = 0.3,
  scheduler: Scheduler | None = None,
  task_generator: TaskGenerator | None = None,
  metrics: Metrics | None = None,
)
```

Public methods:

- `simulation.start() -> None`
- `simulation.pause() -> None`
- `simulation.resume() -> None`
- `simulation.reset() -> None`
- `simulation.stop() -> None`
- `simulation.get_state() -> dict[str, Any]`
- `simulation.get_state() -> dict[str, Any]`

Property:

- `simulation.is_paused -> bool`

Important private methods:

- `simulation._validate_initial_state(robots, tasks) -> None`
- `simulation._run() -> None`
- `simulation._tick() -> None`
- `simulation._assign_pending_tasks() -> None`
- `simulation._begin_task(robot: Robot, task: Task) -> None`
- `simulation._route_robot_to(robot: Robot, task: Task, destination: tuple[int, int]) -> None`
- `simulation._handle_arrival(robot: Robot) -> None`
- `simulation._advance_robots() -> None`
- `simulation._occupied_cells() -> set[tuple[int, int]]`

Important internal state:

- `simulation._warehouse`
- `simulation._robots`
- `simulation._tasks`
- `simulation._initial_robots`
- `simulation._initial_tasks`
- `simulation._tick_count`
- `simulation._tick_interval`
- `simulation._lock`
- `simulation._stop_event`
- `simulation._running_event`
- `simulation._thread`

Important behavior:

- `start()` starts the background simulation thread.
- `pause()` stops ticking but keeps state.
- `resume()` continues ticking.
- `reset()` restores robots and tasks to their initial state.
- `get_state()` returns a JSON-serializable snapshot.
- `_validate_initial_state()` resolves task `pickup` and `dropoff` names and raises `ValueError` for unknown locations.
- `_begin_task()` routes to `warehouse.resolve(task.pickup)` and records assignment timing.
- `_handle_arrival()` routes to `warehouse.resolve(task.dropoff)` when arriving at pickup and records completion or failure.
- `_tick()` asks the task generator for new work, uses the scheduler to assign pending tasks, and records metrics.
- Pathfinding operates on coordinates only; name resolution happens at the call sites.
- The simulation reserves occupied cells during each tick so robots do not step into the same cell.

## Flask Layer

### `app.py`

Important constants:

- `WAREHOUSE_LAYOUT: list[str]`
- `WAREHOUSE_LOCATIONS: dict[str, Location]`

Important private functions:

- `_build_warehouse() -> tuple[list[str], dict[str, Location]]`

Important functions:

- `create_initial_warehouse() -> Warehouse`
- `create_initial_robots() -> list[Robot]`
- `create_initial_tasks(warehouse: Warehouse) -> list[Task]`
- `create_default_simulation() -> Simulation`
- `create_app(simulation: Simulation | None = None, start_simulation: bool = True) -> Flask`

Routes:

- `GET /`
- `GET /api/state`
- `POST /api/pause`
- `POST /api/resume`
- `POST /api/reset`

Important behavior:

- `WAREHOUSE_LAYOUT` and `WAREHOUSE_LOCATIONS` are generated together by `_build_warehouse()`, so the grid and the named locations never drift apart.
- `create_initial_tasks()` is now a legacy compatibility helper; the default
  app wiring uses dynamic generation instead of seeding those demo tasks.
- `create_default_simulation()` wires in the baseline scheduler, task
  generator, and metrics collector.
- `create_app()` may start the simulation automatically.
- Routes should remain thin.
- Business logic should stay in `simulation/`.

## JSON API

### `GET /api/state`

Returns:

```json
{
  "paused": false,
  "tick": 0,
  "warehouse": {
    "width": 26,
    "height": 21,
    "layout": [["EMPTY"]],
    "obstacles": [[2, 2]],
    "locations": {
      "A-01": { "cell": [2, 2], "access": [2, 4] },
      "PICK-1": { "cell": [4, 8], "access": [4, 8] }
    },
    "racks": { "A": [2, 2] }
  },
  "robots": [
    {
      "id": "R1",
      "x": 1,
      "y": 7,
      "color": "#ef4444",
      "status": "Idle",
      "currentTaskId": null,
      "currentTarget": null,
      "blockedTicks": 0,
      "replanning": false,
      "yieldingTo": null,
      "replanCooldown": 0
    }
  ],
  "tasks": [
    {
      "id": "T3",
      "name": "Pick order 1",
      "pickup": "B-02",
      "dropoff": "PICK-1",
      "taskType": "PICK",
      "priority": 1,
      "createdAt": 0,
      "completedAt": null,
      "status": "Pending",
      "assignedRobotId": null,
      "phase": "To pickup"
    }
  ],
  "metrics": {
    "tasksGenerated": 3,
    "tasksAssigned": 2,
    "tasksCompleted": 1,
    "tasksFailed": 0,
    "blockedTimeTicks": 0,
    "blockedTimeSeconds": 0.0,
    "replanningCount": 0,
    "deadlockResolutions": 0,
    "throughputPerTick": 0.02,
    "averageTaskWaitingTime": 4.0,
    "averageTaskCompletionTime": 19.0,
    "simulationTicks": 50,
    "simulationSeconds": 15.0,
    "robotDistanceTravelled": { "R1": 22 },
    "robotBusyTicks": { "R1": 22 },
    "robotUtilization": { "R1": 0.44 }
  }
}
```

Important JSON keys:

- `paused`
- `tick`
- `warehouse`
- `robots`
- `tasks`

Robot JSON keys:

- `id`
- `x`
- `y`
- `color`
- `status`
- `currentTaskId`
- `currentTarget`
- `blockedTicks`
- `replanning`
- `yieldingTo`
- `replanCooldown`

Task JSON keys:

- `id`
- `name`
- `pickup`
- `dropoff`
- `taskType`
- `priority`
- `createdAt`
- `completedAt`
- `status`
- `assignedRobotId`
- `phase`

Warehouse JSON keys:

- `width`
- `height`
- `layout`
- `obstacles`
- `locations`
- `racks`

Metrics JSON keys:

- `tasksGenerated`
- `tasksAssigned`
- `tasksCompleted`
- `tasksFailed`
- `blockedTimeTicks`
- `blockedTimeSeconds`
- `replanningCount`
- `deadlockResolutions`
- `throughputPerTick`
- `averageTaskWaitingTime`
- `averageTaskCompletionTime`
- `simulationTicks`
- `simulationSeconds`
- `robotDistanceTravelled`
- `robotBusyTicks`
- `robotUtilization`

## Frontend JavaScript

### `static/simulation.js`

Important constants:

- `CELL_SIZE`
- `POLL_INTERVAL_MS`

Important DOM ids:

- `warehouse`
- `robot-list`
- `task-list`
- `simulation-state`
- `pause-btn`
- `resume-btn`
- `reset-btn`

Important state variables:

- `robotElements`
- `previousWarehouseKey`
- `updateInProgress`

Important functions:

- `refresh()`
- `fetchState()`
- `postCommand(url)`
- `render(state)`
- `buildStaticLayer(warehouse)`
- `addCell(x, y, className, label)`
- `addMarker([x, y], text, tooltip)`
- `updateRobots(robots)`
- `updateSidePanel(state)`
- `createCard(title, rows, extraClass)`
- `createMetricCard(title, value, detail)`

Important behavior:

- The frontend polls `/api/state`.
- It rebuilds the static warehouse layer when the warehouse JSON changes.
- Robots are updated without rebuilding the entire warehouse.
- Tile rendering uses `warehouse.layout`.
- `buildStaticLayer()` also renders rack letter labels from `warehouse.racks`.
- Station markers are no longer added; zone naming lives in a static HTML legend below the map.
- `addMarker()` is retained but currently unused.
- Task cards display `pickup` / `dropoff` as strings and also show task type, status, and assignment details.
- The sidebar includes a compact operational dashboard for queue depth,
  throughput, average wait/completion time, and robot utilization.

## CSS Classes

### `static/style.css`

Tile classes:

- `.tile`
- `.empty`
- `.shelf`
- `.aisle`
- `.main_aisle`
- `.packing`
- `.receiving`
- `.shipping`
- `.charging`
- `.intersection`
- `.buffer`
- `.pick_station`
- `.consolidation`
- `.staging`
- `.maintenance`

Other important classes:

- `.marker`
- `.robot`
- `.robot.idle`
- `.rack-label`
- `.card`
- `.card-title`
- `.row`
- `.label`
- `.value`
- `.map-column`
- `.legend`
- `.legend-item`
- `.swatch`

## Extension Points

These are intentionally not implemented yet:

- `CHARGING` → battery charging behavior
- `INTERSECTION` → traffic control or collision avoidance
- `MAIN_AISLE` → priority routing or speed changes
- `PACKING` → packing queue or processing delay
- `RECEIVING` → inbound task generation
- `SHIPPING` → outbound task completion
- `EMPTY` → dynamic obstacles or editor placement
- `BUFFER` → QC delay or put-away scheduling
- `PICK_STATION` → pick processing time or queueing
- `CONSOLIDATION` → order merge logic
- `STAGING` → carrier lane assignment
- `MAINTENANCE` → robot repair / downtime behavior
