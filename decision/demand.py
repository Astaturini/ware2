from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from simulation.task import TaskType
from simulation.task_generator import TaskGenerator


ALLOWED_DEMAND_TASK_TYPES = (
    TaskType.PUTAWAY,
    TaskType.PICK,
    TaskType.PACK,
    TaskType.SHIP,
)


class DemandMode(str, Enum):
    LEGACY = "legacy"
    UNIFORM = "uniform"
    RATE_SCHEDULE = "rate_schedule"
    CSV_ORDERS = "csv_orders"


@dataclass(frozen=True)
class DemandEvent:
    tick: int
    task_type: TaskType
    pickup: str | None = None
    dropoff: str | None = None
    priority: int | None = None


@dataclass(frozen=True)
class RateSegment:
    """
    Half-open interval: [start_tick, end_tick).
    If end_tick is None, the segment continues indefinitely.
    """

    start_tick: int
    end_tick: int | None = None
    rate_per_tick: float = 0.0
    task_weights: Mapping[str, float] | None = None


@dataclass
class DemandConfig:
    mode: DemandMode = DemandMode.LEGACY

    # Used by UNIFORM mode.
    rate_per_tick: float = 0.0
    task_weights: dict[str, float] = field(default_factory=dict)

    # Used by RATE_SCHEDULE mode.
    segments: list[RateSegment] = field(default_factory=list)

    # Used by CSV_ORDERS mode.
    csv_path: str | None = None
    events: list[DemandEvent] = field(default_factory=list)

    def validate(self) -> None:
        if not isinstance(self.mode, DemandMode):
            raise ValueError("mode must be a DemandMode")

        if self.mode == DemandMode.LEGACY:
            return

        if self.mode == DemandMode.UNIFORM:
            if not math.isfinite(self.rate_per_tick) or self.rate_per_tick < 0:
                raise ValueError("rate_per_tick must be finite and >= 0")
            _normalize_weight_pairs(self.task_weights)
            return

        if self.mode == DemandMode.RATE_SCHEDULE:
            if not self.segments:
                raise ValueError("rate_schedule requires at least one segment")

            for segment in self.segments:
                if segment.start_tick < 0:
                    raise ValueError("segment.start_tick must be >= 0")

                if segment.end_tick is not None and segment.end_tick <= segment.start_tick:
                    raise ValueError("segment.end_tick must be greater than segment.start_tick")

                if not math.isfinite(segment.rate_per_tick) or segment.rate_per_tick < 0:
                    raise ValueError("segment.rate_per_tick must be finite and >= 0")

                _normalize_weight_pairs(segment.task_weights)
            return

        if self.mode == DemandMode.CSV_ORDERS:
            if not self.events and not self.csv_path:
                raise ValueError("csv_orders requires either events or csv_path")

            for event in self.events:
                if event.tick < 0:
                    raise ValueError("event.tick must be >= 0")
                _normalize_task_type(event.task_type)
            return

        raise ValueError(f"Unsupported demand mode: {self.mode}")

    def resolved_events(self) -> list[DemandEvent]:
        if self.events:
            events = list(self.events)
        elif self.csv_path:
            events = load_demand_events_from_csv(self.csv_path)
        else:
            events = []

        events.sort(key=lambda event: event.tick)
        return events

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DemandConfig":
        if not isinstance(data, Mapping):
            raise TypeError("data must be a mapping")

        mode_raw = data.get("mode", DemandMode.LEGACY.value)
        if isinstance(mode_raw, DemandMode):
            mode = mode_raw
        else:
            mode = DemandMode(str(mode_raw).strip().lower())

        rate_per_tick = float(data.get("rate_per_tick", 0.0) or 0.0)
        task_weights = dict(data.get("task_weights") or {})

        segments: list[RateSegment] = []
        for raw_segment in data.get("segments", []) or []:
            if isinstance(raw_segment, RateSegment):
                segments.append(raw_segment)
            else:
                end_tick = raw_segment.get("end_tick", None)
                segments.append(
                    RateSegment(
                        start_tick=int(raw_segment.get("start_tick", 0)),
                        end_tick=None if end_tick is None else int(end_tick),
                        rate_per_tick=float(raw_segment.get("rate_per_tick", 0.0) or 0.0),
                        task_weights=raw_segment.get("task_weights", None),
                    )
                )

        events: list[DemandEvent] = []
        for raw_event in data.get("events", []) or []:
            if isinstance(raw_event, DemandEvent):
                events.append(raw_event)
            else:
                events.append(_event_from_dict(raw_event))

        config = cls(
            mode=mode,
            rate_per_tick=rate_per_tick,
            task_weights=task_weights,
            segments=segments,
            csv_path=_optional_str(data.get("csv_path")),
            events=events,
        )
        config.validate()
        return config

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "rate_per_tick": self.rate_per_tick,
            "task_weights": dict(self.task_weights),
            "segments": [
                {
                    "start_tick": segment.start_tick,
                    "end_tick": segment.end_tick,
                    "rate_per_tick": segment.rate_per_tick,
                    "task_weights": dict(segment.task_weights) if segment.task_weights else None,
                }
                for segment in self.segments
            ],
            "csv_path": self.csv_path,
            "events": [
                {
                    "tick": event.tick,
                    "task_type": event.task_type.name,
                    "pickup": event.pickup,
                    "dropoff": event.dropoff,
                    "priority": event.priority,
                }
                for event in self.events
            ],
        }


