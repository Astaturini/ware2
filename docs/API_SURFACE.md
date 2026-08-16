# API Surface

This document lists the important names used by the warehouse simulator.

If code and documentation disagree, the code is the source of truth, but this
file should be updated immediately.

## Breaking Changes From v0.2.0

`Warehouse` constructor: `pickup` / `dropoff` arguments were removed and
replaced with a `locations` mapping.

`warehouse.pickup` and `warehouse.dropoff` attributes were removed.

`Task.pickup` and `Task.dropoff` changed from `tuple[int, int]` to `str`
(location names).

`Task` gained `task_type`, `priority`, `created_at`, and `completed_at`.

Warehouse JSON: `pickup` / `dropoff` keys were removed; `locations` and
`racks` were added.

Task JSON: `pickup` / `dropoff` values are now strings.

`/api/state` now includes a `metrics` object with aggregate operational data.

## Changes From v0.3.0 (v0.3.1)

No breaking JSON API changes. Robot, task, and warehouse JSON keys are
unchanged.

`Simulation` gained traffic/conflict-resolution state and methods, and its
constructor accepts optional traffic tuning arguments:
`blocked_replan_seconds` (default `0.9`) and `replan_cooldown_ticks`
(default `2`).

`TaskGenerator` gained an optional `seed` argument for reproducible random
location selection. `seed=None` preserves the old deterministic round-robin
behavior.

`Simulation._prune_old_tasks()` removes completed/failed tasks older than
100 ticks so the JSON payload and UI stay small.

Frontend: the `robot-list` sidebar section was removed. The sidebar now shows
the dashboard on top and a scrollable task list below. Robots and task
locations are highlighted on the map instead.

## Coordinate System

Coordinates are `(x, y)`.

`x` increases to the right.

`y` increases downward.

Origin is the top-left corner.

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

class CellType(str, Enum)

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

    CellType.EMPTY.value == "EMPTY"
    CellType.SHELF.value == "SHELF"

#### `LAYOUT_SYMBOLS`

LAYOUT_SYMBOLS: dict[str, CellType]

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

@dataclass(frozen=True)
class Location

Fields:

- `location.name: str`
- `location.cell: tuple[int, int]`
- `location.access: tuple[int, int]`

Meaning:

`cell` is the physical cell the location represents (a shelf cell for storage
locations, or the station cell for work stations).

`access` is the passable cell an AMR actually drives to.

#### `Warehouse`

class Warehouse

Constructor:

    Warehouse(
        layout: Iterable[str],
        locations: Mapping[str, Location] | None = None,
    )

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

`is_blocked()` returns `True` for out-of-bounds cells.

`is_blocked()` returns `True` for `SHELF` cells.

All other cell types are currently passable.

`resolve()` returns the location's access coordinate and raises `KeyError`
for unknown names.

`_validate()` checks that every location's cell and access are in bounds and
that access is not blocked.

`_rack_anchors()` returns one anchor cell per rack letter, used for map
labels (`"B"`, not `"B-02"`).

---

### `simulation/robot.py`

#### `RobotStatus`

class RobotStatus(str, Enum)

Members:

- `IDLE = "Idle"`
- `MOVING = "Moving"`

#### `Robot`

@dataclass
class Robot

Fields:

- `robot.id: str`
- `robot.x: int`
- `robot.y: int`
- `robot.color: str`
- `robot.status: RobotStatus`
- `robot.path: list[tuple[int, int]]`
- `robot.current_task_id: str | None`
- `robot.route_goal: tuple[int, int] | None`
- `robot.blocked_ticks: int`
- `robot.replanning: bool`
- `robot.yielding_to: str | None`
- `robot.replan_cooldown: int`
- `robot.travel_history: list[tuple[int, int]]`

Property:

- `robot.current_target -> tuple[int, int] | None`

Public methods:

- `robot.set_path(path: list[tuple[int, int]]) -> None`
- `robot.advance() -> bool`
- `robot.to_dict() -> dict[str, Any]`

Important behavior:

`set_path()` expects a path excluding the robot's current cell.

`advance()` moves the robot one cell.

`advance()` returns `True` when the robot reaches the end of its path.

`route_goal` is the current final destination for the robot's current task
phase.

`travel_history` stores previously visited cells and is used for backtracking
during yield maneuvers.

---

### `simulation/task.py`

#### `TaskType`

class TaskType(str, Enum)

Members:

- `PUTAWAY`
- `PICK`
- `PACK`
- `SHIP`
- `LEGACY`

#### `TaskStatus`

class TaskStatus(str, Enum)

Members:

