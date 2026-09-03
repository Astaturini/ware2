API Surface

This document lists the important names used by the warehouse simulator.
If code and documentation disagree, the code is the source of truth, but this
file should be updated immediately.

Project State

Project Name: warehouse_simulator
Current Version: v0.7.2
Git Tag: v0.7.2
Python Version: Python 3.13+ recommended. Pin Python 3.13 if dependency wheels are unstable on newer interpreters.
Dependencies: Flask, pandas, numpy, ECharts (frontend), Optuna (optional), pytest (development/testing)
Run Command: `python app.py`
Production: `gunicorn app:app` (never the Flask dev server when hosted)

Where The Project Is Now

v0.7.2 adds Spatial Diagnostics on top of the unchanged v0.7.1 Decision and
Realistic Scenario layers:

Spatial bottleneck analysis: blockage onset coordinates are recorded in
events.csv and aggregated into per-cell bottleneck statistics from saved
artifacts only.
Recorded benchmarks: benchmark.py now records every run through
ExperimentRunner into data/runs/<run_id>/.
Single-run engineering reports: decision/report.py can report one run without
a study, writing to data/reports/.

v0.7.1 adds a Decision Layer and Realistic Scenario layer on top of the
unchanged v0.6.0 algorithm plugin layer and unchanged v0.5.0 experimentation,
recording, storage, and analysis infrastructure.

New responsibilities added in v0.7.x:

Business KPIs: Cost KPIs computed from immutable saved run artifacts.
Batch experimentation / Design of Experiments: Factorial study runner.
Engineering reporting: Markdown study reports generated from saved study results.
Dynamic demand profiles: Legacy synthetic demand preserved; uniform, rate schedules, and deterministic CSV/order events added.
Configurable layout presets: Default warehouse preserved; JSON layout definitions and preset layouts added.

The v0.6.0 plugin layer remains unchanged:

Path Planning: `PathPlanner`, `BFSPathPlanner`, `AStarPathPlanner`
Scheduling: `Scheduler`, `CostBasedScheduler`, `PriorityScheduler`,
`FIFOScheduler`, `TotalCostScheduler`, `AuctionScheduler`
Conflict Resolution: `ConflictManager`, `LocalYieldConflictManager`,
`ZoneLockConflictManager`, `PrioritizedReservationConflictManager`

The v0.5 experimentation layer (config, recorder, runner, storage, analysis)
is unchanged. The v0.4 battery/charging/failure simulation core is unchanged.
The v0.3.1 traffic model is preserved as the `local_yield` baseline.

v0.5 separates six responsibilities (unchanged):

Simulation (`simulation/`) — v0.4 core with v0.6 plugin injection points.
Experiment configuration (`experiment/config.py`) — authoritative run
parameters.
Metrics recorder (`experiment/recorder.py`) — observes, never modifies.
Experiment runner (`experiment/runner.py`) — lifecycle, stopping, saving.
Data storage (`data/runs/<run_id>/`) — immutable per-run artifacts.
Visualization/analysis (`analysis/` + frontend) — reads saved data only.

The simulation does not depend on plotting. The plotting system never needs
live simulation objects. A completed experiment is fully reproducible and
analyzable from its saved files.

The UI is a multi-stage workflow, not one dashboard:

Setup -> Run (live) or Fast (headless) -> Results -> Experiments ->
Visualization -> Analysis -> Compare.

View transitions are a client-side state machine; the backend never redirects.

Breaking Changes / Changes From v0.3.1 (v0.4.0)

Core Architecture

Added `simulation/config.py` containing `BatteryConfig`, `ChargingConfig`,
and `FailureConfig`.
Added `simulation/charging.py` containing `ChargingStation`.
`Simulation` constructor now accepts keyword-only v0.4 arguments:
`battery_config`, `charging_config`, `failure_config`, and `seed`.
`Simulation` now owns charging-station state, maintenance-cell scanning,
failure RNG, dynamic resume-location tracking, and congestion snapshots.
Added task interruption, recovery, and reassignment logic.
Added battery drain from actual movement.
Added loaded movement consuming more energy than empty movement.
Added critical battery, opportunistic charging, and empty-battery recovery.
Added robot failures, repair time, and maintenance relocation.
Yield scoring now includes battery urgency.
Added taskless routing helper `_route_robot_to_cell()` for charger and
maintenance movement.

Data Models

`Robot` gained `RobotMode` and v0.4 battery/charging/failure fields.
`Task` gained `LoadState`, `INTERRUPTED` status, interruption count,
last-assigned robot, and resume-location fields.
`Metrics` gained battery, charging, waiting-breakdown, interruption,
failure, and congestion-related fields/methods.

Frontend / CLI

`benchmark.py` accepts v0.4 battery, charging, and failure parameters.
`optimize_optuna.py` accepts fixed v0.4 parameters and optional
`--search-v04` mode.
Frontend supports `Interrupted` tasks, robot mode/battery tooltips, and
v0.4 dashboard metrics.
CSS adds styles for interrupted tasks and robot battery/charging/failure
states.

Breaking Changes / Changes From v0.4.0 (v0.5.0)

Added `experiment/` package: `config.py`, `factory.py`, `recorder.py`,
`runner.py`.
Added `analysis/` package: `loader.py`, `metrics.py`, `web.py`.
`app.py` uses a mutable `holder = {"simulation": ..., "runner": ...}`; the
v0.4 closure-based single-simulation wiring is gone.
`create_default_simulation()` replaced by
`create_simulation_from_config(ExperimentConfig.default())`.
Robot creation is dynamic and seeded (old hardcoded 13-position list gone);
no robot-count cap beyond available passable cells.
`ExperimentConfig` gained `display_name` (label only) and `fast_mode`
(pacing only; never affects results).
New routes: experiment lifecycle, run deletion, and analysis JSON API.
Frontend rewritten: view state machine, `MultiSelect` component, ECharts
charts (line, stacked area, bar, histogram), experiment delete, legend,
fast-run progress view.
CSS rewritten: dark theme, flat borderless tiles, glow-only task/location
highlights, square robots.
New persistent storage layout under `data/runs/`.
`benchmark.py` and `optimize_optuna.py` unchanged.

Breaking Changes / Changes From v0.5.0 (v0.6.0)

Core Architecture

`simulation/pathfinding.py` UPDATED: added `PathPlanner` protocol,
`BFSPathPlanner`, and `AStarPathPlanner` classes. `find_shortest_path()`
preserved as backward-compatible wrapper delegating to `BFSPathPlanner`.
`simulation/scheduler.py` UPDATED: added `PriorityScheduler`,
`FIFOScheduler`, `TotalCostScheduler`, and `AuctionScheduler` alongside
existing `CostBasedScheduler`. All implement the `Scheduler` protocol.
Added `simulation/conflict.py` containing `ConflictManager` protocol,
`LocalYieldConflictManager`, `ZoneLockConflictManager`, and
`PrioritizedReservationConflictManager`.
Added `simulation/reservations.py` containing `ReservationTable`.
`Simulation` constructor gained keyword-only `path_planner` argument.
`Simulation` gained `set_conflict_manager()` public method.
`Simulation` gained `_conflict_manager` internal state, initialized to
`LocalYieldConflictManager(self)`.
`Simulation._tick()` now calls `self._conflict_manager.tick()` before
`_advance_robots()`.
`Simulation._advance_robots()` now calls
`self._conflict_manager.allow_step()` before the occupied-cell check.
`Simulation._congestion_snapshot()` reads
`self._conflict_manager.active_conflicts`.
All conflict-related private methods moved from `Simulation` into
`LocalYieldConflictManager`.

Experiment Configuration

`ExperimentConfig` gained `path_planner: str = "bfs"` field.
`ExperimentConfig` gained `conflict_manager: str = "local_yield"` field.
`ExperimentConfig.__post_init__` validates `path_planner` against
`PATH_PLANNER_CHOICES` and `conflict_manager` against
`CONFLICT_MANAGER_CHOICES`.

Factory

`experiment/factory.py` gained `create_path_planner_from_name(name)`.
`experiment/factory.py` gained
`create_scheduler_from_name(name, path_planner)`.
`experiment/factory.py` gained
`create_conflict_manager_from_name(name, sim)`.
`experiment/factory.py` gained `create_path_planner(config)`.
`experiment/factory.py` gained `create_scheduler(config, path_planner)`.
`experiment/factory.py` gained `create_conflict_manager(config, sim)`.
`create_simulation_from_config()` now creates and injects the configured
scheduler, path planner, and conflict manager.

CLI

`benchmark.py` gained `--path-planner` argument
(choices: `bfs`, `astar`, `weighted_astar`; default: `bfs`).
`benchmark.py` gained `--scheduler` argument
(choices: `baseline`, `priority`, `fifo`, `total_cost`, `auction`;
default: `baseline`).
`benchmark.py` gained `--conflict-manager` argument
(choices: `local_yield`, `zone_locks`, `priority_reservation`;
default: `local_yield`).
`benchmark.py` prints active path planner, scheduler, and conflict manager
class names before running.
`benchmark.py` prints conflict manager diagnostics after running
(`tick_calls`, `robots_with_paths`, `locks_created`,
`reservations_created`, `denied_steps`).

Frontend

