from __future__ import annotations

import argparse
import time

from simulation.config import BatteryConfig, ChargingConfig, FailureConfig
from simulation.metrics import Metrics
from simulation.robot import Robot, RobotStatus
from simulation.scheduler import CostBasedScheduler
from simulation.simulation import Simulation
from simulation.task_generator import TaskGenerator
from simulation.warehouse_layout import build_warehouse


"""
Headless benchmark for the warehouse simulation.

Examples:

v0.3-style benchmark:

    python benchmark.py --robots 8 --block-replan 0.7 --cooldown 7 --target 200

v0.4 benchmark with battery/charging:

    python benchmark.py \
        --robots 8 \
        --seed 42 \
        --target 200 \
        --battery-capacity 100 \
        --empty-move-energy 0.7 \
        --loaded-move-energy 1.0 \
        --critical-battery 20 \
        --opportunistic-charge-threshold 40 \
        --idle-opportunistic-ticks 10 \
        --battery-safety-margin 5 \
        --charger-capacity 4 \
        --charge-duration-ticks 10

v0.4 benchmark with failures:

    python benchmark.py \
        --robots 8 \
        --seed 42 \
        --target 200 \
        --failure-enabled \
        --mtbf-ticks 1500 \
        --mttr-ticks 25
"""


def create_robots(num_robots: int) -> list[Robot]:
    # Spawn points as app.py has them.
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


