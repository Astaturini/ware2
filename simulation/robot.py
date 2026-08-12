from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RobotStatus(str, Enum):
    IDLE = "Idle"
    MOVING = "Moving"


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
        }