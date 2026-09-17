from pathlib import Path
import time

import pytest

from decision.monte_carlo import MonteCarloConfig, run_monte_carlo


def _base_config() -> dict[str, object]:
    return {
        "seed": 1,
        "num_robots": 1,
        "stop_mode": "fixed_ticks",
        "target_tasks": None,
        "max_ticks": 5,
    }


def test_metrics_only_does_not_write_run_artifacts(tmp_path: Path) -> None:
    result = run_monte_carlo(
        MonteCarloConfig(
            base_config=_base_config(),
            n_runs=2,
            seeds=[11, 12],
            output_dir=str(tmp_path / "monte_carlo"),
            runs_base_dir=str(tmp_path / "runs"),
            trial_artifact_mode="metrics_only",
        )
    )

    assert result.successful_runs == 2
    assert result.failed_runs == 0
    assert not (tmp_path / "runs").exists()
    assert result.aggregate["successful_runs"] == 2
    assert '"run_artifacts_written": false' in result.summary_json.read_text()


def test_metrics_only_parallel_results_match_sequential(tmp_path: Path) -> None:
    sequential = run_monte_carlo(
        MonteCarloConfig(
            base_config=_base_config(),
            n_runs=2,
            seeds=[11, 12],
            output_dir=str(tmp_path / "sequential"),
            runs_base_dir=str(tmp_path / "runs-sequential"),
            max_workers=1,
            trial_artifact_mode="metrics_only",
        )
    )
    parallel = run_monte_carlo(
        MonteCarloConfig(
            base_config=_base_config(),
            n_runs=2,
            seeds=[11, 12],
            output_dir=str(tmp_path / "parallel"),
            runs_base_dir=str(tmp_path / "runs-parallel"),
            max_workers=2,
            trial_artifact_mode="metrics_only",
        )
    )

    assert parallel.aggregate == sequential.aggregate
    assert parallel.successful_runs == sequential.successful_runs
    assert parallel.failed_runs == sequential.failed_runs


def test_metrics_only_matches_full_trial_metrics(tmp_path: Path) -> None:
    from decision.cost import CostConfig
    from decision.monte_carlo import build_trial_config, extract_run_metrics
    from experiment.config import ExperimentConfig
    from experiment.factory import create_simulation_from_config
    from experiment.headless import run_headless_trial
    from experiment.runner import ExperimentRunner

    cost_config = CostConfig(
        robot_opex_per_hour=12.5,
        charger_infra_cost_per_hour=2.0,
        downtime_cost_per_hour=30.0,
        sla_target_ticks=10,
        sla_penalty_per_late_tick=0.5,
    )
    trial_dict = build_trial_config(_base_config(), 11, 0, force_fast_mode=True)
    trial_config = ExperimentConfig.from_dict(trial_dict)

    runner = ExperimentRunner(base_dir=str(tmp_path / "runs"))
    run_id = runner.start(trial_config, create_simulation_from_config)
    deadline = time.monotonic() + 10
    while not runner.finished:
        if time.monotonic() >= deadline:
            runner.stop("test_timeout")
            pytest.fail("experiment runner did not finish before the test deadline")
        time.sleep(0.01)

    full = extract_run_metrics(
        run_id,
        str(tmp_path / "runs"),
        cost_config=cost_config,
        sla_target_ticks=10,
    )
    light = run_headless_trial(
        trial_dict,
        sla_target_ticks=10,
        cost_config=cost_config,
    )
    assert light.ok, light.error

    for key in (
        "tasks_created",
        "tasks_completed",
        "tasks_failed",
        "simulation_ticks",
        "average_cycle_time",
        "average_wait_time",
        "average_throughput",
        "total_blocked_ticks",
        "total_replans",
        "total_operating_cost",
        "cost_per_task",
        "sla_compliance_rate",
    ):
        assert light.metrics[key] == full[key]
