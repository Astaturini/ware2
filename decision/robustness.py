# decision/robustness.py
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import time
import uuid
from dataclasses import dataclass, field, fields, asdict, replace
from pathlib import Path
from typing import Any

from analysis.loader import DEFAULT_RUNS_DIR, load_run
from experiment.config import ExperimentConfig

from decision.cost import CostConfig
from decision.sensitivity import (
    _execute_trial,
    extract_sensitivity_metrics,
    generate_seeds,
    _build_variant_config,
)


_ALLOWED_COST_FIELDS = {f.name for f in fields(CostConfig)}

_METRICS = (
    "cost_per_task",
    "p95_cycle_time",
    "average_cycle_time",
    "average_throughput",
    "tasks_completed",
    "sla_compliance_rate",
    "total_blocked_ticks",
)

_ALLOWED_METRICS = set(_METRICS)


@dataclass(frozen=True)
class RobustnessCandidate:
    label: str
    overrides: dict[str, Any]


@dataclass(frozen=True)
class RobustnessConfig:
    base_config: dict[str, Any]
    candidates: list[RobustnessCandidate]
    reps: int = 20
    base_seed: int | None = None
    constraints: dict[str, float] = field(default_factory=dict)
    objective: str = "cost_per_task"
    direction: str = "minimize"
    min_pass_probability: float = 0.95
    sla_target_ticks: int | None = None
    cost_config: CostConfig | None = None
    force_fast_mode: bool = True
    output_dir: str = "data/robustness"
    runs_base_dir: str = DEFAULT_RUNS_DIR

    def __post_init__(self) -> None:
        if self.reps < 1:
            raise ValueError("reps must be >= 1")
        if not self.base_config:
            raise ValueError("base_config is required")
        if not self.candidates:
            raise ValueError("candidates is required")
        if self.objective not in _ALLOWED_METRICS:
            raise ValueError(f"unsupported objective metric: {self.objective}")
        if self.direction not in {"minimize", "maximize"}:
            raise ValueError("direction must be minimize or maximize")
        if not 0.0 <= self.min_pass_probability <= 1.0:
            raise ValueError("min_pass_probability must be between 0 and 1")

        for key in self.constraints:
            if not key.endswith("_max") and not key.endswith("_min"):
                raise ValueError("constraint keys must end with _max or _min")

            metric = key[:-4]
            if metric not in _ALLOWED_METRICS:
                raise ValueError(f"unsupported constraint metric: {metric}")

        if self.objective == "cost_per_task" and self.cost_config is None:
            raise ValueError("cost_config is required when objective is cost_per_task")

        if any(key.startswith("cost_per_task") for key in self.constraints) and self.cost_config is None:
            raise ValueError("cost_config is required for cost_per_task constraints")

        if any(key.startswith("sla_compliance_rate") for key in self.constraints):
            has_sla = (
                self.sla_target_ticks is not None
                or (self.cost_config is not None and self.cost_config.sla_target_ticks is not None)
            )
            if not has_sla:
                raise ValueError("sla_target_ticks is required for sla_compliance_rate constraints")


def _make_cost_config(data: dict[str, Any]) -> CostConfig:
    clean = {k: v for k, v in data.items() if k in _ALLOWED_COST_FIELDS}
    return CostConfig(**clean)


def _load_cost_config(path: str | Path) -> CostConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("cost config JSON must be an object")
    return _make_cost_config(data)


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


def _summarize_values(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "mean": None,
            "stdev": None,
            "min": None,
            "p05": None,
            "median": None,
            "p95": None,
            "max": None,
        }

    mean = statistics.fmean(values)
    stdev = statistics.stdev(values) if len(values) > 1 else 0.0

    return {
        "count": len(values),
        "mean": mean,
        "stdev": stdev,
        "min": min(values),
        "p05": _percentile(values, 0.05),
        "median": statistics.median(values),
        "p95": _percentile(values, 0.95),
        "max": max(values),
    }


