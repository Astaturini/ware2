from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from analysis.metrics import task_lifecycle_from_events

from .cost import CostConfig


@dataclass(frozen=True)
class CostKPIs:
    total_operating_cost: float
    cost_per_task: float | None
    sla_compliance_rate: float | None

    completed_tasks: int
    sla_evaluated_tasks: int
    late_tasks: int

    simulation_seconds: float
    currency: str
    cost_breakdown: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_cost_kpis(run_data: Any, cost_config: CostConfig) -> CostKPIs:
    """
    Compute business KPIs from immutable run artifacts only.

    run_data is expected to be the RunData object returned by
    analysis.loader.load_run(), or any object exposing:
      - config: dict-like
      - summary: dict-like
      - events: pandas DataFrame
    """

    if not isinstance(cost_config, CostConfig):
        raise TypeError("cost_config must be a CostConfig")

    raw_summary = getattr(run_data, "summary", None)
    raw_config = getattr(run_data, "config", None)

    summary: Mapping[str, Any] = raw_summary if isinstance(raw_summary, Mapping) else {}
    config: Mapping[str, Any] = raw_config if isinstance(raw_config, Mapping) else {}

    tick_interval = _tick_interval_seconds(config, summary)

    simulation_ticks = _to_int(summary.get("simulation_ticks"), 0)
    simulation_seconds = _to_float(
        summary.get("simulation_seconds"),
        default=simulation_ticks * tick_interval,
    )
    simulation_seconds = max(0.0, simulation_seconds)
    simulation_hours = simulation_seconds / 3600.0

    robot_count = max(
        0,
        _to_int(
            summary.get("robot_count"),
            _to_int(config.get("num_robots"), 0),
        ),
    )

    charger_capacity = max(0, _to_int(config.get("charger_capacity"), 0))

    failure_downtime_ticks = max(0, _to_int(summary.get("failure_downtime_ticks"), 0))
    failure_downtime_seconds = failure_downtime_ticks * tick_interval

    robot_operating_cost = (
        robot_count
        * simulation_hours
        * cost_config.robot_opex_per_hour
    )

    charger_infrastructure_cost = (
        charger_capacity
        * simulation_hours
        * cost_config.charger_infra_cost_per_hour
    )

    downtime_penalty_cost = (
        failure_downtime_seconds
        / 3600.0
        * cost_config.downtime_cost_per_hour
    )

    cycle_times = _completed_cycle_times(run_data)
    sla_evaluated_tasks = int(len(cycle_times))

    late_tasks = 0
    sla_compliance_rate: float | None = None
    sla_penalty_cost = 0.0

    if cost_config.sla_target_ticks is not None and sla_evaluated_tasks > 0:
        target = float(cost_config.sla_target_ticks)
        late_mask = cycle_times > target
        late_ticks = (cycle_times - target).clip(lower=0.0)

        late_tasks = int(late_mask.sum())
        sla_compliance_rate = float(
            (sla_evaluated_tasks - late_tasks) / sla_evaluated_tasks
        )
        sla_penalty_cost = float(
            late_ticks.sum() * cost_config.sla_penalty_per_late_tick
        )

    completed_tasks = max(
        0,
        _to_int(summary.get("tasks_completed"), sla_evaluated_tasks),
    )

    total_operating_cost = float(
        robot_operating_cost
        + charger_infrastructure_cost
        + downtime_penalty_cost
        + sla_penalty_cost
    )

    cost_per_task: float | None
    if completed_tasks > 0:
        cost_per_task = float(total_operating_cost / completed_tasks)
    else:
        cost_per_task = None

    cost_breakdown = {
        "robot_operating_cost": float(robot_operating_cost),
        "charger_infrastructure_cost": float(charger_infrastructure_cost),
        "downtime_penalty_cost": float(downtime_penalty_cost),
        "sla_penalty_cost": float(sla_penalty_cost),
    }

    return CostKPIs(
        total_operating_cost=total_operating_cost,
        cost_per_task=cost_per_task,
        sla_compliance_rate=sla_compliance_rate,
        completed_tasks=completed_tasks,
        sla_evaluated_tasks=sla_evaluated_tasks,
        late_tasks=late_tasks,
        simulation_seconds=simulation_seconds,
        currency=cost_config.currency,
        cost_breakdown=cost_breakdown,
    )


def compute_cost_kpis_for_run_id(
    run_id: str,
    cost_config: CostConfig,
    base_dir: str | None = None,
) -> CostKPIs:
    """
    Convenience wrapper that loads a saved run via analysis.loader and
    computes cost KPIs from immutable artifacts.
    """

    from analysis.loader import DEFAULT_RUNS_DIR, load_run

    resolved_base_dir = base_dir if base_dir is not None else DEFAULT_RUNS_DIR
    run_data = load_run(run_id, resolved_base_dir)
    return compute_cost_kpis(run_data, cost_config)


def _tick_interval_seconds(config: Mapping[str, Any], summary: Mapping[str, Any]) -> float:
    tick_interval = _to_float(config.get("tick_interval"), default=math.nan)

    if math.isfinite(tick_interval) and tick_interval > 0:
        return tick_interval

    simulation_ticks = _to_int(summary.get("simulation_ticks"), 0)
    simulation_seconds = _to_float(summary.get("simulation_seconds"), default=math.nan)

    if (
        simulation_ticks > 0
        and math.isfinite(simulation_seconds)
        and simulation_seconds >= 0
    ):
        inferred = simulation_seconds / simulation_ticks
        if math.isfinite(inferred) and inferred > 0:
            return inferred

    # Fallback matches the project's default tick interval.
    return 0.3


def _completed_cycle_times(run_data: Any) -> pd.Series:
    events = getattr(run_data, "events", None)

    if events is None:
        return pd.Series(dtype=float)

    if hasattr(events, "empty") and events.empty:
        return pd.Series(dtype=float)

    if hasattr(events, "__len__") and len(events) == 0:
        return pd.Series(dtype=float)

    lifecycle = task_lifecycle_from_events(events)

    if lifecycle is None:
        return pd.Series(dtype=float)

    if isinstance(lifecycle, pd.Series):
        cycle = pd.to_numeric(lifecycle, errors="coerce").dropna()
        return cycle[cycle >= 0]

    if not isinstance(lifecycle, pd.DataFrame) or lifecycle.empty:
        return pd.Series(dtype=float)

    if "cycle_time" in lifecycle.columns:
        cycle = pd.to_numeric(lifecycle["cycle_time"], errors="coerce")
    elif {"created_tick", "completed_tick"}.issubset(lifecycle.columns):
        created = pd.to_numeric(lifecycle["created_tick"], errors="coerce")
        completed = pd.to_numeric(lifecycle["completed_tick"], errors="coerce")
        cycle = completed - created
    else:
        return pd.Series(dtype=float)

    if "completed_tick" in lifecycle.columns:
        completed = pd.to_numeric(lifecycle["completed_tick"], errors="coerce")
        cycle = cycle[completed.notna()]

    cycle = pd.to_numeric(cycle, errors="coerce").dropna()
    return cycle[cycle >= 0]


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default

        if isinstance(value, float) and not math.isfinite(value):
            return default

        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default

        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError, OverflowError):
        return default