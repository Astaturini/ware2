from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BatteryConfig:
    """
    Battery model configuration.

    Battery is represented as energy units, with capacity defaulting to 100.
    Movement consumes one cell worth of energy. Loaded movement consumes more.
    """

    capacity: float = 100.0

    # Energy consumed per successful cell movement.
    empty_move_energy: float = 0.7
    loaded_move_energy: float = 1.0

    # Thresholds.
    critical_battery: float = 10.0
    opportunistic_charge_threshold: float = 30.0

    # Idle robots may opportunistically charge after being idle this many ticks.
    idle_ticks_before_opportunistic_charge: int = 10

    # Extra energy reserve required when judging task feasibility.
    safety_margin: float = 5.0

    # If battery reaches zero, the robot is down for at least this many ticks.
    empty_battery_recovery_ticks: int = 15

    def move_cost(self, loaded: bool) -> float:
        return self.loaded_move_energy if loaded else self.empty_move_energy

    def is_critical(self, battery: float) -> bool:
        return battery <= self.critical_battery

    def is_opportunistic_candidate(self, battery: float) -> bool:
        return battery < self.opportunistic_charge_threshold


@dataclass(frozen=True)
class ChargingConfig:
    """
    Charging station configuration.

    capacity is logical station capacity.
    Physical CHARGING cells can further constrain actual simultaneous charging.
    """

    capacity: int = 4
    charge_duration_ticks: int = 10


@dataclass(frozen=True)
class FailureConfig:
    """
    Basic robot failure/repair configuration.

    mtbf_ticks = mean ticks between failures.
    mtbf_ticks <= 0 disables random failures.
    """

    enabled: bool = False
    mtbf_ticks: float = 0.0
    mttr_ticks: int = 25
    seed: int | None = None

    # If True, failed/dead robots are moved/towed to a MAINTENANCE cell.
    # If False, they remain where they failed and become obstacles.
    relocate_to_maintenance: bool = True