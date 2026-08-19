from __future__ import annotations

import argparse

import optuna

from simulation.config import BatteryConfig, ChargingConfig, FailureConfig
from simulation.metrics import Metrics
from simulation.robot import Robot, RobotStatus
from simulation.scheduler import CostBasedScheduler
from simulation.simulation import Simulation
from simulation.task_generator import TaskGenerator
from simulation.warehouse_layout import build_warehouse


DEFAULT_ROBOT_XS = [1, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24]
ROBOT_Y = 7

ROBOT_COLORS = [
    "#ef4444",
    "#3b82f6",
    "#10b981",
    "#f59e0b",
    "#8b5cf6",
    "#ec4899",
    "#14b8a6",
    "#f97316",
    "#64748b",
    "#84cc16",
    "#06b6d4",
    "#a855f7",
    "#f43f5e",
]


def create_robots(num_robots: int) -> list[Robot]:
    count = min(num_robots, len(DEFAULT_ROBOT_XS))

    return [
        Robot(
            id=f"R{i + 1}",
            x=DEFAULT_ROBOT_XS[i],
            y=ROBOT_Y,
            color=ROBOT_COLORS[i % len(ROBOT_COLORS)],
            status=RobotStatus.IDLE,
        )
        for i in range(count)
    ]


def make_task_generator(warehouse, seed: int | None):
    """Create TaskGenerator with seed if supported, fallback otherwise."""

    try:
        return TaskGenerator(warehouse, seed=seed)
    except TypeError:
        return TaskGenerator(warehouse)


def safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def build_v04_configs(trial: optuna.Trial, args, seed: int | None):
    """
    Build v0.4 configs.

    If args.search_v04 is True, battery/charging parameters are suggested by
    Optuna. Otherwise fixed CLI/default values are used.
    """

    if args.search_v04:
        empty_move_energy = trial.suggest_float(
            "empty_move_energy",
            0.3,
            1.5,
        )

        loaded_move_factor = trial.suggest_float(
            "loaded_move_factor",
            1.0,
            2.0,
        )

        loaded_move_energy = empty_move_energy * loaded_move_factor

        critical_battery = trial.suggest_float(
            "critical_battery",
            5.0,
            35.0,
        )

        opportunistic_charge_threshold = trial.suggest_float(
            "opportunistic_charge_threshold",
            20.0,
            80.0,
        )

        # Keep threshold meaningfully above critical battery.
        opportunistic_charge_threshold = max(
            opportunistic_charge_threshold,
            critical_battery + 5.0,
        )

        safety_margin = trial.suggest_float(
            "battery_safety_margin",
            0.0,
            15.0,
        )

        charger_capacity = trial.suggest_int(
            "charger_capacity",
            1,
            8,
        )

        charge_duration_ticks = trial.suggest_int(
            "charge_duration_ticks",
            3,
            30,
        )

        battery_config = BatteryConfig(
            capacity=args.battery_capacity,
            empty_move_energy=empty_move_energy,
            loaded_move_energy=loaded_move_energy,
            critical_battery=critical_battery,
            opportunistic_charge_threshold=opportunistic_charge_threshold,
            idle_ticks_before_opportunistic_charge=args.idle_opportunistic_ticks,
            safety_margin=safety_margin,
        )

        charging_config = ChargingConfig(
            capacity=charger_capacity,
            charge_duration_ticks=charge_duration_ticks,
        )

        if args.failure_enabled:
            mtbf_ticks = trial.suggest_float(
                "mtbf_ticks",
                300.0,
                5000.0,
            )
            mttr_ticks = trial.suggest_int(
                "mttr_ticks",
                5,
                60,
            )
        else:
            mtbf_ticks = 0.0
            mttr_ticks = args.mttr_ticks

        failure_config = FailureConfig(
            enabled=args.failure_enabled,
            mtbf_ticks=mtbf_ticks,
            mttr_ticks=mttr_ticks,
            seed=seed,
        )

        trial.set_user_attr("empty_move_energy", empty_move_energy)
        trial.set_user_attr("loaded_move_energy", loaded_move_energy)
        trial.set_user_attr("critical_battery", critical_battery)
        trial.set_user_attr(
            "opportunistic_charge_threshold",
            opportunistic_charge_threshold,
        )
        trial.set_user_attr("battery_safety_margin", safety_margin)
        trial.set_user_attr("charger_capacity", charger_capacity)
        trial.set_user_attr("charge_duration_ticks", charge_duration_ticks)

        if args.failure_enabled:
            trial.set_user_attr("mtbf_ticks", mtbf_ticks)
            trial.set_user_attr("mttr_ticks", mttr_ticks)

        return battery_config, charging_config, failure_config

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
        seed=seed,
    )

    return battery_config, charging_config, failure_config


