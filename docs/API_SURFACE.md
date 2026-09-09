# API Surface

This document lists the important names used by the warehouse simulator.

If code and documentation disagree, the code is the source of truth, but this file should be updated immediately.

---

## Project State

Project Name: `warehouse_simulator`

Current Version: `v0.8.3`

Previous Documented Version: `v0.8.2`

Version Meaning:

```text
v0.8.3 = v0.8.2 backend + Phase 3 run-linked actions + Setup v0.7.1 demand/layout fields + Phase 4 guided decision forms
v0.8.2 = v0.8.1 backend + Decision Frontend / Decision Web API / Decision Job API / UI refactor
```

Python Version: Python 3.13+ recommended. Pin Python 3.13 if dependency wheels are unstable on newer interpreters.

Dependencies:

```text
Flask
pandas
numpy
ECharts frontend
Optuna required for decision.optimizer and decision.multiobjective
pytest for development/testing
```

Run Command:

```bash
python app.py
```

Production:

```bash
gunicorn app:app
```

Never use the Flask development server when hosted.

---

## Document Update Note for v0.8.2

This revision preserves the old v0.8.1 backend surface.

The following old materials remain valid and must not be treated as removed:

```text
simulation core
battery / charging / failure behavior
traffic / conflict resolution behavior
experiment lifecycle
run storage format
analysis API
decision CLI
decision backend modules
Monte Carlo, sensitivity, optimizer, multi-objective, robustness schemas
benchmark behavior
```

What changed in v0.8.2:

```text
Added decision/web.py
Added decision/jobs.py
Added Decision REST API
Added Decision Job API
Added Decision Center frontend
Refactored frontend from monolithic files into modular templates/CSS/JS
Added job launcher UI
Added job polling UI
Added artifact-opening from finished jobs
Added run-level decision endpoints for cost KPIs and spatial analysis
Deprecated monolithic static/simulation.js
Deprecated monolithic static/style.css
Deprecated monolithic templates/index.html without Jinja partials
```

No simulation core changes.

No `ExperimentConfig` schema changes.

No decision math moved into the frontend.

---

## Document Update Note for v0.8.3

This revision preserves the v0.8.2 backend surface.

The following old materials remain valid and must not be treated as removed:

```text
simulation core
battery / charging / failure behavior
traffic / conflict resolution behavior
experiment lifecycle
run storage format
analysis API
decision CLI
decision backend modules
Monte Carlo, sensitivity, optimizer, multi-objective, robustness schemas
benchmark behavior
Decision Web API
Decision Job API
Decision Center read-only artifact browsers
job launcher and job polling
```

What changed in v0.8.3:

```text
Implemented Phase 3 run-linked actions.
Implemented Setup support for v0.7.1 demand fields.
Implemented Setup support for v0.7.1 layout fields.
Implemented Phase 4 guided decision job forms.
Added static/js/decision_forms.js.
Updated the decision job modal to support guided mode and advanced JSON mode.
Updated static/js/app.js to bind guided modal controls, run-linked action delegation, and Setup demand/layout conditional visibility.
Updated static/js/experiments.js to read v0.7.1 demand/layout fields and render run-linked action buttons.
Updated Results and Experiments views with run-linked decision actions.
Guided forms now exist for:
monte_carlo
sensitivity
report
spatial
optimizer
multiobjective
robustness
study
```

No simulation core changes.

No `ExperimentConfig` schema changes.

No decision math moved into the frontend.

No backend Flask route changes.

No decision backend module changes.

No stored run artifact format changes.

---

## Where The Project Is Now

v0.8.2 is a Decision Frontend and Job API layer built on top of the unchanged v0.8.1 Optimization and Robustness layer, the unchanged v0.8.0 Uncertainty and Risk Analysis layer, the unchanged v0.7.x Decision and Realistic Scenario layers, the unchanged v0.6.0 algorithm plugin layer, the unchanged v0.5.0 experimentation/recording/storage/analysis infrastructure, and the unchanged v0.4.0 battery/charging/failure simulation core.

v0.8.2 adds:

Decision Web API:

```text
decision/web.py
```

Purpose:

```text
Expose decision artifacts as controlled read-only JSON APIs.
```

Decision Job API:

```text
decision/jobs.py
```

Purpose:

```text
Run decision-layer jobs separately from the live experiment runner.
```

Decision Frontend:

```text
Decision Center UI
Decision Overview
Studies browser
Reports browser
Spatial analysis view
Cost KPI view
Monte Carlo browser
Sensitivity browser
Optimization browser
Multi-objective browser
Robustness browser
Jobs view
Job launcher modal
```

Frontend refactor:

```text
templates/index.html became a Jinja shell with view partials
static/style.css was split into static/css/*.css
static/simulation.js was split into static/js/*.js
```

v0.8.3 adds:

Frontend Decision Workflow Completion:

Setup support for v0.7.1 demand fields:

```text
demand_mode
demand_rate_per_tick
demand_task_weights
demand_segments
demand_csv_path
demand_events
```

Setup support for v0.7.1 layout fields:

```text
layout_preset
layout_file
```

Run-linked actions from Results and Experiments:

```text
View cost KPIs from a run
View spatial bottlenecks from a run
Generate report from a run
Start Monte Carlo from a run
Start sensitivity from a run
Use run as optimizer baseline
Use run as multi-objective baseline
```

Guided decision job forms:

```text
Guided mode by default for supported modules
Advanced JSON editor preserved
Inline validation
Cost config template editors
Common constraint editors
Search-space builder for optimizer and multi-objective
Objective builder for multi-objective
Robustness candidate source selection
Study factor builder
```

The v0.8.3 frontend completes the non-CLI decision job launching workflow that was introduced in v0.8.2.

v0.8.1 adds:

Business Optimization:

```text
decision/optimizer.py
```

Optuna-based single-objective optimization with constraint handling.

Multi-Objective Optimization:

```text
decision/multiobjective.py
```

NSGA-II Pareto front generation for tradeoffs such as cost versus p95 cycle time.

Stochastic Robustness Verification:

```text
decision/robustness.py
```

Multi-replica verification of candidate configurations with constraint pass probability.

v0.8.0 adds:

Monte Carlo Runner:

```text
decision/monte_carlo.py
```

Executes N identical scenarios with varying seeds.

Calculates confidence intervals, p5/p95 KPIs, and SLA-violation probability.

Sensitivity Analysis:

```text
decision/sensitivity.py
```

One-at-a-time parameter variation around a baseline.

Outputs tornado data for `cost_per_task` and `p95_cycle_time`.

v0.7.2 adds:

Spatial bottleneck analysis:

```text
Blockage onset coordinates are recorded in events.csv and aggregated into per-cell bottleneck statistics from saved artifacts only.
```

Recorded benchmarks:

```text
benchmark.py records every run through ExperimentRunner into data/runs/<run_id>/.
```

Single-run engineering reports:

```text
decision/report.py can report one run without a study, writing to data/reports/.
```

v0.7.1 adds:

Business KPIs:

```text
Cost KPIs computed from immutable saved run artifacts.
```

Batch experimentation / Design of Experiments:

```text
Factorial study runner.
```

Engineering reporting:

```text
Markdown study reports generated from saved study results.
```

Dynamic demand profiles:

```text
Legacy synthetic demand preserved; uniform, rate schedules, and deterministic CSV/order events added.
```

Configurable layout presets:

```text
Default warehouse preserved; JSON layout definitions and preset layouts added.
```

The v0.6.0 plugin layer remains unchanged:

Path Planning:

```text
PathPlanner
BFSPathPlanner
AStarPathPlanner
```

Scheduling:

```text
Scheduler
CostBasedScheduler
PriorityScheduler
FIFOScheduler
TotalCostScheduler
AuctionScheduler
```

Conflict Resolution:

```text
ConflictManager
LocalYieldConflictManager
ZoneLockConflictManager
PrioritizedReservationConflictManager
```

The v0.5 experimentation layer is unchanged:

```text
experiment/config.py
experiment/factory.py
experiment/recorder.py
experiment/runner.py
data/runs/<run_id>/ immutable storage
analysis/loader.py
analysis/metrics.py
analysis/web.py
```

The v0.4 battery/charging/failure simulation core is unchanged.

The v0.3.1 traffic model is preserved as the `local_yield` baseline.

v0.5 separates six responsibilities:

```text
Simulation (simulation/) — v0.4 core with v0.6 plugin injection points.
Experiment configuration (experiment/config.py) — authoritative run parameters.
Metrics recorder (experiment/recorder.py) — observes, never modifies.
Experiment runner (experiment/runner.py) — lifecycle, stopping, saving.
Data storage (data/runs/<run_id>/) — immutable per-run artifacts.
Visualization/analysis (analysis/ + frontend) — reads saved data only.
```

The simulation does not depend on plotting.

The plotting system never needs live simulation objects.

A completed experiment is fully reproducible and analyzable from its saved files.

The UI is a multi-stage workflow, not one dashboard:

```text
Setup
Run live or Fast headless
Results
Experiments
Visualization
Analysis
Compare
Decision
```

View transitions are a client-side state machine; the backend never redirects.

v0.7.x and v0.8.x decision modules may execute new experiments through `ExperimentRunner`, but they must never modify existing run artifacts.

Derived decision artifacts are stored in their own directories under `data/`.

v0.8.2 decision jobs may execute backend decision modules that internally create new runs, but they must not hijack the live experiment runner.

---

## Breaking Changes / Changes From v0.8.2 (v0.8.3)

### Frontend Layer

Added:

```text
static/js/decision_forms.js
```

Purpose:

```text
Guided decision job forms.
Guided/advanced modal behavior.
Inline job config validation.
Client-side config builders for decision jobs.
```

Important guided modules:

```text
monte_carlo
sensitivity
report
spatial
optimizer
multiobjective
robustness
study
```

Updated:

```text
static/js/app.js
```

Added bindings for:

```text
decision-job-use-guided
decision-job-toggle-json
guided module change behavior
run-linked action delegation using `[data-run-action]`
Setup demand/layout conditional visibility
```

Updated:

```text
static/js/experiments.js
```

Added Setup v0.7.1 field reading:

```text
demand_mode
demand_rate_per_tick
demand_task_weights
demand_segments
demand_csv_path
demand_events
layout_preset
layout_file
```

Added Phase 3 support:

```text
Results decision action visibility
Experiments row decision actions
run-linked action buttons using data-run-action and data-run-id
```

Updated:

```text
static/js/decision.js
```

Added Phase 3 run-linked helpers:

```text
DEFAULT_EXAMPLE_COST_CONFIG
ensureRunSelectValue
uniqueSortedInts
buildSensitivityFactorValues
buildRunLinkedSearchSpace
buildRunLinkedConfig
fetchRunSummarySafe
showRunActionError
prepareDecisionRunSelect
goToCostKpisForRun
goToSpatialForRun
openRunLinkedJobModal
handleRunLinkedAction
```

Updated templates:

```text
templates/views/setup.html
templates/views/results.html
templates/views/experiments.html
templates/modals/job_modal.html
```

### Setup Changes

Setup now exposes v0.7.1 demand fields.

Recommended DOM IDs:

```text
cfg-demand-mode
cfg-demand-rate-per-tick
cfg-demand-task-weights
cfg-demand-segments
cfg-demand-csv-file
cfg-demand-events
cfg-layout-preset
cfg-layout-file
```

Conditional containers:

```text
demand-uniform-fields
demand-rate-schedule-fields
demand-csv-fields
```

`readExperimentConfig()` now includes these fields using backend snake_case keys.

Demand mode behavior:

```text
legacy:
no additional demand fields

uniform:
demand_rate_per_tick
demand_task_weights

rate_schedule:
demand_segments

csv_orders:
demand_csv_path
demand_events
```

Layout behavior:

```text
layout_preset is exposed.
layout_file is exposed as an optional local trusted relative path input.
```

Important file policy:

```text
Demand CSV and layout file inputs are currently local trusted relative-path inputs.
They are acceptable for local single-user development.
For hosted deployments, they must be replaced by admin-managed dropdowns or validated uploads.
```

### Decision Job Modal Changes

The decision job modal now supports guided mode.

New modal IDs:

```text
decision-job-use-guided
decision-job-guided
decision-job-json-wrapper
decision-job-toggle-json
decision-job-guided-error
```

Guided behavior:

```text
When guided mode is enabled, the modal renders a module-specific guided form.
When guided mode is disabled, the modal uses the raw JSON editor.
When a Phase 3 run-linked action supplies a prefilled config object, the modal opens in advanced JSON mode.
Guided forms do not attempt to reverse-parse arbitrary Phase 3 JSON back into guided controls.
```

### Run-Linked Action Changes

Results now contains a decision action card:

```text
results-decision-actions-card
```

Run-linked actions use:

```text
data-run-action
data-run-id
```

Supported `data-run-action` values:

```text
cost
spatial
report
monte_carlo
sensitivity
optimizer
multiobjective
```

Behavior:

```text
cost:
opens Decision -> Cost KPIs and selects the run

spatial:
opens Decision -> Spatial and selects the run

report:
opens job modal with report config

monte_carlo:
opens job modal with Monte Carlo config prefilled from run

sensitivity:
opens job modal with sensitivity config prefilled from run

optimizer:
opens job modal with optimizer config prefilled from run

multiobjective:
opens job modal with multi-objective config prefilled from run
```

### v0.8.3 Non-Changes

```text
No simulation core changes.
No `ExperimentConfig` schema changes.
No decision backend module changes.
No Flask decision API route changes.
No decision job API route changes.
No decision math moved to the frontend.
No stored run artifact format changes.
No changes to Monte Carlo, sensitivity, optimizer, multi-objective, or robustness backend schemas.
```

---

## Breaking Changes / Changes From v0.8.1 (v0.8.2)

### Decision Web Layer

Added:

```text
decision/web.py
```

Important factory:

```python
create_decision_blueprint(
    data_dir: Path | str,
    runs_dir: Path | str,
) -> Blueprint
```

Purpose:

```text
Expose read-only decision artifacts as controlled JSON APIs.
```

Added decision read routes:

```text
GET /api/decision/overview

GET /api/decision/studies
GET /api/decision/studies/<study_id>
GET /api/decision/studies/<study_id>/results

GET /api/decision/reports
GET /api/decision/reports/<report_id>

GET /api/decision/monte-carlo
GET /api/decision/monte-carlo/<mc_id>
GET /api/decision/monte-carlo/<mc_id>/results

GET /api/decision/sensitivity
GET /api/decision/sensitivity/<study_id>
GET /api/decision/sensitivity/<study_id>/results
GET /api/decision/sensitivity/<study_id>/tornado

GET /api/decision/optimizations
GET /api/decision/optimizations/<opt_id>
GET /api/decision/optimizations/<opt_id>/trials

GET /api/decision/multiobjective
GET /api/decision/multiobjective/<study_id>
GET /api/decision/multiobjective/<study_id>/trials
GET /api/decision/multiobjective/<study_id>/pareto

GET /api/decision/robustness
GET /api/decision/robustness/<robust_id>
GET /api/decision/robustness/<robust_id>/results

GET /api/runs/<run_id>/cost-kpis
GET /api/runs/<run_id>/spatial
```

Important behavior:

```text
Decision read APIs read saved artifacts only.
IDs are validated.
Payloads are sanitized.
Large tables are paginated.
Full CSV files are not sent to the browser.
NaN becomes null.
Infinity becomes null.
numpy scalars are converted where possible.
```

ID validation pattern:

```text
^[A-Za-z0-9_\-]+$
```

Invalid IDs return 404.

### Decision Job Layer

Added:

```text
decision/jobs.py
```

Important classes:

```python
DecisionJob
DecisionJobManager
DecisionJobError
DecisionJobNotFoundError
DecisionJobConflictError
```

Important factory:

```python
create_decision_jobs_blueprint(manager: DecisionJobManager) -> Blueprint
```

Added job routes:

```text
POST /api/decision/jobs
GET /api/decision/jobs
GET /api/decision/jobs/<job_id>
POST /api/decision/jobs/<job_id>/cancel
```

Supported job modules:

```text
study
report
spatial
monte_carlo
sensitivity
optimizer
multiobjective
robustness
```

Current concurrency policy:

```text
one decision job at a time
```

Current cancellation policy:

```text
queued jobs can be cancelled
running jobs cannot be cancelled yet
finished/failed/cancelled jobs cannot be cancelled
```

Current persistence policy:

```text
job state is in-memory only
job list is lost on Flask restart
generated artifacts remain on disk
```

### Flask Layer

`app.py` UPDATED in v0.8.2.

Added imports:

```python
from decision.web import create_decision_blueprint
from decision.jobs import DecisionJobManager, create_decision_jobs_blueprint
```

Added decision data root:

```python
base_dir = Path(base_data_dir)
data_dir = base_dir.parent
```

For default configuration:

```text
base_dir = data/runs
data_dir = data
```

Added decision job manager:

```python
decision_job_manager = DecisionJobManager(
    data_dir=data_dir,
    runs_dir=base_dir,
    max_workers=1,
)
```

Registered decision blueprints:

```python
app.register_blueprint(
    create_decision_blueprint(
        data_dir=data_dir,
        runs_dir=base_dir,
    )
)

app.register_blueprint(
    create_decision_jobs_blueprint(decision_job_manager)
)
```

Existing routes remain unchanged:

```text
GET /
GET /api/state
POST /api/pause
POST /api/resume
POST /api/reset

POST /api/experiment/start
GET /api/experiment/state
POST /api/experiment/stop
GET /api/experiment/summary

GET /api/runs
DELETE /api/runs/<run_id>
GET /api/runs/compare/series
GET /api/runs/<run_id>/summary
GET /api/runs/<run_id>/series
GET /api/runs/<run_id>/distributions
```

### Frontend Layer

The frontend was refactored from monolithic files into modular files.

Deprecated monolithic files:

```text
templates/index.html as a single giant file
static/style.css as a single giant file
static/simulation.js as a single giant file
```

New frontend structure:

```text
templates/
├── index.html
├── views/
│   ├── setup.html
│   ├── run.html
│   ├── fast.html
│   ├── results.html
│   ├── experiments.html
│   ├── visualization.html
│   ├── analysis.html
│   ├── compare.html
│   └── decision.html
└── modals/
    └── job_modal.html

static/
├── css/
│   ├── theme.css
│   ├── layout.css
│   ├── warehouse.css
│   └── decision.css
└── js/
    ├── utils.js
    ├── state.js
    ├── charts.js
    ├── warehouse.js
    ├── experiments.js
    ├── decision.js
    ├── decision_forms.js
    └── app.js
```

Important note:

```text
The ECharts wrapper module is static/js/charts.js.
If a local file was accidentally named chart.js, it must be renamed to charts.js or the script tag must be corrected.

Important note:
`static/js/decision_forms.js` must load after `static/js/decision.js` and before `static/js/app.js`.
It overrides guided job modal behavior, including `openJobModal` and `submitJob`.
```

Correct script load order:

```html
<script src="/static/js/utils.js"></script>
<script src="/static/js/state.js"></script>
<script src="/static/js/charts.js"></script>
<script src="/static/js/warehouse.js"></script>
<script src="/static/js/experiments.js"></script>
<script src="/static/js/decision.js"></script>
<script src="/static/js/decision_forms.js"></script>
<script src="/static/js/app.js"></script>
```

ECharts must load before the JS modules that render charts.

CDN form:

```html
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
```

Offline/vendored form:

```html
<script src="/static/vendor/echarts.min.js"></script>
```

### v0.8.2 Non-Changes

No simulation core changes.

No `ExperimentConfig` schema changes.

No changes to decision math modules.

No changes to stored run artifact format.

No changes to Monte Carlo, sensitivity, optimizer, multi-objective, or robustness backend schemas.

No decision math moved to the frontend.

### v0.8.3 Known Limitations

Frontend limitations:

