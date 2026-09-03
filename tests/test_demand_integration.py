import pytest

from decision.demand import DemandTaskGenerator
from experiment.config import ExperimentConfig
from experiment.factory import create_simulation_from_config
from simulation.task_generator import TaskGenerator


def make_config(**overrides) -> ExperimentConfig:
    data = {
        "seed": 1,
        "num_robots": 1,
        "stop_mode": "fixed_ticks",
        "target_tasks": None,
        "max_ticks": 5,
    }
    data.update(overrides)
    return ExperimentConfig.from_dict(data)


def test_default_demand_mode_is_legacy():
    config = ExperimentConfig.default()
    assert config.demand_mode == "legacy"
    assert config.demand_rate_per_tick == 0.0
    assert config.demand_task_weights == {}
    assert config.demand_segments == []
    assert config.demand_csv_path is None
    assert config.demand_events == []


def test_old_config_payload_remains_legacy():
    config = ExperimentConfig.from_dict(
        {
            "seed": 1,
            "num_robots": 2,
            "stop_mode": "fixed_ticks",
            "target_tasks": None,
            "max_ticks": 10,
        }
    )

    assert config.demand_mode == "legacy"
    assert config.demand_rate_per_tick == 0.0


def test_factory_creates_legacy_task_generator_by_default():
    config = make_config()
    sim = create_simulation_from_config(config)

    assert isinstance(sim._task_generator, TaskGenerator)
    assert not isinstance(sim._task_generator, DemandTaskGenerator)


def test_factory_creates_demand_task_generator_for_uniform():
    config = make_config(
        demand_mode="uniform",
        demand_rate_per_tick=1.0,
        demand_task_weights={"PICK": 1.0},
    )

    sim = create_simulation_from_config(config)

    assert isinstance(sim._task_generator, DemandTaskGenerator)


def test_factory_creates_demand_task_generator_for_inline_csv_events():
    config = make_config(
        demand_mode="csv_orders",
        demand_events=[
            {
                "tick": 2,
                "task_type": "PICK",
            }
        ],
    )

    sim = create_simulation_from_config(config)

    assert isinstance(sim._task_generator, DemandTaskGenerator)


def test_invalid_demand_mode_rejected():
    with pytest.raises(ValueError):
        make_config(demand_mode="not_a_mode")


def test_rate_schedule_requires_segments():
    with pytest.raises(ValueError):
        make_config(
            demand_mode="rate_schedule",
            demand_segments=[],
        )


def test_csv_orders_requires_source():
    with pytest.raises(ValueError):
        make_config(demand_mode="csv_orders")


def test_negative_demand_rate_rejected():
    with pytest.raises(ValueError):
        make_config(
            demand_mode="uniform",
            demand_rate_per_tick=-0.1,
        )