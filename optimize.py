from __future__ import annotations

import argparse
import csv
import itertools
import random
from statistics import mean

from simulation.warehouse_layout import build_warehouse
from simulation.robot import Robot, RobotStatus
from simulation.simulation import Simulation
from simulation.task_generator import TaskGenerator
from simulation.metrics import Metrics
from simulation.scheduler import CostBasedScheduler


DEFAULT_ROBOT_XS = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 24]
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
]

NUMERIC_KEYS = [
    "ticks",
    "generated",
    "completed",
    "failed",
    "blocked_ticks",
    "replans",
    "deadlock_resolutions",
    "avg_wait",
    "avg_cycle",
    "throughput",
]


def make_task_generator(warehouse, seed: int | None):
    """Create TaskGenerator with seed if supported.

    Your updated TaskGenerator supports seed.
    If you are still using the old deterministic one, this falls back safely.
    """
    try:
        return TaskGenerator(warehouse, seed=seed)
    except TypeError:
        return TaskGenerator(warehouse)


def create_robots(num_robots: int) -> list[Robot]:
    effective_count = min(num_robots, len(DEFAULT_ROBOT_XS))

    robots: list[Robot] = []

    for i in range(effective_count):
        robots.append(
            Robot(
                id=f"R{i + 1}",
                x=DEFAULT_ROBOT_XS[i],
                y=ROBOT_Y,
                color=ROBOT_COLORS[i % len(ROBOT_COLORS)],
                status=RobotStatus.IDLE,
            )
        )

    return robots


def run_once(
    params: dict,
    target_completed: int,
    max_ticks: int,
    seed: int | None,
) -> dict:
    warehouse = build_warehouse()

    num_robots = min(int(params["num_robots"]), len(DEFAULT_ROBOT_XS))
    robots = create_robots(num_robots)

    metrics = Metrics()
    task_generator = make_task_generator(warehouse, seed)

    sim = Simulation(
        warehouse=warehouse,
        robots=robots,
        tasks=[],
        tick_interval=0.3,
        scheduler=CostBasedScheduler(),
        task_generator=task_generator,
        metrics=metrics,
        blocked_replan_seconds=float(params["blocked_replan_seconds"]),
        replan_cooldown_ticks=int(params["replan_cooldown_ticks"]),
    )

    ticks = 0

    while metrics.tasks_completed < target_completed and ticks < max_ticks:
        with sim._lock:
            sim._tick()
        ticks += 1

    completed = metrics.tasks_completed
    assigned = max(metrics.tasks_assigned, 1)

    result = {
        "ticks": ticks,
        "generated": metrics.tasks_generated,
        "completed": completed,
        "failed": metrics.tasks_failed,
        "blocked_ticks": metrics.blocked_time_ticks,
        "replans": metrics.replanning_count,
        "deadlock_resolutions": metrics.deadlock_resolutions,
        "avg_wait": metrics.task_waiting_time_total / assigned,
        "avg_cycle": (
            metrics.task_completion_time_total / completed
            if completed > 0
            else float(max_ticks)
        ),
        "throughput": completed / max(ticks, 1),
    }

    return result


def compute_score(result: dict, objective: str, target_completed: int) -> float:
    """Convert metrics into a single score.

    Higher score is always better.
    For minimization objectives, we return negative values.
    """

    if result["completed"] <= 0:
        return -1_000_000.0

    missing = max(0, target_completed - result["completed"])

    # Strong penalty if the run did not complete enough tasks.
    penalty = missing * 100.0

    if objective == "throughput":
        return result["throughput"] - penalty

    if objective == "cycle":
        return -result["avg_cycle"] - penalty

    if objective == "wait":
        return -result["avg_wait"] - penalty

    if objective == "blocked":
        blocked_rate = result["blocked_ticks"] / max(result["ticks"], 1)
        return -blocked_rate - penalty

    if objective == "replans":
        return -result["replans"] - penalty

    raise ValueError(f"Unknown objective: {objective}")


