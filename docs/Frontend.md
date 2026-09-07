# Frontend Implementation & Test Plan — v0.7.1+ Decision Features

Project: `warehouse_simulator`

Scope: Frontend implementation and testing for all decision-layer features from v0.7.1 through v0.8.1.

Source of truth:

1. Existing code.
2. `API_SURFACE.md`.
3. This plan.

If this document disagrees with code, code wins. Update this document immediately.

Version note:

`API_SURFACE.md` documents the decision layer as introduced in v0.7.1, spatial diagnostics in v0.7.2, uncertainty analysis in v0.8.0, and optimization/robustness in v0.8.1. If the repository uses a different local tag such as v0.7.0, code wins, but the documentation should be corrected to match the code.

---

## 1. Goal

Turn the completed backend decision modules into a frontend decision-support workflow that can be used by non-CLI users.

The frontend must allow a user to:

1. Configure realistic v0.7.1 scenarios.
2. Inspect run-level business KPIs.
3. Inspect spatial bottlenecks.
4. Browse studies / DoE results.
5. Browse Monte Carlo and sensitivity results.
6. Browse optimization, multi-objective optimization, and robustness results.
7. Launch decision jobs from the UI.
8. Monitor decision job status.
9. Open and inspect generated decision artifacts.
10. Follow the recommended v0.8.1 workflow:
    baseline -> uncertainty -> sensitivity -> optimization -> tradeoffs -> robustness -> recommendation -> report.

The frontend is not a new analytics engine. It is a viewer, launcher, and state machine for backend-produced decision artifacts.

---

## 2. Non-Goals

The frontend must not:

1. Compute decision metrics.
2. Compute cost KPIs.
3. Compute SLA compliance.
4. Compute confidence intervals.
5. Compute tornado deltas.
6. Compute Pareto dominance.
7. Compute robustness pass probability.
8. Compute spatial bottleneck aggregation.
9. Modify existing run artifacts.
10. Directly read or write filesystem artifacts without a backend API.
11. Depend on live simulation objects for decision views.
12. Treat single-replica optimizer or Pareto results as deployable recommendations.

---

## 3. Target User

The target user is a non-CLI user.

Therefore the UI must provide:

1. Guided forms for common decision jobs.
2. JSON templates for advanced users.
3. Backend validation errors in readable language.
4. Clear loading, empty, error, and success states.
5. Job status tracking.
6. Links from decision artifacts back to underlying runs.
7. Clear warnings when evidence is exploratory rather than deployable.

A read-only artifact browser is useful, but it is not sufficient for the stated non-CLI user goal. Job launching is required.

---

## 4. Strict Architecture Rules

### Rule 1 — Frontend must not compute decision logic

Frontend must not calculate:

- cost KPIs
- SLA compliance
- confidence intervals
- tornado deltas
- Pareto dominance
- robustness pass probability
- spatial aggregation
- study comparisons
- optimizer feasibility
- constraint satisfaction

All decision math remains in Python.

Frontend responsibilities:

- fetch JSON
- render tables/charts
- submit forms
- poll jobs
- display errors/loading/empty states
- sort or filter already-computed rows for display only

### Rule 2 — Decision views read saved artifacts only

Decision views must read backend-produced JSON derived from:

    data/runs/<run_id>/
    data/studies/<study_id>/
    data/reports/
    data/monte_carlo/<mc_id>/
    data/sensitivity/<study_id>/
    data/optimizations/<opt_id>/
    data/multiobjective/<study_id>/
    data/robustness/<robust_id>/

Decision job creation may write new artifacts, but only through backend decision modules.

Existing `data/runs/<run_id>/` artifacts are immutable and must never be modified by decision jobs or decision UI actions.

### Rule 3 — The frontend must access artifacts through backend JSON APIs

The browser must not fetch raw CSV, JSON, or Markdown files directly from static filesystem paths.

The backend must expose controlled JSON APIs.

Routes must validate IDs and sanitize payloads.

### Rule 4 — Long-running decision jobs must be asynchronous

Monte Carlo, sensitivity, optimization, multi-objective optimization, and robustness jobs can be CPU-intensive.

The frontend must not block on a synchronous Flask request.

The backend must provide:

- job creation
- job status polling
- job listing
- error reporting
- artifact linkage after completion

The first implementation may use a simple in-process job manager for local single-user use.

Hosted production deployments should use a proper queue or worker process.

### Rule 5 — Large artifacts must be paginated, aggregated, or downsampled

Full CSV files must not be sent to the browser.

Backend payload builders must:

- paginate large tables
- aggregate summaries server-side
- downsample chart data where necessary
- sanitize NaN and Infinity
- convert numpy scalars to native JSON types

### Rule 6 — File inputs must be controlled

The UI must not allow arbitrary server filesystem paths to be typed by untrusted users.

File inputs such as:

- `demand_csv_path`
- `layout_file`
- `cost_config`

must be handled through one of these controlled mechanisms:

1. Admin-managed file dropdowns.
2. Validated file uploads.
3. Inline JSON editors for config-like payloads such as cost config.

### Rule 7 — Decision jobs must not hijack the live experiment runner

The existing Flask `holder["runner"]` pattern is for interactive experiment execution.

Decision jobs must use a separate decision job manager.

Decision jobs may use `ExperimentRunner` internally through backend decision modules, but they must not interfere with the live UI experiment runner state.

### Rule 8 — Backend decision payloads should preserve snake_case

Stored configs and decision summaries use snake_case.