def _summarize_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}

    for key in _METRICS:
        nums: list[float] = []

        for row in rows:
            value = _as_finite_float(row.get(key))
            if value is not None:
                nums.append(value)

        summary[key] = _summarize_values(nums)

    return summary


def _evaluate_constraints_for_rows(
    rows: list[dict[str, Any]],
    constraints: dict[str, float],
) -> dict[str, Any]:
    n = len(rows)
    row_feasible = [True] * n
    details: dict[str, Any] = {}

    for key, limit in constraints.items():
        if key.endswith("_max"):
            metric = key[:-4]
            limit_value = float(limit)

            def passes(value: float) -> bool:
                return value <= limit_value + 1e-9

        elif key.endswith("_min"):
            metric = key[:-4]
            limit_value = float(limit)

            def passes(value: float) -> bool:
                return value >= limit_value - 1e-9

        else:
            raise ValueError(f"invalid constraint key: {key}")

        passes_list: list[bool] = []
        finite_values: list[float] = []

        for i, row in enumerate(rows):
            value = _as_finite_float(row.get(metric))

            if value is None:
                ok = False
            else:
                ok = passes(value)
                finite_values.append(value)

            if not ok:
                row_feasible[i] = False

            passes_list.append(ok)

        if key.endswith("_max"):
            worst_value = max(finite_values) if finite_values else None
        else:
            worst_value = min(finite_values) if finite_values else None

        details[key] = {
            "metric": metric,
            "limit": limit,
            "pass_probability": sum(passes_list) / n if n else 0.0,
            "mean_value": statistics.fmean(finite_values) if finite_values else None,
            "worst_value": worst_value,
        }

    return {
        "overall_pass_probability": sum(row_feasible) / n if n else 0.0,
        "row_feasible": row_feasible,
        "details": details,
    }