def evaluate_params(
    params: dict,
    objective: str,
    target_completed: int,
    max_ticks: int,
    reps: int,
    base_seed: int | None,
) -> dict:
    scores: list[float] = []
    collected: dict[str, list[float]] = {key: [] for key in NUMERIC_KEYS}

    for rep in range(reps):
        seed = None if base_seed is None else base_seed + rep

        result = run_once(
            params=params,
            target_completed=target_completed,
            max_ticks=max_ticks,
            seed=seed,
        )

        score = compute_score(result, objective, target_completed)
        scores.append(score)

        for key in NUMERIC_KEYS:
            collected[key].append(result[key])

    summary = {
        "params": params,
        "score": mean(scores),
    }

    for key in NUMERIC_KEYS:
        summary[key] = mean(collected[key])

    return summary


def generate_grid(args: argparse.Namespace):
    robots = args.robots if args.robots else [2, 3, 4, 5]
    blocks = args.blocks if args.blocks else [0.3, 0.6, 0.9, 1.5]
    cooldowns = args.cooldowns if args.cooldowns else [1, 2, 3, 5]

    for robot_count, block_seconds, cooldown in itertools.product(
        robots,
        blocks,
        cooldowns,
    ):
        yield {
            "num_robots": robot_count,
            "blocked_replan_seconds": block_seconds,
            "replan_cooldown_ticks": cooldown,
        }


def generate_random(args: argparse.Namespace):
    rng = random.Random(args.search_seed)

    for _ in range(args.trials):
        yield {
            "num_robots": rng.randint(args.min_robots, args.max_robots),
            "blocked_replan_seconds": round(
                rng.uniform(args.min_block, args.max_block),
                3,
            ),
            "replan_cooldown_ticks": rng.randint(
                args.min_cooldown,
                args.max_cooldown,
            ),
        }


