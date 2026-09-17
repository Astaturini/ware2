from pathlib import Path

import pytest

from decision.jobs import DecisionJobError, DecisionJobManager


def _manager(tmp_path: Path) -> DecisionJobManager:
    return DecisionJobManager(
        data_dir=tmp_path / "data",
        runs_dir=tmp_path / "data" / "runs",
        max_workers=1,
    )


def test_monte_carlo_job_has_workload_limit(tmp_path: Path) -> None:
    manager = _manager(tmp_path)

    with pytest.raises(DecisionJobError, match="n_runs must be <="):
        manager.submit(
            "monte_carlo",
            {
                "base_config": {
                    "seed": 1,
                    "num_robots": 1,
                    "stop_mode": "fixed_ticks",
                    "target_tasks": None,
                    "max_ticks": 5,
                },
                "n_runs": 101,
            },
        )


def test_optimizer_search_space_has_workload_limit(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    search_space = [
        {"name": f"factor_{index}", "type": "int", "low": 1, "high": 2}
        for index in range(21)
    ]

    with pytest.raises(DecisionJobError, match="search_space must contain <="):
        manager.submit(
            "optimizer",
            {
                "base_config": {
                    "seed": 1,
                    "num_robots": 1,
                    "stop_mode": "fixed_ticks",
                    "target_tasks": None,
                    "max_ticks": 5,
                },
                "objective": "p95_cycle_time",
                "search_space": search_space,
                "n_trials": 1,
                "reps": 1,
            },
        )