import argparse
import optuna
from simulation.warehouse_layout import build_warehouse
from simulation.robot import Robot, RobotStatus
from simulation.simulation import Simulation
from simulation.task_generator import TaskGenerator
from simulation.metrics import Metrics
from simulation.scheduler import CostBasedScheduler

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


def objective(trial: optuna.Trial, args) -> float:
    # ------------------------------------------------------------------
    # Search space
    # ------------------------------------------------------------------
    if args.fixed_robots is not None:
        num_robots = int(args.fixed_robots)
    else:
        num_robots = trial.suggest_int("num_robots", 8, 13)

    blocked_replan_seconds = trial.suggest_float("blocked_replan_seconds", 0.2, 3.0)
    replan_cooldown_ticks = trial.suggest_int("replan_cooldown_ticks", 1, 8)

    # ------------------------------------------------------------------
    # Setup simulation
    # ------------------------------------------------------------------
    warehouse = build_warehouse()
    robots = create_robots(num_robots)
    metrics = Metrics()

    seed = args.base_seed + trial.number if args.base_seed is not None else None
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
    # Calculate all metrics
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

    blocked_per_robot_tick = metrics.blocked_time_ticks / max(ticks * num_robots, 1)

    replans_per_task = metrics.replanning_count / max(completed, 1)

    # ------------------------------------------------------------------
    # Log everything to Optuna for dashboard inspection
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

    # ------------------------------------------------------------------
    # Penalize runs that did not complete enough tasks
    # ------------------------------------------------------------------
    if completed < args.target * 0.8:
        if args.objective == "throughput":
            return 0.0
        return float(args.max_ticks)

    # ------------------------------------------------------------------
    # Return the selected objective
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
        # Weighted combination.
        # blocked_per_robot_tick is a rate (small number).
        # replans_per_task is typically a small integer-ish number.
        # Adjust the 0.25 weight if you want replans to matter more/less.
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

    args = parser.parse_args()

    if args.base_seed is not None and args.base_seed < 0:
        args.base_seed = None

    direction = "maximize" if args.objective == "throughput" else "minimize"

    fixed_suffix = f"_fixed{args.fixed_robots}" if args.fixed_robots is not None else ""
    study_name = f"warehouse_{args.objective}{fixed_suffix}"

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
        print(f"Robots:       searching 8 to 13")

    print(f"Target:       {args.target} completed tasks")
    print(f"Max ticks:    {args.max_ticks}")
    print(f"Base seed:    {args.base_seed}")
    print(f"Trials:       {args.trials}")
    print()

    study.optimize(
        lambda trial: objective(trial, args),
        n_trials=args.trials,
        show_progress_bar=True,
    )

    # ------------------------------------------------------------------
    # Print best result
    # ------------------------------------------------------------------
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