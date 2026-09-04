# API Surface

This document lists the important names used by the warehouse simulator.
If code and documentation disagree, the code is the source of truth, but this
file should be updated immediately.

## Project State

Project Name: warehouse_simulator
Current Version: v0.8.1
Git Tag: v0.8.1
Previous Documented Version: v0.7.2
Python Version: Python 3.13+ recommended. Pin Python 3.13 if dependency wheels are unstable on newer interpreters.
Dependencies: Flask, pandas, numpy, ECharts frontend, Optuna required for decision.optimizer and decision.multiobjective, pytest for development/testing
Run Command: `python app.py`
Production: `gunicorn app:app`, never the Flask development server when hosted

## Where The Project Is Now

v0.8.1 is an Optimization and Robustness Layer built on top of the unchanged
v0.8.0 Uncertainty and Risk Analysis layer, the unchanged v0.7.x Decision and
Realistic Scenario layers, the unchanged v0.6.0 algorithm plugin layer, the
unchanged v0.5.0 experimentation/recording/storage/analysis infrastructure,
and the unchanged v0.4.0 battery/charging/failure simulation core.

v0.8.1 adds:

- Business Optimization: `decision/optimizer.py`.
  Optuna-based single-objective optimization with constraint handling.
- Multi-Objective Optimization: `decision/multiobjective.py`.
  NSGA-II Pareto front generation for tradeoffs such as cost versus p95 cycle time.
- Stochastic Robustness Verification: `decision/robustness.py`.
  Multi-replica verification of candidate configurations with constraint pass probability.

v0.8.0 adds:

- Monte Carlo Runner: `decision/monte_carlo.py`.
  Executes N identical scenarios with varying seeds.
  Calculates confidence intervals, p5/p95 KPIs, and SLA-violation probability.
- Sensitivity Analysis: `decision/sensitivity.py`.
  One-at-a-time parameter variation around a baseline.
  Outputs tornado data for `cost_per_task` and `p95_cycle_time`.

v0.7.2 adds:

- Spatial bottleneck analysis: blockage onset coordinates are recorded in
  `events.csv` and aggregated into per-cell bottleneck statistics from saved
  artifacts only.
- Recorded benchmarks: `benchmark.py` records every run through
  `ExperimentRunner` into `data/runs/<run_id>/`.
- Single-run engineering reports: `decision/report.py` can report one run
  without a study, writing to `data/reports/`.

v0.7.1 adds:

- Business KPIs: Cost KPIs computed from immutable saved run artifacts.
- Batch experimentation / Design of Experiments: Factorial study runner.
- Engineering reporting: Markdown study reports generated from saved study results.
- Dynamic demand profiles: Legacy synthetic demand preserved; uniform, rate
  schedules, and deterministic CSV/order events added.
- Configurable layout presets: Default warehouse preserved; JSON layout
  definitions and preset layouts added.

The v0.6.0 plugin layer remains unchanged:

- Path Planning: `PathPlanner`, `BFSPathPlanner`, `AStarPathPlanner`.
- Scheduling: `Scheduler`, `CostBasedScheduler`, `PriorityScheduler`,
  `FIFOScheduler`, `TotalCostScheduler`, `AuctionScheduler`.
- Conflict Resolution: `ConflictManager`, `LocalYieldConflictManager`,
  `ZoneLockConflictManager`, `PrioritizedReservationConflictManager`.

The v0.5 experimentation layer is unchanged:

- `experiment/config.py`
- `experiment/factory.py`
- `experiment/recorder.py`
- `experiment/runner.py`
- `data/runs/<run_id>/` immutable storage
- `analysis/loader.py`
- `analysis/metrics.py`
- `analysis/web.py`

The v0.4 battery/charging/failure simulation core is unchanged.
The v0.3.1 traffic model is preserved as the `local_yield` baseline.

v0.5 separates six responsibilities:

- Simulation (`simulation/`) — v0.4 core with v0.6 plugin injection points.
- Experiment configuration (`experiment/config.py`) — authoritative run parameters.
- Metrics recorder (`experiment/recorder.py`) — observes, never modifies.
- Experiment runner (`experiment/runner.py`) — lifecycle, stopping, saving.
- Data storage (`data/runs/<run_id>/`) — immutable per-run artifacts.
- Visualization/analysis (`analysis/` + frontend) — reads saved data only.

The simulation does not depend on plotting.
The plotting system never needs live simulation objects.
A completed experiment is fully reproducible and analyzable from its saved files.

The UI is a multi-stage workflow, not one dashboard:

Setup -> Run live or Fast headless -> Results -> Experiments ->
Visualization -> Analysis -> Compare

View transitions are a client-side state machine; the backend never redirects.

v0.7.x and v0.8.x decision modules may execute new experiments through
`ExperimentRunner`, but they must never modify existing run artifacts.
Derived decision artifacts are stored in their own directories under `data/`.

## Breaking Changes / Changes From v0.3.1 (v0.4.0)

Core Architecture

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

Data Models

- `Robot` gained `RobotMode` and v0.4 battery/charging/failure fields.
- `Task` gained `LoadState`, `INTERRUPTED` status, interruption count,
  last-assigned robot, and resume-location fields.
- `Metrics` gained battery, charging, waiting-breakdown, interruption,
  failure, and congestion-related fields/methods.

Frontend / CLI

- `benchmark.py` accepts v0.4 battery, charging, and failure parameters.
- `optimize_optuna.py` accepts fixed v0.4 parameters and optional
  `--search-v04` mode.
- Frontend supports `Interrupted` tasks, robot mode/battery tooltips, and
  v0.4 dashboard metrics.
- CSS adds styles for interrupted tasks and robot battery/charging/failure states.

## Breaking Changes / Changes From v0.4.0 (v0.5.0)

- Added `experiment/` package: `config.py`, `factory.py`, `recorder.py`,
  `runner.py`.
- Added `analysis/` package: `loader.py`, `metrics.py`, `web.py`.
- `app.py` uses a mutable `holder = {"simulation": ..., "runner": ...}`; the
  v0.4 closure-based single-simulation wiring is gone.
- `create_default_simulation()` replaced by
  `create_simulation_from_config(ExperimentConfig.default())`.
- Robot creation is dynamic and seeded; old hardcoded 13-position list gone.
- No robot-count cap beyond available passable cells.
- `ExperimentConfig` gained `display_name`, label only, and `fast_mode`,
  pacing only; fast_mode never affects results.
- New routes: experiment lifecycle, run deletion, and analysis JSON API.
- Frontend rewritten: view state machine, `MultiSelect` component, ECharts
  charts, experiment delete, legend, fast-run progress view.
- CSS rewritten: dark theme, flat borderless tiles, glow-only task/location
  highlights, square robots.
- New persistent storage layout under `data/runs/`.
- `benchmark.py` and `optimize_optuna.py` unchanged.

## Breaking Changes / Changes From v0.5.0 (v0.6.0)

Core Architecture

- `simulation/pathfinding.py` UPDATED: added `PathPlanner` protocol,
  `BFSPathPlanner`, and `AStarPathPlanner`. `find_shortest_path()` preserved
  as backward-compatible wrapper delegating to `BFSPathPlanner`.
- `simulation/scheduler.py` UPDATED: added `PriorityScheduler`,
  `FIFOScheduler`, `TotalCostScheduler`, and `AuctionScheduler` alongside
  existing `CostBasedScheduler`. All implement the `Scheduler` protocol.
- Added `simulation/conflict.py` containing `ConflictManager` protocol,
  `LocalYieldConflictManager`, `ZoneLockConflictManager`, and
  `PrioritizedReservationConflictManager`.
- Added `simulation/reservations.py` containing `ReservationTable`.
- `Simulation` constructor gained keyword-only `path_planner` argument.
- `Simulation` gained `set_conflict_manager()` public method.
- `Simulation` gained `_conflict_manager` internal state, initialized to
  `LocalYieldConflictManager(self)`.
- `Simulation._tick()` now calls `self._conflict_manager.tick()` before
  `_advance_robots()`.
- `Simulation._advance_robots()` now calls
  `self._conflict_manager.allow_step()` before the occupied-cell check.
- `Simulation._congestion_snapshot()` reads
  `self._conflict_manager.active_conflicts`.
- All conflict-related private methods moved from `Simulation` into
  `LocalYieldConflictManager`.

Experiment Configuration

- `ExperimentConfig` gained `path_planner: str = "bfs"`.
- `ExperimentConfig` gained `conflict_manager: str = "local_yield"`.
- `ExperimentConfig.__post_init__` validates `path_planner` against
  `PATH_PLANNER_CHOICES` and `conflict_manager` against
  `CONFLICT_MANAGER_CHOICES`.

Factory

- `experiment/factory.py` gained `create_path_planner_from_name(name)`.
- `experiment/factory.py` gained
  `create_scheduler_from_name(name, path_planner)`.
- `experiment/factory.py` gained
  `create_conflict_manager_from_name(name, sim)`.
- `experiment/factory.py` gained `create_path_planner(config)`.
- `experiment/factory.py` gained `create_scheduler(config, path_planner)`.
- `experiment/factory.py` gained `create_conflict_manager(config, sim)`.
- `create_simulation_from_config()` now creates and injects the configured
  scheduler, path planner, and conflict manager.

CLI

- `benchmark.py` gained `--path-planner`, choices `bfs`, `astar`,
  `weighted_astar`, default `bfs`.
- `benchmark.py` gained `--scheduler`, choices `baseline`, `priority`,
  `fifo`, `total_cost`, `auction`, default `baseline`.
- `benchmark.py` gained `--conflict-manager`, choices `local_yield`,
  `zone_locks`, `priority_reservation`, default `local_yield`.
- `benchmark.py` prints active path planner, scheduler, and conflict manager
  class names before running.
- `benchmark.py` prints conflict manager diagnostics after running.

Frontend

- Setup view gained three algorithm dropdowns:
  `cfg-path-planner`, `cfg-scheduler`, `cfg-conflict-manager`.
- Setup view uses `.setup-grid` two-column card layout.
- Run view restructured: `.run-layout` flex container with `.run-main`
  warehouse/legend and `.run-sidebar` controls/dashboard/task list.
- Pause/Resume/Reset buttons moved to `.run-controls` at top of sidebar.
- `readExperimentConfig()` includes `path_planner`, `scheduler`, and
  `conflict_manager`.

CSS

- Added `.setup-grid`, `.setup-grid .card`, `.setup-grid .card.full-width`.
- Added `.run-layout`, `.run-main`, `.run-sidebar`, `.run-controls`.
- Added responsive breakpoint at 1100px.

## Breaking Changes / Changes From v0.6.0 (v0.7.1)

Decision Layer

- Added `decision/` package.
- `decision/cost.py`: `CostConfig` dataclass for run-level business costs.
- `decision/kpis.py`: `CostKPIs`, `compute_cost_kpis()`,
  `compute_cost_kpis_for_run_id()`. Reads saved artifacts only.
- `decision/study.py`: `StudyConfig`, `StudyRunner`. Executes factorial DoE
  matrices and outputs `data/studies/<study_id>/results.csv`.
- `decision/report.py`: `generate_report()`. Generates Markdown engineering
  reports from study results.
- `decision/demand.py`: `DemandConfig`, `DemandModel`, `DemandTaskGenerator`.
  Supports `legacy`, `uniform`, `rate_schedule`, and `csv_orders`.
- `decision/layout.py`: `LayoutConfig`, `PRESET_LAYOUTS`. Supports `default`,
  `high_density`, and `one_way_aisles`.

Experiment Configuration

- `ExperimentConfig` gained additive v0.7.1 fields with backward-compatible defaults:
  `demand_mode`, `demand_rate_per_tick`, `demand_task_weights`,
  `demand_segments`, `demand_csv_path`, `demand_events`,
  `layout_preset`, `layout_file`.
- `ExperimentConfig.__post_init__` validates demand and layout fields.

Factory