The frontend may use camelCase for live simulation state, as already established, but decision-layer payloads should preserve backend snake_case keys to avoid unnecessary mapping errors.

### Rule 9 — Every decision screen must handle empty, loading, error, and success states

Each decision view must define:

- loading state
- empty state
- error state
- partial-success state
- success state

Errors must be readable for non-CLI users.

### Rule 10 — Hosted deployments require protection

If the public can start experiments or decision jobs, add:

- authentication
- authorization
- rate limiting
- job concurrency limits
- upload validation
- request size limits

Decision jobs consume CPU and disk.

---

## 5. Navigation and Information Architecture

Keep the existing workflow intact:

    Setup
    Run
    Fast
    Results
    Experiments
    Visualization
    Analysis
    Compare

Add a new top-level area:

    Decision

Inside Decision:

    Decision
    ├── Overview
    ├── Studies
    ├── Reports
    ├── Spatial
    ├── Monte Carlo
    ├── Sensitivity
    ├── Optimization
    ├── Multi-Objective
    ├── Robustness
    └── Jobs

Do not force all decision features into Setup.

Setup should handle single experiment configuration.

Decision should handle multi-run studies, uncertainty analysis, optimization, and robustness verification.

---

## 6. Backend API Contract

The backend should add a thin Flask decision API layer.

Business logic should live in a new module such as:

    decision/web.py

or:

    decision/api.py

Do not put heavy logic directly in `app.py`.

### 6.1 Overview endpoint

    GET /api/decision/overview

Returns counts and recent artifacts for:

- studies
- reports
- Monte Carlo studies
- sensitivity studies
- optimizations
- multi-objective studies
- robustness studies
- active jobs

### 6.2 Study endpoints

    GET /api/decision/studies
    GET /api/decision/studies/<study_id>
    GET /api/decision/studies/<study_id>/results

Payload requirements:

- study config summary
- generated time
- result rows
- run_id per row
- report availability
- errors

Each study row should trace back to:

    data/runs/<run_id>/

### 6.3 Report endpoints

    GET /api/decision/reports
    GET /api/decision/reports/<report_id>

Payload requirements:

- report id
- generated time
- source type: run or study
- source id
- markdown text or sanitized rendered content

Reports are generated artifacts. The UI must not edit them.

### 6.4 Run-level decision endpoints

    GET /api/runs/<run_id>/cost-kpis
    GET /api/runs/<run_id>/spatial

These endpoints read saved run artifacts only.

Cost KPI endpoint requirements:

- total operating cost
- cost per task
- SLA compliance rate
- completed tasks
- SLA-evaluated tasks
- late tasks
- currency
- cost breakdown
- null handling for zero completed tasks
- null handling for missing SLA target

Spatial endpoint requirements:

- run id
- total blocked events
- events with coordinates
- coverage
- top bottleneck cells
- sort metric
- pre-v0.7.2 warning when coverage is 0.0

### 6.5 Monte Carlo endpoints

    GET /api/decision/monte-carlo
    GET /api/decision/monte-carlo/<mc_id>
    GET /api/decision/monte-carlo/<mc_id>/results

Payload requirements:

- mc_id
- generated_at
- n_runs_requested
- successful_runs
- failed_runs
- seeds
- effective_sla_target_ticks
- aggregate KPIs
- aggregate SLA statistics
- errors
- paginated trial rows

The UI must distinguish:

- `task_late_probability`
- `run_any_violation_probability`

Do not present them as the same metric.

### 6.6 Sensitivity endpoints

    GET /api/decision/sensitivity
    GET /api/decision/sensitivity/<study_id>
    GET /api/decision/sensitivity/<study_id>/results
    GET /api/decision/sensitivity/<study_id>/tornado

Payload requirements:

- study id
- reps
- seeds
- baseline
- factor results
- tornado data
- errors
- reused baseline flags

Default tornado targets:

- `cost_per_task`
- `p95_cycle_time`

### 6.7 Optimization endpoints

    GET /api/decision/optimizations
    GET /api/decision/optimizations/<opt_id>
    GET /api/decision/optimizations/<opt_id>/trials

Payload requirements:

- opt_id
- objective
- direction
- n_trials
- reps
- constraints
- feasible_count
- infeasible_count
- best_trial
- search_space
- paginated trials

Important rule:

`best_trial` is selected from feasible trials only.

If no feasible trial exists, `best_trial` must be null.

### 6.8 Multi-objective endpoints

    GET /api/decision/multiobjective
    GET /api/decision/multiobjective/<study_id>
    GET /api/decision/multiobjective/<study_id>/trials
    GET /api/decision/multiobjective/<study_id>/pareto

Payload requirements:

- study id
- objectives
- constraints
- total_trials
- feasible_count
- pareto_count
- pareto_trials
- paginated all-trial rows
- base_config
- cost_config
- search_space

Important rule:

Pareto candidates are not deployable until verified by robustness.

### 6.9 Robustness endpoints

    GET /api/decision/robustness
    GET /api/decision/robustness/<robust_id>
    GET /api/decision/robustness/<robust_id>/results

Payload requirements:

- robust_id
- reps
- base_seed
- objective
- direction
- constraints
- min_pass_probability
- successful_runs
- failed_runs
- recommended candidate
- candidate results
- constraint details
- errors

Each candidate result should include:

- label
- overrides
- successful_reps
- failed_reps
- constraint_pass_probability
- robust_pass
- objective_mean
- objective_stdev
- metrics
- constraint_details

