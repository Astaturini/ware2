from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RobotStatus(str, Enum):
    IDLE = "Idle"
    MOVING = "Moving"


class RobotMode(str, Enum):
    """
    v0.4 operational state machine.

    RobotStatus remains Idle/Moving for backward compatibility.
    RobotMode carries richer behavior state.
    """

    IDLE = "Idle"
    MOVING = "Moving"
    TO_CHARGER = "To charger"
    WAITING_FOR_CHARGER = "Waiting for charger"
    CHARGING = "Charging"
    FAILED = "Failed"
    REPAIRING = "Repairing"


@dataclass
class Robot:
    """A simple robot that follows a path one cell at a time."""

    id: str
    x: int
    y: int
    color: str
    status: RobotStatus = RobotStatus.IDLE
    path: list[tuple[int, int]] = field(default_factory=list)
    current_task_id: str | None = None

    # Current final destination for the current task phase.
    route_goal: tuple[int, int] | None = None

    # Traffic / conflict-resolution state.
    blocked_ticks: int = 0
    replanning: bool = False
    yielding_to: str | None = None
    replan_cooldown: int = 0

    # Cells previously visited by this robot, used for backtracking.
    travel_history: list[tuple[int, int]] = field(default_factory=list)

    # Internal only. Not exposed to the UI.
    # True when the robot is executing a temporary yield/backtrack path
    # instead of its normal task route.
    temporary_path: bool = False

    # ------------------------------------------------------------------
    # v0.4 battery / charging / failure state
    # ------------------------------------------------------------------
    battery: float = 100.0
    mode: RobotMode = RobotMode.IDLE

    # Used for opportunistic charging.
    idle_ticks: int = 0

    # Waiting-for-charger tracking.
    charger_wait_ticks: int = 0

    # Robot may remember a task it interrupted.
    interrupted_task_id: str | None = None

    # Target charging cell while traveling to charge.
    charge_target: tuple[int, int] | None = None

    # Used for linear charging display.
    charge_start_battery: float | None = None

    # Failure / repair.
    repair_remaining_ticks: int = 0

    @property
    def current_target(self) -> tuple[int, int] | None:
        """Return the next cell the robot will move into, if any."""
        return self.path[0] if self.path else None

    def set_path(self, path: list[tuple[int, int]]) -> None:
        """Assign a normal task path. The path should exclude the current cell."""
        self.path = list(path)
        self.temporary_path = False
        self.status = RobotStatus.MOVING if self.path else RobotStatus.IDLE

    def set_temporary_path(self, path: list[tuple[int, int]]) -> None:
        """Assign a temporary yield/backtrack path."""
        self.path = list(path)
        self.temporary_path = True
        self.status = RobotStatus.MOVING if self.path else RobotStatus.IDLE

    def advance(self) -> bool:
        """Move one cell along the current path.

        Returns True if the robot reached the end of its path.
        """

        if not self.path:
            self.status = RobotStatus.IDLE
            return False

        self.x, self.y = self.path.pop(0)

        if self.path:
            self.status = RobotStatus.MOVING
            return False

        self.status = RobotStatus.IDLE
        return True

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-serializable robot state."""
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "color": self.color,
            "status": self.status.value,
            "currentTaskId": self.current_task_id,
            "currentTarget": self.current_target,
            "blockedTicks": self.blocked_ticks,
            "replanning": self.replanning,
            "yieldingTo": self.yielding_to,
            "replanCooldown": self.replan_cooldown,

            # v0.4
            "battery": self.battery,
            "mode": self.mode.value,
            "idleTicks": self.idle_ticks,
            "chargerWaitTicks": self.charger_wait_ticks,
            "interruptedTaskId": self.interrupted_task_id,
            "chargeTarget": self.charge_target,
            "chargeStartBattery": self.charge_start_battery,
            "repairRemainingTicks": self.repair_remaining_ticks,
        }