Setup view gained three algorithm dropdowns:
`cfg-path-planner`, `cfg-scheduler`, `cfg-conflict-manager`.
Setup view uses `.setup-grid` two-column card layout.
Run view restructured: `.run-layout` flex container with `.run-main`
(warehouse + legend) and `.run-sidebar` (controls + dashboard + task list).
Pause/Resume/Reset buttons moved to `.run-controls` at top of sidebar.
`readExperimentConfig()` includes `path_planner`, `scheduler`, and
`conflict_manager`.

CSS

Added `.setup-grid`, `.setup-grid .card`, `.setup-grid .card.full-width`.
Added `.run-layout`, `.run-main`, `.run-sidebar`, `.run-controls`.
Added responsive breakpoint at 1100px.

Breaking Changes / Changes From v0.6.0 (v0.7.1)

Decision Layer

Added `decision/` package:

`decision/cost.py`: `CostConfig` dataclass for run-level business costs.
`decision/kpis.py`: `CostKPIs`, `compute_cost_kpis()`, `compute_cost_kpis_for_run_id()`. Reads saved artifacts only.
`decision/study.py`: `StudyConfig`, `StudyRunner`. Executes factorial DoE matrices and outputs `data/studies/<study_id>/results.csv`.
`decision/report.py`: `generate_report()`. Generates Markdown engineering reports from study results, including trade-off observations.
`decision/demand.py`: `DemandConfig`, `DemandModel`, `DemandTaskGenerator`. Supports `legacy`, `uniform`, `rate_schedule`, and `csv_orders` demand modes.
`decision/layout.py`: `LayoutConfig`, `PRESET_LAYOUTS`. Supports `default`, `high_density`, and `one_way_aisles` layout presets.

Experiment Configuration

`ExperimentConfig` gained additive v0.7.1 fields with backward-compatible defaults:

`demand_mode: str = "legacy"`
`demand_rate_per_tick: float = 0.0`
`demand_task_weights: dict[str, float]`
`demand_segments: list[dict[str, Any]]`
`demand_csv_path: str | None = None`
`demand_events: list[dict[str, Any]]`
`layout_preset: str = "default"`
`layout_file: str | None = None`

`ExperimentConfig.__post_init__` validates demand and layout fields.

Factory

`experiment/factory.py` gained `create_task_generator(config, warehouse)`.
`create_simulation_from_config()` now builds the warehouse using `decision.layout.create_warehouse_for_experiment()` and the task generator using `create_task_generator()`. Default behavior remains unchanged.

Storage Format

Run storage structure is unchanged. `config.json` gained the new v0.7.1 keys.
New study storage layout added under `data/studies/<study_id>/`.

Breaking Changes / Changes From v0.7.1 (v0.7.2)

Experiment Layer

`ExperimentRunner._snapshot()` now extracts per-robot `x` and `y`.
`MetricsRecorder` writes `{"x": ..., "y": ...}` JSON into the `details`
column of `robot_blocked` events (the cell occupied when blocking started).
`events.csv` schema is unchanged.

Decision Layer

Added `decision/spatial.py`: `SpatialCellLoad`, `SpatialBlockageResult`,
`compute_spatial_blockage()`, `top_bottleneck_cells()`, and internal
`_pair_blocked_episodes()`. Reads saved artifacts only. Blockage episodes
are paired locally from robot_blocked/robot_unblocked events; unclosed
episodes are censored at the final simulation tick. Per-cell metrics:
`blocked_events` (onset count) and `blocked_ticks` (episode duration
attributed to the onset cell).
`decision/report.py` gained `generate_run_report(run_id, base_dir=None)`.
Single-run reports are written to `data/reports/<run_id>_report.md`, never
inside `data/runs/` (run artifacts remain immutable).
Study reports gained a Spatial Bottleneck Analysis section, driven by the
`run_id` column in results.csv. Studies that vary `layout_preset` are
flagged as not comparable across runs.
`python -m decision.report` gained `--run-id` (mutually exclusive with
`--study-dir`) and `--base-dir`.

Decision CLI

Added `python -m decision.spatial --run-id <run_id>` (options: `--base-dir`,
`--top`, `--by {blocked_ticks,blocked_events}`, `--json`).

CLI Layer

`benchmark.py` now records every run through `ExperimentRunner`, writing
config.json, timeseries.csv, events.csv, and summary.json to
`data/runs/<run_id>/`. Benchmark wall-clock times are no longer comparable
to pre-v0.7.2 runs due to recording overhead.

Storage

Run storage structure is unchanged. Pre-v0.7.2 runs have empty `details` on
robot_blocked rows; spatial analysis reports them with coverage 0.0.
Added `data/reports/` for single-run Markdown reports.
`results.csv` carries `run_id` so each study row traces back to
`data/runs/<run_id>/`.

Important Code Default Note

The actual v0.3.1 code defaults are:

blocked_replan_seconds = 0.7
replan_cooldown_ticks = 7

Older documentation may mention `0.9` and `2`. The code defaults are the
source of truth.

Coordinate System

Coordinates are `(x, y)`.
`x` increases to the right.
`y` increases downward.
Origin is the top-left corner.

Naming Rules

Python

Classes use `PascalCase`.
Functions and variables use `snake_case`.
Private methods start with `_`.
Enum members use `UPPER_SNAKE_CASE`.

Stored Experiment Config

Stored `config.json` keys use `snake_case` because they map directly to
`ExperimentConfig` fields.

Live Frontend JSON API

Live `/api/state` and related frontend payloads use the established
camelCase keys from v0.4/v0.5/v0.6.

JavaScript

Functions and variables use `camelCase`.
DOM element variables usually end with `El`.

Python Modules

`simulation/config.py` (NEW in v0.4.0)

Configuration dataclasses for v0.4 features.

`BatteryConfig`

@dataclass(frozen=True)
class BatteryConfig

Fields:
`capacity: float = 100.0`
`empty_move_energy: float = 0.35`
`loaded_move_energy: float = 0.5`
`critical_battery: float = 15.0`
`opportunistic_charge_threshold: float = 30.0`
`idle_ticks_before_opportunistic_charge: int = 10`
`safety_margin: float = 5.0`
`empty_battery_recovery_ticks: int = 15`

Methods:
`move_cost(loaded: bool) -> float`
`is_critical(battery: float) -> bool`
`is_opportunistic_candidate(battery: float) -> bool`

Important behavior:
`empty_move_energy` is consumed per successful empty movement step.
`loaded_move_energy` is consumed per successful loaded movement step.
Battery consumption must come from actual movement, not elapsed time.
`critical_battery` forces charging behavior.
`opportunistic_charge_threshold` allows idle robots to charge after the
idle threshold.
`safety_margin` is added to estimated remaining task energy during
feasibility checks.
`empty_battery_recovery_ticks` is the minimum downtime when battery reaches
zero.

`ChargingConfig`

@dataclass(frozen=True)
class ChargingConfig

Fields:
`capacity: int = 4`
`charge_duration_ticks: int = 10`

Important behavior:
`capacity` is logical station capacity.
Physical `CHARGING` cells can further constrain simultaneous charging.
If the map has fewer usable charging cells than `capacity`, effective
physical charging may be lower.

`FailureConfig`

@dataclass(frozen=True)
class FailureConfig

Fields:
`enabled: bool = False`
`mtbf_ticks: float = 0.0`
`mttr_ticks: int = 25`
`seed: int | None = None`
`relocate_to_maintenance: bool = True`

Important behavior:
`mtbf_ticks <= 0` disables random failures.
`mttr_ticks` is repair duration.
If `relocate_to_maintenance` is true, failed/dead robots are moved/towed to
a `MAINTENANCE` cell.
If false, failed robots remain where they failed and become obstacles.

`simulation/charging.py` (NEW in v0.4.0)

Finite-capacity charging resource model.

`ChargingStation`

@dataclass
class ChargingStation

Fields:
`capacity: int`
`charge_duration_ticks: int`
`active: dict[str, int]` — robot_id -> remaining charging ticks.
`active_cells: dict[str, tuple[int, int]]` — robot_id -> charging cell.
`reserved_cells: dict[str, tuple[int, int]]` — robot_id -> reserved cell.
`waiting: set[str]` — robot ids waiting for charger capacity.

Properties:
`occupancy -> int`
`has_capacity -> bool`

Methods:
`is_charging(robot_id: str) -> bool`
`is_waiting(robot_id: str) -> bool`
`add_waiting(robot_id: str) -> None`
`remove_waiting(robot_id: str) -> None`
`reserve(robot_id: str, cell: tuple[int, int]) -> bool`
`release_reservation(robot_id: str) -> None`
`begin_charging(robot_id: str, cell: tuple[int, int]) -> bool`
`release(robot_id: str) -> None`
`is_cell_active(cell: tuple[int, int]) -> bool`
`is_cell_reserved(cell: tuple[int, int]) -> bool`
`tick() -> list[str]`

Important behavior:
Active robots occupy capacity.
Waiting robots do not occupy capacity.
Reserved robots hold capacity while traveling to a charging cell.
`has_capacity` accounts for active plus reserved robots.
`begin_charging()` converts a reservation into active charging, or takes an
unreserved slot if capacity allows.
`tick()` advances charging timers and returns robot ids that finished.

`simulation/warehouse.py`

`CellType`

class CellType(str, Enum)

Members:
`EMPTY`, `SHELF`, `AISLE`, `MAIN_AISLE`, `PACKING`, `RECEIVING`,
`SHIPPING`, `CHARGING`, `INTERSECTION`, `BUFFER`, `PICK_STATION`,
`CONSOLIDATION`, `STAGING`, `MAINTENANCE`

Values should be the same as member names:

CellType.EMPTY.value == "EMPTY"
CellType.SHELF.value == "SHELF"
CellType.CHARGING.value == "CHARGING"
CellType.MAINTENANCE.value == "MAINTENANCE"

Important:
Enum values and layout symbol keys must not contain trailing spaces.
Correct: `"EMPTY"`, not `"EMPTY "`.
Correct: `"."`, not `". "`.

`LAYOUT_SYMBOLS`

LAYOUT_SYMBOLS: dict[str, CellType]

Supported layout symbols:
`.` -> `EMPTY`
`E` -> `EMPTY`
`#` -> `SHELF`
`a` -> `AISLE`
`M` -> `MAIN_AISLE`
`P` -> `PACKING`
`R` -> `RECEIVING`
`S` -> `SHIPPING`
`C` -> `CHARGING`
`I` -> `INTERSECTION`
`B` -> `BUFFER`
`K` -> `PICK_STATION`
`O` -> `CONSOLIDATION`
`G` -> `STAGING`
`X` -> `MAINTENANCE`

`Location`

@dataclass(frozen=True)
class Location

Fields:
`location.name: str`
`location.cell: tuple[int, int]`
`location.access: tuple[int, int]`

Meaning:
`cell` is the physical cell the location represents.
`access` is the passable cell an AMR actually drives to.

`Warehouse`

class Warehouse

Constructor:

Warehouse(
    layout: Iterable[str],
    locations: Mapping[str, Location] | None = None,
)

Public attributes:
`warehouse.width: int`
`warehouse.height: int`
`warehouse.layout: list[list[CellType]]`
`warehouse.locations: dict[str, Location]`

Public methods:
`warehouse.in_bounds(x: int, y: int) -> bool`
`warehouse.cell_type(x: int, y: int) -> CellType`
`warehouse.is_blocked(x: int, y: int) -> bool`
`warehouse.resolve(name: str) -> tuple[int, int]`
`warehouse.to_dict() -> dict[str, Any]`

Property:
`warehouse.obstacles -> frozenset[tuple[int, int]]`

Private methods:
`warehouse._parse_layout(layout) -> list[list[CellType]]`
`warehouse._validate() -> None`
`warehouse._rack_anchors() -> dict[str, list[int]]`

Important behavior:
`is_blocked()` returns `True` for out-of-bounds cells.
`is_blocked()` returns `True` for `SHELF` cells.
All other cell types are passable.
`resolve()` returns the location's access coordinate and raises `KeyError`
for unknown names.
`_validate()` checks that every location's cell and access are in bounds and
that access is not blocked.
`_rack_anchors()` returns one anchor cell per rack letter.
v0.4 dynamically adds `RESUME-*` locations to `warehouse.locations` during
simulation runtime for interrupted loaded tasks.
`Simulation.get_state()` should strip dynamic `RESUME-*` locations from the
serialized warehouse payload to avoid unnecessary frontend rebuilds.

`simulation/robot.py` (UPDATED in v0.4.0)

`RobotStatus`

class RobotStatus(str, Enum)

Members:
`IDLE = "Idle"`
`MOVING = "Moving"`

`RobotMode` (NEW in v0.4.0)

class RobotMode(str, Enum)

Members:
`IDLE`, `MOVING`, `TO_CHARGER`, `WAITING_FOR_CHARGER`, `CHARGING`,
`FAILED`, `REPAIRING`

Important behavior:
`RobotStatus` remains backward compatible with v0.3 UI consumers.
`RobotMode` carries richer v0.4 operational state.
A robot may have `status == Idle` while `mode == Charging` or
`mode == Waiting for charger`.

`Robot`

@dataclass
class Robot

Existing fields:
`robot.id: str`
`robot.x: int`
`robot.y: int`
`robot.color: str`
`robot.status: RobotStatus`
`robot.path: list[tuple[int, int]]`
`robot.current_task_id: str | None`
`robot.route_goal: tuple[int, int] | None`
`robot.blocked_ticks: int`
`robot.replanning: bool`
`robot.yielding_to: str | None`
`robot.replan_cooldown: int`
`robot.travel_history: list[tuple[int, int]]`
`robot.temporary_path: bool`

New v0.4 fields:
`robot.battery: float`
`robot.mode: RobotMode`
`robot.idle_ticks: int`
`robot.charger_wait_ticks: int`
`robot.interrupted_task_id: str | None`
`robot.charge_target: tuple[int, int] | None`
`robot.charge_start_battery: float | None`
`robot.repair_remaining_ticks: int`

Property:
`robot.current_target -> tuple[int, int] | None`

Public methods:
`robot.set_path(path: list[tuple[int, int]]) -> None`
`robot.set_temporary_path(path: list[tuple[int, int]]) -> None`
`robot.advance() -> bool`
`robot.to_dict() -> dict[str, Any]`

Important behavior:
`set_path()` expects a path excluding the robot's current cell.
`advance()` moves the robot one cell.
`advance()` returns `True` when the robot reaches the end of its path.
`route_goal` is the current final destination for the robot's current task
phase or taskless movement target.
`travel_history` stores previously visited cells and is used for
backtracking during yield maneuvers.
`battery` must never become negative.
`idle_ticks` is used for opportunistic charging.
`charger_wait_ticks` counts waiting for charger capacity, not active
charging time.
`interrupted_task_id` allows a robot to attempt to reclaim its own
interrupted task after charging/repair if the task is still unassigned.

`simulation/task.py` (UPDATED in v0.4.0)

`TaskType`

class TaskType(str, Enum)

Members: `PUTAWAY`, `PICK`, `PACK`, `SHIP`, `LEGACY`

`TaskStatus`

class TaskStatus(str, Enum)

Members:
`PENDING = "Pending"`
`ASSIGNED = "Assigned"`
`COMPLETED = "Completed"`
`FAILED = "Failed"`
`INTERRUPTED = "Interrupted"` (NEW in v0.4.0)

`TaskPhase`

class TaskPhase(str, Enum)

Members:
`TO_PICKUP = "To pickup"`
`TO_DROPOFF = "To dropoff"`
`DONE = "Done"`

`LoadState` (NEW in v0.4.0)

class LoadState(str, Enum)

Members:
`ON_SHELF = "On shelf"`
`CARRIED = "Carried"`
`STAGED = "Staged"`
`DELIVERED = "Delivered"`

Important behavior:
`LoadState` is a logical cargo state, not full physical pallet handling.
If a loaded task is interrupted, the load remains associated with the task
and is logically staged at a resume location.

`Task`

@dataclass
class Task

Existing fields:
`task.id: str`
`task.name: str`
`task.pickup: str`
`task.dropoff: str`
`task.task_type: TaskType`
`task.priority: int`
`task.created_at: int`
`task.completed_at: int | None`
`task.status: TaskStatus`
`task.assigned_robot_id: str | None`
`task.phase: TaskPhase`

New v0.4 fields:
`task.load_state: LoadState`
`task.interruption_count: int`
`task.last_assigned_robot_id: str | None`
`task.resume_location_name: str | None`

Public methods:
`task.to_dict() -> dict[str, Any]`

Important behavior:
`pickup` and `dropoff` are location names, resolved to coordinates via
`warehouse.resolve()`.
If a loaded task is interrupted, `pickup` may be rewritten to a temporary
`RESUME-*` location name.
`INTERRUPTED` tasks remain claimable by another robot.
`interruption_count` supports reassignment metrics.
`last_assigned_robot_id` supports reassignment detection.

`simulation/task_generator.py`

`TaskGenerator`

@dataclass
class TaskGenerator

Constructor fields:
`warehouse: Warehouse`
`start_tick: int = 2`
`seed: int | None = None`

Public methods:
`task_generator.step(tick: int) -> list[Task]`
`task_generator.reset() -> None`

Private methods:
`_refresh_location_cache() -> None`
`_create_task(task_type: TaskType, tick: int) -> Task`
`_pick_one(values: list[str], fallback: str | None = None) -> str`
`_priority_for(task_type: TaskType) -> int`
`_interval_for(task_type: TaskType) -> int`

Important behavior:
Generates tasks during the simulation instead of seeding all work at
startup.
Emits a light stream of `PUTAWAY`, `PICK`, `PACK`, and `SHIP` tasks using
existing named locations.
Priority mapping, lower number = higher priority:
`SHIP` = 0
`PACK` = 1
`PICK` = 2
`PUTAWAY` = 3
If `seed` is an int, random location selection is reproducible.
If `seed` is None, deterministic round-robin behavior is preserved.
Reset re-seeds with the same seed.

`simulation/pathfinding.py` (UPDATED in v0.6.0)

`PathPlanner` (NEW in v0.6.0)

class PathPlanner(Protocol)

Method:
`find_path(warehouse, start, goal, blocked_cells=None) -> list[tuple[int, int]] | None`

Return meaning:
`[]` — already at the goal.
`[...]` — path cells after `start`.
`None` — no path found.

`BFSPathPlanner` (NEW in v0.6.0)

class BFSPathPlanner

Implements `PathPlanner`. Uses BFS. Returns shortest paths. This is the
default planner and produces identical results to the v0.5
`find_shortest_path`.

`AStarPathPlanner` (NEW in v0.6.0)

class AStarPathPlanner

Constructor: `AStarPathPlanner(weight: float = 1.0)`

Implements `PathPlanner`. Uses A* with Manhattan heuristic.
`weight = 1.0`: Standard A*. On a uniform 4-connected grid, returns
shortest paths like BFS, but may choose a different shortest path when
ties exist.
`weight > 1.0`: Weighted A*. Faster search, but paths may be suboptimal.

