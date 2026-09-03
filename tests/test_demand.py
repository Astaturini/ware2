import pytest

from decision.demand import (
    DemandConfig,
    DemandMode,
    RateSegment,
    build_demand_model,
    load_demand_events_from_csv,
)
from simulation.task import TaskType


def test_uniform_rate_one_emits_one_task_per_tick():
    config = DemandConfig(
        mode=DemandMode.UNIFORM,
        rate_per_tick=1.0,
        task_weights={"PICK": 1.0},
    )

    model = build_demand_model(config, seed=42)
    assert model is not None

    for tick in range(10):
        orders = model.orders_at_tick(tick)
        assert len(orders) == 1
        assert orders[0].tick == tick
        assert orders[0].task_type == TaskType.PICK


def test_uniform_rate_two_emits_two_tasks_per_tick():
    config = DemandConfig(
        mode=DemandMode.UNIFORM,
        rate_per_tick=2.0,
        task_weights={"SHIP": 1.0},
    )

    model = build_demand_model(config, seed=7)
    assert model is not None

    for tick in range(5):
        orders = model.orders_at_tick(tick)
        assert len(orders) == 2
        assert all(order.task_type == TaskType.SHIP for order in orders)


def test_uniform_zero_rate_emits_nothing():
    config = DemandConfig(
        mode=DemandMode.UNIFORM,
        rate_per_tick=0.0,
    )

    model = build_demand_model(config, seed=1)
    assert model is not None

    assert model.orders_at_tick(0) == []
    assert model.orders_at_tick(10) == []


def test_rate_schedule_emits_wave_then_stops():
    config = DemandConfig(
        mode=DemandMode.RATE_SCHEDULE,
        segments=[
            RateSegment(
                start_tick=0,
                end_tick=5,
                rate_per_tick=1.0,
                task_weights={"SHIP": 1.0},
            ),
            RateSegment(
                start_tick=5,
                end_tick=10,
                rate_per_tick=0.0,
            ),
        ],
    )

    model = build_demand_model(config, seed=99)
    assert model is not None

    counts = [len(model.orders_at_tick(tick)) for tick in range(10)]
    assert counts == [1, 1, 1, 1, 1, 0, 0, 0, 0, 0]


def test_rate_schedule_requires_segments():
    config = DemandConfig(mode=DemandMode.RATE_SCHEDULE)

    with pytest.raises(ValueError):
        config.validate()


def test_uniform_rejects_negative_rate():
    config = DemandConfig(
        mode=DemandMode.UNIFORM,
        rate_per_tick=-1.0,
    )

    with pytest.raises(ValueError):
        config.validate()


def test_uniform_rejects_unknown_task_type():
    config = DemandConfig(
        mode=DemandMode.UNIFORM,
        rate_per_tick=1.0,
        task_weights={"NOT_A_TASK_TYPE": 1.0},
    )

    with pytest.raises(ValueError):
        config.validate()


def test_csv_orders_emit_exact_ticks(tmp_path):
    csv_path = tmp_path / "orders.csv"
    csv_path.write_text(
        "tick,task_type,pickup,dropoff,priority\n"
        "5,PICK,A-01,PACK-1,1\n"
        "5,SHIP,A-02,SHIPPING,0\n"
        "7,PUTAWAY,RECEIVING,B-01,\n",
        encoding="utf-8",
    )

    events = load_demand_events_from_csv(csv_path)
    assert len(events) == 3
    assert events[0].tick == 5
    assert events[0].task_type == TaskType.PICK
    assert events[0].pickup == "A-01"
    assert events[0].dropoff == "PACK-1"
    assert events[0].priority == 1

    config = DemandConfig(
        mode=DemandMode.CSV_ORDERS,
        csv_path=str(csv_path),
    )

    model = build_demand_model(config, seed=1)
    assert model is not None

    assert model.orders_at_tick(4) == []
    assert len(model.orders_at_tick(5)) == 2
    assert model.orders_at_tick(6) == []
    assert len(model.orders_at_tick(7)) == 1


def test_csv_missing_required_column(tmp_path):
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("tick\n1\n", encoding="utf-8")

    with pytest.raises(ValueError):
        load_demand_events_from_csv(csv_path)


def test_csv_invalid_task_type(tmp_path):
    csv_path = tmp_path / "bad_task_type.csv"
    csv_path.write_text(
        "tick,task_type\n"
        "5,INVALID\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_demand_events_from_csv(csv_path)