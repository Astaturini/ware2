from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import time
import uuid
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Any, cast

from analysis.loader import DEFAULT_RUNS_DIR, load_run
from analysis.metrics import task_lifecycle_from_events
from experiment.config import ExperimentConfig
from experiment.factory import create_simulation_from_config
from experiment.runner import ExperimentRunner

from decision.cost import CostConfig
from decision.execution import validate_execution_options
from decision.kpis import compute_cost_kpis_for_run_id
from decision.parallel import run_trial_specs


_KPI_FIELDS = (
    "tasks_created",
    "tasks_completed",
    "tasks_failed",
    "simulation_ticks",
    "average_cycle_time",
    "average_wait_time",
    "average_throughput",
    "average_robot_utilization",
    "total_blocked_ticks",
    "total_replans",
    "total_operating_cost",
    "cost_per_task",
    "sla_compliance_rate",
)

_ALLOWED_EXPERIMENT_FIELDS = {f.name for f in fields(ExperimentConfig)}
_ALLOWED_COST_FIELDS = {f.name for f in fields(CostConfig)}


@dataclass(frozen=True)
class MonteCarloConfig:
    base_config: dict[str, Any]
    n_runs: int
    base_seed: int | None = None
    seeds: list[int] = field(default_factory=list)
    sla_target_ticks: int | None = None
    cost_config: CostConfig | None = None
    force_fast_mode: bool = True
    output_dir: str = "data/monte_carlo"
    runs_base_dir: str = DEFAULT_RUNS_DIR
    max_workers: int = 1
    trial_artifact_mode: str = "full"

    def __post_init__(self) -> None:
        if self.n_runs < 1:
            raise ValueError("n_runs must be >= 1")
        if not self.base_config:
            raise ValueError("base_config is required")
        if self.seeds and len(self.seeds) < self.n_runs:
            raise ValueError("seeds must contain at least n_runs values")
        validate_execution_options(self.max_workers, self.trial_artifact_mode)


@dataclass(frozen=True)
class MonteCarloResult:
    mc_id: str
    output_dir: Path
    results_csv: Path
    summary_json: Path
    n_runs_requested: int
    successful_runs: int
    failed_runs: int
    aggregate: dict[str, Any]


def generate_seeds(
    n_runs: int,
    base_seed: int | None = None,
    explicit_seeds: list[int] | None = None,
) -> list[int]:
    if explicit_seeds:
        seeds = [int(s) for s in explicit_seeds]
        if len(seeds) < n_runs:
            raise ValueError("explicit_seeds must contain at least n_runs values")
        return seeds[:n_runs]

    rng = random.Random(base_seed)
    seeds: list[int] = []
    seen: set[int] = set()

    while len(seeds) < n_runs:
        seed = rng.randrange(0, 2**31)
        if seed not in seen:
            seen.add(seed)
            seeds.append(seed)

    return seeds


def build_trial_config(
    base_config: dict[str, Any],
    seed: int,
    index: int,
    force_fast_mode: bool = True,
) -> dict[str, Any]:
    clean = {k: v for k, v in base_config.items() if k in _ALLOWED_EXPERIMENT_FIELDS}
    clean["seed"] = int(seed)

    if force_fast_mode:
        clean["fast_mode"] = True

    base_name = str(clean.get("display_name") or "monte_carlo")
    clean["display_name"] = f"{base_name} mc[{index}] seed={seed}"
    return clean


def _as_finite_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _csv_safe(value: Any) -> Any:
    if value is None:
        return ""

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return value if math.isfinite(value) else ""

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)

    return numeric if math.isfinite(numeric) else ""


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None

    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]

    pos = (len(ordered) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)

    if lo == hi:
        return ordered[int(pos)]

    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def _summarize_values(values: list[Any]) -> dict[str, float | int | None] | None:
    nums = [v for value in values if (v := _as_finite_float(value)) is not None]

    if not nums:
        return None

    mean = statistics.fmean(nums)
    stdev = statistics.stdev(nums) if len(nums) > 1 else 0.0
    ci_half = 1.959963984540054 * stdev / math.sqrt(len(nums)) if len(nums) > 1 else 0.0

    return {
        "count": len(nums),
        "mean": mean,
        "stdev": stdev,
        "min": min(nums),
        "p05": _percentile(nums, 0.05),
        "median": statistics.median(nums),
        "p95": _percentile(nums, 0.95),
        "max": max(nums),
        "mean_ci95_low": mean - ci_half,
        "mean_ci95_high": mean + ci_half,
    }


