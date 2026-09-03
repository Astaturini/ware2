import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from decision.study import StudyConfig, StudyRunner


def test_study_runner_executes_factorial_design():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        runs_dir = tmp_path / "runs"
        studies_dir = tmp_path / "studies"
        
        # Minimal config to ensure tests run in < 2 seconds
        config = StudyConfig(
            study_name="test_study",
            base_config={
                "seed": 42,
                "stop_mode": "workload",
                "target_tasks": 5, # Very small workload
                "max_ticks": 500,
                "tick_interval": 0.1,
                "num_robots": 2,
                "scheduler": "baseline",
                "conflict_manager": "local_yield",
                "path_planner": "bfs"
            },
            factors={
                "scheduler": ["baseline", "priority"],
            },
            cost_config={
                "robot_opex_per_hour": 5.0,
                "sla_target_ticks": 100,
                "sla_penalty_per_late_tick": 1.0
            }
        )

        runner = StudyRunner(config, studies_dir=studies_dir, runs_dir=runs_dir)
        results_path = runner.execute()

        # Verify output structure
        assert results_path.exists()
        assert (runner.study_dir / "study_config.json").exists()

        # Verify CSV content
        df = pd.read_csv(results_path)
        assert len(df) == 2  # 2 schedulers
        assert "scheduler" in df.columns
        assert "run_id" in df.columns
        assert "total_operating_cost" in df.columns
        
        # Verify runs were actually saved to the runs directory
        assert len(list(runs_dir.iterdir())) == 2