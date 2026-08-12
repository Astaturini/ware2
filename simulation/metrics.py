from __future__ import annotations

from dataclasses import dataclass, field

from .robot import Robot, RobotStatus
from .task import Task


@dataclass
class Metrics:
    tasks_generated: int = 0
    tasks_assigned: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    blocked_time_ticks: int = 0
    replanning_count: int = 0
    deadlock_resolutions: int = 0
    task_waiting_time_total: float = 0.0
    task_completion_time_total: float = 0.0
    robot_distance_travelled: dict[str, int] = field(default_factory=dict)
    robot_busy_ticks: dict[str, int] = field(default_factory=dict)
    robot_total_ticks: dict[str, int] = field(default_factory=dict)
    robot_blocked_ticks: dict[str, int] = field(default_factory=dict)
    robot_replan_events: dict[str, int] = field(default_factory=dict)
    tick_count: int = 0

    def reset(self) -> None:
        self.tasks_generated = 0
        self.tasks_assigned = 0
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.blocked_time_ticks = 0
        self.replanning_count = 0
        self.deadlock_resolutions = 0
        self.task_waiting_time_total = 0.0
        self.task_completion_time_total = 0.0
        self.robot_distance_travelled.clear()
        self.robot_busy_ticks.clear()
        self.robot_total_ticks.clear()
        self.robot_blocked_ticks.clear()
        self.robot_replan_events.clear()
        self.tick_count = 0

    def register_robot(self, robot: Robot) -> None:
        self.robot_distance_travelled.setdefault(robot.id, 0)
        self.robot_busy_ticks.setdefault(robot.id, 0)
        self.robot_total_ticks.setdefault(robot.id, 0)
        self.robot_blocked_ticks.setdefault(robot.id, 0)
        self.robot_replan_events.setdefault(robot.id, 0)

    def record_generated(self, task: Task) -> None:
        self.tasks_generated += 1

    def record_assigned(self, task: Task, tick: int) -> None:
        self.tasks_assigned += 1
        self.task_waiting_time_total += max(0, tick - task.created_at)

    def record_completed(self, task: Task, tick: int) -> None:
        self.tasks_completed += 1
        self.task_completion_time_total += max(0, tick - task.created_at)

    def record_failed(self, task: Task, tick: int) -> None:
        self.tasks_failed += 1

    def record_blocked(self, robot: Robot, blocked_ticks: int = 1) -> None:
        self.register_robot(robot)
        self.blocked_time_ticks += blocked_ticks
        self.robot_blocked_ticks[robot.id] += blocked_ticks

    def record_replan(self, robot: Robot) -> None:
        self.register_robot(robot)
        self.replanning_count += 1
        self.robot_replan_events[robot.id] += 1

    def record_deadlock_resolution(self) -> None:
        self.deadlock_resolutions += 1

    def record_robot_move(self, robot: Robot, distance: int = 1) -> None:
        self.register_robot(robot)
        self.robot_distance_travelled[robot.id] += distance

    def record_tick(self, robots: list[Robot]) -> None:
        self.tick_count += 1
        for robot in robots:
            self.register_robot(robot)
            self.robot_total_ticks[robot.id] += 1
            if robot.status == RobotStatus.MOVING:
                self.robot_busy_ticks[robot.id] += 1

    def to_dict(self, tick_interval: float) -> dict[str, object]:
        assigned = max(self.tasks_assigned, 1)
        completed = max(self.tasks_completed, 1)
        total_ticks = max(self.tick_count, 1)
        return {
            "tasksGenerated": self.tasks_generated,
            "tasksAssigned": self.tasks_assigned,
            "tasksCompleted": self.tasks_completed,
            "tasksFailed": self.tasks_failed,
            "blockedTimeTicks": self.blocked_time_ticks,
            "blockedTimeSeconds": self.blocked_time_ticks * tick_interval,
            "replanningCount": self.replanning_count,
            "deadlockResolutions": self.deadlock_resolutions,
            "replanEvents": self.replanning_count,
            "throughputPerTick": self.tasks_completed / total_ticks,
            "averageTaskWaitingTime": self.task_waiting_time_total / assigned,
            "averageTaskCompletionTime": self.task_completion_time_total / completed,
            "simulationTicks": self.tick_count,
            "simulationSeconds": self.tick_count * tick_interval,
            "robotDistanceTravelled": dict(self.robot_distance_travelled),
            "robotBusyTicks": dict(self.robot_busy_ticks),
            "robotBlockedTicks": dict(self.robot_blocked_ticks),
            "robotReplanEvents": dict(self.robot_replan_events),
            "robotUtilization": {
                robot_id: (
                    self.robot_busy_ticks.get(robot_id, 0)
                    / max(self.robot_total_ticks.get(robot_id, 0), 1)
                )
                for robot_id in self.robot_total_ticks
            },
        }
