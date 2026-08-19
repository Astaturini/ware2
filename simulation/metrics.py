from __future__ import annotations

from dataclasses import dataclass, field

from .robot import Robot, RobotStatus
from .task import Task


@dataclass
class Metrics:
    # ------------------------------------------------------------------
    # Existing v0.3 metrics
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # v0.4 metrics
    # ------------------------------------------------------------------
    battery_capacity: float = 100.0
    battery_sum: float = 0.0
    battery_samples: int = 0

    charging_events: int = 0
    total_charging_ticks: int = 0

    charger_wait_ticks: int = 0
    charger_wait_events: int = 0

    traffic_wait_ticks: int = 0
    station_wait_ticks: int = 0

    battery_task_interruptions: int = 0
    failure_task_interruptions: int = 0
    task_reassignments: int = 0

    failed_robot_events: int = 0
    failure_downtime_ticks: int = 0

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

        # v0.4 resets.
        # battery_capacity is intentionally preserved.
        self.battery_sum = 0.0
        self.battery_samples = 0
        self.charging_events = 0
        self.total_charging_ticks = 0
        self.charger_wait_ticks = 0
        self.charger_wait_events = 0
        self.traffic_wait_ticks = 0
        self.station_wait_ticks = 0
        self.battery_task_interruptions = 0
        self.failure_task_interruptions = 0
        self.task_reassignments = 0
        self.failed_robot_events = 0
        self.failure_downtime_ticks = 0

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

        # v0.4: blocked time is traffic waiting.
        self.traffic_wait_ticks += blocked_ticks

    def record_replan(self, robot: Robot) -> None:
        self.register_robot(robot)
        self.replanning_count += 1
        self.robot_replan_events[robot.id] += 1

    def record_deadlock_resolution(self) -> None:
        self.deadlock_resolutions += 1

    def record_robot_move(self, robot: Robot, distance: int = 1) -> None:
        self.register_robot(robot)
        self.robot_distance_travelled[robot.id] += distance

    # ------------------------------------------------------------------
    # v0.4 recording helpers
    # ------------------------------------------------------------------
    def record_battery_sample(self, robot: Robot) -> None:
        battery = float(getattr(robot, "battery", self.battery_capacity))
        self.battery_sum += battery
        self.battery_samples += 1

    def record_charging_start(self) -> None:
        self.charging_events += 1

    def record_charging_tick(self) -> None:
        self.total_charging_ticks += 1

    def record_charger_wait_start(self) -> None:
        self.charger_wait_events += 1

    def record_charger_wait_tick(self) -> None:
        self.charger_wait_ticks += 1

    def record_battery_task_interruption(self) -> None:
        self.battery_task_interruptions += 1

    def record_failure_task_interruption(self) -> None:
        self.failure_task_interruptions += 1

    def record_task_reassignment(self) -> None:
        self.task_reassignments += 1

    def record_failed_robot_event(self) -> None:
        self.failed_robot_events += 1

    def record_failure_downtime_tick(self) -> None:
        self.failure_downtime_ticks += 1

    def record_tick(self, robots: list[Robot]) -> None:
        self.tick_count += 1

        for robot in robots:
            self.register_robot(robot)
            self.robot_total_ticks[robot.id] += 1

            if robot.status == RobotStatus.MOVING:
                self.robot_busy_ticks[robot.id] += 1

            # v0.4 battery sample.
            self.record_battery_sample(robot)

    def to_dict(self, tick_interval: float) -> dict[str, object]:
        assigned = max(self.tasks_assigned, 1)
        completed = max(self.tasks_completed, 1)
        total_ticks = max(self.tick_count, 1)

        average_battery = (
            self.battery_sum / self.battery_samples
            if self.battery_samples
            else self.battery_capacity
        )
        average_battery_percent = (
            average_battery / self.battery_capacity * 100.0
            if self.battery_capacity > 0
            else 0.0
        )

        average_charger_wait_ticks = (
            self.charger_wait_ticks / max(self.charger_wait_events, 1)
        )

        total_wait_ticks = (
            self.traffic_wait_ticks
            + self.charger_wait_ticks
            + self.station_wait_ticks
        )

        return {
            # Existing v0.3 keys.
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

            # v0.4 keys.
            "averageBattery": average_battery,
            "averageBatteryPercent": average_battery_percent,
            "chargingEvents": self.charging_events,
            "totalChargingTicks": self.total_charging_ticks,
            "totalChargingSeconds": self.total_charging_ticks * tick_interval,
            "chargerWaitTicks": self.charger_wait_ticks,
            "chargerWaitSeconds": self.charger_wait_ticks * tick_interval,
            "chargerWaitEvents": self.charger_wait_events,
            "averageChargerWaitTicks": average_charger_wait_ticks,
            "averageChargerWaitSeconds": average_charger_wait_ticks * tick_interval,
            "trafficWaitTicks": self.traffic_wait_ticks,
            "trafficWaitSeconds": self.traffic_wait_ticks * tick_interval,
            "stationWaitTicks": self.station_wait_ticks,
            "stationWaitSeconds": self.station_wait_ticks * tick_interval,
            "totalWaitTicks": total_wait_ticks,
            "totalWaitSeconds": total_wait_ticks * tick_interval,
            "batteryTaskInterruptions": self.battery_task_interruptions,
            "failureTaskInterruptions": self.failure_task_interruptions,
            "taskReassignments": self.task_reassignments,
            "failedRobotEvents": self.failed_robot_events,
            "failureDowntimeTicks": self.failure_downtime_ticks,
            "failureDowntimeSeconds": self.failure_downtime_ticks * tick_interval,
        }