class DemandModel:
    def reset(self) -> None:
        raise NotImplementedError

    def orders_at_tick(self, tick: int) -> list[DemandEvent]:
        raise NotImplementedError


class UniformDemandModel(DemandModel):
    def __init__(
        self,
        rate_per_tick: float,
        task_weights: Mapping[str, float] | None,
        seed: int | None,
    ):
        if not math.isfinite(rate_per_tick) or rate_per_tick < 0:
            raise ValueError("rate_per_tick must be finite and >= 0")

        self._rate = float(rate_per_tick)
        pairs = _normalize_weight_pairs(task_weights)
        self._types = [task_type for task_type, _ in pairs]
        self._weights = [weight for _, weight in pairs]
        self._seed = seed
        self._rng = random.Random(seed if seed is not None else 0)

    def reset(self) -> None:
        self._rng = random.Random(self._seed if self._seed is not None else 0)

    def orders_at_tick(self, tick: int) -> list[DemandEvent]:
        if tick < 0 or self._rate <= 0:
            return []

        count = _emit_count_for_rate(self._rng, self._rate)
        return [
            DemandEvent(
                tick=tick,
                task_type=_choose_task_type(self._rng, self._types, self._weights),
            )
            for _ in range(count)
        ]


class RateScheduleDemandModel(DemandModel):
    def __init__(self, segments: list[RateSegment], seed: int | None):
        if not segments:
            raise ValueError("rate_schedule requires at least one segment")

        self._segments: list[tuple[int, int | None, float, list[TaskType], list[float]]] = []

        for segment in segments:
            if segment.start_tick < 0:
                raise ValueError("segment.start_tick must be >= 0")

            if segment.end_tick is not None and segment.end_tick <= segment.start_tick:
                raise ValueError("segment.end_tick must be greater than segment.start_tick")

            if not math.isfinite(segment.rate_per_tick) or segment.rate_per_tick < 0:
                raise ValueError("segment.rate_per_tick must be finite and >= 0")

            pairs = _normalize_weight_pairs(segment.task_weights)
            types = [task_type for task_type, _ in pairs]
            weights = [weight for _, weight in pairs]

            self._segments.append(
                (
                    segment.start_tick,
                    segment.end_tick,
                    float(segment.rate_per_tick),
                    types,
                    weights,
                )
            )

        self._seed = seed
        self._rng = random.Random(seed if seed is not None else 0)

    def reset(self) -> None:
        self._rng = random.Random(self._seed if self._seed is not None else 0)

    def orders_at_tick(self, tick: int) -> list[DemandEvent]:
        if tick < 0:
            return []

        orders: list[DemandEvent] = []

        for start_tick, end_tick, rate, types, weights in self._segments:
            if tick < start_tick:
                continue

            if end_tick is not None and tick >= end_tick:
                continue

            if rate <= 0:
                continue

            count = _emit_count_for_rate(self._rng, rate)
            for _ in range(count):
                orders.append(
                    DemandEvent(
                        tick=tick,
                        task_type=_choose_task_type(self._rng, types, weights),
                    )
                )

        return orders


class CsvDemandModel(DemandModel):
    def __init__(self, events: list[DemandEvent]):
        if not events:
            raise ValueError("csv_orders requires at least one demand event")

        self._events = sorted(events, key=lambda event: event.tick)
        self._index = 0

    def reset(self) -> None:
        self._index = 0

    def orders_at_tick(self, tick: int) -> list[DemandEvent]:
        if tick < 0:
            return []

        orders: list[DemandEvent] = []

        while self._index < len(self._events) and self._events[self._index].tick <= tick:
            event = self._events[self._index]
            self._index += 1

            # Emit only exact-tick events. Missed events are skipped, not emitted late.
            if event.tick == tick:
                orders.append(event)

        return orders


