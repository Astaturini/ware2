from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from decision.cost import CostConfig
from decision.kpis import compute_cost_kpis_from_primitives

from .config import ExperimentConfig
from .factory import create_simulation_from_config
from .runner import (
    build_run_summary,
    evaluate_stop_condition,
    snapshot_simulation,
)


@dataclass(frozen=True)
class HeadlessTrialResult:
    ok: bool
    metrics: dict[str, Any]
    summary: dict[str, Any]
    task_lifecycles: tuple[dict[str, Any], ...]
    error: str | None = None


class TaskLifecycleCollector:
    def __init__(self) -> None:
        self._tasks: dict[str, dict[str, Any]] = {}

    def observe(self, snapshot: dict[str, Any]) -> None:
        tick = int(snapshot.get("tick", 0))
        for task in snapshot.get("tasks", []):
            task_id = str(task["id"])
            record = self._tasks.setdefault(
                task_id,
                {
                    "task_id": task_id,
                    "created_tick": task.get("created_at", tick),
                    "first_assigned_tick": None,
                    "completed_tick": None,
                    "failed_tick": None,
                },
            )

            status = task.get("status")
            if status == "Assigned" and record["first_assigned_tick"] is None:
                record["first_assigned_tick"] = tick
            if status == "Completed" and record["completed_tick"] is None:
                record["completed_tick"] = task.get("completed_at", tick)
            if status == "Failed" and record["failed_tick"] is None:
                record["failed_tick"] = tick

    def rows(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._tasks.values())

    def dataframe(self) -> pd.DataFrame:
        rows = list(self.rows())
        if not rows:
            return pd.DataFrame(
                columns=[
                    "task_id",
                    "created_tick",
                    "first_assigned_tick",
                    "completed_tick",
                    "failed_tick",
                    "waiting_time",
                    "cycle_time",
                ]
            )

        frame = pd.DataFrame(rows)
        frame["waiting_time"] = frame["first_assigned_tick"] - frame["created_tick"]
        frame["cycle_time"] = frame["completed_tick"] - frame["created_tick"]
        return frame


def _finite_values(rows: tuple[dict[str, Any], ...], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = row.get(key)
        if value is None:
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue
    return values


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    return float(pd.Series(values).quantile(percentile / 100.0))


def build_headless_metrics(
    summary: dict[str, Any],
    collector: TaskLifecycleCollector,
    *,
    config: ExperimentConfig,
    sla_target_ticks: int | None,
    cost_config: CostConfig | None,
) -> dict[str, Any]:
    rows = collector.rows()
    cycle_times = _finite_values(rows, "cycle_time")
    waiting_times = _finite_values(rows, "waiting_time")

    metrics: dict[str, Any] = {
        "seed": config.seed,
        "stop_reason": summary.get("stop_reason"),
        "tasks_created": summary.get("tasks_created"),
        "tasks_completed": summary.get("tasks_completed"),
        "tasks_failed": summary.get("tasks_failed"),
        "simulation_ticks": summary.get("simulation_ticks"),
        "average_cycle_time": summary.get("average_cycle_time"),
        "average_wait_time": summary.get("average_wait_time"),
        "average_throughput": summary.get("average_throughput"),
        "average_robot_utilization": summary.get("average_robot_utilization"),
        "total_blocked_ticks": summary.get("total_blocked_ticks"),
        "total_replans": summary.get("total_replans"),
        "charging_events": summary.get("charging_events"),
        "total_charging_ticks": summary.get("total_charging_ticks"),
        "charger_wait_ticks": summary.get("charger_wait_ticks"),
        "battery_task_interruptions": summary.get("battery_task_interruptions"),
        "failure_task_interruptions": summary.get("failure_task_interruptions"),
        "task_reassignments": summary.get("task_reassignments"),
        "failed_robot_events": summary.get("failed_robot_events"),
        "failure_downtime_ticks": summary.get("failure_downtime_ticks"),
        "p95_cycle_time": _percentile(cycle_times, 95.0),
        "p95_waiting_time": _percentile(waiting_times, 95.0),
    }

    evaluated = len(cycle_times)
    late = sum(1 for value in cycle_times if sla_target_ticks is not None and value > sla_target_ticks)
    metrics["sla_target_ticks"] = sla_target_ticks
    metrics["sla_evaluated_tasks"] = evaluated if sla_target_ticks is not None else None
    metrics["late_tasks"] = late if sla_target_ticks is not None else None
    metrics["sla_compliance_rate"] = (
        1.0 - late / evaluated
        if sla_target_ticks is not None and evaluated
        else None
    )

    if cost_config is not None:
        kpis = compute_cost_kpis_from_primitives(
            summary=summary,
            config=config.to_dict(),
            task_lifecycles=collector.dataframe(),
            cost_config=cost_config,
        )
        metrics["total_operating_cost"] = kpis.total_operating_cost
        metrics["cost_per_task"] = kpis.cost_per_task
        metrics["sla_compliance_rate"] = kpis.sla_compliance_rate
        metrics["sla_evaluated_tasks"] = kpis.sla_evaluated_tasks
        metrics["late_tasks"] = kpis.late_tasks

    return metrics


def run_headless_trial(
    config_dict: dict[str, Any],
    *,
    sla_target_ticks: int | None = None,
    cost_config: CostConfig | None = None,
) -> HeadlessTrialResult:
    try:
        config = ExperimentConfig.from_dict(config_dict)
        sim = create_simulation_from_config(config)
        collector = TaskLifecycleCollector()
        stop_reason: str | None = None
        sim.resume()

        try:
            while True:
                with sim._lock:
                    sim._tick()
                    snapshot = snapshot_simulation(sim)
                    collector.observe(snapshot)

                stop_reason = evaluate_stop_condition(config, snapshot)
                if stop_reason is not None:
                    break
        finally:
            sim.stop()

        summary = build_run_summary(sim, config, stop_reason)
        metrics = build_headless_metrics(
            summary,
            collector,
            config=config,
            sla_target_ticks=sla_target_ticks,
            cost_config=cost_config,
        )
        return HeadlessTrialResult(
            ok=True,
            metrics=metrics,
            summary=summary,
            task_lifecycles=collector.rows(),
        )
    except Exception as exc:
        return HeadlessTrialResult(
            ok=False,
            metrics={},
            summary={},
            task_lifecycles=(),
            error=str(exc),
        )