- `experiment/factory.py` gained `create_task_generator(config, warehouse)`.
- `create_simulation_from_config()` now builds the warehouse using
  `decision.layout.create_warehouse_for_experiment()` and the task generator
  using `create_task_generator()`. Default behavior remains unchanged.

Storage Format

- Run storage structure is unchanged.
- `config.json` gained the new v0.7.1 keys.
- New study storage layout added under `data/studies/<study_id>/`.

## Breaking Changes / Changes From v0.7.1 (v0.7.2)

Experiment Layer

- `ExperimentRunner._snapshot()` now extracts per-robot `x` and `y`.
- `MetricsRecorder` writes `{"x": ..., "y": ...}` JSON into the `details`
  column of `robot_blocked` events.
- `events.csv` schema is unchanged.

Decision Layer

- Added `decision/spatial.py`: `SpatialCellLoad`, `SpatialBlockageResult`,
  `compute_spatial_blockage()`, `top_bottleneck_cells()`, and internal
  `_pair_blocked_episodes()`.
- `decision/report.py` gained `generate_run_report(run_id, base_dir=None)`.
- Single-run reports are written to `data/reports/<run_id>_report.md`, never
  inside `data/runs/`.
- Study reports gained a Spatial Bottleneck Analysis section.
- `python -m decision.report` gained `--run-id`, mutually exclusive with
  `--study-dir`, and `--base-dir`.

Decision CLI

- Added `python -m decision.spatial --run-id <run_id>` with options
  `--base-dir`, `--top`, `--by {blocked_ticks,blocked_events}`, and `--json`.

CLI Layer

- `benchmark.py` now records every run through `ExperimentRunner`.
- Benchmark wall-clock times are no longer comparable to pre-v0.7.2 runs due
  to recording overhead.

Storage

- Run storage structure is unchanged.
- Pre-v0.7.2 runs have empty `details` on `robot_blocked` rows.
- Spatial analysis reports them with coverage 0.0.
- Added `data/reports/` for single-run Markdown reports.
- `results.csv` carries `run_id` so each study row traces back to
  `data/runs/<run_id>/`.

## Breaking Changes / Changes From v0.7.2 (v0.8.0)

Decision Layer

- Added `decision/monte_carlo.py`.
- Added `decision/sensitivity.py`.

Monte Carlo:

- Executes N identical experiment configurations with different seeds.
- Calculates confidence intervals, p5/p95 KPIs, and SLA violation statistics.
- Writes derived artifacts to `data/monte_carlo/<mc_id>/`.
- Each trial writes a normal immutable run artifact to `data/runs/<run_id>/`.

Sensitivity:

- Performs one-at-a-time parameter variation around a baseline configuration.
- Uses multiple replications per factor level.
- Writes `results.csv`, `tornado.csv`, and `summary.json` to
  `data/sensitivity/<study_id>/`.
- Each non-reused trial writes a normal immutable run artifact to
  `data/runs/<run_id>/`.

No simulation core changes.
No ExperimentConfig schema changes.
No frontend changes.

## Breaking Changes / Changes From v0.8.0 (v0.8.1)

Decision Layer

- Added `decision/optimizer.py`.
- Added `decision/multiobjective.py`.
- Added `decision/robustness.py`.

Single-objective optimization:

- Optuna TPESampler.
- Constraint handling through Optuna `constraints_func`.
- Explicit feasible/infeasible reporting.
- Writes `data/optimizations/<opt_id>/summary.json`.

Multi-objective optimization:

- Optuna NSGAIISampler.
- Pareto front extraction from feasible trials.
- Writes `data/multiobjective/<study_id>/summary.json`, `trials.json`, and
  `pareto.csv`.

Robustness verification:

- Multi-replica candidate verification.
- Calculates `constraint_pass_probability`.
- Recommends candidates only when constraint pass probability meets
  `min_pass_probability`.
- Writes `data/robustness/<robust_id>/results.csv` and `summary.json`.

No simulation core changes.
No ExperimentConfig schema changes.
No frontend changes.
Optuna becomes required for optimization modules.

## Important Code Default Note

The actual v0.3.1 code defaults are:

- blocked_replan_seconds = 0.7
- replan_cooldown_ticks = 7

Older documentation may mention `0.9` and `2`. The code defaults are the
source of truth.

## Coordinate System

Coordinates are `(x, y)`.
`x` increases to the right.
`y` increases downward.
Origin is the top-left corner.

## Naming Rules

Python

- Classes use `PascalCase`.
- Functions and variables use `snake_case`.
- Private methods start with `_`.
- Enum members use `UPPER_SNAKE_CASE`.

Stored Experiment Config

- Stored `config.json` keys use `snake_case` because they map directly to
  `ExperimentConfig` fields.

Live Frontend JSON API

- Live `/api/state` and related frontend payloads use the established
  camelCase keys from v0.4/v0.5/v0.6.

JavaScript

- Functions and variables use `camelCase`.
- DOM element variables usually end with `El`.

## Python Modules

### `simulation/config.py`, NEW in v0.4.0

Configuration dataclasses for v0.4 features.

#### `BatteryConfig`

```python
@dataclass(frozen=True)
class BatteryConfig
```

Fields:

- `capacity: float = 100.0`
- `empty_move_energy: float = 0.35`
- `loaded_move_energy: float = 0.5`
- `critical_battery: float = 15.0`
- `opportunistic_charge_threshold: float = 30.0`
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
- `opportunistic_charge_threshold` allows idle robots to charge after the idle threshold.
- `safety_margin` is added to estimated remaining task energy during feasibility checks.
- `empty_battery_recovery_ticks` is the minimum downtime when battery reaches zero.

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

### `simulation/charging.py`, NEW in v0.4.0

Finite-capacity charging resource model.

#### `ChargingStation`

```python
@dataclass
class ChargingStation
```

Fields:

- `capacity: int`
- `charge_duration_ticks: int`
- `active: dict[str, int]` — robot_id -> remaining charging ticks.
- `active_cells: dict[str, tuple[int, int]]` — robot_id -> charging cell.
- `reserved_cells: dict[str, tuple[int, int]]` — robot_id -> reserved cell.
- `waiting: set[str]` — robot ids waiting for charger capacity.

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

### `simulation/warehouse.py`

#### `CellType`

```python
class CellType(str, Enum)
```

Members:

`EMPTY`, `SHELF`, `AISLE`, `MAIN_AISLE`, `PACKING`, `RECEIVING`,
`SHIPPING`, `CHARGING`, `INTERSECTION`, `BUFFER`, `PICK_STATION`,
`CONSOLIDATION`, `STAGING`, `MAINTENANCE`

Values should be the same as member names:

- CellType.EMPTY.value == "EMPTY"
- CellType.SHELF.value == "SHELF"
- CellType.CHARGING.value == "CHARGING"
- CellType.MAINTENANCE.value == "MAINTENANCE"

Important:

- Enum values and layout symbol keys must not contain trailing spaces.
- Correct: `"EMPTY"`, not `"EMPTY "`.
- Correct: `"."`, not `". "`.

#### `LAYOUT_SYMBOLS`

```python
LAYOUT_SYMBOLS: dict[str, CellType]
```

Supported layout symbols:

- `.` -> `EMPTY`
- `E` -> `EMPTY`
- `#` -> `SHELF`
- `a` -> `AISLE`
- `M` -> `MAIN_AISLE`
- `P` -> `PACKING`
- `R` -> `RECEIVING`
- `S` -> `SHIPPING`
- `C` -> `CHARGING`
- `I` -> `INTERSECTION`
- `B` -> `BUFFER`
- `K` -> `PICK_STATION`
- `O` -> `CONSOLIDATION`
- `G` -> `STAGING`
- `X` -> `MAINTENANCE`

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

### `simulation/robot.py`, UPDATED in v0.4.0

#### `RobotStatus`

```python
class RobotStatus(str, Enum)
```

Members:

- `IDLE = "Idle"`
- `MOVING = "Moving"`

#### `RobotMode`, NEW in v0.4.0

```python
class RobotMode(str, Enum)
```

Members:

`IDLE`, `MOVING`, `TO_CHARGER`, `WAITING_FOR_CHARGER`, `CHARGING`,
`FAILED`, `REPAIRING`

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

### `simulation/task.py`, UPDATED in v0.4.0

#### `TaskType`

```python
class TaskType(str, Enum)
```

Members: `PUTAWAY`, `PICK`, `PACK`, `SHIP`, `LEGACY`

#### `TaskStatus`

```python
class TaskStatus(str, Enum)
```

Members:

- `PENDING = "Pending"`
- `ASSIGNED = "Assigned"`
- `COMPLETED = "Completed"`
- `FAILED = "Failed"`
- `INTERRUPTED = "Interrupted"`, NEW in v0.4.0

#### `TaskPhase`

```python
class TaskPhase(str, Enum)
```

Members:

- `TO_PICKUP = "To pickup"`
- `TO_DROPOFF = "To dropoff"`
- `DONE = "Done"`

#### `LoadState`, NEW in v0.4.0

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

- Generates tasks during the simulation instead of seeding all work at startup.
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

### `simulation/pathfinding.py`, UPDATED in v0.6.0

#### `PathPlanner`, NEW in v0.6.0

```python
class PathPlanner(Protocol)
```

Method:

- `find_path(warehouse, start, goal, blocked_cells=None) -> list[tuple[int, int]] | None`

Return meaning:

- `[]` — already at the goal.
- `[...]` — path cells after `start`.
- `None` — no path found.

#### `BFSPathPlanner`, NEW in v0.6.0

```python
class BFSPathPlanner
```

Implements `PathPlanner`. Uses BFS. Returns shortest paths. This is the
default planner and produces identical results to the v0.5
`find_shortest_path`.

#### `AStarPathPlanner`, NEW in v0.6.0

```python
class AStarPathPlanner
```

Constructor: `AStarPathPlanner(weight: float = 1.0)`

Implements `PathPlanner`. Uses A* with Manhattan heuristic.

- `weight = 1.0`: Standard A*. On a uniform 4-connected grid, returns
  shortest paths like BFS, but may choose a different shortest path when
  ties exist.
- `weight > 1.0`: Weighted A*. Faster search, but paths may be suboptimal.

#### `find_shortest_path`, preserved

```python
find_shortest_path(
    warehouse: Warehouse,
    start: tuple[int, int],
    goal: tuple[int, int],
    blocked_cells: Iterable[tuple[int, int]] | None = None,
) -> list[tuple[int, int]] | None
```

Backward-compatible wrapper. Delegates to a module-level `BFSPathPlanner`
instance. Existing modules that still import `find_shortest_path` will keep
working. New code should use an injected `PathPlanner` instead.

### `simulation/scheduler.py`, UPDATED in v0.6.0

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

Baseline scheduler. Chooses the idle robot with the shortest feasible path to
each pending task pickup. Processes tasks by `(-priority, created_at, id)`.
Constructor accepts optional `path_planner` keyword argument. Defaults to
`BFSPathPlanner()`.

#### `PriorityScheduler`, NEW in v0.6.0

```python
class PriorityScheduler
```

Nearest-pickup dispatcher with correct priority ordering. Processes tasks by
`(priority, created_at, id)` where lower `priority` value = higher urgency.
For each task, assigns the nearest feasible robot to the pickup.

#### `FIFOScheduler`, NEW in v0.6.0

```python
class FIFOScheduler
```

Nearest-pickup dispatcher that processes oldest tasks first. Processes tasks
by `(created_at, priority, id)`. For each task, assigns the nearest feasible
robot to the pickup.

#### `TotalCostScheduler`, NEW in v0.6.0

```python
class TotalCostScheduler
```

Battery/energy-aware scheduler. For each task, computes the estimated total
cost as `distance_to_pickup + distance_pickup_to_dropoff`. Assigns the robot
with the lowest total cost. Constructor accepts optional `path_planner`,
`empty_move_energy`, `loaded_move_energy`, `safety_margin`, and
`critical_battery` keyword arguments.

