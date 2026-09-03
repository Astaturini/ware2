from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import time
import uuid
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any, cast

from analysis.loader import DEFAULT_RUNS_DIR, load_run
from analysis.metrics import task_lifecycle_from_events
from experiment.config import ExperimentConfig
from experiment.factory import create_simulation_from_config
from experiment.runner import ExperimentRunner

from decision.cost import CostConfig
from decision.kpis import compute_cost_kpis_for_run_id


_ALLOWED_EXPERIMENT_FIELDS = {f.name for f in fields(ExperimentConfig)}
_ALLOWED_COST_FIELDS = {f.name for f in fields(CostConfig)}

_AGG_FIELDS = (
    "tasks_created",
    "tasks_completed",
    "simulation_ticks",
    "average_cycle_time",
    "p95_cycle_time",
    "average_throughput",
    "total_blocked_ticks",
    "total_replans",
    "total_operating_cost",
    "cost_per_task",
    "sla_compliance_rate",
)

_TORNADO_TARGETS = (
    "cost_per_task",
    "p95_cycle_time",
)


@dataclass(frozen=True)
class FactorSpec:
    name: str
    values: list[Any]


@dataclass(frozen=True)
class SensitivityConfig:
    base_config: dict[str, Any]
    factors: list[FactorSpec]
    reps: int = 3
    base_seed: int | None = None
    sla_target_ticks: int | None = None
    cost_config: CostConfig | None = None
    force_fast_mode: bool = True
    output_dir: str = "data/sensitivity"
    runs_base_dir: str = DEFAULT_RUNS_DIR

    def __post_init__(self) -> None:
        if self.reps < 1:
            raise ValueError("reps must be >= 1")
        if not self.base_config:
            raise ValueError("base_config is required")
        if not self.factors:
            raise ValueError("at least one factor is required")

        for factor in self.factors:
            if not factor.name:
                raise ValueError("factor name is required")
            if factor.name not in _ALLOWED_EXPERIMENT_FIELDS:
                raise ValueError(f"unknown experiment field: {factor.name}")
            if factor.name in {"seed", "display_name", "fast_mode"}:
                raise ValueError(f"factor {factor.name} is not a valid sensitivity factor")
            if not factor.values:
                raise ValueError(f"factor {factor.name} must contain at least one value")


@dataclass(frozen=True)
class SensitivityResult:
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


def generate_seeds(n_runs: int, base_seed: int | None = None) -> list[int]:
    rng = random.Random(base_seed)
    seeds: list[int] = []
    seen: set[int] = set()

    while len(seeds) < n_runs:
        seed = rng.randrange(0, 2**31)
        if seed not in seen:
            seen.add(seed)
            seeds.append(seed)

    return seeds


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

    # This matches the calling convention that worked in your Monte Carlo run.
    run_id = runner.start(config, create_simulation_from_config)

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


def _build_variant_config(
    base_config: dict[str, Any],
    overrides: dict[str, Any],
    seed: int,
    display_name: str,
    force_fast_mode: bool = True,
) -> dict[str, Any]:
    clean = {k: v for k, v in base_config.items() if k in _ALLOWED_EXPERIMENT_FIELDS}

    for key, value in overrides.items():
        if key not in _ALLOWED_EXPERIMENT_FIELDS:
            raise ValueError(f"unknown experiment field: {key}")
        clean[key] = value

    clean["seed"] = int(seed)

    if force_fast_mode:
        clean["fast_mode"] = True

    clean["display_name"] = display_name
    return clean


