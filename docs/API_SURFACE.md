# API Surface

This document lists the important names used by the warehouse simulator.
If code and documentation disagree, the code is the source of truth, but this
file should be updated immediately.

## Project State

- **Project Name:** warehouse_simulator
- **Current Version:** v0.4.0
- **Git Tag:** v0.4.0
- **Python Version:** Python 3.13+
- **Dependencies:** Flask, Optuna (optional, for optimization)
- **Run Command:** `python app.py`

## Where The Project Is Now

v0.4.0 preserves the v0.3.1 traffic/conflict-resolution system and adds
battery simulation, charging behavior, charging-related waiting, task
interruption/reassignment, congestion metrics, and basic robot failure/repair
behavior.

The 26×21 layout, racks A–H, named storage locations, receiving, buffer, pick
stations, consolidation, packing, staging, shipping, charging, and maintenance
areas remain unchanged.

The task model now includes logical load state and interruption/recovery
state. The robot model now includes battery, operational mode, idle time,
charger waiting time, interrupted-task memory, and repair state.

Runtime architecture is split into task generation, baseline cost-based
scheduling, pathfinding, robot motion, traffic resolution, battery/charging,
failure/repair, and metrics collection.

The major change from v0.3.1 is that route feasibility is no longer assumed
to remain valid after assignment. v0.3 conflict resolution can cause yielding,
backtracking, detours, and replanning, so v0.4 continuously re-evaluates
battery feasibility after route changes and during execution.

If a task becomes battery-infeasible, the robot interrupts the task, preserves
task/load state, seeks charging, and the interrupted task can later be resumed
by the original robot or reassigned to another robot.

## Breaking Changes / Changes From v0.3.1 (v0.4.0)

### Core Architecture

- Added `simulation/config.py` containing `BatteryConfig`, `ChargingConfig`,
  and `FailureConfig`.
- Added `simulation/charging.py` containing `ChargingStation`.
- `Simulation` constructor now accepts keyword-only v0.4 arguments:
  `battery_config`, `charging_config`, `failure_config`, and `seed`.
- `Simulation` now owns charging-station state, maintenance-cell scanning,
  failure RNG, dynamic resume-location tracking, and congestion snapshots.
- Added task interruption, recovery, and reassignment logic.
- Added battery drain from actual movement.
- Added loaded movement consuming more energy than empty movement.
- Added critical battery, opportunistic charging, and empty-battery recovery.
- Added robot failures, repair time, and maintenance relocation.
- Yield scoring now includes battery urgency.
- Added taskless routing helper `_route_robot_to_cell()` for charger and
  maintenance movement.

### Data Models

- `Robot` gained `RobotMode` and v0.4 battery/charging/failure fields.
- `Task` gained `LoadState`, `INTERRUPTED` status, interruption count,
  last-assigned robot, and resume-location fields.
- `Metrics` gained battery, charging, waiting-breakdown, interruption,
  failure, and congestion-related fields/methods.

### Frontend / CLI

- `benchmark.py` accepts v0.4 battery, charging, and failure parameters.
- `optimize_optuna.py` accepts fixed v0.4 parameters and optional
  `--search-v04` mode.
- Frontend supports `Interrupted` tasks, robot mode/battery tooltips, and
  v0.4 dashboard metrics.
- CSS adds styles for interrupted tasks and robot battery/charging/failure
  states.

### Important Code Default Note

The actual v0.3.1 code defaults are:

```python
blocked_replan_seconds = 0.7
replan_cooldown_ticks = 7
```

Older documentation may mention `0.9` and `2`. The code defaults are the
source of truth.

---

## Coordinate System

Coordinates are `(x, y)`.

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

---

## Python Modules

### `simulation/config.py` (NEW in v0.4.0)

Configuration dataclasses for v0.4 features.

#### `BatteryConfig`

```python
@dataclass(frozen=True)
class BatteryConfig
```

Fields:

- `capacity: float = 100.0`
- `empty_move_energy: float = 0.7`
- `loaded_move_energy: float = 1.0`
- `critical_battery: float = 20.0`
- `opportunistic_charge_threshold: float = 40.0`
- `idle_ticks_before_opportunistic_charge: int = 10`
- `safety_margin: float = 5.0`
- `empty_battery_recovery_ticks: int = 15`

Methods:

- `move_cost(loaded: bool) -> float`
- `is_critical(battery: float) -> bool`
- `is_opportunistic_candidate(battery: float) -> bool`

Important behavior:

- `empty_move_energy` is consumed per successful empty movement step.
- `loaded_move_energy` is consumed per successful loaded movement step.
- Battery consumption must come from actual movement, not elapsed time.
- `critical_battery` forces charging behavior.
- `opportunistic_charge_threshold` allows idle robots to charge after the
  idle threshold.
- `safety_margin` is added to estimated remaining task energy during
  feasibility checks.
- `empty_battery_recovery_ticks` is the minimum downtime when battery reaches
  zero.

#### `ChargingConfig`

```python
@dataclass(frozen=True)
class ChargingConfig
```

Fields:

- `capacity: int = 4`
- `charge_duration_ticks: int = 10`

Important behavior:

- `capacity` is logical station capacity.
- Physical `CHARGING` cells can further constrain simultaneous charging.
- If the map has fewer usable charging cells than `capacity`, effective
  physical charging may be lower.

#### `FailureConfig`

```python
@dataclass(frozen=True)
class FailureConfig
```

Fields:

- `enabled: bool = False`
- `mtbf_ticks: float = 0.0`
- `mttr_ticks: int = 25`
- `seed: int | None = None`
- `relocate_to_maintenance: bool = True`

Important behavior:

- `mtbf_ticks <= 0` disables random failures.
- `mttr_ticks` is repair duration.
- If `relocate_to_maintenance` is true, failed/dead robots are moved/towed to
  a `MAINTENANCE` cell.
- If false, failed robots remain where they failed and become obstacles.

---

### `simulation/charging.py` (NEW in v0.4.0)

Finite-capacity charging resource model.

#### `ChargingStation`

```python
@dataclass
class ChargingStation
```

Fields:

- `capacity: int`
- `charge_duration_ticks: int`
- `active: dict[str, int]`
  - robot_id → remaining charging ticks.
- `active_cells: dict[str, tuple[int, int]]`
  - robot_id → charging cell occupied by that robot.
- `reserved_cells: dict[str, tuple[int, int]]`
  - robot_id → charging cell reserved while robot is moving to charge.
- `waiting: set[str]`
  - robot ids waiting for charger capacity.

Properties:

- `occupancy -> int`
- `has_capacity -> bool`

Methods:

- `is_charging(robot_id: str) -> bool`
- `is_waiting(robot_id: str) -> bool`
- `add_waiting(robot_id: str) -> None`
- `remove_waiting(robot_id: str) -> None`
- `reserve(robot_id: str, cell: tuple[int, int]) -> bool`
- `release_reservation(robot_id: str) -> None`
- `begin_charging(robot_id: str, cell: tuple[int, int]) -> bool`
- `release(robot_id: str) -> None`
- `is_cell_active(cell: tuple[int, int]) -> bool`
- `is_cell_reserved(cell: tuple[int, int]) -> bool`
- `tick() -> list[str]`

Important behavior:

- Active robots occupy capacity.
- Waiting robots do not occupy capacity.
- Reserved robots hold capacity while traveling to a charging cell.
- `has_capacity` accounts for active plus reserved robots.
- `begin_charging()` converts a reservation into active charging, or takes an
  unreserved slot if capacity allows.
- `tick()` advances charging timers and returns robot ids that finished.

---

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

Values should be the same as member names:

```python
CellType.EMPTY.value == "EMPTY"
CellType.SHELF.value == "SHELF"
CellType.CHARGING.value == "CHARGING"
CellType.MAINTENANCE.value == "MAINTENANCE"
```

Important:

- Enum values and layout symbol keys must not contain trailing spaces.
- Correct: `"EMPTY"`, not `"EMPTY "`.
- Correct: `"."`, not `". "`.

#### `LAYOUT_SYMBOLS`

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

- `cell` is the physical cell the location represents.
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

- `warehouse._parse_layout(layout) -> list[list[CellType]]`
- `warehouse._validate() -> None`
- `warehouse._rack_anchors() -> dict[str, list[int]]`

Important behavior:

- `is_blocked()` returns `True` for out-of-bounds cells.
- `is_blocked()` returns `True` for `SHELF` cells.
- All other cell types are passable.
- `resolve()` returns the location's access coordinate and raises `KeyError`
  for unknown names.
- `_validate()` checks that every location's cell and access are in bounds and
  that access is not blocked.
- `_rack_anchors()` returns one anchor cell per rack letter.
- v0.4 dynamically adds `RESUME-*` locations to `warehouse.locations` during
  simulation runtime for interrupted loaded tasks.
- `Simulation.get_state()` should strip dynamic `RESUME-*` locations from the
  serialized warehouse payload to avoid unnecessary frontend rebuilds.

---

### `simulation/robot.py` (UPDATED in v0.4.0)

#### `RobotStatus`

```python
class RobotStatus(str, Enum)
```

Members:

- `IDLE = "Idle"`
- `MOVING = "Moving"`

#### `RobotMode` (NEW)

```python
class RobotMode(str, Enum)
```

Members:

- `IDLE`
- `MOVING`
- `TO_CHARGER`
- `WAITING_FOR_CHARGER`
- `CHARGING`
- `FAILED`
- `REPAIRING`

Important behavior:

- `RobotStatus` remains backward compatible with v0.3 UI consumers.
- `RobotMode` carries richer v0.4 operational state.
- A robot may have `status == Idle` while `mode == Charging` or
  `mode == Waiting for charger`.

#### `Robot`

```python
@dataclass
class Robot
```

Existing fields:

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

New v0.4 fields:

- `robot.battery: float`
- `robot.mode: RobotMode`
- `robot.idle_ticks: int`
- `robot.charger_wait_ticks: int`
- `robot.interrupted_task_id: str | None`
- `robot.charge_target: tuple[int, int] | None`
- `robot.charge_start_battery: float | None`
- `robot.repair_remaining_ticks: int`

Property:

- `robot.current_target -> tuple[int, int] | None`

Public methods:

- `robot.set_path(path: list[tuple[int, int]]) -> None`
- `robot.set_temporary_path(path: list[tuple[int, int]]) -> None`
- `robot.advance() -> bool`
- `robot.to_dict() -> dict[str, Any]`

Important behavior:

- `set_path()` expects a path excluding the robot's current cell.
- `advance()` moves the robot one cell.
- `advance()` returns `True` when the robot reaches the end of its path.
- `route_goal` is the current final destination for the robot's current task
  phase or taskless movement target.
- `travel_history` stores previously visited cells and is used for
  backtracking during yield maneuvers.
- `battery` must never become negative.
- `idle_ticks` is used for opportunistic charging.
- `charger_wait_ticks` counts waiting for charger capacity, not active
  charging time.
- `interrupted_task_id` allows a robot to attempt to reclaim its own
  interrupted task after charging/repair if the task is still unassigned.

---

### `simulation/task.py` (UPDATED in v0.4.0)

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
- `INTERRUPTED = "Interrupted"` (NEW)

#### `TaskPhase`

```python
class TaskPhase(str, Enum)
```

Members:

- `TO_PICKUP = "To pickup"`
- `TO_DROPOFF = "To dropoff"`
- `DONE = "Done"`

#### `LoadState` (NEW)

```python
class LoadState(str, Enum)
```

Members:

- `ON_SHELF = "On shelf"`
- `CARRIED = "Carried"`
- `STAGED = "Staged"`
- `DELIVERED = "Delivered"`

Important behavior:

- `LoadState` is a logical cargo state, not full physical pallet handling.
- If a loaded task is interrupted, the load remains associated with the task
  and is logically staged at a resume location.

#### `Task`

```python
@dataclass
class Task
```

Existing fields:

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

New v0.4 fields:

- `task.load_state: LoadState`
- `task.interruption_count: int`
- `task.last_assigned_robot_id: str | None`
- `task.resume_location_name: str | None`

Public methods:

- `task.to_dict() -> dict[str, Any]`

Important behavior:

- `pickup` and `dropoff` are location names, resolved to coordinates via
  `warehouse.resolve()`.
- If a loaded task is interrupted, `pickup` may be rewritten to a temporary
  `RESUME-*` location name.
- `INTERRUPTED` tasks remain claimable by another robot.
- `interruption_count` supports reassignment metrics.
- `last_assigned_robot_id` supports reassignment detection.

---

### `simulation/task_generator.py`

#### `TaskGenerator`

```python
@dataclass
class TaskGenerator
```

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
- `_priority_for(task_type: TaskType) -> int`
- `_interval_for(task_type: TaskType) -> int`

Important behavior:

- Generates tasks during the simulation instead of seeding all work at
  startup.
- Emits a light stream of `PUTAWAY`, `PICK`, `PACK`, and `SHIP` tasks using
  existing named locations.
- Priority mapping, lower number = higher priority:
  - `SHIP` = 0
  - `PACK` = 1
  - `PICK` = 2
  - `PUTAWAY` = 3
- If `seed` is an int, random location selection is reproducible.
- If `seed` is None, deterministic round-robin behavior is preserved.
- Reset re-seeds with the same seed.

---

### `simulation/scheduler.py` (UPDATED in v0.4.0)

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

#### `Scheduler`

```python
class Scheduler(Protocol)
```

Method:

- `select_assignments(pending_tasks, robots, warehouse, blocked_cells=None) -> list[Assignment]`

#### `CostBasedScheduler`

```python
class CostBasedScheduler
```

Public methods:

- `select_assignments(pending_tasks, robots, warehouse, blocked_cells=None) -> list[Assignment]`

Important behavior:

- Centralized baseline scheduler.
- Chooses the idle robot with the shortest feasible path to each pending task
  pickup.
- v0.4 adds a backward-compatible guard: robots whose `mode` is not `Idle`
  should not be considered available, even if `status == Idle`.
- This prevents charging, waiting-for-charger, failed, or repairing robots
  from being assigned tasks if a caller passes all robots directly.

---

### `simulation/metrics.py` (UPDATED in v0.4.0)

#### `Metrics`

```python
@dataclass
class Metrics
```

Existing v0.3 fields:

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

New v0.4 fields:

- `metrics.battery_capacity: float`
- `metrics.battery_sum: float`
- `metrics.battery_samples: int`
- `metrics.charging_events: int`
- `metrics.total_charging_ticks: int`
- `metrics.charger_wait_ticks: int`
- `metrics.charger_wait_events: int`
- `metrics.traffic_wait_ticks: int`
- `metrics.station_wait_ticks: int`
- `metrics.battery_task_interruptions: int`
- `metrics.failure_task_interruptions: int`
- `metrics.task_reassignments: int`
- `metrics.failed_robot_events: int`
- `metrics.failure_downtime_ticks: int`

Existing methods:

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

New v0.4 methods:

- `metrics.record_battery_sample(robot: Robot) -> None`
- `metrics.record_charging_start() -> None`
- `metrics.record_charging_tick() -> None`
- `metrics.record_charger_wait_start() -> None`
- `metrics.record_charger_wait_tick() -> None`
- `metrics.record_battery_task_interruption() -> None`
- `metrics.record_failure_task_interruption() -> None`
- `metrics.record_task_reassignment() -> None`
- `metrics.record_failed_robot_event() -> None`
- `metrics.record_failure_downtime_tick() -> None`

Important behavior:

- Existing v0.3 metric keys remain unchanged.
- Blocked time is also counted as traffic waiting.
- Active charging time is not waiting time.
- Waiting for a free charger slot is charger waiting.
- Battery samples are used to compute average battery.
- Charger waiting events are used to compute average charger wait.

---

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

- `[]` — already at the goal.
- `[...]` — path cells after `start`.
- `None` — no path found.

Important behavior:

- Uses BFS.
- Avoids blocked cells.
- Treats all non-shelf cells as passable.
- May optionally avoid additional occupied cells supplied by the caller.
- The goal is removed from the blocked set before BFS.
- v0.4 battery feasibility may use this helper with failed-robot cells or
  occupied cells depending on the call site.

---

### `simulation/simulation.py` (UPDATED in v0.4.0)

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
    blocked_replan_seconds: float = 0.7,
    replan_cooldown_ticks: int = 7,
    *,
    battery_config: BatteryConfig | None = None,
    charging_config: ChargingConfig | None = None,
    failure_config: FailureConfig | None = None,
    seed: int | None = None,
)
```

Public methods:

- `simulation.start() -> None`
- `simulation.pause() -> None`
- `simulation.resume() -> None`
- `simulation.reset() -> None`
- `simulation.stop() -> None`
- `simulation.get_state() -> dict[str, Any]`

Property:

- `simulation.is_paused -> bool`

Important internal state:

Existing:

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

New v0.4:

- `simulation._battery_cfg`
- `simulation._charging_cfg`
- `simulation._failure_cfg`
- `simulation._charging_station`
- `simulation._charging_cells`
- `simulation._maintenance_cells`
- `simulation._failure_seed`
- `simulation._failure_rng`
- `simulation._dynamic_location_names`

Existing important private methods:

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
- `simulation._attempt_resume_route(robot: Robot) -> bool`
- `simulation._route_robot_to(robot: Robot, task: Task, destination: tuple[int, int]) -> None`
- `simulation._handle_arrival(robot: Robot) -> None`
- `simulation._release_conflict(robot: Robot) -> None`
- `simulation._clear_conflicts_for_robot(robot: Robot) -> None`
- `simulation._occupied_cells(exclude_robot_id: str | None = None) -> set[tuple[int, int]]`
- `simulation._robot_at(cell: tuple[int, int], exclude_robot_id: str | None = None) -> Robot | None`
- `simulation._task_priority(task_id: str | None) -> int`

New v0.4 private methods:

Lifecycle / safety:

- `simulation._safe_metric(method_name: str, *args: Any) -> None`
- `simulation._congestion_snapshot() -> dict[str, Any]`

Cell scanning / relocation:

- `simulation._scan_cells(cell_type: CellType) -> list[tuple[int, int]]`
- `simulation._nearest_passable_cell(robot: Robot, forbidden_cell_types: set[CellType]) -> tuple[int, int] | None`
- `simulation._relocate_robot_to_maintenance(robot: Robot) -> None`
- `simulation._relocate_waiting_robot_off_charger(robot: Robot) -> None`
- `simulation._try_exit_maintenance(robot: Robot) -> None`

Battery:

- `simulation._robot_is_loaded(robot: Robot) -> bool`
- `simulation._consume_move_energy(robot: Robot) -> None`
- `simulation._failed_robot_cells(exclude_robot_id: str | None = None) -> set[tuple[int, int]]`
- `simulation._path_distance(start: tuple[int, int], goal: tuple[int, int], blocked_cells: set[tuple[int, int]] | None = None) -> int | None`
- `simulation._remaining_task_energy(robot: Robot, task: Task) -> float | None`
- `simulation._battery_feasible_for_new_task(robot: Robot, task: Task) -> bool`
- `simulation._update_battery_checks() -> None`
- `simulation._check_battery_for_active_task(robot: Robot) -> None`
- `simulation._handle_battery_depleted(robot: Robot) -> None`

Task interruption / recovery:

- `simulation._add_resume_location(task: Task, cell: tuple[int, int]) -> str`
- `simulation._interrupt_current_task(robot: Robot, reason: str) -> None`
- `simulation._try_reclaim_interrupted_task(robot: Robot) -> None`

Charging:

- `simulation._enter_charging(robot: Robot, reason: str) -> None`
- `simulation._enter_waiting_without_reservation(robot: Robot) -> None`
- `simulation._choose_free_charging_cell(robot: Robot) -> tuple[int, int] | None`
- `simulation._handle_charging_arrival(robot: Robot) -> None`
- `simulation._update_charging_station() -> None`
- `simulation._update_charger_waiting() -> None`
- `simulation._try_dispatch_waiting_robot(robot: Robot) -> bool`
- `simulation._update_idle_and_opportunistic_charging() -> None`

Failure / repair:

- `simulation._update_failures_and_repairs() -> None`
- `simulation._fail_robot(robot: Robot) -> None`
- `simulation._update_robot_repairs() -> None`

Taskless routing:

- `simulation._route_robot_to_cell(robot: Robot, destination: tuple[int, int]) -> bool`

Important behavior:

- `start()` starts the background simulation thread.
- `pause()` stops ticking but keeps state.
- `resume()` continues ticking.
- `reset()` restores robots and tasks to their initial state, clears traffic
  conflict state, clears dynamic resume locations, resets charging station
  state, resets failure RNG, and restores robot batteries/modes.
- `get_state()` returns a JSON-serializable snapshot.
- `get_state()` should strip dynamic `RESUME-*` locations from the warehouse
  payload.
- `_validate_initial_state()` resolves task pickup/dropoff names and raises
  `ValueError` for unknown or blocked locations.
- `_begin_task()` routes to `warehouse.resolve(task.pickup)` and records
  assignment timing.
- `_handle_arrival()` routes to `warehouse.resolve(task.dropoff)` when
  arriving at pickup and records completion or failure.
- `_tick()` runs failures/repairs, charging station progression, task
  generation, assignment, battery checks, opportunistic charging, robot
  movement, metrics, and pruning.
- `_prune_old_tasks()` deletes completed/failed tasks whose `completed_at` is
  more than 100 ticks old. Interrupted tasks are not pruned.

---

## Traffic / Conflict Resolution Behavior (v0.3.1 preserved)

- When a robot's next cell is occupied by another robot, the blocked robot
  increments `blocked_ticks`.
- After `blocked_replan_seconds` the conflict becomes eligible for yielding.
- For each blocking pair, only one robot may replan at a time.
- The selected yielder is stored in `_active_conflict_yielder`.
- The non-yielding robot's route is frozen during the conflict.
- The yielding robot receives a local yield step from `_choose_yield_step()`.
- Yield step preference:
  1. A neighboring cell that still allows reaching the current `route_goal`.
  2. A backtrack step through recent `travel_history`.
  3. Any safe escape neighbor, biased away from the blocker.
- A valid yield step must be in bounds, not a shelf, not occupied, and not
  claimed by another robot's immediate next target.
- If the preferred yielder is stationary it can be forced to yield.
- If the preferred yielder cannot act quickly enough, the blocked robot yields
  instead.
- If the active yielder appears inactive for too long, the blocked robot takes
  over.
- `_can_yield()` prevents a robot from participating in more than one active
  conflict and enforces `replan_cooldown`.
- `_attempt_resume_route()` resumes normal BFS routing after a yield maneuver.
- `_advance_replanning_robot()` retries a different local yield step if the
  current yield step stays blocked for 2+ ticks.
- `_release_conflict()` clears the pair record when the yielder moves.
- `_clear_conflicts_for_robot()` removes stale conflicts when a robot begins a
  task, arrives, interrupts, fails, or starts charging.
- This is a local deadlock-recovery mechanism. It is not reservation-based
  multi-agent pathfinding and does not implement intersection control.

### v0.4 Yield Score Additions

- `_yield_score()` still uses idle status, task priority, and blocked time.
- Battery urgency reduces willingness to yield.
- Critical battery robots are strongly protected from unnecessary yielding.
- Failed, repairing, and actively charging robots cannot yield.
- Battery is one factor, not the only factor.

---

## Battery / Charging / Failure Behavior (v0.4.0)

### Battery Simulation

- Every robot has a battery value.
- Battery decreases only from actual successful movement.
- Loaded movement consumes more energy than empty movement.
- Battery cannot become negative.
- Battery feasibility includes a safety margin.
- Initial route estimates are not guaranteed to remain valid.

### Battery-Aware Routing

- When a task is assigned, the simulation estimates whether the route is
  battery-feasible.
- During execution, the simulation estimates energy required to complete the
  current remaining route.
- Battery feasibility is re-evaluated after:
  - task assignment,
  - arrival at pickup,
  - successful movement,
  - route resumption,
  - yield-step assignment,
  - replanning or detours.
- If the remaining task becomes infeasible, the robot interrupts the task and
  seeks charging.
- The robot must not blindly continue until battery reaches zero.

### Charging Decisions

Critical battery:

- If battery <= critical threshold, the robot seeks charging.
- If active task cannot be safely finished, the task is interrupted.
- Critical charging has priority over opportunistic charging.

Insufficient for task:

- If remaining battery < estimated remaining task energy + safety margin, the
  task is interrupted.
- Task state is preserved.
- The robot goes to charging.
- After charging, the robot may reclaim the task if it is still unassigned.
- Another robot may claim the interrupted task before then.

Opportunistic charging:

- Idle robots may charge if:
  - they have no task,
  - they have been idle for `idle_ticks_before_opportunistic_charge`,
  - battery is below `opportunistic_charge_threshold`,
  - charger capacity is available,
  - a usable charging cell is available.
- Idle robots do not charge immediately.

### Charging Station Behavior

- Charging station has finite logical capacity.
- Default capacity is 4 robots.
- Charging duration is configurable.
- Active charging robots occupy slots.
- Reserved robots occupy slots while traveling to charge.
- Waiting robots do not occupy slots.
- Waiting robots should not stand on charging cells.
- If a waiting robot is on a charging cell and cannot charge, it is relocated
  off the charging cell.
- When capacity opens, waiting robots are dispatched deterministically.

### Task Interruption / Reassignment

Task interruption reasons:

- `critical_battery`
- `insufficient_for_task`
- `no_feasible_route`
- `empty_battery`
- `failure`

Interrupt behavior:

- The task is preserved.
- Task progress/state is preserved.
- The robot is removed from the task.
- The task becomes `Interrupted`.
- The task becomes claimable by another robot.
- The original robot remembers the interrupted task and may reclaim it after
  charging/repair if it is still unassigned.
- Normal traffic conflicts do not automatically interrupt tasks.

Load behavior:

- If interrupted before pickup, load remains `On shelf`.
- If interrupted while carrying, load becomes `Staged` at a logical resume
  location.
- If another robot claims the resumed task, it routes to the resume location,
  then to dropoff.
- This is operational/logical recovery, not detailed physical pallet handling.

### Empty Battery Behavior

- If battery reaches zero:
  - active task is interrupted,
  - robot becomes failed/down,
  - robot is relocated to maintenance if enabled,
  - robot remains down for at least `empty_battery_recovery_ticks`,
  - after recovery, battery is restored.

### Failure / Repair Behavior

- Random failures are optional and controlled by `FailureConfig.enabled`.
- `mtbf_ticks` controls average ticks between failures.
- `mttr_ticks` controls repair duration.
- Failed robots stop moving and stop executing tasks.
- Failed robots cannot yield.
- Failed robots remain occupied cells unless relocated.
- If `relocate_to_maintenance` is true, failed/dead robots are moved/towed to
  a `MAINTENANCE` cell.
- After repair, robots return to service.
- After repair, robots may reclaim their interrupted task if still available.
- If no task is reclaimed and the robot is on a maintenance cell, it tries to
  move out of maintenance.

---

## Flask Layer

### `app.py`

Important functions:

- `create_initial_warehouse() -> Warehouse`
- `create_initial_robots() -> list[Robot]`
- `create_initial_tasks(warehouse: Warehouse) -> list[Task]`
- `create_default_simulation(...) -> Simulation`
- `create_app(simulation: Simulation | None = None, start_simulation: bool = True) -> Flask`

v0.4 constructor wiring:

```python
create_default_simulation(
    battery_config: BatteryConfig | None = None,
    charging_config: ChargingConfig | None = None,
    failure_config: FailureConfig | None = None,
    seed: int | None = 731,
)
```

Routes:

- `GET /`
- `GET /api/state`
- `POST /api/pause`
- `POST /api/resume`
- `POST /api/reset`

Important behavior:

- Routes remain thin.
- Business logic stays in `simulation/`.
- Robot ids should be clean strings: `"R1"`, `"R2"`, etc.
- Robot colors should be clean strings.
- `create_initial_tasks()` is a legacy compatibility helper.
- Default app wiring uses dynamic task generation.

---

## CLI Layer

### `benchmark.py`

Purpose:

- Runs a headless synchronous benchmark.
- Does not start Flask.
- Does not poll.
- Directly calls `sim._tick()` under the simulation lock.

Existing arguments:

- `--robots`
- `--block-replan`
- `--cooldown`
- `--target`
- `--seed`

New v0.4 arguments:

- `--max-ticks`
- `--battery-capacity`
- `--empty-move-energy`
- `--loaded-move-energy`
- `--critical-battery`
- `--opportunistic-charge-threshold`
- `--idle-opportunistic-ticks`
- `--battery-safety-margin`
- `--charger-capacity`
- `--charge-duration-ticks`
- `--failure-enabled`
- `--mtbf-ticks`
- `--mttr-ticks`

Important behavior:

- Preserves existing benchmark output.
- Adds v0.4 battery/charging/failure metrics output.
- Uses the same `Simulation` object as the Flask app.

Example:

```bash
python benchmark.py \
  --robots 8 \
  --seed 42 \
  --target 200 \
  --battery-capacity 100 \
  --empty-move-energy 0.7 \
  --loaded-move-energy 1.0 \
  --critical-battery 20 \
  --opportunistic-charge-threshold 40 \
  --idle-opportunistic-ticks 10 \
  --battery-safety-margin 5 \
  --charger-capacity 4 \
  --charge-duration-ticks 10