def objective(trial: optuna.Trial, args) -> float:
    # ------------------------------------------------------------------
    # Search space
    # ------------------------------------------------------------------
    if args.fixed_robots is not None:
        num_robots = int(args.fixed_robots)
    else:
        num_robots = trial.suggest_int("num_robots", 8, 13)

    blocked_replan_seconds = trial.suggest_float(
        "blocked_replan_seconds",
        0.2,
        3.0,
    )

    replan_cooldown_ticks = trial.suggest_int(
        "replan_cooldown_ticks",
        1,
        8,
    )

    # ------------------------------------------------------------------
    # Setup simulation
    # ------------------------------------------------------------------
    warehouse = build_warehouse()
    robots = create_robots(num_robots)
    metrics = Metrics()

    seed = args.base_seed + trial.number if args.base_seed is not None else None

    battery_config, charging_config, failure_config = build_v04_configs(
        trial,
        args,
        seed,
    )

    task_generator = make_task_generator(warehouse, seed)

    sim = Simulation(
        warehouse=warehouse,
        robots=robots,
        tasks=[],
        tick_interval=0.3,
        scheduler=CostBasedScheduler(),
        task_generator=task_generator,
        metrics=metrics,
        blocked_replan_seconds=blocked_replan_seconds,
        replan_cooldown_ticks=replan_cooldown_ticks,
        battery_config=battery_config,
        charging_config=charging_config,
        failure_config=failure_config,
        seed=seed,
    )

    # ------------------------------------------------------------------
    # Run headless
    # ------------------------------------------------------------------
    ticks = 0

    while metrics.tasks_completed < args.target and ticks < args.max_ticks:
        with sim._lock:
            sim._tick()
        ticks += 1

    # ------------------------------------------------------------------
    # Calculate metrics
    # ------------------------------------------------------------------
    completed = metrics.tasks_completed
    assigned = max(metrics.tasks_assigned, 1)

    throughput = completed / max(ticks, 1)

    avg_wait = metrics.task_waiting_time_total / assigned

    avg_cycle = (
        metrics.task_completion_time_total / max(completed, 1)
        if completed > 0
        else float(args.max_ticks)
    )

    blocked_per_robot_tick = metrics.blocked_time_ticks / max(
        ticks * num_robots,
        1,
    )

    replans_per_task = metrics.replanning_count / max(completed, 1)

    average_battery = safe_divide(metrics.battery_sum, metrics.battery_samples)

    average_charger_wait = safe_divide(
        metrics.charger_wait_ticks,
        metrics.charger_wait_events,
    )

    # ------------------------------------------------------------------
    # Log everything to Optuna
    # ------------------------------------------------------------------
    trial.set_user_attr("num_robots", num_robots)
    trial.set_user_attr("completed", completed)
    trial.set_user_attr("ticks", ticks)
    trial.set_user_attr("throughput", throughput)
    trial.set_user_attr("avg_wait", avg_wait)
    trial.set_user_attr("avg_cycle", avg_cycle)
    trial.set_user_attr("blocked_ticks", metrics.blocked_time_ticks)
    trial.set_user_attr("blocked_per_robot_tick", blocked_per_robot_tick)
    trial.set_user_attr("replans", metrics.replanning_count)
    trial.set_user_attr("replans_per_task", replans_per_task)
    trial.set_user_attr("deadlock_resolutions", metrics.deadlock_resolutions)

    # v0.4 metrics.
    trial.set_user_attr("average_battery", average_battery)
    trial.set_user_attr("charging_events", metrics.charging_events)
    trial.set_user_attr("total_charging_ticks", metrics.total_charging_ticks)
    trial.set_user_attr("charger_wait_ticks", metrics.charger_wait_ticks)
    trial.set_user_attr("average_charger_wait", average_charger_wait)
    trial.set_user_attr(
        "battery_task_interruptions",
        metrics.battery_task_interruptions,
    )
    trial.set_user_attr(
        "failure_task_interruptions",
        metrics.failure_task_interruptions,
    )
    trial.set_user_attr("task_reassignments", metrics.task_reassignments)
    trial.set_user_attr("failed_robot_events", metrics.failed_robot_events)
    trial.set_user_attr(
        "failure_downtime_ticks",
        metrics.failure_downtime_ticks,
    )

    # ------------------------------------------------------------------
    # Penalize runs that did not complete enough tasks
    # ------------------------------------------------------------------
    if completed < args.target * 0.8:
        if args.objective == "throughput":
            return 0.0
        return float(args.max_ticks)

    # ------------------------------------------------------------------
    # Return selected objective
    # ------------------------------------------------------------------
    if args.objective == "throughput":
        return throughput

    if args.objective == "wait":
        return avg_wait

    if args.objective == "cycle":
        return avg_cycle

    if args.objective == "blocked":
        return blocked_per_robot_tick

    if args.objective == "replans":
        return replans_per_task

    if args.objective == "blocked_replans":
        return blocked_per_robot_tick + 0.25 * replans_per_task

    return throughput


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Optuna optimization for warehouse simulation."
    )

    parser.add_argument(
        "--trials",
        type=int,
        default=50,
        help="Number of optimization trials.",
    )
    parser.add_argument(
        "--target",
        type=int,
        default=50,
        help="Stop each run after this many completed tasks.",
    )
    parser.add_argument(
        "--max-ticks",
        type=int,
        default=20_000,
        help="Safety limit per run.",
    )
    parser.add_argument(
        "--base-seed",
        type=int,
        default=1000,
        help="Base RNG seed. Each trial uses base_seed + trial.number. Use -1 for no seed.",
    )
    parser.add_argument(
        "--objective",
        choices=[
            "throughput",
            "wait",
            "cycle",
            "blocked",
            "replans",
            "blocked_replans",
        ],
        default="throughput",
        help=(
            "Metric to optimize. "
            "throughput is maximized; all others are minimized."
        ),
    )
    parser.add_argument(
        "--fixed-robots",
        type=int,
        default=None,
        help="Fix number of robots instead of optimizing it.",
    )
    parser.add_argument(
        "--db",
        type=str,
        default="sqlite:///optuna_study.db",
        help="Optuna storage URL.",
    )

    # ------------------------------------------------------------------
    # v0.4 fixed configuration options
    # ------------------------------------------------------------------
    parser.add_argument(
        "--search-v04",
        action="store_true",
        help="Include selected v0.4 battery/charging parameters in the Optuna search.",
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
        default=0.7,
        help="Fixed empty movement energy when --search-v04 is not used.",
    )
    parser.add_argument(
        "--loaded-move-energy",
        type=float,
        default=1.0,
        help="Fixed loaded movement energy when --search-v04 is not used.",
    )
    parser.add_argument(
        "--critical-battery",
        type=float,
        default=20.0,
        help="Fixed critical battery threshold when --search-v04 is not used.",
    )
    parser.add_argument(
        "--opportunistic-charge-threshold",
        type=float,
        default=40.0,
        help="Fixed opportunistic threshold when --search-v04 is not used.",
    )
    parser.add_argument(
        "--idle-opportunistic-ticks",
        type=int,
        default=10,
        help="Idle ticks before opportunistic charging.",
    )
    parser.add_argument(
        "--battery-safety-margin",
        type=float,
        default=5.0,
        help="Fixed battery safety margin when --search-v04 is not used.",
    )
    parser.add_argument(
        "--charger-capacity",
        type=int,
        default=4,
        help="Fixed charger capacity when --search-v04 is not used.",
    )
    parser.add_argument(
        "--charge-duration-ticks",
        type=int,
        default=10,
        help="Fixed charge duration when --search-v04 is not used.",
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
        help="Fixed mean ticks between failures when --search-v04 is not used.",
    )
    parser.add_argument(
        "--mttr-ticks",
        type=int,
        default=25,
        help="Fixed repair duration in ticks when --search-v04 is not used.",
    )

    args = parser.parse_args()

    if args.base_seed is not None and args.base_seed < 0:
        args.base_seed = None

    direction = "maximize" if args.objective == "throughput" else "minimize"

    fixed_suffix = (
        f"_fixed{args.fixed_robots}"
        if args.fixed_robots is not None
        else ""
    )

    v04_suffix = "_v04search" if args.search_v04 else ""

    study_name = f"warehouse_{args.objective}{fixed_suffix}{v04_suffix}"
    storage = optuna.storages.RDBStorage(args.db)

    study = optuna.create_study(
        study_name=study_name,
        storage=storage,
        direction=direction,
        load_if_exists=True,
    )

    print(f"Objective:    {args.objective} ({direction})")
    print(f"Study name:   {study_name}")

    if args.fixed_robots is not None:
        print(f"Robots:       fixed at {args.fixed_robots}")
    else:
        print("Robots:       searching 8 to 13")

    print(f"Target:       {args.target} completed tasks")
    print(f"Max ticks:    {args.max_ticks}")
    print(f"Base seed:    {args.base_seed}")
    print(f"Trials:       {args.trials}")
    print(f"Search v0.4:  {args.search_v04}")
    print(f"Failures:     {args.failure_enabled}")
    print()

    study.optimize(
        lambda trial: objective(trial, args),
        n_trials=args.trials,
        show_progress_bar=True,
    )

    print()
    print("=" * 50)
    print("BEST TRIAL")
    print("=" * 50)
    print(f"Objective value: {study.best_value:.6f}")
    print()
    print("Parameters:")

    for key, value in study.best_params.items():
        print(f"  {key}: {value}")

    best = study.best_trial

    if best.user_attrs:
        print()
        print("Metrics:")

        for key, value in best.user_attrs.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.4f}")
            else:
                print(f"  {key}: {value}")

    print()
    print(f"Database: {args.db}")
    print(f"View with: optuna-dashboard {args.db}")


if __name__ == "__main__":
    main()