#### `AuctionScheduler`, NEW in v0.6.0

```python
class AuctionScheduler
```

Centralized first-price auction approximation. Each remaining task receives
bids from each remaining robot. The lowest total bid wins. Bid cost is
`distance_to_pickup + distance_pickup_to_dropoff`. Iterates until all tasks
or robots are exhausted.

### `simulation/conflict.py`, NEW in v0.6.0

#### `ConflictManager`

```python
class ConflictManager(Protocol)
```

Methods:

- `handle_blocked_robot(robot, next_cell) -> None`
- `advance_replanning_robot(robot, occupied) -> None`
- `release_conflict(robot) -> None`
- `clear_conflicts_for_robot(robot) -> None`
- `reset() -> None`
- `tick(current_tick: int, robots: list[Robot]) -> None`
- `allow_step(robot, next_cell, occupied) -> bool`
- `release_robot(robot_id: str) -> None`

Property:

- `active_conflicts -> int`

#### `LocalYieldConflictManager`

```python
class LocalYieldConflictManager
```

Constructor: `LocalYieldConflictManager(sim: Simulation)`

Baseline reactive conflict manager. Contains all the v0.3.1
traffic/conflict resolution logic previously in `Simulation`. `tick()` and
`allow_step()` are no-ops. `release_robot()` is a no-op.

Important behavior:

- Preserves the v0.3.1 local deadlock-recovery mechanism exactly.
- `handle_blocked_robot()`, `advance_replanning_robot()`,
  `release_conflict()`, `clear_conflicts_for_robot()` implement the
  existing yield logic.
- `_make_robot_yield()`, `_select_yielding_robot()`, `_yield_score()`,
  `_can_yield()`, `_choose_yield_step()` are private helpers.
- `_complete_yield()` resumes normal routing after a yield maneuver.

#### `ZoneLockConflictManager`, NEW in v0.6.0

```python
class ZoneLockConflictManager
```

Constructor: `ZoneLockConflictManager(sim: Simulation, lookahead: int = 2)`

Inherits from `LocalYieldConflictManager`. Adds proactive path-corridor zone
locks on top of the reactive local yield system.

Important behavior:

- `tick()` rebuilds zone locks from each robot's current path. Claims the
  next `lookahead` cells on each robot's path. Robots are sorted by
  `_yield_score()`; less willing to yield claims first.
- `allow_step()` denies a step if the target cell is locked by another robot,
  unless the robot has been blocked for too long. Starvation fallback:
  `blocked_ticks >= blocked_replan_threshold_ticks * 2`.
- Diagnostic counters: `denied_steps`, `locks_created`, `tick_calls`,
  `robots_with_paths`.
- Failed, repairing, and charging robots do not create claims.

#### `PrioritizedReservationConflictManager`, NEW in v0.6.0

```python
class PrioritizedReservationConflictManager
```

Constructor:
`PrioritizedReservationConflictManager(sim: Simulation, horizon: int = 32)`

Inherits from `LocalYieldConflictManager`. Adds approximate prioritized
reservation-based conflict management on top of the reactive local yield
system.

Important behavior:

- `tick()` rebuilds vertex reservations from each robot's current path using
  a `ReservationTable`. Robots are sorted by a priority score. Higher score
  reserves first.
- Priority score considers robot mode, task priority, loaded status, battery
  urgency, and blocked time.
- `allow_step()` denies a step if the target cell is reserved by another robot
  at the next tick, unless the robot has been blocked for too long.
  Starvation fallback: `blocked_ticks >= blocked_replan_threshold_ticks * 2`.
- Diagnostic counters: `denied_steps`, `reservations_created`, `tick_calls`,
  `robots_with_paths`.
- Failed, repairing, and charging robots do not create reservations.
- This is not full space-time MAPF. It is a practical proactive traffic
  manager for experimentation.

### `simulation/reservations.py`, NEW in v0.6.0

#### `ReservationTable`

```python
class ReservationTable
```

Simple vertex reservation table. Tracks which robot intends to occupy which
cell at which tick. Does not track edge reservations, so swap collisions are
not fully covered.

Fields:

- `_vertex_reservations: dict[tuple[int, int], dict[int, str]]`
  — cell -> tick -> robot_id.
- `_robot_reservations: dict[str, set[tuple[tuple[int, int], int]]]`
  — robot_id -> set of reserved (cell, tick) pairs.

Methods:

- `reset() -> None`
- `reserve(robot_id: str, cell: tuple[int, int], tick: int) -> bool`
- `owner(cell: tuple[int, int], tick: int) -> str | None`
- `is_free(cell: tuple[int, int], tick: int, robot_id: str) -> bool`
- `release_robot(robot_id: str) -> None`
- `prune(current_tick: int) -> None`

### `simulation/metrics.py`, UPDATED in v0.4.0

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