```text
Advanced decision charts are not implemented yet.
Spatial heatmap overlay is not implemented yet.
Demand CSV and layout file selection use local trusted relative-path text inputs, not managed dropdowns or uploads.
Guided robustness supports multi-objective study IDs and explicit candidates JSON, but not direct optimizer-summary import.
Guided forms do not parse arbitrary Phase 3 prefilled JSON back into guided controls; Phase 3 prefills open in Advanced JSON mode.
Study guided form supports simple factor entry, but does not yet provide factorial-size estimation or advanced DoE validation.
```

Job system limitations:

```text
Job state is in-memory only.
Jobs are lost from the UI on Flask restart.
Running jobs cannot be cancelled.
Progress reporting is not implemented.
Template endpoints are not implemented.
File selection/upload endpoints are not implemented.
```

Decision API limitations:

```text
Cost KPI endpoint currently accepts cost config as URL-encoded JSON.
Report indexing currently focuses on data/reports single-run reports.
Study report browsing may require navigation through study detail depending on implementation.
Spatial jobs do not currently produce a dedicated stored artifact directory.
```

---

## Breaking Changes / Changes From v0.3.1 (v0.4.0)

### Core Architecture

Added `simulation/config.py` containing `BatteryConfig`, `ChargingConfig`, and `FailureConfig`.

Added `simulation/charging.py` containing `ChargingStation`.

`Simulation` constructor now accepts keyword-only v0.4 arguments:

```text
battery_config
charging_config
failure_config
seed
```

`Simulation` now owns:

```text
charging-station state
maintenance-cell scanning
failure RNG
dynamic resume-location tracking
congestion snapshots
```

Added:

```text
task interruption, recovery, and reassignment logic
battery drain from actual movement
loaded movement consuming more energy than empty movement
critical battery, opportunistic charging, and empty-battery recovery
robot failures, repair time, and maintenance relocation
battery urgency in yield scoring
taskless routing helper _route_robot_to_cell() for charger and maintenance movement
```

### Data Models

`Robot` gained `RobotMode` and v0.4 battery/charging/failure fields.

`Task` gained:

```text
LoadState
INTERRUPTED status
interruption count
last-assigned robot
resume-location fields
```

`Metrics` gained battery, charging, waiting-breakdown, interruption, failure, and congestion-related fields/methods.

### Frontend / CLI

`benchmark.py` accepts v0.4 battery, charging, and failure parameters.

`optimize_optuna.py` accepts fixed v0.4 parameters and optional `--search-v04` mode.

Frontend supports:

```text
Interrupted tasks
robot mode/battery tooltips
v0.4 dashboard metrics
```

CSS adds styles for interrupted tasks and robot battery/charging/failure states.

---

## Breaking Changes / Changes From v0.4.0 (v0.5.0)

Added `experiment/` package:

```text
config.py
factory.py
recorder.py
runner.py
```

Added `analysis/` package:

```text
loader.py
metrics.py
web.py
```

`app.py` uses a mutable holder:

```python
holder = {
    "simulation": ...,
    "runner": ...
}
```

The v0.4 closure-based single-simulation wiring is gone.

`create_default_simulation()` replaced by:

```python
create_simulation_from_config(ExperimentConfig.default())
```

Robot creation is dynamic and seeded; old hardcoded 13-position list gone.

No robot-count cap beyond available passable cells.

`ExperimentConfig` gained:

```text
display_name
fast_mode
```

`display_name` is label only.

`fast_mode` affects pacing only; fast_mode never affects results.

New routes:

```text
experiment lifecycle
run deletion
analysis JSON API
```

Frontend rewritten:

```text
view state machine
MultiSelect component
ECharts charts
experiment delete
legend
fast-run progress view
```

CSS rewritten:

```text
dark theme
flat borderless tiles
glow-only task/location highlights
square robots
```

New persistent storage layout under:

```text
data/runs/
```

`benchmark.py` and `optimize_optuna.py` unchanged.

---

## Breaking Changes / Changes From v0.5.0 (v0.6.0)

### Core Architecture

`simulation/pathfinding.py` UPDATED:

Added:

```text
PathPlanner protocol
BFSPathPlanner
AStarPathPlanner
```

`find_shortest_path()` preserved as backward-compatible wrapper delegating to `BFSPathPlanner`.

`simulation/scheduler.py` UPDATED:

Added:

```text
PriorityScheduler
FIFOScheduler
TotalCostScheduler
AuctionScheduler
```

Existing:

```text
CostBasedScheduler
```

All implement the `Scheduler` protocol.

Added `simulation/conflict.py` containing:

```text
ConflictManager protocol
LocalYieldConflictManager
ZoneLockConflictManager
PrioritizedReservationConflictManager
```

Added `simulation/reservations.py` containing:

```text
ReservationTable
```

`Simulation` constructor gained keyword-only:

```text
path_planner
```

`Simulation` gained:

```python
set_conflict_manager()
```

`Simulation` gained internal state:

```text
_conflict_manager
```

Initialized to:

```python
LocalYieldConflictManager(self)
```

`Simulation._tick()` now calls:

```python
self._conflict_manager.tick()
```

before:

```python
_advance_robots()
```

`Simulation._advance_robots()` now calls:

```python
self._conflict_manager.allow_step()
```

before the occupied-cell check.

`Simulation._congestion_snapshot()` reads:

```python
self._conflict_manager.active_conflicts
```

All conflict-related private methods moved from `Simulation` into `LocalYieldConflictManager`.

### Experiment Configuration

`ExperimentConfig` gained:

```text
path_planner: str = "bfs"
conflict_manager: str = "local_yield"
```

`ExperimentConfig.__post_init__` validates:

```text
path_planner against PATH_PLANNER_CHOICES
conflict_manager against CONFLICT_MANAGER_CHOICES
```

### Factory

`experiment/factory.py` gained:

```text
create_path_planner_from_name(name)
create_scheduler_from_name(name, path_planner)
create_conflict_manager_from_name(name, sim)
create_path_planner(config)
create_scheduler(config, path_planner)
create_conflict_manager(config, sim)
```

`create_simulation_from_config()` now creates and injects the configured scheduler, path planner, and conflict manager.

### CLI

`benchmark.py` gained:

```text
--path-planner
--scheduler
--conflict-manager
```

Choices:

```text
path-planner: bfs, astar, weighted_astar
scheduler: baseline, priority, fifo, total_cost, auction
conflict-manager: local_yield, zone_locks, priority_reservation
```

Defaults:

```text
--path-planner bfs
--scheduler baseline
--conflict-manager local_yield
```

`benchmark.py` prints active path planner, scheduler, and conflict manager class names before running.

`benchmark.py` prints conflict manager diagnostics after running.

### Frontend

Setup view gained three algorithm dropdowns:

```text
cfg-path-planner
cfg-scheduler
cfg-conflict-manager
```

Setup view uses `.setup-grid` two-column card layout.

Run view restructured:

```text
.run-layout flex container
.run-main warehouse/legend
.run-sidebar controls/dashboard/task list
```

Pause/Resume/Reset buttons moved to `.run-controls` at top of sidebar.

`readExperimentConfig()` includes:

```text
path_planner
scheduler
conflict_manager
```

### CSS

Added:

```text
.setup-grid
.setup-grid .card
.setup-grid .card.full-width
.run-layout
.run-main
.run-sidebar
.run-controls
```

Added responsive breakpoint at 1100px.

---

## Breaking Changes / Changes From v0.6.0 (v0.7.1)

### Decision Layer

Added `decision/` package.

`decision/cost.py`:

```text
CostConfig dataclass for run-level business costs.
```

`decision/kpis.py`:

```text
CostKPIs
compute_cost_kpis()
compute_cost_kpis_for_run_id()
```

Reads saved artifacts only.

`decision/study.py`:

```text
StudyConfig
StudyRunner
```

Executes factorial DoE matrices and outputs:

```text
data/studies/<study_id>/results.csv
```

`decision/report.py`:

```text
generate_report()
```

Generates Markdown engineering reports from study results.

`decision/demand.py`:

```text
DemandConfig
DemandModel
DemandTaskGenerator
```

Supports:

```text
legacy
uniform
rate_schedule
csv_orders
```

`decision/layout.py`:

```text
LayoutConfig
PRESET_LAYOUTS
```

Supports:

```text
default
high_density
one_way_aisles
```

### Experiment Configuration

`ExperimentConfig` gained additive v0.7.1 fields with backward-compatible defaults:

```text
demand_mode
demand_rate_per_tick
demand_task_weights
demand_segments
demand_csv_path
demand_events
layout_preset
layout_file
```

`ExperimentConfig.__post_init__` validates demand and layout fields.

### Factory

`experiment/factory.py` gained:

```text
create_task_generator(config, warehouse)
```

`create_simulation_from_config()` now builds the warehouse using:

```python
decision.layout.create_warehouse_for_experiment()
```

and the task generator using:

```python
create_task_generator()
```

Default behavior remains unchanged.

### Storage Format

Run storage structure is unchanged.

`config.json` gained the new v0.7.1 keys.

New study storage layout added under:

```text
data/studies/<study_id>/
```

---

## Breaking Changes / Changes From v0.7.1 (v0.7.2)

### Experiment Layer

`ExperimentRunner._snapshot()` now extracts per-robot `x` and `y`.

`MetricsRecorder` writes:

```json
{"x": ..., "y": ...}
```

JSON into the `details` column of `robot_blocked` events.

`events.csv` schema is unchanged.

### Decision Layer

Added `decision/spatial.py`:

```text
SpatialCellLoad
SpatialBlockageResult
compute_spatial_blockage()
top_bottleneck_cells()
_pair_blocked_episodes()
```

`decision/report.py` gained:

```python
generate_run_report(run_id, base_dir=None)
```

Single-run reports are written to:

```text
data/reports/<run_id>_report.md
```

Never inside:

```text
data/runs/
```

Study reports gained a Spatial Bottleneck Analysis section.

`python -m decision.report` gained:

```text
--run-id
--base-dir
```

`--run-id` is mutually exclusive with `--study-dir`.

### Decision CLI

Added:

```bash
python -m decision.spatial --run-id <run_id>
```

Options:

```text
--base-dir
--top
--by blocked_ticks|blocked_events
--json
```

### CLI Layer

`benchmark.py` now records every run through `ExperimentRunner`.

Benchmark wall-clock times are no longer comparable to pre-v0.7.2 runs due to recording overhead.

### Storage

Run storage structure is unchanged.

Pre-v0.7.2 runs have empty `details` on `robot_blocked` rows.

Spatial analysis reports them with coverage 0.0.

Added:

```text
data/reports/
```

for single-run Markdown reports.

`results.csv` carries `run_id` so each study row traces back to:

```text
data/runs/<run_id>/
```

---

## Breaking Changes / Changes From v0.7.2 (v0.8.0)

### Decision Layer

Added:

```text
decision/monte_carlo.py
decision/sensitivity.py
```

Monte Carlo:

```text
Executes N identical experiment configurations with different seeds.
Calculates confidence intervals, p5/p95 KPIs, and SLA violation statistics.
Writes derived artifacts to data/monte_carlo/<mc_id>/.
Each trial writes a normal immutable run artifact to data/runs/<run_id>/.
```

Sensitivity:

```text
Performs one-at-a-time parameter variation around a baseline configuration.
Uses multiple replications per factor level.
Writes results.csv, tornado.csv, and summary.json to data/sensitivity/<study_id>/.
Each non-reused trial writes a normal immutable run artifact to data/runs/<run_id>/.
```

No simulation core changes.

No `ExperimentConfig` schema changes.

No frontend changes at the time.

---

## Breaking Changes / Changes From v0.8.0 (v0.8.1)

### Decision Layer

Added:

```text
decision/optimizer.py
decision/multiobjective.py
decision/robustness.py
```

Single-objective optimization:

```text
Optuna TPESampler.
Constraint handling through Optuna constraints_func.
Explicit feasible/infeasible reporting.
Writes data/optimizations/<opt_id>/summary.json.
```

Multi-objective optimization:

```text
Optuna NSGAIISampler.
Pareto front extraction from feasible trials.
Writes data/multiobjective/<study_id>/summary.json, trials.json, and pareto.csv.
```

Robustness verification:

```text
Multi-replica candidate verification.
Calculates constraint_pass_probability.
Recommends candidates only when constraint pass probability meets min_pass_probability.
Writes data/robustness/<robust_id>/results.csv and summary.json.
```

No simulation core changes.

No `ExperimentConfig` schema changes.

No frontend changes at the time.

Optuna becomes required for optimization modules.

---

## Important Code Default Note

The actual v0.3.1 code defaults are:

```text
blocked_replan_seconds = 0.7
replan_cooldown_ticks = 7
```

Older documentation may mention `0.9` and `2`.

The code defaults are the source of truth.

---

## Coordinate System

Coordinates are `(x, y)`.

```text
x increases to the right.
y increases downward.
Origin is the top-left corner.
```

---

## Naming Rules

### Python

```text
Classes use PascalCase.
Functions and variables use snake_case.
Private methods start with _.
Enum members use UPPER_SNAKE_CASE.
```

### Stored Experiment Config

Stored `config.json` keys use `snake_case` because they map directly to `ExperimentConfig` fields.

### Live Frontend JSON API

Live `/api/state` and related frontend payloads use the established camelCase keys from v0.4/v0.5/v0.6.

Decision-layer payloads added in v0.8.2 preserve backend snake_case keys.

### JavaScript

```text
Functions and variables use camelCase.
DOM element variables usually end with El.
```

---

## Python Modules

### `simulation/config.py`, NEW in v0.4.0

Configuration dataclasses for v0.4 features.

#### `BatteryConfig`

```python
@dataclass(frozen=True)
class BatteryConfig
```

Fields:

```text
capacity: float = 100.0
empty_move_energy: float = 0.35
loaded_move_energy: float = 0.5
critical_battery: float = 15.0
opportunistic_charge_threshold: float = 30.0
idle_ticks_before_opportunistic_charge: int = 10
safety_margin: float = 5.0
empty_battery_recovery_ticks: int = 15
```

Methods:

```text
move_cost(loaded: bool) -> float
is_critical(battery: float) -> bool
is_opportunistic_candidate(battery: float) -> bool
```

Important behavior:

```text
empty_move_energy is consumed per successful empty movement step.
loaded_move_energy is consumed per successful loaded movement step.
Battery consumption must come from actual movement, not elapsed time.
critical_battery forces charging behavior.
opportunistic_charge_threshold allows idle robots to charge after the idle threshold.
safety_margin is added to estimated remaining task energy during feasibility checks.
empty_battery_recovery_ticks is the minimum downtime when battery reaches zero.
```

#### `ChargingConfig`

```python
@dataclass(frozen=True)
class ChargingConfig
```

Fields:

```text
capacity: int = 4
charge_duration_ticks: int = 10
```

Important behavior:

```text
capacity is logical station capacity.
Physical CHARGING cells can further constrain simultaneous charging.
If the map has fewer usable charging cells than capacity, effective physical charging may be lower.
```

#### `FailureConfig`

```python
@dataclass(frozen=True)
class FailureConfig
```

Fields:

```text
enabled: bool = False
mtbf_ticks: float = 0.0
mttr_ticks: int = 25
seed: int | None = None
relocate_to_maintenance: bool = True
```

Important behavior:

```text
mtbf_ticks <= 0 disables random failures.
mttr_ticks is repair duration.
If relocate_to_maintenance is true, failed/dead robots are moved/towed to a MAINTENANCE cell.
If false, failed robots remain where they failed and become obstacles.
```

---

### `simulation/charging.py`, NEW in v0.4.0

Finite-capacity charging resource model.

#### `ChargingStation`

```python
@dataclass
class ChargingStation
```

Fields:

```text
capacity: int
charge_duration_ticks: int
active: dict[str, int]
active_cells: dict[str, tuple[int, int]]
reserved_cells: dict[str, tuple[int, int]]
waiting: set[str]
```

Meaning:

```text
active — robot_id -> remaining charging ticks.
active_cells — robot_id -> charging cell.
reserved_cells — robot_id -> reserved cell.
waiting — robot ids waiting for charger capacity.
```

Properties:

```text
occupancy -> int
has_capacity -> bool
```

Methods:

```text
is_charging(robot_id: str) -> bool
is_waiting(robot_id: str) -> bool
add_waiting(robot_id: str) -> None
remove_waiting(robot_id: str) -> None
reserve(robot_id: str, cell: tuple[int, int]) -> bool
release_reservation(robot_id: str) -> None
begin_charging(robot_id: str, cell: tuple[int, int]) -> bool
release(robot_id: str) -> None
is_cell_active(cell: tuple[int, int]) -> bool
is_cell_reserved(cell: tuple[int, int]) -> bool
tick() -> list[str]
```

Important behavior:

```text
Active robots occupy capacity.
Waiting robots do not occupy capacity.
Reserved robots hold capacity while traveling to a charging cell.
has_capacity accounts for active plus reserved robots.
begin_charging() converts a reservation into active charging, or takes an unreserved slot if capacity allows.
tick() advances charging timers and returns robot ids that finished.
```

---

### `simulation/warehouse.py`

#### `CellType`

```python
class CellType(str, Enum)
```

Members:

```text
EMPTY
SHELF
AISLE
MAIN_AISLE
PACKING
RECEIVING
SHIPPING
CHARGING
INTERSECTION
BUFFER
PICK_STATION
CONSOLIDATION
STAGING
MAINTENANCE
```

Values should be the same as member names:

```python
CellType.EMPTY.value == "EMPTY"
CellType.SHELF.value == "SHELF"
CellType.CHARGING.value == "CHARGING"
CellType.MAINTENANCE.value == "MAINTENANCE"
```

Important:

```text
Enum values and layout symbol keys must not contain trailing spaces.
Correct: "EMPTY", not "EMPTY ".
Correct: ".", not ". ".
```

#### `LAYOUT_SYMBOLS`

```python
LAYOUT_SYMBOLS: dict[str, CellType]
```

Supported layout symbols:

```text
. -> EMPTY
E -> EMPTY
# -> SHELF
a -> AISLE
M -> MAIN_AISLE
P -> PACKING
R -> RECEIVING
S -> SHIPPING
C -> CHARGING
I -> INTERSECTION
B -> BUFFER
K -> PICK_STATION
O -> CONSOLIDATION
G -> STAGING
X -> MAINTENANCE
```

#### `Location`

```python
@dataclass(frozen=True)
class Location
```

Fields:

```text
location.name: str
location.cell: tuple[int, int]
location.access: tuple[int, int]
```

Meaning:

```text
cell is the physical cell the location represents.
access is the passable cell an AMR actually drives to.
```

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

```text
warehouse.width: int
warehouse.height: int
warehouse.layout: list[list[CellType]]
warehouse.locations: dict[str, Location]
```

Public methods:

```text
warehouse.in_bounds(x: int, y: int) -> bool
warehouse.cell_type(x: int, y: int) -> CellType
warehouse.is_blocked(x: int, y: int) -> bool
warehouse.resolve(name: str) -> tuple[int, int]
warehouse.to_dict() -> dict[str, Any]
```

Property:

```text
warehouse.obstacles -> frozenset[tuple[int, int]]
```

Private methods:

```text
warehouse._parse_layout(layout) -> list[list[CellType]]
warehouse._validate() -> None
warehouse._rack_anchors() -> dict[str, list[int]]
```

Important behavior:

```text
is_blocked() returns True for out-of-bounds cells.
is_blocked() returns True for SHELF cells.
All other cell types are passable.
resolve() returns the location's access coordinate and raises KeyError for unknown names.
_validate() checks that every location's cell and access are in bounds and that access is not blocked.
_rack_anchors() returns one anchor cell per rack letter.
```

v0.4 dynamically adds `RESUME-*` locations to `warehouse.locations` during simulation runtime for interrupted loaded tasks.

`Simulation.get_state()` should strip dynamic `RESUME-*` locations from the serialized warehouse payload to avoid unnecessary frontend rebuilds.

---