`find_shortest_path` (preserved)

find_shortest_path(
    warehouse: Warehouse,
    start: tuple[int, int],
    goal: tuple[int, int],
    blocked_cells: Iterable[tuple[int, int]] | None = None,
) -> list[tuple[int, int]] | None

Backward-compatible wrapper. Delegates to a module-level `BFSPathPlanner`
instance. Existing modules that still import `find_shortest_path` will keep
working. New code should use an injected `PathPlanner` instead.

`simulation/scheduler.py` (UPDATED in v0.6.0)

`Assignment`

@dataclass(frozen=True)
class Assignment

Fields:
`assignment.task_id: str`
`assignment.robot_id: str`
`assignment.cost: int`
`assignment.path: list[tuple[int, int]]`

`Scheduler`

class Scheduler(Protocol)

Method:
`select_assignments(pending_tasks, robots, warehouse, blocked_cells=None) -> list[Assignment]`

`CostBasedScheduler`

class CostBasedScheduler

Baseline scheduler. Chooses the idle robot with the shortest feasible path to
each pending task pickup. Processes tasks by `(-priority, created_at, id)`.
Constructor accepts optional `path_planner` keyword argument. Defaults to
`BFSPathPlanner()`.

`PriorityScheduler` (NEW in v0.6.0)

class PriorityScheduler

Nearest-pickup dispatcher with correct priority ordering. Processes tasks by
`(priority, created_at, id)` where lower `priority` value = higher urgency.
For each task, assigns the nearest feasible robot to the pickup.

`FIFOScheduler` (NEW in v0.6.0)

class FIFOScheduler

Nearest-pickup dispatcher that processes oldest tasks first. Processes tasks
by `(created_at, priority, id)`. For each task, assigns the nearest feasible
robot to the pickup.

`TotalCostScheduler` (NEW in v0.6.0)

class TotalCostScheduler

Battery/energy-aware scheduler. For each task, computes the estimated total
cost as `distance_to_pickup + distance_pickup_to_dropoff`. Assigns the robot
with the lowest total cost. Constructor accepts optional `path_planner`,
`empty_move_energy`, `loaded_move_energy`, `safety_margin`, and
`critical_battery` keyword arguments.

`AuctionScheduler` (NEW in v0.6.0)

class AuctionScheduler

Centralized first-price auction approximation. Each remaining task receives
bids from each remaining robot. The lowest total bid wins. Bid cost is
`distance_to_pickup + distance_pickup_to_dropoff`. Iterates until all tasks
or robots are exhausted.

`simulation/conflict.py` (NEW in v0.6.0)

`ConflictManager`

class ConflictManager(Protocol)

Methods:
`handle_blocked_robot(robot, next_cell) -> None`
`advance_replanning_robot(robot, occupied) -> None`
`release_conflict(robot) -> None`
`clear_conflicts_for_robot(robot) -> None`
`reset() -> None`
`tick(current_tick: int, robots: list[Robot]) -> None`
`allow_step(robot, next_cell, occupied) -> bool`
`release_robot(robot_id: str) -> None`

Property:
`active_conflicts -> int`

`LocalYieldConflictManager`

class LocalYieldConflictManager

Constructor: `LocalYieldConflictManager(sim: Simulation)`

Baseline reactive conflict manager. Contains all the v0.3.1
traffic/conflict resolution logic previously in `Simulation`. `tick()` and
`allow_step()` are no-ops. `release_robot()` is a no-op.

Important behavior:
Preserves the v0.3.1 local deadlock-recovery mechanism exactly.
`handle_blocked_robot()`, `advance_replanning_robot()`,
`release_conflict()`, `clear_conflicts_for_robot()` implement the
existing yield logic.
`_make_robot_yield()`, `_select_yielding_robot()`, `_yield_score()`,
`_can_yield()`, `_choose_yield_step()` are private helpers.
`_complete_yield()` resumes normal routing after a yield maneuver.

`ZoneLockConflictManager` (NEW in v0.6.0)

class ZoneLockConflictManager

Constructor: `ZoneLockConflictManager(sim: Simulation, lookahead: int = 2)`

Inherits from `LocalYieldConflictManager`. Adds proactive path-corridor zone
locks on top of the reactive local yield system.

Important behavior:
`tick()` rebuilds zone locks from each robot's current path. Claims the
next `lookahead` cells on each robot's path. Robots are sorted by
`_yield_score()` (less willing to yield claims first).
`allow_step()` denies a step if the target cell is locked by another robot,
unless the robot has been blocked for too long (starvation fallback:
`blocked_ticks >= blocked_replan_threshold_ticks * 2`).
Diagnostic counters: `denied_steps`, `locks_created`, `tick_calls`,
`robots_with_paths`.
Failed, repairing, and charging robots do not create claims.

`PrioritizedReservationConflictManager` (NEW in v0.6.0)

class PrioritizedReservationConflictManager

Constructor:
`PrioritizedReservationConflictManager(sim: Simulation, horizon: int = 32)`

Inherits from `LocalYieldConflictManager`. Adds approximate prioritized
reservation-based conflict management on top of the reactive local yield
system.

Important behavior:
`tick()` rebuilds vertex reservations from each robot's current path using
a `ReservationTable`. Robots are sorted by a priority score (higher score
reserves first). Priority score considers: robot mode, task priority,
loaded status, battery urgency, and blocked time.
`allow_step()` denies a step if the target cell is reserved by another robot
at the next tick, unless the robot has been blocked for too long
(starvation fallback: `blocked_ticks >= blocked_replan_threshold_ticks * 2`).
Diagnostic counters: `denied_steps`, `reservations_created`, `tick_calls`,
`robots_with_paths`.
Failed, repairing, and charging robots do not create reservations.
This is not full space-time MAPF. It is a practical proactive traffic
manager for experimentation.

`simulation/reservations.py` (NEW in v0.6.0)

`ReservationTable`

class ReservationTable

Simple vertex reservation table. Tracks which robot intends to occupy which
cell at which tick. Does not track edge reservations (swap collisions).

Fields:
`_vertex_reservations: dict[tuple[int, int], dict[int, str]]`
— cell -> tick -> robot_id.
`_robot_reservations: dict[str, set[tuple[tuple[int, int], int]]]`
— robot_id -> set of reserved (cell, tick) pairs.

Methods:
`reset() -> None`
`reserve(robot_id: str, cell: tuple[int, int], tick: int) -> bool`
`owner(cell: tuple[int, int], tick: int) -> str | None`
`is_free(cell: tuple[int, int], tick: int, robot_id: str) -> bool`
`release_robot(robot_id: str) -> None`
`prune(current_tick: int) -> None`

`simulation/metrics.py` (UPDATED in v0.4.0)

`Metrics`

@dataclass
class Metrics

Existing v0.3 fields:
`metrics.tasks_generated: int`
`metrics.tasks_assigned: int`
`metrics.tasks_completed: int`
`metrics.tasks_failed: int`
`metrics.blocked_time_ticks: int`
`metrics.replanning_count: int`
`metrics.deadlock_resolutions: int`
`metrics.task_waiting_time_total: float`
`metrics.task_completion_time_total: float`
`metrics.robot_distance_travelled: dict[str, int]`
`metrics.robot_busy_ticks: dict[str, int]`
`metrics.robot_total_ticks: dict[str, int]`
`metrics.robot_blocked_ticks: dict[str, int]`
`metrics.robot_replan_events: dict[str, int]`
`metrics.tick_count: int`

New v0.4 fields:
`metrics.battery_capacity: float`
`metrics.battery_sum: float`
`metrics.battery_samples: int`
`metrics.charging_events: int`
`metrics.total_charging_ticks: int`
`metrics.charger_wait_ticks: int`
`metrics.charger_wait_events: int`
`metrics.traffic_wait_ticks: int`
`metrics.station_wait_ticks: int`
`metrics.battery_task_interruptions: int`
`metrics.failure_task_interruptions: int`
`metrics.task_reassignments: int`
`metrics.failed_robot_events: int`
`metrics.failure_downtime_ticks: int`

Existing methods:
`metrics.reset() -> None`
`metrics.register_robot(robot: Robot) -> None`
`metrics.record_generated(task: Task) -> None`
`metrics.record_assigned(task: Task, tick: int) -> None`
`metrics.record_completed(task: Task, tick: int) -> None`
`metrics.record_failed(task: Task, tick: int) -> None`
`metrics.record_blocked(robot: Robot, blocked_ticks: int = 1) -> None`
`metrics.record_replan(robot: Robot) -> None`
`metrics.record_deadlock_resolution() -> None`
`metrics.record_robot_move(robot: Robot, distance: int = 1) -> None`
`metrics.record_tick(robots: list[Robot]) -> None`
`metrics.to_dict(tick_interval: float) -> dict[str, Any]`

New v0.4 methods:
`metrics.record_battery_sample(robot: Robot) -> None`
`metrics.record_charging_start() -> None`
`metrics.record_charging_tick() -> None`
`metrics.record_charger_wait_start() -> None`
`metrics.record_charger_wait_tick() -> None`
`metrics.record_battery_task_interruption() -> None`
`metrics.record_failure_task_interruption() -> None`
`metrics.record_task_reassignment() -> None`
`metrics.record_failed_robot_event() -> None`
`metrics.record_failure_downtime_tick() -> None`

