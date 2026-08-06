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

    @property
    def current_target(self) -> tuple[int, int] | None:
        """Return the next cell the robot will move into, if any."""
        return self.path[0] if self.path else None

    def set_path(self, path: list[tuple[int, int]]) -> None:
        """Assign a new path. The path should exclude the robot's current cell."""
        self.path = list(path)
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
        }