def run_benchmark(
    num_robots: int,
    blocked_replan_seconds: float,
    replan_cooldown_ticks: int,
    target_completed: int,
    max_ticks: int,
    seed: int | None,
    battery_config: BatteryConfig,
    charging_config: ChargingConfig,
    failure_config: FailureConfig,
) -> None:
    print("--- Starting Benchmark ---")
    print(f"Robots: {num_robots}")
    print(
        "Replan Params: "
        f"block={blocked_replan_seconds}s, "
        f"cooldown={replan_cooldown_ticks} ticks"
    )
    print(f"Target: {target_completed} completed tasks")
    print(f"Max ticks: {max_ticks}")
    print(f"Seed: {seed}")
    print()

    print("--- v0.4 Config ---")
    print(f"Battery capacity: {battery_config.capacity}")
    print(f"Empty move energy: {battery_config.empty_move_energy}")
    print(f"Loaded move energy: {battery_config.loaded_move_energy}")
    print(f"Critical battery: {battery_config.critical_battery}")
    print(
        "Opportunistic threshold: "
        f"{battery_config.opportunistic_charge_threshold}"
    )
    print(
        "Idle ticks before opportunistic charge: "
        f"{battery_config.idle_ticks_before_opportunistic_charge}"
    )
    print(f"Battery safety margin: {battery_config.safety_margin}")
    print(f"Charger capacity: {charging_config.capacity}")
    print(f"Charge duration ticks: {charging_config.charge_duration_ticks}")
    print(f"Failure enabled: {failure_config.enabled}")
    print(f"MTBF ticks: {failure_config.mtbf_ticks}")
    print(f"MTTR ticks: {failure_config.mttr_ticks}")
    print()

    warehouse = build_warehouse()
    robots = create_robots(num_robots)
    metrics = Metrics()

    sim = Simulation(
        warehouse=warehouse,
        robots=robots,
        tasks=[],
        tick_interval=0.3,
        scheduler=CostBasedScheduler(),
        task_generator=TaskGenerator(warehouse=warehouse, seed=seed),
        metrics=metrics,
        blocked_replan_seconds=blocked_replan_seconds,
        replan_cooldown_ticks=replan_cooldown_ticks,
        battery_config=battery_config,
        charging_config=charging_config,
        failure_config=failure_config,
        seed=seed,
    )

    start_time = time.perf_counter()

    ticks = 0
    while metrics.tasks_completed < target_completed and ticks < max_ticks:
        with sim._lock:
            sim._tick()
        ticks += 1

    end_time = time.perf_counter()

    print(f"--- Results after {ticks} ticks ---")
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

    print(f"Average Battery: {average_battery:.2f} / {metrics.battery_capacity:.2f}")
    print(f"Average Battery Percent: {average_battery_percent:.2f}%")
    print(f"Charging Events: {metrics.charging_events}")
    print(f"Total Charging Ticks: {metrics.total_charging_ticks}")
    print(f"Charger Wait Events: {metrics.charger_wait_events}")
    print(f"Charger Wait Ticks: {metrics.charger_wait_ticks}")
    print(f"Average Charger Wait: {average_charger_wait:.2f} ticks")
    print(f"Traffic Wait Ticks: {metrics.traffic_wait_ticks}")
    print(f"Total Wait Ticks: {metrics.traffic_wait_ticks + metrics.charger_wait_ticks + metrics.station_wait_ticks}")
    print(f"Battery Task Interruptions: {metrics.battery_task_interruptions}")
    print(f"Failure Task Interruptions: {metrics.failure_task_interruptions}")
    print(f"Task Reassignments: {metrics.task_reassignments}")
    print(f"Failed Robot Events: {metrics.failed_robot_events}")
    print(f"Failure Downtime Ticks: {metrics.failure_downtime_ticks}")

    print()
    print("Per-Robot Utilization:")

    for robot_id in metrics.robot_total_ticks:
        busy = metrics.robot_busy_ticks.get(robot_id, 0)
        total = metrics.robot_total_ticks.get(robot_id, 1)
        blocked = metrics.robot_blocked_ticks.get(robot_id, 0)
        replans = metrics.robot_replan_events.get(robot_id, 0)

        print(
            f"  {robot_id}: "
            f"{busy / total:.1%} busy, "
            f"{blocked} blocked ticks, "
            f"{replans} replans"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Headless warehouse simulation benchmark."
    )

    # Existing v0.3 parameters.
    parser.add_argument(
        "--robots",
        type=int,
        default=4,
        help="Number of robots.",
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
        default=1000,
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
        help="RNG seed for task generator and v0.4 failure generator.",
    )

    # v0.4 battery parameters.
    parser.add_argument(
        "--battery-capacity",
        type=float,
        default=100.0,
        help="Battery capacity.",
    )
    parser.add_argument(
        "--empty-move-energy",
        type=float,
        default=0.7,
        help="Energy consumed per empty movement step.",
    )
    parser.add_argument(
        "--loaded-move-energy",
        type=float,
        default=1.0,
        help="Energy consumed per loaded movement step.",
    )
    parser.add_argument(
        "--critical-battery",
        type=float,
        default=20.0,
        help="Critical battery threshold.",
    )
    parser.add_argument(
        "--opportunistic-charge-threshold",
        type=float,
        default=40.0,
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

    # v0.4 charging parameters.
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

    # v0.4 failure parameters.
    parser.add_argument(
        "--failure-enabled",
        action="store_true",
        help="Enable random robot failures.",
    )
    parser.add_argument(
        "--mtbf-ticks",
        type=float,
        default=0.0,
        help="Mean ticks between failures. Ignored unless --failure-enabled.",
    )
    parser.add_argument(
        "--mttr-ticks",
        type=int,
        default=25,
        help="Repair duration in ticks.",
    )

    args = parser.parse_args()

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
        mtbf_ticks=args.mtbf_ticks if args.failure_enabled else 0.0,
        mttr_ticks=args.mttr_ticks,
        seed=args.seed,
    )

    run_benchmark(
        num_robots=args.robots,
        blocked_replan_seconds=args.block_replan,
        replan_cooldown_ticks=args.cooldown,
        target_completed=args.target,
        max_ticks=args.max_ticks,
        seed=args.seed,
        battery_config=battery_config,
        charging_config=charging_config,
        failure_config=failure_config,
    )