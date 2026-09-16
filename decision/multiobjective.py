# decision/multiobjective.py
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

import optuna
from optuna.trial import Trial

from analysis.loader import DEFAULT_RUNS_DIR, load_run
from experiment.config import ExperimentConfig

from decision.cost import CostConfig
from decision.execution import validate_execution_options
from decision.optimizer import SearchSpaceSpec, suggest_param
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
class ObjectiveSpec:
    metric: str
    direction: str = "minimize"


@dataclass(frozen=True)
class MultiObjectiveConfig:
    base_config: dict[str, Any]
    search_space: list[SearchSpaceSpec]
    objectives: list[ObjectiveSpec]
    constraints: dict[str, float] = field(default_factory=dict)
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
    max_workers: int = 1
    trial_artifact_mode: str = "full"

    def __post_init__(self) -> None:
        if self.n_trials < 1:
            raise ValueError("n_trials must be >= 1")
        if self.reps < 1:
            raise ValueError("reps must be >= 1")
        if not self.base_config:
            raise ValueError("base_config is required")
        if not self.search_space:
            raise ValueError("search_space is required")
        if not self.objectives:
            raise ValueError("objectives is required")
        validate_execution_options(self.max_workers, self.trial_artifact_mode)

        for objective in self.objectives:
            if objective.metric not in _ALLOWED_METRICS:
                raise ValueError(f"unsupported objective metric: {objective.metric}")
            if objective.direction not in {"minimize", "maximize"}:
                raise ValueError("objective direction must be minimize or maximize")

        for key in self.constraints:
            if not key.endswith("_max") and not key.endswith("_min"):
                raise ValueError("constraint keys must end with _max or _min")

            metric = key[:-4]
            if metric not in _ALLOWED_METRICS:
                raise ValueError(f"unsupported constraint metric: {metric}")

        if any(o.metric == "cost_per_task" for o in self.objectives) and self.cost_config is None:
            raise ValueError("cost_config is required when cost_per_task is an objective")

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


def _worst_value(direction: str) -> float:
    if direction == "minimize":
        return 1e12
    return -1e12


def _constraint_values(metrics: dict[str, Any], constraints: dict[str, float]) -> list[float]:
    values: list[float] = []

    for key, limit in constraints.items():
        if key.endswith("_max"):
            metric = key[:-4]
            value = _as_finite_float(metrics.get(metric))
            values.append(float("inf") if value is None else value - float(limit))
        elif key.endswith("_min"):
            metric = key[:-4]
            value = _as_finite_float(metrics.get(metric))
            values.append(float("inf") if value is None else float(limit) - value)
        else:
            raise ValueError(f"invalid constraint key: {key}")

    return values


