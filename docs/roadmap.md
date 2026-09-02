# Project Roadmap: warehouse_simulator

## Vision
Transform the `warehouse_simulator` from a technical animation/simulation engine into a **Manufacturing Systems Decision-Support Platform**. The goal is to evaluate AMR fleet sizing, scheduling policies, traffic management, and charging capacity under realistic operational constraints, outputting actionable engineering insights rather than just raw simulation metrics.

## Current State: v0.6.0 (Algorithm Plugin Layer)
- **Core**: Discrete-event simulation with battery, charging, and failure modeling (v0.4).
- **Experimentation**: Reproducible runs, immutable storage (`data/runs/`), headless/fast modes (v0.5).
- **Algorithms**: Pluggable Path Planners, Schedulers, and Conflict Managers (v0.6).
- **Gap**: Lacks business KPIs, batch scenario execution, spatial diagnostics, and optimization frameworks.

---

## Phase 1: Decision Layer Foundation (v0.7.0)
*Goal: Turn isolated simulation runs into comparable experiments with business KPIs.*

- [ ] **1.1 Cost KPIs (`decision/cost.py`, `decision/kpis.py`)**
  - Implement `CostConfig` (robot CapEx/OpEx, charger infra, downtime penalties, SLA penalties).
  - Calculate `cost_per_task`, `total_operating_cost`, `sla_compliance_rate`.
  - Must read from `summary.json` and `events.csv` only (no simulation core modifications).
- [ ] **1.2 Study / DoE Runner (`decision/study.py`)**
  - Implement `StudyConfig` to define factor matrices (e.g., robot counts, schedulers).
  - Batch execute experiments via CLI.
  - Output `data/studies/<study_id>/results.csv`.
- [ ] **1.3 Exportable Reports (`decision/report.py`)**
  - Generate Markdown/HTML engineering reports from study results.
  - Include recommendations, KPI tables, and tradeoff summaries.

## Phase 2: Realistic Scenarios (v0.7.1)
*Goal: Replace synthetic random tasks and static layouts with operational profiles.*

- [ ] **2.1 Dynamic Demand (`decision/demand.py`)**
  - Support `uniform`, `rate_schedule` (time-based waves), and `csv_orders` (deterministic waves).
  - Integrate with `TaskGenerator` without breaking existing seeded random generation.
- [ ] **2.2 Configurable Layout Presets (`decision/layout.py`)**
  - JSON-based layout and location definitions.
  - Strict validation (bounds, passable access cells, charging/maintenance existence).
  - Provide 3-4 preset layouts (e.g., default, high-density, one-way aisles).

## Phase 3: Spatial Diagnostics (v0.7.2)
*Goal: Identify physical layout bottlenecks, not just system-wide averages.*

- [ ] **3.1 Spatial Bottleneck Analysis (`decision/spatial.py`)**
  - Extend `MetricsRecorder` to capture `(x, y)` coordinates in `robot_blocked` events.
  - Aggregate blocked events into a 2D heatmap and identify top bottleneck cells/aisles.
  - Integrate spatial summaries into the v0.7.0 Report Generator.

## Phase 4: Uncertainty & Risk Analysis (v0.8.0)
*Goal: Measure system stability and parameter sensitivity under variation.*

- [ ] **4.1 Monte Carlo Runner (`decision/monte_carlo.py`)**
  - Execute N identical scenarios with varying seeds.
  - Calculate confidence intervals, p5/p95 KPIs, and probability of SLA violation.
- [ ] **4.2 Sensitivity Analysis (`decision/sensitivity.py`)**
  - One-at-a-time parameter variation around a baseline configuration.
  - Output tornado charts/data showing parameter impact on `cost_per_task` and `p95_cycle_time`.

## Phase 5: Optimization Layer (v0.8.1)
*Goal: Automate the search for optimal fleet and traffic configurations.*

- [ ] **5.1 Business Optimization (`decision/optimizer.py`)**
  - Wrap/extend Optuna to minimize `cost_per_task` or maximize `throughput`.
  - Search space: `num_robots`, `charger_capacity`, `scheduler`, `conflict_manager`.
- [ ] **5.2 Constrained Optimization**
  - Implement penalty functions for hard operational limits (e.g., `p95_cycle_time <= SLA`, `blocked_ratio <= max_allowed`).
  - Ensure optimizer explicitly reports infeasible search spaces rather than returning bad configurations.