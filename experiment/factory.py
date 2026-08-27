from __future__ import annotations

import random

from simulation.config import BatteryConfig, ChargingConfig, FailureConfig
from simulation.conflict import (
    ConflictManager,
    LocalYieldConflictManager,
    PrioritizedReservationConflictManager,
    ZoneLockConflictManager,
)
from simulation.metrics import Metrics
from simulation.pathfinding import (
    AStarPathPlanner,
    BFSPathPlanner,
    PathPlanner,
)
from simulation.robot import Robot, RobotStatus
from simulation.scheduler import (
    AuctionScheduler,
    CostBasedScheduler,
    FIFOScheduler,
    PriorityScheduler,
    Scheduler,
    TotalCostScheduler,
)
from simulation.simulation import Simulation
from simulation.task_generator import TaskGenerator
from simulation.warehouse import Warehouse
from simulation.warehouse_layout import build_warehouse

from .config import ExperimentConfig


# Colorblind-safe palette (Okabe-Ito) for robots.
ROBOT_COLORS: list[str] = [
    "#E69F00",  # orange
    "#56B4E9",  # sky blue
    "#009E73",  # bluish green
    "#F0E442",  # yellow
    "#0072B2",  # blue
    "#D55E00",  # vermillion
    "#CC79A7",  # reddish purple
    "#999999",  # gray
    "#000000",  # black
]


# ------------------------------------------------------------------
# Path planner factory helpers
# ------------------------------------------------------------------

def create_path_planner_from_name(name: str) -> PathPlanner:
    """Create a path planner from a plain string name."""
    if name == "bfs":
        return BFSPathPlanner()

    if name == "astar":
        return AStarPathPlanner(weight=1.0)

    if name == "weighted_astar":
        return AStarPathPlanner(weight=1.2)

    raise ValueError(
        f"Unknown path planner: {name!r}. "
        "Expected one of: bfs, astar, weighted_astar."
    )


def create_path_planner(config: ExperimentConfig) -> PathPlanner:
    """Create the configured path planner."""
    name = getattr(config, "path_planner", "bfs")
    return create_path_planner_from_name(name)


# ------------------------------------------------------------------
# Scheduler factory helpers
# ------------------------------------------------------------------

def create_scheduler_from_name(
    name: str,
    path_planner: PathPlanner,
) -> Scheduler:
    """Create a scheduler from a plain string name."""
    if name == "baseline":
        return CostBasedScheduler(path_planner=path_planner)

    if name == "priority":
        return PriorityScheduler(path_planner=path_planner)

    if name == "fifo":
        return FIFOScheduler(path_planner=path_planner)

    if name == "total_cost":
        return TotalCostScheduler(path_planner=path_planner)

    if name == "auction":
        return AuctionScheduler(path_planner=path_planner)

    raise ValueError(
        f"Unknown scheduler: {name!r}. "
        "Expected one of: baseline, priority, fifo, total_cost, auction."
    )


def create_scheduler(
    config: ExperimentConfig,
    path_planner: PathPlanner,
) -> Scheduler:
    """Create the configured task allocation scheduler."""
    name = getattr(config, "scheduler", "baseline")

    if name == "total_cost":
        return TotalCostScheduler(
            path_planner=path_planner,
            empty_move_energy=config.empty_move_energy,
            loaded_move_energy=config.loaded_move_energy,
            safety_margin=config.battery_safety_margin,
            critical_battery=config.critical_battery,
        )

    return create_scheduler_from_name(name, path_planner)


# ------------------------------------------------------------------
# Conflict manager factory helpers
# ------------------------------------------------------------------

def create_conflict_manager_from_name(
    name: str,
    sim: Simulation,
) -> ConflictManager:
    """Create a conflict manager from a plain string name."""
    if name == "local_yield":
        return LocalYieldConflictManager(sim)

    if name == "zone_locks":
        return ZoneLockConflictManager(sim)

    if name == "priority_reservation":
        return PrioritizedReservationConflictManager(sim)

    raise ValueError(
        f"Unknown conflict manager: {name!r}. "
        "Expected one of: local_yield, zone_locks, priority_reservation."
    )


