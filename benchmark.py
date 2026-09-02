from __future__ import annotations

import argparse
import time

from experiment.config import ExperimentConfig
from experiment.factory import (
    create_conflict_manager_from_name,
    create_path_planner_from_name,
    create_scheduler,
    create_scheduler_from_name,
    create_simulation_from_config,
)
from simulation.config import BatteryConfig, ChargingConfig, FailureConfig
from simulation.metrics import Metrics
from simulation.robot import Robot, RobotStatus
from simulation.simulation import Simulation
from simulation.task_generator import TaskGenerator
from simulation.warehouse_layout import build_warehouse


"""
Headless benchmark for the warehouse simulation.
"""


def create_legacy_robots(num_robots: int) -> list[Robot]:
    """Old hardcoded spawn points from pre-v0.5 benchmark/app behavior."""
    spawn_points = [
        (1, 7),
        (9, 7),
        (17, 7),
        (24, 7),
        (1, 20),
        (9, 20),
        (17, 20),
        (24, 20),
        (1, 0),
        (9, 0),
        (17, 0),
        (12, 1),
        (13, 0),
    ]

    colors = [
        "#ef4444",
        "#3b82f6",
        "#10b981",
        "#f59e0b",
        "#8b5cf6",
        "#ec4899",
        "#14b8a6",
        "#f97316",
    ]

    robots: list[Robot] = []

    for i in range(min(num_robots, len(spawn_points))):
        robots.append(
            Robot(
                id=f"R{i + 1}",
                x=spawn_points[i][0],
                y=spawn_points[i][1],
                color=colors[i % len(colors)],
                status=RobotStatus.IDLE,
            )
        )

    return robots


def safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def print_conflict_diagnostics(sim: Simulation) -> None:
    cm = getattr(sim, "_conflict_manager", None)

    print("--- Conflict Manager Diagnostics After Run ---")

    if cm is None:
        print("No conflict manager attached.")
        print()
        return

    print(f"Active conflict manager: {type(cm).__name__}")

    counters = [
        ("Conflict tick calls", "tick_calls"),
        ("Robots seen with paths", "robots_with_paths"),
        ("Proactive locks created", "locks_created"),
        ("Proactive reservations created", "reservations_created"),
        ("Proactive denied steps", "denied_steps"),
    ]

    found = False

    for label, attr in counters:
        if hasattr(cm, attr):
            print(f"{label}: {getattr(cm, attr)}")
            found = True

    if not found:
        print("No proactive counters present. This is normal for local_yield.")

    print()