- `PENDING = "Pending"`
- `ASSIGNED = "Assigned"`
- `COMPLETED = "Completed"`
- `FAILED = "Failed"`

#### `TaskPhase`

class TaskPhase(str, Enum)

Members:

- `TO_PICKUP = "To pickup"`
- `TO_DROPOFF = "To dropoff"`
- `DONE = "Done"`

#### `Task`

@dataclass
class Task

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

`pickup` and `dropoff` are location names, resolved to coordinates via
`warehouse.resolve()`.

---

### `simulation/task_generator.py`

#### `TaskGenerator`

@dataclass
class TaskGenerator

Constructor fields:

- `warehouse: Warehouse`
- `start_tick: int = 2`
- `seed: int | None = None`

Public methods:

- `task_generator.step(tick: int) -> list[Task]`
- `task_generator.reset() -> None`

Private methods:

- `_refresh_location_cache() -> None`
- `_create_task(task_type: TaskType, tick: int) -> Task`
- `_pick_one(values: list[str], fallback: str | None = None) -> str`
- `_priority_for(task_type: TaskType) -> int` (static)
- `_interval_for(task_type: TaskType) -> int` (static)

Important behavior:

Generates tasks during the simulation instead of seeding all work at startup.

Emits a light stream of `PUTAWAY`, `PICK`, `PACK`, and `SHIP` tasks using the
existing named locations.

First due ticks: `PUTAWAY` at `start_tick`, `PICK` at `start_tick + 2`,
`PACK` at `start_tick + 4`, `SHIP` at `start_tick + 6`.

Generation intervals (ticks): `PUTAWAY` 8, `PICK` 10, `PACK` 12, `SHIP` 14.

Priority mapping (lower number = higher priority):

- `SHIP` = 0 (most urgent)
- `PACK` = 1
- `PICK` = 2
- `PUTAWAY` = 3 (least urgent)

If `seed` is an int, `_pick_one()` uses a private `random.Random(seed)`
instance for reproducible location selection. `reset()` re-seeds with the
same seed. If `seed` is None, selection stays deterministic round-robin.

---

### `simulation/scheduler.py`

#### `Assignment`

@dataclass(frozen=True)
class Assignment

Fields:

- `assignment.task_id: str`
- `assignment.robot_id: str`
- `assignment.cost: int`
- `assignment.path: list[tuple[int, int]]`

#### `CostBasedScheduler`

class CostBasedScheduler

Public methods:

- `select_assignments(pending_tasks, robots, warehouse, blocked_cells=None) -> list[Assignment]`

Important behavior:

Centralized baseline scheduler used by v0.3.

Chooses the idle robot with the shortest feasible path to each pending task
pickup.

Is structured so a different scheduling strategy can be swapped in later.

---

### `simulation/metrics.py`

#### `Metrics`

@dataclass
class Metrics

Important fields:

- `metrics.tasks_generated: int`
- `metrics.tasks_assigned: int`
- `metrics.tasks_completed: int`
- `metrics.tasks_failed: int`
- `metrics.blocked_time_ticks: int`
- `metrics.replanning_count: int`
- `metrics.deadlock_resolutions: int`
- `metrics.task_waiting_time_total: float`
- `metrics.task_completion_time_total: float`
- `metrics.robot_distance_travelled: dict[str, int]`
- `metrics.robot_busy_ticks: dict[str, int]`
- `metrics.robot_total_ticks: dict[str, int]`
- `metrics.robot_blocked_ticks: dict[str, int]`
- `metrics.robot_replan_events: dict[str, int]`
- `metrics.tick_count: int`

Public methods:

- `metrics.reset() -> None`
- `metrics.register_robot(robot: Robot) -> None`
- `metrics.record_generated(task: Task) -> None`
- `metrics.record_assigned(task: Task, tick: int) -> None`
- `metrics.record_completed(task: Task, tick: int) -> None`
- `metrics.record_failed(task: Task, tick: int) -> None`
- `metrics.record_blocked(robot: Robot, blocked_ticks: int = 1) -> None`
- `metrics.record_replan(robot: Robot) -> None`
- `metrics.record_deadlock_resolution() -> None`
- `metrics.record_robot_move(robot: Robot, distance: int = 1) -> None`
- `metrics.record_tick(robots: list[Robot]) -> None`
- `metrics.to_dict(tick_interval: float) -> dict[str, Any]`

Important behavior:

Tracks task throughput, wait time, completion time, robot distance, busy
time, blocked time, replanning activity, and utilization.

---

### `simulation/pathfinding.py`

