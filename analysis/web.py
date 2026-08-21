from __future__ import annotations

import math
import re
from typing import Any

import numpy as np
import pandas as pd

from .loader import DEFAULT_RUNS_DIR, list_runs, load_run
from .metrics import (
    blocked_episodes_from_events,
    distribution_stats,
    ensure_derived_timeseries,
    task_lifecycle_from_events,
    utilization_from_summary,
)

RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+$")

DEFAULT_MAX_POINTS = 2000
MAX_POINTS_LIMIT = 5000


class AnalysisApiError(Exception):
    pass


def _validate_run_id(run_id: str) -> None:
    if not RUN_ID_PATTERN.match(run_id):
        raise AnalysisApiError("Invalid run id.")


def _clean_number(value: Any) -> Any:
    try:
        f = float(value)
    except Exception:
        return value

    if math.isnan(f) or math.isinf(f):
        return None

    return f


def _sanitize(obj: Any) -> Any:
    """
    Make payloads JSON-safe.
    """
    if isinstance(obj, dict):
        return {str(key): _sanitize(value) for key, value in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [_sanitize(item) for item in obj]

    if isinstance(obj, np.integer):
        return int(obj)

    if isinstance(obj, np.floating):
        return _clean_number(float(obj))

    if isinstance(obj, np.bool_):
        return bool(obj)

    if isinstance(obj, float):
        return _clean_number(obj)

    if isinstance(obj, (int, str, bool)) or obj is None:
        return obj

    if isinstance(obj, pd.Timestamp):
        return str(obj)

    return str(obj)


def _parse_columns(columns: str | list[str]) -> list[str]:
    if isinstance(columns, str):
        return [column.strip() for column in columns.split(",") if column.strip()]

    return [str(column).strip() for column in columns if str(column).strip()]


def _clamp_max_points(max_points: Any) -> int:
    try:
        value = int(max_points)
    except Exception:
        value = DEFAULT_MAX_POINTS

    value = max(50, value)
    value = min(MAX_POINTS_LIMIT, value)

    return value


def _downsample(df: pd.DataFrame, column: str, max_points: int) -> list[list[float]]:
    if df.empty or column not in df.columns or "tick" not in df.columns:
        return []

    ticks = pd.to_numeric(df["tick"], errors="coerce")
    values = pd.to_numeric(df[column], errors="coerce")

    valid = ticks.notna() & values.notna()
    ticks = ticks[valid]
    values = values[valid]

    n = len(values)

    if n == 0:
        return []

    if n <= max_points:
        return [[int(t), float(v)] for t, v in zip(ticks, values)]

    bucket_size = n / max_points
    points: list[list[float]] = []

    for i in range(max_points):
        start = int(i * bucket_size)
        end = int((i + 1) * bucket_size)

        if start >= n:
            break

        end = min(end, n)

        if start >= end:
            continue

        tick_slice = ticks.iloc[start:end]
        value_slice = values.iloc[start:end]

        if value_slice.empty:
            continue

        points.append(
            [
                int(round(float(tick_slice.mean()))),
                float(value_slice.mean()),
            ]
        )

    return points


def _histogram(
    series: pd.Series, bins: int = 50
) -> dict[str, list[float] | list[int]]:
    clean = pd.to_numeric(series, errors="coerce").dropna()

    if clean.empty:
        return {
            "bin_centers": [],
            "bin_edges": [],
            "counts": [],
        }

    counts, edges = np.histogram(clean, bins=bins)
    centers = (edges[:-1] + edges[1:]) / 2.0

    return {
        "bin_centers": centers.tolist(),
        "bin_edges": edges.tolist(),
        "counts": counts.tolist(),
    }


def list_runs_payload(base_dir: str = DEFAULT_RUNS_DIR) -> dict[str, Any]:
    runs = list_runs(base_dir)

    return _sanitize(
        {
            "runs": runs,
        }
    )


def get_run_summary(
    run_id: str,
    base_dir: str = DEFAULT_RUNS_DIR,
) -> dict[str, Any]:
    _validate_run_id(run_id)

    try:
        run = load_run(run_id, base_dir)
    except FileNotFoundError as exc:
        raise AnalysisApiError(str(exc)) from exc

    if not run.summary:
        raise AnalysisApiError("Run has no summary yet.")

    return _sanitize(
        {
            "run_id": run.run_id,
            "config": run.config,
            "summary": run.summary,
        }
    )


def get_run_series(
    run_id: str,
    columns: str | list[str],
    base_dir: str = DEFAULT_RUNS_DIR,
    max_points: Any = DEFAULT_MAX_POINTS,
) -> dict[str, Any]:
    _validate_run_id(run_id)
    max_points = _clamp_max_points(max_points)

    try:
        run = load_run(run_id, base_dir)
    except FileNotFoundError as exc:
        raise AnalysisApiError(str(exc)) from exc

    df = ensure_derived_timeseries(run.timeseries)

    if df.empty:
        raise AnalysisApiError("Run has no time-series data.")

    requested = _parse_columns(columns)

    if not requested:
        requested = ["throughput_rolling_100"]

    series = []

    for column in requested:
        if column not in df.columns:
            continue

        points = _downsample(df, column, max_points)

        if not points:
            continue

        series.append(
            {
                "name": column,
                "points": points,
            }
        )

    if not series:
        raise AnalysisApiError("No valid time-series columns found.")

    return _sanitize(
        {
            "run_id": run_id,
            "max_points": max_points,
            "series": series,
        }
    )


def get_compare_series(
    run_ids: list[str],
    column: str,
    base_dir: str = DEFAULT_RUNS_DIR,
    max_points: Any = DEFAULT_MAX_POINTS,
) -> dict[str, Any]:
    max_points = _clamp_max_points(max_points)
    column = str(column).strip()

    if not column:
        raise AnalysisApiError("Column is required.")

    if not run_ids:
        raise AnalysisApiError("No run ids provided.")

    runs_payload = []

    for run_id in run_ids:
        _validate_run_id(run_id)

        try:
            run = load_run(run_id, base_dir)
        except FileNotFoundError:
            continue

        df = ensure_derived_timeseries(run.timeseries)

        if df.empty or column not in df.columns:
            continue

        points = _downsample(df, column, max_points)

        if not points:
            continue

        runs_payload.append(
            {
                "run_id": run_id,
                "points": points,
            }
        )

    if not runs_payload:
        raise AnalysisApiError("No valid runs found for comparison.")

    return _sanitize(
        {
            "column": column,
            "max_points": max_points,
            "runs": runs_payload,
        }
    )


def get_run_distributions(
    run_id: str,
    base_dir: str = DEFAULT_RUNS_DIR,
    bins: int = 50,
) -> dict[str, Any]:
    _validate_run_id(run_id)

    try:
        run = load_run(run_id, base_dir)
    except FileNotFoundError as exc:
        raise AnalysisApiError(str(exc)) from exc

    stats = distribution_stats(run)
    lifecycle = task_lifecycle_from_events(run.events)

    final_tick = int(run.summary.get("simulation_ticks", 0)) or None
    blocked_episodes = blocked_episodes_from_events(run.events, final_tick=final_tick)

    utilization_df = utilization_from_summary(run.summary)

    waiting_series = (
        lifecycle["waiting_time"].dropna()
        if not lifecycle.empty and "waiting_time" in lifecycle.columns
        else pd.Series(dtype=float)
    )

    cycle_series = (
        lifecycle["cycle_time"].dropna()
        if not lifecycle.empty and "cycle_time" in lifecycle.columns
        else pd.Series(dtype=float)
    )

    blocked_series = (
        blocked_episodes["duration_ticks"].dropna()
        if not blocked_episodes.empty and "duration_ticks" in blocked_episodes.columns
        else pd.Series(dtype=float)
    )

    payload = {
        "run_id": run_id,
        "stats": stats,
        "histograms": {
            "task_waiting_time": _histogram(waiting_series, bins=bins),
            "task_cycle_time": _histogram(cycle_series, bins=bins),
            "robot_blocked_episode_ticks": _histogram(blocked_series, bins=bins),
        },
        "robot_utilization": (
            utilization_df.to_dict(orient="records")
            if utilization_df is not None and not utilization_df.empty
            else None
        ),
    }

    return _sanitize(payload)