def _lifecycle_records(events: Any) -> list[dict[str, Any]]:
    lifecycle = task_lifecycle_from_events(events)

    if hasattr(lifecycle, "to_dict"):
        records = lifecycle.to_dict(orient="records")
        return [
            {str(key): value for key, value in record.items()}
            for record in records
        ]

    if isinstance(lifecycle, dict):
        return [
            {str(key): value for key, value in record.items()}
            for record in dict.values(cast(dict[Any, Any], lifecycle))
        ]

    return cast(list[dict[str, Any]], list(lifecycle))


def _execute_trial(config: ExperimentConfig, runs_base_dir: str) -> str:
    runner = ExperimentRunner(base_dir=runs_base_dir)
    run_id = runner.start(config, create_simulation_from_config)

    # Wait briefly for the runner thread to become active. Very fast headless
    # runs may finish almost immediately.
    start_wait = time.time()
    while not runner.is_active and not runner.finished:
        if time.time() - start_wait > 2.0:
            state = runner.get_state()
            raise RuntimeError(f"runner never became active: {state}")
        time.sleep(0.01)

    while True:
        if runner.finished:
            break

        if not runner.is_active:
            time.sleep(0.01)
            if runner.finished:
                break
            state = runner.get_state()
            raise RuntimeError(f"runner stopped without finishing: {state}")

        time.sleep(0.05)

    state = runner.get_state()
    stop_reason = str(state.get("stopReason") or "")
    if stop_reason.startswith("error"):
        raise RuntimeError(f"run {run_id} failed: {stop_reason}")

    return run_id


def extract_run_metrics(
    run_id: str,
    runs_base_dir: str,
    cost_config: CostConfig | None = None,
    sla_target_ticks: int | None = None,
) -> dict[str, Any]:
    run = load_run(run_id, runs_base_dir)
    summary = run.summary or {}
    config = run.config or {}

    row: dict[str, Any] = {
        "run_id": run_id,
        "seed": config.get("seed"),
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
    }

    if sla_target_ticks is not None:
        records = _lifecycle_records(run.events)
        cycles: list[float] = []

        for record in records:
            completed_tick = record.get("completed_tick")
            cycle_time = record.get("cycle_time")

            if completed_tick is None or cycle_time is None:
                continue

            numeric_cycle = _as_finite_float(cycle_time)
            if numeric_cycle is not None:
                cycles.append(numeric_cycle)

        late = [cycle for cycle in cycles if cycle > float(sla_target_ticks)]

        row["sla_target_ticks"] = sla_target_ticks
        row["sla_evaluated_tasks"] = len(cycles)
        row["late_tasks"] = len(late)
        row["sla_compliance_rate"] = (1.0 - len(late) / len(cycles)) if cycles else None

    if cost_config is not None:
        effective_cost = cost_config

        if (
            sla_target_ticks is not None
            and effective_cost.sla_target_ticks != sla_target_ticks
        ):
            effective_cost = replace(effective_cost, sla_target_ticks=sla_target_ticks)

        kpis = compute_cost_kpis_for_run_id(
            run_id,
            effective_cost,
            base_dir=runs_base_dir,
        )

        row["total_operating_cost"] = kpis.total_operating_cost
        row["cost_per_task"] = kpis.cost_per_task

        if kpis.sla_compliance_rate is not None:
            row["sla_compliance_rate"] = kpis.sla_compliance_rate

        if row.get("sla_evaluated_tasks") is None:
            row["sla_evaluated_tasks"] = kpis.sla_evaluated_tasks
            row["late_tasks"] = kpis.late_tasks

    return row


