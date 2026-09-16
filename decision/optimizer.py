from __future__ import annotations

import argparse
import json
import math
import statistics
import time
import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import optuna
from optuna.trial import FrozenTrial, Trial

from analysis.loader import DEFAULT_RUNS_DIR, load_run
from experiment.config import ExperimentConfig

from decision.cost import CostConfig
from decision.execution import validate_execution_options
from decision.sensitivity import (
    _execute_trial,
    extract_sensitivity_metrics,
    generate_seeds,
    _build_variant_config,
    _ALLOWED_COST_FIELDS,
)


@dataclass(frozen=True)
class SearchSpaceSpec:
    name: str
    type: str  # "int", "float", "categorical"
    low: float | None = None
    high: float | None = None
    choices: list[Any] | None = None


@dataclass(frozen=True)
class OptimizerConfig:
    base_config: dict[str, Any]
    search_space: list[SearchSpaceSpec]
    objective: str = "cost_per_task"
    direction: str = "minimize"
    n_trials: int = 50
    reps: int = 1
    base_seed: int | None = None
    constraints: dict[str, float] = field(default_factory=dict)
    sla_target_ticks: int | None = None
    cost_config: CostConfig | None = None
    force_fast_mode: bool = True
    output_dir: str = "data/optimizations"
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
        if self.direction not in {"minimize", "maximize"}:
            raise ValueError("direction must be minimize or maximize")
        validate_execution_options(self.max_workers, self.trial_artifact_mode)
        
        allowed_objectives = {
            "cost_per_task", 
            "p95_cycle_time", 
            "average_throughput", 
            "tasks_completed"
        }
        if self.objective not in allowed_objectives:
            raise ValueError(f"unsupported objective: {self.objective}")


def suggest_param(trial: Trial, spec: SearchSpaceSpec) -> Any:
    if spec.type == "int":
        if spec.low is None or spec.high is None:
            raise ValueError(f"int parameter {spec.name} requires low and high")
        return trial.suggest_int(spec.name, int(spec.low), int(spec.high))
    elif spec.type == "float":
        if spec.low is None or spec.high is None:
            raise ValueError(f"float parameter {spec.name} requires low and high")
        return trial.suggest_float(spec.name, float(spec.low), float(spec.high))
    elif spec.type == "categorical":
        if not spec.choices:
            raise ValueError(f"categorical parameter {spec.name} requires choices")
        return trial.suggest_categorical(spec.name, spec.choices)
    else:
        raise ValueError(f"unknown parameter type: {spec.type}")


def _load_cost_config(path: str | Path) -> CostConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("cost config JSON must be an object")
    clean = {k: v for k, v in data.items() if k in _ALLOWED_COST_FIELDS}
    return CostConfig(**clean)