### `simulation/simulation.py`, UPDATED in v0.6.0

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
    path_planner: PathPlanner | None = None,
)
```

Public methods:

- `simulation.start() -> None`
- `simulation.pause() -> None`
- `simulation.resume() -> None`
- `simulation.reset() -> None`
- `simulation.stop() -> None`
- `simulation.get_state() -> dict[str, Any]`
- `simulation.set_conflict_manager(manager: ConflictManager) -> None`, NEW in v0.6.0

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

New v0.6:

- `simulation._path_planner` — injected `PathPlanner` instance. Defaults to
  `BFSPathPlanner()`.
- `simulation._conflict_manager` — injected `ConflictManager` instance.
  Defaults to `LocalYieldConflictManager(self)`.

Important behavior:

- `start()` starts the background simulation thread.
- `pause()` stops ticking but keeps state.
- `resume()` continues ticking.
- `reset()` restores robots and tasks to their initial state, clears conflict
  manager state via `self._conflict_manager.reset()`, clears dynamic resume
  locations, resets charging station state, resets failure RNG, and restores
  robot batteries/modes.
- `set_conflict_manager()` replaces the active conflict manager and rebinds
  its `_sim` reference.
- `get_state()` returns a JSON-serializable snapshot.
- `get_state()` should strip dynamic `RESUME-*` locations from the warehouse
  payload.
- `_tick()` runs failures/repairs, charging station progression, task
  generation, assignment, battery checks, opportunistic charging, conflict
  manager tick, robot movement, metrics, and pruning.
- `_advance_robots()` calls `self._conflict_manager.allow_step()` before the
  occupied-cell check. Replanning/yielding robots are NOT gated by
  `allow_step()` so deadlock escape still works.
- `_prune_old_tasks()` deletes completed/failed tasks whose `completed_at` is
  more than 100 ticks old. Interrupted tasks are not pruned.

## Traffic / Conflict Resolution Behavior

### v0.3.1 Local Yield, preserved as `local_yield`

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

### v0.6 Zone Locks, `zone_locks`

- Proactive path-corridor zone locks on top of reactive local yield.
- Each tick, `tick()` rebuilds zone locks from each robot's current path.
- Claims the next `lookahead` cells, default 2, on each robot's path.
- Robots are sorted by `_yield_score()`; less willing to yield claims first.
- `allow_step()` denies a step if the target cell is locked by another robot.
- Starvation fallback: if `blocked_ticks >= blocked_replan_threshold_ticks * 2`,
  the robot is allowed through regardless of locks.
- Failed, repairing, and charging robots do not create claims.
- Diagnostic counters: `denied_steps`, `locks_created`, `tick_calls`,
  `robots_with_paths`.

### v0.6 Priority Reservation, `priority_reservation`

- Approximate prioritized reservation-based conflict management on top of
  reactive local yield.
- Each tick, `tick()` rebuilds vertex reservations from each robot's current
  path using a `ReservationTable`.
- Robots are sorted by a priority score. Higher-priority robots reserve first.
- Priority score considers robot mode, task priority, loaded status, battery
  urgency, and blocked time.
- `allow_step()` denies a step if the target cell is reserved by another robot
  at the next tick.
- Starvation fallback: if `blocked_ticks >= blocked_replan_threshold_ticks * 2`,
  the robot is allowed through regardless of reservations.
- Failed, repairing, and charging robots do not create reservations.
- Diagnostic counters: `denied_steps`, `reservations_created`, `tick_calls`,
  `robots_with_paths`.
- This is not full space-time MAPF. It is a practical proactive traffic
  manager for experimentation.

## Battery / Charging / Failure Behavior, v0.4.0

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

If battery reaches zero:

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

## Decision Layer Modules, UPDATED in v0.8.1

### `decision/cost.py`

#### `CostConfig`

```python
@dataclass(frozen=True)
class CostConfig
```

Fields:

- `robot_opex_per_hour: float = 0.0`
- `charger_infra_cost_per_hour: float = 0.0`
- `downtime_cost_per_hour: float = 0.0`
- `sla_target_ticks: int | None = None`
- `sla_penalty_per_late_tick: float = 0.0`
- `currency: str = "USD"`

Important behavior:

- All monetary rates must be finite and >= 0.
- CapEx and Energy costs are intentionally excluded at the run level.
- `sla_target_ticks` is expressed in simulation ticks.

### `decision/kpis.py`

#### `CostKPIs`

```python
@dataclass(frozen=True)
class CostKPIs
```

Fields:

- `total_operating_cost: float`
- `cost_per_task: float | None`
- `sla_compliance_rate: float | None`
- `completed_tasks: int`
- `sla_evaluated_tasks: int`
- `late_tasks: int`
- `simulation_seconds: float`
- `currency: str`
- `cost_breakdown: dict[str, float]`

Functions:

- `compute_cost_kpis(run_data, cost_config) -> CostKPIs`
- `compute_cost_kpis_for_run_id(run_id, cost_config, base_dir=None) -> CostKPIs`

Important behavior:

- Reads saved artifacts only.
- Handles zero completed tasks.
- `cost_per_task` is None when `completed_tasks` is zero.
- `sla_compliance_rate` is None when no SLA-evaluated tasks exist.

### `decision/study.py`

Important names:

- `StudyConfig`
- `StudyRunner`

Important behavior:

- Executes factorial DoE matrices.
- Outputs `data/studies/<study_id>/results.csv`.
- `results.csv` carries a `run_id` column so each row traces back to
  `data/runs/<run_id>/` artifacts.
- Study execution writes normal immutable run artifacts for each experiment row.

CLI:

```bash
python -m decision.study --config <study_config.json>
```

### `decision/report.py`

Functions:

- `generate_report(study_dir: str | Path) -> Path`
- `generate_run_report(run_id: str, base_dir: str | None = None) -> Path`, NEW in v0.7.2

Important behavior:

- Generates Markdown engineering reports.
- Study reports include trade-off observations.
- Study reports include a Spatial Bottleneck Analysis section when spatial
  data is available.
- Single-run reports include configuration, KPIs, distributions, and spatial
  bottleneck tables.
- Single-run reports are written to `data/reports/<run_id>_report.md`.
- Reports never modify `data/runs/<run_id>/`.

CLI:

```bash
python -m decision.report --study-dir <study_dir>
python -m decision.report --run-id <run_id> [--base-dir DIR]
```

`--study-dir` and `--run-id` are mutually exclusive.

### `decision/spatial.py`, NEW in v0.7.2

#### `SpatialCellLoad`

```python
@dataclass(frozen=True)
class SpatialCellLoad
```

Fields:

- `x: int`
- `y: int`
- `blocked_events: int`
- `blocked_ticks: int`

#### `SpatialBlockageResult`

```python
@dataclass(frozen=True)
class SpatialBlockageResult
```

Fields:

- `run_id: str`
- `total_blocked_events: int`
- `events_with_coordinates: int`
- `coverage: float`
- `cells: list[SpatialCellLoad]`

Property:

- `has_data -> bool`

Method:

- `top_cells(n: int = 5, by: str = "blocked_ticks") -> list[SpatialCellLoad]`

Functions:

- `compute_spatial_blockage(run_data) -> SpatialBlockageResult`
- `top_bottleneck_cells(run_data, top_n=5) -> list[SpatialCellLoad]`
- `_pair_blocked_episodes(events, final_tick)` — internal episode pairing.

CLI:

```bash
python -m decision.spatial --run-id <run_id> [--base-dir DIR] [--top N] [--by blocked_ticks|blocked_events] [--json]
```

Important behavior:

- Reads saved artifacts only.
- `robot_blocked` rows must carry `{"x": ..., "y": ...}` JSON in `details`
  for v0.7.2+ runs.
- Pre-v0.7.2 runs are reported with coverage 0.0.
- Episodes are paired locally from robot_blocked/robot_unblocked events.
- Unclosed episodes are censored at `summary.json simulation_ticks`.
- `blocked_ticks` are attributed to the onset cell.
- A robot can drift during yield, so exact cells are approximate.
- Hotspots near chargers indicate capacity problems.
- Hotspots at aisle intersections indicate traffic-control problems.

### `decision/demand.py`

Important names:

- `DemandMode`
- `DemandEvent`
- `RateSegment`
- `DemandConfig`
- `DemandModel`
- `DemandTaskGenerator`

Supported demand modes:

- `legacy`
- `uniform`
- `rate_schedule`
- `csv_orders`

Important behavior:

- `legacy` preserves the original synthetic TaskGenerator behavior.
- New demand modes integrate through
  `experiment/factory.create_task_generator()`.
- Demand behavior is controlled by `ExperimentConfig` demand fields.

### `decision/layout.py`

Important names:

- `LayoutConfig`
- `PRESET_LAYOUTS`
- `create_warehouse_for_experiment()`

Supported layout presets:

- `default`
- `high_density`
- `one_way_aisles`

Important behavior:

- `default` preserves the original warehouse layout.
- JSON-based layout definitions are supported.
- Layout validation includes bounds, passable access cells, and required
  functional cells.

### `decision/monte_carlo.py`, NEW in v0.8.0

#### `MonteCarloConfig`

```python
@dataclass(frozen=True)
class MonteCarloConfig
```

Fields:

- `base_config: dict[str, Any]`
- `n_runs: int`
- `base_seed: int | None = None`
- `seeds: list[int]`
- `sla_target_ticks: int | None = None`
- `cost_config: CostConfig | None = None`
- `force_fast_mode: bool = True`
- `output_dir: str = "data/monte_carlo"`
- `runs_base_dir: str = DEFAULT_RUNS_DIR`

#### `MonteCarloResult`

```python
@dataclass(frozen=True)
class MonteCarloResult
```

Fields:

- `mc_id: str`
- `output_dir: Path`
- `results_csv: Path`
- `summary_json: Path`
- `n_runs_requested: int`
- `successful_runs: int`
- `failed_runs: int`
- `aggregate: dict[str, Any]`

Functions:

- `generate_seeds(n_runs, base_seed=None, explicit_seeds=None) -> list[int]`
- `build_trial_config(base_config, seed, index, force_fast_mode=True) -> dict[str, Any]`
- `extract_run_metrics(run_id, runs_base_dir, cost_config=None, sla_target_ticks=None) -> dict[str, Any]`
- `run_monte_carlo(mc_config: MonteCarloConfig) -> MonteCarloResult`

CLI:

```bash
python -m decision.monte_carlo --config <base_config.json> --n <runs>
python -m decision.monte_carlo --from-run-id <run_id> --n <runs>
```

Common options:

- `--n`
- `--base-seed`
- `--seeds`
- `--sla-target-ticks`
- `--cost-config`
- `--output-dir`
- `--runs-base-dir`

Important behavior:

- Executes N identical experiment configurations with different seeds.
- Each trial writes a normal immutable run artifact to `data/runs/<run_id>/`.
- Monte Carlo derived artifacts are written to `data/monte_carlo/<mc_id>/`.
- `force_fast_mode` is True by default because Monte Carlo should be headless.
- `fast_mode` only removes wall-clock pacing and does not change simulation results.
- `summary.json` contains errors when trials fail.
- `results.csv` contains per-trial metrics.
- Aggregate includes mean, standard deviation, min, p05, median, p95, max,
  and normal-approximation confidence intervals for mean KPIs.
- SLA statistics include both `task_late_probability` and
  `run_any_violation_probability`.

SLA metric interpretation:

- `task_late_probability` is the fraction of completed tasks that violated the
  SLA target.
- `run_any_violation_probability` is the fraction of Monte Carlo trials where
  at least one task violated the SLA target.
- `task_late_probability` is usually the more operationally meaningful SLA metric.

### `decision/sensitivity.py`, NEW in v0.8.0

#### `FactorSpec`

```python
@dataclass(frozen=True)
class FactorSpec
```

Fields:

- `name: str`
- `values: list[Any]`

#### `SensitivityConfig`

```python
@dataclass(frozen=True)
class SensitivityConfig
```

Fields:

- `base_config: dict[str, Any]`
- `factors: list[FactorSpec]`
- `reps: int = 3`
- `base_seed: int | None = None`
- `sla_target_ticks: int | None = None`
- `cost_config: CostConfig | None = None`
- `force_fast_mode: bool = True`
- `output_dir: str = "data/sensitivity"`
- `runs_base_dir: str = DEFAULT_RUNS_DIR`

#### `SensitivityResult`

```python
@dataclass(frozen=True)
class SensitivityResult
```

Fields:

- `study_id: str`
- `output_dir: Path`
- `results_csv: Path`
- `summary_json: Path`
- `tornado_csv: Path`
- `successful_runs: int`
- `failed_runs: int`
- `baseline: dict[str, Any]`
- `factor_results: list[dict[str, Any]]`
- `tornado: dict[str, list[dict[str, Any]]]`
- `errors: list[dict[str, Any]]`

Functions:

- `run_sensitivity(cfg: SensitivityConfig) -> SensitivityResult`
- `extract_sensitivity_metrics(run_id, runs_base_dir, cost_config=None, sla_target_ticks=None) -> dict[str, Any]`

CLI:

```bash
python -m decision.sensitivity --config <sensitivity_config.json>
```

Important behavior:

- Performs one-at-a-time, OAT, parameter variation around a baseline configuration.
- Each factor level is evaluated with `reps` replications.
- The same seed set is used across factor levels for paired comparison.
- If a factor value equals the baseline value, baseline runs are reused.
- Writes `results.csv`, `tornado.csv`, and `summary.json`.
- Each non-reused sensitivity trial writes a normal immutable run artifact to
  `data/runs/<run_id>/`.
- Tornado output is sorted by absolute delta.
- Default tornado targets are `cost_per_task` and `p95_cycle_time`.
- OAT sensitivity does not reveal interaction effects.

`extract_sensitivity_metrics` adds:

- `p95_cycle_time`
- feasibility flags
- optional cost KPI fields
- optional direct SLA compliance fields

Example sensitivity config:

```json
{
  "from_run_id": "<run_id>",
  "reps": 3,
  "base_seed": 42,
  "cost_config": "cost_config.json",
  "sla_target_ticks": 300,
  "factors": [
    {
      "name": "num_robots",
      "values": [6, 8, 10]
    },
    {
      "name": "conflict_manager",
      "values": ["local_yield", "zone_locks", "priority_reservation"]
    },
    {
      "name": "charger_capacity",
      "values": [2, 4, 6]
    }
  ]
}
```

### `decision/optimizer.py`, NEW in v0.8.1

#### `SearchSpaceSpec`

```python
@dataclass(frozen=True)
class SearchSpaceSpec
```

Fields:

- `name: str`
- `type: str`
- `low: float | None = None`
- `high: float | None = None`
- `choices: list[Any] | None = None`

Supported `type` values:

- `int`
- `float`
- `categorical`

#### `OptimizerConfig`

```python
@dataclass(frozen=True)
class OptimizerConfig
```

Fields:

- `base_config: dict[str, Any]`
- `search_space: list[SearchSpaceSpec]`
- `objective: str = "cost_per_task"`
- `direction: str = "minimize"`
- `n_trials: int = 50`
- `reps: int = 1`
- `base_seed: int | None = None`
- `constraints: dict[str, float]`
- `sla_target_ticks: int | None = None`
- `cost_config: CostConfig | None = None`
- `force_fast_mode: bool = True`
- `output_dir: str = "data/optimizations"`
- `runs_base_dir: str = DEFAULT_RUNS_DIR`
- `timeout: float | None = None`

Functions:

- `suggest_param(trial, spec: SearchSpaceSpec) -> Any`
- `run_optimization(cfg: OptimizerConfig) -> dict[str, Any]`

CLI:

```bash
python -m decision.optimizer --config <optimizer_config.json>
```

Common options:

- `--n-trials`
- `--reps`
- `--base-seed`
- `--timeout`
- `--cost-config`

Important behavior:

- Uses Optuna TPESampler.
- Uses constrained optimization through Optuna `constraints_func`.
- `constraints_func` is marked experimental by Optuna. The warning is expected.
- Evaluates each trial with `reps` replications.
- Use `reps: 1` for cheap exploration.
- Use robustness verification before deploying any optimizer result.
- Writes `data/optimizations/<opt_id>/summary.json`.
- Explicitly reports `feasible_count` and `infeasible_count`.
- `best_trial` is selected from feasible trials only.
- `best_trial` is null when no feasible trial exists.

Primary supported constraints in `decision/optimizer.py`:

- `p95_cycle_time_max`
- `sla_compliance_rate_min`

Constraint semantics:

- `p95_cycle_time_max` is satisfied when `p95_cycle_time <= limit`.
- `sla_compliance_rate_min` is satisfied when `sla_compliance_rate >= limit`.

Supported objective metrics:

- `cost_per_task`
- `p95_cycle_time`
- `average_throughput`
- `tasks_completed`

`cost_per_task` requires a `CostConfig`.

Example optimizer config:

```json
{
  "from_run_id": "<run_id>",
  "objective": "cost_per_task",
  "direction": "minimize",
  "n_trials": 20,
  "reps": 1,
  "base_seed": 42,
  "cost_config": "cost_config.json",
  "sla_target_ticks": 300,
  "constraints": {
    "p95_cycle_time_max": 60.0
  },
  "search_space": [
    {
      "name": "num_robots",
      "type": "int",
      "low": 4,
      "high": 12
    },
    {
      "name": "charger_capacity",
      "type": "int",
      "low": 2,
      "high": 8
    },
    {
      "name": "conflict_manager",
      "type": "categorical",
      "choices": ["local_yield", "zone_locks", "priority_reservation"]
    },
    {
      "name": "scheduler",
      "type": "categorical",
      "choices": ["baseline", "priority", "fifo", "total_cost", "auction"]
    }
  ]
}
```

### `decision/multiobjective.py`, NEW in v0.8.1

#### `ObjectiveSpec`

```python
@dataclass(frozen=True)
class ObjectiveSpec
```

Fields:

- `metric: str`
- `direction: str = "minimize"`

#### `MultiObjectiveConfig`

```python
@dataclass(frozen=True)
class MultiObjectiveConfig
```

Fields:

- `base_config: dict[str, Any]`
- `search_space: list[SearchSpaceSpec]`
- `objectives: list[ObjectiveSpec]`
- `constraints: dict[str, float]`
- `n_trials: int = 50`
- `reps: int = 1`
- `base_seed: int | None = None`
- `population_size: int | None = None`
- `sla_target_ticks: int | None = None`
- `cost_config: CostConfig | None = None`
- `force_fast_mode: bool = True`
- `output_dir: str = "data/multiobjective"`
- `runs_base_dir: str = DEFAULT_RUNS_DIR`
- `timeout: float | None = None`

Functions:

- `run_multiobjective(cfg: MultiObjectiveConfig) -> dict[str, Any]`
- `_pareto_trials(trials, directions) -> list[dict[str, Any]]`
- `_dominates(a, b, directions) -> bool`

CLI:

```bash
python -m decision.multiobjective --config <multiobjective_config.json>
```

Common options:

- `--n-trials`
- `--reps`
- `--base-seed`
- `--timeout`
- `--cost-config`

Important behavior:

- Uses Optuna NSGAIISampler.
- Supports multiple objectives.
- Typical use is minimizing `cost_per_task` while minimizing `p95_cycle_time`.
- Uses cheap single-replica evaluations by default.
- Feasibility is evaluated after simulation.
- The Pareto front is extracted from feasible trials only.
- If `feasible_count` is zero, the search space or constraints are too strict.
- Writes `summary.json`, `trials.json`, and `pareto.csv`.
- `summary.json` includes `base_config` and `cost_config` so robustness
  verification can inherit them.
- Pareto candidates are not deployable until verified by
  `decision/robustness.py`.

Constraint key convention in multi-objective and robustness modules:

- `<metric>_max`
- `<metric>_min`

Examples:

- `p95_cycle_time_max`
- `sla_compliance_rate_min`
- `cost_per_task_max`
- `total_blocked_ticks_max`
- `average_cycle_time_max`

Constraint satisfaction rule:

- For `<metric>_max`, value <= limit.
- For `<metric>_min`, value >= limit.

Allowed metrics for objectives and generic constraints:

- `cost_per_task`
- `p95_cycle_time`
- `average_cycle_time`
- `average_throughput`
- `tasks_completed`
- `sla_compliance_rate`
- `total_blocked_ticks`

Example multi-objective config:

```json
{
  "from_run_id": "<run_id>",
  "n_trials": 30,
  "reps": 1,
  "base_seed": 42,
  "cost_config": "cost_config.json",
  "sla_target_ticks": 300,
  "constraints": {
    "sla_compliance_rate_min": 0.95
  },
  "objectives": [
    {
      "metric": "cost_per_task",
      "direction": "minimize"
    },
    {
      "metric": "p95_cycle_time",
      "direction": "minimize"
    }
  ],
  "search_space": [
    {
      "name": "num_robots",
      "type": "int",
      "low": 4,
      "high": 12
    },
    {
      "name": "charger_capacity",
      "type": "int",
      "low": 2,
      "high": 8
    },
    {
      "name": "conflict_manager",
      "type": "categorical",
      "choices": ["local_yield", "zone_locks", "priority_reservation"]
    },
    {
      "name": "scheduler",
      "type": "categorical",
      "choices": ["baseline", "priority", "fifo", "total_cost", "auction"]
    }
  ]
}
```

### `decision/robustness.py`, NEW in v0.8.1

#### `RobustnessCandidate`

```python
@dataclass(frozen=True)
class RobustnessCandidate
```

Fields:

- `label: str`
- `overrides: dict[str, Any]`

#### `RobustnessConfig`

```python
@dataclass(frozen=True)
class RobustnessConfig
```

Fields:

- `base_config: dict[str, Any]`
- `candidates: list[RobustnessCandidate]`
- `reps: int = 20`
- `base_seed: int | None = None`
- `constraints: dict[str, float]`
- `objective: str = "cost_per_task"`
- `direction: str = "minimize"`
- `min_pass_probability: float = 0.95`
- `sla_target_ticks: int | None = None`
- `cost_config: CostConfig | None = None`
- `force_fast_mode: bool = True`
- `output_dir: str = "data/robustness"`
- `runs_base_dir: str = DEFAULT_RUNS_DIR`

Functions:

- `run_robustness(cfg: RobustnessConfig) -> dict[str, Any]`
- `_evaluate_constraints_for_rows(rows, constraints) -> dict[str, Any]`
- `_summarize_metrics(rows) -> dict[str, Any]`

CLI:

```bash
python -m decision.robustness --config <robustness_config.json>
```

Common options:

- `--reps`
- `--base-seed`
- `--min-pass-probability`

Important behavior:

- Verifies candidate configurations under stochastic variation.
- Runs each candidate with many seeds.
- `reps: 20` is the practical minimum for deployment decisions.
- Uses the same seed set across candidates for paired comparison.
- Calculates `constraint_pass_probability` for each candidate.
- `constraint_pass_probability` is the fraction of replications satisfying all
  constraints.
- A candidate is `robust_pass` when
  `constraint_pass_probability >= min_pass_probability`.
- `recommended` is null when no candidate meets `min_pass_probability`.
- Writes `results.csv` and `summary.json`.
- Each replication writes a normal immutable run artifact to
  `data/runs/<run_id>/`.

Candidate sources:

- Explicit `candidates` list in robustness config.
- `from_multiobjective` path pointing to a multi-objective `summary.json`.
- Multi-objective Pareto trials can be selected automatically.
- Single-objective `best_trial` can be used if present in an optimizer summary.

Important robustness rule:

- Do not deploy single-replica optimizer or Pareto candidates without
  robustness verification.

Example robustness config:

```json
{
  "from_multiobjective": "data/multiobjective/<study_id>/summary.json",
  "max_candidates": 3,
  "reps": 20,
  "base_seed": 123,
  "constraints": {
    "p95_cycle_time_max": 60.0,
    "sla_compliance_rate_min": 0.95
  },
  "objective": "cost_per_task",
  "direction": "minimize",
  "min_pass_probability": 0.90,
  "cost_config": "cost_config.json",
  "sla_target_ticks": 300
}
```

## Experiment Lifecycle, v0.5.0

User defines ExperimentConfig through UI form or JSON.

POST /api/experiment/start

- unique run_id created
- run directory created
- config.json saved
- Simulation created from config
- Simulation is not started directly
- MetricsRecorder attached
- runner drives `sim._tick()` under `sim._lock`
- recorder writes one time-series row plus inferred events per tick
- stop condition reached
- recorder closed
- summary.json written
- visualization and analysis read saved files only

The runner does not call `Simulation.start()`.
It drives `_tick()` directly in its own daemon thread.
It sleeps `tick_interval` between ticks in normal mode.
In fast mode it yields only.

## Reproducibility And Seeding

Rule:

same config + same seed = same result

The seed controls:

- `TaskGenerator(warehouse, seed=seed)` location selection.
- failure RNG, `FailureConfig.seed` / `Simulation(seed=...)`.
- robot spawn positions, seeded shuffle of passable cells in
  `experiment/factory.generate_spawn_positions()`.

No global RNG reliance.
No new randomness introduced in v0.5+.
`fast_mode` removes wall-clock pacing only.
Tick semantics and results are identical in live and fast mode.

Monte Carlo and robustness modules generate deterministic seed lists when
`base_seed` is provided. If explicit seeds are provided, they are used directly.

## Stopping Conditions

`stop_mode = "fixed_ticks"`:

- Run until `max_ticks`.
- Answers: how much work is completed in the same time?

`stop_mode = "workload"`:

- Run until `target_tasks` completed.
- `max_ticks` is the safety horizon.
- Answers: how long does the same workload take?

`stop_reason` values written to summary.json:

- `target_reached`
- `max_ticks_reached`
- `stopped_by_user`
- `reset_by_user`
- `error: <message>`

## Fast / Headless Mode

`ExperimentConfig.fast_mode: bool = False`

When true:

- `ExperimentRunner` does not sleep `tick_interval`.
- It yields with `time.sleep(0)` periodically.
- `tick_interval` is untouched.
- results remain reproducible.

UI:

- Setup checkbox `cfg-fast-mode`.
- Start shows `view-fast` with progress text `fast-status` and `fast-stop-btn`.
- On finish the poller auto-transitions to Results.

Recorded as metadata in config.json and summary.json as `fast_mode`.
Fast mode pins one CPU core for its duration. That is expected.

Monte Carlo, sensitivity, optimization, multi-objective, and robustness
modules usually force `fast_mode` True because they are headless decision-layer
workflows.

## Run Identity And Storage Format

run_id format: `YYYYMMDD_HHMMSS_<6 hex>`
Example: `20260821_013526_a83f21`

Runs are never overwritten.
`display_name` is metadata only.

### Run Storage

```text
data/
└── runs/
    └── <run_id>/
        ├── config.json
        ├── timeseries.csv
        ├── events.csv
        └── summary.json