def _aggregate(rows: list[dict[str, Any]], sla_target_ticks: int | None) -> dict[str, Any]:
    if not rows:
        return {
            "successful_runs": 0,
            "stop_reason_counts": {},
            "kpis": {},
        }

    kpis: dict[str, Any] = {}
    for key in _KPI_FIELDS:
        kpis[key] = _summarize_values([row.get(key) for row in rows])

    stop_reason_counts: dict[str, int] = {}
    for row in rows:
        reason = str(row.get("stop_reason") or "unknown")
        stop_reason_counts[reason] = stop_reason_counts.get(reason, 0) + 1

    aggregate: dict[str, Any] = {
        "successful_runs": len(rows),
        "stop_reason_counts": stop_reason_counts,
        "kpis": kpis,
    }

    if sla_target_ticks is not None:
        evaluated_tasks = sum(int(row.get("sla_evaluated_tasks") or 0) for row in rows)
        late_tasks = sum(int(row.get("late_tasks") or 0) for row in rows)

        runs_evaluated = sum(
            1 for row in rows if int(row.get("sla_evaluated_tasks") or 0) > 0
        )
        runs_with_any_late = sum(
            1 for row in rows if int(row.get("late_tasks") or 0) > 0
        )

        aggregate["sla"] = {
            "target_ticks": sla_target_ticks,
            "evaluated_tasks": evaluated_tasks,
            "late_tasks": late_tasks,
            "task_late_probability": (late_tasks / evaluated_tasks)
            if evaluated_tasks
            else None,
            "runs_evaluated": runs_evaluated,
            "runs_with_any_late": runs_with_any_late,
            "run_any_violation_probability": (runs_with_any_late / runs_evaluated)
            if runs_evaluated
            else None,
        }

    return aggregate


def _write_results_csv(
    results_csv: Path,
    rows: list[dict[str, Any]],
    errors: list[dict[str, Any]],
) -> None:
    if rows:
        fieldnames: list[str] = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)

        required = ["mc_index", "seed", "run_id", "stop_reason"]
        fieldnames = [key for key in required if key in fieldnames] + [
            key for key in fieldnames if key not in required
        ]

        with results_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, restval="")
            writer.writeheader()
            for row in rows:
                writer.writerow({key: _csv_safe(row.get(key)) for key in fieldnames})
        return

    with results_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["mc_index", "seed", "run_id", "error"])


def _run_monte_carlo_metrics_only(
    mc_config: MonteCarloConfig,
    seeds: list[int],
    effective_sla: int | None,
    cost_config: CostConfig | None,
    progress_callback: Any | None = None,
) -> MonteCarloResult:
    mc_id = time.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
    out_dir = Path(mc_config.output_dir) / mc_id
    out_dir.mkdir(parents=True, exist_ok=True)

    specs: list[dict[str, Any]] = []
    for index, seed in enumerate(seeds):
        specs.append(
            {
                "index": index,
                "seed": seed,
                "config": build_trial_config(
                    mc_config.base_config,
                    seed=seed,
                    index=index,
                    force_fast_mode=mc_config.force_fast_mode,
                ),
                "sla_target_ticks": effective_sla,
                "cost_config": cost_config,
            }
        )

    def report_trial_progress(completed: int, total: int) -> None:
        if progress_callback is not None:
            progress_callback(
                10 + int(completed / total * 80),
                f"Completed trial {completed} of {total}.",
            )

    outcomes = run_trial_specs(
        specs,
        max_workers=mc_config.max_workers,
        progress_callback=report_trial_progress,
    )
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for spec, outcome in zip(specs, outcomes):
        if outcome.ok:
            row = dict(outcome.metrics)
            row.update(
                {
                    "mc_index": spec["index"],
                    "seed": spec["seed"],
                    "run_id": None,
                    "status": "ok",
                }
            )
            rows.append(row)
        else:
            errors.append(
                {
                    "mc_index": spec["index"],
                    "seed": spec["seed"],
                    "stage": "run",
                    "error": outcome.error,
                }
            )

    rows.sort(key=lambda row: int(row["mc_index"]))
    results_csv = out_dir / "results.csv"
    _write_results_csv(results_csv, rows, errors)
    aggregate = _aggregate(rows, effective_sla)
    summary = {
        "mc_id": mc_id,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_runs_requested": mc_config.n_runs,
        "successful_runs": len(rows),
        "failed_runs": len(errors),
        "seeds": seeds,
        "effective_sla_target_ticks": effective_sla,
        "force_fast_mode": mc_config.force_fast_mode,
        "trial_artifact_mode": mc_config.trial_artifact_mode,
        "max_workers": mc_config.max_workers,
        "run_artifacts_written": False,
        "base_config": mc_config.base_config,
        "aggregate": aggregate,
        "errors": errors,
    }
    summary_json = out_dir / "summary.json"
    summary_json.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    return MonteCarloResult(
        mc_id=mc_id,
        output_dir=out_dir,
        results_csv=results_csv,
        summary_json=summary_json,
        n_runs_requested=mc_config.n_runs,
        successful_runs=len(rows),
        failed_runs=len(errors),
        aggregate=aggregate,
    )