def create_conflict_manager(
    config: ExperimentConfig,
    sim: Simulation,
) -> ConflictManager:
    """Create the configured conflict manager."""
    name = getattr(config, "conflict_manager", "local_yield")
    return create_conflict_manager_from_name(name, sim)


# ------------------------------------------------------------------
# Robot creation
# ------------------------------------------------------------------

def generate_spawn_positions(
    num_robots: int,
    warehouse: Warehouse,
    seed: int,
) -> list[tuple[int, int]]:
    """Generate deterministic spawn positions using seeded RNG."""
    rng = random.Random(seed)

    passable_cells: list[tuple[int, int]] = []

    for y in range(warehouse.height):
        for x in range(warehouse.width):
            if not warehouse.is_blocked(x, y):
                passable_cells.append((x, y))

    if len(passable_cells) < num_robots:
        raise ValueError(
            f"Not enough passable cells for {num_robots} robots. "
            f"Only {len(passable_cells)} available."
        )

    rng.shuffle(passable_cells)
    return passable_cells[:num_robots]


def create_experiment_robots(
    num_robots: int,
    warehouse: Warehouse,
    seed: int,
) -> list[Robot]:
    """Create robots with deterministic seeded spawn positions."""
    if num_robots < 1:
        raise ValueError("num_robots must be at least 1.")

    spawn_positions = generate_spawn_positions(num_robots, warehouse, seed)

    robots: list[Robot] = []

    for i, (x, y) in enumerate(spawn_positions):
        robots.append(
            Robot(
                id=f"R{i + 1}",
                x=x,
                y=y,
                color=ROBOT_COLORS[i % len(ROBOT_COLORS)],
                status=RobotStatus.IDLE,
                path=[],
                current_task_id=None,
            )
        )

    return robots


# ------------------------------------------------------------------
# Simulation creation
# ------------------------------------------------------------------

def create_simulation_from_config(config: ExperimentConfig) -> Simulation:
    warehouse = build_warehouse()

    robots = create_experiment_robots(
        config.num_robots,
        warehouse,
        config.seed,
    )

    battery_config = BatteryConfig(
        capacity=config.battery_capacity,
        empty_move_energy=config.empty_move_energy,
        loaded_move_energy=config.loaded_move_energy,
        critical_battery=config.critical_battery,
        opportunistic_charge_threshold=config.opportunistic_charge_threshold,
        idle_ticks_before_opportunistic_charge=config.idle_ticks_before_opportunistic_charge,
        safety_margin=config.battery_safety_margin,
        empty_battery_recovery_ticks=config.empty_battery_recovery_ticks,
    )

    charging_config = ChargingConfig(
        capacity=config.charger_capacity,
        charge_duration_ticks=config.charge_duration_ticks,
    )

    failure_config = FailureConfig(
        enabled=config.failure_enabled,
        mtbf_ticks=config.mtbf_ticks,
        mttr_ticks=config.mttr_ticks,
        seed=config.seed,
        relocate_to_maintenance=config.relocate_to_maintenance,
    )

    path_planner = create_path_planner(config)
    scheduler = create_scheduler(config, path_planner)

    sim = Simulation(
        warehouse=warehouse,
        robots=robots,
        tasks=[],
        tick_interval=config.tick_interval,
        scheduler=scheduler,
        task_generator=TaskGenerator(warehouse, seed=config.seed),
        metrics=Metrics(),
        blocked_replan_seconds=config.blocked_replan_seconds,
        replan_cooldown_ticks=config.replan_cooldown_ticks,
        battery_config=battery_config,
        charging_config=charging_config,
        failure_config=failure_config,
        seed=config.seed,
        path_planner=path_planner,
    )

    # Conflict manager is injected after Simulation exists because the
    # conflict managers need a reference to the simulation.
    if hasattr(sim, "set_conflict_manager"):
        sim.set_conflict_manager(create_conflict_manager(config, sim))

    return sim