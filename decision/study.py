from __future__ import annotations

import itertools
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from analysis.loader import DEFAULT_RUNS_DIR, load_run
from decision.cost import CostConfig
from decision.kpis import compute_cost_kpis
from decision.execution import validate_execution_options
from experiment.config import ExperimentConfig
from experiment.factory import create_simulation_from_config
from experiment.runner import ExperimentRunner


@dataclass
class StudyConfig:
    study_name: str
    base_config: dict[str, Any]
    factors: dict[str, list[Any]]
    cost_config: dict[str, Any] = field(default_factory=dict)
    max_workers: int = 1
    trial_artifact_mode: str = "full"

    def __post_init__(self) -> None:
        validate_execution_options(self.max_workers, self.trial_artifact_mode)

    @classmethod
    def from_json(cls, path: str | Path) -> "StudyConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)


def generate_study_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_uuid = uuid.uuid4().hex[:6]
    return f"{timestamp}_{short_uuid}"


class StudyRunner:
    def __init__(
        self,
        config: StudyConfig,
        studies_dir: str | Path = "data/studies",
        runs_dir: str | Path = DEFAULT_RUNS_DIR,
    ):
        self.config = config
        self.studies_dir = Path(studies_dir)
        self.runs_dir = Path(runs_dir)
        
        self.study_id = generate_study_id()
        self.study_dir = self.studies_dir / self.study_id
        self.study_dir.mkdir(parents=True, exist_ok=True)

        self._cost_cfg = CostConfig(**self.config.cost_config)

    def _generate_combinations(self) -> list[dict[str, Any]]:
        keys = list(self.config.factors.keys())
        values = list(self.config.factors.values())
        return [dict(zip(keys, combo)) for combo in itertools.product(*values)]

    def _run_single_experiment(self, combo: dict[str, Any]) -> dict[str, Any]:
        # Merge base config with current factor combination
        run_cfg_dict = {**self.config.base_config, **combo}
        
        # Force fast_mode for batch execution
        run_cfg_dict["fast_mode"] = True 
        
        try:
            exp_config = ExperimentConfig.from_dict(run_cfg_dict)
        except Exception as e:
            return {"error": f"Config validation failed: {e}", **combo}

        runner = ExperimentRunner(base_dir=str(self.runs_dir))
        
        try:
            run_id = runner.start(exp_config, create_simulation_from_config)
            
            # Block until the daemon thread finishes
            while runner.is_active:
                time.sleep(0.05)
                
            state = runner.get_state()
            stop_reason = state.get("stopReason", "")
            
            if stop_reason.startswith("error"):
                return {"error": stop_reason, "run_id": run_id, **combo}
                
        except Exception as e:
            return {"error": f"Execution failed: {e}", **combo}

        # Load immutable artifacts and compute KPIs
        try:
            run_data = load_run(run_id, str(self.runs_dir))
            kpis = compute_cost_kpis(run_data, self._cost_cfg)
            
            result = {
                "run_id": run_id,
                "stop_reason": stop_reason,
                "tasks_completed": kpis.completed_tasks,
                "simulation_seconds": kpis.simulation_seconds,
                "total_operating_cost": kpis.total_operating_cost,
                "cost_per_task": kpis.cost_per_task,
                "sla_compliance_rate": kpis.sla_compliance_rate,
                **combo
            }
            return result
            
        except Exception as e:
            return {"error": f"Analysis failed: {e}", "run_id": run_id, **combo}

    def execute(self) -> Path:
        combinations = self._generate_combinations()
        print(f"Starting study '{self.config.study_name}' ({self.study_id})")
        print(f"Executing {len(combinations)} experiment combinations...")

        results = []
        for i, combo in enumerate(combinations, 1):
            print(f"[{i}/{len(combinations)}] Running: {combo}")
            row = self._run_single_experiment(combo)
            results.append(row)

        df = pd.DataFrame(results)
        
        # Reorder columns to put factors and errors first
        factor_cols = list(self.config.factors.keys())
        other_cols = [c for c in df.columns if c not in factor_cols]
        df = df[factor_cols + other_cols]

        results_path = self.study_dir / "results.csv"
        df.to_csv(results_path, index=False)

        config_path = self.study_dir / "study_config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self.config), f, indent=2)

        print(f"Study complete. Results saved to: {results_path}")
        return results_path


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run a Design of Experiments (DoE) Study")
    parser.add_argument("--config", required=True, help="Path to study JSON config")
    parser.add_argument("--studies-dir", default="data/studies", help="Base directory for studies")
    parser.add_argument("--runs-dir", default=DEFAULT_RUNS_DIR, help="Base directory for runs")
    
    args = parser.parse_args()
    
    cfg = StudyConfig.from_json(args.config)
    runner = StudyRunner(cfg, studies_dir=args.studies_dir, runs_dir=args.runs_dir)
    runner.execute()


if __name__ == "__main__":
    main()