def run_monte_carlo(
    mc_config: MonteCarloConfig,
    progress_callback: Any | None = None,
) -> MonteCarloResult:
    validate_execution_options(mc_config.max_workers, mc_config.trial_artifact_mode)
    seeds = generate_seeds(
        mc_config.n_runs,
        base_seed=mc_config.base_seed,
        explicit_seeds=mc_config.seeds,
    )

    effective_sla = mc_config.sla_target_ticks
    cost_config = mc_config.cost_config
    if cost_config is not None and effective_sla is None:
        effective_sla = cost_config.sla_target_ticks
    if (
        cost_config is not None
        and effective_sla is not None
        and cost_config.sla_target_ticks != effective_sla
    ):
        cost_config = replace(cost_config, sla_target_ticks=effective_sla)

    if mc_config.trial_artifact_mode == "metrics_only":
        return _run_monte_carlo_metrics_only(
            mc_config,
            seeds,
            effective_sla,
            cost_config,
            progress_callback=progress_callback,
        )

    return _run_monte_carlo_full(mc_config, seeds, progress_callback=progress_callback)


def _run_monte_carlo_full(
    mc_config: MonteCarloConfig,
    seeds: list[int],
    progress_callback: Any | None = None,
) -> MonteCarloResult:

    mc_id = time.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
    out_dir = Path(mc_config.output_dir) / mc_id
    out_dir.mkdir(parents=True, exist_ok=True)

    effective_sla = mc_config.sla_target_ticks
    cost_config = mc_config.cost_config

    if cost_config is not None and effective_sla is None:
        effective_sla = cost_config.sla_target_ticks

    if (
        cost_config is not None
        and effective_sla is not None
        and cost_config.sla_target_ticks != effective_sla
    ):
        cost_config = replace(cost_config, sla_target_ticks=effective_sla)

    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for index, seed in enumerate(seeds):
        trial_dict = build_trial_config(
            mc_config.base_config,
            seed=seed,
            index=index,
            force_fast_mode=mc_config.force_fast_mode,
        )

        try:
            trial_config = ExperimentConfig.from_dict(trial_dict)
        except Exception as exc:
            errors.append(
                {
                    "mc_index": index,
                    "seed": seed,
                    "stage": "config",
                    "error": str(exc),
                }
            )

        if progress_callback is not None:
            completed = index + 1
            progress_callback(
                10 + int(completed / len(seeds) * 80),
                f"Completed trial {completed} of {len(seeds)}.",
            )
            continue

        try:
            run_id = _execute_trial(trial_config, mc_config.runs_base_dir)
            row = extract_run_metrics(
                run_id,
                mc_config.runs_base_dir,
                cost_config=cost_config,
                sla_target_ticks=effective_sla,
            )
            row["mc_index"] = index
            rows.append(row)
        except Exception as exc:
            errors.append(
                {
                    "mc_index": index,
                    "seed": seed,
                    "stage": "run",
                    "error": str(exc),
                }
            )

    results_csv = out_dir / "results.csv"

    if rows:
        fieldnames: list[str] = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)

        required = ["mc_index", "seed", "run_id", "stop_reason"]
        fieldnames = [key for key in required if key in fieldnames] + [
            key for key in fieldnames if key not in required
        ]

        with results_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, restval="")
            writer.writeheader()
            for row in rows:
                writer.writerow({k: _csv_safe(row.get(k)) for k in fieldnames})
    else:
        with results_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["mc_index", "seed", "run_id", "error"])

    aggregate = _aggregate(rows, effective_sla)

    summary = {
        "mc_id": mc_id,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_runs_requested": mc_config.n_runs,
        "successful_runs": len(rows),
        "failed_runs": len(errors),
        "seeds": seeds,
        "effective_sla_target_ticks": effective_sla,
        "force_fast_mode": mc_config.force_fast_mode,
        "trial_artifact_mode": mc_config.trial_artifact_mode,
        "max_workers": mc_config.max_workers,
        "run_artifacts_written": True,
        "base_config": mc_config.base_config,
        "aggregate": aggregate,
        "errors": errors,
    }

    summary_json = out_dir / "summary.json"
    summary_json.write_text(
        json.dumps(summary, indent=2, default=str),
        encoding="utf-8",
    )

    return MonteCarloResult(
        mc_id=mc_id,
        output_dir=out_dir,
        results_csv=results_csv,
        summary_json=summary_json,
        n_runs_requested=mc_config.n_runs,
        successful_runs=len(rows),
        failed_runs=len(errors),
        aggregate=aggregate,
    )