#### `find_shortest_path`

    find_shortest_path(
        warehouse: Warehouse,
        start: tuple[int, int],
        goal: tuple[int, int],
        blocked_cells: Iterable[tuple[int, int]] | None = None,
    ) -> list[tuple[int, int]] | None

Return meaning:

- `[]` — already at the goal
- `[...]` — path cells after `start`
- `None` — no path found

Important behavior:

Uses BFS.

Avoids blocked cells.

Currently treats all non-shelf cells as passable.

May optionally avoid additional occupied cells supplied by the caller.

---

### `simulation/simulation.py`

#### `Simulation`

class Simulation

Constructor:

    Simulation(
        warehouse: Warehouse,
        robots: list[Robot],
        tasks: list[Task],
        tick_interval: float = 0.3,
        scheduler: Scheduler | None = None,
        task_generator: TaskGenerator | None = None,
        metrics: Metrics | None = None,
        blocked_replan_seconds: float = 0.9,
        replan_cooldown_ticks: int = 2,
    )

Public methods:

- `simulation.start() -> None`
- `simulation.pause() -> None`
- `simulation.resume() -> None`
- `simulation.reset() -> None`
- `simulation.stop() -> None`
- `simulation.get_state() -> dict[str, Any]`

Property:

- `simulation.is_paused -> bool`

Important private methods:

- `simulation._validate_initial_state(robots, tasks) -> None`
- `simulation._run() -> None`
- `simulation._tick() -> None`
- `simulation._prune_old_tasks() -> None`
- `simulation._assign_pending_tasks() -> None`
- `simulation._begin_task(robot: Robot, task: Task) -> None`
- `simulation._advance_robots() -> None`
- `simulation._advance_replanning_robot(robot: Robot, occupied: set[tuple[int, int]]) -> None`
- `simulation._complete_yield(robot: Robot) -> None`
- `simulation._handle_blocked_robot(robot: Robot, next_cell: tuple[int, int]) -> None`
- `simulation._make_robot_yield(robot: Robot, blocker: Robot, pair_key: frozenset[str]) -> bool`
- `simulation._select_yielding_robot(robot: Robot, blocker: Robot) -> Robot`
- `simulation._yield_score(robot: Robot) -> int`
- `simulation._robot_is_in_active_conflict(robot_id: str) -> bool`
- `simulation._can_yield(robot: Robot) -> bool`
- `simulation._choose_yield_step(robot: Robot, blocker: Robot, occupied: set[tuple[int, int]]) -> tuple[int, int] | None`
- `simulation._claimed_cells(exclude_robot_id: str | None = None) -> set[tuple[int, int]]`
- `simulation._build_backtrack_path(robot: Robot) -> list[tuple[int, int]] | None`
- `simulation._attempt_resume_route(robot: Robot) -> bool`
- `simulation._attempt_replan_route(robot: Robot, occupied: set[tuple[int, int]], pair_key: frozenset[str] | None = None) -> bool`
- `simulation._assign_yield_path(robot: Robot, yield_path: list[tuple[int, int]]) -> None`
- `simulation._route_robot_to(robot: Robot, task: Task, destination: tuple[int, int]) -> None`
- `simulation._handle_arrival(robot: Robot) -> None`
- `simulation._release_conflict(robot: Robot) -> None`
- `simulation._clear_conflicts_for_robot(robot: Robot) -> None`
- `simulation._occupied_cells(exclude_robot_id: str | None = None) -> set[tuple[int, int]]`
- `simulation._robot_at(cell: tuple[int, int], exclude_robot_id: str | None = None) -> Robot | None`
- `simulation._task_priority(task_id: str | None) -> int`

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
- `simulation._blocked_replan_threshold_ticks`
- `simulation._replan_cooldown_ticks`
- `simulation._active_conflict_yielder`

`_active_conflict_yielder` maps a robot-pair key to the currently yielding
robot id:

    pair_key = frozenset({robot_id_a, robot_id_b})
    self._active_conflict_yielder[pair_key] = yielder_robot_id

Important behavior:

`start()` starts the background simulation thread.

`pause()` stops ticking but keeps state.

`resume()` continues ticking.

`reset()` restores robots and tasks to their initial state and clears traffic
conflict state.

`get_state()` returns a JSON-serializable snapshot.

`_validate_initial_state()` resolves task `pickup` and `dropoff` names and
raises `ValueError` for unknown locations.

`_begin_task()` routes to `warehouse.resolve(task.pickup)` and records
assignment timing.

`_handle_arrival()` routes to `warehouse.resolve(task.dropoff)` when arriving
at pickup and records completion or failure.

