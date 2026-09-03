from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostConfig:
    """
    Run-level cost configuration.

    This is intentionally OpEx-focused. CapEx amortization should be handled
    explicitly by the caller or by a later financial layer.
    """

    robot_opex_per_hour: float = 0.0
    charger_infra_cost_per_hour: float = 0.0
    downtime_cost_per_hour: float = 0.0

    # If None, SLA compliance and SLA penalty are not evaluated.
    sla_target_ticks: int | None = None
    sla_penalty_per_late_tick: float = 0.0

    currency: str = "USD"

    def __post_init__(self) -> None:
        if self.robot_opex_per_hour < 0:
            raise ValueError("robot_opex_per_hour must be >= 0")

        if self.charger_infra_cost_per_hour < 0:
            raise ValueError("charger_infra_cost_per_hour must be >= 0")

        if self.downtime_cost_per_hour < 0:
            raise ValueError("downtime_cost_per_hour must be >= 0")

        if self.sla_penalty_per_late_tick < 0:
            raise ValueError("sla_penalty_per_late_tick must be >= 0")

        if self.sla_target_ticks is not None and self.sla_target_ticks < 0:
            raise ValueError("sla_target_ticks must be >= 0 when provided")

        if not isinstance(self.currency, str) or not self.currency.strip():
            raise ValueError("currency must be a non-empty string") 