### `simulation/robot.py`, UPDATED in v0.4.0

#### `RobotStatus`

```python
class RobotStatus(str, Enum)
```

Members:

```text
IDLE = "Idle"
MOVING = "Moving"
```

#### `RobotMode`, NEW in v0.4.0

```python
class RobotMode(str, Enum)
```

Members:

```text
IDLE
MOVING
TO_CHARGER
WAITING_FOR_CHARGER
CHARGING
FAILED
REPAIRING
```

Important behavior:

```text
RobotStatus remains backward compatible with v0.3 UI consumers.
RobotMode carries richer v0.4 operational state.
A robot may have status == Idle while mode == Charging or mode == Waiting for charger.
```

#### `Robot`

```python
@dataclass
class Robot
```

Existing fields:

```text
robot.id: str
robot.x: int
robot.y: int
robot.color: str
robot.status: RobotStatus
robot.path: list[tuple[int, int]]
robot.current_task_id: str | None
robot.route_goal: tuple[int, int] | None
robot.blocked_ticks: int
robot.replanning: bool
robot.yielding_to: str | None
robot.replan_cooldown: int
robot.travel_history: list[tuple[int, int]]
robot.temporary_path: bool
```

New v0.4 fields:

```text
robot.battery: float
robot.mode: RobotMode
robot.idle_ticks: int
robot.charger_wait_ticks: int
robot.interrupted_task_id: str | None
robot.charge_target: tuple[int, int] | None
robot.charge_start_battery: float | None
robot.repair_remaining_ticks: int
```

Property:

```text
robot.current_target -> tuple[int, int] | None
```

Public methods:

```text
robot.set_path(path: list[tuple[int, int]]) -> None
robot.set_temporary_path(path: list[tuple[int, int]]) -> None
robot.advance() -> bool
robot.to_dict() -> dict[str, Any]
```

Important behavior:

```text
set_path() expects a path excluding the robot's current cell.
advance() moves the robot one cell.
advance() returns True when the robot reaches the end of its path.
route_goal is the current final destination for the robot's current task phase or taskless movement target.
travel_history stores previously visited cells and is used for backtracking during yield maneuvers.
battery must never become negative.
idle_ticks is used for opportunistic charging.
charger_wait_ticks counts waiting for charger capacity, not active charging time.
interrupted_task_id allows a robot to attempt to reclaim its own interrupted task after charging/repair if the task is still unassigned.
```

---

### `simulation/task.py`, UPDATED in v0.4.0

#### `TaskType`

```python
class TaskType(str, Enum)
```

Members:

```text
PUTAWAY
PICK
PACK
SHIP
LEGACY
```

#### `TaskStatus`

```python
class TaskStatus(str, Enum)
```

Members:

```text
PENDING = "Pending"
ASSIGNED = "Assigned"
COMPLETED = "Completed"
FAILED = "Failed"
INTERRUPTED = "Interrupted"
```

`INTERRUPTED` is NEW in v0.4.0.

#### `TaskPhase`

```python
class TaskPhase(str, Enum)
```

Members:

```text
TO_PICKUP = "To pickup"
TO_DROPOFF = "To dropoff"
DONE = "Done"
```

#### `LoadState`, NEW in v0.4.0

```python
class LoadState(str, Enum)
```

Members:

```text
ON_SHELF = "On shelf"
CARRIED = "Carried"
STAGED = "Staged"
DELIVERED = "Delivered"
```

Important behavior:

```text
LoadState is a logical cargo state, not full physical pallet handling.
If a loaded task is interrupted, the load remains associated with the task and is logically staged at a resume location.
```

#### `Task`

```python
@dataclass
class Task
```

Existing fields:

```text
task.id: str
task.name: str
task.pickup: str
task.dropoff: str
task.task_type: TaskType
task.priority: int
task.created_at: int
task.completed_at: int | None
task.status: TaskStatus
task.assigned_robot_id: str | None
task.phase: TaskPhase
```

New v0.4 fields:

```text
task.load_state: LoadState
task.interruption_count: int
task.last_assigned_robot_id: str | None
task.resume_location_name: str | None
```

Public methods:

```text
task.to_dict() -> dict[str, Any]
```

Important behavior:

```text
pickup and dropoff are location names, resolved to coordinates via warehouse.resolve().
If a loaded task is interrupted, pickup may be rewritten to a temporary RESUME-* location name.
INTERRUPTED tasks remain claimable by another robot.
interruption_count supports reassignment metrics.
last_assigned_robot_id supports reassignment detection.
```

---

### `simulation/task_generator.py`

#### `TaskGenerator`

```python
@dataclass
class TaskGenerator
```

Constructor fields:

```text
warehouse: Warehouse
start_tick: int = 2
seed: int | None = None
```

Public methods:

```text
task_generator.step(tick: int) -> list[Task]
task_generator.reset() -> None
```

Private methods:

```text
_refresh_location_cache() -> None
_create_task(task_type: TaskType, tick: int) -> Task
_pick_one(values: list[str], fallback: str | None = None) -> str
_priority_for(task_type: TaskType) -> int
_interval_for(task_type: TaskType) -> int
```

Important behavior:

```text
Generates tasks during the simulation instead of seeding all work at startup.
Emits a light stream of PUTAWAY, PICK, PACK, and SHIP tasks using existing named locations.
```

Priority mapping, lower number = higher priority:

```text
SHIP = 0
PACK = 1
PICK = 2
PUTAWAY = 3
```

If `seed` is an int, random location selection is reproducible.

If `seed` is None, deterministic round-robin behavior is preserved.

Reset re-seeds with the same seed.

---

### `simulation/pathfinding.py`, UPDATED in v0.6.0

#### `PathPlanner`, NEW in v0.6.0

```python
class PathPlanner(Protocol)
```

Method:

```python
find_path(warehouse, start, goal, blocked_cells=None) -> list[tuple[int, int]] | None
```

Return meaning:

```text
[] — already at the goal.
[...] — path cells after start.
None — no path found.
```

#### `BFSPathPlanner`, NEW in v0.6.0

```python
class BFSPathPlanner
```

Implements `PathPlanner`.

Uses BFS.

Returns shortest paths.

This is the default planner and produces identical results to the v0.5 `find_shortest_path`.

#### `AStarPathPlanner`, NEW in v0.6.0

```python
class AStarPathPlanner
```

Constructor:

```python
AStarPathPlanner(weight: float = 1.0)
```

Implements `PathPlanner`.

Uses A* with Manhattan heuristic.

```text
weight = 1.0: Standard A*. On a uniform 4-connected grid, returns shortest paths like BFS, but may choose a different shortest path when ties exist.
weight > 1.0: Weighted A*. Faster search, but paths may be suboptimal.
```

#### `find_shortest_path`, preserved

```python
find_shortest_path(
    warehouse: Warehouse,
    start: tuple[int, int],
    goal: tuple[int, int],
    blocked_cells: Iterable[tuple[int, int]] | None = None,
) -> list[tuple[int, int]] | None
```

Backward-compatible wrapper.

Delegates to a module-level `BFSPathPlanner` instance.

Existing modules that still import `find_shortest_path` will keep working.

New code should use an injected `PathPlanner` instead.

---

### `simulation/scheduler.py`, UPDATED in v0.6.0

#### `Assignment`

```python
@dataclass(frozen=True)
class Assignment
```

Fields:

```text
assignment.task_id: str
assignment.robot_id: str
assignment.cost: int
assignment.path: list[tuple[int, int]]
```

#### `Scheduler`

```python
class Scheduler(Protocol)
```

Method:

```python
select_assignments(pending_tasks, robots, warehouse, blocked_cells=None) -> list[Assignment]
```

#### `CostBasedScheduler`

```python
class CostBasedScheduler
```

Baseline scheduler.

Chooses the idle robot with the shortest feasible path to each pending task pickup.

Processes tasks by:

```text
(-priority, created_at, id)
```

Constructor accepts optional `path_planner` keyword argument.

Defaults to:

```python
BFSPathPlanner()
```

#### `PriorityScheduler`, NEW in v0.6.0

```python
class PriorityScheduler
```

Nearest-pickup dispatcher with correct priority ordering.

Processes tasks by:

```text
(priority, created_at, id)
```

where lower `priority` value = higher urgency.

For each task, assigns the nearest feasible robot to the pickup.

#### `FIFOScheduler`, NEW in v0.6.0

```python
class FIFOScheduler
```

Nearest-pickup dispatcher that processes oldest tasks first.

Processes tasks by:

```text
(created_at, priority, id)
```

For each task, assigns the nearest feasible robot to the pickup.

#### `TotalCostScheduler`, NEW in v0.6.0

```python
class TotalCostScheduler
```

Battery/energy-aware scheduler.

For each task, computes the estimated total cost as:

```text
distance_to_pickup + distance_pickup_to_dropoff
```

Assigns the robot with the lowest total cost.

Constructor accepts optional:

```text
path_planner
empty_move_energy
loaded_move_energy
safety_margin
critical_battery
```

#### `AuctionScheduler`, NEW in v0.6.0

```python
class AuctionScheduler
```

Centralized first-price auction approximation.

Each remaining task receives bids from each remaining robot.

The lowest total bid wins.

Bid cost is:

```text
distance_to_pickup + distance_pickup_to_dropoff
```

Iterates until all tasks or robots are exhausted.

---

### `simulation/conflict.py`, NEW in v0.6.0

#### `ConflictManager`

```python
class ConflictManager(Protocol)
```

Methods:

```text
handle_blocked_robot(robot, next_cell) -> None
advance_replanning_robot(robot, occupied) -> None
release_conflict(robot) -> None
clear_conflicts_for_robot(robot) -> None
reset() -> None
tick(current_tick: int, robots: list[Robot]) -> None
allow_step(robot, next_cell, occupied) -> bool
release_robot(robot_id: str) -> None
```

Property:

```text
active_conflicts -> int
```

#### `LocalYieldConflictManager`

```python
class LocalYieldConflictManager
```

Constructor:

```python
LocalYieldConflictManager(sim: Simulation)
```

Baseline reactive conflict manager.

Contains all the v0.3.1 traffic/conflict resolution logic previously in `Simulation`.

`tick()` and `allow_step()` are no-ops.

`release_robot()` is a no-op.

Important behavior:

```text
Preserves the v0.3.1 local deadlock-recovery mechanism exactly.
handle_blocked_robot(), advance_replanning_robot(), release_conflict(), clear_conflicts_for_robot() implement the existing yield logic.
_make_robot_yield(), _select_yielding_robot(), _yield_score(), _can_yield(), _choose_yield_step() are private helpers.
_complete_yield() resumes normal routing after a yield maneuver.
```

#### `ZoneLockConflictManager`, NEW in v0.6.0

```python
class ZoneLockConflictManager
```

Constructor:

```python
ZoneLockConflictManager(sim: Simulation, lookahead: int = 2)
```

Inherits from `LocalYieldConflictManager`.

Adds proactive path-corridor zone locks on top of the reactive local yield system.

Important behavior:

```text
tick() rebuilds zone locks from each robot's current path.
Claims the next lookahead cells on each robot's path.
Robots are sorted by _yield_score(); less willing to yield claims first.
allow_step() denies a step if the target cell is locked by another robot, unless the robot has been blocked for too long.
Starvation fallback: blocked_ticks >= blocked_replan_threshold_ticks * 2.
Failed, repairing, and charging robots do not create claims.
```

Diagnostic counters:

```text
denied_steps
locks_created
tick_calls
robots_with_paths
```

#### `PrioritizedReservationConflictManager`, NEW in v0.6.0

```python
class PrioritizedReservationConflictManager
```

Constructor:

```python
PrioritizedReservationConflictManager(sim: Simulation, horizon: int = 32)
```

Inherits from `LocalYieldConflictManager`.

Adds approximate prioritized reservation-based conflict management on top of the reactive local yield system.

Important behavior:

```text
tick() rebuilds vertex reservations from each robot's current path using a ReservationTable.
Robots are sorted by a priority score. Higher score reserves first.
Priority score considers robot mode, task priority, loaded status, battery urgency, and blocked time.
allow_step() denies a step if the target cell is reserved by another robot at the next tick, unless the robot has been blocked for too long.
Starvation fallback: blocked_ticks >= blocked_replan_threshold_ticks * 2.
Failed, repairing, and charging robots do not create reservations.
```

Diagnostic counters:

```text
denied_steps
reservations_created
tick_calls
robots_with_paths
```

This is not full space-time MAPF.

It is a practical proactive traffic manager for experimentation.

---

### `simulation/reservations.py`, NEW in v0.6.0

#### `ReservationTable`

```python
class ReservationTable
```

Simple vertex reservation table.

Tracks which robot intends to occupy which cell at which tick.

Does not track edge reservations, so swap collisions are not fully covered.

Fields:

```text
_vertex_reservations: dict[tuple[int, int], dict[int, str]]
_robot_reservations: dict[str, set[tuple[tuple[int, int], int]]]
```

Meaning:

```text
_vertex_reservations — cell -> tick -> robot_id.
_robot_reservations — robot_id -> set of reserved (cell, tick) pairs.
```

Methods:

```text
reset() -> None
reserve(robot_id: str, cell: tuple[int, int], tick: int) -> bool
owner(cell: tuple[int, int], tick: int) -> str | None
is_free(cell: tuple[int, int], tick: int, robot_id: str) -> bool
release_robot(robot_id: str) -> None
prune(current_tick: int) -> None
```

---

### `simulation/metrics.py`, UPDATED in v0.4.0

#### `Metrics`

```python
@dataclass
class Metrics
```

Existing v0.3 fields:

```text
metrics.tasks_generated: int
metrics.tasks_assigned: int
metrics.tasks_completed: int
metrics.tasks_failed: int
metrics.blocked_time_ticks: int
metrics.replanning_count: int
metrics.deadlock_resolutions: int
metrics.task_waiting_time_total: float
metrics.task_completion_time_total: float
metrics.robot_distance_travelled: dict[str, int]
metrics.robot_busy_ticks: dict[str, int]
metrics.robot_total_ticks: dict[str, int]
metrics.robot_blocked_ticks: dict[str, int]
metrics.robot_replan_events: dict[str, int]
metrics.tick_count: int
```

New v0.4 fields:

```text
metrics.battery_capacity: float
metrics.battery_sum: float
metrics.battery_samples: int
metrics.charging_events: int
metrics.total_charging_ticks: int
metrics.charger_wait_ticks: int
metrics.charger_wait_events: int
metrics.traffic_wait_ticks: int
metrics.station_wait_ticks: int
metrics.battery_task_interruptions: int
metrics.failure_task_interruptions: int
metrics.task_reassignments: int
metrics.failed_robot_events: int
metrics.failure_downtime_ticks: int
```

Existing methods:

```text
metrics.reset() -> None
metrics.register_robot(robot: Robot) -> None
metrics.record_generated(task: Task) -> None
metrics.record_assigned(task: Task, tick: int) -> None
metrics.record_completed(task: Task, tick: int) -> None
metrics.record_failed(task: Task, tick: int) -> None
metrics.record_blocked(robot: Robot, blocked_ticks: int = 1) -> None
metrics.record_replan(robot: Robot) -> None
metrics.record_deadlock_resolution() -> None
metrics.record_robot_move(robot: Robot, distance: int = 1) -> None
metrics.record_tick(robots: list[Robot]) -> None
metrics.to_dict(tick_interval: float) -> dict[str, Any]
```

New v0.4 methods:

```text
metrics.record_battery_sample(robot: Robot) -> None
metrics.record_charging_start() -> None
metrics.record_charging_tick() -> None
metrics.record_charger_wait_start() -> None
metrics.record_charger_wait_tick() -> None
metrics.record_battery_task_interruption() -> None
metrics.record_failure_task_interruption() -> None
metrics.record_task_reassignment() -> None
metrics.record_failed_robot_event() -> None
metrics.record_failure_downtime_tick() -> None
```

Important behavior:

```text
Existing v0.3 metric keys remain unchanged.
Blocked time is also counted as traffic waiting.
Active charging time is not waiting time.
Waiting for a free charger slot is charger waiting.
Battery samples are used to compute average battery.
Charger waiting events are used to compute average charger wait.
```

---

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

```text
simulation.start() -> None
simulation.pause() -> None
simulation.resume() -> None
simulation.reset() -> None
simulation.stop() -> None
simulation.get_state() -> dict[str, Any]
simulation.set_conflict_manager(manager: ConflictManager) -> None
```

`set_conflict_manager()` is NEW in v0.6.0.

Property:

```text
simulation.is_paused -> bool
```

Important internal state:

Existing:

```text
simulation._warehouse
simulation._robots
simulation._tasks
simulation._initial_robots
simulation._initial_tasks
simulation._tick_count
simulation._tick_interval
simulation._lock
simulation._stop_event
simulation._running_event
simulation._thread
simulation._blocked_replan_threshold_ticks
simulation._replan_cooldown_ticks
```

New v0.4:

```text
simulation._battery_cfg
simulation._charging_cfg
simulation._failure_cfg
simulation._charging_station
simulation._charging_cells
simulation._maintenance_cells
simulation._failure_seed
simulation._failure_rng
simulation._dynamic_location_names
```

New v0.6:

```text
simulation._path_planner
simulation._conflict_manager
```

Defaults:

```text
_path_planner defaults to BFSPathPlanner()
_conflict_manager defaults to LocalYieldConflictManager(self)
```

Important behavior:

```text
start() starts the background simulation thread.
pause() stops ticking but keeps state.
resume() continues ticking.
reset() restores robots and tasks to their initial state, clears conflict manager state via self._conflict_manager.reset(), clears dynamic resume locations, resets charging station state, resets failure RNG, and restores robot batteries/modes.
set_conflict_manager() replaces the active conflict manager and rebinds its _sim reference.
get_state() returns a JSON-serializable snapshot.
get_state() should strip dynamic RESUME-* locations from the warehouse payload.
_tick() runs failures/repairs, charging station progression, task generation, assignment, battery checks, opportunistic charging, conflict manager tick, robot movement, metrics, and pruning.
_advance_robots() calls self._conflict_manager.allow_step() before the occupied-cell check. Replanning/yielding robots are NOT gated by allow_step() so deadlock escape still works.
_prune_old_tasks() deletes completed/failed tasks whose completed_at is more than 100 ticks old. Interrupted tasks are not pruned.
```

---

## Traffic / Conflict Resolution Behavior

### v0.3.1 Local Yield, preserved as `local_yield`

When a robot's next cell is occupied by another robot, the blocked robot increments `blocked_ticks`.

After `blocked_replan_seconds` the conflict becomes eligible for yielding.

For each blocking pair, only one robot may replan at a time.

The selected yielder is stored in `_active_conflict_yielder`.

The non-yielding robot's route is frozen during the conflict.

The yielding robot receives a local yield step from `_choose_yield_step()`.

Yield step preference:

```text
A neighboring cell that still allows reaching the current route_goal.
A backtrack step through recent travel_history.
Any safe escape neighbor, biased away from the blocker.
```

A valid yield step must be:

```text
in bounds
not a shelf
not occupied
not claimed by another robot's immediate next target
```

If the preferred yielder is stationary it can be forced to yield.

If the preferred yielder cannot act quickly enough, the blocked robot yields instead.

If the active yielder appears inactive for too long, the blocked robot takes over.

`_can_yield()` prevents a robot from participating in more than one active conflict and enforces `replan_cooldown`.

`_attempt_resume_route()` resumes normal BFS routing after a yield maneuver.

`_advance_replanning_robot()` retries a different local yield step if the current yield step stays blocked for 2+ ticks.

`_release_conflict()` clears the pair record when the yielder moves.

`_clear_conflicts_for_robot()` removes stale conflicts when a robot begins a task, arrives, interrupts, fails, or starts charging.

This is a local deadlock-recovery mechanism.

It is not reservation-based multi-agent pathfinding and does not implement intersection control.

### v0.4 Yield Score Additions