```

### Study Storage, NEW in v0.7.1

```text
data/
└── studies/
    └── <study_id>/
        ├── study_config.json
        ├── results.csv
        └── report.md
```

`results.csv` carries a `run_id` column so each study row traces back to
`data/runs/<run_id>/`.

### Report Storage, NEW in v0.7.2

```text
data/
└── reports/
    └── <run_id>_report.md
```

Single-run reports are never written inside `data/runs/`.

### Monte Carlo Storage, NEW in v0.8.0

```text
data/
└── monte_carlo/
    └── <mc_id>/
        ├── results.csv
        └── summary.json
```

Each Monte Carlo trial also writes a normal immutable run artifact under
`data/runs/<run_id>/`.

### Sensitivity Storage, NEW in v0.8.0

```text
data/
└── sensitivity/
    └── <study_id>/
        ├── results.csv
        ├── tornado.csv
        └── summary.json
```

Each sensitivity trial also writes a normal immutable run artifact under
`data/runs/<run_id>/`.

### Optimization Storage, NEW in v0.8.1

```text
data/
└── optimizations/
    └── <opt_id>/
        └── summary.json
```

Each optimization trial may write normal immutable run artifacts under
`data/runs/<run_id>/`.

### Multi-Objective Storage, NEW in v0.8.1

```text
data/
└── multiobjective/
    └── <study_id>/
        ├── summary.json
        ├── trials.json
        └── pareto.csv
```

Each multi-objective trial may write normal immutable run artifacts under
`data/runs/<run_id>/`.

### Robustness Verification Storage, NEW in v0.8.1

```text
data/
└── robustness/
    └── <robust_id>/
        ├── results.csv
        └── summary.json
