from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from simulation.simulation import Simulation

from .config import ExperimentConfig
from .recorder import MetricsRecorder


class ExperimentRunner:
    def __init__(self, base_dir: str = "data/runs") -> None:
        self.base_dir = Path(base_dir)
        self.sim: Simulation | None = None
        self.config: ExperimentConfig | None = None
        self.recorder: MetricsRecorder | None = None

        self.run_id: str | None = None
        self.run_dir: Path | None = None
        self.stop_reason: str | None = None

        self._thread: threading.Thread | None = None
        self._summary: dict[str, Any] | None = None
        self._finalized = False

    @property
    def is_active(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._finalized

    @property
    def finished(self) -> bool:
        return self._finalized

    def start(
        self,
        config: ExperimentConfig,
        sim_factory: Callable[[ExperimentConfig], Simulation],
    ) -> str:
        if self.is_active:
            raise RuntimeError("An experiment is already running.")

        self.config = config
        self.sim = sim_factory(config)
        self.stop_reason = None
        self._summary = None
        self._finalized = False

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_id = uuid.uuid4().hex[:6]
        self.run_id = f"{timestamp}_{short_id}"

        self.run_dir = self.base_dir / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

        config.save(self.run_dir)
        self.recorder = MetricsRecorder(str(self.run_dir), self.run_id)

        self.sim.resume()

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

        return self.run_id

    def stop(self, reason: str = "stopped_by_user") -> None:
        if self._finalized:
            return

        if self.stop_reason is None:
            self.stop_reason = reason

        if self.sim is not None:
            self.sim.stop()

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        elif not self._finalized:
            self._finalize()

    def get_state(self) -> dict[str, Any]:
        return {
            "active": self.is_active,
            "finished": self.finished,
            "runId": self.run_id,
            "runDir": str(self.run_dir) if self.run_dir else None,
            "stopReason": self.stop_reason,
            "paused": bool(self.sim.is_paused) if self.sim is not None else True,
            "tick": int(self.sim._tick_count) if self.sim is not None else 0,
            "fastMode": bool(self.config.fast_mode) if self.config is not None else False,
        }

    def get_summary(self) -> dict[str, Any] | None:
        if self._summary is not None:
            return self._summary

        if self.run_dir is None:
            return None

        summary_path = self.run_dir / "summary.json"
        if not summary_path.exists():
            return None

        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                self._summary = json.load(f)
                return self._summary
        except Exception:
            return None

    def _run(self) -> None:
        assert self.sim is not None
        assert self.config is not None
        assert self.recorder is not None

        while not self.sim._stop_event.is_set():
            if self.sim.is_paused:
                time.sleep(0.05)
                continue

            try:
                with self.sim._lock:
                    self.sim._tick()
                    snapshot = self._snapshot()
                    self.recorder.record(snapshot)

                    reason = self._evaluate_stop_condition(snapshot)
                    if reason is not None:
                        self.stop_reason = reason
                        self.sim.stop()
                        break
            except Exception as exc:
                self.stop_reason = f"error: {exc}"
                self.sim.stop()
                break

            if self.config.fast_mode:
                # No wall-clock pacing. Yield occasionally so the web
                # server thread can answer polls during long runs.
                if self.sim._tick_count % 500 == 0:
                    time.sleep(0)
            else:
                time.sleep(self.sim._tick_interval)

        self._finalize()

    def _evaluate_stop_condition(self, snapshot: dict[str, Any]) -> str | None:
        assert self.config is not None

        tick = int(snapshot["tick"])
        completed = float(snapshot["metrics"].get("tasks_completed", 0))

        if self.config.stop_mode == "fixed_ticks":
            if tick >= self.config.max_ticks:
                return "max_ticks_reached"

        if self.config.stop_mode == "workload":
            if self.config.target_tasks is not None and completed >= self.config.target_tasks:
                return "target_reached"
            if tick >= self.config.max_ticks:
                return "max_ticks_reached"

        return None

    def _snapshot(self) -> dict[str, Any]:
        assert self.sim is not None

        metrics = self.sim._metrics

        def metric_value(name: str, default: float = 0.0) -> float:
            return float(getattr(metrics, name, default))

        tasks: list[dict[str, Any]] = []
        for task in self.sim._tasks.values():
            tasks.append(
                {
                    "id": task.id,
                    "status": getattr(task.status, "value", str(task.status)),
                    "assigned_robot_id": task.assigned_robot_id,
                    "task_type": getattr(task.task_type, "value", str(task.task_type)),
                    "pickup": task.pickup,
                    "dropoff": task.dropoff,
                    "created_at": task.created_at,
                    "completed_at": task.completed_at,
                }
            )

        robots: list[dict[str, Any]] = []
        for robot in self.sim._robots.values():
            robots.append(
                {
                    "id": robot.id,
                    "status": getattr(robot.status, "value", str(robot.status)),
                    "mode": getattr(robot.mode, "value", str(robot.mode)),
                    "x": robot.x,
                    "y": robot.y,
                    "blocked_ticks": robot.blocked_ticks,
                    "replanning": robot.replanning,
                    "battery": float(getattr(robot, "battery", 0.0)),
                }
            )

        return {
            "tick": self.sim._tick_count,
            "metrics": {
                "tasks_generated": metric_value("tasks_generated"),
                "tasks_assigned": metric_value("tasks_assigned"),
                "tasks_completed": metric_value("tasks_completed"),
                "tasks_failed": metric_value("tasks_failed"),
                "blocked_time_ticks": metric_value("blocked_time_ticks"),
                "replanning_count": metric_value("replanning_count"),
                "task_waiting_time_total": metric_value("task_waiting_time_total"),
                "task_completion_time_total": metric_value("task_completion_time_total"),
            },
            "tasks": tasks,
            "robots": robots,
        }

    def _finalize(self) -> None:
        if self._finalized:
            return

        if self.sim is None or self.config is None or self.recorder is None:
            return
        if self.run_dir is None or self.run_id is None:
            return

        self.recorder.close()

        metrics = self.sim._metrics
        ticks = int(self.sim._tick_count)

        tasks_generated = int(getattr(metrics, "tasks_generated", 0))
        tasks_assigned = int(getattr(metrics, "tasks_assigned", 0))
        tasks_completed = int(getattr(metrics, "tasks_completed", 0))
        tasks_failed = int(getattr(metrics, "tasks_failed", 0))

        blocked_ticks = int(getattr(metrics, "blocked_time_ticks", 0))
        replans = int(getattr(metrics, "replanning_count", 0))

        waiting_total = float(getattr(metrics, "task_waiting_time_total", 0.0))
        completion_total = float(getattr(metrics, "task_completion_time_total", 0.0))

        robot_busy_ticks = getattr(metrics, "robot_busy_ticks", {}) or {}
        robot_total_ticks = getattr(metrics, "robot_total_ticks", {}) or {}
        robot_blocked_ticks = getattr(metrics, "robot_blocked_ticks", {}) or {}
        robot_distance_travelled = getattr(metrics, "robot_distance_travelled", {}) or {}

        busy_sum = sum(int(v) for v in robot_busy_ticks.values())
        total_sum = sum(int(v) for v in robot_total_ticks.values())

        average_throughput = tasks_completed / ticks if ticks > 0 else 0.0
        average_wait_time = waiting_total / tasks_assigned if tasks_assigned > 0 else 0.0
        average_cycle_time = completion_total / tasks_completed if tasks_completed > 0 else 0.0
        average_utilization = busy_sum / total_sum if total_sum > 0 else 0.0

        robot_utilization: dict[str, float] = {}
        for robot_id, total in robot_total_ticks.items():
            total = int(total)
            busy = int(robot_busy_ticks.get(robot_id, 0))
            robot_utilization[str(robot_id)] = busy / total if total > 0 else 0.0

        summary = {
            "run_id": self.run_id,
            "seed": self.config.seed,
            "scheduler": self.config.scheduler,
            "stop_reason": self.stop_reason,
            "fast_mode": self.config.fast_mode,
            "simulation_ticks": ticks,
            "simulation_seconds": ticks * self.config.tick_interval,
            "robot_count": self.config.num_robots,
            "tasks_created": tasks_generated,
            "tasks_assigned": tasks_assigned,
            "tasks_completed": tasks_completed,
            "tasks_failed": tasks_failed,
            "average_throughput": average_throughput,
            "average_wait_time": average_wait_time,
            "average_cycle_time": average_cycle_time,
            "average_robot_utilization": average_utilization,
            "total_replans": replans,
            "total_blocked_ticks": blocked_ticks,
            "blocked_time_seconds": blocked_ticks * self.config.tick_interval,
            "charging_events": int(getattr(metrics, "charging_events", 0)),
            "total_charging_ticks": int(getattr(metrics, "total_charging_ticks", 0)),
            "charger_wait_ticks": int(getattr(metrics, "charger_wait_ticks", 0)),
            "charger_wait_events": int(getattr(metrics, "charger_wait_events", 0)),
            "battery_task_interruptions": int(getattr(metrics, "battery_task_interruptions", 0)),
            "failure_task_interruptions": int(getattr(metrics, "failure_task_interruptions", 0)),
            "task_reassignments": int(getattr(metrics, "task_reassignments", 0)),
            "failed_robot_events": int(getattr(metrics, "failed_robot_events", 0)),
            "failure_downtime_ticks": int(getattr(metrics, "failure_downtime_ticks", 0)),
            "robot_utilization": robot_utilization,
            "robot_busy_ticks": {str(k): int(v) for k, v in robot_busy_ticks.items()},
            "robot_total_ticks": {str(k): int(v) for k, v in robot_total_ticks.items()},
            "robot_blocked_ticks": {str(k): int(v) for k, v in robot_blocked_ticks.items()},
            "robot_distance_travelled": {str(k): int(v) for k, v in robot_distance_travelled.items()},
        }

        with open(self.run_dir / "summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        self._summary = summary
        self._finalized = True