```

Example with failures:

```bash
python benchmark.py \
  --robots 8 \
  --seed 42 \
  --target 200 \
  --failure-enabled \
  --mtbf-ticks 1500 \
  --mttr-ticks 25
```

### `optimize_optuna.py`

Purpose:

- Uses Optuna to optimize simulation parameters.
- Runs headless simulations inside each trial.

Existing search parameters:

- `num_robots`
- `blocked_replan_seconds`
- `replan_cooldown_ticks`

Existing arguments:

- `--trials`
- `--target`
- `--max-ticks`
- `--base-seed`
- `--objective`
- `--fixed-robots`
- `--db`

New v0.4 arguments:

- `--search-v04`
- `--battery-capacity`
- `--empty-move-energy`
- `--loaded-move-energy`
- `--critical-battery`
- `--opportunistic-charge-threshold`
- `--idle-opportunistic-ticks`
- `--battery-safety-margin`
- `--charger-capacity`
- `--charge-duration-ticks`
- `--failure-enabled`
- `--mtbf-ticks`
- `--mttr-ticks`

Important behavior:

- Without `--search-v04`, optimization behavior remains v0.3-style but runs
  with v0.4 battery/charging defaults.
- With `--search-v04`, selected battery/charging parameters are included in
  the search space.
- v0.4 metrics are logged as Optuna user attributes.
- Study name includes a v0.4 suffix when `--search-v04` is used.

---

## JSON API

### `GET /api/state`

Returns:

```json
{
  "paused": false,
  "tick": 150,
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
      "x": 5,
      "y": 7,
      "color": "#ef4444",
      "status": "Moving",
      "mode": "To charger",
      "currentTaskId": null,
      "currentTarget": [10, 7],
      "blockedTicks": 0,
      "replanning": false,
      "yieldingTo": null,
      "replanCooldown": 0,
      "battery": 18.5,
      "idleTicks": 0,
      "chargerWaitTicks": 0,
      "interruptedTaskId": "G00042",
      "chargeTarget": [10, 7],
      "chargeStartBattery": null,
      "repairRemainingTicks": 0
    }
  ],
  "tasks": [
    {
      "id": "G00042",
      "name": "Pick order G00042",
      "pickup": "RESUME-G00042",
      "dropoff": "PICK-1",
      "taskType": "PICK",
      "priority": 2,
      "createdAt": 100,
      "completedAt": null,
      "status": "Interrupted",
      "assignedRobotId": null,
      "phase": "To pickup",
      "loadState": "Staged",
      "interruptionCount": 1,
      "lastAssignedRobotId": "R1",
      "resumeLocationName": "RESUME-G00042"
    }
  ],
  "metrics": {
    "tasksGenerated": 50,
    "tasksAssigned": 45,
    "tasksCompleted": 40,
    "tasksFailed": 0,
    "blockedTimeTicks": 12,
    "blockedTimeSeconds": 3.6,
    "replanningCount": 2,
    "deadlockResolutions": 2,
    "replanEvents": 2,
    "throughputPerTick": 0.26,
    "averageTaskWaitingTime": 4.0,
    "averageTaskCompletionTime": 19.0,
    "simulationTicks": 150,
    "simulationSeconds": 45.0,
    "robotDistanceTravelled": { "R1": 120 },
    "robotBusyTicks": { "R1": 110 },
    "robotBlockedTicks": { "R1": 12 },
    "robotReplanEvents": { "R1": 2 },
    "robotUtilization": { "R1": 0.73 },
    "averageBattery": 65.4,
    "averageBatteryPercent": 65.4,
    "chargingEvents": 5,
    "totalChargingTicks": 50,
    "totalChargingSeconds": 15.0,
    "chargerWaitTicks": 10,
    "chargerWaitSeconds": 3.0,
    "chargerWaitEvents": 2,
    "averageChargerWaitTicks": 5.0,
    "averageChargerWaitSeconds": 1.5,
    "trafficWaitTicks": 12,
    "trafficWaitSeconds": 3.6,
    "stationWaitTicks": 0,
    "stationWaitSeconds": 0.0,
    "totalWaitTicks": 22,
    "totalWaitSeconds": 6.6,
    "batteryTaskInterruptions": 1,
    "failureTaskInterruptions": 0,
    "taskReassignments": 0,
    "failedRobotEvents": 0,
    "failureDowntimeTicks": 0,
    "failureDowntimeSeconds": 0.0,
    "congestion": {
      "blockedRobots": 1,
      "waitingForChargerRobots": 0,
      "chargingRobots": 2,
      "toChargerRobots": 1,
      "failedRobots": 0,
      "replanningRobots": 0,
      "activeConflicts": 1,
      "chargerOccupancy": 2,
      "chargerWaiting": 0,
      "averageBlockedTicks": 0.1,
      "robotsByRow": { "row-07": 3, "row-08": 1 }
    }
  }
}
```

Important top-level keys:

- `paused`
- `tick`
- `warehouse`
- `robots`
- `tasks`
- `metrics`

### Robot JSON keys

Existing:

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

New v0.4:

- `battery`
- `mode`
- `idleTicks`
- `chargerWaitTicks`
- `interruptedTaskId`
- `chargeTarget`
- `chargeStartBattery`
- `repairRemainingTicks`

### Task JSON keys

Existing:

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

New v0.4:

- `loadState`
- `interruptionCount`
- `lastAssignedRobotId`
- `resumeLocationName`

Important:

- `status` can now be `"Interrupted"`.

### Warehouse JSON keys

- `width`
- `height`
- `layout`
- `obstacles`
- `locations`
- `racks`

Important:

- Dynamic `RESUME-*` locations used internally for task recovery should not
  appear in the serialized warehouse payload.

### Metrics JSON keys

Existing:

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

New v0.4:

- `averageBattery`
- `averageBatteryPercent`
- `chargingEvents`
- `totalChargingTicks`
- `totalChargingSeconds`
- `chargerWaitTicks`
- `chargerWaitSeconds`
- `chargerWaitEvents`
- `averageChargerWaitTicks`
- `averageChargerWaitSeconds`
- `trafficWaitTicks`
- `trafficWaitSeconds`
- `stationWaitTicks`
- `stationWaitSeconds`
- `totalWaitTicks`
- `totalWaitSeconds`
- `batteryTaskInterruptions`
- `failureTaskInterruptions`
- `taskReassignments`
- `failedRobotEvents`
- `failureDowntimeTicks`
- `failureDowntimeSeconds`
- `congestion`

`replanEvents` duplicates `replanningCount` for backward compatibility.

### Congestion JSON keys

Inside `metrics.congestion`:

- `blockedRobots`
- `waitingForChargerRobots`
- `chargingRobots`
- `toChargerRobots`
- `failedRobots`
- `replanningRobots`
- `activeConflicts`
- `chargerOccupancy`
- `chargerWaiting`
- `averageBlockedTicks`
- `robotsByRow`

Important behavior:

- Congestion should emerge from robot interactions.
- It is measured, not artificially imposed.

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

Important state variables:

- `robotElements`
- `previousWarehouseKey`
- `updateInProgress`

Important functions:

Existing / core:

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

New v0.4 helpers:

- `safeString(value)`
- `toNumber(value, fallback)`
- `staticWarehouseKey(warehouse)`

Important behavior:

- The frontend polls `/api/state` every 300 ms.
- It rebuilds the static warehouse layer only when static warehouse structure
  changes.
- `staticWarehouseKey()` should ignore `warehouse.locations` so dynamic
  `RESUME-*` locations do not force map rebuilds.
- `addCell()` stores `dataset.x` and `dataset.y` on every tile.
- `updateRobots()` keeps robot identity color and adds task-type ring classes.
- v0.4 robot rendering adds mode/battery classes:
  - `.low-battery`
  - `.to-charger`
  - `.waiting-for-charger`
  - `.charging`
  - `.failed`
- Robot tooltips include battery and mode information.
- `updateTaskHighlights()` highlights active task locations.
- Interrupted tasks may be faintly highlighted to show preserved work.
- `updateSidePanel()` renders:
  - metrics dashboard,
  - Active Queue,
  - Recent History.
- Active Queue includes `Pending`, `Assigned`, and `Interrupted` tasks.
- Recent History includes completed/failed tasks only.
- Event listeners must use clean strings:
  - `"click"`, not `"click "`
  - `"/api/pause"`, not `"/api/pause "`

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

Existing:

- `.robot`
- `.robot.idle`
- `.robot.has-task`
- `.robot.task-putaway`
- `.robot.task-pick`
- `.robot.task-pack`
- `.robot.task-ship`

New v0.4:

- `.robot.low-battery`
- `.robot.to-charger`
- `.robot.waiting-for-charger`
- `.robot.charging`
- `.robot.failed`

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

Existing:

- `.section-header`
- `.empty-msg`
- `.task-row`
- `.task-row.pending`
- `.task-row.assigned`
- `.task-row.completed`
- `.task-row.failed`
- `.task-badge`
- `.task-badge.putaway`
- `.task-badge.pick`
- `.task-badge.pack`
- `.task-badge.ship`
- `.task-badge.legacy`
- `.task-info`
- `.task-title`
- `.task-sub`

New v0.4:

- `.task-row.interrupted`

Important ids styled directly:

- `#warehouse`
- `#dashboard-grid`
- `#task-list`
- `#simulation-state`