Important behavior:
Existing v0.3 metric keys remain unchanged.
Blocked time is also counted as traffic waiting.
Active charging time is not waiting time.
Waiting for a free charger slot is charger waiting.
Battery samples are used to compute average battery.
Charger waiting events are used to compute average charger wait.

`simulation/simulation.py` (UPDATED in v0.6.0)

`Simulation`

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
    blocked_replan_seconds: float = 0.7,
    replan_cooldown_ticks: int = 7,
    *,
    battery_config: BatteryConfig | None = None,
    charging_config: ChargingConfig | None = None,
    failure_config: FailureConfig | None = None,
    seed: int | None = None,
    path_planner: PathPlanner | None = None,
)

Public methods:
`simulation.start() -> None`
`simulation.pause() -> None`
`simulation.resume() -> None`
`simulation.reset() -> None`
`simulation.stop() -> None`
`simulation.get_state() -> dict[str, Any]`
`simulation.set_conflict_manager(manager: ConflictManager) -> None` (NEW)

Property:
`simulation.is_paused -> bool`

Important internal state:

Existing:
`simulation._warehouse`
`simulation._robots`
`simulation._tasks`
`simulation._initial_robots`
`simulation._initial_tasks`
`simulation._tick_count`
`simulation._tick_interval`
`simulation._lock`
`simulation._stop_event`
`simulation._running_event`
`simulation._thread`
`simulation._blocked_replan_threshold_ticks`
`simulation._replan_cooldown_ticks`

New v0.4:
`simulation._battery_cfg`
`simulation._charging_cfg`
`simulation._failure_cfg`
`simulation._charging_station`
`simulation._charging_cells`
`simulation._maintenance_cells`
`simulation._failure_seed`
`simulation._failure_rng`
`simulation._dynamic_location_names`

New v0.6:
`simulation._path_planner` — injected `PathPlanner` instance. Defaults to
`BFSPathPlanner()`.
`simulation._conflict_manager` — injected `ConflictManager` instance.
Defaults to `LocalYieldConflictManager(self)`.

Important behavior:
`start()` starts the background simulation thread.
`pause()` stops ticking but keeps state.
`resume()` continues ticking.
`reset()` restores robots and tasks to their initial state, clears conflict
manager state via `self._conflict_manager.reset()`, clears dynamic resume
locations, resets charging station state, resets failure RNG, and restores
robot batteries/modes.
`set_conflict_manager()` replaces the active conflict manager and rebinds
its `_sim` reference.
`get_state()` returns a JSON-serializable snapshot.
`get_state()` should strip dynamic `RESUME-*` locations from the warehouse
payload.
`_tick()` runs failures/repairs, charging station progression, task
generation, assignment, battery checks, opportunistic charging,
conflict manager tick (v0.6), robot movement, metrics, and pruning.
`_advance_robots()` calls `self._conflict_manager.allow_step()` before the
occupied-cell check. Replanning/yielding robots are NOT gated by
`allow_step()` so deadlock escape still works.
`_prune_old_tasks()` deletes completed/failed tasks whose `completed_at` is
more than 100 ticks old. Interrupted tasks are not pruned.

Traffic / Conflict Resolution Behavior

v0.3.1 Local Yield (preserved as `local_yield`)

When a robot's next cell is occupied by another robot, the blocked robot
increments `blocked_ticks`.
After `blocked_replan_seconds` the conflict becomes eligible for yielding.
For each blocking pair, only one robot may replan at a time.
The selected yielder is stored in `_active_conflict_yielder`.
The non-yielding robot's route is frozen during the conflict.
The yielding robot receives a local yield step from `_choose_yield_step()`.
Yield step preference:
A neighboring cell that still allows reaching the current `route_goal`.
A backtrack step through recent `travel_history`.
Any safe escape neighbor, biased away from the blocker.
A valid yield step must be in bounds, not a shelf, not occupied, and not
claimed by another robot's immediate next target.
If the preferred yielder is stationary it can be forced to yield.
If the preferred yielder cannot act quickly enough, the blocked robot yields
instead.
If the active yielder appears inactive for too long, the blocked robot takes
over.
`_can_yield()` prevents a robot from participating in more than one active
conflict and enforces `replan_cooldown`.
`_attempt_resume_route()` resumes normal BFS routing after a yield maneuver.
`_advance_replanning_robot()` retries a different local yield step if the
current yield step stays blocked for 2+ ticks.
`_release_conflict()` clears the pair record when the yielder moves.
`_clear_conflicts_for_robot()` removes stale conflicts when a robot begins a
task, arrives, interrupts, fails, or starts charging.
This is a local deadlock-recovery mechanism. It is not reservation-based
multi-agent pathfinding and does not implement intersection control.

v0.4 Yield Score Additions

`_yield_score()` still uses idle status, task priority, and blocked time.
Battery urgency reduces willingness to yield.
Critical battery robots are strongly protected from unnecessary yielding.
Failed, repairing, and actively charging robots cannot yield.
Battery is one factor, not the only factor.

v0.6 Zone Locks (`zone_locks`)

Proactive path-corridor zone locks on top of reactive local yield.
Each tick, `tick()` rebuilds zone locks from each robot's current path.
Claims the next `lookahead` cells (default 2) on each robot's path.
Robots are sorted by `_yield_score()` — less willing to yield claims first.
`allow_step()` denies a step if the target cell is locked by another robot.
Starvation fallback: if `blocked_ticks >= blocked_replan_threshold_ticks * 2`,
the robot is allowed through regardless of locks.
Failed, repairing, and charging robots do not create claims.
Diagnostic counters: `denied_steps`, `locks_created`, `tick_calls`,
`robots_with_paths`.

v0.6 Priority Reservation (`priority_reservation`)

Approximate prioritized reservation-based conflict management on top of
reactive local yield.
Each tick, `tick()` rebuilds vertex reservations from each robot's current
path using a `ReservationTable`.
Robots are sorted by a priority score. Higher-priority robots reserve first.
Priority score considers: robot mode, task priority, loaded status, battery
urgency, and blocked time.
`allow_step()` denies a step if the target cell is reserved by another robot
at the next tick.
Starvation fallback: if `blocked_ticks >= blocked_replan_threshold_ticks * 2`,
the robot is allowed through regardless of reservations.
Failed, repairing, and charging robots do not create reservations.
Diagnostic counters: `denied_steps`, `reservations_created`, `tick_calls`,
`robots_with_paths`.
This is not full space-time MAPF. It is a practical proactive traffic
manager for experimentation.

Battery / Charging / Failure Behavior (v0.4.0)

Battery Simulation

Every robot has a battery value.
Battery decreases only from actual successful movement.
Loaded movement consumes more energy than empty movement.
Battery cannot become negative.
Battery feasibility includes a safety margin.
Initial route estimates are not guaranteed to remain valid.

Battery-Aware Routing

When a task is assigned, the simulation estimates whether the route is
battery-feasible.
During execution, the simulation estimates energy required to complete the
current remaining route.
Battery feasibility is re-evaluated after:
task assignment,
arrival at pickup,
successful movement,
route resumption,
yield-step assignment,
replanning or detours.
If the remaining task becomes infeasible, the robot interrupts the task and
seeks charging.
The robot must not blindly continue until battery reaches zero.

Charging Decisions

Critical battery:
If battery <= critical threshold, the robot seeks charging.
If active task cannot be safely finished, the task is interrupted.
Critical charging has priority over opportunistic charging.
Insufficient for task:
If remaining battery < estimated remaining task energy + safety margin, the
task is interrupted.
Task state is preserved.
The robot goes to charging.
After charging, the robot may reclaim the task if it is still unassigned.
Another robot may claim the interrupted task before then.
Opportunistic charging:
Idle robots may charge if:
they have no task,
they have been idle for `idle_ticks_before_opportunistic_charge`,
battery is below `opportunistic_charge_threshold`,
charger capacity is available,
a usable charging cell is available.
Idle robots do not charge immediately.

Charging Station Behavior

Charging station has finite logical capacity.
Default capacity is 4 robots.
Charging duration is configurable.
Active charging robots occupy slots.
Reserved robots occupy slots while traveling to charge.
Waiting robots do not occupy slots.
Waiting robots should not stand on charging cells.
If a waiting robot is on a charging cell and cannot charge, it is relocated
off the charging cell.
When capacity opens, waiting robots are dispatched deterministically.

Task Interruption / Reassignment

Task interruption reasons:
`critical_battery`
`insufficient_for_task`
`no_feasible_route`
`empty_battery`
`failure`

Interrupt behavior:
The task is preserved.
Task progress/state is preserved.
The robot is removed from the task.
The task becomes `Interrupted`.
The task becomes claimable by another robot.
The original robot remembers the interrupted task and may reclaim it after
charging/repair if it is still unassigned.
Normal traffic conflicts do not automatically interrupt tasks.

Load behavior:
If interrupted before pickup, load remains `On shelf`.
If interrupted while carrying, load becomes `Staged` at a logical resume
location.
If another robot claims the resumed task, it routes to the resume location,
then to dropoff.
This is operational/logical recovery, not detailed physical pallet handling.

Empty Battery Behavior

If battery reaches zero:
active task is interrupted,
robot becomes failed/down,
robot is relocated to maintenance if enabled,
robot remains down for at least `empty_battery_recovery_ticks`,
after recovery, battery is restored.

Failure / Repair Behavior