def extract_sensitivity_metrics(
    run_id: str,
    runs_base_dir: str,
    cost_config: CostConfig | None = None,
    sla_target_ticks: int | None = None,
) -> dict[str, Any]:
    run = load_run(run_id, runs_base_dir)
    summary = run.summary or {}
    config = run.config or {}

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

    p95_cycle_time = _percentile(cycles, 0.95)

    row: dict[str, Any] = {
        "run_id": run_id,
        "seed": config.get("seed"),
        "stop_reason": summary.get("stop_reason"),
        "tasks_created": summary.get("tasks_created"),
        "tasks_completed": summary.get("tasks_completed"),
        "simulation_ticks": summary.get("simulation_ticks"),
        "average_cycle_time": summary.get("average_cycle_time"),
        "p95_cycle_time": p95_cycle_time,
        "average_throughput": summary.get("average_throughput"),
        "total_blocked_ticks": summary.get("total_blocked_ticks"),
        "total_replans": summary.get("total_replans"),
    }

    if sla_target_ticks is not None:
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

    row["feasible"] = bool(
        int(row.get("tasks_completed") or 0) > 0
        and row.get("p95_cycle_time") is not None
    )
    row["cost_feasible"] = bool(
        row.get("feasible")
        and row.get("cost_per_task") is not None
    )

    return row