---

## UI / Visualization

- Robot body color = robot identity.
- Robot ring/glow = current task type.
- Tile highlight = task location.
- Phase `To pickup`: strong amber highlight on pickup/access, faint green
  highlight on dropoff.
- Phase `To dropoff`: strong green highlight on dropoff/access.
- Highlights are derived from `/api/state` on every poll.
- Dashboard is a compact metric grid at the top of the sidebar.
- Task list uses compact rows with type badges and status borders.
- Active Queue includes `Pending`, `Assigned`, and `Interrupted` tasks.
- Recent History includes completed/failed tasks.
- Robot battery/mode is exposed through tooltip and CSS state classes.

---

## Extension Points

These are intentionally not implemented yet or only partially implemented:

- `INTERSECTION` → formal intersection traffic control.
- `MAIN_AISLE` → priority routing or speed changes.
- `PACKING` → packing queue or processing delay.
- `RECEIVING` → inbound task generation coupling.
- `SHIPPING` → outbound task completion coupling.
- `EMPTY` → dynamic obstacles or editor placement.
- `BUFFER` → QC delay or put-away scheduling.
- `PICK_STATION` → pick processing time or queueing.
- `CONSOLIDATION` → order merge logic.
- `STAGING` → carrier lane assignment.
- Physical load handoff → v0.4 uses logical task recovery, not physical pallet
  transfer.
- Reservation-based pathfinding → v0.4 uses local single-yielder deadlock
  recovery plus charger slot reservations, not full time-windowed MAPF.
- Predictive maintenance → not implemented.