`_tick()` asks the task generator for new work, uses the scheduler to assign
pending tasks, advances robots, records metrics, and prunes old tasks.

`_prune_old_tasks()` deletes completed/failed tasks whose `completed_at` is
more than 100 ticks old. Metrics are unaffected because aggregates were
already recorded.

Pathfinding operates on coordinates only; name resolution happens at the call
sites.

The simulation reserves occupied cells during each tick so robots do not step
into the same cell.

---

## Traffic / Conflict Resolution Behavior (v0.3.1)

When a robot's next cell is occupied by another robot, the blocked robot
increments `blocked_ticks`.

After `blocked_replan_seconds` (default 0.9 s ≈ 3 ticks at 0.3 s) the
conflict becomes eligible for yielding.

For each blocking pair, only one robot may replan at a time. The selected
yielder is stored in `_active_conflict_yielder`.

Yielder selection uses `_yield_score()`; higher score means more willing to
yield:

- Idle robots (no task) score 10000 and yield first.
- `priority_pressure = priority * 20`. Lower task priority numbers are more
  urgent and yield less; larger numbers yield more.
- `blocked_pressure = blocked_ticks * 10`. Two blocked ticks can overcome one
  priority level.
- Ties fall back to blocked time, then lower robot id.

The non-yielding robot's route is frozen during the conflict.

The yielding robot receives a single local yield step from
`_choose_yield_step()`:

1. Prefer a neighboring cell that still allows reaching the current
   `route_goal` (validated with BFS from that neighbor).
2. Otherwise prefer a backtrack step through recent `travel_history`.
3. Otherwise choose any safe escape neighbor, biased away from the blocker.

A valid yield step must be in bounds, not a shelf, not occupied, and not
claimed by another robot's immediate next target (`_claimed_cells()`).

If the preferred yielder is stationary (no path) it can be forced to yield.
If the preferred yielder cannot act quickly enough, the blocked robot yields
instead after `threshold + 2` ticks. If the active yielder appears inactive
for `threshold * 3` ticks, the blocked robot takes over.

`_can_yield()` prevents a robot from participating in more than one active
conflict and enforces `replan_cooldown`.

`_attempt_resume_route()` resumes normal BFS routing after a yield maneuver
without waiting for replan cooldown. It avoids occupied and claimed cells and
rejects a first step into either.

`_advance_replanning_robot()` retries a different local yield step if the
current yield step stays blocked for 2+ ticks.

`_release_conflict()` clears the pair record when the yielder moves.
`_clear_conflicts_for_robot()` removes stale conflicts when a robot begins a
task, arrives, or fails.

This is a local deadlock-recovery mechanism. It is not reservation-based
multi-agent pathfinding and does not implement intersection control.

---

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

`WAREHOUSE_LAYOUT` and `WAREHOUSE_LOCATIONS` are generated together by
`_build_warehouse()`, so the grid and the named locations never drift apart.

`create_initial_tasks()` is a legacy compatibility helper; the default app
wiring uses dynamic generation instead of seeding those demo tasks.

`create_default_simulation()` wires in the baseline scheduler, task
generator, and metrics collector.

`create_app()` may start the simulation automatically.

Routes should remain thin. Business logic should stay in `simulation/`.

Robot ids must be clean strings: `"R1"`, `"R2"`, `"R3"`, `"R4"` (no trailing
spaces).

---

## JSON API

### `GET /api/state`

Returns:

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
          "id": "G00001",
          "name": "Pick order G00001",
          "pickup": "B-02",
          "dropoff": "PICK-1",
          "taskType": "PICK",
          "priority": 2,
          "createdAt": 4,
          "completedAt": null,
          "status": "Assigned",
          "assignedRobotId": "R1",
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
        "replanEvents": 0,
        "throughputPerTick": 0.02,
        "averageTaskWaitingTime": 4.0,
        "averageTaskCompletionTime": 19.0,
        "simulationTicks": 50,
        "simulationSeconds": 15.0,
        "robotDistanceTravelled": { "R1": 22 },
        "robotBusyTicks": { "R1": 22 },
        "robotBlockedTicks": { "R1": 0 },
        "robotReplanEvents": { "R1": 0 },
        "robotUtilization": { "R1": 0.44 }
      }
    }

Important JSON keys:

- `paused`
- `tick`
- `warehouse`
- `robots`
- `tasks`
- `metrics`

### Robot JSON keys

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

### Task JSON keys

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

### Warehouse JSON keys

- `width`
- `height`
- `layout`
- `obstacles`
- `locations`
- `racks`

### Metrics JSON keys