```

Each robustness replication writes a normal immutable run artifact under
`data/runs/<run_id>/`.

## config.json keys

config.json keys use snake_case because they map directly to ExperimentConfig fields.

Primary keys:

`seed`, `num_robots`, `display_name`, `stop_mode`, `target_tasks`,
`max_ticks`, `tick_interval`, `fast_mode`, `blocked_replan_seconds`,
`replan_cooldown_ticks`, `battery_capacity`, `empty_move_energy`,
`loaded_move_energy`, `critical_battery`,
`opportunistic_charge_threshold`, `idle_ticks_before_opportunistic_charge`,
`battery_safety_margin`, `empty_battery_recovery_ticks`, `charger_capacity`,
`charge_duration_ticks`, `failure_enabled`, `mtbf_ticks`, `mttr_ticks`,
`relocate_to_maintenance`, `scheduler`, `path_planner`, `conflict_manager`.

New v0.7.1 keys:

`demand_mode`, `demand_rate_per_tick`, `demand_task_weights`,
`demand_segments`, `demand_csv_path`, `demand_events`,
`layout_preset`, `layout_file`.

## timeseries.csv headers

One row per tick:

`tick`, `tasks_pending`, `tasks_outstanding`, `tasks_created_this_tick`,
`tasks_completed_this_tick`, `tasks_completed_total`, `tasks_failed_total`,
`robots_active`, `robots_idle`, `robots_blocked`, `robots_charging`,
`robots_to_charger`, `robots_waiting_for_charger`, `robots_failed`,
`average_battery`, `min_battery`, `max_battery`, `replans_this_tick`,
`replans_total`, `blocked_ticks_this_tick`, `blocked_ticks_total`.

Definitions:

- `tasks_pending` = live tasks with status Pending, unassigned only.
- `tasks_outstanding` = generated - completed - failed.
- `tasks_outstanding` includes Pending, Assigned, and Interrupted tasks.
- `tasks_outstanding` never counts completed tasks awaiting pruning.
- Robot buckets are mutually exclusive and sum to the robot population.
- Robot bucket priority:
  failed/repairing > charging > waiting-for-charger > blocked > to-charger >
  active > idle.
- `throughput[t] = tasks_completed_this_tick`.
- Averages and rolling windows exist only in the analysis layer.

## events.csv headers

`run_id`, `tick`, `event_type`, `robot_id`, `task_id`, `details`.

Missing fields are empty strings, never invented.

As of v0.7.2:

- `robot_blocked` rows carry `{"x": ..., "y": ...}` JSON in `details`.
- The coordinates represent the cell occupied when blocking started.
- Pre-v0.7.2 runs have empty `details` on `robot_blocked` rows.

Event types:

`task_created`, `task_assigned`, `task_completed`, `task_failed`,
`task_interrupted`, `task_reassigned`, `robot_blocked`, `robot_unblocked`,
`robot_replanned`, `robot_started_charging`, `robot_finished_charging`,
`robot_waiting_for_charger`, `robot_faulted`, `robot_recovered`.

Known limitation: multiple transitions inside one tick can be coalesced.
Live task pruning never deletes history.
CSVs are written independently.

## summary.json keys

`run_id`, `seed`, `scheduler`, `stop_reason`, `fast_mode`,
`simulation_ticks`, `simulation_seconds`, `robot_count`, `tasks_created`,
`tasks_assigned`, `tasks_completed`, `tasks_failed`, `average_throughput`,
`average_wait_time`, `average_cycle_time`, `average_robot_utilization`,
`total_replans`, `total_blocked_ticks`, `blocked_time_seconds`,
`charging_events`, `total_charging_ticks`, `charger_wait_ticks`,
`charger_wait_events`, `battery_task_interruptions`,
`failure_task_interruptions`, `task_reassignments`, `failed_robot_events`,
`failure_downtime_ticks`, `robot_utilization`, `robot_busy_ticks`,
`robot_total_ticks`, `robot_blocked_ticks`, `robot_distance_travelled`.

Summary is for quick comparison; the CSVs are authoritative.

## experiment/config.py, UPDATED in v0.7.1, UNCHANGED in v0.8.x

`ExperimentConfig` — @dataclass(frozen=True), validated in `__post_init__`.

Fields and defaults:

`seed: int`, `num_robots: int`, `display_name: str = ""`,
`stop_mode: Literal["fixed_ticks", "workload"]`, `target_tasks: int | None`,
`max_ticks: int`, `tick_interval: float = 0.3`, `fast_mode: bool = False`,
`blocked_replan_seconds: float = 0.7`, `replan_cooldown_ticks: int = 7`,
`battery_capacity: float = 100.0`, `empty_move_energy: float = 0.35`,
`loaded_move_energy: float = 0.5`, `critical_battery: float = 15.0`,
`opportunistic_charge_threshold: float = 30.0`,
`idle_ticks_before_opportunistic_charge: int = 10`,
`battery_safety_margin: float = 5.0`,
`empty_battery_recovery_ticks: int = 15`,
`charger_capacity: int = 4`, `charge_duration_ticks: int = 10`,
`failure_enabled: bool = False`, `mtbf_ticks: float = 0.0`,
`mttr_ticks: int = 25`, `relocate_to_maintenance: bool = True`,
`scheduler: str = "baseline"`,
`path_planner: str = "bfs"`, NEW in v0.6.0,
`conflict_manager: str = "local_yield"`, NEW in v0.6.0,
`demand_mode: str = "legacy"`, NEW in v0.7.1,
`demand_rate_per_tick: float = 0.0`, NEW in v0.7.1,
`demand_task_weights: dict[str, float]`, NEW in v0.7.1,
`demand_segments: list[dict[str, Any]]`, NEW in v0.7.1,
`demand_csv_path: str | None = None`, NEW in v0.7.1,
`demand_events: list[dict[str, Any]]`, NEW in v0.7.1,
`layout_preset: str = "default"`, NEW in v0.7.1,
`layout_file: str | None = None`, NEW in v0.7.1.

Module-level constants:

```python
PATH_PLANNER_CHOICES = {"bfs", "astar", "weighted_astar"}
CONFLICT_MANAGER_CHOICES = {"local_yield", "zone_locks", "priority_reservation"}
DEMAND_MODE_CHOICES = {"legacy", "uniform", "rate_schedule", "csv_orders"}
LAYOUT_PRESET_CHOICES = {"default", "high_density", "one_way_aisles"}
```

Methods:

- `default()`
- `to_dict()`
- `save(directory)`
- `load(directory)`
- `from_dict(data)`

`from_dict(data)` merges over defaults then validates.

Validation highlights:

- seed required.
- num_robots >= 1.
- workload requires target_tasks >= 1.
- max_ticks >= 1.
- tick_interval > 0.
- failure_enabled requires mtbf_ticks > 0.
- path_planner must be in PATH_PLANNER_CHOICES.
- conflict_manager must be in CONFLICT_MANAGER_CHOICES.
- demand_mode must be in DEMAND_MODE_CHOICES.
- layout_preset must be in LAYOUT_PRESET_CHOICES.

## experiment/factory.py, UPDATED in v0.7.1

`ROBOT_COLORS: list[str]` — Okabe-Ito-style palette, cycled by index.

Functions:

- `generate_spawn_positions(num_robots, warehouse, seed) -> list[tuple[int,int]]`
- `create_experiment_robots(num_robots, warehouse, seed) -> list[Robot]`
- `create_path_planner_from_name(name: str) -> PathPlanner`, NEW in v0.6.0
- `create_scheduler_from_name(name: str, path_planner: PathPlanner) -> Scheduler`, NEW in v0.6.0
- `create_conflict_manager_from_name(name: str, sim: Simulation) -> ConflictManager`, NEW in v0.6.0
- `create_path_planner(config: ExperimentConfig) -> PathPlanner`, NEW in v0.6.0
- `create_scheduler(config: ExperimentConfig, path_planner: PathPlanner) -> Scheduler`, NEW in v0.6.0
- `create_conflict_manager(config: ExperimentConfig, sim: Simulation) -> ConflictManager`, NEW in v0.6.0
- `create_task_generator(config: ExperimentConfig, warehouse: Warehouse) -> TaskGenerator`, NEW in v0.7.1
- `create_simulation_from_config(config) -> Simulation`

Important behavior:

- `generate_spawn_positions()` collects passable cells, shuffles with
  `random.Random(seed)`, takes N. ValueError if fewer passable cells than requested.
- `create_experiment_robots()` creates ids `R1..RN`, clean strings,
  deterministic seeded positions.
- `create_simulation_from_config()` builds the warehouse via
  `decision.layout.create_warehouse_for_experiment()`, builds the task
  generator via `create_task_generator()`, builds robots, configs, path
  planner, scheduler, and injects conflict manager via
  `sim.set_conflict_manager()`.

## experiment/recorder.py, UPDATED in v0.7.2

`MetricsRecorder(run_dir: str, run_id: str)`.

Public:

- `record(snapshot: dict)`
- `close()`

Important behavior:

- Opens `timeseries.csv` and `events.csv`.
- Writes headers.
- Flushes periodically.
- `close()` flushes and closes.
- Receives primitive snapshots only.
- Never stores live object references.

`record()` writes one time-series row.
It then infers task/robot events by diffing previous-tick primitive state.

Internal previous state fields:

- `_prev_metrics`
- `_prev_tasks`
- `_prev_robots`

Completed/failed tasks are dropped from `_prev_tasks` only after being seen
Completed/Failed.
`robot_unblocked` is suppressed when caused by failed/repairing/charging/waiting transitions.

As of v0.7.2:

- `robot_blocked` events write `{"x": ..., "y": ...}` JSON into the `details`
  column.
- The coordinates represent the cell occupied when blocking started.

## experiment/runner.py, UPDATED in v0.7.2

`ExperimentRunner(base_dir: str = "data/runs")`.

Properties:

- `is_active`
- `finished`

Public methods:

- `start(config, sim_factory) -> run_id`
- `stop(reason="stopped_by_user")`
- `get_state() -> dict`
- `get_summary() -> dict | None`

Important behavior:

- `start()` creates run dir, saves config, creates recorder, calls
  `sim.resume()`, starts daemon thread. RuntimeError if a run is active.
- `stop()` sets stop reason, calls `sim.stop()`, joins.
- `get_state()` returns `{active, finished, runId, runDir, stopReason, paused, tick, fastMode}`.
- `get_summary()` returns in-memory summary or reads summary.json.

Internal:

- `_run()` loops while not `sim._stop_event`, skips while `sim.is_paused`,
  under `sim._lock` calls `_tick()`, `_snapshot()`, `recorder.record()`, and
  evaluates stop condition.
- Pacing: fast_mode -> `time.sleep(0)` every 500 ticks; normal mode ->
  `time.sleep(sim._tick_interval)`.
- Exceptions set `stop_reason = "error: ..."`.
- `_snapshot()` extracts primitive metrics counters, per-task fields, and
  per-robot fields including x and y.
- `_evaluate_stop_condition()` implements fixed_ticks and workload stopping.
- `_finalize()` closes recorder, computes and writes summary.json once.

## analysis/loader.py, NEW in v0.5.0

`DEFAULT_RUNS_DIR = "data/runs"`.

`RunData` dataclass:

- `run_id`
- `run_dir`
- `config`
- `summary`
- `timeseries`
- `events`

Functions:

- `list_runs(base_dir) -> list[dict]`
- `load_run(run_id, base_dir) -> RunData`

Important behavior:

- `list_runs` returns newest first.
- Each entry contains `run_id`, `run_dir`, `config`, `summary`.
- `load_run` raises FileNotFoundError if the run is missing.

## analysis/metrics.py, NEW in v0.5.0

Functions:

- `ensure_derived_timeseries(df)`
- `percentile_summary(series)`
- `task_lifecycle_from_events(events)`
- `blocked_episodes_from_events(events, final_tick=None)`
- `event_counts(events)`
- `utilization_from_summary(summary)`
- `robot_count_from_run(run)`
- `distribution_stats(run)`

`ensure_derived_timeseries(df)`:

- Adds `tick` if absent.
- Adds `tasks_completed_total` cumsum if absent.
- Adds `throughput = tasks_completed_this_tick`.
- Adds `throughput_rolling_50`.
- Adds `throughput_rolling_100`.
- Never alters recorded columns.

`percentile_summary(series)`:

- Returns `count`, `mean`, `median`, `p90`, `p95`, `max`.

`task_lifecycle_from_events(events)`:

Per task returns:

- `created_tick`
- `first_assigned_tick`
- `completed_tick`
- `failed_tick`
- `waiting_time = first_assigned_tick - created_tick`
- `cycle_time = completed_tick - created_tick`

`blocked_episodes_from_events(events, final_tick=None)`:

Pairs robot_blocked/robot_unblocked into episodes.

Episode fields:

- `robot_id`
- `start_tick`
- `end_tick`
- `duration_ticks`
- `open_at_end`

Unclosed episodes are censored at `final_tick`.

`distribution_stats(run)`:

Percentile summaries for:

- task_waiting_time
- task_cycle_time
- robot_blocked_episode_ticks
- system_active_fraction
- robot_utilization

## analysis/web.py, NEW in v0.5.0

Important names:

- `RUN_ID_PATTERN = ^[A-Za-z0-9_\-]+$`
- `DEFAULT_MAX_POINTS = 2000`
- `MAX_POINTS_LIMIT = 5000`
- `_sanitize()`
- `_downsample(df, column, max_points)`
- `_histogram(series, bins)`

Payload builders:

- `list_runs_payload(base_dir) -> {"runs": [...]}`
- `get_run_summary(run_id, base_dir) -> {"run_id", "config", "summary"}`
- `get_run_series(run_id, columns, base_dir, max_points) -> {"run_id", "max_points", "series": [{"name", "points"}]}`
- `get_compare_series(run_ids, column, base_dir, max_points) -> {"column", "max_points", "runs": [{"run_id", "points"}]}`
- `get_run_distributions(run_id, base_dir, bins) -> distributions payload`

Important behavior:

- Invalid run ids raise `AnalysisApiError`, mapped to 404 by Flask routes.
- `max_points` is clamped, min 50.
- `_sanitize()` makes JSON safe; NaN/Inf become null; numpy scalars converted.
- `_downsample()` uses bucket-mean to `[[tick, value], ...]`.
- Full CSVs are never sent to the browser.
- Only downsampled payloads are sent.

## Flask Layer, UPDATED in v0.5.0, UNCHANGED in v0.8.x

### `app.py`

Important functions:

- `create_app(base_data_dir: str = "data/runs", start_simulation: bool = False) -> Flask`
- module-level `app = create_app()`

Holder pattern:

```python
holder = {
    "simulation": <Simulation>,
    "runner": <ExperimentRunner | None>
}
```

All state routes read `holder["simulation"]`.
`create_default_simulation()` is replaced by
`create_simulation_from_config(ExperimentConfig.default())`.

Routes, legacy semantics preserved:

- `GET /`
- `GET /api/state`
- `POST /api/pause`
- `POST /api/resume`
- `POST /api/reset`

`GET /api/state` returns the v0.4 payload plus top-level `experiment` key.

If runner present, `experiment` is `runner.get_state()`.
Else:

```json
{
  "active": false,
  "finished": false,
  "runId": null,
  "stopReason": null,
  "fastMode": false
}
```

`POST /api/reset` stops active runner with `reset_by_user` and recreates
default simulation.

Routes, v0.5 experiment lifecycle:

- `POST /api/experiment/start`
- `GET /api/experiment/state`
- `POST /api/experiment/stop`
- `GET /api/experiment/summary`

Important behavior:

- `POST /api/experiment/start` returns 409 if a run is active.
- Returns 400 on validation or spawn errors.
- Body is ExperimentConfig JSON, merged over defaults.
- Returns `{runId}`.
- Swaps holder simulation/runner.
- `GET /api/experiment/summary` returns 404 without runner; 409 not finished.

Routes, v0.5 analysis API:

- `GET /api/runs`
- `DELETE /api/runs/<run_id>`
- `GET /api/runs/compare/series?runs=a,b&column=...&max_points=...`
- `GET /api/runs/<run_id>/summary`
- `GET /api/runs/<run_id>/series?columns=a,b&max_points=...`
- `GET /api/runs/<run_id>/distributions?bins=...`

Important behavior:

- Routes stay thin.
- Business logic lives in `simulation/`, `experiment/`, and `analysis/`.
- The raw `data/runs` directory is not served statically.

## CLI Layer, UPDATED in v0.8.1

### `benchmark.py`

Purpose:

- Runs a headless synchronous benchmark.
- Does not start Flask.
- Does not poll.
- Directly calls `sim._tick()` under the simulation lock.
- As of v0.7.2, records every run through `ExperimentRunner`.

Existing arguments:

- `--robots`
- `--block-replan`
- `--cooldown`
- `--target`
- `--seed`

v0.4 arguments:

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

v0.5 arguments:

- `--spawn`, choices: `seeded`, `legacy`; default: `seeded`
- `--display-name`

v0.6 arguments:

- `--path-planner`, choices: `bfs`, `astar`, `weighted_astar`; default: `bfs`
- `--scheduler`, choices: `baseline`, `priority`, `fifo`, `total_cost`,
  `auction`; default: `baseline`
- `--conflict-manager`, choices: `local_yield`, `zone_locks`,
  `priority_reservation`; default: `local_yield`

Important behavior:

- Benchmark wall-clock times are not comparable to pre-v0.7.2 runs due to
  recording overhead.

Examples:

```bash
python benchmark.py \
  --robots 8 \
  --seed 42 \
  --target 200 \
  --path-planner astar \
  --scheduler priority \
  --conflict-manager priority_reservation