`_yield_score()` still uses idle status, task priority, and blocked time.

Battery urgency reduces willingness to yield.

Critical battery robots are strongly protected from unnecessary yielding.

Failed, repairing, and actively charging robots cannot yield.

Battery is one factor, not the only factor.

### v0.6 Zone Locks, `zone_locks`

Proactive path-corridor zone locks on top of reactive local yield.

Each tick, `tick()` rebuilds zone locks from each robot's current path.

Claims the next `lookahead` cells, default 2, on each robot's path.

Robots are sorted by `_yield_score()`; less willing to yield claims first.

`allow_step()` denies a step if the target cell is locked by another robot.

Starvation fallback:

```text
blocked_ticks >= blocked_replan_threshold_ticks * 2
```

Failed, repairing, and charging robots do not create claims.

Diagnostic counters:

```text
denied_steps
locks_created
tick_calls
robots_with_paths
```

### v0.6 Priority Reservation, `priority_reservation`

Approximate prioritized reservation-based conflict management on top of reactive local yield.

Each tick, `tick()` rebuilds vertex reservations from each robot's current path using a `ReservationTable`.

Robots are sorted by a priority score.

Higher-priority robots reserve first.

Priority score considers:

```text
robot mode
task priority
loaded status
battery urgency
blocked time
```

`allow_step()` denies a step if the target cell is reserved by another robot at the next tick.

Starvation fallback:

```text
blocked_ticks >= blocked_replan_threshold_ticks * 2
```

Failed, repairing, and charging robots do not create reservations.

Diagnostic counters:

```text
denied_steps
reservations_created
tick_calls
robots_with_paths
```

This is not full space-time MAPF.

It is a practical proactive traffic manager for experimentation.

---

## Battery / Charging / Failure Behavior, v0.4.0

### Battery Simulation

Every robot has a battery value.

Battery decreases only from actual successful movement.

Loaded movement consumes more energy than empty movement.

Battery cannot become negative.

Battery feasibility includes a safety margin.

Initial route estimates are not guaranteed to remain valid.

### Battery-Aware Routing

When a task is assigned, the simulation estimates whether the route is battery-feasible.

During execution, the simulation estimates energy required to complete the current remaining route.

Battery feasibility is re-evaluated after:

```text
task assignment
arrival at pickup
successful movement
route resumption
yield-step assignment
replanning or detours
```

If the remaining task becomes infeasible, the robot interrupts the task and seeks charging.

The robot must not blindly continue until battery reaches zero.

### Charging Decisions

Critical battery:

```text
If battery <= critical threshold, the robot seeks charging.
If active task cannot be safely finished, the task is interrupted.
Critical charging has priority over opportunistic charging.
```

Insufficient for task:

```text
If remaining battery < estimated remaining task energy + safety margin, the task is interrupted.
Task state is preserved.
The robot goes to charging.
After charging, the robot may reclaim the task if it is still unassigned.
Another robot may claim the interrupted task before then.
```

Opportunistic charging:

Idle robots may charge if:

```text
they have no task
they have been idle for idle_ticks_before_opportunistic_charge
battery is below opportunistic_charge_threshold
charger capacity is available
a usable charging cell is available
```

Idle robots do not charge immediately.

### Charging Station Behavior

Charging station has finite logical capacity.

Default capacity is 4 robots.

Charging duration is configurable.

Active charging robots occupy slots.

Reserved robots occupy slots while traveling to charge.

Waiting robots do not occupy slots.

Waiting robots should not stand on charging cells.

If a waiting robot is on a charging cell and cannot charge, it is relocated off the charging cell.

When capacity opens, waiting robots are dispatched deterministically.

### Task Interruption / Reassignment

Task interruption reasons:

```text
critical_battery
insufficient_for_task
no_feasible_route
empty_battery
failure
```

Interrupt behavior:

```text
The task is preserved.
Task progress/state is preserved.
The robot is removed from the task.
The task becomes Interrupted.
The task becomes claimable by another robot.
The original robot remembers the interrupted task and may reclaim it after charging/repair if it is still unassigned.
Normal traffic conflicts do not automatically interrupt tasks.
```

Load behavior:

```text
If interrupted before pickup, load remains On shelf.
If interrupted while carrying, load becomes Staged at a logical resume location.
If another robot claims the resumed task, it routes to the resume location, then to dropoff.
```

This is operational/logical recovery, not detailed physical pallet handling.

### Empty Battery Behavior

If battery reaches zero:

```text
active task is interrupted
robot becomes failed/down
robot is relocated to maintenance if enabled
robot remains down for at least empty_battery_recovery_ticks
after recovery, battery is restored
```

### Failure / Repair Behavior

Random failures are optional and controlled by `FailureConfig.enabled`.

`mtbf_ticks` controls average ticks between failures.

`mttr_ticks` controls repair duration.

Failed robots stop moving and stop executing tasks.

Failed robots cannot yield.

Failed robots remain occupied cells unless relocated.

If `relocate_to_maintenance` is true, failed/dead robots are moved/towed to a `MAINTENANCE` cell.

After repair, robots return to service.

After repair, robots may reclaim their interrupted task if still available.

If no task is reclaimed and the robot is on a maintenance cell, it tries to move out of maintenance.

---

## Decision Layer Modules, UPDATED in v0.8.2

### `decision/cost.py`

#### `CostConfig`

```python
@dataclass(frozen=True)
class CostConfig
```

Fields:

```text
robot_opex_per_hour: float = 0.0
charger_infra_cost_per_hour: float = 0.0
downtime_cost_per_hour: float = 0.0
sla_target_ticks: int | None = None
sla_penalty_per_late_tick: float = 0.0
currency: str = "USD"
```

Important behavior:

```text
All monetary rates must be finite and >= 0.
CapEx and Energy costs are intentionally excluded at the run level.
sla_target_ticks is expressed in simulation ticks.
```

---

### `decision/kpis.py`

#### `CostKPIs`

```python
@dataclass(frozen=True)
class CostKPIs
```

Fields:

```text
total_operating_cost: float
cost_per_task: float | None
sla_compliance_rate: float | None
completed_tasks: int
sla_evaluated_tasks: int
late_tasks: int
simulation_seconds: float
currency: str
cost_breakdown: dict[str, float]
```

Functions:

```text
compute_cost_kpis(run_data, cost_config) -> CostKPIs
compute_cost_kpis_for_run_id(run_id, cost_config, base_dir=None) -> CostKPIs
```

Important behavior:

```text
Reads saved artifacts only.
Handles zero completed tasks.
cost_per_task is None when completed_tasks is zero.
sla_compliance_rate is None when no SLA-evaluated tasks exist.
```

---

### `decision/study.py`

Important names:

```text
StudyConfig
StudyRunner
```

Important behavior:

```text
Executes factorial DoE matrices.
Outputs data/studies/<study_id>/results.csv.
results.csv carries a run_id column so each row traces back to data/runs/<run_id>/ artifacts.
Study execution writes normal immutable run artifacts for each experiment row.
```

CLI:

```bash
python -m decision.study --config <study_config.json>
```

---

### `decision/report.py`

Functions:

```text
generate_report(study_dir: str | Path) -> Path
generate_run_report(run_id: str, base_dir: str | None = None) -> Path
```

`generate_run_report()` is NEW in v0.7.2.

Important behavior:

```text
Generates Markdown engineering reports.
Study reports include trade-off observations.
Study reports include a Spatial Bottleneck Analysis section when spatial data is available.
Single-run reports include configuration, KPIs, distributions, and spatial bottleneck tables.
Single-run reports are written to data/reports/<run_id>_report.md.
Reports never modify data/runs/<run_id>/.
```

CLI:

```bash
python -m decision.report --study-dir <study_dir>
python -m decision.report --run-id <run_id> [--base-dir DIR]
```

`--study-dir` and `--run-id` are mutually exclusive.

---

### `decision/spatial.py`, NEW in v0.7.2

#### `SpatialCellLoad`

```python
@dataclass(frozen=True)
class SpatialCellLoad
```

Fields:

```text
x: int
y: int
blocked_events: int
blocked_ticks: int
```

#### `SpatialBlockageResult`

```python
@dataclass(frozen=True)
class SpatialBlockageResult
```

Fields:

```text
run_id: str
total_blocked_events: int
events_with_coordinates: int
coverage: float
cells: list[SpatialCellLoad]
```

Property:

```text
has_data -> bool
```

Method:

```text
top_cells(n: int = 5, by: str = "blocked_ticks") -> list[SpatialCellLoad]
```

Functions:

```text
compute_spatial_blockage(run_data) -> SpatialBlockageResult
top_bottleneck_cells(run_data, top_n=5) -> list[SpatialCellLoad]
_pair_blocked_episodes(events, final_tick)
```

CLI:

```bash
python -m decision.spatial --run-id <run_id> [--base-dir DIR] [--top N] [--by blocked_ticks|blocked_events] [--json]
```

Important behavior:

```text
Reads saved artifacts only.
robot_blocked rows must carry {"x": ..., "y": ...} JSON in details for v0.7.2+ runs.
Pre-v0.7.2 runs are reported with coverage 0.0.
Episodes are paired locally from robot_blocked/robot_unblocked events.
Unclosed episodes are censored at summary.json simulation_ticks.
blocked_ticks are attributed to the onset cell.
A robot can drift during yield, so exact cells are approximate.
Hotspots near chargers indicate capacity problems.
Hotspots at aisle intersections indicate traffic-control problems.
```

---

### `decision/demand.py`

Important names:

```text
DemandMode
DemandEvent
RateSegment
DemandConfig
DemandModel
DemandTaskGenerator
```

Supported demand modes:

```text
legacy
uniform
rate_schedule
csv_orders
```

Important behavior:

```text
legacy preserves the original synthetic TaskGenerator behavior.
New demand modes integrate through experiment/factory.create_task_generator().
Demand behavior is controlled by ExperimentConfig demand fields.
```

---

### `decision/layout.py`

Important names:

```text
LayoutConfig
PRESET_LAYOUTS
create_warehouse_for_experiment()
```

Supported layout presets:

```text
default
high_density
one_way_aisles
```

Important behavior:

```text
default preserves the original warehouse layout.
JSON-based layout definitions are supported.
Layout validation includes bounds, passable access cells, and required functional cells.
```

---

### `decision/monte_carlo.py`, NEW in v0.8.0

#### `MonteCarloConfig`

```python
@dataclass(frozen=True)
class MonteCarloConfig
```

Fields:

```text
base_config: dict[str, Any]
n_runs: int
base_seed: int | None = None
seeds: list[int]
sla_target_ticks: int | None = None
cost_config: CostConfig | None = None
force_fast_mode: bool = True
output_dir: str = "data/monte_carlo"
runs_base_dir: str = DEFAULT_RUNS_DIR
```

#### `MonteCarloResult`

```python
@dataclass(frozen=True)
class MonteCarloResult
```

Fields:

```text
mc_id: str
output_dir: Path
results_csv: Path
summary_json: Path
n_runs_requested: int
successful_runs: int
failed_runs: int
aggregate: dict[str, Any]
```

Functions:

```text
generate_seeds(n_runs, base_seed=None, explicit_seeds=None) -> list[int]
build_trial_config(base_config, seed, index, force_fast_mode=True) -> dict[str, Any]
extract_run_metrics(run_id, runs_base_dir, cost_config=None, sla_target_ticks=None) -> dict[str, Any]
run_monte_carlo(mc_config: MonteCarloConfig) -> MonteCarloResult
```

CLI:

```bash
python -m decision.monte_carlo --config <base_config.json> --n <runs>
python -m decision.monte_carlo --from-run-id <run_id> --n <runs>
```

Common options:

```text
--n
--base-seed
--seeds
--sla-target-ticks
--cost-config
--output-dir
--runs-base-dir
```

Important behavior:

```text
Executes N identical experiment configurations with different seeds.
Each trial writes a normal immutable run artifact to data/runs/<run_id>/.
Monte Carlo derived artifacts are written to data/monte_carlo/<mc_id>/.
force_fast_mode is True by default because Monte Carlo should be headless.
fast_mode only removes wall-clock pacing and does not change simulation results.
summary.json contains errors when trials fail.
results.csv contains per-trial metrics.
Aggregate includes mean, standard deviation, min, p05, median, p95, max, and normal-approximation confidence intervals for mean KPIs.
SLA statistics include both task_late_probability and run_any_violation_probability.
```

SLA metric interpretation:

```text
task_late_probability is the fraction of completed tasks that violated the SLA target.
run_any_violation_probability is the fraction of Monte Carlo trials where at least one task violated the SLA target.
task_late_probability is usually the more operationally meaningful SLA metric.
```

---

### `decision/sensitivity.py`, NEW in v0.8.0

#### `FactorSpec`

```python
@dataclass(frozen=True)
class FactorSpec
```

Fields:

```text
name: str
values: list[Any]
```

#### `SensitivityConfig`

```python
@dataclass(frozen=True)
class SensitivityConfig
```

Fields:

```text
base_config: dict[str, Any]
factors: list[FactorSpec]
reps: int = 3
base_seed: int | None = None
sla_target_ticks: int | None = None
cost_config: CostConfig | None = None
force_fast_mode: bool = True
output_dir: str = "data/sensitivity"
runs_base_dir: str = DEFAULT_RUNS_DIR
```

#### `SensitivityResult`

```python
@dataclass(frozen=True)
class SensitivityResult
```

Fields:

```text
study_id: str
output_dir: Path
results_csv: Path
summary_json: Path
tornado_csv: Path
successful_runs: int
failed_runs: int
baseline: dict[str, Any]
factor_results: list[dict[str, Any]]
tornado: dict[str, list[dict[str, Any]]]
errors: list[dict[str, Any]]
```

Functions:

```text
run_sensitivity(cfg: SensitivityConfig) -> SensitivityResult
extract_sensitivity_metrics(run_id, runs_base_dir, cost_config=None, sla_target_ticks=None) -> dict[str, Any]
```

CLI:

```bash
python -m decision.sensitivity --config <sensitivity_config.json>
```

Important behavior:

```text
Performs one-at-a-time, OAT, parameter variation around a baseline configuration.
Each factor level is evaluated with reps replications.
The same seed set is used across factor levels for paired comparison.
If a factor value equals the baseline value, baseline runs are reused.
Writes results.csv, tornado.csv, and summary.json.
Each non-reused sensitivity trial writes a normal immutable run artifact to data/runs/<run_id>/.
Tornado output is sorted by absolute delta.
Default tornado targets are cost_per_task and p95_cycle_time.
OAT sensitivity does not reveal interaction effects.
```

`extract_sensitivity_metrics` adds:

```text
p95_cycle_time
feasibility flags
optional cost KPI fields
optional direct SLA compliance fields
```

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

---

### `decision/optimizer.py`, NEW in v0.8.1

#### `SearchSpaceSpec`

```python
@dataclass(frozen=True)
class SearchSpaceSpec
```

Fields:

```text
name: str
type: str
low: float | None = None
high: float | None = None
choices: list[Any] | None = None
```

Supported `type` values:

```text
int
float
categorical
```

#### `OptimizerConfig`

```python
@dataclass(frozen=True)
class OptimizerConfig
```

Fields:

```text
base_config: dict[str, Any]
search_space: list[SearchSpaceSpec]
objective: str = "cost_per_task"
direction: str = "minimize"
n_trials: int = 50
reps: int = 1
base_seed: int | None = None
constraints: dict[str, float]
sla_target_ticks: int | None = None
cost_config: CostConfig | None = None
force_fast_mode: bool = True
output_dir: str = "data/optimizations"
runs_base_dir: str = DEFAULT_RUNS_DIR
timeout: float | None = None
```

Functions:

```text
suggest_param(trial, spec: SearchSpaceSpec) -> Any
run_optimization(cfg: OptimizerConfig) -> dict[str, Any]
```

CLI:

```bash
python -m decision.optimizer --config <optimizer_config.json>
```

Common options:

```text
--n-trials
--reps
--base-seed
--timeout
--cost-config
```

Important behavior:

```text
Uses Optuna TPESampler.
Uses constrained optimization through Optuna constraints_func.
constraints_func is marked experimental by Optuna. The warning is expected.
Evaluates each trial with reps replications.
Use reps: 1 for cheap exploration.
Use robustness verification before deploying any optimizer result.
Writes data/optimizations/<opt_id>/summary.json.
Explicitly reports feasible_count and infeasible_count.
best_trial is selected from feasible trials only.
best_trial is null when no feasible trial exists.
```

Primary supported constraints:

```text
p95_cycle_time_max
sla_compliance_rate_min
```

Constraint semantics:

```text
p95_cycle_time_max is satisfied when p95_cycle_time <= limit.
sla_compliance_rate_min is satisfied when sla_compliance_rate >= limit.
```

Supported objective metrics:

```text
cost_per_task
p95_cycle_time
average_throughput
tasks_completed
```

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

---

### `decision/multiobjective.py`, NEW in v0.8.1

#### `ObjectiveSpec`

```python
@dataclass(frozen=True)
class ObjectiveSpec
```

Fields:

```text
metric: str
direction: str = "minimize"
```

#### `MultiObjectiveConfig`

```python
@dataclass(frozen=True)
class MultiObjectiveConfig
```

Fields:

```text
base_config: dict[str, Any]
search_space: list[SearchSpaceSpec]
objectives: list[ObjectiveSpec]
constraints: dict[str, float]
n_trials: int = 50
reps: int = 1
base_seed: int | None = None
population_size: int | None = None
sla_target_ticks: int | None = None
cost_config: CostConfig | None = None
force_fast_mode: bool = True
output_dir: str = "data/multiobjective"
runs_base_dir: str = DEFAULT_RUNS_DIR
timeout: float | None = None
```

Functions:

```text
run_multiobjective(cfg: MultiObjectiveConfig) -> dict[str, Any]
_pareto_trials(trials, directions) -> list[dict[str, Any]]
_dominates(a, b, directions) -> bool
```

CLI:

```bash
python -m decision.multiobjective --config <multiobjective_config.json>
```

Common options:

```text
--n-trials
--reps
--base-seed
--timeout
--cost-config
```

Important behavior:

```text
Uses Optuna NSGAIISampler.
Supports multiple objectives.
Typical use is minimizing cost_per_task while minimizing p95_cycle_time.
Uses cheap single-replica evaluations by default.
Feasibility is evaluated after simulation.
The Pareto front is extracted from feasible trials only.
If feasible_count is zero, the search space or constraints are too strict.
Writes summary.json, trials.json, and pareto.csv.
summary.json includes base_config and cost_config so robustness verification can inherit them.
Pareto candidates are not deployable until verified by decision/robustness.py.
```

Constraint key convention in multi-objective and robustness modules:

```text
<metric>_max
<metric>_min
```

Examples:

```text
p95_cycle_time_max
sla_compliance_rate_min
cost_per_task_max
total_blocked_ticks_max
average_cycle_time_max
```

Constraint satisfaction rule:

```text
For <metric>_max, value <= limit.
For <metric>_min, value >= limit.
```

Allowed metrics for objectives and generic constraints:

```text
cost_per_task
p95_cycle_time
average_cycle_time
average_throughput
tasks_completed
sla_compliance_rate
total_blocked_ticks
```

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

---

### `decision/robustness.py`, NEW in v0.8.1

#### `RobustnessCandidate`

```python
@dataclass(frozen=True)
class RobustnessCandidate
```

Fields:

```text
label: str
overrides: dict[str, Any]
```

#### `RobustnessConfig`

```python
@dataclass(frozen=True)
class RobustnessConfig
```

Fields:

```text
base_config: dict[str, Any]
candidates: list[RobustnessCandidate]
reps: int = 20
base_seed: int | None = None
constraints: dict[str, float]
objective: str = "cost_per_task"
direction: str = "minimize"
min_pass_probability: float = 0.95
sla_target_ticks: int | None = None
cost_config: CostConfig | None = None
force_fast_mode: bool = True
output_dir: str = "data/robustness"
runs_base_dir: str = DEFAULT_RUNS_DIR
```

