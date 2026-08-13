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

## Changes From v0.3.0

v0.3.1 introduces local single-robot traffic/conflict resolution.

No breaking JSON API changes are introduced in v0.3.1.

`Robot` gains an internal `temporary_path` field and a `set_temporary_path()`
method. These are used for temporary yield/backtrack movement and are not
exposed in the robot JSON.

`Simulation` gains traffic/conflict-resolution state and methods.

`Simulation` constructor accepts optional traffic tuning arguments:
`blocked_replan_seconds` and `replan_cooldown_ticks`.

The simulation uses `_active_conflicts` instead of the older
`_active_conflict_yielder` mapping.

Metrics JSON includes `robotBlockedTicks`, `robotReplanEvents`, and
`replanEvents`.

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

`cell` is the physical cell the location represents, such as a shelf cell for
storage locations or the station cell for work stations.

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

- `warehouse._parse_layout(layout) -> list[list[CellType]]`
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
labels such as `"B"` instead of `"B-02"`.

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
- `robot.temporary_path: bool`

Property:

- `robot.current_target -> tuple[int, int] | None`

Public methods:

- `robot.set_path(path: list[tuple[int, int]]) -> None`
- `robot.set_temporary_path(path: list[tuple[int, int]]) -> None`
- `robot.advance() -> bool`
- `robot.to_dict() -> dict[str, Any]`

Important behavior:

`set_path()` expects a path excluding the robot's current cell.

`set_path()` clears `temporary_path`.

`set_temporary_path()` marks the current path as a temporary yield/backtrack
path.

`advance()` moves the robot one cell.

`advance()` returns `True` when the robot reaches the end of its path.

`temporary_path` is internal and is not exposed in the robot JSON.

`route_goal` is the current final destination for the robot's current task
phase.

`travel_history` is used for backtracking during yield maneuvers.

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

class TaskGenerator

Constructor:

    TaskGenerator(warehouse: Warehouse, start_tick: int = 2)

Public methods:

- `task_generator.step(tick: int) -> list[Task]`
- `task_generator.reset() -> None`

Important behavior:

Generates tasks during the simulation instead of seeding all work at startup.

Emits a light stream of `PUTAWAY`, `PICK`, `PACK`, and `SHIP` tasks using the
existing named locations.

Uses the warehouse layout to pick reasonable pickup and dropoff names.

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

`record_blocked()` increments aggregate blocked ticks and per-robot blocked
ticks.

`record_replan()` increments aggregate replan count and per-robot replan
events.

`record_deadlock_resolution()` increments the deadlock-resolution counter.

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
        blocked_replan_seconds: float = 2.0,
        replan_cooldown_ticks: int = 5,
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
- `simulation._assign_pending_tasks() -> None`
- `simulation._begin_task(robot: Robot, task: Task) -> None`
- `simulation._advance_robots() -> None`
- `simulation._move_robot(robot: Robot, occupied: set[tuple[int, int]]) -> bool`
- `simulation._advance_replanning_robot(robot: Robot, occupied: set[tuple[int, int]]) -> None`
- `simulation._handle_blocked_robot(robot: Robot, next_cell: tuple[int, int]) -> None`
- `simulation._select_yielding_robot(robot: Robot, blocker: Robot) -> Robot`
- `simulation._robot_is_blocker(robot_id: str) -> bool`
- `simulation._make_robot_yield(robot: Robot, blocker: Robot) -> bool`
- `simulation._force_yield(robot: Robot, blocker: Robot) -> bool`
- `simulation._register_conflict(yielder: Robot, blocker: Robot) -> frozenset[str]`
- `simulation._watchdog_conflicts() -> None`
- `simulation._try_assign_yield_path_from_active_conflict(robot: Robot) -> bool`
- `simulation._choose_and_assign_yield_step(robot: Robot, blocker: Robot) -> bool`
- `simulation._choose_backtrack_step(robot: Robot, safe_neighbors: list[tuple[int, int]], blocked: set[tuple[int, int]]) -> tuple[int, int] | None`
- `simulation._local_blocked_cells(robot: Robot) -> set[tuple[int, int]]`
- `simulation._neighbors(cell: tuple[int, int]) -> tuple[tuple[int, int], ...]`
- `simulation._clear_conflict(pair_key: frozenset[str], resume_yielder: bool = False) -> None`
- `simulation._clear_conflicts_where_yielder(robot: Robot) -> None`
- `simulation._release_blocker_conflicts(robot: Robot) -> None`
- `simulation._clear_conflicts_for_robot(robot: Robot) -> None`
- `simulation._complete_yield(robot: Robot) -> None`
- `simulation._attempt_resume_route(robot: Robot) -> bool`
- `simulation._route_robot_to(robot: Robot, task: Task, destination: tuple[int, int]) -> None`
- `simulation._handle_arrival(robot: Robot) -> None`
- `simulation._occupied_cells(exclude_robot_id: str | None = None) -> set[tuple[int, int]]`
- `simulation._claimed_cells(exclude_robot_id: str | None = None) -> set[tuple[int, int]]`
- `simulation._robot_at(cell: tuple[int, int], exclude_robot_id: str | None = None) -> Robot | None`

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
- `simulation._max_conflict_age_ticks`
- `simulation._active_conflicts`

