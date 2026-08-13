from __future__ import annotations

import random
from dataclasses import dataclass, field

from .task import Task, TaskType
from .warehouse import CellType, Warehouse


@dataclass
class TaskGenerator:
    """Create a light stream of operational tasks over time.

    If seed is None, the generator keeps the old deterministic round-robin
    location selection.

    If seed is an int, location selection becomes random but reproducible.
    """

    warehouse: Warehouse
    start_tick: int = 2
    seed: int | None = None

    _next_task_number: int = 1
    _next_due: dict[TaskType, int] = field(default_factory=dict)
    _storage_locations: list[str] = field(default_factory=list)
    _pick_stations: list[str] = field(default_factory=list)
    _packing_locations: list[str] = field(default_factory=list)
    _shipping_locations: list[str] = field(default_factory=list)
    _receiving_locations: list[str] = field(default_factory=list)
    _staging_locations: list[str] = field(default_factory=list)

    _rng: random.Random | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)
        self._refresh_location_cache()
        self._next_due = {
            TaskType.PUTAWAY: self.start_tick,
            TaskType.PICK: self.start_tick + 2,
            TaskType.PACK: self.start_tick + 4,
            TaskType.SHIP: self.start_tick + 6,
        }

    def reset(self) -> None:
        self._next_task_number = 1
        self._rng = random.Random(self.seed)
        self._refresh_location_cache()
        self._next_due = {
            TaskType.PUTAWAY: self.start_tick,
            TaskType.PICK: self.start_tick + 2,
            TaskType.PACK: self.start_tick + 4,
            TaskType.SHIP: self.start_tick + 6,
        }

    def step(self, tick: int) -> list[Task]:
        generated: list[Task] = []

        for task_type, due_tick in self._next_due.items():
            if tick < due_tick:
                continue

            if tick == due_tick:
                generated.append(self._create_task(task_type, tick))
                self._next_due[task_type] = due_tick + self._interval_for(task_type)

        return generated

    def _refresh_location_cache(self) -> None:
        storage: list[str] = []
        pick_stations: list[str] = []
        packing: list[str] = []
        shipping: list[str] = []
        receiving: list[str] = []
        staging: list[str] = []

        for name, location in self.warehouse.locations.items():
            cell_type = self.warehouse.cell_type(*location.cell)

            if cell_type is CellType.SHELF:
                storage.append(name)
            elif cell_type is CellType.PICK_STATION:
                pick_stations.append(name)
            elif cell_type is CellType.PACKING:
                packing.append(name)
            elif cell_type is CellType.SHIPPING:
                shipping.append(name)
            elif cell_type in {CellType.RECEIVING, CellType.BUFFER}:
                receiving.append(name)
            elif cell_type is CellType.STAGING:
                staging.append(name)

        self._storage_locations = sorted(storage)
        self._pick_stations = sorted(pick_stations)
        self._packing_locations = sorted(packing)
        self._shipping_locations = sorted(shipping)
        self._receiving_locations = sorted(receiving)
        self._staging_locations = sorted(staging)

    def _create_task(self, task_type: TaskType, tick: int) -> Task:
        task_id = f"G{self._next_task_number:05d}"
        self._next_task_number += 1

        if task_type is TaskType.PUTAWAY:
            pickup = self._pick_one(self._receiving_locations, fallback="RECV")
            dropoff = self._pick_one(self._storage_locations)
            name = f"Inbound putaway {task_id}"

        elif task_type is TaskType.PICK:
            pickup = self._pick_one(self._storage_locations)
            dropoff = self._pick_one(self._pick_stations)
            name = f"Pick order {task_id}"

        elif task_type is TaskType.PACK:
            pickup = self._pick_one(self._pick_stations)
            dropoff = self._pick_one(self._packing_locations)
            name = f"Pack order {task_id}"

        else:
            if self._staging_locations:
                pickup = self._pick_one(self._staging_locations)
            else:
                pickup = self._pick_one(self._packing_locations)

            dropoff = self._pick_one(self._shipping_locations)
            name = f"Ship order {task_id}"

        return Task(
            id=task_id,
            name=name,
            pickup=pickup,
            dropoff=dropoff,
            task_type=task_type,
            priority=self._priority_for(task_type),
            created_at=tick,
        )

    def _pick_one(self, values: list[str], fallback: str | None = None) -> str:
        if values:
            # If a seed was provided, use reproducible random selection.
            # If no seed was provided, preserve the old deterministic behavior.
            if self.seed is not None:
                assert self._rng is not None
                return self._rng.choice(values)

            index = (self._next_task_number - 1) % len(values)
            return values[index]

        if fallback is not None:
            return fallback

        raise ValueError("Task generator has no suitable locations for this task type.")

    @staticmethod
    def _priority_for(task_type: TaskType) -> int:
        # Lower number = higher priority
        return {
            TaskType.PUTAWAY: 3,
            TaskType.PICK: 2,
            TaskType.PACK: 1,
            TaskType.SHIP: 0,
        }[task_type]

    @staticmethod
    def _interval_for(task_type: TaskType) -> int:
        return {
            TaskType.PUTAWAY: 8,
            TaskType.PICK: 10,
            TaskType.PACK: 12,
            TaskType.SHIP: 14,
        }[task_type]