def _aggregate_metrics(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    aggregate: dict[str, float | None] = {}

    for key in _METRICS:
        nums: list[float] = []

        for row in rows:
            value = _as_finite_float(row.get(key))
            if value is not None:
                nums.append(value)

        aggregate[key] = statistics.fmean(nums) if nums else None

    return aggregate


def _evaluate_params(
    cfg: MultiObjectiveConfig,
    overrides: dict[str, Any],
    trial_number: int,
    seeds: list[int],
    cost_config: CostConfig | None,
    effective_sla: int | None,
) -> dict[str, float | None]:
    rows: list[dict[str, Any]] = []
    base_name = cfg.base_config.get("display_name") or "multiobjective"

    for rep, seed in enumerate(seeds):
        display_name = f"{base_name} mo trial={trial_number} rep={rep} seed={seed}"

        trial_dict = _build_variant_config(
            cfg.base_config,
            overrides=overrides,
            seed=seed,
            display_name=display_name,
            force_fast_mode=cfg.force_fast_mode,
        )

        trial_config = ExperimentConfig.from_dict(trial_dict)
        run_id = _execute_trial(trial_config, cfg.runs_base_dir)
        row = extract_sensitivity_metrics(
            run_id,
            cfg.runs_base_dir,
            cost_config=cost_config,
            sla_target_ticks=effective_sla,
        )
        rows.append(row)

    return _aggregate_metrics(rows)


def _to_minimized(values: list[float], directions: list[str]) -> list[float]:
    minimized: list[float] = []

    for value, direction in zip(values, directions):
        if direction == "minimize":
            minimized.append(value)
        else:
            minimized.append(-value)

    return minimized


def _dominates(a: list[float], b: list[float], directions: list[str]) -> bool:
    if len(a) != len(b) or len(a) != len(directions):
        return False

    am = _to_minimized(a, directions)
    bm = _to_minimized(b, directions)

    strictly_better = False

    for av, bv in zip(am, bm):
        if av > bv + 1e-12:
            return False
        if av < bv - 1e-12:
            strictly_better = True

    return strictly_better


def _pareto_trials(
    trials: list[dict[str, Any]],
    directions: list[str],
) -> list[dict[str, Any]]:
    pareto: list[dict[str, Any]] = []

    for i, trial in enumerate(trials):
        if not trial.get("values"):
            continue

        dominated = False

        for j, other in enumerate(trials):
            if i == j or not other.get("values"):
                continue

            if _dominates(other["values"], trial["values"], directions):
                dominated = True
                break

        if not dominated:
            pareto.append(trial)

    if directions:
        pareto.sort(
            key=lambda t: t["values"][0]
            if directions[0] == "minimize"
            else -t["values"][0]
        )

    return pareto


def run_multiobjective(cfg: MultiObjectiveConfig) -> dict[str, Any]:
    study_id = time.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
    out_dir = Path(cfg.output_dir) / study_id
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

    base_name = cfg.base_config.get("display_name") or "multiobjective"

    def objective(trial: Trial) -> tuple[float, ...]:
        overrides = {}

        for spec in cfg.search_space:
            overrides[spec.name] = suggest_param(trial, spec)

        try:
            metrics = _evaluate_params(
                cfg,
                overrides=overrides,
                trial_number=trial.number,
                seeds=seeds,
                cost_config=cost_config,
                effective_sla=effective_sla,
            )
        except Exception as exc:
            trial.set_user_attr("error", str(exc))
            trial.set_user_attr("metrics", {})
            trial.set_user_attr("constraints", [])
            trial.set_user_attr("feasible", False)
            return tuple(_worst_value(o.direction) for o in cfg.objectives)

        constraints = _constraint_values(metrics, cfg.constraints)
        feasible = all(value <= 1e-9 for value in constraints)

        trial.set_user_attr("metrics", metrics)
        trial.set_user_attr("constraints", constraints)
        trial.set_user_attr("feasible", feasible)

        values: list[float] = []

        for objective_spec in cfg.objectives:
            value = _as_finite_float(metrics.get(objective_spec.metric))
            values.append(value if value is not None else _worst_value(objective_spec.direction))

        return tuple(values)

    directions = [objective.direction for objective in cfg.objectives]

    optuna.logging.set_verbosity(optuna.logging.INFO)

    if cfg.n_trials < 2:
        sampler = optuna.samplers.RandomSampler(seed=cfg.base_seed)
    else:
        population_size = cfg.population_size or min(50, cfg.n_trials)
        population_size = max(2, min(population_size, cfg.n_trials))
        sampler = optuna.samplers.NSGAIISampler(
            seed=cfg.base_seed,
            population_size=population_size,
        )

    study = optuna.create_study(
        study_name=study_id,
        directions=directions,
        sampler=sampler,
    )

    study.optimize(objective, n_trials=cfg.n_trials, timeout=cfg.timeout)

    trials_data: list[dict[str, Any]] = []

    for trial in study.trials:
        trials_data.append(
            {
                "number": trial.number,
                "params": trial.params,
                "values": list(trial.values) if trial.values is not None else [],
                "state": trial.state.name,
                "metrics": trial.user_attrs.get("metrics", {}),
                "constraints": trial.user_attrs.get("constraints", []),
                "feasible": trial.user_attrs.get("feasible", False),
                "error": trial.user_attrs.get("error"),
            }
        )

    feasible_trials = [
        trial
        for trial in trials_data
        if trial["feasible"] and trial["state"] == "COMPLETE"
    ]

    pareto = _pareto_trials(feasible_trials, directions)

    trials_path = out_dir / "trials.json"
    trials_path.write_text(
        json.dumps(trials_data, indent=2, default=str),
        encoding="utf-8",
    )

    objective_columns = [f"objective:{o.metric}" for o in cfg.objectives]
    param_columns = [spec.name for spec in cfg.search_space]

    pareto_csv = out_dir / "pareto.csv"
    fieldnames = ["trial_number", "feasible"] + objective_columns + param_columns + ["constraint_values"]

    with pareto_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, restval="")
        writer.writeheader()

        for trial in pareto:
            row: dict[str, Any] = {
                "trial_number": trial["number"],
                "feasible": trial["feasible"],
                "constraint_values": json.dumps(trial.get("constraints", []), default=str),
            }

            for i, column in enumerate(objective_columns):
                row[column] = trial["values"][i] if i < len(trial["values"]) else None

            for param in param_columns:
                row[param] = trial["params"].get(param)

            writer.writerow({k: _csv_safe(row.get(k)) for k in fieldnames})

    summary = {
        "study_id": study_id,
        "output_dir": str(out_dir),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "objectives": [{"metric": o.metric, "direction": o.direction} for o in cfg.objectives],
        "constraints": cfg.constraints,
        "n_trials": cfg.n_trials,
        "reps": cfg.reps,
        "base_seed": cfg.base_seed,
        "sla_target_ticks": effective_sla,
        "base_config": cfg.base_config,
        "cost_config": asdict(cost_config) if cost_config is not None else None,
        "search_space": [
            {
                "name": spec.name,
                "type": spec.type,
                "low": spec.low,
                "high": spec.high,
                "choices": spec.choices,
            }
            for spec in cfg.search_space
        ],
        "total_trials": len(trials_data),
        "feasible_count": len(feasible_trials),
        "pareto_count": len(pareto),
        "pareto_trials": pareto,
    }

    summary_path = out_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, default=str),
        encoding="utf-8",
    )

    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m decision.multiobjective",
        description="Run NSGA-II multi-objective optimization.",
    )
    parser.add_argument("--config", required=True, help="Path to multi-objective config JSON.")
    parser.add_argument("--n-trials", type=int, default=None, help="Override n_trials.")
    parser.add_argument("--reps", type=int, default=None, help="Override reps.")
    parser.add_argument("--base-seed", type=int, default=None, help="Override base seed.")
    parser.add_argument("--timeout", type=float, default=None, help="Timeout in seconds.")
    parser.add_argument("--cost-config", type=str, default=None, help="Override cost config path.")

    args = parser.parse_args(argv)

    raw = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        parser.error("--config must contain a JSON object")

    runs_base_dir = raw.get("runs_base_dir", DEFAULT_RUNS_DIR)

    if "from_run_id" in raw and "base_config" in raw:
        parser.error("config may contain either from_run_id or base_config, not both")

    if "from_run_id" in raw:
        run = load_run(raw["from_run_id"], runs_base_dir)
        base_config = dict(run.config)
    elif "base_config" in raw:
        base_config = raw["base_config"]
    else:
        parser.error("config must contain from_run_id or base_config")

    search_space_raw = raw.get("search_space", [])
    if not isinstance(search_space_raw, list) or not search_space_raw:
        parser.error("config must contain a non-empty search_space list")

    search_space = [
        SearchSpaceSpec(
            name=str(spec["name"]),
            type=str(spec["type"]),
            low=spec.get("low"),
            high=spec.get("high"),
            choices=spec.get("choices"),
        )
        for spec in search_space_raw
    ]

    objectives_raw = raw.get("objectives", [])
    if not isinstance(objectives_raw, list) or not objectives_raw:
        parser.error("config must contain a non-empty objectives list")

    objectives = [
        ObjectiveSpec(
            metric=str(obj["metric"]),
            direction=str(obj.get("direction", "minimize")),
        )
        for obj in objectives_raw
    ]

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

    sla_target_ticks = raw.get("sla_target_ticks")
    if sla_target_ticks is None and cost_config is not None:
        sla_target_ticks = cost_config.sla_target_ticks

    if sla_target_ticks is not None:
        sla_target_ticks = int(sla_target_ticks)

    cfg = MultiObjectiveConfig(
        base_config=base_config,
        search_space=search_space,
        objectives=objectives,
        constraints=raw.get("constraints", {}),
        n_trials=args.n_trials or int(raw.get("n_trials", 50)),
        reps=args.reps or int(raw.get("reps", 1)),
        base_seed=args.base_seed or raw.get("base_seed"),
        population_size=raw.get("population_size"),
        sla_target_ticks=sla_target_ticks,
        cost_config=cost_config,
        output_dir=raw.get("output_dir", "data/multiobjective"),
        runs_base_dir=runs_base_dir,
        timeout=args.timeout or raw.get("timeout"),
    )

    summary = run_multiobjective(cfg)

    print(
        json.dumps(
            {
                "study_id": summary["study_id"],
                "output_dir": summary["output_dir"],
                "total_trials": summary["total_trials"],
                "feasible_count": summary["feasible_count"],
                "pareto_count": summary["pareto_count"],
                "top_pareto": summary["pareto_trials"][:5],
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()