```

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

- Legacy Optuna parameter optimizer.
- Prefer `decision/optimizer.py`, `decision/multiobjective.py`, and
  `decision/robustness.py` for v0.8.1 workflows.

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

v0.4 arguments:

- `--search-v04`
- plus battery/charging/failure parameter set.

Important behavior:

- Without `--search-v04`, optimization behavior remains v0.3-style but runs
  with v0.4 battery/charging defaults.
- With `--search-v04`, selected battery/charging parameters are included in
  the search space.
- v0.4 metrics are logged as Optuna user attributes.
- Study name includes a v0.4 suffix when `--search-v04` is used.

### Decision CLI, UPDATED in v0.8.1

Study:

```bash
python -m decision.study --config <study_config.json>
```

Report:

```bash
python -m decision.report --study-dir <study_dir>
python -m decision.report --run-id <run_id> [--base-dir DIR]
```

Spatial:

```bash
python -m decision.spatial --run-id <run_id> [--base-dir DIR] [--top N] [--by blocked_ticks|blocked_events] [--json]
```

Monte Carlo:

```bash
python -m decision.monte_carlo --config <base_config.json> --n <runs>
python -m decision.monte_carlo --from-run-id <run_id> --n <runs>
```

Sensitivity:

```bash
python -m decision.sensitivity --config <sensitivity_config.json>
```

Single-objective optimization:

```bash
python -m decision.optimizer --config <optimizer_config.json>
```

Multi-objective optimization:

```bash
python -m decision.multiobjective --config <multiobjective_config.json>
```

Robustness verification:

```bash
python -m decision.robustness --config <robustness_config.json>
```

## Decision Output Schemas, v0.8.x

### Monte Carlo `summary.json`

Important fields:

- `mc_id`
- `generated_at`
- `n_runs_requested`
- `successful_runs`
- `failed_runs`
- `seeds`
- `effective_sla_target_ticks`
- `force_fast_mode`
- `base_config`
- `aggregate`
- `errors`

`aggregate.kpis` contains per-KPI summaries:

- `count`
- `mean`
- `stdev`
- `min`
- `p05`
- `median`
- `p95`
- `max`
- `mean_ci95_low`
- `mean_ci95_high`

`aggregate.sla` contains:

- `target_ticks`
- `evaluated_tasks`
- `late_tasks`
- `task_late_probability`
- `runs_evaluated`
- `runs_with_any_late`
- `run_any_violation_probability`

### Sensitivity `summary.json`

Important fields:

- `study_id`
- `generated_at`
- `reps`
- `seeds`
- `effective_sla_target_ticks`
- `base_config`
- `factors`
- `baseline`
- `factor_results`
- `tornado`
- `errors`

`baseline` contains:

- `runs`
- `aggregate`
- `cost_per_task`
- `p95_cycle_time`

`factor_results` contains per-factor levels:

- `value`
- `reused_baseline`
- `runs`
- `aggregate`
- `cost_per_task`
- `p95_cycle_time`
- `delta_cost_per_task`
- `delta_percent_cost_per_task`
- `delta_p95_cycle_time`
- `delta_percent_p95_cycle_time`

`tornado` contains sorted lists for:

- `cost_per_task`
- `p95_cycle_time`

### Optimizer `summary.json`

Important fields:

- `opt_id`
- `generated_at`
- `n_trials`
- `reps`
- `objective`
- `direction`
- `constraints`
- `best_trial`
- `feasible_count`
- `infeasible_count`
- `search_space`

`best_trial` contains:

- `number`
- `params`
- `value`
- `state`
- `metrics`
- `feasible`
- `constraints`
- `error`

### Multi-Objective `summary.json`

Important fields:

- `study_id`
- `output_dir`
- `generated_at`
- `objectives`
- `constraints`
- `n_trials`
- `reps`
- `base_seed`
- `sla_target_ticks`
- `base_config`
- `cost_config`
- `search_space`
- `total_trials`
- `feasible_count`
- `pareto_count`
- `pareto_trials`

`pareto_trials` entries contain:

- `number`
- `params`
- `values`
- `state`
- `metrics`
- `constraints`
- `feasible`
- `error`

`trials.json` contains all trials, not only Pareto trials.

`pareto.csv` contains:

- `trial_number`
- `feasible`
- one column per objective
- one column per search-space parameter
- `constraint_values`

### Robustness `summary.json`

Important fields:

- `robust_id`
- `output_dir`
- `generated_at`
- `reps`
- `base_seed`
- `objective`
- `direction`
- `constraints`
- `min_pass_probability`
- `sla_target_ticks`
- `base_config`
- `cost_config`
- `successful_runs`
- `failed_runs`
- `recommended`
- `candidates`
- `errors`

Each candidate result contains:

- `label`
- `overrides`
- `successful_reps`
- `failed_reps`
- `constraint_pass_probability`
- `robust_pass`
- `objective_metric`
- `objective_direction`
- `objective_mean`
- `objective_stdev`
- `metrics`
- `constraint_details`

`constraint_details` contains per-constraint:

- `metric`
- `limit`
- `pass_probability`
- `mean_value`
- `worst_value`

## JSON API

### `GET /api/state`

Returns the v0.4 payload plus the v0.5 top-level `experiment` key described
in the Flask Layer section.

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

`paused`, `tick`, `warehouse`, `robots`, `tasks`, `metrics`,
`experiment` (v0.5)

Robot JSON keys:

Existing:

`id`, `x`, `y`, `color`, `status`, `currentTaskId`, `currentTarget`,
`blockedTicks`, `replanning`, `yieldingTo`, `replanCooldown`

v0.4:

`battery`, `mode`, `idleTicks`, `chargerWaitTicks`, `interruptedTaskId`,
`chargeTarget`, `chargeStartBattery`, `repairRemainingTicks`

Task JSON keys:

Existing:

`id`, `name`, `pickup`, `dropoff`, `taskType`, `priority`, `createdAt`,
`completedAt`, `status`, `assignedRobotId`, `phase`

v0.4:

`loadState`, `interruptionCount`, `lastAssignedRobotId`,
`resumeLocationName`

Important: `status` can be `"Interrupted"`.

Warehouse JSON keys:

`width`, `height`, `layout`, `obstacles`, `locations`, `racks`

Important: dynamic `RESUME-*` locations must not appear in the serialized
warehouse payload.

Metrics JSON keys:

Existing:

`tasksGenerated`, `tasksAssigned`, `tasksCompleted`, `tasksFailed`,
`blockedTimeTicks`, `blockedTimeSeconds`, `replanningCount`,
`deadlockResolutions`, `replanEvents`, `throughputPerTick`,
`averageTaskWaitingTime`, `averageTaskCompletionTime`, `simulationTicks`,
`simulationSeconds`, `robotDistanceTravelled`, `robotBusyTicks`,
`robotBlockedTicks`, `robotReplanEvents`, `robotUtilization`

v0.4:

`averageBattery`, `averageBatteryPercent`, `chargingEvents`,
`totalChargingTicks`, `totalChargingSeconds`, `chargerWaitTicks`,
`chargerWaitSeconds`, `chargerWaitEvents`, `averageChargerWaitTicks`,
`averageChargerWaitSeconds`, `trafficWaitTicks`, `trafficWaitSeconds`,
`stationWaitTicks`, `stationWaitSeconds`, `totalWaitTicks`,
`totalWaitSeconds`, `batteryTaskInterruptions`,
`failureTaskInterruptions`, `taskReassignments`, `failedRobotEvents`,
`failureDowntimeTicks`, `failureDowntimeSeconds`, `congestion`

`replanEvents` duplicates `replanningCount` for backward compatibility.

Congestion JSON keys inside `metrics.congestion`:

`blockedRobots`, `waitingForChargerRobots`, `chargingRobots`,
`toChargerRobots`, `failedRobots`, `replanningRobots`, `activeConflicts`,
`chargerOccupancy`, `chargerWaiting`, `averageBlockedTicks`, `robotsByRow`

Important: congestion emerges from robot interactions; it is measured, not
artificially imposed.

### v0.5 analysis endpoint examples

`GET /api/runs/<run_id>/series`:

```json
{
  "run_id": "20260821_013526_a83f21",
  "max_points": 2000,
  "series": [
    {"name": "throughput_rolling_100", "points": [[0, 0.0], [50, 0.12]]}
  ]
}
```

`GET /api/runs/compare/series`:

```json
{
  "column": "robots_blocked",
  "max_points": 2000,
  "runs": [
    { "run_id": "runA", "points": [[0, 0], [10, 1]] },
    { "run_id": "runB", "points": [[0, 0], [10, 3]] }
  ]
}
```

`GET /api/runs/<run_id>/distributions`:

```json
{
  "run_id": "...",
  "stats": {
    "task_waiting_time": {
      "count": 500,
      "mean": 12.4,
      "median": 10.0,
      "p90": 25.0,
      "p95": 31.0,
      "max": 60.0
    }
  },
  "histograms": {
    "task_waiting_time": {
      "bin_centers": [1.0],
      "bin_edges": [0.0, 2.0],
      "counts": [12]
    }
  },
  "robot_utilization": [{ "robot_id": "R1", "utilization": 0.74 }]
}
```

## Frontend JavaScript, UPDATED in v0.6.0, UNCHANGED in v0.8.x

No v0.7.x or v0.8.x frontend changes exist because the project follows
No UI First for decision-layer features.

### `static/simulation.js`

Important constants:

- `CELL_SIZE` (32)
- `POLL_INTERVAL_MS` (300)
- `CHART_COLORS` (Okabe-Ito: `#E69F00`, `#56B4E9`, `#009E73`, `#F0E442`,
  `#0072B2`, `#D55E00`, `#CC79A7`, `#999999`)