def run_optimization(cfg: OptimizerConfig) -> dict[str, Any]:
    opt_id = time.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
    out_dir = Path(cfg.output_dir) / opt_id
    out_dir.mkdir(parents=True, exist_ok=True)
    
    seeds = generate_seeds(cfg.reps, cfg.base_seed)
    
    effective_sla = cfg.sla_target_ticks
    cost_config = cfg.cost_config
    if cost_config is not None and effective_sla is None:
        effective_sla = cost_config.sla_target_ticks
    if cost_config is not None and effective_sla is not None and cost_config.sla_target_ticks != effective_sla:
        cost_config = replace(cost_config, sla_target_ticks=effective_sla)
        
    base_name = cfg.base_config.get("display_name") or "optimizer"
    
    def objective(trial: Trial) -> float:
        overrides = {}
        for spec in cfg.search_space:
            overrides[spec.name] = suggest_param(trial, spec)
            
        trial_metrics = []
        for rep, seed in enumerate(seeds):
            display_name = f"{base_name} opt trial={trial.number} rep={rep} seed={seed}"
            trial_dict = _build_variant_config(
                cfg.base_config,
                overrides=overrides,
                seed=seed,
                display_name=display_name,
                force_fast_mode=cfg.force_fast_mode,
            )
            try:
                trial_config = ExperimentConfig.from_dict(trial_dict)
                metrics = extract_sensitivity_metrics(
                    _execute_trial(trial_config, cfg.runs_base_dir),
                    cfg.runs_base_dir,
                    cost_config=cost_config,
                    sla_target_ticks=effective_sla,
                )
                trial_metrics.append(metrics)
            except Exception as e:
                trial.set_user_attr("error", str(e))
                return float("inf") if cfg.direction == "minimize" else float("-inf")
                    
        agg = {}
        for key in ["cost_per_task", "p95_cycle_time", "average_throughput", "tasks_completed", "sla_compliance_rate"]:
            vals = [m[key] for m in trial_metrics if m.get(key) is not None and math.isfinite(m[key])]
            agg[key] = statistics.fmean(vals) if vals else None
                
        # Optuna constraints: value <= 0 means satisfied.
        constraint_violations = []
        
        if "p95_cycle_time_max" in cfg.constraints:
            val = agg.get("p95_cycle_time")
            limit = cfg.constraints["p95_cycle_time_max"]
            constraint_violations.append(float("inf") if val is None else val - limit)
                
        if "sla_compliance_rate_min" in cfg.constraints:
            val = agg.get("sla_compliance_rate")
            limit = cfg.constraints["sla_compliance_rate_min"]
            constraint_violations.append(float("inf") if val is None else limit - val)
                
        trial.set_user_attr("constraints", constraint_violations)
        trial.set_user_attr("metrics", agg)
        trial.set_user_attr("feasible", all(v <= 1e-9 for v in constraint_violations))
        
        obj_val = agg.get(cfg.objective)
        if obj_val is None or not math.isfinite(obj_val):
            return float("inf") if cfg.direction == "minimize" else float("-inf")
            
        return obj_val

    def constraints_func(trial: FrozenTrial) -> list[float]:
        return trial.user_attrs.get("constraints", [])

    optuna.logging.set_verbosity(optuna.logging.INFO)
    
    # Use TPESampler with native constraint handling
    sampler = optuna.samplers.TPESampler(constraints_func=constraints_func, seed=cfg.base_seed)
    
    study = optuna.create_study(
        study_name=opt_id,
        direction=cfg.direction,
        sampler=sampler,
    )
    
    study.optimize(objective, n_trials=cfg.n_trials, timeout=cfg.timeout)
    
    trials_data = []
    for t in study.trials:
        trials_data.append({
            "number": t.number,
            "params": t.params,
            "value": t.value,
            "state": t.state.name,
            "metrics": t.user_attrs.get("metrics", {}),
            "feasible": t.user_attrs.get("feasible", False),
            "constraints": t.user_attrs.get("constraints", []),
            "error": t.user_attrs.get("error"),
        })
        
    best_trial = None
    feasible_trials = [t for t in trials_data if t["feasible"] and t["state"] == "COMPLETE"]
    if feasible_trials:
        if cfg.direction == "minimize":
            best_trial = min(feasible_trials, key=lambda x: x["value"])
        else:
            best_trial = max(feasible_trials, key=lambda x: x["value"])
            
    summary = {
        "opt_id": opt_id,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_trials": cfg.n_trials,
        "reps": cfg.reps,
        "objective": cfg.objective,
        "direction": cfg.direction,
        "constraints": cfg.constraints,
        "best_trial": best_trial,
        "feasible_count": len(feasible_trials),
        "infeasible_count": len(trials_data) - len(feasible_trials),
        "search_space": [{"name": s.name, "type": s.type} for s in cfg.search_space],
    }
    
    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    
    trials_path = out_dir / "trials.json"
    trials_path.write_text(json.dumps(trials_data, indent=2, default=str), encoding="utf-8")
    
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m decision.optimizer",
        description="Run Optuna-based business optimization.",
    )
    parser.add_argument("--config", required=True, help="Path to optimizer config JSON.")
    parser.add_argument("--n-trials", type=int, default=None, help="Override n_trials.")
    parser.add_argument("--reps", type=int, default=None, help="Override reps.")
    parser.add_argument("--base-seed", type=int, default=None, help="Override base seed.")
    parser.add_argument("--timeout", type=float, default=None, help="Timeout in seconds.")
    
    args = parser.parse_args(argv)
    
    raw = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        parser.error("--config must contain a JSON object")
        return
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
            name=str(s["name"]),
            type=str(s["type"]),
            low=s.get("low"),
            high=s.get("high"),
            choices=s.get("choices"),
        )
        for s in search_space_raw
    ]
    
    cost_config = None
    if "cost_config" in raw:
        raw_cost = raw["cost_config"]
        if isinstance(raw_cost, str):
            cost_config = _load_cost_config(raw_cost)
        elif isinstance(raw_cost, dict):
            clean = {k: v for k, v in raw_cost.items() if k in _ALLOWED_COST_FIELDS}
            cost_config = CostConfig(**clean)
            
    sla_target_ticks = raw.get("sla_target_ticks")
    if sla_target_ticks is None and cost_config is not None:
        sla_target_ticks = cost_config.sla_target_ticks
        
    cfg = OptimizerConfig(
        base_config=base_config,
        search_space=search_space,
        objective=raw.get("objective", "cost_per_task"),
        direction=raw.get("direction", "minimize"),
        n_trials=args.n_trials or raw.get("n_trials", 50),
        reps=args.reps or raw.get("reps", 1),
        base_seed=args.base_seed or raw.get("base_seed"),
        constraints=raw.get("constraints", {}),
        sla_target_ticks=sla_target_ticks,
        cost_config=cost_config,
        output_dir=raw.get("output_dir", "data/optimizations"),
        runs_base_dir=runs_base_dir,
        timeout=args.timeout or raw.get("timeout"),
    )
    
    summary = run_optimization(cfg)
    
    print(json.dumps({
        "opt_id": summary["opt_id"],
        "output_dir": str(Path(cfg.output_dir) / summary["opt_id"]),
        "feasible_count": summary["feasible_count"],
        "infeasible_count": summary["infeasible_count"],
        "best_trial": summary["best_trial"],
    }, indent=2, default=str))


if __name__ == "__main__":
    main()