def _load_cost_config(path: str | Path) -> CostConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError("cost config JSON must be an object")

    clean = {k: v for k, v in data.items() if k in _ALLOWED_COST_FIELDS}
    return CostConfig(**clean)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m decision.monte_carlo",
        description="Run Monte Carlo replications of a warehouse simulator experiment.",
    )

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--config",
        help="Path to a base ExperimentConfig JSON file.",
    )
    source.add_argument(
        "--from-run-id",
        help="Reuse config.json from an existing run in data/runs/.",
    )

    parser.add_argument("--n", type=int, default=30, help="Number of Monte Carlo runs.")
    parser.add_argument("--base-seed", type=int, default=None, help="Seed used to generate trial seeds.")
    parser.add_argument("--seeds", type=int, nargs="*", default=None, help="Explicit trial seeds.")
    parser.add_argument("--sla-target-ticks", type=int, default=None, help="SLA target in ticks.")
    parser.add_argument("--cost-config", type=str, default=None, help="Optional CostConfig JSON file.")
    parser.add_argument("--output-dir", type=str, default="data/monte_carlo")
    parser.add_argument("--runs-base-dir", type=str, default=DEFAULT_RUNS_DIR)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument(
        "--trial-artifact-mode",
        choices=("full", "metrics_only"),
        default="full",
    )

    args = parser.parse_args(argv)

    if args.config:
        base_config = json.loads(Path(args.config).read_text(encoding="utf-8"))
        if not isinstance(base_config, dict):
            parser.error("--config must contain a JSON object")

        # Convenience: allow a Monte Carlo wrapper file containing base_config.
        if "base_config" in base_config and isinstance(base_config["base_config"], dict):
            base_config = base_config["base_config"]
    else:
        run = load_run(args.from_run_id, args.runs_base_dir)
        base_config = dict(run.config)

    cost_config = _load_cost_config(args.cost_config) if args.cost_config else None

    mc_config = MonteCarloConfig(
        base_config=base_config,
        n_runs=args.n,
        base_seed=args.base_seed,
        seeds=args.seeds or [],
        sla_target_ticks=args.sla_target_ticks,
        cost_config=cost_config,
        output_dir=args.output_dir,
        runs_base_dir=args.runs_base_dir,
        max_workers=args.max_workers,
        trial_artifact_mode=args.trial_artifact_mode,
    )

    result = run_monte_carlo(mc_config)

    print(
        json.dumps(
            {
                "mc_id": result.mc_id,
                "output_dir": str(result.output_dir),
                "results_csv": str(result.results_csv),
                "summary_json": str(result.summary_json),
                "successful_runs": result.successful_runs,
                "failed_runs": result.failed_runs,
                "sla": result.aggregate.get("sla"),
                "kpis": {
                    key: value
                    for key, value in result.aggregate.get("kpis", {}).items()
                    if value is not None
                },
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()