`_active_conflicts` maps a robot-pair key to an active conflict record:

    pair_key = frozenset({robot_id_a, robot_id_b})

    self._active_conflicts[pair_key] = {
        "yielder": robot_id,
        "blocker": robot_id,
        "created_tick": tick,
        "last_tick": tick,
        "replan_counted": bool,
    }

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
pending tasks, runs traffic watchdog logic, advances robots, and records
metrics.

Pathfinding operates on coordinates only; name resolution happens at the call
sites.

The simulation reserves occupied cells during each tick so robots do not step
into the same cell.

Task assignment is unchanged by yielding. Yielding is local and temporary.

Normal task routing still uses BFS.

---

## Traffic / Conflict Resolution Behavior

v0.3.1 uses single-robot conflict resolution.

When a robot's next cell is occupied by another robot, the blocked robot
increments `blocked_ticks`.

After `blocked_replan_seconds` has been converted into ticks, the conflict
becomes eligible for yielding.

For a conflicting robot pair, the simulation chooses exactly one yielder.

Yielder selection rules:

1. If one robot has no task and the other has a task, prefer the idle robot.
2. Otherwise, prefer the robot that has been blocked longer.
3. If still tied, prefer the lower robot ID.

The non-yielding robot is frozen:

- its route is not replaced,
- it does not participate in replanning for that conflict,
- it continues as soon as its next cell is available.

Only the yielding robot may receive a temporary path.

The yielding robot evaluates local next moves.

A valid yield move must be:

- in bounds,
- not a shelf,
- not blocked,
- not occupied,
- not claimed by another robot's immediate next target,
- not an immediate recreation of the same conflict.

Yield-move preference:

1. Choose a neighboring cell that still allows reaching the current task
   goal.
2. If none exists, choose a backtrack step toward a previously visited cell.
3. If no backtrack step exists, choose any safe local escape neighbor.

Temporary yield paths do not trigger task arrival.

When the blocker robot moves and is no longer blocked, the conflict is
cleared.

When the yielding robot completes its temporary maneuver, it resumes normal
routing toward its current `route_goal`.

If a conflict remains active longer than `_max_conflict_age_ticks`, the
watchdog swaps the yielding robot.

This avoids the old failure mode where both robots replanned simultaneously
and recreated the same head-on conflict.

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

`create_initial_tasks()` is a legacy compatibility helper. The default app
wiring uses dynamic generation instead of seeding those demo tasks.

`create_default_simulation()` wires in the baseline scheduler, task
generator, and metrics collector.

`create_app()` may start the simulation automatically.

Routes should remain thin.

Business logic should stay in `simulation/`.

Robot ids should be clean strings such as `"R1"`, `"R2"`, `"R3"`, and
`"R4"` without trailing spaces.

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

`temporaryPath` is intentionally not exposed in the JSON API.

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

