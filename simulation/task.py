from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    PENDING = "Pending"
    ASSIGNED = "Assigned"
    COMPLETED = "Completed"
    FAILED = "Failed"


class TaskPhase(str, Enum):
    TO_PICKUP = "To pickup"
    TO_DROPOFF = "To dropoff"
    DONE = "Done"


@dataclass
class Task:
    id: str
    name: str
    pickup: str      # location name, e.g. "B-02" or "PICK-1"
    dropoff: str     # location name
    status: TaskStatus = TaskStatus.PENDING
    assigned_robot_id: str | None = None
    phase: TaskPhase = TaskPhase.TO_PICKUP

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "pickup": self.pickup,
            "dropoff": self.dropoff,
            "status": self.status.value,
            "assignedRobotId": self.assigned_robot_id,
            "phase": self.phase.value,
        }