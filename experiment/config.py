from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal


PATH_PLANNER_CHOICES = {
    "bfs",
    "astar",
    "weighted_astar",
}

SCHEDULER_CHOICES = {
    "baseline",
    "priority",
    "fifo",
    "total_cost",
    "auction",
}

CONFLICT_MANAGER_CHOICES = {
    "local_yield",
    "zone_locks",
    "priority_reservation",
}


@dataclass(frozen=True)
class ExperimentConfig:
    seed: int
    num_robots: int
    stop_mode: Literal["fixed_ticks", "workload"]
    target_tasks: int | None
    max_ticks: int

    display_name: str = ""
    tick_interval: float = 0.3
    fast_mode: bool = False

    blocked_replan_seconds: float = 0.7
    replan_cooldown_ticks: int = 7

    battery_capacity: float = 100.0
    empty_move_energy: float = 0.35
    loaded_move_energy: float = 0.5
    critical_battery: float = 15.0
    opportunistic_charge_threshold: float = 30.0
    idle_ticks_before_opportunistic_charge: int = 10
    battery_safety_margin: float = 5.0
    empty_battery_recovery_ticks: int = 15

    charger_capacity: int = 4
    charge_duration_ticks: int = 10

    failure_enabled: bool = False
    mtbf_ticks: float = 0.0
    mttr_ticks: int = 25
    relocate_to_maintenance: bool = True

    scheduler: str = "baseline"

    # v0.6 algorithm-selection fields.
    path_planner: str = "bfs"
    conflict_manager: str = "local_yield"

    def __post_init__(self) -> None:
        if self.seed is None:
            raise ValueError("seed is required for reproducible experiments.")

        if self.num_robots < 1:
            raise ValueError("num_robots must be at least 1.")

        if self.stop_mode not in {"fixed_ticks", "workload"}:
            raise ValueError(
                "stop_mode must be either 'fixed_ticks' or 'workload'."
            )

        if self.stop_mode == "workload":
            if self.target_tasks is None or self.target_tasks < 1:
                raise ValueError(
                    "target_tasks must be a positive integer in workload mode."
                )

        if self.max_ticks < 1:
            raise ValueError("max_ticks must be at least 1.")

        if self.tick_interval <= 0:
            raise ValueError("tick_interval must be positive.")

        if self.blocked_replan_seconds < 0:
            raise ValueError("blocked_replan_seconds must be >= 0.")

        if self.replan_cooldown_ticks < 1:
            raise ValueError("replan_cooldown_ticks must be at least 1.")

        if self.battery_capacity <= 0:
            raise ValueError("battery_capacity must be positive.")

        if self.empty_move_energy < 0 or self.loaded_move_energy < 0:
            raise ValueError("move energy values must be >= 0.")

        if self.charger_capacity < 1:
            raise ValueError("charger_capacity must be at least 1.")

        if self.charge_duration_ticks < 1:
            raise ValueError("charge_duration_ticks must be at least 1.")

        if self.mtbf_ticks < 0:
            raise ValueError("mtbf_ticks must be >= 0.")

        if self.mttr_ticks < 1:
            raise ValueError("mttr_ticks must be at least 1.")

        if self.failure_enabled and self.mtbf_ticks <= 0:
            raise ValueError(
                "mtbf_ticks must be > 0 when failure_enabled is true."
            )

        if self.path_planner not in PATH_PLANNER_CHOICES:
            raise ValueError(
                f"path_planner must be one of {sorted(PATH_PLANNER_CHOICES)}."
            )

        if self.scheduler not in SCHEDULER_CHOICES:
            raise ValueError(
                f"scheduler must be one of {sorted(SCHEDULER_CHOICES)}."
            )

        if self.conflict_manager not in CONFLICT_MANAGER_CHOICES:
            raise ValueError(
                f"conflict_manager must be one of {sorted(CONFLICT_MANAGER_CHOICES)}."
            )

    @classmethod
    def default(cls) -> "ExperimentConfig":
        return cls(
            seed=42,
            num_robots=6,
            display_name="",
            stop_mode="workload",
            target_tasks=500,
            max_ticks=100_000,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, directory: str | Path) -> None:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        with open(directory / "config.json", "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, directory: str | Path) -> "ExperimentConfig":
        with open(
            Path(directory) / "config.json", "r", encoding="utf-8"
        ) as f:
            return cls.from_dict(json.load(f))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExperimentConfig":
        base = cls.default().to_dict()
        known = set(cls.__dataclass_fields__.keys())

        for key, value in (data or {}).items():
            if key in known:
                base[key] = value

        return cls(**base)