def _aggregate_rows(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None

    aggregate: dict[str, Any] = {
        "runs": len(rows),
        "feasible_runs": sum(1 for row in rows if row.get("feasible")),
        "cost_feasible_runs": sum(1 for row in rows if row.get("cost_feasible")),
    }

    for key in _AGG_FIELDS:
        nums: list[float] = []

        for row in rows:
            value = _as_finite_float(row.get(key))
            if value is not None:
                nums.append(value)

        if not nums:
            aggregate[key] = None
            continue

        aggregate[key] = {
            "count": len(nums),
            "mean": statistics.fmean(nums),
            "stdev": statistics.stdev(nums) if len(nums) > 1 else 0.0,
            "min": min(nums),
            "max": max(nums),
        }

    return aggregate


def _metric_mean(aggregate: dict[str, Any] | None, key: str) -> float | None:
    if not aggregate:
        return None

    block = aggregate.get(key)
    if not block:
        return None

    return _as_finite_float(block.get("mean"))


def _percent_delta(variant: float | None, baseline: float | None) -> float | None:
    if variant is None or baseline is None:
        return None

    if baseline == 0:
        return None

    return (variant - baseline) / abs(baseline)


def _make_cost_config(data: dict[str, Any]) -> CostConfig:
    clean = {k: v for k, v in data.items() if k in _ALLOWED_COST_FIELDS}
    return CostConfig(**clean)


def _load_cost_config(path: str | Path) -> CostConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError("cost config JSON must be an object")

    return _make_cost_config(data)


def run_sensitivity(cfg: SensitivityConfig) -> SensitivityResult:
    study_id = time.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
    out_dir = Path(cfg.output_dir) / study_id
    out_dir.mkdir(parents=True, exist_ok=True)

    results_csv = out_dir / "results.csv"
    tornado_csv = out_dir / "tornado.csv"
    summary_json = out_dir / "summary.json"

    seeds = generate_seeds(cfg.reps, cfg.base_seed)

    effective_sla = cfg.sla_target_ticks
    cost_config = cfg.cost_config

    if cost_config is not None and effective_sla is None:
        effective_sla = cost_config.sla_target_ticks

    if (
        cost_config is not None
        and effective_sla is not None
        and cost_config.sla_target_ticks != effective_sla
    ):
        cost_config = replace(cost_config, sla_target_ticks=effective_sla)

    defaults = ExperimentConfig.default().to_dict()
    baseline_values = {
        **defaults,
        **{k: v for k, v in cfg.base_config.items() if k in _ALLOWED_EXPERIMENT_FIELDS},
    }

    errors: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []
    cache: dict[str, list[dict[str, Any]]] = {}

    def run_level(factor_name: str | None, value: Any) -> list[dict[str, Any]]:
        key = json.dumps({"factor": factor_name, "value": value}, sort_keys=True, default=str)
        if key in cache:
            return cache[key]

        level_rows: list[dict[str, Any]] = []
        overrides = {} if factor_name is None else {factor_name: value}

        for rep, seed in enumerate(seeds):
            if factor_name is None:
                display_name = (
                    f"{baseline_values.get('display_name') or 'sensitivity'} "
                    f"baseline rep={rep} seed={seed}"
                )
            else:
                display_name = (
                    f"{baseline_values.get('display_name') or 'sensitivity'} "
                    f"{factor_name}={value} rep={rep} seed={seed}"
                )

            trial_dict = _build_variant_config(
                cfg.base_config,
                overrides=overrides,
                seed=seed,
                display_name=display_name,
                force_fast_mode=cfg.force_fast_mode,
            )

            try:
                trial_config = ExperimentConfig.from_dict(trial_dict)
                run_id = _execute_trial(trial_config, cfg.runs_base_dir)
                row = extract_sensitivity_metrics(
                    run_id,
                    cfg.runs_base_dir,
                    cost_config=cost_config,
                    sla_target_ticks=effective_sla,
                )
                row.update(
                    {
                        "factor": factor_name or "baseline",
                        "value": "" if factor_name is None else value,
                        "rep": rep,
                        "seed": seed,
                    }
                )
                level_rows.append(row)
                all_rows.append(row)
            except Exception as exc:
                errors.append(
                    {
                        "factor": factor_name or "baseline",
                        "value": value,
                        "rep": rep,
                        "seed": seed,
                        "stage": "trial",
                        "error": str(exc),
                    }
                )

        cache[key] = level_rows
        return level_rows

    baseline_rows = run_level(None, None)
    baseline_aggregate = _aggregate_rows(baseline_rows)

    baseline_summary = {
        "runs": len(baseline_rows),
        "aggregate": baseline_aggregate,
        "cost_per_task": _metric_mean(baseline_aggregate, "cost_per_task"),
        "p95_cycle_time": _metric_mean(baseline_aggregate, "p95_cycle_time"),
    }

    if not baseline_rows:
        results_csv.write_text("factor,value,rep,seed,error\n", encoding="utf-8")
        tornado_csv.write_text(
            "target,factor,value,label,baseline,variant,delta,delta_percent,abs_delta\n",
            encoding="utf-8",
        )

        summary = {
            "study_id": study_id,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "reps": cfg.reps,
            "seeds": seeds,
            "effective_sla_target_ticks": effective_sla,
            "base_config": cfg.base_config,
            "factors": [{"name": f.name, "values": f.values} for f in cfg.factors],
            "baseline": baseline_summary,
            "factor_results": [],
            "tornado": {
                "cost_per_task": [],
                "p95_cycle_time": [],
            },
            "errors": errors,
        }

        summary_json.write_text(
            json.dumps(summary, indent=2, default=str),
            encoding="utf-8",
        )

        return SensitivityResult(
            study_id=study_id,
            output_dir=out_dir,
            results_csv=results_csv,
            summary_json=summary_json,
            tornado_csv=tornado_csv,
            successful_runs=0,
            failed_runs=len(errors),
            baseline=baseline_summary,
            factor_results=[],
            tornado={
                "cost_per_task": [],
                "p95_cycle_time": [],
            },
            errors=errors,
        )

    baseline_cost = baseline_summary["cost_per_task"]
    baseline_p95 = baseline_summary["p95_cycle_time"]

    factor_results: list[dict[str, Any]] = []
    tornado_entries: list[dict[str, Any]] = []

    for factor in cfg.factors:
        baseline_value = baseline_values.get(factor.name)
        levels: list[dict[str, Any]] = []

        for value in factor.values:
            reused_baseline = value == baseline_value
            level_rows = baseline_rows if reused_baseline else run_level(factor.name, value)
            aggregate = _aggregate_rows(level_rows)

            variant_cost = _metric_mean(aggregate, "cost_per_task")
            variant_p95 = _metric_mean(aggregate, "p95_cycle_time")

            delta_cost = (
                variant_cost - baseline_cost
                if variant_cost is not None and baseline_cost is not None
                else None
            )
            delta_p95 = (
                variant_p95 - baseline_p95
                if variant_p95 is not None and baseline_p95 is not None
                else None
            )

            percent_cost = _percent_delta(variant_cost, baseline_cost)
            percent_p95 = _percent_delta(variant_p95, baseline_p95)

            levels.append(
                {
                    "value": value,
                    "reused_baseline": reused_baseline,
                    "runs": len(level_rows),
                    "aggregate": aggregate,
                    "cost_per_task": variant_cost,
                    "p95_cycle_time": variant_p95,
                    "delta_cost_per_task": delta_cost,
                    "delta_percent_cost_per_task": percent_cost,
                    "delta_p95_cycle_time": delta_p95,
                    "delta_percent_p95_cycle_time": percent_p95,
                }
            )

            if not reused_baseline:
                if delta_cost is not None:
                    tornado_entries.append(
                        {
                            "target": "cost_per_task",
                            "factor": factor.name,
                            "value": value,
                            "label": f"{factor.name}={value}",
                            "baseline": baseline_cost,
                            "variant": variant_cost,
                            "delta": delta_cost,
                            "delta_percent": percent_cost,
                            "abs_delta": abs(delta_cost),
                        }
                    )

                if delta_p95 is not None:
                    tornado_entries.append(
                        {
                            "target": "p95_cycle_time",
                            "factor": factor.name,
                            "value": value,
                            "label": f"{factor.name}={value}",
                            "baseline": baseline_p95,
                            "variant": variant_p95,
                            "delta": delta_p95,
                            "delta_percent": percent_p95,
                            "abs_delta": abs(delta_p95),
                        }
                    )

        factor_results.append(
            {
                "factor": factor.name,
                "baseline_value": baseline_value,
                "levels": levels,
            }
        )

    tornado = {
        target: sorted(
            (entry for entry in tornado_entries if entry["target"] == target),
            key=lambda entry: entry["abs_delta"],
            reverse=True,
        )
        for target in _TORNADO_TARGETS
    }

    if all_rows:
        fieldnames: list[str] = []
        for row in all_rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)

        required = [
            "factor",
            "value",
            "rep",
            "seed",
            "run_id",
            "stop_reason",
            "feasible",
            "cost_feasible",
            "p95_cycle_time",
            "cost_per_task",
            "tasks_completed",
        ]
        fieldnames = [key for key in required if key in fieldnames] + [
            key for key in fieldnames if key not in required
        ]

        with results_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, restval="")
            writer.writeheader()
            for row in all_rows:
                writer.writerow({k: _csv_safe(row.get(k)) for k in fieldnames})
    else:
        results_csv.write_text("factor,value,rep,seed,error\n", encoding="utf-8")

    tornado_fieldnames = [
        "target",
        "factor",
        "value",
        "label",
        "baseline",
        "variant",
        "delta",
        "delta_percent",
        "abs_delta",
    ]

    with tornado_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=tornado_fieldnames, restval="")
        writer.writeheader()

        for target in _TORNADO_TARGETS:
            for entry in tornado.get(target, []):
                writer.writerow({k: _csv_safe(entry.get(k)) for k in tornado_fieldnames})

    summary = {
        "study_id": study_id,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "reps": cfg.reps,
        "seeds": seeds,
        "effective_sla_target_ticks": effective_sla,
        "base_config": cfg.base_config,
        "factors": [{"name": f.name, "values": f.values} for f in cfg.factors],
        "baseline": baseline_summary,
        "factor_results": factor_results,
        "tornado": tornado,
        "errors": errors,
    }

    summary_json.write_text(
        json.dumps(summary, indent=2, default=str),
        encoding="utf-8",
    )

    return SensitivityResult(
        study_id=study_id,
        output_dir=out_dir,
        results_csv=results_csv,
        summary_json=summary_json,
        tornado_csv=tornado_csv,
        successful_runs=len(all_rows),
        failed_runs=len(errors),
        baseline=baseline_summary,
        factor_results=factor_results,
        tornado=tornado,
        errors=errors,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m decision.sensitivity",
        description="Run one-at-a-time sensitivity analysis around a baseline experiment.",
    )
    parser.add_argument("--config", required=True, help="Path to sensitivity config JSON.")
    parser.add_argument("--reps", type=int, default=None, help="Override reps from config.")
    parser.add_argument("--base-seed", type=int, default=None, help="Override base seed.")
    parser.add_argument("--sla-target-ticks", type=int, default=None, help="Override SLA target.")
    parser.add_argument("--cost-config", type=str, default=None, help="Override cost config path.")
    parser.add_argument("--output-dir", type=str, default=None, help="Override output dir.")
    parser.add_argument("--runs-base-dir", type=str, default=None, help="Override runs base dir.")

    args = parser.parse_args(argv)

    raw = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        parser.error("--config must contain a JSON object")

    runs_base_dir = args.runs_base_dir or raw.get("runs_base_dir", DEFAULT_RUNS_DIR)

    if "from_run_id" in raw and "base_config" in raw:
        parser.error("config may contain either from_run_id or base_config, not both")

    if "from_run_id" in raw:
        run = load_run(raw["from_run_id"], runs_base_dir)
        base_config = dict(run.config)
    elif "base_config" in raw:
        base_config = raw["base_config"]
    else:
        parser.error("config must contain from_run_id or base_config")

    if not isinstance(base_config, dict):
        parser.error("base_config must be a JSON object")

    factors_raw = raw.get("factors", [])
    if not isinstance(factors_raw, list) or not factors_raw:
        parser.error("config must contain a non-empty factors list")

    factors: list[FactorSpec] = []
    for item in factors_raw:
        if not isinstance(item, dict):
            parser.error("each factor must be an object")

        if "name" not in item or "values" not in item:
            parser.error("each factor must contain name and values")

        if not isinstance(item["values"], list):
            parser.error("factor values must be a list")

        factors.append(
            FactorSpec(
                name=str(item["name"]),
                values=list(item["values"]),
            )
        )

    cost_config: CostConfig | None = None

    if args.cost_config:
        cost_config = _load_cost_config(args.cost_config)
    elif "cost_config" in raw:
        raw_cost = raw["cost_config"]

        if isinstance(raw_cost, str):
            cost_config = _load_cost_config(raw_cost)
        elif isinstance(raw_cost, dict):
            cost_config = _make_cost_config(raw_cost)
        else:
            parser.error("cost_config must be a path string or JSON object")

    sla_target_ticks = (
        args.sla_target_ticks
        if args.sla_target_ticks is not None
        else raw.get("sla_target_ticks")
    )

    if sla_target_ticks is None and cost_config is not None:
        sla_target_ticks = cost_config.sla_target_ticks

    if sla_target_ticks is not None:
        sla_target_ticks = int(sla_target_ticks)

    reps = args.reps if args.reps is not None else int(raw.get("reps", 3))

    base_seed = args.base_seed if args.base_seed is not None else raw.get("base_seed")
    if base_seed is not None:
        base_seed = int(base_seed)

    output_dir = args.output_dir or raw.get("output_dir", "data/sensitivity")

    cfg = SensitivityConfig(
        base_config=base_config,
        factors=factors,
        reps=reps,
        base_seed=base_seed,
        sla_target_ticks=sla_target_ticks,
        cost_config=cost_config,
        output_dir=output_dir,
        runs_base_dir=runs_base_dir,
    )

    result = run_sensitivity(cfg)

    payload = {
        "study_id": result.study_id,
        "output_dir": str(result.output_dir),
        "results_csv": str(result.results_csv),
        "summary_json": str(result.summary_json),
        "tornado_csv": str(result.tornado_csv),
        "successful_runs": result.successful_runs,
        "failed_runs": result.failed_runs,
        "baseline": result.baseline,
        "top_tornado": {
            "cost_per_task": result.tornado.get("cost_per_task", [])[:5],
            "p95_cycle_time": result.tornado.get("p95_cycle_time", [])[:5],
        },
    }

    if result.failed_runs:
        payload["errors"] = result.errors[:5]

    print(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    main()