### 6.10 Job endpoints

    POST /api/decision/jobs
    GET /api/decision/jobs
    GET /api/decision/jobs/<job_id>
    POST /api/decision/jobs/<job_id>/cancel

Job creation request body:

    {
      "module": "monte_carlo",
      "config": { ... }
    }

Supported modules:

- `study`
- `report`
- `spatial`
- `monte_carlo`
- `sensitivity`
- `optimizer`
- `multiobjective`
- `robustness`

Job response:

    {
      "job_id": "...",
      "module": "...",
      "status": "queued",
      "created_at": "..."
    }

Job status response:

    {
      "job_id": "...",
      "module": "...",
      "status": "running",
      "created_at": "...",
      "started_at": "...",
      "finished_at": null,
      "artifact_type": null,
      "artifact_id": null,
      "progress": null,
      "error": null
    }

Job status values:

    queued
    running
    finished
    failed
    cancelled

If cancellation is not implemented, return a clear error or disable cancellation in the UI.

### 6.11 Template endpoints

    GET /api/decision/templates
    GET /api/decision/templates/<module>

Supported templates:

- `cost_config`
- `study`
- `monte_carlo`
- `sensitivity`
- `optimizer`
- `multiobjective`
- `robustness`

Templates allow non-CLI users to start from valid example JSON instead of blank forms.

### 6.12 File endpoints

If file selection or upload is supported:

    GET /api/decision/files/demand-csv
    GET /api/decision/files/layouts
    GET /api/decision/files/cost-configs
    POST /api/decision/files/upload

Rules:

- validate file type
- validate file size
- store uploads in a controlled directory
- never expose arbitrary filesystem paths
- never allow path traversal

If uploads are not supported, provide dropdowns of admin-managed files.

---

## 7. Job Execution Model

### 7.1 Decision job manager

Create a separate decision job manager.

It must not reuse the live simulation holder:

    holder = {
      "simulation": ...,
      "runner": ...
    }

The decision job manager is responsible for:

- job ids
- module names
- configs
- queued/running/finished/failed state
- artifact ids
- error messages
- concurrency limits
- optional progress reporting

### 7.2 Concurrency policy

First version recommendation:

Allow only one decision job at a time.

Reason:

Monte Carlo, sensitivity, optimization, multi-objective optimization, and robustness can be CPU-intensive.

Later versions may support:

- one job per module
- worker pool
- queue priority
- batch scheduling

### 7.3 Progress reporting

Minimum acceptable:

    queued
    running
    finished
    failed

Better:

    completed_units
    total_units
    elapsed_seconds

Best:

Module-specific progress, such as:

- Monte Carlo: completed trials / total trials
- Sensitivity: factor / value / replication
- Optimizer: trial / total trials
- Multi-objective: generation or trial / total trials
- Robustness: candidate / replication

If backend modules do not expose progress callbacks, do not promise rich progress in the UI. Implement status-only polling first.

### 7.4 Production behavior

For local single-user use, a background thread may be acceptable.

For hosted production, use:

- queueing
- dedicated worker processes
- batch scheduling
- authentication
- rate limiting

Do not use the Flask development server for hosted production.

---

## 8. File Handling Policy

### 8.1 Demand CSV

For `demand_mode = csv_orders`, the UI must not require a non-CLI user to know a server path.

Preferred options:

1. Dropdown of admin-managed CSV files.
2. File upload with backend validation.
3. Inline CSV preview if small.

Do not accept arbitrary paths from untrusted users.

### 8.2 Layout file

For custom layouts, preferred options:

1. Use built-in presets:
   - default
   - high_density
   - one_way_aisles
2. Select an admin-managed layout JSON file.
3. Upload a layout JSON file.
4. Paste layout JSON into an advanced editor.

The backend must validate layout structure before starting a run.

### 8.3 Cost config

Cost config is required for `cost_per_task` metrics and cost objectives.

Preferred UI behavior:

1. Provide a cost config JSON editor.
2. Provide a cost config template.
3. Optionally allow saved cost configs.
4. Do not require a filesystem path for non-CLI users.

Example cost config template:

    {
      "robot_opex_per_hour": 12.5,
      "charger_infra_cost_per_hour": 2.0,
      "downtime_cost_per_hour": 30.0,
      "sla_target_ticks": 300,
      "sla_penalty_per_late_tick": 0.5,
      "currency": "USD"
    }

If objective or KPI requires `cost_per_task` and no valid cost config exists, block submission with a readable error.

---

## 9. Setup View Changes

Setup must support v0.7.1 experiment fields.

Add these fields conditionally:

- `demand_mode`
- `demand_rate_per_tick`
- `demand_task_weights`
- `demand_segments`
- `demand_csv_path`
- `demand_events`
- `layout_preset`
- `layout_file`

Recommended DOM ids:

    cfg-demand-mode
    cfg-demand-rate-per-tick
    cfg-demand-task-weights
    cfg-demand-segments
    cfg-demand-csv-file
    cfg-demand-events
    cfg-layout-preset
    cfg-layout-file

`readExperimentConfig()` must include these fields using snake_case keys.

### 9.1 Conditional demand form

If `demand_mode = legacy`:

Show no additional demand fields.

If `demand_mode = uniform`:

Show:

- `demand_rate_per_tick`
- `demand_task_weights`

If `demand_mode = rate_schedule`:

Show:

- `demand_segments`

If `demand_mode = csv_orders`:

Show:

- file selector or upload control for demand CSV
- optional preview

### 9.2 Conditional layout form