`replanEvents` duplicates `replanningCount` for backward compatibility with
existing dashboards or debugging views.

---

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

The frontend polls `/api/state`.

It rebuilds the static warehouse layer when the warehouse JSON changes.

Robots are updated without rebuilding the entire warehouse.

Tile rendering uses `warehouse.layout`.

`buildStaticLayer()` also renders rack letter labels from `warehouse.racks`.

Station markers are no longer added; zone naming lives in a static HTML
legend below the map.

`addMarker()` is retained but currently unused.

Task cards display `pickup` / `dropoff` as strings and also show task type,
status, and assignment details.

The sidebar includes a compact operational dashboard for queue depth,
throughput, average wait/completion time, blocked time, replanning activity,
and robot utilization.

No frontend change is required for v0.3.1 traffic/replanning behavior.

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

No CSS change is required for v0.3.1.

---

## Extension Points

These are intentionally not implemented yet:

- `CHARGING` → battery charging behavior
- `INTERSECTION` → formal traffic control or collision avoidance
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

The v0.3.1 traffic layer is a local deadlock-resolution mechanism, not a
replacement for future intersection control, priority routing, or
reservation-based multi-agent pathfinding.

### Traffic / Conflict Resolution (v0.3.1+)

`Simulation` constructor accepts optional traffic tuning arguments:

-   `blocked_replan_seconds: float = 0.9`
-   `replan_cooldown_ticks: int = 2`

Important private methods for traffic resolution:

-   `simulation._handle_blocked_robot(robot: Robot, next_cell: tuple[int, int]) -> None`
-   `simulation._select_yielding_robot(robot: Robot, blocker: Robot) -> Robot`
-   `simulation._yield_score(robot: Robot) -> int`
-   `simulation._make_robot_yield(robot: Robot, blocker: Robot, pair_key: frozenset[str]) -> bool`
-   `simulation._choose_yield_step(robot: Robot, blocker: Robot, occupied: set[tuple[int, int]]) -> tuple[int, int] | None`
-   `simulation._claimed_cells(exclude_robot_id: str | None = None) -> set[tuple[int, int]]`
-   `simulation._can_yield(robot: Robot) -> bool`
-   `simulation._robot_is_in_active_conflict(robot_id: str) -> bool`
-   `simulation._complete_yield(robot: Robot) -> None`
-   `simulation._attempt_resume_route(robot: Robot) -> bool`
-   `simulation._release_conflict(robot: Robot) -> None`
-   `simulation._clear_conflicts_for_robot(robot: Robot) -> None`

Important internal state for traffic resolution:

-   `simulation._active_conflict_yielder: dict[frozenset[str], str]`
-   `simulation._blocked_replan_threshold_ticks: int`
-   `simulation._replan_cooldown_ticks: int`

Traffic behavior:

-   When a robot is blocked by another robot, it increments `blocked_ticks`.
-   After `blocked_replan_seconds` (converted to ticks), the conflict becomes eligible for yielding.
-   For each blocking pair, only one robot may replan at a time.
-   The yielder is selected using `_yield_score()`:
    -   Idle robots yield first.
    -   Lower `task.priority` values are more urgent and yield less.
    -   Robots blocked longer yield more.
-   The non-yielding robot’s route is frozen during the conflict.
-   The yielding robot uses `_choose_yield_step()` to select a single safe local move:
    -   Prefer a neighbor that still allows reaching the current `route_goal`.
    -   Otherwise prefer backtracking through `travel_history`.
    -   Otherwise choose any safe escape neighbor away from the blocker.
-   Temporary yield paths do not trigger task arrival.
-   When the conflict clears, `_attempt_resume_route()` resumes normal BFS routing immediately without waiting for replan cooldown.
-   If the preferred yielder is stationary or cannot act, the simulation may force it to yield or fall back to the blocked robot to prevent long deadlocks.
-   `_active_conflict_yielder` tracks which robot is currently yielding for each pair.
-   `_clear_conflicts_for_robot()` removes stale conflicts when a robot begins a new task or arrives at a destination.

