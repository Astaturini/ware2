import pandas as pd
import pytest

from decision import kpis
from decision.cost import CostConfig
from decision.kpis import compute_cost_kpis


class RunStub:
    def __init__(self, config, summary, events):
        self.config = config
        self.summary = summary
        self.events = events


def test_cost_kpis_basic(monkeypatch):
    events = pd.DataFrame(
        {
            "run_id": ["x", "x", "x", "x"],
            "tick": [0, 0, 50, 150],
            "event_type": [
                "task_created",
                "task_created",
                "task_completed",
                "task_completed",
            ],
            "robot_id": ["", "", "R1", "R2"],
            "task_id": ["T1", "T2", "T1", "T2"],
            "details": ["", "", "", ""],
        }
    )

    lifecycle = pd.DataFrame(
        {
            "task_id": ["T1", "T2"],
            "created_tick": [0.0, 0.0],
            "completed_tick": [50.0, 150.0],
            "cycle_time": [50.0, 150.0],
        }
    )

    monkeypatch.setattr(kpis, "task_lifecycle_from_events", lambda _events: lifecycle)

    run = RunStub(
        config={
            "tick_interval": 1.0,
            "num_robots": 3,
            "charger_capacity": 2,
        },
        summary={
            "simulation_seconds": 3600.0,
            "robot_count": 3,
            "tasks_completed": 2,
            "failure_downtime_ticks": 1800,
        },
        events=events,
    )

    cost_config = CostConfig(
        robot_opex_per_hour=10.0,
        charger_infra_cost_per_hour=5.0,
        downtime_cost_per_hour=60.0,
        sla_target_ticks=100,
        sla_penalty_per_late_tick=1.0,
        currency="USD",
    )

    result = compute_cost_kpis(run, cost_config)

    # Robot cost: 3 robots * 1 hour * 10 = 30
    # Charger cost: 2 chargers * 1 hour * 5 = 10
    # Downtime cost: 1800 ticks * 1s = 1800s = 0.5h * 60 = 30
    # SLA penalty: task T2 is 50 ticks late * 1 = 50
    # Total = 120
    assert result.total_operating_cost == pytest.approx(120.0)

    # Cost per task: 120 / 2 completed tasks = 60
    assert result.cost_per_task == pytest.approx(60.0)

    # One out of two evaluated tasks is within SLA.
    assert result.sla_compliance_rate == pytest.approx(0.5)

    assert result.completed_tasks == 2
    assert result.sla_evaluated_tasks == 2
    assert result.late_tasks == 1

    assert result.cost_breakdown["robot_operating_cost"] == pytest.approx(30.0)
    assert result.cost_breakdown["charger_infrastructure_cost"] == pytest.approx(10.0)
    assert result.cost_breakdown["downtime_penalty_cost"] == pytest.approx(30.0)
    assert result.cost_breakdown["sla_penalty_cost"] == pytest.approx(50.0)


def test_zero_completed_tasks_returns_none_cost_per_task():
    run = RunStub(
        config={
            "tick_interval": 1.0,
            "num_robots": 1,
            "charger_capacity": 0,
        },
        summary={
            "simulation_seconds": 3600.0,
            "robot_count": 1,
            "tasks_completed": 0,
            "failure_downtime_ticks": 0,
        },
        events=pd.DataFrame(),
    )

    cost_config = CostConfig(
        robot_opex_per_hour=10.0,
        charger_infra_cost_per_hour=0.0,
        downtime_cost_per_hour=0.0,
        sla_target_ticks=100,
        sla_penalty_per_late_tick=1.0,
    )

    result = compute_cost_kpis(run, cost_config)

    assert result.total_operating_cost == pytest.approx(10.0)
    assert result.cost_per_task is None
    assert result.sla_compliance_rate is None
    assert result.completed_tasks == 0
    assert result.sla_evaluated_tasks == 0
    assert result.late_tasks == 0


def test_missing_summary_completed_uses_lifecycle(monkeypatch):
    events = pd.DataFrame({"tick": [0]})

    lifecycle = pd.DataFrame(
        {
            "task_id": ["T1"],
            "cycle_time": [10.0],
        }
    )

    monkeypatch.setattr(kpis, "task_lifecycle_from_events", lambda _events: lifecycle)

    run = RunStub(
        config={
            "tick_interval": 1.0,
            "num_robots": 0,
            "charger_capacity": 0,
        },
        summary={
            "simulation_seconds": 0.0,
        },
        events=events,
    )

    cost_config = CostConfig(
        robot_opex_per_hour=0.0,
        sla_target_ticks=5,
        sla_penalty_per_late_tick=0.0,
    )

    result = compute_cost_kpis(run, cost_config)

    assert result.completed_tasks == 1
    assert result.sla_evaluated_tasks == 1
    assert result.late_tasks == 1
    assert result.sla_compliance_rate == pytest.approx(0.0)


def test_no_sla_target_returns_none_sla_rate(monkeypatch):
    events = pd.DataFrame({"tick": [0]})

    lifecycle = pd.DataFrame(
        {
            "task_id": ["T1"],
            "cycle_time": [10.0],
        }
    )

    monkeypatch.setattr(kpis, "task_lifecycle_from_events", lambda _events: lifecycle)

    run = RunStub(
        config={},
        summary={
            "simulation_seconds": 0.0,
            "tasks_completed": 1,
        },
        events=events,
    )

    cost_config = CostConfig(
        robot_opex_per_hour=0.0,
        sla_target_ticks=None,
    )

    result = compute_cost_kpis(run, cost_config)

    assert result.sla_compliance_rate is None
    assert result.sla_evaluated_tasks == 1
    assert result.late_tasks == 0


def test_cost_config_rejects_negative_values():
    with pytest.raises(ValueError):
        CostConfig(robot_opex_per_hour=-1.0)

    with pytest.raises(ValueError):
        CostConfig(sla_target_ticks=-10)

    with pytest.raises(ValueError):
        CostConfig(sla_penalty_per_late_tick=-0.1)

    with pytest.raises(ValueError):
        CostConfig(currency="")