Functions:

```text
run_robustness(cfg: RobustnessConfig) -> dict[str, Any]
_evaluate_constraints_for_rows(rows, constraints) -> dict[str, Any]
_summarize_metrics(rows) -> dict[str, Any]
```

CLI:

```bash
python -m decision.robustness --config <robustness_config.json>
```

Common options:

```text
--reps
--base-seed
--min-pass-probability
```

Important behavior:

```text
Verifies candidate configurations under stochastic variation.
Runs each candidate with many seeds.
reps: 20 is the practical minimum for deployment decisions.
Uses the same seed set across candidates for paired comparison.
Calculates constraint_pass_probability for each candidate.
constraint_pass_probability is the fraction of replications satisfying all constraints.
A candidate is robust_pass when constraint_pass_probability >= min_pass_probability.
recommended is null when no candidate meets min_pass_probability.
Writes results.csv and summary.json.
Each replication writes a normal immutable run artifact to data/runs/<run_id>/.
```

Candidate sources:

```text
Explicit candidates list in robustness config.
from_multiobjective path pointing to a multi-objective summary.json.
Multi-objective Pareto trials can be selected automatically.
Single-objective best_trial can be used if present in an optimizer summary.
```

Important robustness rule:

```text
Do not deploy single-replica optimizer or Pareto candidates without robustness verification.
```

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

---

### `decision/web.py`, NEW in v0.8.2

Purpose:

```text
Expose decision artifacts as controlled read-only JSON APIs.
```

Important factory:

```python
create_decision_blueprint(
    data_dir: Path | str,
    runs_dir: Path | str,
) -> Blueprint
```

Important internal helpers:

```text
_is_safe_id()
_sanitize()
_read_json()
_generated_at_for_dir()
_dir_artifact_summary()
_reports_summary()
_read_csv_page()
_page_args()
_cost_config_from_request()
_list_artifact_dirs()
_get_artifact_dir()
_read_summary()
_paginate_list()
_read_json_list()
_load_trials_from_artifact()
_load_tornado_payload()
```

Important behavior:

```text
Reads saved artifacts only.
Validates IDs.
Sanitizes JSON.
Paginates large tables.
Does not send full CSV files.
Does not modify run artifacts.
Does not compute decision math.
```

ID validation pattern:

```text
^[A-Za-z0-9_\-]+$
```

Sanitization rules:

```text
NaN -> null
Infinity -> null
numpy scalars -> native Python values where possible
Path -> POSIX string
dataclasses -> dict
```

---

### `decision/jobs.py`, NEW in v0.8.2

Purpose:

```text
Run decision-layer jobs separately from the live experiment runner.
```

Important classes:

```python
DecisionJob
DecisionJobManager
DecisionJobError
DecisionJobNotFoundError
DecisionJobConflictError
```

Important factory:

```python
create_decision_jobs_blueprint(manager: DecisionJobManager) -> Blueprint
```

Supported job modules:

```text
study
report
spatial
monte_carlo
sensitivity
optimizer
multiobjective
robustness
```

Module constant:

```python
SUPPORTED_DECISION_JOB_MODULES
```

Current concurrency policy:

```text
one decision job at a time
```

Current cancellation policy:

```text
queued jobs can be cancelled
running jobs cannot be cancelled yet
finished/failed/cancelled jobs cannot be cancelled
```

Current persistence policy:

```text
job state is in-memory only
job list is lost on Flask restart
generated artifacts remain on disk
```

Important rule:

```text
Decision jobs must not reuse the live experiment holder.
```

The live holder remains:

```python
holder = {
    "simulation": ...,
    "runner": ...
}
```

Decision jobs may internally use backend decision modules that execute experiments, but they must not hijack the interactive experiment runner.

---

## Experiment Lifecycle, v0.5.0

User defines `ExperimentConfig` through UI form or JSON.

```text
POST /api/experiment/start
unique run_id created
run directory created
config.json saved
Simulation created from config
Simulation is not started directly
MetricsRecorder attached
runner drives sim._tick() under sim._lock
recorder writes one time-series row plus inferred events per tick
stop condition reached
recorder closed
summary.json written
visualization and analysis read saved files only
```

The runner does not call `Simulation.start()`.

It drives `_tick()` directly in its own daemon thread.

It sleeps `tick_interval` between ticks in normal mode.

In fast mode it yields only.

---

## Reproducibility And Seeding

Rule:

```text
same config + same seed = same result
```

The seed controls:

```text
TaskGenerator(warehouse, seed=seed) location selection.
failure RNG, FailureConfig.seed / Simulation(seed=...).
robot spawn positions, seeded shuffle of passable cells in experiment/factory.generate_spawn_positions().
```

No global RNG reliance.

No new randomness introduced in v0.5+.

`fast_mode` removes wall-clock pacing only.

Tick semantics and results are identical in live and fast mode.

Monte Carlo and robustness modules generate deterministic seed lists when `base_seed` is provided.

If explicit seeds are provided, they are used directly.

---

## Stopping Conditions

`stop_mode = "fixed_ticks"`:

```text
Run until max_ticks.
Answers: how much work is completed in the same time?
```

`stop_mode = "workload"`:

```text
Run until target_tasks completed.
max_ticks is the safety horizon.
Answers: how long does the same workload take?
```

`stop_reason` values written to summary.json:

```text
target_reached
max_ticks_reached
stopped_by_user
reset_by_user
error: <message>
```

---

## Fast / Headless Mode

`ExperimentConfig.fast_mode: bool = False`

When true:

```text
ExperimentRunner does not sleep tick_interval.
It yields with time.sleep(0) periodically.
tick_interval is untouched.
results remain reproducible.
```

UI:

```text
Setup checkbox cfg-fast-mode.
Start shows view-fast with progress text fast-status and fast-stop-btn.
On finish the poller auto-transitions to Results.
```

Recorded as metadata in config.json and summary.json as `fast_mode`.

Fast mode pins one CPU core for its duration. That is expected.

Monte Carlo, sensitivity, optimization, multi-objective, and robustness modules usually force `fast_mode` True because they are headless decision-layer workflows.

---

## Run Identity And Storage Format

run_id format:

```text
YYYYMMDD_HHMMSS_<6 hex>
```

Example:

```text
20260821_013526_a83f21
```

Runs are never overwritten.

`display_name` is metadata only.

---

## Run Storage

```text
data/
└── runs/
    └── <run_id>/
        ├── config.json
        ├── timeseries.csv
        ├── events.csv
        └── summary.json
```

---

## Study Storage, NEW in v0.7.1

```text
data/
└── studies/
    └── <study_id>/
        ├── study_config.json
        ├── results.csv
        └── report.md
```

`results.csv` carries a `run_id` column so each study row traces back to:

```text
data/runs/<run_id>/
```

---

## Report Storage, NEW in v0.7.2

```text
data/
└── reports/
    └── <run_id>_report.md
```

Single-run reports are never written inside `data/runs/`.

---

## Monte Carlo Storage, NEW in v0.8.0

```text
data/
└── monte_carlo/
    └── <mc_id>/
        ├── results.csv
        └── summary.json
```

Each Monte Carlo trial also writes a normal immutable run artifact under:

```text
data/runs/<run_id>/
```

---

## Sensitivity Storage, NEW in v0.8.0

```text
data/
└── sensitivity/
    └── <study_id>/
        ├── results.csv
        ├── tornado.csv
        └── summary.json
```

Each sensitivity trial also writes a normal immutable run artifact under:

```text
data/runs/<run_id>/
```

---

## Optimization Storage, NEW in v0.8.1

```text
data/
└── optimizations/
    └── <opt_id>/
        └── summary.json
```

Each optimization trial may write normal immutable run artifacts under:

```text
data/runs/<run_id>/
```

---

## Multi-Objective Storage, NEW in v0.8.1

```text
data/
└── multiobjective/
    └── <study_id>/
        ├── summary.json
        ├── trials.json
        └── pareto.csv
```

Each multi-objective trial may write normal immutable run artifacts under:

```text
data/runs/<run_id>/
```

---

## Robustness Verification Storage, NEW in v0.8.1

```text
data/
└── robustness/
    └── <robust_id>/
        ├── results.csv
        └── summary.json
```

Each robustness replication writes a normal immutable run artifact under:

```text
data/runs/<run_id>/
```

---

## config.json keys

config.json keys use snake_case because they map directly to ExperimentConfig fields.

Primary keys:

```text
seed
num_robots
display_name
stop_mode
target_tasks
max_ticks
tick_interval
fast_mode
blocked_replan_seconds
replan_cooldown_ticks
battery_capacity
empty_move_energy
loaded_move_energy
critical_battery
opportunistic_charge_threshold
idle_ticks_before_opportunistic_charge
battery_safety_margin
empty_battery_recovery_ticks
charger_capacity
charge_duration_ticks
failure_enabled
mtbf_ticks
mttr_ticks
relocate_to_maintenance
scheduler
path_planner
conflict_manager
```

New v0.7.1 keys:

```text
demand_mode
demand_rate_per_tick
demand_task_weights
demand_segments
demand_csv_path
demand_events
layout_preset
layout_file
```

---

## timeseries.csv headers

One row per tick:

```text
tick
tasks_pending
tasks_outstanding
tasks_created_this_tick
tasks_completed_this_tick
tasks_completed_total
tasks_failed_total
robots_active
robots_idle
robots_blocked
robots_charging
robots_to_charger
robots_waiting_for_charger
robots_failed
average_battery
min_battery
max_battery
replans_this_tick
replans_total
blocked_ticks_this_tick
blocked_ticks_total
```

Definitions:

```text
tasks_pending = live tasks with status Pending, unassigned only.
tasks_outstanding = generated - completed - failed.
tasks_outstanding includes Pending, Assigned, and Interrupted tasks.
tasks_outstanding never counts completed tasks awaiting pruning.
```

Robot buckets are mutually exclusive and sum to the robot population.

Robot bucket priority:

```text
failed/repairing > charging > waiting-for-charger > blocked > to-charger > active > idle
```

```text
throughput[t] = tasks_completed_this_tick
```

Averages and rolling windows exist only in the analysis layer.

---

## events.csv headers

```text
run_id
tick
event_type
robot_id
task_id
details
```

Missing fields are empty strings, never invented.

As of v0.7.2:

```text
robot_blocked rows carry {"x": ..., "y": ...} JSON in details.
The coordinates represent the cell occupied when blocking started.
Pre-v0.7.2 runs have empty details on robot_blocked rows.
```

Event types:

```text
task_created
task_assigned
task_completed
task_failed
task_interrupted
task_reassigned
robot_blocked
robot_unblocked
robot_replanned
robot_started_charging
robot_finished_charging
robot_waiting_for_charger
robot_faulted
robot_recovered
```

Known limitation:

```text
multiple transitions inside one tick can be coalesced.
```

Live task pruning never deletes history.

CSVs are written independently.

---

## summary.json keys

```text
run_id
seed
scheduler
stop_reason
fast_mode
simulation_ticks
simulation_seconds
robot_count
tasks_created
tasks_assigned
tasks_completed
tasks_failed
average_throughput
average_wait_time
average_cycle_time
average_robot_utilization
total_replans
total_blocked_ticks
blocked_time_seconds
charging_events
total_charging_ticks
charger_wait_ticks
charger_wait_events
battery_task_interruptions
failure_task_interruptions
task_reassignments
failed_robot_events
failure_downtime_ticks
robot_utilization
robot_busy_ticks
robot_total_ticks
robot_blocked_ticks
robot_distance_travelled
```

Summary is for quick comparison; the CSVs are authoritative.

---

## experiment/config.py, UPDATED in v0.7.1, UNCHANGED in v0.8.x

`ExperimentConfig` — @dataclass(frozen=True), validated in `__post_init__`.

Fields and defaults:

```text
seed: int
num_robots: int
display_name: str = ""
stop_mode: Literal["fixed_ticks", "workload"]
target_tasks: int | None
max_ticks: int
tick_interval: float = 0.3
fast_mode: bool = False
blocked_replan_seconds: float = 0.7
replan_cooldown_ticks: int = 7
battery_capacity: float = 100.0
empty_move_energy: float = 0.35
loaded_move_energy: float = 0.5
critical_battery: float = 15.0
opportunistic_charge_threshold: float = 30.0
idle_ticks_before_opportunistic_charge: int = 10
battery_safety_margin: float = 5.0
empty_battery_recovery_ticks: int = 15
charger_capacity: int = 4
charge_duration_ticks: int = 10
failure_enabled: bool = False
mtbf_ticks: float = 0.0
mttr_ticks: int = 25
relocate_to_maintenance: bool = True
scheduler: str = "baseline"
path_planner: str = "bfs"
conflict_manager: str = "local_yield"
demand_mode: str = "legacy"
demand_rate_per_tick: float = 0.0
demand_task_weights: dict[str, float]
demand_segments: list[dict[str, Any]]
demand_csv_path: str | None = None
demand_events: list[dict[str, Any]]
layout_preset: str = "default"
layout_file: str | None = None
```

Module-level constants:

```python
PATH_PLANNER_CHOICES = {"bfs", "astar", "weighted_astar"}
CONFLICT_MANAGER_CHOICES = {"local_yield", "zone_locks", "priority_reservation"}
DEMAND_MODE_CHOICES = {"legacy", "uniform", "rate_schedule", "csv_orders"}
LAYOUT_PRESET_CHOICES = {"default", "high_density", "one_way_aisles"}
```

Methods:

```text
default()
to_dict()
save(directory)
load(directory)
from_dict(data)
```

`from_dict(data)` merges over defaults then validates.

Validation highlights:

```text
seed required.
num_robots >= 1.
workload requires target_tasks >= 1.
max_ticks >= 1.
tick_interval > 0.
failure_enabled requires mtbf_ticks > 0.
path_planner must be in PATH_PLANNER_CHOICES.
conflict_manager must be in CONFLICT_MANAGER_CHOICES.
demand_mode must be in DEMAND_MODE_CHOICES.
layout_preset must be in LAYOUT_PRESET_CHOICES.
```

---

## experiment/factory.py, UPDATED in v0.7.1

`ROBOT_COLORS: list[str]` — Okabe-Ito-style palette, cycled by index.

Functions:

```text
generate_spawn_positions(num_robots, warehouse, seed) -> list[tuple[int,int]]
create_experiment_robots(num_robots, warehouse, seed) -> list[Robot]
create_path_planner_from_name(name: str) -> PathPlanner
create_scheduler_from_name(name: str, path_planner: PathPlanner) -> Scheduler
create_conflict_manager_from_name(name: str, sim: Simulation) -> ConflictManager
create_path_planner(config: ExperimentConfig) -> PathPlanner
create_scheduler(config: ExperimentConfig, path_planner: PathPlanner) -> Scheduler
create_conflict_manager(config: ExperimentConfig, sim: Simulation) -> ConflictManager
create_task_generator(config: ExperimentConfig, warehouse: Warehouse) -> TaskGenerator
create_simulation_from_config(config) -> Simulation
```

Important behavior:

```text
generate_spawn_positions() collects passable cells, shuffles with random.Random(seed), takes N. ValueError if fewer passable cells than requested.
create_experiment_robots() creates ids R1..RN, clean strings, deterministic seeded positions.
create_simulation_from_config() builds the warehouse via decision.layout.create_warehouse_for_experiment(), builds the task generator via create_task_generator(), builds robots, configs, path planner, scheduler, and injects conflict manager via sim.set_conflict_manager().
```

---

## experiment/recorder.py, UPDATED in v0.7.2

```python
MetricsRecorder(run_dir: str, run_id: str)
```

Public:

```text
record(snapshot: dict)
close()
```

Important behavior:

```text
Opens timeseries.csv and events.csv.
Writes headers.
Flushes periodically.
close() flushes and closes.
Receives primitive snapshots only.
Never stores live object references.
record() writes one time-series row.
It then infers task/robot events by diffing previous-tick primitive state.
```

Internal previous state fields:

```text
_prev_metrics
_prev_tasks
_prev_robots
```

Completed/failed tasks are dropped from `_prev_tasks` only after being seen Completed/Failed.

`robot_unblocked` is suppressed when caused by failed/repairing/charging/waiting transitions.

As of v0.7.2:

```text
robot_blocked events write {"x": ..., "y": ...} JSON into the details column.
The coordinates represent the cell occupied when blocking started.
```

---

## experiment/runner.py, UPDATED in v0.7.2

```python
ExperimentRunner(base_dir: str = "data/runs")
```

Properties:

```text
is_active
finished
```

Public methods:

```text
start(config, sim_factory) -> run_id
stop(reason="stopped_by_user")
get_state() -> dict
get_summary() -> dict | None
```

Important behavior:

```text
start() creates run dir, saves config, creates recorder, calls sim.resume(), starts daemon thread. RuntimeError if a run is active.
stop() sets stop reason, calls sim.stop(), joins.
get_state() returns {active, finished, runId, runDir, stopReason, paused, tick, fastMode}.
get_summary() returns in-memory summary or reads summary.json.
```

Internal:

```text
_run() loops while not sim._stop_event, skips while sim.is_paused, under sim._lock calls _tick(), _snapshot(), recorder.record(), and evaluates stop condition.
Pacing: fast_mode -> time.sleep(0) every 500 ticks; normal mode -> time.sleep(sim._tick_interval).
Exceptions set stop_reason = "error: ...".
_snapshot() extracts primitive metrics counters, per-task fields, and per-robot fields including x and y.
_evaluate_stop_condition() implements fixed_ticks and workload stopping.
_finalize() closes recorder, computes and writes summary.json once.
```

---

## analysis/loader.py, NEW in v0.5.0

```python
DEFAULT_RUNS_DIR = "data/runs"
```

`RunData` dataclass:

```text
run_id
run_dir
config
summary
timeseries
events
```

Functions:

```text
list_runs(base_dir) -> list[dict]
load_run(run_id, base_dir) -> RunData
```

Important behavior:

```text
list_runs returns newest first.
Each entry contains run_id, run_dir, config, summary.
load_run raises FileNotFoundError if the run is missing.
```

---

## analysis/metrics.py, NEW in v0.5.0

Functions:

```text
ensure_derived_timeseries(df)
percentile_summary(series)
task_lifecycle_from_events(events)
blocked_episodes_from_events(events, final_tick=None)
event_counts(events)
utilization_from_summary(summary)
robot_count_from_run(run)
distribution_stats(run)
```

`ensure_derived_timeseries(df)`:

```text
Adds tick if absent.
Adds tasks_completed_total cumsum if absent.
Adds throughput = tasks_completed_this_tick.
Adds throughput_rolling_50.
Adds throughput_rolling_100.
Never alters recorded columns.
```

`percentile_summary(series)`:

```text
Returns count, mean, median, p90, p95, max.
```

`task_lifecycle_from_events(events)`:

Per task returns:

```text
created_tick
first_assigned_tick
completed_tick
failed_tick
waiting_time = first_assigned_tick - created_tick
cycle_time = completed_tick - created_tick
```

`blocked_episodes_from_events(events, final_tick=None)`:

```text
Pairs robot_blocked/robot_unblocked into episodes.
```

Episode fields:

```text
robot_id
start_tick
end_tick
duration_ticks
open_at_end
```

Unclosed episodes are censored at `final_tick`.

`distribution_stats(run)`:

Percentile summaries for:

```text
task_waiting_time
task_cycle_time
robot_blocked_episode_ticks
system_active_fraction
robot_utilization
```

---

## analysis/web.py, NEW in v0.5.0

Important names:

```text
RUN_ID_PATTERN = ^[A-Za-z0-9_\-]+$
DEFAULT_MAX_POINTS = 2000
MAX_POINTS_LIMIT = 5000
_sanitize()
_downsample(df, column, max_points)
_histogram(series, bins)
```

Payload builders:

```text
list_runs_payload(base_dir) -> {"runs": [...]}
get_run_summary(run_id, base_dir) -> {"run_id", "config", "summary"}
get_run_series(run_id, columns, base_dir, max_points) -> {"run_id", "max_points", "series": [{"name", "points"}]}
get_compare_series(run_ids, column, base_dir, max_points) -> {"column", "max_points", "runs": [{"run_id", "points"}]}
get_run_distributions(run_id, base_dir, bins) -> distributions payload
```

Important behavior:

```text
Invalid run ids raise AnalysisApiError, mapped to 404 by Flask routes.
max_points is clamped, min 50.
_sanitize() makes JSON safe; NaN/Inf become null; numpy scalars converted.
_downsample() uses bucket-mean to [[tick, value], ...].
Full CSVs are never sent to the browser.
Only downsampled payloads are sent.
```

---

## Flask Layer, UPDATED in v0.8.2

### `app.py`

Important functions:

```python
create_app(
    base_data_dir: str = "data/runs",
    start_simulation: bool = False,
) -> Flask
```

module-level:

```python
app = create_app()
```

Holder pattern:

```python
holder = {
    "simulation": <Simulation>,
    "runner": <ExperimentRunner | None>
}
```

All live state routes read:

```python
holder["simulation"]
```

`create_default_simulation()` is replaced by:

```python
create_simulation_from_config(ExperimentConfig.default())
```

New in v0.8.2:

```python
decision_job_manager = DecisionJobManager(
    data_dir=data_dir,
    runs_dir=base_dir,
    max_workers=1,
)
```

Where:

```python
base_dir = Path(base_data_dir)
data_dir = base_dir.parent
```

For default configuration:

```text
base_dir = data/runs
data_dir = data
```

Registered blueprints new in v0.8.2:

```python
app.register_blueprint(
    create_decision_blueprint(
        data_dir=data_dir,
        runs_dir=base_dir,
    )
)

app.register_blueprint(
    create_decision_jobs_blueprint(decision_job_manager)
)
```

Routes, legacy semantics preserved:

```text
GET /
GET /api/state
POST /api/pause
POST /api/resume
POST /api/reset
```

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

`POST /api/reset` stops active runner with `reset_by_user` and recreates default simulation.

Routes, v0.5 experiment lifecycle:

```text
POST /api/experiment/start
GET /api/experiment/state
POST /api/experiment/stop
GET /api/experiment/summary
```

Important behavior:

```text
POST /api/experiment/start returns 409 if a run is active.
Returns 400 on validation or spawn errors.
Body is ExperimentConfig JSON, merged over defaults.
Returns {runId}.
Swaps holder simulation/runner.
GET /api/experiment/summary returns 404 without runner; 409 not finished.
```

Routes, v0.5 analysis API:

```text
GET /api/runs
DELETE /api/runs/<run_id>
GET /api/runs/compare/series?runs=a,b&column=...&max_points=...
GET /api/runs/<run_id>/summary
GET /api/runs/<run_id>/series?columns=a,b&max_points=...
GET /api/runs/<run_id>/distributions?bins=...
```

Routes, v0.8.2 decision API:

```text
GET /api/decision/overview

GET /api/decision/studies
GET /api/decision/studies/<study_id>
GET /api/decision/studies/<study_id>/results

GET /api/decision/reports
GET /api/decision/reports/<report_id>

GET /api/decision/monte-carlo
GET /api/decision/monte-carlo/<mc_id>
GET /api/decision/monte-carlo/<mc_id>/results

GET /api/decision/sensitivity
GET /api/decision/sensitivity/<study_id>
GET /api/decision/sensitivity/<study_id>/results
GET /api/decision/sensitivity/<study_id>/tornado

GET /api/decision/optimizations
GET /api/decision/optimizations/<opt_id>
GET /api/decision/optimizations/<opt_id>/trials

GET /api/decision/multiobjective
GET /api/decision/multiobjective/<study_id>
GET /api/decision/multiobjective/<study_id>/trials
GET /api/decision/multiobjective/<study_id>/pareto

GET /api/decision/robustness
GET /api/decision/robustness/<robust_id>
GET /api/decision/robustness/<robust_id>/results

GET /api/runs/<run_id>/cost-kpis
GET /api/runs/<run_id>/spatial
```

Routes, v0.8.2 decision jobs API:

```text
POST /api/decision/jobs
GET /api/decision/jobs
GET /api/decision/jobs/<job_id>
POST /api/decision/jobs/<job_id>/cancel
```

Important behavior:

```text
Routes stay thin.
Business logic lives in simulation/, experiment/, analysis/, and decision/.
The raw data/runs directory is not served statically.
Decision artifacts are not served as raw static files.
```

---

## Decision Read API, NEW in v0.8.2

### Overview

```text
GET /api/decision/overview
```

Returns counts and latest artifact metadata for:

```text
studies
reports
monte_carlo
sensitivity
optimizations
multiobjective
robustness
jobs
```

### Studies

```text
GET /api/decision/studies
GET /api/decision/studies/<study_id>
GET /api/decision/studies/<study_id>/results
```

Purpose:

```text
Browse factorial DoE studies generated by decision/study.py.
```

Important fields:

```text
study_id
generated_at
config
report_available
rows
total_rows
page
page_size
```

Each result row may contain:

```text
run_id
factor columns
metric columns
```

Each `run_id` should trace back to:

```text
data/runs/<run_id>/
```

### Reports

```text
GET /api/decision/reports
GET /api/decision/reports/<report_id>
```

Purpose:

```text
Expose generated Markdown reports from data/reports/.
```

Important fields:

```text
report_id
generated_at
source_type
source_id
markdown
```

Current implementation:

```text
source_type = "run"
source_id = run id extracted from report file name
```

Reports are generated artifacts.

The UI must not edit reports.

### Monte Carlo

```text
GET /api/decision/monte-carlo
GET /api/decision/monte-carlo/<mc_id>
GET /api/decision/monte-carlo/<mc_id>/results
```

Purpose:

```text
Browse Monte Carlo artifacts generated by decision/monte_carlo.py.
```

List fields:

```text
mc_id
generated_at
n_runs_requested
successful_runs
failed_runs
effective_sla_target_ticks
```

Detail fields:

```text
mc_id
generated_at
summary
```

Results endpoint returns paginated trial rows:

```text
mc_id
page
page_size
total_rows
rows
```

### Sensitivity

```text
GET /api/decision/sensitivity
GET /api/decision/sensitivity/<study_id>
GET /api/decision/sensitivity/<study_id>/results
GET /api/decision/sensitivity/<study_id>/tornado
```

Purpose:

```text
Browse sensitivity artifacts generated by decision/sensitivity.py.
```

List fields:

```text
study_id
generated_at
reps
successful_runs
failed_runs
effective_sla_target_ticks
```

Detail fields:

```text
study_id
generated_at
summary
```

Tornado endpoint returns:

```json
{
  "study_id": "...",
  "tornado": {
    "cost_per_task": [],
    "p95_cycle_time": []
  }
}
```

If summary tornado data is unavailable, backend may fall back to parsing:

```text
tornado.csv
```

Important warning:

```text
One-at-a-time sensitivity does not reveal interaction effects.
```

### Optimization

```text
GET /api/decision/optimizations
GET /api/decision/optimizations/<opt_id>
GET /api/decision/optimizations/<opt_id>/trials
```

Purpose:

```text
Browse single-objective optimizer artifacts generated by decision/optimizer.py.
```

List fields:

```text
opt_id
generated_at
objective
direction
n_trials
feasible_count
infeasible_count
```

Detail fields:

```text
opt_id
generated_at
summary
```

Trials endpoint returns:

```text
opt_id
page
page_size
total_rows
rows
```

Important rule:

```text
best_trial is selected from feasible trials only.
```

If no feasible trial exists:

```json
{
  "best_trial": null
}
```

Do not present an infeasible trial as the best result.

Important warning:

```text
Single-replica optimizer results are exploratory.
Run robustness verification before deployment.
```

### Multi-Objective

```text
GET /api/decision/multiobjective
GET /api/decision/multiobjective/<study_id>
GET /api/decision/multiobjective/<study_id>/trials
GET /api/decision/multiobjective/<study_id>/pareto
```

Purpose:

```text
Browse multi-objective artifacts generated by decision/multiobjective.py.
```

List fields:

```text
study_id
generated_at
n_trials
feasible_count
pareto_count
```

Detail fields:

```text
study_id
generated_at
summary
```

Trials endpoint returns all trials where available:

```text
study_id
page
page_size
total_rows
rows
```

Pareto endpoint returns Pareto trials where available:

```text
study_id
page
page_size
total_rows
rows
```

Important rule:

```text
Pareto candidates are not deployable until verified by robustness.
```

### Robustness

```text
GET /api/decision/robustness
GET /api/decision/robustness/<robust_id>
GET /api/decision/robustness/<robust_id>/results
```

Purpose:

```text
Browse robustness verification artifacts generated by decision/robustness.py.
```

List fields:

```text
robust_id
generated_at
reps
objective
direction
successful_runs
failed_runs
recommended
```

Detail fields:

```text
robust_id
generated_at
summary
```

Results endpoint returns:

```text
robust_id
page
page_size
total_rows
rows
```

Important rules:

```text
constraint_pass_probability is the critical deployment metric.
robust_pass is true only when constraint_pass_probability >= min_pass_probability.
recommended is null when no candidate meets min_pass_probability.
reps below 20 is not recommended for deployment decisions.
```

### Run-Level Cost KPIs

```text
GET /api/runs/<run_id>/cost-kpis
```

Query parameters:

```text
cost_config
sla_target_ticks
```

`cost_config` must be URL-encoded JSON.

Example:

```bash
curl -G "http://127.0.0.1:5000/api/runs/<run_id>/cost-kpis" \
  --data-urlencode 'cost_config={"robot_opex_per_hour":12.5,"charger_infra_cost_per_hour":2.0,"downtime_cost_per_hour":30.0,"sla_target_ticks":300,"sla_penalty_per_late_tick":0.5,"currency":"USD"}'
```

Response fields:

```text
total_operating_cost
cost_per_task
sla_compliance_rate
completed_tasks
sla_evaluated_tasks
late_tasks
simulation_seconds
currency
cost_breakdown
```

Important null rules:

```text
cost_per_task is null when completed_tasks is zero.
sla_compliance_rate is null when no SLA-evaluated tasks exist.
```

Temporary implementation note:

```text
The frontend currently sends cost config as URL-encoded JSON.
Future versions may use saved cost configs, cost config files, or POST-based cost evaluation.
```

### Run-Level Spatial Analysis

```text
GET /api/runs/<run_id>/spatial
```

Query parameters:

```text
top
by
```

Allowed `by` values:

```text
blocked_ticks
blocked_events
```

Response fields:

```text
run_id
total_blocked_events
events_with_coordinates
coverage
has_data
sort_by
top_n
top_cells
```

Each top cell:

```text
x
y
blocked_events
blocked_ticks
```

Important warnings:

```text
Pre-v0.7.2 runs have coverage 0.0.
A robot can drift during yield, so exact cells are approximate.
Hotspots near chargers indicate capacity problems.
Hotspots at aisle intersections indicate traffic-control problems.
```

---

## Decision Job API, NEW in v0.8.2

### Create job

```text
POST /api/decision/jobs
```

Request body:

```json
{
  "module": "monte_carlo",
  "config": {
    "from_run_id": "<run_id>",
    "n_runs": 2,
    "base_seed": 42,
    "sla_target_ticks": 300,
    "cost_config": {
      "robot_opex_per_hour": 12.5,
      "charger_infra_cost_per_hour": 2.0,
      "downtime_cost_per_hour": 30.0,
      "sla_target_ticks": 300,
      "sla_penalty_per_late_tick": 0.5,
      "currency": "USD"
    }
  }
}
```

Response:

```json
{
  "job_id": "job_20260904_234416_41bb1f",
  "module": "monte_carlo",
  "status": "queued",
  "created_at": "2026-09-04T23:44:16.335389",
  "started_at": null,
  "finished_at": null,
  "artifact_type": null,
  "artifact_id": null,
  "progress": null,
  "error": null
}
```

Status code:

```text
201 Created
```

Invalid module returns:

```text
400 Bad Request
```

Invalid config returns:

```text
400 Bad Request
```

### List jobs

```text
GET /api/decision/jobs
```

Response:

```json
{
  "jobs": []
}
```

Jobs are sorted newest first.

### Get job

```text
GET /api/decision/jobs/<job_id>
```

Response fields:

```text
job_id
module
status
created_at
started_at
finished_at
artifact_type
artifact_id
progress
error
```

Invalid job id returns:

```text
404 Not Found
```

### Cancel job

```text
POST /api/decision/jobs/<job_id>/cancel
```

Possible outcomes:

```text
200 OK if queued job was cancelled
404 Not Found if job id is invalid
409 Conflict if job cannot be cancelled
```

Example conflict error:

```json
{
  "error": "Running decision jobs cannot be cancelled yet. Only queued jobs can be cancelled."
}
```

---

## Job Status Values

```text
queued
running
finished
failed
cancelled
```

Meaning:

```text
queued: accepted but not started
running: currently executing
finished: completed successfully
failed: completed with error
cancelled: cancelled before execution
```

Artifact linkage:

When a job finishes successfully:

```text
artifact_type describes the decision artifact type
artifact_id describes the artifact id
```

Examples:

```text
artifact_type = monte_carlo
artifact_id = <mc_id>

artifact_type = sensitivity
artifact_id = <study_id>

artifact_type = optimization
artifact_id = <opt_id>

artifact_type = multiobjective
artifact_id = <study_id>

artifact_type = robustness
artifact_id = <robust_id>

artifact_type = study
artifact_id = <study_id>

artifact_type = report
artifact_id = <run_id or study_id>

artifact_type = spatial
artifact_id = <run_id>
```

Spatial analysis is computed on demand and does not currently create a dedicated stored artifact directory.

---

## Job Module Behavior

### `monte_carlo`

Expected config fields:

```text
from_run_id or base_config
n_runs
base_seed
seeds
sla_target_ticks
cost_config
```

Validation:

```text
n_runs >= 1
source config required
explicit seeds length must equal n_runs if provided
cost_config must be valid if provided
```

Artifact:

```text
data/monte_carlo/<mc_id>/
```

### `sensitivity`

Expected config fields:

```text
from_run_id or base_config
factors
reps
base_seed
sla_target_ticks
cost_config
```

Validation:

```text
factors must be non-empty
each factor needs name and non-empty values
reps >= 1
source config required
```

Artifact:

```text
data/sensitivity/<study_id>/
```

### `optimizer`

Expected config fields:

```text
from_run_id or base_config
objective
direction
n_trials
reps
base_seed
constraints
sla_target_ticks
cost_config
search_space
timeout
```

Validation:

```text
search_space must be non-empty
objective must be supported
direction must be minimize or maximize
n_trials >= 1
reps >= 1
cost_config required for cost_per_task objective
```

Artifact:

```text
data/optimizations/<opt_id>/
```

### `multiobjective`

Expected config fields:

```text
from_run_id or base_config
objectives
constraints
search_space
n_trials
reps
base_seed
population_size
sla_target_ticks
cost_config
timeout
```

Validation:

```text
at least two objectives for meaningful Pareto workflow
search_space must be non-empty
objective metrics must be supported
directions must be valid
cost_config required if any objective is cost_per_task
```

Artifact:

```text
data/multiobjective/<study_id>/
```

### `robustness`

Expected config fields:

```text
candidates or from_multiobjective_id
reps
base_seed
objective
direction
min_pass_probability
constraints
sla_target_ticks
cost_config
max_candidates
```

Validation:

```text
candidate source required
reps >= 1
min_pass_probability between 0 and 1
constraints should not be empty for deployment decisions
cost_config required for cost_per_task objective
```

Artifact:

```text
data/robustness/<robust_id>/
```

Important warning:

```text
reps below 20 is not recommended for deployment decisions.
```

### `report`

Expected config fields:

```text
run_id or study_id
```

Behavior:

```text
run_id generates a single-run report
study_id generates a study report
```

Artifact:

```text
data/reports/<run_id>_report.md
or
study report inside study directory
```

### `spatial`

Expected config fields:

```text
run_id
top
by
```

Behavior:

```text
Computes spatial blockage analysis from saved run artifacts.
```

Current artifact linkage:

```text
artifact_type = spatial
artifact_id = run_id
```

Spatial analysis does not currently write a dedicated artifact directory.

### `study`

Expected config fields:

```text
study config fields accepted by decision/study.py
from_run_id or base_config where applicable
```

Behavior:

```text
Executes factorial study through backend study runner.
```

Artifact:

```text
data/studies/<study_id>/
```

Important warning:

```text
Large factorial designs can create many runs.
```

---

## Template Endpoints

Not implemented in v0.8.2.

Planned:

```text
GET /api/decision/templates
GET /api/decision/templates/<module>
```

Current frontend behavior:

```text
Job modal supports guided forms for all primary decision modules.
Client-side JSON templates remain available.
When guided mode is disabled, or when Load JSON template is clicked, the JSON editor is populated with a module template.
```

Supported client-side template modules:

```text
monte_carlo
sensitivity
optimizer
multiobjective
robustness
study
report
spatial
```

---

## File Endpoints

Not implemented in v0.8.2.

Planned future routes:

```text
GET /api/decision/files/demand-csv
GET /api/decision/files/layouts
GET /api/decision/files/cost-configs
POST /api/decision/files/upload
```

Current file policy:

```text
No arbitrary filesystem paths should be accepted from untrusted users.
Demand CSV and layout file Setup fields are implemented as local trusted relative-path text inputs.
These are acceptable for local single-user development.
For hosted deployments, they must be replaced by admin-managed dropdowns or validated uploads.
Managed file selection/upload endpoints remain not implemented.
Cost config is edited inline as JSON.
```

---

## Decision Output Schemas, v0.8.x

### Monte Carlo `summary.json`

Important fields:

```text
mc_id
generated_at
n_runs_requested
successful_runs
failed_runs
seeds
effective_sla_target_ticks
force_fast_mode
base_config
aggregate
errors
```

`aggregate.kpis` contains per-KPI summaries:

```text
count
mean
stdev
min
p05
median
p95
max
mean_ci95_low
mean_ci95_high
```

`aggregate.sla` contains:

```text
target_ticks
evaluated_tasks
late_tasks
task_late_probability
runs_evaluated
runs_with_any_late
run_any_violation_probability
```

### Sensitivity `summary.json`

Important fields:

```text
study_id
generated_at
reps
seeds
effective_sla_target_ticks
base_config
factors
baseline
factor_results
tornado
errors
```

`baseline` contains:

```text
runs
aggregate
cost_per_task
p95_cycle_time
```

`factor_results` contains per-factor levels:

```text
value
reused_baseline
runs
aggregate
cost_per_task
p95_cycle_time
delta_cost_per_task
delta_percent_cost_per_task
delta_p95_cycle_time
delta_percent_p95_cycle_time
```

`tornado` contains sorted lists for:

```text
cost_per_task
p95_cycle_time
```

### Optimizer `summary.json`

Important fields:

```text
opt_id
generated_at
n_trials
reps
objective
direction
constraints
best_trial
feasible_count
infeasible_count
search_space
```

`best_trial` contains:

```text
number
params
value
state
metrics
feasible
constraints
error
```

### Multi-Objective `summary.json`

Important fields:

```text
study_id
output_dir
generated_at
objectives
constraints
n_trials
reps
base_seed
sla_target_ticks
base_config
cost_config
search_space
total_trials
feasible_count
pareto_count
pareto_trials
```

`pareto_trials` entries contain:

```text
number
params
values
state
metrics
constraints
feasible
error
```

`trials.json` contains all trials, not only Pareto trials.

`pareto.csv` contains:

```text
trial_number
feasible
one column per objective
one column per search-space parameter
constraint_values
```

### Robustness `summary.json`

Important fields:

```text
robust_id
output_dir
generated_at
reps
base_seed
objective
direction
constraints
min_pass_probability
sla_target_ticks
base_config
cost_config
successful_runs
failed_runs
recommended
candidates
errors
```

Each candidate result contains:

```text
label
overrides
successful_reps
failed_reps
constraint_pass_probability
robust_pass
objective_metric
objective_direction
objective_mean
objective_stdev
metrics
constraint_details
```

`constraint_details` contains per-constraint:

```text
metric
limit
pass_probability
mean_value
worst_value
```

---

## CLI Layer, UPDATED in v0.8.1

### `benchmark.py`

Purpose:

```text
Runs a headless synchronous benchmark.
Does not start Flask.
Does not poll.
Directly calls sim._tick() under the simulation lock.
As of v0.7.2, records every run through ExperimentRunner.
```

Existing arguments:

```text
--robots
--block-replan
--cooldown
--target
--seed
```

v0.4 arguments:

```text
--max-ticks
--battery-capacity
--empty-move-energy
--loaded-move-energy
--critical-battery
--opportunistic-charge-threshold
--idle-opportunistic-ticks
--battery-safety-margin
--charger-capacity
--charge-duration-ticks
--failure-enabled
--mtbf-ticks
--mttr-ticks
```

v0.5 arguments:

```text
--spawn, choices: seeded, legacy; default: seeded
--display-name
```

v0.6 arguments:

```text
--path-planner, choices: bfs, astar, weighted_astar; default: bfs
--scheduler, choices: baseline, priority, fifo, total_cost, auction; default: baseline
--conflict-manager, choices: local_yield, zone_locks, priority_reservation; default: local_yield
```

Important behavior:

```text
Benchmark wall-clock times are not comparable to pre-v0.7.2 runs due to recording overhead.
```

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

```text
Legacy Optuna parameter optimizer.
Prefer decision/optimizer.py, decision/multiobjective.py, and decision/robustness.py for v0.8.1 workflows.
```

Existing search parameters:

```text
num_robots
blocked_replan_seconds
replan_cooldown_ticks
```

Existing arguments:

```text
--trials
--target
--max-ticks
--base-seed
--objective
--fixed-robots
--db
```

v0.4 arguments:

```text
--search-v04
plus battery/charging/failure parameter set.
```

Important behavior:

```text
Without --search-v04, optimization behavior remains v0.3-style but runs with v0.4 battery/charging defaults.
With --search-v04, selected battery/charging parameters are included in the search space.
v0.4 metrics are logged as Optuna user attributes.
Study name includes a v0.4 suffix when --search-v04 is used.
```

---

## Decision CLI, UPDATED in v0.8.1

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

---

## JSON API

### `GET /api/state`

Returns the v0.4 payload plus the v0.5 top-level `experiment` key described in the Flask Layer section.

Example:

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

```text
paused
tick
warehouse
robots
tasks
metrics
experiment
```

Robot JSON keys:

Existing:

```text
id
x
y
color
status
currentTaskId
currentTarget
blockedTicks
replanning
yieldingTo
replanCooldown
```

v0.4:

```text
battery
mode
idleTicks
chargerWaitTicks
interruptedTaskId
chargeTarget
chargeStartBattery
repairRemainingTicks
```

Task JSON keys:

Existing:

```text
id
name
pickup
dropoff
taskType
priority
createdAt
completedAt
status
assignedRobotId
phase
```

v0.4:

```text
loadState
interruptionCount
lastAssignedRobotId
resumeLocationName
```

Important:

```text
status can be "Interrupted".
```

Warehouse JSON keys:

```text
width
height
layout
obstacles
locations
racks
```

Important:

```text
dynamic RESUME-* locations must not appear in the serialized warehouse payload.
```

Metrics JSON keys:

Existing:

```text
tasksGenerated
tasksAssigned
tasksCompleted
tasksFailed
blockedTimeTicks
blockedTimeSeconds
replanningCount
deadlockResolutions
replanEvents
throughputPerTick
averageTaskWaitingTime
averageTaskCompletionTime
simulationTicks
simulationSeconds
robotDistanceTravelled
robotBusyTicks
robotBlockedTicks
robotReplanEvents
robotUtilization
```

v0.4:

```text
averageBattery
averageBatteryPercent
chargingEvents
totalChargingTicks
totalChargingSeconds
chargerWaitTicks
chargerWaitSeconds
chargerWaitEvents
averageChargerWaitTicks
averageChargerWaitSeconds
trafficWaitTicks
trafficWaitSeconds
stationWaitTicks
stationWaitSeconds
totalWaitTicks
totalWaitSeconds
batteryTaskInterruptions
failureTaskInterruptions
taskReassignments
failedRobotEvents
failureDowntimeTicks
failureDowntimeSeconds
congestion
```

`replanEvents` duplicates `replanningCount` for backward compatibility.

Congestion JSON keys inside `metrics.congestion`:

```text
blockedRobots
waitingForChargerRobots
chargingRobots
toChargerRobots
failedRobots
replanningRobots
activeConflicts
chargerOccupancy
chargerWaiting
averageBlockedTicks
robotsByRow
```

Important:

```text
congestion emerges from robot interactions; it is measured, not artificially imposed.
```

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

---

## Frontend Structure, NEW in v0.8.2

The frontend was refactored from monolithic files into modular files.

Old monolithic files, deprecated:

```text
templates/index.html as a single giant file
static/style.css as a single giant file
static/simulation.js as a single giant file
```

New structure:

```text
templates/
├── index.html
├── views/
│   ├── setup.html
│   ├── run.html
│   ├── fast.html
│   ├── results.html
│   ├── experiments.html
│   ├── visualization.html
│   ├── analysis.html
│   ├── compare.html
│   └── decision.html
└── modals/
    └── job_modal.html

static/
├── css/
│   ├── theme.css
│   ├── layout.css
│   ├── warehouse.css
│   └── decision.css
└── js/
    ├── utils.js
    ├── state.js
    ├── charts.js
    ├── warehouse.js
    ├── experiments.js
    ├── decision.js
    └── app.js
```

Important note:

```text
The ECharts wrapper module is static/js/charts.js.
If a local file was accidentally named chart.js, it must be renamed to charts.js or the script tag must be corrected.
```

---

## Frontend Script Load Order

The script load order matters.

Correct order:

```html
<script src="/static/js/utils.js"></script>
<script src="/static/js/state.js"></script>
<script src="/static/js/charts.js"></script>
<script src="/static/js/warehouse.js"></script>
<script src="/static/js/experiments.js"></script>
<script src="/static/js/decision.js"></script>
<script src="/static/js/app.js"></script>
```

ECharts must load before the JS modules that render charts.

Correct external dependency:

```html
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
```

For offline or air-gapped hosts:

```html
<script src="/static/vendor/echarts.min.js"></script>
```

---

## Frontend Module Responsibilities

### `static/js/utils.js`

Pure helpers.

Important functions:

```text
safeString
toNumber
escapeHtml
formatValue
formValue
formNumber
formNumberOrNull
formBool
decisionFetchJson
flattenRow
deriveColumns
formatMoney
formatPercent
formatProbability
on
```

### `static/js/state.js`

Application state and shared infrastructure.

Important globals:

```text
CELL_SIZE
POLL_INTERVAL_MS
CHART_COLORS
views
currentView
activeRunId
robotElements
previousWarehouseKey
updateInProgress
visualizationChart
compareChart
analysisCharts
compareMultiSelect
decisionSubview
jobPollingInterval
```

Important functions:

```text
initViews
showView
createMetricCard
createTaskRow
refresh
populateRunSelects
```

Important class:

```text
MultiSelect
```

### `static/js/charts.js`

ECharts wrappers.

Important functions:

```text
ensureECharts
getBaseChartOption
renderLineChart
renderStackedAreaChart
renderBarChart
renderHistogramChart
```

`ensureECharts` fails loudly if ECharts is not loaded.

### `static/js/warehouse.js`

Live warehouse rendering.

Important functions:

```text
staticWarehouseKey
render
buildStaticLayer
addCell
updateRobots
updateTaskHighlights
highlightLocation
addTileClass
updateSidePanel
```

### `static/js/experiments.js`

Experiment lifecycle and old analysis views.

Important functions:

```text
readExperimentConfig
startExperiment
showResults
renderSummary
openRunSummary
loadExperiments
generateVisualization
generateAnalysis
generateComparison
updateResultsDecisionActionsVisibility
createRunActionButton
createRunLinkedActionsGroup
```

`readExperimentConfig()` includes:

```text
display_name
seed
num_robots
stop_mode
target_tasks
max_ticks
tick_interval
fast_mode
blocked_replan_seconds
replan_cooldown_ticks
path_planner
scheduler
conflict_manager
battery fields
charging fields
failure fields
```

Implemented Setup v0.7.1 fields:

```text
demand_mode
demand_rate_per_tick
demand_task_weights
demand_segments
demand_csv_path
demand_events
layout_preset
layout_file
```

`readExperimentConfig()` includes these fields using backend snake_case keys.

Setup validation helpers may include:

```text
parseSetupJson
parseSetupJsonObject
parseSetupJsonArray
validateNonNegativeNumberObject
validateRelativeTrustedPath
validateDemandSegments
validateDemandEvents
```

Phase 3 helpers may include:

```text
updateResultsDecisionActionsVisibility
createRunActionButton
createRunLinkedActionsGroup
```

### `static/js/decision.js`

Decision Center logic.

Important functions:

```text
decisionContainer
setDecisionLoading
setDecisionError
setDecisionEmpty
decisionCard
decisionTableHtml
renderDecisionTable
renderRowsTable
paginationControls
renderPaginatedDynamicTable
renderObjectTable
renderErrorsTable
probabilityBarHtml
robustPassBadge

showDecisionSubview
refreshDecision

loadDecisionOverview
loadDecisionStudies
loadStudyDetail
loadDecisionReports
openReport
generateSpatial
generateCostKpis

loadDecisionMonteCarlo
openMonteCarloDetail

loadDecisionSensitivity
openSensitivityDetail

loadDecisionOptimizations
openOptimizationDetail

loadDecisionMultiobjective
openMultiobjectiveDetail

loadDecisionRobustness
openRobustnessDetail

loadDecisionJobs
renderJobs
openArtifact
cancelJob
startJobPolling
stopJobPolling

openJobModal
closeJobModal
loadJobTemplate
submitJob

ensureRunSelectValue
uniqueSortedInts
buildSensitivityFactorValues
buildRunLinkedSearchSpace
buildRunLinkedConfig
fetchRunSummarySafe
showRunActionError
prepareDecisionRunSelect
goToCostKpisForRun
goToSpatialForRun
openRunLinkedJobModal
handleRunLinkedAction
```

Phase 3 run-linked behavior:

`handleRunLinkedAction` handles buttons using `data-run-action`.
Cost and spatial actions navigate to existing read-only Decision subviews.
Report, Monte Carlo, sensitivity, optimizer, and multi-objective actions open the decision job modal with a prefilled JSON config.
Phase 3 run-linked prefill remains JSON-based.
Phase 4 guided forms do not reverse-parse arbitrary prefilled JSON.

### `static/js/decision_forms.js`, NEW in v0.8.3

Purpose:

```text
Guided decision job forms.
Guided/advanced modal state.
Client-side validation for guided decision job configs.
Config builders for supported decision modules.
```

Important modal helpers:

```text
isGuidedJobFormEnabled
hasGuidedJobForm
setJobGuidedError
clearJobGuidedError
updateJobGuidedVisibility
toggleJobGuidedJson
onDecisionJobModuleChange
```

Important validation helpers:

```text
populateJobRunSelect
parseGuidedJson
parseGuidedJsonObject
parseGuidedJsonArray
guidedRequiredInteger
guidedOptionalInteger
guidedRequiredNumber
guidedOptionalNumber
getCostConfigTemplateObject
```

Important shared decision-form helpers:

```text
supportedObjectiveMetrics
defaultDirectionForMetric
metricOptionsHtml
parseGuidedCostConfig
buildGuidedCommonConstraints
renderGuidedSearchSpaceSection
getGuidedCheckedChoices
buildGuidedSearchSpace
```

Important factor helpers:

```text
commonFactorOptions
parseGuidedFactorValues
addGuidedFactorRow
buildGuidedFactors
```

Important guided form render functions:

```text
renderGuidedJobForm
renderMonteCarloGuidedForm
renderSensitivityGuidedForm
renderReportGuidedForm
renderSpatialGuidedForm
renderOptimizerGuidedForm
renderMultiobjectiveGuidedForm
renderRobustnessGuidedForm
renderStudyGuidedForm
```

Important guided form config builders:

```text
buildGuidedJobConfig
buildMonteCarloGuidedConfig
buildSensitivityGuidedConfig
buildReportGuidedConfig
buildSpatialGuidedConfig
buildOptimizerGuidedConfig
buildMultiobjectiveGuidedConfig
buildRobustnessGuidedConfig
buildStudyGuidedConfig
```

Overrides:

```text
openJobModal
submitJob
```

Important behavior:

```text
Guided mode is enabled by default when opening a new job.
Advanced JSON mode remains available.
Phase 3 prefilled job configs open in Advanced JSON mode.
Guided forms build snake_case backend configs.
Guided forms do not compute decision math.
Backend validation remains authoritative.
```

### `static/js/app.js`

Initialization and event binding.

Important responsibilities:

```text
initialize views
show default view
bind navigation buttons
bind experiment controls
bind visualization/analysis/compare controls
bind decision subview buttons
bind spatial/cost controls
bind Phase 3 run-linked action delegation
bind job modal guided controls
initialize Setup stop-mode visibility
initialize Setup demand/layout visibility
start polling
```

Phase 3 bindings:

```text
document-level click delegation for `[data-run-action]`
`handleRunLinkedAction(button)`
```

Phase 4 bindings:

```text
decision-job-module change routing
decision-job-use-guided change handling
decision-job-toggle-json click handling
decision-job-template-btn JSON template loading
decision-job-submit-btn job submission
decision-job-close-btn modal closing
```

Setup bindings:

```text
cfg-stop-mode conditional target tasks visibility
cfg-demand-mode conditional demand field visibility
cfg-layout-preset layout visibility hook
```

---

## DOM IDs, UPDATED in v0.8.2

### Existing nav IDs

```text
nav-setup-btn
nav-run-btn
nav-results-btn
nav-experiments-btn
nav-visualization-btn
nav-analysis-btn
nav-compare-btn
```

New nav ID:

```text
nav-decision-btn
```

### Existing view IDs

```text
view-setup
view-run
view-fast
view-results
view-experiments
view-visualization
view-analysis
view-compare
```

New view ID:

```text
view-decision
```

### Setup IDs

Existing:

```text
cfg-display-name
cfg-seed
cfg-num-robots
cfg-stop-mode
cfg-target-tasks
cfg-max-ticks
cfg-tick-interval
cfg-blocked-replan-seconds
cfg-replan-cooldown-ticks
cfg-fast-mode
cfg-path-planner
cfg-scheduler
cfg-conflict-manager
cfg-battery-capacity
cfg-empty-move-energy
cfg-loaded-move-energy
cfg-critical-battery
cfg-opportunistic-charge-threshold
cfg-charger-capacity
cfg-charge-duration-ticks
cfg-failure-enabled
cfg-mtbf-ticks
cfg-mttr-ticks
start-experiment-btn
```

New UI helper ID:

```text
target-tasks-field
```

`target-tasks-field` is the label/container for `cfg-target-tasks`.

It is shown or hidden depending on stop mode.

Setup v0.7.1 demand IDs:

```text
cfg-demand-mode
cfg-demand-rate-per-tick
cfg-demand-task-weights
cfg-demand-segments
cfg-demand-csv-file
cfg-demand-events
cfg-layout-preset
cfg-layout-file
```

Setup conditional containers:

```text
demand-uniform-fields
demand-rate-schedule-fields
demand-csv-fields
```

### Results / Experiments run-linked IDs

Results decision action IDs:

```text
results-decision-actions-card
```

Run-linked action attributes:

```text
data-run-action
data-run-id
```

Supported `data-run-action` values:

```text
cost
spatial
report
monte_carlo
sensitivity
optimizer
multiobjective
```

### Decision subview containers

```text
decision-overview
decision-studies
decision-reports
decision-spatial
decision-cost
decision-monte-carlo
decision-sensitivity
decision-optimization
decision-multiobjective
decision-robustness
decision-jobs
```

### Decision navigation buttons

```text
decision-open-overview-btn
decision-open-studies-btn
decision-open-reports-btn
decision-open-spatial-btn
decision-open-cost-btn
decision-open-monte-carlo-btn
decision-open-sensitivity-btn
decision-open-optimization-btn
decision-open-multiobjective-btn
decision-open-robustness-btn
decision-open-jobs-btn
decision-refresh-btn
```

### Spatial controls

```text
spatial-run-select
spatial-top
spatial-by
spatial-generate-btn
spatial-detail
```

### Cost KPI controls

```text
cost-run-select
cost-config-editor
cost-generate-btn
cost-detail
```

### Job modal controls

```text
decision-job-modal
decision-job-module
decision-job-config-editor
decision-job-template-btn
decision-job-submit-btn
decision-job-close-btn
decision-job-error
decision-job-use-guided
decision-job-guided
decision-job-json-wrapper
decision-job-toggle-json
decision-job-guided-error
```

Guided form dynamic ID prefixes:

```text
mc-source-type
mc-run-id
mc-base-config
mc-n-runs
mc-base-seed
mc-sla-target-ticks
mc-cost-config
sens-source-type
sens-run-id
sens-base-config
sens-reps
sens-base-seed
sens-sla-target-ticks
sens-cost-config
sens-factor-rows
sens-add-factor-btn
sens-factor-options
report-source-type
report-run-id
report-study-id
spatial-job-run-id
spatial-job-top
spatial-job-by
opt-source-type
opt-run-id
opt-base-config
opt-objective
opt-direction
opt-n-trials
opt-reps
opt-base-seed
opt-sla-target-ticks
opt-cost-config
opt-constraint-p95-max
opt-constraint-sla-min
opt-ss-num-robots-enabled
opt-ss-num-robots-low
opt-ss-num-robots-high
opt-ss-charger-capacity-enabled
opt-ss-charger-capacity-low
opt-ss-charger-capacity-high
opt-ss-conflict-manager-enabled
opt-ss-scheduler-enabled
mo-source-type
mo-run-id
mo-base-config
mo-n-trials
mo-reps
mo-base-seed
mo-population-size
mo-sla-target-ticks
mo-cost-config
mo-objective-rows
mo-add-objective-btn
mo-constraint-p95-max
mo-constraint-sla-min
mo-ss-num-robots-enabled
mo-ss-num-robots-low
mo-ss-num-robots-high
mo-ss-charger-capacity-enabled
mo-ss-charger-capacity-low
mo-ss-charger-capacity-high
mo-ss-conflict-manager-enabled
mo-ss-scheduler-enabled
rob-source-type
rob-from-mo-id
rob-mo-options
rob-max-candidates
rob-candidates-json
rob-reps
rob-reps-warning
rob-base-seed
rob-objective
rob-direction
rob-min-pass-probability
rob-sla-target-ticks
rob-cost-config
rob-constraint-p95-max
rob-constraint-sla-min
study-source-type
study-run-id
study-base-config
study-factor-rows
study-add-factor-btn
study-factor-options
```

### Jobs table dynamic data attributes

```text
data-open-artifact-type
data-open-artifact-id
data-cancel-job
```

---

## CSS Classes, UPDATED in v0.8.2

Existing classes remain:

```text
.toolbar
.view
.form-grid
.metric-card
.task-row
.task-badge
.chart-container
.analysis-chart-wrapper
.experiment-row
.multi-select
.setup-grid
.run-layout
.run-main
.run-sidebar
.run-controls
```

New Decision Center classes:

```text
.decision-subnav
.decision-subview
.decision-toolbar
.decision-cards
.decision-card
.decision-card-title
.decision-card-value
.decision-card-detail
.decision-status
.decision-status.loading
.decision-status.error
.decision-status.warning
.decision-status.success
.decision-table-wrapper
.decision-table
.json-preview
.markdown-preview
.badge
.badge-success
.badge-warning
.badge-error
.badge-info
```

New modal classes:

```text
.modal
.modal-content
.modal-header
.modal-close
.modal-body
.modal-footer
```

New guided form classes:

```text
.decision-guided-form
.decision-guided-subsection
.decision-guided-row
.decision-guided-checkbox-grid
.decision-guided-warning
```

---

## Frontend Phase Status, v0.8.2

### Phase 0 — API contract and payload builders

Status:

```text
Complete
```

Delivered:

```text
Decision API routes
JSON payload builders
ID validation
sanitization
pagination for large tables
read-only artifact endpoints
```

### Phase 1 — Read-only Decision Center

Status:

```text
Complete
```

Delivered:

```text
Decision nav item
Decision Overview
Studies list/detail/results
Reports list/detail
Spatial analysis view
Cost KPI view
Monte Carlo list/detail/results
Sensitivity list/detail/results/tornado table
Optimization list/detail/trials
Multi-objective list/detail/trials/Pareto
Robustness list/detail/results
Loading states
Empty states
Error states
```

Missing from Phase 1 ideal scope:

```text
Advanced charts for Monte Carlo histograms
Advanced tornado charts
Pareto scatter charts
Optimizer objective-vs-trial charts
Spatial heatmap overlay
```

These are Phase 5 visualization items.

### Phase 2 — Job launcher

Status:

```text
Complete, minimum viable
```

Delivered:

```text
Decision job manager
Job API
Job modal
JSON template loading
Job submission
Jobs view
Job polling
Readable job errors
Open artifact from finished job
Cancel queued job
```

Current limitations:

```text
Guided forms are available for supported modules; the advanced JSON editor remains available.
Running jobs cannot be cancelled yet.
Job progress is status-only; progress field is currently null.
Job history is in-memory only.
Template endpoints are not implemented; templates are client-side.
```

### Phase 3 — Run-linked actions

Status:

```text
Complete
```

Delivered:

```text
Results decision action card.
Experiments row decision actions.
Run-linked cost KPI access.
Run-linked spatial bottleneck access.
Run-linked report job prefill.
Run-linked Monte Carlo job prefill.
Run-linked sensitivity job prefill.
Run-linked optimizer baseline prefill.
Run-linked multi-objective baseline prefill.
```

Implementation notes:

```text
Cost and spatial actions navigate to existing read-only Decision subviews.
Job actions open the decision job modal with prefilled JSON.
Phase 3 prefills are JSON-based.
After Phase 4, Phase 3 prefilled configs open in Advanced JSON mode.
```

### Phase 4 — Guided forms

Status:

```text
Complete
```

Delivered:

```text
Guided/advanced mode in the decision job modal.
Guided forms for:
monte_carlo
sensitivity
report
spatial
optimizer
multiobjective
robustness
study

Advanced JSON editor preserved.
Client-side JSON template loading preserved.
Inline validation for guided forms.
Cost config template editors.
Common constraint editors.
Search-space builder for optimizer and multi-objective.
Objective builder for multi-objective.
Robustness candidate source selection.
Study factor builder.
```

Implementation notes:

```text
Guided mode is enabled by default for new jobs.
Advanced JSON mode remains available.
Phase 3 prefilled configs open in Advanced JSON mode.
Guided forms build snake_case backend configs.
Guided forms do not compute decision math.
Backend validation remains authoritative.
```

### Phase 5 — Advanced visualization and workflow integration

Status:

```text
Not started
```

Planned:

```text
Monte Carlo histograms
Tornado charts
Pareto scatter charts
Robustness probability bars
Spatial heatmap overlay optional
Guided pipeline from baseline to robustness
```

---

## Setup v0.7.1 Demand and Layout Fields, NEW in v0.8.3

Setup now supports the v0.7.1 experiment fields required for realistic non-CLI scenarios.

Demand fields:

```text
demand_mode
demand_rate_per_tick
demand_task_weights
demand_segments
demand_csv_path
demand_events
```

Layout fields:

```text
layout_preset
layout_file
```

Recommended DOM IDs:

```text
cfg-demand-mode
cfg-demand-rate-per-tick
cfg-demand-task-weights
cfg-demand-segments
cfg-demand-csv-file
cfg-demand-events
cfg-layout-preset
cfg-layout-file
```

Conditional demand behavior:

```text
If demand_mode = legacy: show no additional demand fields.
If demand_mode = uniform: show demand_rate_per_tick and demand_task_weights.
If demand_mode = rate_schedule: show demand_segments.
If demand_mode = csv_orders: show demand_csv_path and demand_events.
```

`readExperimentConfig()` must send these fields using backend snake_case keys.

Demand validation behavior:

```text
demand_rate_per_tick must be a finite number >= 0 when uniform demand is used.
demand_task_weights must be a JSON object with finite non-negative numeric values.
demand_segments must be a JSON array of segment objects.
Each demand segment should include valid start_tick, end_tick, and rate values.
demand_events must be a JSON array of event objects when provided.
demand_csv_path must be a relative trusted path when provided.
```

Layout behavior:

```text
layout_preset supports default, high_density, and one_way_aisles.
layout_file is optional.
```

Important file policy:

```text
Demand CSV and layout file inputs are currently implemented as local trusted relative-path text inputs.
This is acceptable for local single-user development.
For hosted deployments, these inputs must be replaced by admin-managed dropdowns or validated uploads.
Arbitrary server filesystem paths must not be accepted from untrusted users.
Path traversal patterns should be rejected.
```

## Run-Linked Actions, NEW in v0.8.3

Run-linked actions allow a user to start decision workflows from an existing run.

Entry points:

```text
Results view
Experiments list
```

Results DOM contract:

```text
results-decision-actions-card
```

Run-linked action attributes:

```text
data-run-action
data-run-id
```

Supported `data-run-action` values:

```text
cost
spatial
report
monte_carlo
sensitivity
optimizer
multiobjective
```

Behavior:

```text
cost: navigate to Decision -> Cost KPIs and select the run.
spatial: navigate to Decision -> Spatial and select the run.
report: open the decision job modal and prefill report config with the selected run id.
monte_carlo: open the modal and prefill Monte Carlo config using the selected run id.
sensitivity: open the modal and prefill sensitivity config using the selected run id.
optimizer: open the modal and prefill single-objective optimizer config using the selected run as baseline.
multiobjective: open the modal and prefill multi-objective config using the selected run as baseline.
```

Phase 3 configs are JSON-based. After Phase 4, Phase 3 prefilled configs open in Advanced JSON mode. Guided forms do not attempt to reverse-parse arbitrary Phase 3 JSON.

## Guided Decision Job Forms, NEW in v0.8.3

The decision job modal supports guided forms for non-CLI users and an advanced JSON editor for advanced users.

Supported guided modules:

```text
monte_carlo
sensitivity
report
spatial
optimizer
multiobjective
robustness
study
```

Modal behavior:

```text
When guided mode is enabled, render the module-specific guided form and hide the raw JSON editor.
When guided mode is disabled, hide the guided form and show the raw JSON editor.
When a Phase 3 run-linked action supplies a prefilled config object, open the modal in Advanced JSON mode.
```

Guided forms cover:

```text
Monte Carlo source selection, runs, seed, SLA target, and cost config.
Sensitivity source selection, replications, seed, SLA target, cost config, and factor rows.
Report run/study source selection.
Spatial run, top-cell count, and sort mode.
Optimizer objective, direction, trials, replications, cost config, common constraints, and search space.
Multi-objective trials, replications, population size, objectives, constraints, cost config, and search space.
Robustness candidate source, candidate limits, replications, objective, constraints, and cost config.
Study source and factor rows.
```

Monte Carlo validation:

```text
source run or base config required
n_runs >= 1
cost config must be a valid JSON object if provided
```

Sensitivity validation:

```text
source run or base config required
reps >= 1
at least one factor required
each factor requires at least one value
```

Report validation requires a run or study id. Spatial validation requires a run, `top >= 1`, and `sort by` equal to `blocked_ticks` or `blocked_events`.

Optimizer validation requires a source, supported objective, direction equal to `minimize` or `maximize`, `n_trials >= 1`, `reps >= 1`, a non-empty search space, and a cost config when the objective is `cost_per_task`.

Multi-objective validation requires at least two supported objectives, valid directions, a non-empty search space, and a cost config if any objective is `cost_per_task`.

Robustness validation requires a candidate source, `reps >= 1`, `min_pass_probability` between 0 and 1, and a cost config when the objective is `cost_per_task`. Explicit candidates require `label` and `overrides`.

Study validation requires a source, at least one factor, and at least one value per factor.

Supported objective metrics:

```text
cost_per_task
p95_cycle_time
average_cycle_time
average_throughput
tasks_completed
sla_compliance_rate
total_blocked_ticks
```

A robustness warning remains visible when reps are below 20, and a study warning remains visible for large factorial designs.

Important global rule:

```text
Guided forms only build request JSON.
They do not compute decision math.
Backend validation remains authoritative.
```

## Frontend Behavior Rules

### Loading states

Every decision screen must show a loading state before data arrives.

Current implementation:

```text
Loading…
```

### Empty states

Every decision screen must show a readable empty state.

Examples:

```text
No studies found.
No Monte Carlo studies found.
No sensitivity studies found.
No optimization studies found.
No multi-objective studies found.
No robustness studies found.
No active or recent decision jobs.
```

### Error states

Backend errors must be displayed in readable language.

Examples:

```text
Run id not found.
Study not found.
Monte Carlo study not found.
Sensitivity study not found.
Optimization study not found.
Multi-objective study not found.
Robustness study not found.
Job not found.
Unsupported decision module.
Job config must be a JSON object.
```

### Warning states

Important warnings that must remain visible in the UI:

```text
Single-replica optimizer results are exploratory.
Pareto candidates are not deployable until verified by robustness.
One-at-a-time sensitivity does not reveal interaction effects.
Pre-v0.7.2 spatial coverage is 0.0.
reps below 20 is not recommended for deployment decisions.
No feasible optimizer solution is a valid result.
```

---

## Decision UI Interpretation Rules

### Monte Carlo SLA metrics

The UI must distinguish:

```text
task_late_probability
run_any_violation_probability
```

Do not present them as the same metric.

### Optimizer best trial

The UI must show:

```text
best_trial only when it exists
```

If `best_trial` is null:

```text
No feasible solution found.
```

Do not show an infeasible trial as best.

### Multi-objective Pareto candidates

Pareto candidates are candidate configurations, not deployable recommendations.

The UI must show:

```text
Pareto candidates are not deployable until verified by robustness.
```

### Robustness recommendation

The UI must show recommended candidate only when backend provides one.

If `recommended` is null:

```text
No candidate met the required constraint pass probability.
```

---

## Frontend JavaScript Historical Note

Previous API_SURFACE versions contained:

```text
Frontend JavaScript, UPDATED in v0.6.0, UNCHANGED in v0.8.x
```

That statement is superseded by v0.8.2.

The old monolithic `static/simulation.js` is deprecated.

Its responsibilities are preserved in the new modular frontend files:

```text
static/js/utils.js
static/js/state.js
static/js/charts.js
static/js/warehouse.js
static/js/experiments.js
static/js/decision.js
static/js/app.js
```

Old v0.5/v0.6 DOM IDs and functions remain conceptually preserved, but the current source of truth is the modular frontend structure.

---

## UI / Visualization, UPDATED in v0.8.2

Existing UI workflow remains:

```text
Setup
Run
Fast
Results
Experiments
Visualization
Analysis
Compare
```

New Decision workflow added:

```text
Decision
├── Overview
├── Studies
├── Reports
├── Spatial
├── Cost KPIs
├── Monte Carlo
├── Sensitivity
├── Optimization
├── Multi-Objective
├── Robustness
└── Jobs
```

Decision views must not compute decision math.

Decision views must read backend JSON only.

Decision views must handle:

```text
loading
empty
error
success
partial success
```

Decision views must show warnings for exploratory or non-deployable results.

---

## Security Rules, UPDATED in v0.8.2

Decision jobs can create expensive CPU and disk work.

Required protections:

```text
ID validation
no arbitrary filesystem paths
no raw static serving of data directories
upload validation if uploads are added
request size limits
rate limiting for job creation in hosted deployments
authentication for hosted deployments
authorization for job submission
concurrency limits
```

ID validation pattern:

```text
^[A-Za-z0-9_\-]+$
```

Do not build filesystem paths directly from unvalidated user input.

Current job manager concurrency:

```text
max_workers = 1
```

---

## Deployment Notes, UPDATED in v0.8.2

Serve with:

```bash
gunicorn app:app
```

or platform equivalent.

Never use the Flask development server when hosted.

`data/runs/` must be on persistent storage.

Ephemeral filesystems lose experiments on restart.

Decision job state is also in-memory in v0.8.2, so Flask restarts lose the active job list.

ECharts may load from CDN or be vendored at:

```text
static/vendor/echarts.min.js
```

For offline or air-gapped hosts, vendor ECharts.

If the public can start experiments or decision jobs, add:

```text
authentication
authorization
rate limiting
job concurrency limits
upload validation
request size limits
```

Experiments consume CPU and disk.

Fast mode pins one core for its duration.

Optimization, Monte Carlo, sensitivity, multi-objective, and robustness studies are CPU-intensive.

For production use, consider:

```text
queueing
batch scheduling
dedicated worker processes
persistent job history
```

---

## Engineering Principles for Decision Layer, v0.8.x

Single-replica results are exploratory.

Single-replica optimizer and multi-objective trials are cheap but noisy.

They identify candidate regions. They do not prove operational robustness.

Robustness verification is mandatory before deployment.

Use `decision/robustness.py` with at least `reps: 20` before treating a configuration as deployable.

If a candidate is close to a constraint boundary, use `reps: 30` or more.

`constraint_pass_probability` is the critical deployment metric.

A candidate with the lowest mean `cost_per_task` but a 70% constraint pass probability is not deployable.

A slightly more expensive candidate with 95%+ constraint pass probability is usually preferable.

Pareto fronts are candidate sets.

Multi-objective Pareto fronts show tradeoffs. They are not final answers.

Each Pareto candidate should be robustness-checked.

OAT sensitivity does not show interactions.

One-at-a-time sensitivity identifies local parameter influence. It cannot prove interaction effects.

Use full DoE, multi-objective search, or targeted experiments for interactions.

Infeasible optimization results are valid results.

If `feasible_count` is zero, the optimizer or multi-objective study has proven that the current search space and constraints are incompatible.

Do not relax this silently.

Either widen the search space, relax constraints, or redesign the operational scenario.

Run artifacts remain immutable.

Monte Carlo, sensitivity, optimizer, multi-objective, and robustness modules may create new runs.

They must never modify existing `data/runs/<run_id>/` artifacts.

Frontend must not compute decision math.

Frontend must only render backend-produced decision artifacts.

---

## Recommended v0.8.2 Workflow

The recommended decision workflow is:

```text
1. Define baseline experiment and CostConfig.
2. Run a normal simulation or benchmark and produce data/runs/<run_id>/.
3. Run Monte Carlo to measure baseline variability.
4. Run sensitivity analysis to identify high-impact parameters.
5. Run single-objective optimization to find a cheap feasible configuration.
6. Run multi-objective optimization to explore cost versus cycle-time tradeoffs.
7. Select Pareto or best candidates.
8. Run robustness verification with reps >= 20.
9. Choose the recommended candidate only if constraint_pass_probability meets the required operational risk threshold.
10. Generate engineering reports from the final verified configuration.
```

The v0.8.3 frontend supports this workflow through the Decision Center, Job Launcher, run-linked actions, and guided decision forms.
Advanced decision charts, spatial heatmap overlay, and managed file selection remain pending.

---

## Extension Points

### Preserved v0.4 extension points

```text
INTERSECTION -> formal intersection traffic control.
MAIN_AISLE -> priority routing or speed changes.
PACKING -> packing queue or processing delay.
RECEIVING -> inbound task generation coupling.
SHIPPING -> outbound task completion coupling.
EMPTY -> dynamic obstacles or editor placement.
BUFFER -> QC delay or put-away scheduling.
PICK_STATION -> pick processing time or queueing.
CONSOLIDATION -> order merge logic.
STAGING -> carrier lane assignment.
Physical load handoff -> v0.4 uses logical task recovery, not physical pallet transfer.
Predictive maintenance -> not implemented.
```

### New v0.5 extension points

```text
SQLite/Parquet storage if CSV experiments grow large.
Explicit in-simulation event hooks to replace tick-resolution inference.
Per-robot time-series utilization/blocked columns if summary-level distributions become insufficient.
Server-side analysis caching if hosted traffic grows.
```

### New v0.6 extension points

```text
Additional PathPlanner implementations plug in through ExperimentConfig.path_planner and create_path_planner_from_name.
Examples: D* Lite, LPA*, congestion-aware A*.

Additional Scheduler implementations plug in through ExperimentConfig.scheduler and create_scheduler_from_name.
Examples: Hungarian assignment, rolling horizon optimizer, reinforcement learning.

Additional ConflictManager implementations plug in through ExperimentConfig.conflict_manager and create_conflict_manager_from_name.
Examples: one-way aisle policies, intersection signal control, full CBS/ECBS.

Edge reservations in ReservationTable to prevent swap collisions.
Persist conflict manager diagnostics to summary.json for cross-run comparison.
```

### New v0.7.1 extension points

```text
Persist Cost KPIs into summary.json or a dedicated decision.json artifact.
Add directional aisle constraints through a dedicated ConflictManager.
Add demand-profile validation against layout location availability before run start.
Add study-level demand factors and layout factors to DoE configs.
```

### New v0.7.2 extension points

```text
Frontend heatmap overlay of spatial bottlenecks on the warehouse layout.
Spatial payload builder in analysis/web.py.
GET /api/runs/<run_id>/spatial route once backend is proven.
Cell-type labeling of bottleneck cells via reconstructed layout presets.
```

The spatial route is implemented in v0.8.2 through `decision/web.py`.

### New v0.8.0 extension points

```text
Bayesian optimization samplers as alternatives to TPE.
Sobol quasi-random sequences for sensitivity analysis.
Variance-based global sensitivity indices beyond OAT.
Parallel Monte Carlo execution across multiple CPU cores or cluster nodes.
Persistent Monte Carlo trial registry for cross-study comparison.
```

### New v0.8.1 extension points

```text
Multi-fidelity optimization.
Constrained NSGA-III for many-objective optimization.
Robust optimization that optimizes worst-case performance across seed distributions.
Surrogate modeling to replace simulation calls in the optimization loop.
Automated Markdown reports from optimization and robustness studies.
Frontend optimization dashboards after backend workflows are proven.
Pareto front comparison API once multi-objective studies are stable.
Robustness-aware optimizer that directly uses constraint_pass_probability in the objective or constraint system.
```

### New v0.8.2 extension points

```text
Persistent job history.
Job progress callbacks.
Saved cost configs.
```

### Completed in v0.8.3

```text
Run-linked actions from Results and Experiments.
Guided decision job forms.
Setup v0.7.1 demand and layout fields.
```

### Remaining v0.8.3+ extension points

```text
Managed demand CSV selection/upload.
Managed layout file selection/upload.
Saved cost configs.
Decision artifact comparison views.
Pareto scatter charts.
Tornado charts.
Monte Carlo histograms.
Spatial heatmap overlay.
Robustness guided import from optimizer summary.
Guided forms that parse existing JSON back into guided controls.
```

---

## Documentation Maintenance

When implementing future changes:

Update this file whenever:

```text
Flask routes change
decision payload schemas change
job API changes
frontend views change
DOM IDs change
CSS class contracts change
JS module structure changes
storage format changes
CLI commands change
```

Keep code as the source of truth.