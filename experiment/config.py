from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


PATH_PLANNER_CHOICES = {
    "bfs",
    "astar",
    "weighted_astar",
}

CONFLICT_MANAGER_CHOICES = {
    "local_yield",
    "zone_locks",
    "priority_reservation",
}

DEMAND_MODE_CHOICES = {
    "legacy",
    "uniform",
    "rate_schedule",
    "csv_orders",
}

LAYOUT_PRESET_CHOICES = {
    "default",
    "high_density",
    "one_way_aisles",
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
    path_planner: str = "bfs"
    conflict_manager: str = "local_yield"

    # v0.7.1 demand layer.
    # Defaults preserve v0.6.0 TaskGenerator behavior.
    demand_mode: str = "legacy"
    demand_rate_per_tick: float = 0.0
    demand_task_weights: dict[str, float] = field(default_factory=dict)
    demand_segments: list[dict[str, Any]] = field(default_factory=list)
    demand_csv_path: str | None = None
    demand_events: list[dict[str, Any]] = field(default_factory=list)

    # v0.7.1 layout layer.
    # Defaults preserve v0.6.0 build_warehouse() behavior.
    layout_preset: str = "default"
    layout_file: str | None = None

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

        if self.conflict_manager not in CONFLICT_MANAGER_CHOICES:
            raise ValueError(
                f"conflict_manager must be one of {sorted(CONFLICT_MANAGER_CHOICES)}."
            )

        _validate_demand_config(self)
        _validate_layout_config(self)

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
        with open(Path(directory) / "config.json", "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExperimentConfig":
        base = cls.default().to_dict()
        known = set(cls.__dataclass_fields__.keys())

        for key, value in (data or {}).items():
            if key in known:
                base[key] = value

        # Normalize nullable mutable fields coming from JSON payloads.
        base["demand_task_weights"] = dict(base.get("demand_task_weights") or {})
        base["demand_segments"] = list(base.get("demand_segments") or [])
        base["demand_events"] = list(base.get("demand_events") or [])

        if base.get("demand_csv_path") == "":
            base["demand_csv_path"] = None

        if base.get("layout_file") == "":
            base["layout_file"] = None

        return cls(**base)


def _validate_demand_config(config: ExperimentConfig) -> None:
    if config.demand_mode not in DEMAND_MODE_CHOICES:
        raise ValueError(
            f"demand_mode must be one of {sorted(DEMAND_MODE_CHOICES)}."
        )

    if not math.isfinite(config.demand_rate_per_tick):
        raise ValueError("demand_rate_per_tick must be finite.")

    if config.demand_rate_per_tick < 0:
        raise ValueError("demand_rate_per_tick must be >= 0.")

    _validate_demand_weights(config.demand_task_weights, "demand_task_weights")

    if not isinstance(config.demand_segments, list):
        raise ValueError("demand_segments must be a list.")

    for index, segment in enumerate(config.demand_segments):
        context = f"demand_segments[{index}]"

        if not isinstance(segment, Mapping):
            raise ValueError(f"{context} must be an object.")

        start_tick = _as_int(segment.get("start_tick", 0), f"{context}.start_tick")
        if start_tick < 0:
            raise ValueError(f"{context}.start_tick must be >= 0.")

        end_raw = segment.get("end_tick", None)
        if end_raw is not None:
            end_tick = _as_int(end_raw, f"{context}.end_tick")
            if end_tick <= start_tick:
                raise ValueError(
                    f"{context}.end_tick must be greater than {context}.start_tick."
                )

        rate_raw = segment.get("rate_per_tick", 0.0)
        try:
            rate = float(rate_raw)
        except Exception as exc:
            raise ValueError(f"{context}.rate_per_tick must be numeric.") from exc

        if not math.isfinite(rate) or rate < 0:
            raise ValueError(f"{context}.rate_per_tick must be finite and >= 0.")

        if segment.get("task_weights", None) is not None:
            _validate_demand_weights(
                segment.get("task_weights"),
                f"{context}.task_weights",
            )

    if not isinstance(config.demand_events, list):
        raise ValueError("demand_events must be a list.")

    for index, event in enumerate(config.demand_events):
        context = f"demand_events[{index}]"

        if not isinstance(event, Mapping):
            raise ValueError(f"{context} must be an object.")

        tick = _as_int(event.get("tick"), f"{context}.tick")
        if tick < 0:
            raise ValueError(f"{context}.tick must be >= 0.")

        task_type = event.get("task_type")
        if not isinstance(task_type, str) or not task_type.strip():
            raise ValueError(f"{context}.task_type must be a non-empty string.")

        priority_raw = event.get("priority", None)
        if priority_raw is not None and str(priority_raw).strip() != "":
            _as_int(priority_raw, f"{context}.priority")

    if config.demand_csv_path is not None:
        if not isinstance(config.demand_csv_path, str) or not config.demand_csv_path.strip():
            raise ValueError("demand_csv_path must be a non-empty string when provided.")

    if config.demand_mode == "rate_schedule" and not config.demand_segments:
        raise ValueError("rate_schedule demand mode requires demand_segments.")

    if config.demand_mode == "csv_orders":
        if not config.demand_csv_path and not config.demand_events:
            raise ValueError(
                "csv_orders demand mode requires demand_csv_path or demand_events."
            )


def _validate_layout_config(config: ExperimentConfig) -> None:
    if config.layout_preset not in LAYOUT_PRESET_CHOICES:
        raise ValueError(
            f"layout_preset must be one of {sorted(LAYOUT_PRESET_CHOICES)}."
        )

    if config.layout_file is not None:
        if not isinstance(config.layout_file, str) or not config.layout_file.strip():
            raise ValueError("layout_file must be a non-empty string when provided.")


def _validate_demand_weights(weights: Any, context: str) -> None:
    if weights is None:
        return

    if not isinstance(weights, Mapping):
        raise ValueError(f"{context} must be a mapping.")

    for key, value in weights.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{context} contains an invalid task type key.")

        try:
            weight = float(value)
        except Exception as exc:
            raise ValueError(f"{context}[{key!r}] must be numeric.") from exc

        if not math.isfinite(weight) or weight < 0:
            raise ValueError(f"{context}[{key!r}] must be finite and >= 0.")


def _as_int(value: Any, context: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{context} must be an integer.")

    try:
        if isinstance(value, float):
            if not math.isfinite(value) or not value.is_integer():
                raise ValueError(f"{context} must be an integer.")

        return int(value)
    except Exception as exc:
        raise ValueError(f"{context} must be an integer.") from exc