If `layout_preset = default`:

Show no layout file field.

If `layout_preset = high_density` or `one_way_aisles`:

Show preset description and no file field.

If custom layout is supported:

Show:

- layout file selector
- or upload control
- or JSON editor

### 9.3 Setup UX rule

Do not make Setup a giant wall of fields.

Use sections:

    Scenario
    ├── Demand
    └── Layout

Show only relevant fields for the selected mode.

---

## 10. Decision Center Screens

### 10.1 Decision Overview

Purpose: show what decision artifacts exist.

Show cards for:

- Studies
- Reports
- Monte Carlo
- Sensitivity
- Optimization
- Multi-Objective
- Robustness
- Jobs

For each card show:

- artifact count
- latest artifact id
- latest generated time
- success/failure state
- open button

### 10.2 Studies view

Purpose: browse v0.7.1 factorial DoE studies.

Show:

- study id
- generated time
- study config summary
- result table
- report availability
- errors

Result table columns should include:

- `run_id`
- factor columns
- `tasks_completed`
- `average_cycle_time`
- `p95_cycle_time`
- `average_throughput`
- `cost_per_task`
- `sla_compliance_rate`

Each row must link to the existing run result page using `run_id`.

### 10.3 Reports view

Purpose: view generated Markdown reports.

Support:

- single-run reports
- study reports

Show:

- report name
- source type
- source id
- generated time
- Markdown preview
- download button

Do not allow editing reports in the UI.

### 10.4 Spatial view

Purpose: inspect v0.7.2 spatial bottleneck analysis.

Show:

- run id
- total blocked events
- events with coordinates
- coverage
- top bottleneck cells

Columns:

- `x`
- `y`
- `blocked_events`
- `blocked_ticks`

Sorting options:

- `blocked_ticks`
- `blocked_events`

Important warnings:

- Pre-v0.7.2 runs have coverage 0.0.
- A robot can drift during yield, so exact cells are approximate.
- Hotspots near chargers indicate capacity problems.
- Hotspots at aisle intersections indicate traffic-control problems.

First version should use a table.

Heatmap overlay is optional and can be delayed.

### 10.5 Monte Carlo view

Purpose: inspect variability and SLA risk.

Show summary cards:

- requested runs
- successful runs
- failed runs
- effective SLA target
- task late probability
- run any-violation probability

Show KPI table:

For each KPI:

- count
- mean
- stdev
- min
- p05
- median
- p95
- max
- mean_ci95_low
- mean_ci95_high

Useful KPIs:

- `cost_per_task`
- `average_cycle_time`
- `p95_cycle_time`
- `average_throughput`
- `tasks_completed`

Show trial table with pagination.

Show errors when failed runs exist.

Important SLA interpretation:

`task_late_probability` is the fraction of completed tasks that violated the SLA target.

`run_any_violation_probability` is the fraction of Monte Carlo trials where at least one task violated the SLA target.

`task_late_probability` is usually more operationally meaningful.

### 10.6 Sensitivity view

Purpose: inspect one-at-a-time parameter influence.

Show:

- baseline summary
- factor table
- tornado charts
- errors

Show tornado charts for:

- `cost_per_task`
- `p95_cycle_time`

Factor table columns:

- factor name
- value
- reused_baseline
- runs
- `cost_per_task`
- `p95_cycle_time`
- delta cost
- delta percent cost
- delta p95
- delta percent p95

Important warning:

One-at-a-time sensitivity does not reveal interaction effects.

### 10.7 Single-objective optimization view

Purpose: inspect constrained single-objective search results.

Show:

- objective
- direction
- trials
- reps
- feasible count
- infeasible count
- best trial
- search space
- constraints

Important rule:

`best_trial` is selected from feasible trials only.

If `best_trial` is null, show:

    No feasible solution found.

Do not show an infeasible trial as the best result.

Show trial table with pagination.

Useful chart:

- objective value versus trial number
- feasible/infeasible coloring

Important warning:

Single-replica optimizer results are exploratory. Run robustness verification before deployment.

### 10.8 Multi-objective view

Purpose: inspect tradeoffs and Pareto candidates.

Show:

- objectives
- constraints
- total trials
- feasible count
- Pareto count
- Pareto table
- Pareto scatter chart

Typical Pareto chart axes:

- x: `cost_per_task`
- y: `p95_cycle_time`

Color points by:

- feasible
- infeasible
- Pareto front member

Important warning:

Pareto candidates are not deployable until verified by robustness.

Provide action:

    Send to Robustness

### 10.9 Robustness view

Purpose: verify deployability under stochastic variation.

This is the most important decision screen.

Show:

- reps
- base seed
- objective
- direction
- constraints
- min pass probability
- successful runs
- failed runs
- recommended candidate
- candidate table
- errors

Candidate table columns:

- label
- successful reps
- failed reps
- constraint_pass_probability
- robust_pass
- objective_mean
- objective_stdev
- constraint details

Important visual:

Show `constraint_pass_probability` as a bar or gauge with a threshold line at `min_pass_probability`.

Important rules:

- A candidate is robust when `constraint_pass_probability >= min_pass_probability`.
- `recommended` is null when no candidate meets `min_pass_probability`.
- A candidate with the lowest mean cost but insufficient pass probability is not deployable.
- `reps: 20` is the practical minimum for deployment decisions.
- If a candidate is close to a constraint boundary, use `reps: 30` or more.

Show warning when:

    reps < 20

### 10.10 Jobs view

