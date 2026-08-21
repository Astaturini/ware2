from __future__ import annotations

import csv
import os
from typing import Any


class MetricsRecorder:
    """
    Records time-series observations and inferred events.

    This class receives primitive snapshot dictionaries only.
    It does not store live simulation object references.
    """

    TIME_SERIES_HEADERS = [
        "tick",
        "tasks_pending",
        "tasks_outstanding",
        "tasks_created_this_tick",
        "tasks_completed_this_tick",
        "tasks_completed_total",
        "tasks_failed_total",
        "robots_active",
        "robots_idle",
        "robots_blocked",
        "robots_charging",
        "robots_to_charger",
        "robots_waiting_for_charger",
        "robots_failed",
        "average_battery",
        "min_battery",
        "max_battery",
        "replans_this_tick",
        "replans_total",
        "blocked_ticks_this_tick",
        "blocked_ticks_total",
    ]

    EVENT_HEADERS = [
        "run_id",
        "tick",
        "event_type",
        "robot_id",
        "task_id",
        "details",
    ]

    def __init__(self, run_dir: str, run_id: str) -> None:
        self.run_dir = run_dir
        self.run_id = run_id

        self.ts_path = os.path.join(run_dir, "timeseries.csv")
        self.ev_path = os.path.join(run_dir, "events.csv")

        self.ts_file = open(self.ts_path, "w", newline="", encoding="utf-8")
        self.ev_file = open(self.ev_path, "w", newline="", encoding="utf-8")

        self.ts_writer = csv.writer(self.ts_file)
        self.ev_writer = csv.writer(self.ev_file)

        self.ts_writer.writerow(self.TIME_SERIES_HEADERS)
        self.ev_writer.writerow(self.EVENT_HEADERS)

        self._prev_metrics: dict[str, float] = {}
        self._prev_tasks: dict[str, dict[str, Any]] = {}
        self._prev_robots: dict[str, dict[str, Any]] = {}
        self._record_count = 0
        self._closed = False

    def record(self, snapshot: dict[str, Any]) -> None:
        if self._closed:
            raise RuntimeError("MetricsRecorder is already closed.")

        tick = int(snapshot["tick"])
        metrics = snapshot["metrics"]
        tasks = snapshot["tasks"]
        robots = snapshot["robots"]

        self._record_time_series(tick, metrics, tasks, robots)
        self._record_task_events(tick, tasks)
        self._record_robot_events(tick, robots)

        self._prev_metrics = dict(metrics)
        self._record_count += 1

        if self._record_count % 100 == 0:
            self.ts_file.flush()
            self.ev_file.flush()

    def _delta(self, name: str, current: float) -> float:
        previous = self._prev_metrics.get(name, 0.0)
        return float(current) - float(previous)

    def _record_time_series(
        self,
        tick: int,
        metrics: dict[str, Any],
        tasks: list[dict[str, Any]],
        robots: list[dict[str, Any]],
    ) -> None:
        # Pending means strictly unassigned Pending tasks.
        tasks_pending = sum(1 for task in tasks if task["status"] == "Pending")

        tasks_generated = float(metrics.get("tasks_generated", 0))
        tasks_completed = float(metrics.get("tasks_completed", 0))
        tasks_failed = float(metrics.get("tasks_failed", 0))

        # Outstanding means created but not completed/failed.
        # This includes Pending, Assigned, and Interrupted tasks.
        tasks_outstanding = max(0, tasks_generated - tasks_completed - tasks_failed)

        tasks_created_this_tick = self._delta("tasks_generated", tasks_generated)
        tasks_completed_this_tick = self._delta("tasks_completed", tasks_completed)

        robots_active = 0
        robots_idle = 0
        robots_blocked = 0
        robots_charging = 0
        robots_to_charger = 0
        robots_waiting_for_charger = 0
        robots_failed = 0

        batteries: list[float] = []

        for robot in robots:
            mode = robot["mode"]
            blocked_ticks = int(robot.get("blocked_ticks", 0))
            battery = float(robot.get("battery", 0.0))
            batteries.append(battery)

            # Mutually exclusive state buckets.
            if mode in {"Failed", "Repairing"}:
                robots_failed += 1
            elif mode == "Charging":
                robots_charging += 1
            elif mode == "Waiting for charger":
                robots_waiting_for_charger += 1
            elif blocked_ticks > 0:
                robots_blocked += 1
            elif mode == "To charger":
                robots_to_charger += 1
            elif mode == "Moving":
                robots_active += 1
            elif mode == "Idle":
                robots_idle += 1
            else:
                robots_idle += 1

        average_battery = sum(batteries) / len(batteries) if batteries else 0.0
        min_battery = min(batteries) if batteries else 0.0
        max_battery = max(batteries) if batteries else 0.0

        replans_total = float(metrics.get("replanning_count", 0))
        replans_this_tick = self._delta("replanning_count", replans_total)

        blocked_ticks_total = float(metrics.get("blocked_time_ticks", 0))
        blocked_ticks_this_tick = self._delta("blocked_time_ticks", blocked_ticks_total)

        row = [
            tick,
            tasks_pending,
            tasks_outstanding,
            tasks_created_this_tick,
            tasks_completed_this_tick,
            tasks_completed,
            tasks_failed,
            robots_active,
            robots_idle,
            robots_blocked,
            robots_charging,
            robots_to_charger,
            robots_waiting_for_charger,
            robots_failed,
            round(average_battery, 4),
            round(min_battery, 4),
            round(max_battery, 4),
            replans_this_tick,
            replans_total,
            blocked_ticks_this_tick,
            blocked_ticks_total,
        ]

        self.ts_writer.writerow(row)

    def _record_task_events(self, tick: int, tasks: list[dict[str, Any]]) -> None:
        current_task_ids = set()

        for task in tasks:
            task_id = task["id"]
            current_task_ids.add(task_id)

            status = task["status"]
            assigned_robot_id = task.get("assigned_robot_id")

            previous = self._prev_tasks.get(task_id)

            if previous is None:
                details = (
                    f"type={task.get('task_type')} "
                    f"pickup={task.get('pickup')} "
                    f"dropoff={task.get('dropoff')}"
                )
                self._write_event(tick, "task_created", None, task_id, details)
                previous_status = None
                previous_robot = None
            else:
                previous_status = previous.get("status")
                previous_robot = previous.get("assigned_robot_id")

            if status != previous_status:
                if status == "Assigned":
                    self._write_event(
                        tick,
                        "task_assigned",
                        assigned_robot_id,
                        task_id,
                        None,
                    )
                elif status == "Completed":
                    self._write_event(
                        tick,
                        "task_completed",
                        assigned_robot_id or previous_robot,
                        task_id,
                        None,
                    )
                elif status == "Failed":
                    self._write_event(
                        tick,
                        "task_failed",
                        assigned_robot_id or previous_robot,
                        task_id,
                        None,
                    )
                elif status == "Interrupted":
                    self._write_event(
                        tick,
                        "task_interrupted",
                        assigned_robot_id or previous_robot,
                        task_id,
                        None,
                    )

            if (
                status == "Assigned"
                and previous_status == "Assigned"
                and assigned_robot_id is not None
                and previous_robot is not None
                and assigned_robot_id != previous_robot
            ):
                self._write_event(
                    tick,
                    "task_reassigned",
                    assigned_robot_id,
                    task_id,
                    f"previous_robot={previous_robot}",
                )

            self._prev_tasks[task_id] = {
                "status": status,
                "assigned_robot_id": assigned_robot_id,
            }

        # Remove completed/failed tasks that were pruned from live simulation.
        # Interrupted tasks are not pruned by v0.4.
        for task_id in list(self._prev_tasks.keys()):
            if task_id not in current_task_ids:
                old_status = self._prev_tasks[task_id].get("status")
                if old_status in {"Completed", "Failed"}:
                    del self._prev_tasks[task_id]

    def _record_robot_events(self, tick: int, robots: list[dict[str, Any]]) -> None:
        current_robot_ids = set()

        for robot in robots:
            robot_id = robot["id"]
            current_robot_ids.add(robot_id)

            mode = robot["mode"]
            blocked_ticks = int(robot.get("blocked_ticks", 0))
            replanning = bool(robot.get("replanning", False))

            previous = self._prev_robots.get(robot_id)

            if previous is None:
                self._prev_robots[robot_id] = {
                    "mode": mode,
                    "blocked_ticks": blocked_ticks,
                    "replanning": replanning,
                }
                continue

            previous_mode = previous.get("mode")
            previous_blocked = int(previous.get("blocked_ticks", 0))
            previous_replanning = bool(previous.get("replanning", False))

            if previous_blocked == 0 and blocked_ticks > 0:
                self._write_event(tick, "robot_blocked", robot_id, None, None)

            if (
                previous_blocked > 0
                and blocked_ticks == 0
                and mode not in {"Failed", "Repairing", "Charging", "Waiting for charger"}
            ):
                self._write_event(tick, "robot_unblocked", robot_id, None, None)

            if not previous_replanning and replanning:
                self._write_event(tick, "robot_replanned", robot_id, None, None)

            if previous_mode != mode:
                if mode == "Charging":
                    self._write_event(tick, "robot_started_charging", robot_id, None, None)

                if previous_mode == "Charging" and mode != "Charging":
                    self._write_event(tick, "robot_finished_charging", robot_id, None, None)

                if mode in {"Failed", "Repairing"} and previous_mode not in {"Failed", "Repairing"}:
                    self._write_event(tick, "robot_faulted", robot_id, None, None)

                if previous_mode in {"Failed", "Repairing"} and mode not in {"Failed", "Repairing"}:
                    self._write_event(tick, "robot_recovered", robot_id, None, None)

                if mode == "Waiting for charger" and previous_mode != "Waiting for charger":
                    self._write_event(tick, "robot_waiting_for_charger", robot_id, None, None)

            self._prev_robots[robot_id] = {
                "mode": mode,
                "blocked_ticks": blocked_ticks,
                "replanning": replanning,
            }

        for robot_id in list(self._prev_robots.keys()):
            if robot_id not in current_robot_ids:
                del self._prev_robots[robot_id]

    def _write_event(
        self,
        tick: int,
        event_type: str,
        robot_id: str | None,
        task_id: str | None,
        details: str | None,
    ) -> None:
        self.ev_writer.writerow(
            [
                self.run_id,
                tick,
                event_type,
                robot_id or "",
                task_id or "",
                details or "",
            ]
        )

    def close(self) -> None:
        if self._closed:
            return

        self.ts_file.flush()
        self.ev_file.flush()
        self.ts_file.close()
        self.ev_file.close()
        self._closed = True