Random failures are optional and controlled by `FailureConfig.enabled`.
`mtbf_ticks` controls average ticks between failures.
`mttr_ticks` controls repair duration.
Failed robots stop moving and stop executing tasks.
Failed robots cannot yield.
Failed robots remain occupied cells unless relocated.
If `relocate_to_maintenance` is true, failed/dead robots are moved/towed to
a `MAINTENANCE` cell.
After repair, robots return to service.
After repair, robots may reclaim their interrupted task if still available.
If no task is reclaimed and the robot is on a maintenance cell, it tries to
move out of maintenance.

Decision Layer Modules (UPDATED in v0.7.2)

`decision/cost.py`

`CostConfig`

@dataclass(frozen=True)
class CostConfig

Fields:
`robot_opex_per_hour: float = 0.0`
`charger_infra_cost_per_hour: float = 0.0`
`downtime_cost_per_hour: float = 0.0`
`sla_target_ticks: int | None = None`
`sla_penalty_per_late_tick: float = 0.0`
`currency: str = "USD"`

Important behavior:
All monetary rates must be finite and >= 0.
CapEx and Energy costs are intentionally excluded at the run level.

`decision/kpis.py`

`CostKPIs`

@dataclass(frozen=True)
class CostKPIs

Fields:
`total_operating_cost: float`
`cost_per_task: float | None`
`sla_compliance_rate: float | None`
`completed_tasks: int`
`sla_evaluated_tasks: int`
`late_tasks: int`
`simulation_seconds: float`
`currency: str`
`cost_breakdown: dict[str, float]`

Functions:
`compute_cost_kpis(run_data, cost_config) -> CostKPIs`
`compute_cost_kpis_for_run_id(run_id, cost_config, base_dir=None) -> CostKPIs`

`decision/study.py`

`StudyConfig`, `StudyRunner`

Executes factorial DoE matrices and outputs `data/studies/<study_id>/results.csv`.
`results.csv` carries a `run_id` column so each row traces back to
`data/runs/<run_id>/` artifacts.

`decision/report.py`

`generate_report(study_dir: str | Path) -> Path`
`generate_run_report(run_id: str, base_dir: str | None = None) -> Path` (NEW in v0.7.2)

Generates Markdown engineering reports from study results, including
trade-off observations and a Spatial Bottleneck Analysis section.
Single-run reports include configuration, KPIs, distributions, and spatial
bottleneck tables, and are written to `data/reports/<run_id>_report.md`,
never inside `data/runs/` (run artifacts remain immutable).
CLI: `python -m decision.report --study-dir <study_dir>` or
`python -m decision.report --run-id <run_id> [--base-dir DIR]`.

`decision/spatial.py` (NEW in v0.7.2)

`SpatialCellLoad`

@dataclass(frozen=True)
class SpatialCellLoad

Fields:
`x: int`
`y: int`
`blocked_events: int`
`blocked_ticks: int`

`SpatialBlockageResult`

@dataclass(frozen=True)
class SpatialBlockageResult

Fields:
`run_id: str`
`total_blocked_events: int`
`events_with_coordinates: int`
`coverage: float`
`cells: list[SpatialCellLoad]`

Property:
`has_data -> bool`

Method:
`top_cells(n: int = 5, by: str = "blocked_ticks") -> list[SpatialCellLoad]`

Functions:
`compute_spatial_blockage(run_data) -> SpatialBlockageResult`
`top_bottleneck_cells(run_data, top_n=5) -> list[SpatialCellLoad]`
`_pair_blocked_episodes(events, final_tick)` — internal episode pairing.

CLI: `python -m decision.spatial --run-id <run_id> [--base-dir DIR]
[--top N] [--by {blocked_ticks,blocked_events}] [--json]`

Important behavior:
Reads saved artifacts only (events.csv via `analysis.loader`).
`robot_blocked` rows must carry `{"x": ..., "y": ...}` JSON in `details`
(v0.7.2+ runs). Pre-v0.7.2 runs are reported with coverage 0.0.
Episodes are paired locally from robot_blocked/robot_unblocked events;
unclosed episodes are censored at `summary.json` `simulation_ticks`.
`blocked_ticks` are attributed to the onset cell; a robot can drift during
yield, so exact cells are approximate.
Hotspots near chargers indicate capacity problems; hotspots at aisle
intersections indicate traffic-control problems.

`decision/demand.py`

`DemandMode`, `DemandEvent`, `RateSegment`, `DemandConfig`, `DemandModel`, `DemandTaskGenerator`

Supports `legacy`, `uniform`, `rate_schedule`, and `csv_orders` demand modes.

`decision/layout.py`

`LayoutConfig`, `PRESET_LAYOUTS`

Supports `default`, `high_density`, and `one_way_aisles` layout presets.

Experiment Lifecycle (v0.5.0)

User defines ExperimentConfig (UI form or JSON)
-> POST /api/experiment/start
-> unique run_id created; run dir created; config.json saved
-> Simulation created from config (not started; runner drives ticking)
-> MetricsRecorder attached
-> runner calls `sim._tick()` under `sim._lock` each loop (benchmark pattern)
-> recorder writes one time-series row plus inferred events per tick
-> stop condition reached -> recorder closed -> summary.json written
-> visualization/analysis read saved files only (live sim not required)

The runner does NOT call `Simulation.start()`. It drives `_tick()` directly in
its own daemon thread and sleeps `tick_interval` between ticks (or yields only,
in fast mode).

Reproducibility And Seeding (v0.5.0)

`same config + same seed = same result`.

The seed controls:
`TaskGenerator(warehouse, seed=seed)` location selection,
failure RNG (`FailureConfig.seed` / `Simulation(seed=...)`),
robot spawn positions (seeded shuffle of passable cells in
`experiment/factory.generate_spawn_positions()`).

No global RNG reliance. No new randomness introduced in v0.5.
`fast_mode` removes wall-clock pacing only; tick semantics and results are
identical in live and fast mode.

Stopping Conditions (v0.5.0)

`stop_mode = "fixed_ticks"`: run until `max_ticks`. Answers "how much work in
the same time?".
`stop_mode = "workload"`: run until `target_tasks` completed, with `max_ticks`
as safety horizon. Answers "how long for the same workload?".
`stop_reason` values written to summary.json:
`target_reached`, `max_ticks_reached`, `stopped_by_user`, `reset_by_user`,
`error: <message>`.

Fast / Headless Mode (v0.5.0)

`ExperimentConfig.fast_mode: bool = False`.
When true, `ExperimentRunner._run()` does not sleep `tick_interval`; it yields
with `time.sleep(0)` every 500 ticks so the web server thread can answer polls.
`tick_interval` is untouched (it feeds `_blocked_replan_threshold_ticks`), so
results stay reproducible.
UI: Setup checkbox `cfg-fast-mode`; start shows `view-fast` (progress text
`fast-status`, `fast-stop-btn` -> POST /api/experiment/stop) instead of the
live map; on finish the poller auto-transitions to Results.
Recorded as metadata in config.json and summary.json (`fast_mode`).
Fast mode pins one CPU core for its duration; that is expected.

Run Identity And Storage Format (v0.5.0 / v0.7.2)

run_id format: `YYYYMMDD_HHMMSS_<6 hex>`, e.g. `20260821_013526_a83f21`.
Never seed-only; runs are never overwritten. `display_name` is metadata only.

data/
└── runs/
    └── <run_id>/
        ├── config.json
        ├── timeseries.csv
        ├── events.csv
        └── summary.json

data/
└── studies/ (NEW in v0.7.1)
    └── <study_id>/
        ├── study_config.json
        ├── results.csv
        └── report.md

data/
└── reports/ (NEW in v0.7.2)
    └── <run_id>_report.md

config.json keys (ExperimentConfig.to_dict()):
`seed`, `num_robots`, `display_name`, `stop_mode`, `target_tasks`,
`max_ticks`, `tick_interval`, `fast_mode`, `blocked_replan_seconds`,
`replan_cooldown_ticks`, `battery_capacity`, `empty_move_energy`,
`loaded_move_energy`, `critical_battery`,
`opportunistic_charge_threshold`, `idle_ticks_before_opportunistic_charge`,
`battery_safety_margin`, `empty_battery_recovery_ticks`, `charger_capacity`,
`charge_duration_ticks`, `failure_enabled`, `mtbf_ticks`, `mttr_ticks`,
`relocate_to_maintenance`, `scheduler`, `path_planner` (v0.6),
`conflict_manager` (v0.6).

New v0.7.1 keys:
`demand_mode`, `demand_rate_per_tick`, `demand_task_weights`, `demand_segments`,
`demand_csv_path`, `demand_events`, `layout_preset`, `layout_file`.

timeseries.csv headers (one row per tick):
`tick`, `tasks_pending`, `tasks_outstanding`, `tasks_created_this_tick`,
`tasks_completed_this_tick`, `tasks_completed_total`, `tasks_failed_total`,
`robots_active`, `robots_idle`, `robots_blocked`, `robots_charging`,
`robots_to_charger`, `robots_waiting_for_charger`, `robots_failed`,
`average_battery`, `min_battery`, `max_battery`, `replans_this_tick`,
`replans_total`, `blocked_ticks_this_tick`, `blocked_ticks_total`.

Definitions:
`tasks_pending` = live tasks with status Pending (unassigned only).
`tasks_outstanding` = generated - completed - failed (Pending + Assigned +
Interrupted). Never counts completed tasks awaiting pruning.
Robot buckets are mutually exclusive and sum to the population, priority:
failed/repairing > charging > waiting-for-charger > blocked
(blocked_ticks > 0) > to-charger > active (Moving) > idle.
Throughput stays per-tick: `throughput[t] = tasks_completed_this_tick`.
Averages/rolling windows exist only in the analysis layer.