Purpose: monitor decision jobs.

Show:

- job id
- module
- status
- created time
- started time
- finished time
- artifact type
- artifact id
- progress
- error

Provide actions:

- refresh
- open artifact when finished
- cancel if supported

Polling should be used while jobs are active.

---

## 11. Run-Linked Actions

The easiest entry point for non-CLI users is an existing run.

Add actions to Results or Experiments pages:

    View cost KPIs
    View spatial bottlenecks
    Generate run report
    Start Monte Carlo from this run
    Start sensitivity from this run
    Use as optimizer baseline
    Use as multi-objective baseline

These actions should prefill decision job forms using the selected run id.

Examples:

Monte Carlo:

    from_run_id: selected run

Sensitivity:

    from_run_id: selected run

Optimizer:

    from_run_id: selected run

Multi-objective:

    from_run_id: selected run

Robustness:

    from_multiobjective: selected multi-objective summary

This avoids forcing users to manually reconstruct configs.

---

## 12. Decision Job Forms

For non-CLI users, provide guided forms first and JSON editors as advanced fallbacks.

### 12.1 Monte Carlo form

Fields:

- source type:
  - from run id
  - from base config JSON
- run id dropdown or config JSON
- number of runs
- base seed
- explicit seeds optional
- SLA target ticks optional
- cost config JSON optional

Validation:

- number of runs >= 1
- source run or base config required
- seeds length must match number of runs if explicit seeds are provided
- cost config required if cost KPIs are requested

Warnings:

- Monte Carlo creates multiple immutable runs.
- Large run counts consume CPU and disk.

### 12.2 Sensitivity form

Fields:

- source type:
  - from run id
  - from base config JSON
- run id dropdown or config JSON
- reps
- base seed
- SLA target ticks optional
- cost config JSON optional
- factors JSON

Factor template:

    [
      {
        "name": "num_robots",
        "values": [6, 8, 10]
      }
    ]

Validation:

- at least one factor
- each factor has at least one value
- reps >= 1
- source run or base config required

Warning:

One-at-a-time sensitivity does not reveal interaction effects.

### 12.3 Single-objective optimizer form

Fields:

- source type:
  - from run id
  - from base config JSON
- objective
- direction
- trials
- reps
- base seed
- SLA target ticks optional
- cost config JSON
- constraints JSON
- search space JSON

Supported objectives:

- `cost_per_task`
- `p95_cycle_time`
- `average_throughput`
- `tasks_completed`

Validation:

- search space must not be empty
- objective must be supported
- direction must be minimize or maximize
- trials >= 1
- reps >= 1
- cost config required when objective is `cost_per_task`
- constraints must use supported keys

Primary supported constraints:

    p95_cycle_time_max
    sla_compliance_rate_min

Warning:

Single-replica optimizer results are exploratory.

### 12.4 Multi-objective form

Fields:

- source type:
  - from run id
  - from base config JSON
- objectives JSON
- constraints JSON
- search space JSON
- trials
- reps
- base seed
- population size optional
- SLA target ticks optional
- cost config JSON

Objective template:

    [
      {
        "metric": "cost_per_task",
        "direction": "minimize"
      },
      {
        "metric": "p95_cycle_time",
        "direction": "minimize"
      }
    ]

Validation:

- at least two objectives for a meaningful Pareto workflow
- search space must not be empty
- objective metrics must be supported
- directions must be valid
- trials >= 1
- reps >= 1
- cost config required if any objective is `cost_per_task`

Warning:

Pareto candidates are not deployable until verified by robustness.

### 12.5 Robustness form

Fields:

- candidate source:
  - explicit candidates JSON
  - from multi-objective summary
  - from optimizer summary
- max candidates if using multi-objective summary
- reps
- base seed
- objective
- direction
- min pass probability
- SLA target ticks optional
- cost config JSON
- constraints JSON

Validation:

- at least one candidate or valid source summary
- reps >= 1
- min pass probability between 0 and 1
- constraints must not be empty for deployment decisions
- cost config required if objective is `cost_per_task`

Strong warning:

`reps: 20` is the practical minimum for deployment decisions.

If candidate is near a constraint boundary, suggest:

    reps >= 30

### 12.6 Study form

Fields:

- study config JSON
- optional template button

Validation:

- factorial factors must be valid
- base config must be valid
- study must produce at least one run

Warning:

Large factorial designs can create many runs.

### 12.7 Report form

Fields:

- source type:
  - run id
  - study id or study directory
- run id dropdown or study dropdown

Validation:

- run or study must exist

Report generation may be synchronous if fast, or submitted as a job if slow.

### 12.8 Spatial form

Fields:

- run id dropdown
- top N
- sort by:
  - blocked_ticks
  - blocked_events

Validation:

- run id must exist
- top N >= 1

---

## 13. Error, Empty, and Warning States

Every decision screen must define these states.

### 13.1 Empty states

Examples:

Studies:

    No studies found. Run a factorial study from the CLI or start a study job.

Monte Carlo:

    No Monte Carlo studies found. Start Monte Carlo from an existing run.

Sensitivity:

    No sensitivity studies found. Start sensitivity analysis from an existing run.

Optimizer:

    No optimization studies found. Start a single-objective optimization.

Multi-objective:

    No multi-objective studies found. Start a multi-objective optimization.

Robustness:

    No robustness studies found. Verify Pareto or optimizer candidates with robustness verification.

Jobs:

    No active or recent decision jobs.

### 13.2 Error states

Show backend errors in readable language.

Examples:

Missing run:

    Run id not found.

Invalid config:

    The job config is invalid.

Missing cost config:

    cost_per_task requires a valid CostConfig.

Missing SLA target:

    SLA metrics are not evaluated because sla_target_ticks is not set.

Optuna missing:

    Optimization requires Optuna. Install the optimization dependencies.

No feasible optimizer result:

    No feasible trial found. The search space or constraints may be too strict.

No robust candidate:

    No candidate met the required constraint pass probability.

### 13.3 Warning states

Use warnings for exploratory or partial evidence.

Examples:

Single-replica optimizer:

    Single-replica optimizer results are exploratory. Run robustness verification before deployment.

Pareto candidate:

    Pareto candidates are not deployable until verified by robustness.

Low robustness reps:

    reps below 20 is not recommended for deployment decisions.

Pre-v0.7.2 spatial:

    This run was recorded before spatial blockage coordinates were added. Coverage is 0.0.

OAT sensitivity:

    One-at-a-time sensitivity does not reveal interaction effects.

Infeasible optimization:

    No feasible trial exists. Do not silently relax constraints. Either widen the search space, relax constraints, or redesign the operational scenario.

---

## 14. Payload and Visualization Rules

### 14.1 Tables

Paginate large tables.

Recommended default page size:

    50 or 100 rows

Include:

- total_rows
- page
- page_size
- rows

### 14.2 Charts

Use ECharts.

Recommended charts:

Monte Carlo:

- histogram of KPI distributions
- box plot optional
- confidence interval table

Sensitivity:

- horizontal tornado chart

Optimizer:

- objective value versus trial number
- feasible/infeasible coloring

Multi-objective:

- Pareto scatter plot
- Pareto table

Robustness:

- constraint pass probability bar chart
- threshold line at min_pass_probability

Spatial:

- top bottleneck table first
- heatmap overlay optional later

### 14.3 Downsampling

Do not send full CSV files.

Use server-side aggregation or downsampling.

For chart payloads, return points in a compact format such as:

    [[tick, value], ...]

Sanitize:

- NaN -> null
- Infinity -> null
- numpy scalars -> native JSON numbers

---

## 15. Security Rules

The decision UI can create expensive CPU and disk work.

Implement:

1. ID validation.
2. No arbitrary filesystem paths.
3. No raw static serving of data directories.
4. Upload validation.
5. Request size limits.
6. Rate limiting for job creation.
7. Authentication for hosted deployments.
8. Authorization for job submission.
9. Concurrency limits.
10. Audit logging for job submission and deletion if deletion is supported.

ID validation pattern for run-like IDs:

    ^[A-Za-z0-9_\-]+$

Do not build filesystem paths directly from unvalidated user input.

---

## 16. Frontend State Machine and DOM IDs

Add a new view:

    view-decision

Add nav button:

    nav-decision-btn

Recommended decision subview containers:

    decision-overview
    decision-studies
    decision-reports
    decision-spatial
    decision-monte-carlo
    decision-sensitivity
    decision-optimization
    decision-multiobjective
    decision-robustness
    decision-jobs

Recommended controls:

    decision-refresh-btn
    decision-open-studies-btn
    decision-open-reports-btn
    decision-open-spatial-btn
    decision-open-monte-carlo-btn
    decision-open-sensitivity-btn
    decision-open-optimizations-btn
    decision-open-multiobjective-btn
    decision-open-robustness-btn
    decision-open-jobs-btn

Recommended detail containers:

    study-detail
    report-detail
    spatial-detail
    monte-carlo-detail
    sensitivity-detail
    optimization-detail
    multiobjective-detail
    robustness-detail
    job-detail

Recommended job modal controls:

    decision-job-modal
    decision-job-module
    decision-job-config-editor
    decision-job-template-btn
    decision-job-submit-btn
    decision-job-cancel-btn
    decision-job-error

View transitions must remain client-side.

The backend must not redirect views.

---

## 17. Implementation Phases

### Phase 0 — API contract and payload builders

Deliverables:

1. Define decision API routes.
2. Define JSON payload shapes.
3. Add payload builders in Python.
4. Sanitize NaN/Infinity.
5. Validate IDs.
6. Paginate large artifacts.
7. Update `API_SURFACE.md`.

Exit criteria:

Backend can return all decision artifacts as controlled JSON.

### Phase 1 — Read-only Decision Center

Deliverables:

1. Add Decision nav item.
2. Add Decision Overview.
3. Add artifact list views.
4. Add artifact detail views.
5. Add loading, empty, and error states.
6. Link decision rows to existing run pages where possible.

Exit criteria:

A user can browse all backend-generated decision artifacts without CLI.

### Phase 2 — Job launcher

Deliverables:

1. Add decision job manager.
2. Add job API.
3. Add job modal.
4. Add job polling.
5. Add Jobs view.
6. Add readable job errors.
7. Link finished jobs to artifacts.

Exit criteria:

A non-CLI user can launch and monitor decision jobs from the UI.

### Phase 3 — Run-linked actions

Deliverables:

1. Add actions from Results or Experiments pages.
2. Prefill forms from selected run.
3. Support:
   - Monte Carlo from run
   - sensitivity from run
   - report from run
   - spatial from run
   - optimizer from run
   - multi-objective from run

Exit criteria:

A user can start common decision jobs without manually writing base config JSON.

### Phase 4 — Guided forms

Deliverables:

1. Replace raw JSON-only forms with guided inputs for common cases.
2. Keep advanced JSON editor available.
3. Add template buttons.
4. Add inline validation.
5. Add cost config editor.
6. Add constraint editor for common constraints.

Exit criteria:

A non-CLI user can launch standard decision workflows without editing raw JSON.

### Phase 5 — Advanced visualization and workflow integration

Deliverables:

1. Monte Carlo histograms.
2. Tornado charts.
3. Pareto scatter charts.
4. Robustness probability bars.
5. Spatial heatmap overlay optional.
6. Guided pipeline from baseline to robustness.

Exit criteria:

The UI clearly guides users through the recommended v0.8.1 workflow.

---

## 18. Minimum Viable Non-CLI Version

The smallest acceptable version for non-CLI users must include:

1. Setup support for v0.7.1 demand and layout fields.
2. Decision nav item.
3. Decision Overview.
4. Read-only views for:
   - studies
   - reports
   - Monte Carlo
   - sensitivity
   - optimizations
   - multi-objective
   - robustness
5. Jobs view.
6. Job launcher for:
   - Monte Carlo
   - sensitivity
   - optimizer
   - multi-objective
   - robustness
   - report
   - spatial
7. Job status polling.
8. Readable validation errors.
9. Links from decision artifacts to underlying runs.
10. Clear warnings for exploratory and non-deployable results.

A read-only viewer alone is not sufficient for non-CLI users.

---

## 19. Test Plan

### 19.1 Backend API unit tests

Test:

    GET /api/decision/overview returns 200
    GET /api/decision/studies returns 200
    GET /api/decision/studies/<invalid_id> returns 404
    GET /api/decision/monte-carlo/<invalid_id> returns 404
    GET /api/decision/sensitivity/<invalid_id> returns 404
    GET /api/decision/optimizations/<invalid_id> returns 404
    GET /api/decision/multiobjective/<invalid_id> returns 404
    GET /api/decision/robustness/<invalid_id> returns 404
    POST /api/decision/jobs returns 400 for invalid module
    POST /api/decision/jobs returns 400 for missing config
    GET /api/decision/jobs/<invalid_id> returns 404

### 19.2 Payload builder tests

Test that payload builders:

- sanitize NaN
- sanitize Infinity
- convert numpy scalars
- paginate large tables
- downsample chart data
- do not expose full CSV files
- do not expose arbitrary filesystem paths
- return null for unavailable metrics instead of inventing values

### 19.3 Immutable run artifact tests

Test that decision modules and decision APIs:

- create new runs where expected
- never modify existing `data/runs/<run_id>/config.json`
- never modify existing `data/runs/<run_id>/timeseries.csv`
- never modify existing `data/runs/<run_id>/events.csv`
- never modify existing `data/runs/<run_id>/summary.json`

### 19.4 Monte Carlo tests

Use tiny configs:

    num_robots = 2
    max_ticks = 20
    n_runs = 2

Test:

- artifacts are written to `data/monte_carlo/<mc_id>/`
- each trial writes a normal run under `data/runs/<run_id>/`
- summary includes aggregate KPIs
- summary includes SLA stats when SLA target is set
- failed trials are reported in errors
- explicit seed list length validation works
- force_fast_mode is true by default

### 19.5 Sensitivity tests

Use tiny configs:

    reps = 2
    one factor
    two values

Test:

- artifacts are written to `data/sensitivity/<study_id>/`
- baseline is present
- factor results are present
- tornado output is sorted by absolute delta
- reused baseline flag is correct
- OAT warning is surfaced in UI copy
- invalid factor config returns 400

### 19.6 Optimizer tests

Use tiny configs:

    n_trials = 2
    reps = 1

Test:

- artifacts are written to `data/optimizations/<opt_id>/`
- feasible_count and infeasible_count are present
- best_trial is null when no feasible trial exists
- best_trial is not selected from infeasible trials
- missing cost config for `cost_per_task` objective returns error
- Optuna missing returns readable error

### 19.7 Multi-objective tests

Use tiny configs:

    n_trials = 2
    reps = 1
    two objectives

Test:

- summary.json is written
- trials.json is written
- pareto.csv is written
- feasible_count is present
- pareto_count is present
- Pareto front is extracted from feasible trials only
- zero feasible count produces readable warning
- Pareto candidates are labeled exploratory in UI

### 19.8 Robustness tests

Use tiny configs for automated tests:

    reps = 2 or 3

Use realistic configs for manual acceptance:

    reps >= 20

Test:

- results.csv and summary.json are written
- each candidate has constraint_pass_probability
- robust_pass is true only when constraint_pass_probability >= min_pass_probability
- recommended is null when no candidate meets threshold
- constraint_details are present
- from_multiobjective source works
- explicit candidate source works
- reps below 20 triggers UI warning

### 19.9 Job manager tests

Test:

- job can be queued
- job can transition to running
- job can finish
- job can fail
- job status is retrievable
- invalid job id returns 404
- duplicate job submission does not corrupt state
- concurrency limit is enforced
- cancellation returns clear response if not implemented

### 19.10 Frontend rendering tests

For each decision view test:

- loading state
- empty state
- error state
- success state
- partial success state

Specific tests:

Monte Carlo:

- renders KPI table
- renders SLA panel when SLA target exists
- hides or disables SLA panel when SLA target is missing
- renders failed runs and errors

Sensitivity:

- renders baseline
- renders tornado charts from backend data only
- renders reused baseline flags

Optimizer:

- renders best trial when feasible_count > 0
- renders no feasible solution when best_trial is null
- renders infeasible count