def run_robustness(cfg: RobustnessConfig) -> dict[str, Any]:
    robust_id = time.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
    out_dir = Path(cfg.output_dir) / robust_id
    out_dir.mkdir(parents=True, exist_ok=True)

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

    base_name = cfg.base_config.get("display_name") or "robustness"

    all_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    candidate_results: list[dict[str, Any]] = []

    for candidate in cfg.candidates:
        rows: list[dict[str, Any]] = []

        for rep, seed in enumerate(seeds):
            display_name = f"{base_name} robust {candidate.label} rep={rep} seed={seed}"

            trial_dict = _build_variant_config(
                cfg.base_config,
                overrides=candidate.overrides,
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
                        "candidate": candidate.label,
                        "rep": rep,
                        "seed": seed,
                        "overrides": json.dumps(candidate.overrides, default=str),
                    }
                )
                rows.append(row)
            except Exception as exc:
                errors.append(
                    {
                        "candidate": candidate.label,
                        "rep": rep,
                        "seed": seed,
                        "error": str(exc),
                    }
                )

        constraint_evaluation = _evaluate_constraints_for_rows(rows, cfg.constraints)

        for row, feasible in zip(rows, constraint_evaluation["row_feasible"]):
            row["feasible"] = feasible

        all_rows.extend(rows)

        metrics_summary = _summarize_metrics(rows)

        objective_values = [
            value
            for row in rows
            if (value := _as_finite_float(row.get(cfg.objective))) is not None
        ]

        objective_mean = statistics.fmean(objective_values) if objective_values else None
        objective_stdev = statistics.stdev(objective_values) if len(objective_values) > 1 else 0.0

        successful_reps = len(rows)
        failed_reps = cfg.reps - successful_reps

        constraint_pass_probability = constraint_evaluation["overall_pass_probability"]
        robust_pass = bool(successful_reps > 0 and constraint_pass_probability >= cfg.min_pass_probability)

        candidate_results.append(
            {
                "label": candidate.label,
                "overrides": candidate.overrides,
                "successful_reps": successful_reps,
                "failed_reps": failed_reps,
                "constraint_pass_probability": constraint_pass_probability,
                "robust_pass": robust_pass,
                "objective_metric": cfg.objective,
                "objective_direction": cfg.direction,
                "objective_mean": objective_mean,
                "objective_stdev": objective_stdev,
                "metrics": metrics_summary,
                "constraint_details": constraint_evaluation["details"],
            }
        )

    def rank_key(result: dict[str, Any]) -> tuple[bool, float]:
        robust = bool(result["robust_pass"])
        objective_mean = result["objective_mean"]

        if objective_mean is None:
            objective_key = float("inf")
        elif cfg.direction == "minimize":
            objective_key = objective_mean
        else:
            objective_key = -objective_mean

        return (not robust, objective_key)

    candidate_results.sort(key=rank_key)

    recommended = (
        candidate_results[0]
        if candidate_results and candidate_results[0]["robust_pass"]
        else None
    )

    results_csv = out_dir / "results.csv"

    if all_rows:
        fieldnames: list[str] = []
        for row in all_rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)

        required = [
            "candidate",
            "rep",
            "seed",
            "run_id",
            "feasible",
            cfg.objective,
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
        results_csv.write_text("candidate,rep,seed,error\n", encoding="utf-8")

    summary = {
        "robust_id": robust_id,
        "output_dir": str(out_dir),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "reps": cfg.reps,
        "base_seed": cfg.base_seed,
        "objective": cfg.objective,
        "direction": cfg.direction,
        "constraints": cfg.constraints,
        "min_pass_probability": cfg.min_pass_probability,
        "sla_target_ticks": effective_sla,
        "base_config": cfg.base_config,
        "cost_config": asdict(cost_config) if cost_config is not None else None,
        "successful_runs": len(all_rows),
        "failed_runs": len(errors),
        "recommended": recommended,
        "candidates": candidate_results,
        "errors": errors,
    }

    summary_path = out_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, default=str),
        encoding="utf-8",
    )

    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m decision.robustness",
        description="Run stochastic robustness verification on candidate configurations.",
    )
    parser.add_argument("--config", required=True, help="Path to robustness config JSON.")
    parser.add_argument("--reps", type=int, default=None, help="Override reps.")
    parser.add_argument("--base-seed", type=int, default=None, help="Override base seed.")
    parser.add_argument(
        "--min-pass-probability",
        type=float,
        default=None,
        help="Override minimum constraint pass probability.",
    )

    args = parser.parse_args(argv)

    raw = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        parser.error("--config must contain a JSON object")

    runs_base_dir = raw.get("runs_base_dir", DEFAULT_RUNS_DIR)

    base_summary: dict[str, Any] | None = None

    if "from_multiobjective" in raw:
        mo_path = Path(raw["from_multiobjective"])

        if mo_path.is_dir():
            mo_path = mo_path / "summary.json"

        base_summary = json.loads(mo_path.read_text(encoding="utf-8"))

    if "from_run_id" in raw and "base_config" in raw:
        parser.error("config may contain either from_run_id or base_config, not both")

    if "from_run_id" in raw:
        run = load_run(raw["from_run_id"], runs_base_dir)
        base_config = dict(run.config)
    elif "base_config" in raw:
        base_config = raw["base_config"]
    elif base_summary is not None and "base_config" in base_summary:
        base_config = base_summary["base_config"]
    else:
        parser.error("config must contain from_run_id, base_config, or from_multiobjective with base_config")

    if not isinstance(base_config, dict):
        parser.error("base_config must be a JSON object")

    constraints = raw.get("constraints")
    if constraints is None and base_summary is not None:
        constraints = base_summary.get("constraints", {})
    constraints = constraints or {}

    if not isinstance(constraints, dict):
        parser.error("constraints must be a JSON object")

    cost_config: CostConfig | None = None

    if "cost_config" in raw:
        raw_cost = raw["cost_config"]

        if isinstance(raw_cost, str):
            cost_config = _load_cost_config(raw_cost)
        elif isinstance(raw_cost, dict):
            cost_config = _make_cost_config(raw_cost)
        else:
            parser.error("cost_config must be a path string or JSON object")
    elif base_summary is not None and isinstance(base_summary.get("cost_config"), dict):
        cost_config = _make_cost_config(base_summary["cost_config"])

    sla_target_ticks = raw.get("sla_target_ticks")

    if sla_target_ticks is None and base_summary is not None:
        sla_target_ticks = base_summary.get("sla_target_ticks")

    if sla_target_ticks is None and cost_config is not None:
        sla_target_ticks = cost_config.sla_target_ticks

    if sla_target_ticks is not None:
        sla_target_ticks = int(sla_target_ticks)

    objective = raw.get("objective")
    direction = raw.get("direction")

    if objective is None and base_summary is not None:
        if base_summary.get("objectives"):
            objective = base_summary["objectives"][0].get("metric", "cost_per_task")
            direction = direction or base_summary["objectives"][0].get("direction", "minimize")
        elif base_summary.get("objective"):
            objective = base_summary["objective"]
            direction = direction or base_summary.get("direction", "minimize")

    if objective is None:
        objective = "cost_per_task"

    if direction is None:
        direction = "minimize"

    candidates: list[RobustnessCandidate] = []

    if "candidates" in raw:
        candidates_raw = raw["candidates"]

        if not isinstance(candidates_raw, list) or not candidates_raw:
            parser.error("candidates must be a non-empty list")

        for i, item in enumerate(candidates_raw):
            if not isinstance(item, dict):
                parser.error("each candidate must be an object")

            overrides = item.get("overrides", {})
            if not isinstance(overrides, dict):
                parser.error("candidate overrides must be an object")

            candidates.append(
                RobustnessCandidate(
                    label=str(item.get("label") or f"candidate_{i}"),
                    overrides=overrides,
                )
            )
    else:
        if base_summary is None:
            parser.error("config must contain candidates or from_multiobjective")

        items: list[dict[str, Any]] = []

        if base_summary.get("pareto_trials"):
            items = base_summary["pareto_trials"]
        elif base_summary.get("best_trial"):
            items = [base_summary["best_trial"]]

        if not items:
            parser.error("no candidates found in multiobjective/optimization summary")

        max_candidates = int(raw.get("max_candidates", 3))

        for i, trial in enumerate(items[:max_candidates]):
            candidates.append(
                RobustnessCandidate(
                    label=f"trial_{trial.get('number', i)}",
                    overrides=dict(trial.get("params", {})),
                )
            )

    cfg = RobustnessConfig(
        base_config=base_config,
        candidates=candidates,
        reps=args.reps or int(raw.get("reps", 20)),
        base_seed=args.base_seed if args.base_seed is not None else raw.get("base_seed"),
        constraints=constraints,
        objective=str(objective),
        direction=str(direction),
        min_pass_probability=(
            args.min_pass_probability
            if args.min_pass_probability is not None
            else float(raw.get("min_pass_probability", 0.95))
        ),
        sla_target_ticks=sla_target_ticks,
        cost_config=cost_config,
        output_dir=raw.get("output_dir", "data/robustness"),
        runs_base_dir=runs_base_dir,
    )

    summary = run_robustness(cfg)

    recommended = summary.get("recommended")

    recommended_payload = None

    if recommended is not None:
        recommended_payload = {
            "label": recommended["label"],
            "overrides": recommended["overrides"],
            "constraint_pass_probability": recommended["constraint_pass_probability"],
            "objective_metric": recommended["objective_metric"],
            "objective_mean": recommended["objective_mean"],
            "objective_stdev": recommended["objective_stdev"],
        }

    print(
        json.dumps(
            {
                "robust_id": summary["robust_id"],
                "output_dir": summary["output_dir"],
                "successful_runs": summary["successful_runs"],
                "failed_runs": summary["failed_runs"],
                "recommended": recommended_payload,
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()