Important state variables:

- `views`, `currentView`, `activeRunId`
- `robotElements`, `previousWarehouseKey`, `updateInProgress`
- `visualizationChart`, `compareChart`, `analysisCharts`,
  `compareMultiSelect`

View DOM ids, v0.5:

`view-setup`, `view-run`, `view-fast`, `view-results`, `view-experiments`,
`view-visualization`, `view-analysis`, `view-compare`

Legacy DOM ids, unchanged:

`warehouse`, `dashboard-grid`, `task-list`, `simulation-state`,
`pause-btn`, `resume-btn`, `reset-btn`

New v0.5 DOM ids:

Nav:

`nav-setup-btn`, `nav-run-btn`, `nav-results-btn`,
`nav-experiments-btn`, `nav-visualization-btn`, `nav-analysis-btn`,
`nav-compare-btn`

Setup:

`cfg-display-name`, `cfg-seed`, `cfg-num-robots`, `cfg-stop-mode`,
`cfg-target-tasks`, `cfg-max-ticks`, `cfg-tick-interval`,
`cfg-blocked-replan-seconds`, `cfg-replan-cooldown-ticks`, `cfg-fast-mode`,
`cfg-battery-capacity`, `cfg-empty-move-energy`, `cfg-loaded-move-energy`,
`cfg-critical-battery`, `cfg-opportunistic-charge-threshold`,
`cfg-charger-capacity`, `cfg-charge-duration-ticks`, `cfg-failure-enabled`,
`cfg-mtbf-ticks`, `cfg-mttr-ticks`, `start-experiment-btn`

New v0.6 Setup DOM ids:

`cfg-path-planner`, `cfg-scheduler`, `cfg-conflict-manager`

Fast:

`fast-status`, `fast-stop-btn`

Results/experiments:

`result-summary`, `experiment-list`, `run-again-btn`,
`view-experiments-btn`, `view-visualization-btn`, `view-analysis-btn`,
`back-to-setup-btn`

Visualization:

`visualization-run-select`, `visualization-metric-select`,
`visualization-generate-btn`, `visualization-chart`

Analysis:

`analysis-run-select`, `analysis-generate-btn`, `analysis-stats`,
`analysis-charts`

Compare:

`compare-run-select` (MultiSelect), `compare-metric-select`,
`compare-chart-type`, `compare-generate-btn`, `compare-chart`

Important functions:

Core, preserved from v0.4:

`refresh()`, `fetchState()`, `postCommand(url)`, `render(state)`,
`buildStaticLayer(warehouse)`, `addCell(x, y, className)`,
`updateRobots(robots, tasks)`, `updateTaskHighlights(state)`,
`highlightLocation(locations, locationName, className)`,
`addTileClass(coord, className)`, `updateSidePanel(state)`,
`createTaskRow(task, isHistory)`, `createMetricCard(title, value, detail)`,
`safeString(value)`, `toNumber(value, fallback)`,
`staticWarehouseKey(warehouse)`

New v0.5:

`initViews()`, `showView(name)`, `on(id, event, handler)`
`formatValue(value)`, `formValue(id)`, `formNumber(id, fallback)`,
`formNumberOrNull(id)`, `formBool(id)`
`readExperimentConfig()` includes `display_name`, `fast_mode`,
`path_planner`, `scheduler`, `conflict_manager`
`startExperiment()` reads config once;
`showView(config.fast_mode ? "fast" : "run")`
`showResults()`, `renderSummary(summary)`
`loadExperiments()` Open + Delete buttons, `deleteExperiment(runId)`
confirm + DELETE
`populateRunSelects()`
`generateVisualization()`, `generateAnalysis()`, `generateComparison()`

Chart helpers:

`getBaseChartOption()`,
`renderLineChart(containerId, series, options)` smooth by default,
`renderStackedAreaChart(containerId, series)`,
`renderBarChart(containerId, categories, values, title)`,
`renderHistogramChart(containerEl, histogram)`

`class MultiSelect` — checkbox dropdown with removable tags;
`setOptions()`, `getSelected()`, `clear()`

Note: v0.4 helpers `shortLabel()` and `addMarker()` were removed in the v0.5
rewrite; no caller remains.

## CSS Classes, UPDATED in v0.6.0, UNCHANGED in v0.8.x

Important v0.6 classes:

- `.setup-grid`
- `.setup-grid .card`
- `.setup-grid .card.full-width`
- `.run-layout`
- `.run-main`
- `.run-sidebar`
- `.run-controls`

Responsive breakpoint at 1100px.

## UI / Visualization, UPDATED in v0.6.0, UNCHANGED in v0.8.x

No v0.7.x or v0.8.x UI changes exist because decision-layer features are
CLI-first and backend-first.

## Deployment Notes

Serve with `gunicorn app:app` or platform equivalent.
Never use the Flask development server when hosted.

`data/runs/` must be on persistent storage.
Ephemeral filesystems lose experiments on restart.

ECharts may load from CDN or be vendored at
`static/vendor/echarts.min.js` for offline/air-gapped hosts.

If the public can start experiments, add authentication and rate limiting.
Experiments consume CPU and disk.
Fast mode pins one core for its duration.

Optimization, Monte Carlo, and robustness studies are CPU-intensive.
For production use, consider queueing, batch scheduling, or dedicated worker
processes.

## Engineering Principles for Decision Layer, v0.8.x

Single-replica results are exploratory.
Single-replica optimizer and multi-objective trials are cheap but noisy.
They identify candidate regions. They do not prove operational robustness.

Robustness verification is mandatory before deployment.
Use `decision/robustness.py` with at least `reps: 20` before treating a
configuration as deployable. If a candidate is close to a constraint boundary,
use `reps: 30` or more.

`constraint_pass_probability` is the critical deployment metric.
A candidate with the lowest mean `cost_per_task` but a 70% constraint pass
probability is not deployable. A slightly more expensive candidate with 95%+
constraint pass probability is usually preferable.

Pareto fronts are candidate sets.
Multi-objective Pareto fronts show tradeoffs. They are not final answers.
Each Pareto candidate should be robustness-checked.

OAT sensitivity does not show interactions.
One-at-a-time sensitivity identifies local parameter influence. It cannot prove
interaction effects. Use full DoE, multi-objective search, or targeted
experiments for interactions.

Infeasible optimization results are valid results.
If `feasible_count` is zero, the optimizer or multi-objective study has proven
that the current search space and constraints are incompatible. Do not relax
this silently. Either widen the search space, relax constraints, or redesign
the operational scenario.

Run artifacts remain immutable.
Monte Carlo, sensitivity, optimizer, multi-objective, and robustness modules
may create new runs. They must never modify existing `data/runs/<run_id>/`
artifacts.

## Recommended v0.8.1 Workflow

1. Define baseline experiment and `CostConfig`.
2. Run a normal simulation or benchmark and produce `data/runs/<run_id>/`.
3. Run Monte Carlo to measure baseline variability.
4. Run sensitivity analysis to identify high-impact parameters.
5. Run single-objective optimization to find a cheap feasible configuration.
6. Run multi-objective optimization to explore cost versus cycle-time tradeoffs.
7. Select Pareto or best candidates.
8. Run robustness verification with `reps >= 20`.
9. Choose the recommended candidate only if `constraint_pass_probability`
   meets the required operational risk threshold.
10. Generate engineering reports from the final verified configuration.

## Extension Points

### Preserved v0.4 extension points

- `INTERSECTION` -> formal intersection traffic control.
- `MAIN_AISLE` -> priority routing or speed changes.
- `PACKING` -> packing queue or processing delay.
- `RECEIVING` -> inbound task generation coupling.
- `SHIPPING` -> outbound task completion coupling.
- `EMPTY` -> dynamic obstacles or editor placement.
- `BUFFER` -> QC delay or put-away scheduling.
- `PICK_STATION` -> pick processing time or queueing.
- `CONSOLIDATION` -> order merge logic.
- `STAGING` -> carrier lane assignment.
- Physical load handoff -> v0.4 uses logical task recovery, not physical
  pallet transfer.
- Predictive maintenance -> not implemented.

### New v0.5 extension points

- SQLite/Parquet storage if CSV experiments grow large.
- Explicit in-simulation event hooks to replace tick-resolution inference.
- Per-robot time-series utilization/blocked columns if summary-level
  distributions become insufficient.
- Server-side analysis caching if hosted traffic grows.

### New v0.6 extension points

- Additional `PathPlanner` implementations plug in through
  `ExperimentConfig.path_planner` and `create_path_planner_from_name`.
  Examples: D* Lite, LPA*, congestion-aware A*.
- Additional `Scheduler` implementations plug in through
  `ExperimentConfig.scheduler` and `create_scheduler_from_name`.
  Examples: Hungarian assignment, rolling horizon optimizer, reinforcement
  learning.
- Additional `ConflictManager` implementations plug in through
  `ExperimentConfig.conflict_manager` and
  `create_conflict_manager_from_name`.
  Examples: one-way aisle policies, intersection signal control, full CBS/ECBS.
- Edge reservations in `ReservationTable` to prevent swap collisions.
- Persist conflict manager diagnostics to summary.json for cross-run comparison.

### New v0.7.1 extension points

- Persist Cost KPIs into `summary.json` or a dedicated `decision.json` artifact.
- Add directional aisle constraints through a dedicated `ConflictManager`.
- Add demand-profile validation against layout location availability before
  run start.
- Add study-level demand factors and layout factors to DoE configs.

### New v0.7.2 extension points

- Frontend heatmap overlay of spatial bottlenecks on the warehouse layout.
- Spatial payload builder in `analysis/web.py`.
- `GET /api/runs/<run_id>/spatial` route once backend is proven.
- Cell-type labeling of bottleneck cells via reconstructed layout presets.

### New v0.8.0 extension points

- Bayesian optimization samplers as alternatives to TPE.
- Sobol quasi-random sequences for sensitivity analysis.
- Variance-based global sensitivity indices beyond OAT.
- Parallel Monte Carlo execution across multiple CPU cores or cluster nodes.
- Persistent Monte Carlo trial registry for cross-study comparison.

### New v0.8.1 extension points

- Multi-fidelity optimization.
- Constrained NSGA-III for many-objective optimization.
- Robust optimization that optimizes worst-case performance across seed
  distributions.
- Surrogate modeling to replace simulation calls in the optimization loop.
- Automated Markdown reports from optimization and robustness studies.
- Frontend optimization dashboards after backend workflows are proven.
- Pareto front comparison API once multi-objective studies are stable.
- Robustness-aware optimizer that directly uses `constraint_pass_probability`
  in the objective or constraint system.