events.csv headers:
`run_id`, `tick`, `event_type`, `robot_id`, `task_id`, `details`.
Missing fields are empty strings, never invented.

As of v0.7.2, `robot_blocked` rows carry `{"x": ..., "y": ...}` JSON in
`details` (the cell occupied when blocking started). All other event types
leave `details` empty unless documented. Pre-v0.7.2 runs have empty
`details` on `robot_blocked` rows.

Event types (inferred from primitive snapshots at tick resolution):
`task_created`, `task_assigned`, `task_completed`, `task_failed`,
`task_interrupted`, `task_reassigned`, `robot_blocked`, `robot_unblocked`,
`robot_replanned`, `robot_started_charging`, `robot_finished_charging`,
`robot_waiting_for_charger`, `robot_faulted`, `robot_recovered`.

Known limitation: multiple transitions inside one tick can be coalesced.
Live task pruning never deletes history; CSVs are written independently.

summary.json keys:
`run_id`, `seed`, `scheduler`, `stop_reason`, `fast_mode`,
`simulation_ticks`, `simulation_seconds`, `robot_count`, `tasks_created`,
`tasks_assigned`, `tasks_completed`, `tasks_failed`, `average_throughput`,
`average_wait_time`, `average_cycle_time`, `average_robot_utilization`,
`total_replans`, `total_blocked_ticks`, `blocked_time_seconds`,
`charging_events`, `total_charging_ticks`, `charger_wait_ticks`,
`charger_wait_events`, `battery_task_interruptions`,
`failure_task_interruptions`, `task_reassignments`, `failed_robot_events`,
`failure_downtime_ticks`, `robot_utilization` (dict robot_id -> 0..1),
`robot_busy_ticks`, `robot_total_ticks`, `robot_blocked_ticks`,
`robot_distance_travelled`.

Summary is for quick comparison; the CSVs are authoritative.

experiment/config.py (UPDATED in v0.7.1)

`ExperimentConfig` — @dataclass(frozen=True), validated in `__post_init__`.

Fields (defaults):
`seed: int`, `num_robots: int`, `display_name: str = ""`,
`stop_mode: Literal["fixed_ticks", "workload"]`, `target_tasks: int | None`,
`max_ticks: int`, `tick_interval: float = 0.3`, `fast_mode: bool = False`,
`blocked_replan_seconds: float = 0.7`, `replan_cooldown_ticks: int = 7`,
`battery_capacity: float = 100.0`, `empty_move_energy: float = 0.35`,
`loaded_move_energy: float = 0.5`, `critical_battery: float = 15.0`,
`opportunistic_charge_threshold: float = 30.0`,
`idle_ticks_before_opportunistic_charge: int = 10`,
`battery_safety_margin: float = 5.0`, `empty_battery_recovery_ticks: int = 15`,
`charger_capacity: int = 4`, `charge_duration_ticks: int = 10`,
`failure_enabled: bool = False`, `mtbf_ticks: float = 0.0`,
`mttr_ticks: int = 25`, `relocate_to_maintenance: bool = True`,
`scheduler: str = "baseline"`,
`path_planner: str = "bfs"` (NEW in v0.6.0),
`conflict_manager: str = "local_yield"` (NEW in v0.6.0),
`demand_mode: str = "legacy"` (NEW in v0.7.1),
`demand_rate_per_tick: float = 0.0` (NEW in v0.7.1),
`demand_task_weights: dict[str, float]` (NEW in v0.7.1),
`demand_segments: list[dict[str, Any]]` (NEW in v0.7.1),
`demand_csv_path: str | None = None` (NEW in v0.7.1),
`demand_events: list[dict[str, Any]]` (NEW in v0.7.1),
`layout_preset: str = "default"` (NEW in v0.7.1),
`layout_file: str | None = None` (NEW in v0.7.1).

Module-level constants:
`PATH_PLANNER_CHOICES = {"bfs", "astar", "weighted_astar"}`
`CONFLICT_MANAGER_CHOICES = {"local_yield", "zone_locks", "priority_reservation"}`
`DEMAND_MODE_CHOICES = {"legacy", "uniform", "rate_schedule", "csv_orders"}` (NEW in v0.7.1)
`LAYOUT_PRESET_CHOICES = {"default", "high_density", "one_way_aisles"}` (NEW in v0.7.1)

Methods: `default()`, `to_dict()`, `save(directory)`, `load(directory)`,
`from_dict(data)` (merges over defaults then validates).

Validation highlights: seed required; num_robots >= 1; workload requires
target_tasks >= 1; max_ticks >= 1; tick_interval > 0; failure_enabled requires
mtbf_ticks > 0; path_planner must be in PATH_PLANNER_CHOICES;
conflict_manager must be in CONFLICT_MANAGER_CHOICES; demand_mode must be in
DEMAND_MODE_CHOICES; layout_preset must be in LAYOUT_PRESET_CHOICES.

experiment/factory.py (UPDATED in v0.7.1)

`ROBOT_COLORS: list[str]` — Okabe-Ito-style palette, cycled by index.
`generate_spawn_positions(num_robots, warehouse, seed) -> list[tuple[int,int]]`
— collects passable cells, shuffles with `random.Random(seed)`, takes N;
ValueError if fewer passable cells than requested.
`create_experiment_robots(num_robots, warehouse, seed) -> list[Robot]` —
ids `R1..RN`, clean strings, deterministic seeded positions.
`create_path_planner_from_name(name: str) -> PathPlanner` (NEW in v0.6.0)
`create_scheduler_from_name(name: str, path_planner: PathPlanner) -> Scheduler` (NEW in v0.6.0)
`create_conflict_manager_from_name(name: str, sim: Simulation) -> ConflictManager` (NEW in v0.6.0)
`create_path_planner(config: ExperimentConfig) -> PathPlanner` (NEW in v0.6.0)
`create_scheduler(config: ExperimentConfig, path_planner: PathPlanner) -> Scheduler` (NEW in v0.6.0)
`create_conflict_manager(config: ExperimentConfig, sim: Simulation) -> ConflictManager` (NEW in v0.6.0)
`create_task_generator(config: ExperimentConfig, warehouse: Warehouse) -> TaskGenerator` (NEW in v0.7.1)
`create_simulation_from_config(config) -> Simulation` — builds warehouse via
`decision.layout.create_warehouse_for_experiment()`, builds task generator via
`create_task_generator()`, builds robots, configs, path planner, scheduler;
injects conflict manager via `sim.set_conflict_manager()`.

experiment/recorder.py (UPDATED in v0.7.2)

`MetricsRecorder(run_dir: str, run_id: str)`.
Public: `record(snapshot: dict)`, `close()`.
Opens `timeseries.csv` / `events.csv`, writes headers; flushes every 100
records; `close()` flushes and closes.
Receives primitive snapshots only (ints/floats/strings); never stores live
object references.
`record()` writes one time-series row, then infers task/robot events by
diffing previous-tick primitive state (`_prev_metrics`, `_prev_tasks`,
`_prev_robots`).
Completed/failed tasks are dropped from `_prev_tasks` only after being seen
Completed/Failed. `robot_unblocked` suppressed when caused by
failed/repairing/charging/waiting transitions.
As of v0.7.2, `robot_blocked` events write `{"x": ..., "y": ...}` JSON into
the `details` column (the cell occupied when blocking started).

experiment/runner.py (UPDATED in v0.7.2)

`ExperimentRunner(base_dir: str = "data/runs")`.
Properties: `is_active`, `finished`.
`start(config, sim_factory) -> run_id` — creates run dir, saves config,
creates recorder, `sim.resume()`, starts daemon thread; RuntimeError if a run
is active.
`stop(reason="stopped_by_user")` — sets stop reason, `sim.stop()`, joins.
`get_state() -> dict` — `{active, finished, runId, runDir, stopReason, paused, tick, fastMode}`.
`get_summary() -> dict | None` — in-memory or reads summary.json.

Internal:
`_run()` — loop while not `sim._stop_event`; skip while `sim.is_paused`;
under `sim._lock`: `_tick()`, `_snapshot()`, `recorder.record()`, stop
evaluation; pacing: fast_mode -> `time.sleep(0)` every 500 ticks, else
`time.sleep(sim._tick_interval)`; exceptions set
`stop_reason = "error: ..."`.
`_snapshot()` — primitive extraction of metrics counters, per-task
(id/status/assigned_robot_id/task_type/pickup/dropoff/created_at/completed_at),
per-robot (id/status/mode/x/y/blocked_ticks/replanning/battery).
`_evaluate_stop_condition()` — fixed_ticks: tick >= max_ticks; workload:
completed >= target_tasks, else tick >= max_ticks.
`_finalize()` — closes recorder, computes and writes summary.json once.

analysis/loader.py (NEW in v0.5.0)

`DEFAULT_RUNS_DIR = "data/runs"`.
`RunData` dataclass: `run_id`, `run_dir`, `config`, `summary`, `timeseries`,
`events` (pandas DataFrames).
`list_runs(base_dir)` — newest first, `{run_id, run_dir, config, summary}`.
`load_run(run_id, base_dir) -> RunData` — FileNotFoundError if missing.

analysis/metrics.py (NEW in v0.5.0)