Multi-objective:

- renders Pareto count
- renders Pareto table
- renders warning that Pareto candidates are not deployable

Robustness:

- renders constraint_pass_probability
- renders threshold line or threshold text
- renders robust_pass badges
- renders no deployable candidate when recommended is null

Spatial:

- renders coverage
- renders pre-v0.7.2 warning when coverage is 0.0
- renders top bottleneck cells

Jobs:

- renders queued, running, finished, failed states
- polls active jobs
- links finished jobs to artifacts

### 19.11 End-to-end non-CLI workflow test

Scenario:

1. User opens Setup.
2. User selects demand_mode = uniform.
3. User starts a fast run.
4. User opens Results.
5. User clicks Start Monte Carlo.
6. User submits n_runs = 2.
7. User opens Jobs.
8. Monte Carlo job finishes.
9. User opens Monte Carlo result.
10. User clicks Start Sensitivity.
11. User submits a small factor config.
12. Sensitivity job finishes.
13. User opens Sensitivity result.
14. User starts optimizer with n_trials = 2.
15. Optimizer job finishes.
16. User starts robustness with small reps for test speed.
17. Robustness job finishes.
18. UI displays constraint_pass_probability and robust_pass.

For automated tests, tiny reps are acceptable.

For production decisions, robustness reps must be at least 20.

### 19.12 Security tests

Test:

- invalid run id returns 404
- path traversal input is rejected
- arbitrary filesystem paths are not accepted
- uploaded files with invalid type are rejected
- oversized uploads are rejected
- job submission rate limiting works if enabled
- unauthenticated job submission is blocked if authentication is enabled

---

## 20. Acceptance Criteria by Feature

### 20.1 Setup

Acceptance:

- User can select demand_mode.
- UI shows only relevant demand fields.
- User can select layout_preset.
- UI shows only relevant layout fields.
- `readExperimentConfig()` includes v0.7.1 fields.
- Invalid demand config produces readable validation error.
- Invalid layout config produces readable validation error.

### 20.2 Cost KPIs

Acceptance:

- Cost KPIs are computed only by backend.
- Cost KPI panel displays total cost and cost per task.
- Cost per task is unavailable, not zero, when completed_tasks is zero.
- SLA compliance is unavailable when no SLA-evaluated tasks exist.
- Missing cost config produces readable error.

### 20.3 Studies

Acceptance:

- Study list displays existing studies.
- Study detail displays result rows.
- Each row links to run_id.
- Study report can be viewed.
- Missing study returns 404.

### 20.4 Spatial

Acceptance:

- Spatial view displays coverage.
- Pre-v0.7.2 runs show coverage 0.0 and warning.
- Top cells can be sorted by blocked_ticks or blocked_events.
- Spatial coordinates are treated as approximate.

### 20.5 Monte Carlo

Acceptance:

- User can start Monte Carlo from an existing run.
- Job status is visible.
- Finished job links to Monte Carlo artifact.
- Aggregate KPI table renders.
- Confidence intervals are displayed from backend payload only.
- SLA probabilities are displayed and explained.
- Failed trials are visible.

### 20.6 Sensitivity

Acceptance:

- User can start sensitivity from an existing run.
- Baseline is displayed.
- Factor results are displayed.
- Tornado charts are displayed from backend data only.
- OAT limitation warning is visible.

### 20.7 Optimization

Acceptance:

- User can start optimizer from an existing run.
- Feasible and infeasible counts are displayed.
- Best trial is displayed only when feasible.
- No feasible solution state is displayed when best_trial is null.
- Exploratory warning is visible.

### 20.8 Multi-Objective

Acceptance:

- User can start multi-objective optimization from an existing run.
- Objectives and constraints are displayed.
- Pareto count is displayed.
- Pareto candidates are displayed.
- Warning that Pareto candidates are not deployable is visible.
- User can send candidates to robustness.

### 20.9 Robustness

Acceptance:

- User can start robustness verification from explicit candidates or multi-objective summary.
- constraint_pass_probability is displayed.
- min_pass_probability threshold is displayed.
- robust_pass badges are displayed.
- recommended candidate is displayed only when backend provides one.
- No deployable candidate state is displayed when recommended is null.
- Low reps warning is displayed when reps < 20.

### 20.10 Jobs

Acceptance:

- User can submit decision jobs.
- User can see queued, running, finished, and failed states.
- User can see error messages.
- Finished jobs link to artifacts.
- Active jobs poll automatically.
- Long-running jobs do not block the UI.

---

## 21. Definition of Done

A decision feature is frontend-complete when:

1. Backend API returns sanitized JSON payloads.
2. Frontend renders loading, empty, error, and success states.
3. Frontend does not compute decision math.
4. Existing run artifacts are not modified.
5. Large artifacts are paginated or downsampled.
6. Non-CLI users can launch the job from the UI.
7. Non-CLI users can monitor job status.
8. Non-CLI users can open the resulting artifact.
9. Validation errors are readable.
10. Exploratory results are clearly labeled.
11. Deployable recommendations are shown only after robustness verification.
12. API_SURFACE.md is updated.
13. Tests pass.

---

## 22. Documentation Maintenance

When implementing this plan:

1. Update `API_SURFACE.md` whenever Flask routes change.
2. Update `API_SURFACE.md` whenever decision payload schemas change.
3. Update `API_SURFACE.md` whenever frontend views or DOM IDs change.
4. Update this plan if implementation reality diverges.
5. Keep code as the source of truth.