class DemandTaskGenerator(TaskGenerator):
    """
    Demand-aware task generator.

    mode="legacy" preserves existing TaskGenerator behavior exactly.
    Other modes replace the synthetic task stream with a demand profile.
    """

    def __init__(
        self,
        warehouse: Any,
        demand_config: DemandConfig | Mapping[str, Any],
        start_tick: int = 2,
        seed: int | None = None,
    ):
        if isinstance(demand_config, Mapping):
            demand_config = DemandConfig.from_dict(demand_config)

        super().__init__(warehouse, start_tick=start_tick, seed=seed)

        self.demand_config = demand_config
        self._demand_model = build_demand_model(demand_config, seed=seed)

    def reset(self) -> None:
        super().reset()
        if self._demand_model is not None:
            self._demand_model.reset()

    def step(self, tick: int) -> list[Any]:
        if self._demand_model is None:
            return super().step(tick)

        if tick < self.start_tick:
            return []

        orders = self._demand_model.orders_at_tick(tick)
        tasks = []

        for order in orders:
            task = self._create_demand_task(order, tick)
            if task is not None:
                tasks.append(task)

        return tasks

    def _create_demand_task(self, order: DemandEvent, tick: int) -> Any:
        # Reuse the existing private task factory to preserve ID/name/priority behavior.
        task = self._create_task(order.task_type, tick)

        if order.pickup is not None:
            self._resolve_location(order.pickup, tick, "pickup")
            task.pickup = order.pickup
        else:
            self._resolve_location(task.pickup, tick, "pickup")

        if order.dropoff is not None:
            self._resolve_location(order.dropoff, tick, "dropoff")
            task.dropoff = order.dropoff
        else:
            self._resolve_location(task.dropoff, tick, "dropoff")

        if order.priority is not None:
            task.priority = int(order.priority)

        return task

    def _resolve_location(self, name: str, tick: int, role: str) -> None:
        try:
            self.warehouse.resolve(name)
        except KeyError as exc:
            raise ValueError(
                f"Demand event at tick={tick} has unknown {role} location: {name!r}"
            ) from exc


def build_demand_model(
    config: DemandConfig | Mapping[str, Any],
    seed: int | None = None,
) -> DemandModel | None:
    if isinstance(config, Mapping):
        config = DemandConfig.from_dict(config)

    config.validate()

    if config.mode == DemandMode.LEGACY:
        return None

    if config.mode == DemandMode.UNIFORM:
        return UniformDemandModel(
            rate_per_tick=config.rate_per_tick,
            task_weights=config.task_weights,
            seed=seed,
        )

    if config.mode == DemandMode.RATE_SCHEDULE:
        return RateScheduleDemandModel(config.segments, seed=seed)

    if config.mode == DemandMode.CSV_ORDERS:
        events = config.resolved_events()
        if not events:
            raise ValueError("csv_orders demand profile contains no events")
        return CsvDemandModel(events)

    raise ValueError(f"Unsupported demand mode: {config.mode}")


def install_demand(
    sim: Any,
    demand_config: DemandConfig | Mapping[str, Any] | None,
    seed: int | None = None,
) -> Any:
    """
    Temporary integration shim.

    Replaces Simulation._task_generator with a DemandTaskGenerator.
    Proper integration should happen in experiment/factory.py and
    ExperimentConfig so demand profiles are persisted in config.json.
    """

    if demand_config is None:
        return sim

    if isinstance(demand_config, Mapping):
        demand_config = DemandConfig.from_dict(demand_config)

    if demand_config.mode == DemandMode.LEGACY:
        return sim

    warehouse = getattr(sim, "_warehouse", None)
    old_generator = getattr(sim, "_task_generator", None)

    if warehouse is None or old_generator is None:
        raise RuntimeError(
            "install_demand requires access to Simulation._warehouse and "
            "Simulation._task_generator. Proper integration should be done "
            "through experiment/factory.py and ExperimentConfig."
        )

    start_tick = getattr(old_generator, "start_tick", 2)
    if seed is None:
        seed = getattr(old_generator, "seed", None)

    generator = DemandTaskGenerator(
        warehouse=warehouse,
        demand_config=demand_config,
        start_tick=start_tick,
        seed=seed,
    )

    sim._task_generator = generator

    # Best-effort support if a public alias exists.
    if hasattr(sim, "task_generator"):
        try:
            sim.task_generator = generator
        except AttributeError:
            pass

    return sim


