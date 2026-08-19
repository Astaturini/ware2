from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class TaskType(str, Enum):
    PUTAWAY = "PUTAWAY"
    PICK = "PICK"
    PACK = "PACK"
    SHIP = "SHIP"
    LEGACY = "LEGACY"


class TaskStatus(str, Enum):
    PENDING = "Pending"
    ASSIGNED = "Assigned"
    COMPLETED = "Completed"
    FAILED = "Failed"

    # v0.4
    INTERRUPTED = "Interrupted"


class TaskPhase(str, Enum):
    TO_PICKUP = "To pickup"
    TO_DROPOFF = "To dropoff"
    DONE = "Done"


class LoadState(str, Enum):
    """
    Logical cargo state for v0.4.

    This is not full physical pallet handling. It is enough to preserve
    task/load association during interruption and recovery.
    """

    ON_SHELF = "On shelf"
    CARRIED = "Carried"
    STAGED = "Staged"
    DELIVERED = "Delivered"


@dataclass
class Task:
    id: str
    name: str
    pickup: str      # location name, e.g. "B-02" or "PICK-1"
    dropoff: str     # location name
    task_type: TaskType = TaskType.LEGACY
    priority: int = 0
    created_at: int = 0
    completed_at: int | None = None
    status: TaskStatus = TaskStatus.PENDING
    assigned_robot_id: str | None = None
    phase: TaskPhase = TaskPhase.TO_PICKUP

    # ------------------------------------------------------------------
    # v0.4 fields
    # ------------------------------------------------------------------
    load_state: LoadState = LoadState.ON_SHELF
    interruption_count: int = 0
    last_assigned_robot_id: str | None = None

    # If a loaded task is interrupted, the simulation may create a temporary
    # logical resume location such as "RESUME-G00001".
    resume_location_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "pickup": self.pickup,
            "dropoff": self.dropoff,
            "taskType": self.task_type.value,
            "priority": self.priority,
            "createdAt": self.created_at,
            "completedAt": self.completed_at,
            "status": self.status.value,
            "assignedRobotId": self.assigned_robot_id,
            "phase": self.phase.value,

            # v0.4
            "loadState": self.load_state.value,
            "interruptionCount": self.interruption_count,
            "lastAssignedRobotId": self.last_assigned_robot_id,
            "resumeLocationName": self.resume_location_name,
        }