- `tasksGenerated`
- `tasksAssigned`
- `tasksCompleted`
- `tasksFailed`
- `blockedTimeTicks`
- `blockedTimeSeconds`
- `replanningCount`
- `deadlockResolutions`
- `replanEvents`
- `throughputPerTick`
- `averageTaskWaitingTime`
- `averageTaskCompletionTime`
- `simulationTicks`
- `simulationSeconds`
- `robotDistanceTravelled`
- `robotBusyTicks`
- `robotBlockedTicks`
- `robotReplanEvents`
- `robotUtilization`

`replanEvents` duplicates `replanningCount` for backward compatibility.

---

## Frontend JavaScript

### `static/simulation.js`

Important constants:

- `CELL_SIZE`
- `POLL_INTERVAL_MS`

Important DOM ids:

- `warehouse`
- `dashboard-grid`
- `task-list`
- `simulation-state`
- `pause-btn`
- `resume-btn`
- `reset-btn`

The `robot-list` section was removed from the HTML and JS in v0.3.1.

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
- `shortLabel(name)`
- `addCell(x, y, className, label)`
- `addMarker([x, y], text, tooltip)`
- `updateRobots(robots, tasks)`
- `updateTaskHighlights(state)`
- `highlightLocation(state, locationName, className)`
- `addTileClass(coord, className)`
- `updateSidePanel(state)`
- `createTaskRow(task, isHistory)`
- `createMetricCard(title, value, detail)`

Important behavior:

The frontend polls `/api/state` every 300 ms.

It rebuilds the static warehouse layer only when the warehouse JSON changes.

`addCell()` stores `dataset.x` and `dataset.y` on every tile so task
highlights can target cells.

`updateRobots()` keeps the robot's identity color and adds task-type ring
classes plus a `has-task` outline. Robot tooltips show the current task's
name, pickup, and dropoff.

`updateTaskHighlights()` highlights active task locations on the map:

- Phase `To pickup`: strong amber highlight on the pickup cell/access, faint
  green highlight on the dropoff.
- Phase `To dropoff`: strong green highlight on the dropoff cell/access.

Highlights are derived from state on every poll, so they clear automatically
when tasks complete.

`updateSidePanel()` renders:

1. A compact 4-column metrics dashboard.
2. An `Active Queue` section with compact task rows for `Pending` and
   `Assigned` tasks.
3. A `Recent History` section showing the 5 most recent completed/failed
   tasks, with totals taken from metrics.

The task list scrolls inside the sidebar (`#task-list`), so the page no
longer grows with the queue.

---

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

Robot classes:

- `.robot`
- `.robot.idle`
- `.robot.has-task`
- `.robot.task-putaway`
- `.robot.task-pick`
- `.robot.task-pack`
- `.robot.task-ship`

Task location highlight classes:

- `.tile.task-pickup-active`
- `.tile.task-dropoff-active`
- `.tile.task-pickup-faint`
- `.tile.task-dropoff-faint`

Map classes:

- `.rack-label`
- `.marker`
- `.map-column`
- `.legend`
- `.legend-item`
- `.swatch`

Sidebar / dashboard classes:

- `.panel`
- `.metric-card`
- `.metric-title`
- `.metric-value`
- `.metric-detail`
- `.card`
- `.card-title`
- `.row`
- `.label`
- `.value`

Task list classes:

- `.section-header`
- `.empty-msg`
- `.task-row` (with `.pending`, `.assigned`, `.completed`, `.failed`)
- `.task-badge` (with `.putaway`, `.pick`, `.pack`, `.ship`, `.legacy`)
- `.task-info`
- `.task-title`
- `.task-sub`

Important ids styled directly:

- `#warehouse`
- `#dashboard-grid` (4-column grid)
- `#task-list` (scrollable, `max-height` + `overflow-y`)
- `#simulation-state`

---

## Extension Points

These are intentionally not implemented yet:

- `CHARGING` → battery charging behavior
- `INTERSECTION` → formal intersection traffic control
- `MAIN_AISLE` → priority routing or speed changes
- `PACKING` → packing queue or processing delay
- `RECEIVING` → inbound task generation coupling
- `SHIPPING` → outbound task completion coupling
- `EMPTY` → dynamic obstacles or editor placement
- `BUFFER` → QC delay or put-away scheduling
- `PICK_STATION` → pick processing time or queueing
- `CONSOLIDATION` → order merge logic
- `STAGING` → carrier lane assignment
- `MAINTENANCE` → robot repair / downtime behavior

The v0.3.1 traffic layer is local single-yielder deadlock recovery. It is
not a replacement for future reservation-based pathfinding or intersection
control.

