import argparse
import time
from simulation.warehouse_layout import build_warehouse
from simulation.robot import Robot, RobotStatus
from simulation.simulation import Simulation
from simulation.task_generator import TaskGenerator
from simulation.metrics import Metrics
from simulation.scheduler import CostBasedScheduler

"""This script runs a headless benchmark of the warehouse simulation.
   To use, run `python benchmark.py --help` for options.
   the format: python benchmark.py --robots 4 --block-replan 0.9 --cooldown 2 --target 50
   will run a benchmark with 4 robots, 0.9 seconds of blocked replan
   time, 2 ticks of replan cooldown, and a target of 50 completed tasks.
"""

def create_robots(num_robots: int) -> list[Robot]:
    # Spawn points as app.py has them,
    # but we can adjust if needed
    spawn_points = [
        (1, 7), (9, 7), (17, 7), (24, 7),
        (1, 20), (9, 20), (17, 20), (24, 20),
        (1, 0), (9, 0), (17, 0), (12, 1), (13, 0)
    ]
    colors = ["#ef4444", "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316"]
    
    robots = []
    for i in range(min(num_robots, len(spawn_points))):
        robots.append(Robot(
            id=f"R{i+1}",
            x=spawn_points[i][0],
            y=spawn_points[i][1],
            color=colors[i % len(colors)],
            status=RobotStatus.IDLE
        ))
    return robots

def run_benchmark(
    num_robots: int,
    blocked_replan_seconds: float,
    replan_cooldown_ticks: int,
    target_completed: int,
    max_ticks: int = 20000,
    seed: int | None = 42
):
    print(f"--- Starting Benchmark ---")
    print(f"Robots: {num_robots}")
    print(f"Replan Params: block={blocked_replan_seconds}s, cooldown={replan_cooldown_ticks} ticks")
    print(f"Target: {target_completed} completed tasks\n")
    
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
    )
    
    # Headless synchronous execution
    start_time = time.perf_counter()
    ticks = 0
    
    while metrics.tasks_completed < target_completed and ticks < max_ticks:
        with sim._lock:
            sim._tick()
        ticks += 1
        
    end_time = time.perf_counter()
    
    print(f"--- Results after {ticks} ticks ---")
    print(f"Wall-clock time: {end_time - start_time:.2f} seconds")
    print(f"Generated: {metrics.tasks_generated}")
    print(f"Completed: {metrics.tasks_completed}")
    print(f"Failed: {metrics.tasks_failed}")
    print(f"Throughput: {metrics.tasks_completed / max(ticks, 1):.3f} tasks/tick")
    print(f"Blocked Time: {metrics.blocked_time_ticks} ticks")
    print(f"Replan Events: {metrics.replanning_count}")
    print(f"Deadlock Resolutions: {metrics.deadlock_resolutions}")
    print(f"Avg Wait Time: {metrics.task_waiting_time_total / max(metrics.tasks_assigned, 1):.1f} ticks")
    print(f"Avg Cycle Time: {metrics.task_completion_time_total / max(metrics.tasks_completed, 1):.1f} ticks")
    
    print("\nPer-Robot Utilization:")
    for r_id in metrics.robot_total_ticks:
        busy = metrics.robot_busy_ticks.get(r_id, 0)
        total = metrics.robot_total_ticks.get(r_id, 1)
        blocked = metrics.robot_blocked_ticks.get(r_id, 0)
        replans = metrics.robot_replan_events.get(r_id, 0)
        print(f"  {r_id}: {busy/total:.1%} busy, {blocked} blocked ticks, {replans} replans")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Headless Simulation Benchmark")
    parser.add_argument("--robots", type=int, default=4, help="Number of robots")
    parser.add_argument("--block-replan", type=float, default=0.7, help="Blocked replan seconds")
    parser.add_argument("--cooldown", type=int, default=7, help="Replan cooldown ticks")
    parser.add_argument("--target", type=int, default=1000, help="Target completed tasks")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for task generator")
    
    args = parser.parse_args()
    
    run_benchmark(
        num_robots=args.robots,
        blocked_replan_seconds=args.block_replan,
        replan_cooldown_ticks=args.cooldown,
        target_completed=args.target,
        seed=args.seed
    )
    