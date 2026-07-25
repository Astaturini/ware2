import argparse
import optuna
from simulation.warehouse_layout import build_warehouse
from simulation.robot import Robot, RobotStatus
from simulation.simulation import Simulation
from simulation.task_generator import TaskGenerator
from simulation.metrics import Metrics
from simulation.scheduler import CostBasedScheduler

""" This script runs an Optuna optimization for the warehouse simulation.
    It optimizes the number of robots, blocked replan seconds, and replan cooldown ticks
    to maximize throughput or minimize average cycle time and throughput.
    Usage: python optimize_optuna.py --trials 50 --target 1000 --max-ticks 20000
    You can also specify a base RNG seed for reproducibility.
    The results are stored in an SQLite database (default: optuna_study.db) for
    later analysis and visualization with optuna-dashboard. To visualize the 
    results, run `optuna-dashboard sqlite:///optuna_study.db` 
    and open the provided URL in your browser.
    """

DEFAULT_ROBOT_XS = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 24]
ROBOT_Y = 7
ROBOT_COLORS = ["#ef4444", "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316"]

def create_robots(num_robots: int) -> list[Robot]:
    return [
        Robot(
            id=f"R{i+1}", 
            x=DEFAULT_ROBOT_XS[i], 
            y=ROBOT_Y, 
            color=ROBOT_COLORS[i % len(ROBOT_COLORS)], 
            status=RobotStatus.IDLE
        )
        for i in range(min(num_robots, len(DEFAULT_ROBOT_XS)))
    ]

def objective(trial: optuna.Trial, args) -> float:
    # 1. Define the search space
    num_robots = trial.suggest_int("num_robots", 2, 8)
    blocked_replan_seconds = trial.suggest_float("blocked_replan_seconds", 0.2, 3.0)
    replan_cooldown_ticks = trial.suggest_int("replan_cooldown_ticks", 1, 8)

    # 2. Setup Simulation
    warehouse = build_warehouse()
    robots = create_robots(num_robots)
    metrics = Metrics()
    
    # Use a deterministic seed per trial so results are reproducible
    seed = args.base_seed + trial.number if args.base_seed is not None else None
    try:
        task_generator = TaskGenerator(warehouse, seed=seed)
    except TypeError:
        task_generator = TaskGenerator(warehouse)

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

    # 3. Run Headless
    ticks = 0
    while metrics.tasks_completed < args.target and ticks < args.max_ticks:
        with sim._lock:
            sim._tick()
        ticks += 1

    # 4. Calculate Metrics
    throughput = metrics.tasks_completed / max(ticks, 1)
    avg_cycle = (
        metrics.task_completion_time_total / max(metrics.tasks_completed, 1) 
        if metrics.tasks_completed > 0 else args.max_ticks
    )

    # Log everything to Optuna for the dashboard visualizations
    trial.set_user_attr("completed", metrics.tasks_completed)
    trial.set_user_attr("ticks", ticks)
    trial.set_user_attr("avg_cycle", avg_cycle)
    trial.set_user_attr("blocked_ticks", metrics.blocked_time_ticks)
    trial.set_user_attr("replans", metrics.replanning_count)

    # 5. Handle deadlocks / failed runs
    # If the system deadlocked and couldn't complete at least 80% of the target,
    # heavily penalize it so Optuna learns to avoid these parameters.
    if metrics.tasks_completed < args.target * 0.8:
        return 0.0 if args.objective == "throughput" else float(args.max_ticks)

    # 6. Return Objective
    if args.objective == "throughput":
        return throughput
    elif args.objective == "cycle":
        return avg_cycle
    
    return throughput

def main():
    parser = argparse.ArgumentParser(description="Optuna Optimization for Warehouse Sim")
    parser.add_argument("--trials", type=int, default=50, help="Number of optimization trials")
    parser.add_argument("--target", type=int, default=1000, help="Target completed tasks per run")
    parser.add_argument("--max-ticks", type=int, default=20000, help="Safety limit per run")
    parser.add_argument("--base-seed", type=int, default=1000, help="Base RNG seed")
    parser.add_argument("--objective", choices=["throughput", "cycle"], default="throughput")
    parser.add_argument("--db", type=str, default="sqlite:///optuna_study.db")
    args = parser.parse_args()

    direction = "maximize" if args.objective == "throughput" else "minimize"
    
    # Use SQLite storage so we can use optuna-dashboard later
    storage = optuna.storages.RDBStorage(args.db)
    study = optuna.create_study(
        study_name="warehouse_sim_optimizer",
        storage=storage,
        direction=direction,
        load_if_exists=True # Allows you to resume or add more trials later
    )

    print(f"Starting Optuna optimization for {args.objective} ({direction})...")
    study.optimize(lambda trial: objective(trial, args), n_trials=args.trials, show_progress_bar=True)

    print("\n--- Best Trial ---")
    print(f"Value: {study.best_value:.4f}")
    print("Params:")
    for k, v in study.best_params.items():
        print(f"  {k}: {v}")

if __name__ == "__main__":
    main()