`ensure_derived_timeseries(df)` — adds `tick` (if absent),
`tasks_completed_total` (cumsum if absent), `throughput`
(= tasks_completed_this_tick), `throughput_rolling_50`,
`throughput_rolling_100`; never alters recorded columns.
`percentile_summary(series)` — `{count, mean, median, p90, p95, max}`.
`task_lifecycle_from_events(events)` — per task `created_tick`,
`first_assigned_tick`, `completed_tick`, `failed_tick`, `waiting_time`
(= first_assigned - created), `cycle_time` (= completed - created).
`blocked_episodes_from_events(events, final_tick=None)` — pairs
robot_blocked/robot_unblocked into episodes
`{robot_id, start_tick, end_tick, duration_ticks, open_at_end}`; unclosed
episodes censored at final_tick.
`event_counts(events)`, `utilization_from_summary(summary)`,
`robot_count_from_run(run)`, `distribution_stats(run)` (percentile summaries
for task_waiting_time, task_cycle_time, robot_blocked_episode_ticks,
system_active_fraction, robot_utilization).

analysis/web.py (NEW in v0.5.0)

`RUN_ID_PATTERN = ^[A-Za-z0-9_\-]+$`; invalid ids raise `AnalysisApiError`
(mapped to 404 by Flask routes).
`DEFAULT_MAX_POINTS = 2000`, `MAX_POINTS_LIMIT = 5000` (clamped, min 50).
`_sanitize()` — JSON safety; NaN/Inf become null; numpy scalars converted.
`_downsample(df, column, max_points)` — bucket-mean to `[[tick, value], ...]`;
raw points when under the limit.
`_histogram(series, bins)` — `{bin_centers, bin_edges, counts}`.

Payload builders:
`list_runs_payload(base_dir)` -> `{runs: [...]}`.
`get_run_summary(run_id, base_dir)` -> `{run_id, config, summary}`.
`get_run_series(run_id, columns, base_dir, max_points)` ->
`{run_id, max_points, series: [{name, points}]}`.
`get_compare_series(run_ids, column, base_dir, max_points)` ->
`{column, max_points, runs: [{run_id, points}]}`; skips missing runs/columns.
`get_run_distributions(run_id, base_dir, bins)` (bins clamped 10..100) ->
`{run_id, stats, histograms: {task_waiting_time, task_cycle_time, robot_blocked_episode_ticks}, robot_utilization: [{robot_id, utilization}] | null}`.

Full CSVs are never sent to the browser; only downsampled payloads.

Flask Layer (UPDATED in v0.5.0)

`app.py`

Important functions:
`create_app(base_data_dir: str = "data/runs", start_simulation: bool = False) -> Flask`
module-level `app = create_app()`

Holder pattern (replaces v0.4 closure wiring):

holder = { "simulation": <Simulation>, "runner": <ExperimentRunner | None> }

All state routes read `holder["simulation"]`. `create_default_simulation()`
is replaced by `create_simulation_from_config(ExperimentConfig.default())`.

Routes (legacy semantics preserved):
`GET /`
`GET /api/state` — v0.4 payload plus top-level `experiment` key:
runner present -> `runner.get_state()`; else
`{active: false, finished: false, runId: null, stopReason: null, fastMode: false}`.
`POST /api/pause`
`POST /api/resume`
`POST /api/reset` — stops active runner with `reset_by_user`, recreates
default simulation.

Routes (v0.5 experiment lifecycle):
`POST /api/experiment/start` — 409 if a run is active; 400 on validation or
spawn errors; body is ExperimentConfig JSON (merged over defaults); returns
`{runId}`; swaps holder simulation/runner.
`GET /api/experiment/state`
`POST /api/experiment/stop`
`GET /api/experiment/summary` — 404 without runner; 409 not finished.

Routes (v0.5 analysis API):
`GET /api/runs`
`DELETE /api/runs/<run_id>` — validates id, removes dir, `{success, runId}`;
404 if missing.
`GET /api/runs/compare/series?runs=a,b&column=...&max_points=...`
`GET /api/runs/<run_id>/summary`
`GET /api/runs/<run_id>/series?columns=a,b&max_points=...`
`GET /api/runs/<run_id>/distributions?bins=...`

Important behavior:
Routes stay thin; business logic lives in `simulation/`, `experiment/`,
`analysis/`.
The raw `data/runs` directory is NOT served statically.

CLI Layer (UPDATED in v0.7.2)

`benchmark.py`

Purpose:
Runs a headless synchronous benchmark.
Does not start Flask.
Does not poll.
Directly calls `sim._tick()` under the simulation lock.
As of v0.7.2, records every run through `ExperimentRunner` to
`data/runs/<run_id>/`. Benchmark wall-clock times are no longer comparable
to pre-v0.7.2 runs due to recording overhead.

Existing arguments:
`--robots`, `--block-replan`, `--cooldown`, `--target`, `--seed`

v0.4 arguments:
`--max-ticks`, `--battery-capacity`, `--empty-move-energy`, `--loaded-move-energy`,
`--critical-battery`, `--opportunistic-charge-threshold`, `--idle-opportunistic-ticks`,
`--battery-safety-margin`, `--charger-capacity`, `--charge-duration-ticks`,
`--failure-enabled`, `--mtbf-ticks`, `--mttr-ticks`

v0.5 arguments:
`--spawn` (choices: `seeded`, `legacy`; default: `seeded`), `--display-name`

v0.6 arguments:
`--path-planner` (choices: `bfs`, `astar`, `weighted_astar`; default: `bfs`)
`--scheduler` (choices: `baseline`, `priority`, `fifo`, `total_cost`, `auction`; default: `baseline`)
`--conflict-manager` (choices: `local_yield`, `zone_locks`, `priority_reservation`; default: `local_yield`)

`optimize_optuna.py`

Purpose: Uses Optuna to optimize simulation parameters.

Decision CLI (UPDATED in v0.7.2):

python -m decision.study --config <study_config.json>
python -m decision.report --study-dir <study_dir>
python -m decision.report --run-id <run_id>
python -m decision.spatial --run-id <run_id>

JSON API

`GET /api/state`

Returns the v0.4 payload (below) plus the v0.5 top-level `experiment` key
described in the Flask Layer section.

(Rest of JSON API examples unchanged from v0.6.0)

Frontend JavaScript (UPDATED in v0.6.0)

(Rest of Frontend JS unchanged from v0.6.0)

CSS Classes (UPDATED in v0.6.0)

(Rest of CSS unchanged from v0.6.0)

UI / Visualization (UPDATED in v0.6.0)

(Rest of UI unchanged from v0.6.0)

Deployment Notes (v0.5.0)

Serve with `gunicorn app:app` (or platform equivalent); never the Flask dev
server when hosted.
`data/runs/` must be on persistent storage; ephemeral filesystems lose
experiments on restart.
ECharts may load from CDN or be vendored at
`static/vendor/echarts.min.js` for offline/air-gapped hosts.
If the public can start experiments, add authentication/rate limiting;
experiments consume CPU and disk. Fast mode pins one core for its duration.

Extension Points

Preserved v0.4 extension points (intentionally not or only partially
implemented):
`INTERSECTION` -> formal intersection traffic control.
`MAIN_AISLE` -> priority routing or speed changes.
`PACKING` -> packing queue or processing delay.
`RECEIVING` -> inbound task generation coupling.
`SHIPPING` -> outbound task completion coupling.
`EMPTY` -> dynamic obstacles or editor placement.
`BUFFER` -> QC delay or put-away scheduling.
`PICK_STATION` -> pick processing time or queueing.
`CONSOLIDATION` -> order merge logic.
`STAGING` -> carrier lane assignment.
Physical load handoff -> v0.4 uses logical task recovery, not physical
pallet transfer.
Predictive maintenance -> not implemented.

New v0.5 extension points:
SQLite/Parquet storage if CSV experiments grow large.
Explicit in-simulation event hooks to replace tick-resolution inference.
Per-robot time-series utilization/blocked columns if summary-level
distributions become insufficient.
Server-side analysis caching if hosted traffic grows.

New v0.6 extension points:
Additional `PathPlanner` implementations (D* Lite, LPA*, congestion-aware
A*) plug in through `ExperimentConfig.path_planner` and
`create_path_planner_from_name`.
Additional `Scheduler` implementations (Hungarian assignment, rolling
horizon optimizer, reinforcement learning) plug in through
`ExperimentConfig.scheduler` and `create_scheduler_from_name`.
Additional `ConflictManager` implementations (one-way aisle policies,
intersection signal control, full CBS/ECBS) plug in through
`ExperimentConfig.conflict_manager` and
`create_conflict_manager_from_name`.
Edge reservations in `ReservationTable` to prevent swap collisions.
Conflict manager diagnostics could be persisted to summary.json for
cross-run comparison.

New v0.7.1 extension points:
Persist Cost KPIs into `summary.json` or a dedicated `decision.json` artifact.
Add directional aisle constraints through a dedicated `ConflictManager`.
Add demand-profile validation against layout location availability before run start.
Add study-level demand factors and layout factors to DoE configs.
Add Monte Carlo runner in `decision/monte_carlo.py`.
Add sensitivity analysis in `decision/sensitivity.py`.
Add optimization layer in `decision/optimizer.py`.

New v0.7.2 extension points:
Frontend heatmap overlay of spatial bottlenecks on the warehouse layout
(post-run visualization, fed by `compute_spatial_blockage`).
Spatial payload builder in `analysis/web.py` and a
`GET /api/runs/<run_id>/spatial` route once the backend is proven.
Cell-type labeling of bottleneck cells via reconstructed layout presets.