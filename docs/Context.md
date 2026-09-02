# Project Context for AI Assistants

## Project Identity
- **Project Name**: warehouse_simulator
- **Base Version**: v0.6.0
- **Target Version**: v0.7.0 (Decision Layer Foundation)
- **Domain**: Manufacturing Systems Engineering, Intralogistics, AMR Fleet Simulation.

## Current Milestone & Immediate Task
- **Milestone**: Phase 1 - Decision Layer Foundation.
- **Current Task**: Implement Cost KPIs (`decision/cost.py` and `decision/kpis.py`).
- **Next Task After Current**: Implement Study/DoE Runner (`decision/study.py`).

## Strict Architecture Constraints (DO NOT BREAK)
1. **Immutability of v0.5/v0.6**: Do not modify the core simulation semantics, `ExperimentConfig` validation, or the `data/runs/<run_id>/` storage format unless absolutely necessary.
2. **Analysis Layer Rule**: The analysis and decision layers must read saved files (`config.json`, `summary.json`, `events.csv`, `timeseries.csv`) ONLY. They must never depend on live simulation objects.
3. **No UI First**: Build all Phase 1-3 features as CLI scripts and Python modules first. Do not write frontend JavaScript or HTML until the backend logic is proven.
4. **Backward Compatibility**: Any new fields added to configs must have defaults that preserve v0.6.0 behavior.
5. **No Sycophancy**: Do not praise the user. Do not validate bad engineering ideas. Push back if a proposed feature is bloated, unscientific, or disconnected from manufacturing systems realities. State opinions clearly and factually.

## Key Directories & Files
- `simulation/`: Core discrete-event engine (v0.4 battery/failure, v0.6 plugins).
- `experiment/`: Config, factory, runner, and recorder (v0.5).
- `analysis/`: Loader, metrics, and web API payloads (v0.5).
- `decision/`: **(NEW)** Cost, KPIs, DoE, spatial analysis, optimization.
- `data/runs/`: Immutable run artifacts.
- `data/studies/`: **(NEW)** Batch DoE and optimization results.
- `API_SURFACE.md`: The absolute source of truth for naming, state, and architecture.

## Definition of Done for Current Task (Cost KPIs)
- [ ] `CostConfig` dataclass created in `decision/cost.py`.
- [ ] `compute_cost_kpis(run_data, cost_config)` implemented in `decision/kpis.py`.
- [ ] Calculates: `total_operating_cost`, `cost_per_task`, `sla_compliance_rate`.
- [ ] Uses `analysis/loader.py` to read run data.
- [ ] Uses `analysis/metrics.py` (`task_lifecycle_from_events`) to calculate cycle times for SLA penalties.
- [ ] Handles division by zero (e.g., 0 completed tasks).
- [ ] Unit tests added in `tests/test_cost_kpis.py`.

## Instructions for the AI
- When asked to implement a feature, provide the exact file paths, the code, and the CLI command to test it.
- If the user suggests a feature that is too broad or academically toy-like, argue against it and propose a tighter, industry-standard alternative.
- Keep responses concise, highly technical, and focused on systems engineering value.