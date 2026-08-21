from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def ensure_derived_timeseries(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add derived analysis columns without modifying the recorded columns.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    if "tick" not in df.columns:
        df["tick"] = np.arange(len(df))

    if (
        "tasks_completed_total" not in df.columns
        and "tasks_completed_this_tick" in df.columns
    ):
        df["tasks_completed_total"] = df["tasks_completed_this_tick"].cumsum()

    if "throughput" not in df.columns:
        if "tasks_completed_this_tick" in df.columns:
            df["throughput"] = df["tasks_completed_this_tick"]
        elif "tasks_completed_total" in df.columns:
            df["throughput"] = df["tasks_completed_total"].diff().fillna(0.0)
        else:
            df["throughput"] = 0.0

    for window in (50, 100):
        df[f"throughput_rolling_{window}"] = (
            df["throughput"].rolling(window=window, min_periods=1).mean()
        )

    return df


def percentile_summary(series: pd.Series) -> dict[str, float]:
    if series is None or len(series) == 0:
        return {
            "count": 0,
            "mean": np.nan,
            "median": np.nan,
            "p90": np.nan,
            "p95": np.nan,
            "max": np.nan,
        }

    clean = pd.to_numeric(series, errors="coerce").dropna()

    if clean.empty:
        return {
            "count": 0,
            "mean": np.nan,
            "median": np.nan,
            "p90": np.nan,
            "p95": np.nan,
            "max": np.nan,
        }

    return {
        "count": int(clean.count()),
        "mean": float(clean.mean()),
        "median": float(clean.median()),
        "p90": float(clean.quantile(0.90)),
        "p95": float(clean.quantile(0.95)),
        "max": float(clean.max()),
    }


def _filter_id_frame(df: pd.DataFrame, column: str) -> pd.DataFrame:
    if df is None or df.empty or column not in df.columns:
        return pd.DataFrame()

    df = df.copy()
    df[column] = df[column].astype(str).str.strip()
    df = df[~df[column].isin({"", "nan", "None", "null"})]
    return df


def task_lifecycle_from_events(events: pd.DataFrame) -> pd.DataFrame:
    """
    Reconstruct task waiting time and cycle time from event data.

    waiting_time = first assigned tick - created tick
    cycle_time = completed tick - created tick
    """
    empty = pd.DataFrame(
        columns=[
            "created_tick",
            "first_assigned_tick",
            "completed_tick",
            "failed_tick",
            "waiting_time",
            "cycle_time",
        ]
    )

    if events is None or events.empty:
        return empty

    if "event_type" not in events.columns or "task_id" not in events.columns:
        return empty

    ev = _filter_id_frame(events, "task_id")

    if ev.empty or "tick" not in ev.columns:
        return empty

    created = (
        ev[ev["event_type"] == "task_created"]
        .groupby("task_id")["tick"]
        .min()
        .rename("created_tick")
    )

    assigned = (
        ev[ev["event_type"] == "task_assigned"]
        .groupby("task_id")["tick"]
        .min()
        .rename("first_assigned_tick")
    )

    completed = (
        ev[ev["event_type"] == "task_completed"]
        .groupby("task_id")["tick"]
        .min()
        .rename("completed_tick")
    )

    failed = (
        ev[ev["event_type"] == "task_failed"]
        .groupby("task_id")["tick"]
        .min()
        .rename("failed_tick")
    )

    lifecycle = pd.concat(
        [created, assigned, completed, failed],
        axis=1,
    )

    lifecycle["waiting_time"] = (
        lifecycle["first_assigned_tick"] - lifecycle["created_tick"]
    )

    lifecycle["cycle_time"] = (
        lifecycle["completed_tick"] - lifecycle["created_tick"]
    )

    return lifecycle


def blocked_episodes_from_events(
    events: pd.DataFrame,
    final_tick: int | None = None,
) -> pd.DataFrame:
    """
    Reconstruct robot blocking episodes from robot_blocked / robot_unblocked events.
    """
    columns = [
        "robot_id",
        "start_tick",
        "end_tick",
        "duration_ticks",
        "open_at_end",
    ]

    if events is None or events.empty:
        return pd.DataFrame(columns=columns)

    if "event_type" not in events.columns or "robot_id" not in events.columns:
        return pd.DataFrame(columns=columns)

    ev = _filter_id_frame(events, "robot_id")

    if ev.empty or "tick" not in ev.columns:
        return pd.DataFrame(columns=columns)

    ev = ev.sort_values("tick")

    open_starts: dict[str, int] = {}
    rows: list[dict[str, Any]] = []

    for row in ev.itertuples(index=False):
        event_type = getattr(row, "event_type", None)
        robot_id = getattr(row, "robot_id", "")
        tick = int(getattr(row, "tick", 0))

        if not robot_id:
            continue

        if event_type == "robot_blocked":
            if robot_id not in open_starts:
                open_starts[robot_id] = tick

        elif event_type == "robot_unblocked":
            if robot_id in open_starts:
                start_tick = open_starts.pop(robot_id)
                duration = max(0, tick - start_tick)
                rows.append(
                    {
                        "robot_id": robot_id,
                        "start_tick": start_tick,
                        "end_tick": tick,
                        "duration_ticks": duration,
                        "open_at_end": False,
                    }
                )

    if final_tick is not None:
        for robot_id, start_tick in open_starts.items():
            duration = max(0, int(final_tick) - int(start_tick))
            rows.append(
                {
                    "robot_id": robot_id,
                    "start_tick": start_tick,
                    "end_tick": final_tick,
                    "duration_ticks": duration,
                    "open_at_end": True,
                }
            )

    if not rows:
        return pd.DataFrame(columns=columns)

    return pd.DataFrame(rows, columns=columns)


def event_counts(events: pd.DataFrame) -> dict[str, int]:
    if events is None or events.empty or "event_type" not in events.columns:
        return {}

    return {str(event_type): int(count) for event_type, count in events.groupby("event_type").size().items()}


def utilization_from_summary(summary: dict[str, Any]) -> pd.DataFrame | None:
    if not isinstance(summary, dict):
        return None

    robot_utilization = summary.get("robot_utilization")

    if not isinstance(robot_utilization, dict):
        return None

    rows = []

    for robot_id, utilization in robot_utilization.items():
        rows.append(
            {
                "robot_id": str(robot_id),
                "utilization": float(utilization),
            }
        )

    if not rows:
        return None

    return pd.DataFrame(rows)


def robot_count_from_run(run: Any) -> int:
    summary = getattr(run, "summary", {}) or {}
    config = getattr(run, "config", {}) or {}

    count = summary.get("robot_count")
    if count is not None:
        return int(count)

    count = config.get("num_robots")
    if count is not None:
        return int(count)

    df = ensure_derived_timeseries(getattr(run, "timeseries", pd.DataFrame()))

    if df.empty:
        return 0

    state_columns = [
        "robots_active",
        "robots_idle",
        "robots_blocked",
        "robots_charging",
        "robots_to_charger",
        "robots_waiting_for_charger",
        "robots_failed",
    ]

    existing = [col for col in state_columns if col in df.columns]

    if not existing:
        return 0

    return int(df[existing].sum(axis=1).max())


def distribution_stats(run: Any) -> dict[str, Any]:
    """
    Build distribution statistics for one run.
    """
    ts = ensure_derived_timeseries(getattr(run, "timeseries", pd.DataFrame()))
    events = getattr(run, "events", pd.DataFrame())
    summary = getattr(run, "summary", {}) or {}

    final_tick = int(summary.get("simulation_ticks", 0)) or None

    lifecycle = task_lifecycle_from_events(events)
    blocked_episodes = blocked_episodes_from_events(events, final_tick=final_tick)

    waiting_times = (
        lifecycle["waiting_time"].dropna()
        if not lifecycle.empty and "waiting_time" in lifecycle.columns
        else pd.Series(dtype=float)
    )

    cycle_times = (
        lifecycle["cycle_time"].dropna()
        if not lifecycle.empty and "cycle_time" in lifecycle.columns
        else pd.Series(dtype=float)
    )

    blocked_durations = (
        blocked_episodes["duration_ticks"].dropna()
        if not blocked_episodes.empty and "duration_ticks" in blocked_episodes.columns
        else pd.Series(dtype=float)
    )

    stats: dict[str, Any] = {
        "task_waiting_time": percentile_summary(waiting_times),
        "task_cycle_time": percentile_summary(cycle_times),
        "robot_blocked_episode_ticks": percentile_summary(blocked_durations),
    }

    robot_count = robot_count_from_run(run)

    if not ts.empty and robot_count > 0 and "robots_active" in ts.columns:
        active_fraction = ts["robots_active"] / float(robot_count)
        stats["system_active_fraction"] = percentile_summary(active_fraction)
    else:
        stats["system_active_fraction"] = percentile_summary(pd.Series(dtype=float))

    utilization_df = utilization_from_summary(summary)

    if utilization_df is not None and not utilization_df.empty:
        stats["robot_utilization"] = percentile_summary(utilization_df["utilization"])
    else:
        stats["robot_utilization"] = percentile_summary(pd.Series(dtype=float))

    return stats