def run_benchmark(args: argparse.Namespace) -> None:
    mtbf_ticks = args.mtbf_ticks if args.failure_enabled else 0.0

    print("--- Starting Benchmark ---")
    print(f"Robots: {args.robots}")
    print(f"Spawn mode: {args.spawn}")
    print(f"Path planner: {args.path_planner}")
    print(f"Scheduler: {args.scheduler}")
    print(f"Conflict manager: {args.conflict_manager}")
    print(
        "Replan Params: "
        f"block={args.block_replan}s, "
        f"cooldown={args.cooldown} ticks"
    )
    print(f"Target: {args.target} completed tasks")
    print(f"Max ticks: {args.max_ticks}")
    print(f"Seed: {args.seed}")
    print()

    print("--- v0.4 Config ---")
    print(f"Battery capacity: {args.battery_capacity}")
    print(f"Empty move energy: {args.empty_move_energy}")
    print(f"Loaded move energy: {args.loaded_move_energy}")
    print(f"Critical battery: {args.critical_battery}")
    print(f"Opportunistic threshold: {args.opportunistic_charge_threshold}")
    print(
        "Idle ticks before opportunistic charge: "
        f"{args.idle_opportunistic_ticks}"
    )
    print(f"Battery safety margin: {args.battery_safety_margin}")
    print(f"Charger capacity: {args.charger_capacity}")
    print(f"Charge duration ticks: {args.charge_duration_ticks}")
    print(f"Failure enabled: {args.failure_enabled}")
    print(f"MTBF ticks: {mtbf_ticks}")
    print(f"MTTR ticks: {args.mttr_ticks}")
    print()

    if args.spawn == "legacy":
        if args.robots > 13:
            print(
                "WARNING: legacy spawn supports only 13 hardcoded positions. "
                "Robot count will be capped at 13."
            )

        battery_config = BatteryConfig(
            capacity=args.battery_capacity,
            empty_move_energy=args.empty_move_energy,
            loaded_move_energy=args.loaded_move_energy,
            critical_battery=args.critical_battery,
            opportunistic_charge_threshold=args.opportunistic_charge_threshold,
            idle_ticks_before_opportunistic_charge=args.idle_opportunistic_ticks,
            safety_margin=args.battery_safety_margin,
        )

        charging_config = ChargingConfig(
            capacity=args.charger_capacity,
            charge_duration_ticks=args.charge_duration_ticks,
        )

        failure_config = FailureConfig(
            enabled=args.failure_enabled,
            mtbf_ticks=mtbf_ticks,
            mttr_ticks=args.mttr_ticks,
            seed=args.seed,
            relocate_to_maintenance=True,
        )

        warehouse = build_warehouse()
        robots = create_legacy_robots(args.robots)
        metrics = Metrics()

        path_planner = create_path_planner_from_name(args.path_planner)
        scheduler = create_scheduler_from_name(args.scheduler, path_planner)

        sim = Simulation(
            warehouse=warehouse,
            robots=robots,
            tasks=[],
            tick_interval=0.3,
            scheduler=scheduler,
            task_generator=TaskGenerator(warehouse=warehouse, seed=args.seed),
            metrics=metrics,
            blocked_replan_seconds=args.block_replan,
            replan_cooldown_ticks=args.cooldown,
            battery_config=battery_config,
            charging_config=charging_config,
            failure_config=failure_config,
            seed=args.seed,
            path_planner=path_planner,
        )

        if hasattr(sim, "set_conflict_manager"):
            sim.set_conflict_manager(
                create_conflict_manager_from_name(args.conflict_manager, sim)
            )

    else:
        config_dict = {
            "seed": args.seed,
            "num_robots": args.robots,
            "display_name": args.display_name,
            "stop_mode": "workload",
            "target_tasks": args.target,
            "max_ticks": args.max_ticks,
            "tick_interval": 0.3,
            "fast_mode": True,
            "blocked_replan_seconds": args.block_replan,
            "replan_cooldown_ticks": args.cooldown,
            "battery_capacity": args.battery_capacity,
            "empty_move_energy": args.empty_move_energy,
            "loaded_move_energy": args.loaded_move_energy,
            "critical_battery": args.critical_battery,
            "opportunistic_charge_threshold": args.opportunistic_charge_threshold,
            "idle_ticks_before_opportunistic_charge": args.idle_opportunistic_ticks,
            "battery_safety_margin": args.battery_safety_margin,
            "empty_battery_recovery_ticks": 15,
            "charger_capacity": args.charger_capacity,
            "charge_duration_ticks": args.charge_duration_ticks,
            "failure_enabled": args.failure_enabled,
            "mtbf_ticks": mtbf_ticks,
            "mttr_ticks": args.mttr_ticks,
            "relocate_to_maintenance": True,
            "scheduler": args.scheduler,
            "path_planner": args.path_planner,
            "conflict_manager": args.conflict_manager,
        }

        config = ExperimentConfig.from_dict(config_dict)
        sim = create_simulation_from_config(config)

        # CLI arguments are authoritative for benchmarking.
        path_planner = create_path_planner_from_name(args.path_planner)
        sim._path_planner = path_planner
        sim._scheduler = create_scheduler(config, path_planner)

        if hasattr(sim, "set_conflict_manager"):
            sim.set_conflict_manager(
                create_conflict_manager_from_name(args.conflict_manager, sim)
            )

        metrics = sim._metrics

    active_path_planner = type(getattr(sim, "_path_planner", None)).__name__
    active_scheduler = type(getattr(sim, "_scheduler", None)).__name__
    active_conflict_manager = type(
        getattr(sim, "_conflict_manager", None)
    ).__name__

    print(f"Active path planner: {active_path_planner}")
    print(f"Active scheduler: {active_scheduler}")
    print(f"Active conflict manager: {active_conflict_manager}")
    print("Conflict diagnostics will be printed after the run.")
    print()

    start_time = time.perf_counter()
    ticks = 0

    while metrics.tasks_completed < args.target and ticks < args.max_ticks:
        with sim._lock:
            sim._tick()
        ticks += 1

    end_time = time.perf_counter()

    stop_reason = (
        "target_reached"
        if metrics.tasks_completed >= args.target
        else "max_ticks_reached"
    )

    print(f"--- Results after {ticks} ticks ---")
    print(f"Stop reason: {stop_reason}")
    print(f"Wall-clock time: {end_time - start_time:.2f} seconds")
    print()

    print("--- Existing v0.3 Metrics ---")
    print(f"Generated: {metrics.tasks_generated}")
    print(f"Assigned: {metrics.tasks_assigned}")
    print(f"Completed: {metrics.tasks_completed}")
    print(f"Failed: {metrics.tasks_failed}")
    print(
        "Throughput: "
        f"{safe_divide(metrics.tasks_completed, ticks):.3f} tasks/tick"
    )
    print(f"Blocked Time: {metrics.blocked_time_ticks} ticks")
    print(f"Replan Events: {metrics.replanning_count}")
    print(f"Deadlock Resolutions: {metrics.deadlock_resolutions}")
    print(
        "Avg Wait Time: "
        f"{safe_divide(metrics.task_waiting_time_total, metrics.tasks_assigned):.1f} ticks"
    )
    print(
        "Avg Cycle Time: "
        f"{safe_divide(metrics.task_completion_time_total, metrics.tasks_completed):.1f} ticks"
    )
    print()

    print("--- v0.4 Battery / Charging / Failure Metrics ---")

    average_battery = safe_divide(metrics.battery_sum, metrics.battery_samples)
    average_battery_percent = safe_divide(
        average_battery,
        metrics.battery_capacity,
    ) * 100.0

    average_charger_wait = safe_divide(
        metrics.charger_wait_ticks,
        metrics.charger_wait_events,
    )

    total_wait_ticks = (
        metrics.traffic_wait_ticks
        + metrics.charger_wait_ticks
        + metrics.station_wait_ticks
    )

    print(f"Average Battery: {average_battery:.2f} / {metrics.battery_capacity:.2f}")
    print(f"Average Battery Percent: {average_battery_percent:.2f}%")
    print(f"Charging Events: {metrics.charging_events}")
    print(f"Total Charging Ticks: {metrics.total_charging_ticks}")
    print(f"Charger Wait Events: {metrics.charger_wait_events}")
    print(f"Charger Wait Ticks: {metrics.charger_wait_ticks}")
    print(f"Average Charger Wait: {average_charger_wait:.2f} ticks")
    print(f"Traffic Wait Ticks: {metrics.traffic_wait_ticks}")
    print(f"Total Wait Ticks: {total_wait_ticks}")
    print(f"Battery Task Interruptions: {metrics.battery_task_interruptions}")
    print(f"Failure Task Interruptions: {metrics.failure_task_interruptions}")
    print(f"Task Reassignments: {metrics.task_reassignments}")
    print(f"Failed Robot Events: {metrics.failed_robot_events}")
    print(f"Failure Downtime Ticks: {metrics.failure_downtime_ticks}")
    print()

    print("Per-Robot Utilization:")

    for robot_id in sorted(metrics.robot_total_ticks):
        busy = metrics.robot_busy_ticks.get(robot_id, 0)
        total = metrics.robot_total_ticks.get(robot_id, 0)
        blocked = metrics.robot_blocked_ticks.get(robot_id, 0)
        replans = metrics.robot_replan_events.get(robot_id, 0)
        utilization = safe_divide(busy, total)

        print(
            f"  {robot_id}: "
            f"{utilization:.1%} busy, "
            f"{blocked} blocked ticks, "
            f"{replans} replans"
        )

    print()
    print_conflict_diagnostics(sim)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Headless warehouse simulation benchmark."
    )

    parser.add_argument(
        "--robots",
        type=int,
        default=6,
        help="Number of robots.",
    )

    parser.add_argument(
        "--spawn",
        choices=["seeded", "legacy"],
        default="seeded",
        help=(
            "Robot spawn mode. "
            "'seeded' uses v0.5 dynamic seeded spawn positions. "
            "'legacy' uses the old hardcoded spawn points."
        ),
    )

    parser.add_argument(
        "--path-planner",
        choices=["bfs", "astar", "weighted_astar"],
        default="bfs",
        help="Path planning algorithm.",
    )

    parser.add_argument(
        "--scheduler",
        choices=[
            "baseline",
            "priority",
            "fifo",
            "total_cost",
            "auction",
        ],
        default="baseline",
        help="Task allocation scheduler.",
    )

    parser.add_argument(
        "--conflict-manager",
        choices=[
            "local_yield",
            "zone_locks",
            "priority_reservation",
        ],
        default="local_yield",
        help="Conflict resolution manager.",
    )

    parser.add_argument(
        "--display-name",
        type=str,
        default="benchmark",
        help="Display name metadata for seeded experiment config.",
    )

    parser.add_argument(
        "--block-replan",
        type=float,
        default=0.7,
        help="Blocked replan seconds.",
    )

    parser.add_argument(
        "--cooldown",
        type=int,
        default=7,
        help="Replan cooldown ticks.",
    )

    parser.add_argument(
        "--target",
        type=int,
        default=50,
        help="Target completed tasks.",
    )

    parser.add_argument(
        "--max-ticks",
        type=int,
        default=20_000,
        help="Safety tick limit.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="RNG seed for task generator, failure generator, and spawn positions.",
    )

    parser.add_argument(
        "--battery-capacity",
        type=float,
        default=100.0,
        help="Battery capacity.",
    )

    parser.add_argument(
        "--empty-move-energy",
        type=float,
        default=0.35,
        help="Energy consumed per empty movement step.",
    )

    parser.add_argument(
        "--loaded-move-energy",
        type=float,
        default=0.5,
        help="Energy consumed per loaded movement step.",
    )

    parser.add_argument(
        "--critical-battery",
        type=float,
        default=15.0,
        help="Critical battery threshold.",
    )

    parser.add_argument(
        "--opportunistic-charge-threshold",
        type=float,
        default=30.0,
        help="Opportunistic charging threshold.",
    )

    parser.add_argument(
        "--idle-opportunistic-ticks",
        type=int,
        default=10,
        help="Idle ticks before opportunistic charging is allowed.",
    )

    parser.add_argument(
        "--battery-safety-margin",
        type=float,
        default=5.0,
        help="Safety margin used for battery feasibility checks.",
    )

    parser.add_argument(
        "--charger-capacity",
        type=int,
        default=4,
        help="Charging station capacity.",
    )

    parser.add_argument(
        "--charge-duration-ticks",
        type=int,
        default=10,
        help="Charging duration in ticks.",
    )

    parser.add_argument(
        "--failure-enabled",
        action="store_true",
        help="Enable random robot failures.",
    )

    parser.add_argument(
        "--mtbf-ticks",
        type=float,
        default=0.0,
        help="Mean ticks between failures. Required > 0 if --failure-enabled.",
    )

    parser.add_argument(
        "--mttr-ticks",
        type=int,
        default=25,
        help="Repair duration in ticks.",
    )

    args = parser.parse_args()

    if args.robots < 1:
        parser.error("--robots must be at least 1.")

    if args.target < 1:
        parser.error("--target must be at least 1.")

    if args.max_ticks < 1:
        parser.error("--max-ticks must be at least 1.")

    if args.failure_enabled and args.mtbf_ticks <= 0:
        parser.error("--mtbf-ticks must be > 0 when --failure-enabled is set.")

    run_benchmark(args)