def load_demand_events_from_csv(path: str | Path) -> list[DemandEvent]:
    csv_path = Path(path)

    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)

        if not reader.fieldnames:
            raise ValueError(f"CSV demand file is empty: {csv_path}")

        fieldnames = {name.strip() for name in reader.fieldnames if name}
        missing = {"tick", "task_type"} - fieldnames
        if missing:
            raise ValueError(
                f"CSV demand file {csv_path} is missing required columns: {sorted(missing)}"
            )

        events: list[DemandEvent] = []

        for line_number, row in enumerate(reader, start=2):
            clean_row = {
                (key.strip() if key else key): (value.strip() if isinstance(value, str) else value)
                for key, value in row.items()
            }

            try:
                tick = int(clean_row["tick"])
            except Exception as exc:
                raise ValueError(f"Invalid tick on line {line_number}: {clean_row.get('tick')!r}") from exc

            if tick < 0:
                raise ValueError(f"tick must be >= 0 on line {line_number}")

            task_type = _normalize_task_type(clean_row["task_type"])
            pickup = _optional_str(clean_row.get("pickup"))
            dropoff = _optional_str(clean_row.get("dropoff"))
            priority_raw = _optional_str(clean_row.get("priority"))

            priority: int | None
            if priority_raw is None:
                priority = None
            else:
                try:
                    priority = int(priority_raw)
                except Exception as exc:
                    raise ValueError(
                        f"Invalid priority on line {line_number}: {priority_raw!r}"
                    ) from exc

            events.append(
                DemandEvent(
                    tick=tick,
                    task_type=task_type,
                    pickup=pickup,
                    dropoff=dropoff,
                    priority=priority,
                )
            )

    events.sort(key=lambda event: event.tick)
    return events


def _event_from_dict(raw: Mapping[str, Any]) -> DemandEvent:
    if not isinstance(raw, Mapping):
        raise TypeError("event must be a mapping")

    tick = int(raw.get("tick")) # pyright: ignore[reportArgumentType]
    task_type = _normalize_task_type(raw.get("task_type"))
    pickup = _optional_str(raw.get("pickup"))
    dropoff = _optional_str(raw.get("dropoff"))

    priority_raw = raw.get("priority")
    priority = None if priority_raw is None or str(priority_raw).strip() == "" else int(priority_raw)

    if tick < 0:
        raise ValueError("event.tick must be >= 0")

    return DemandEvent(
        tick=tick,
        task_type=task_type,
        pickup=pickup,
        dropoff=dropoff,
        priority=priority,
    )


def _normalize_task_type(value: Any) -> TaskType:
    if isinstance(value, TaskType):
        task_type = value
    else:
        try:
            task_type = TaskType[str(value).strip().upper()]
        except Exception as exc:
            raise ValueError(f"Unknown task type: {value!r}") from exc

    if task_type not in ALLOWED_DEMAND_TASK_TYPES:
        allowed = ", ".join(task_type.name for task_type in ALLOWED_DEMAND_TASK_TYPES)
        raise ValueError(f"Task type {task_type.name} is not allowed in demand profiles. Allowed: {allowed}")

    return task_type


def _normalize_weight_pairs(
    weights: Mapping[str, float] | None,
) -> list[tuple[TaskType, float]]:
    if not weights:
        pairs = [(task_type, 1.0) for task_type in ALLOWED_DEMAND_TASK_TYPES]
    else:
        pairs = []
        for raw_type, raw_weight in weights.items():
            task_type = _normalize_task_type(raw_type)
            weight = float(raw_weight)

            if not math.isfinite(weight) or weight < 0:
                raise ValueError(f"Task weight for {raw_type!r} must be finite and >= 0")

            pairs.append((task_type, weight))

    total = sum(weight for _, weight in pairs)
    if not pairs or total <= 0:
        raise ValueError("task_weights must contain at least one positive weight")

    return pairs


def _choose_task_type(
    rng: random.Random,
    types: list[TaskType],
    weights: list[float],
) -> TaskType:
    return rng.choices(types, weights=weights, k=1)[0]


def _emit_count_for_rate(rng: random.Random, rate: float) -> int:
    if rate <= 0:
        return 0

    base = int(math.floor(rate))
    fractional = rate - base

    if rng.random() < fractional:
        base += 1

    return base


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    return text or None