def write_results(results: list[dict], path: str) -> None:
    fieldnames = [
        "score",
        "num_robots",
        "blocked_replan_seconds",
        "replan_cooldown_ticks",
        "throughput",
        "avg_cycle",
        "avg_wait",
        "blocked_ticks",
        "replans",
        "deadlock_resolutions",
        "completed",
        "generated",
        "failed",
        "ticks",
    ]

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for result in results:
            writer.writerow(
                {
                    "score": round(result["score"], 6),
                    "num_robots": result["params"]["num_robots"],
                    "blocked_replan_seconds": result["params"]["blocked_replan_seconds"],
                    "replan_cooldown_ticks": result["params"]["replan_cooldown_ticks"],
                    "throughput": round(result["throughput"], 6),
                    "avg_cycle": round(result["avg_cycle"], 3),
                    "avg_wait": round(result["avg_wait"], 3),
                    "blocked_ticks": round(result["blocked_ticks"], 3),
                    "replans": round(result["replans"], 3),
                    "deadlock_resolutions": round(result["deadlock_resolutions"], 3),
                    "completed": round(result["completed"], 3),
                    "generated": round(result["generated"], 3),
                    "failed": round(result["failed"], 3),
                    "ticks": round(result["ticks"], 3),
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Headless parameter optimization for warehouse simulation."
    )

    parser.add_argument(
        "--method",
        choices=["grid", "random"],
        default="grid",
        help="Search method.",
    )

    parser.add_argument(
        "--objective",
        choices=["throughput", "cycle", "wait", "blocked", "replans"],
        default="throughput",
        help="Metric to optimize.",
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
        help="Safety limit for each simulation run.",
    )

    parser.add_argument(
        "--reps",
        type=int,
        default=1,
        help="Number of repetitions per parameter set. Use >1 for stochastic runs.",
    )

    parser.add_argument(
        "--base-seed",
        type=int,
        default=1000,
        help="Base seed. Use -1 for no fixed seed.",
    )

    parser.add_argument(
        "--robots",
        type=int,
        nargs="+",
        help="Grid search robot counts.",
    )

    parser.add_argument(
        "--blocks",
        type=float,
        nargs="+",
        help="Grid search blocked_replan_seconds values.",
    )

    parser.add_argument(
        "--cooldowns",
        type=int,
        nargs="+",
        help="Grid search replan_cooldown_ticks values.",
    )

    parser.add_argument(
        "--trials",
        type=int,
        default=30,
        help="Number of random search trials.",
    )

    parser.add_argument(
        "--search-seed",
        type=int,
        default=42,
        help="Seed for random search itself.",
    )

    parser.add_argument(
        "--min-robots",
        type=int,
        default=2,
        help="Minimum robots for random search.",
    )

    parser.add_argument(
        "--max-robots",
        type=int,
        default=8,
        help="Maximum robots for random search.",
    )

    parser.add_argument(
        "--min-block",
        type=float,
        default=0.2,
        help="Minimum blocked_replan_seconds for random search.",
    )

    parser.add_argument(
        "--max-block",
        type=float,
        default=3.0,
        help="Maximum blocked_replan_seconds for random search.",
    )

    parser.add_argument(
        "--min-cooldown",
        type=int,
        default=1,
        help="Minimum replan_cooldown_ticks for random search.",
    )

    parser.add_argument(
        "--max-cooldown",
        type=int,
        default=8,
        help="Maximum replan_cooldown_ticks for random search.",
    )

    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="How many top results to print.",
    )

    parser.add_argument(
        "--out",
        type=str,
        default="optimization_results.csv",
        help="Output CSV file.",
    )

    args = parser.parse_args()

    if args.base_seed is not None and args.base_seed < 0:
        args.base_seed = None

    if args.method == "grid":
        parameter_sets = list(generate_grid(args))
    else:
        parameter_sets = list(generate_random(args))

    print(f"Evaluating {len(parameter_sets)} parameter sets.")
    print(f"Objective: {args.objective}")
    print(f"Target completed tasks: {args.target}")
    print(f"Max ticks per run: {args.max_ticks}")
    print(f"Repetitions per set: {args.reps}")
    print()

    results: list[dict] = []

    for index, params in enumerate(parameter_sets, start=1):
        print(f"[{index}/{len(parameter_sets)}] {params}")

        summary = evaluate_params(
            params=params,
            objective=args.objective,
            target_completed=args.target,
            max_ticks=args.max_ticks,
            reps=args.reps,
            base_seed=args.base_seed,
        )

        results.append(summary)

        print(
            f"    score={summary['score']:.4f} "
            f"throughput={summary['throughput']:.4f} "
            f"cycle={summary['avg_cycle']:.1f} "
            f"wait={summary['avg_wait']:.1f} "
            f"blocked={summary['blocked_ticks']:.0f} "
            f"replans={summary['replans']:.0f} "
            f"completed={summary['completed']:.0f}"
        )

    results.sort(key=lambda item: item["score"], reverse=True)

    print()
    print("Top results:")
    print()

    for rank, result in enumerate(results[: args.top], start=1):
        params = result["params"]

        print(f"{rank}. score={result['score']:.4f}")
        print(f"   robots={params['num_robots']}")
        print(f"   blocked_replan_seconds={params['blocked_replan_seconds']}")
        print(f"   replan_cooldown_ticks={params['replan_cooldown_ticks']}")
        print(f"   throughput={result['throughput']:.4f}")
        print(f"   avg_cycle={result['avg_cycle']:.2f}")
        print(f"   avg_wait={result['avg_wait']:.2f}")
        print(f"   blocked_ticks={result['blocked_ticks']:.0f}")
        print(f"   replans={result['replans']:.0f}")
        print(f"   completed={result['completed']:.0f}")
        print()

    write_results(results, args.out)
    print(f"Saved full results to: {args.out}")


if __name__ == "__main__":
    main()