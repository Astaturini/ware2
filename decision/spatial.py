
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass, field
from typing import Any, cast

import pandas as pd

from analysis.loader import RunData, load_run

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SpatialCellLoad:
    x: int
    y: int
    blocked_events: int
    blocked_ticks: int


@dataclass(frozen=True)
class SpatialBlockageResult:
    run_id: str
    total_blocked_events: int
    events_with_coordinates: int
    coverage: float
    cells: list[SpatialCellLoad] = field(default_factory=list)

    @property
    def has_data(self) -> bool:
        return self.events_with_coordinates > 0

    def top_cells(
        self, n: int = 5, by: str = "blocked_ticks"
    ) -> list[SpatialCellLoad]:
        if by not in {"blocked_ticks", "blocked_events"}:
            raise ValueError("by must be 'blocked_ticks' or 'blocked_events'")
        return sorted(self.cells, key=lambda c: getattr(c, by), reverse=True)[:n]


def _parse_coordinates(details: Any) -> tuple[int, int] | None:
    if details is None or pd.isna(details):
        return None
    text = str(details).strip()
    if not text:
        return None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        return int(data["x"]), int(data["y"])
    except (KeyError, TypeError, ValueError):
        return None


def _pair_blocked_episodes(
    events: pd.DataFrame, final_tick: int | None
) -> list[dict[str, Any]]:
    """Pair robot_blocked/robot_unblocked events into episodes.

    Self-contained on purpose: mirrors analysis.metrics semantics
    (unclosed episodes censored at final_tick) without depending on
    the return type of blocked_episodes_from_events.
    """
    if events.empty or "event_type" not in events.columns:
        return []
    mask = events["event_type"].isin({"robot_blocked", "robot_unblocked"})
    ev = events.loc[mask, ["tick", "event_type", "robot_id"]].copy()
    if ev.empty:
        return []
    ev["tick"] = pd.to_numeric(ev["tick"], errors="coerce")
    ev = ev.dropna(subset=["tick"])
    ev["tick"] = ev["tick"].astype(int)
    # Stable sort keeps file order for identical ticks.
    ev = ev.sort_values("tick", kind="mergesort")

    episodes: list[dict[str, Any]] = []
    for robot_id, group in ev.groupby("robot_id", sort=False):
        start_tick: int | None = None
        for row in group.itertuples(index=False):
            tick = int(cast(Any, row.tick))
            if row.event_type == "robot_blocked":
                if start_tick is None:
                    start_tick = tick
                # Coalesced duplicate onset: keep the first.
            elif row.event_type == "robot_unblocked":
                if start_tick is not None:
                    episodes.append(
                        {
                            "robot_id": robot_id,
                            "start_tick": start_tick,
                            "end_tick": tick,
                            "duration_ticks": max(0, tick - start_tick),
                        }
                    )
                    start_tick = None
                # Stray unblocked without onset: ignore.
        if start_tick is not None:
            end_tick = final_tick if final_tick is not None else start_tick
            episodes.append(
                {
                    "robot_id": robot_id,
                    "start_tick": start_tick,
                    "end_tick": end_tick,
                    "duration_ticks": max(0, end_tick - start_tick),
                }
            )
    return episodes


def compute_spatial_blockage(run_data: RunData) -> SpatialBlockageResult:
    """Aggregate robot_blocked events into per-cell bottleneck statistics."""
    events = run_data.events
    run_id = str(run_data.run_id)

    if events.empty or "event_type" not in events.columns:
        return SpatialBlockageResult(run_id, 0, 0, 0.0)

    blocked = events[events["event_type"] == "robot_blocked"]
    total_blocked_events = int(len(blocked))
    if total_blocked_events == 0:
        return SpatialBlockageResult(run_id, 0, 0, 0.0)

    # 1) Parse onset coordinates and count events per cell.
    event_counts: dict[tuple[int, int], int] = {}
    onset_records: list[tuple[tuple[int, int], int, str]] = []
    events_with_coordinates = 0

    for _, row in blocked.iterrows():
        coord = _parse_coordinates(row.get("details"))
        if coord is None:
            continue
        events_with_coordinates += 1
        event_counts[coord] = event_counts.get(coord, 0) + 1
        try:
            tick = int(cast(Any, row["tick"]))
        except (KeyError, TypeError, ValueError):
            tick = 0
        robot_id = str(row.get("robot_id") or "")
        onset_records.append((coord, tick, robot_id))

    coverage = (
        events_with_coordinates / total_blocked_events
        if total_blocked_events
        else 0.0
    )
    if coverage < 1.0:
        logger.warning(
            "Run %s: %d/%d robot_blocked events have coordinates "
            "(coverage %.1f%%).",
            run_id,
            events_with_coordinates,
            total_blocked_events,
            coverage * 100.0,
        )

    # 2) Pair episodes and attribute durations to onset cells.
    final_tick: int | None = None
    summary = run_data.summary or {}
    raw_ticks = summary.get("simulation_ticks")
    if raw_ticks is not None:
        try:
            final_tick = int(raw_ticks)
        except (TypeError, ValueError):
            final_tick = None

    episodes = _pair_blocked_episodes(events, final_tick)
    episode_duration: dict[tuple[str, int], int] = {}
    for ep in episodes:
        key = (str(ep["robot_id"]), int(ep["start_tick"]))
        episode_duration[key] = episode_duration.get(key, 0) + int(
            ep["duration_ticks"]
        )

    cell_blocked_ticks: dict[tuple[int, int], int] = {c: 0 for c in event_counts}
    for coord, tick, robot_id in onset_records:
        duration = episode_duration.get((robot_id, tick))
        if duration is None:
            # Coalesced transitions can shift onset ticks by one.
            duration = episode_duration.get((robot_id, tick - 1))
        if duration is None:
            duration = episode_duration.get((robot_id, tick + 1))
        if duration:
            cell_blocked_ticks[coord] += duration

    cells = [
        SpatialCellLoad(
            x=x,
            y=y,
            blocked_events=event_counts[(x, y)],
            blocked_ticks=cell_blocked_ticks.get((x, y), 0),
        )
        for (x, y) in event_counts
    ]
    cells.sort(key=lambda c: c.blocked_ticks, reverse=True)

    return SpatialBlockageResult(
        run_id=run_id,
        total_blocked_events=total_blocked_events,
        events_with_coordinates=events_with_coordinates,
        coverage=coverage,
        cells=cells,
    )


def top_bottleneck_cells(
    run_data: RunData, top_n: int = 5
) -> list[SpatialCellLoad]:
    """Convenience wrapper used by report generators."""
    return compute_spatial_blockage(run_data).top_cells(top_n, by="blocked_ticks")


def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Spatial bottleneck analysis for a saved run."
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--base-dir", default=None, help="Runs directory override."
    )
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument(
        "--by",
        choices=["blocked_ticks", "blocked_events"],
        default="blocked_ticks",
        help="Ranking metric.",
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit JSON instead of a table."
    )
    args = parser.parse_args()

    from analysis.loader import DEFAULT_RUNS_DIR

    run_data = load_run(args.run_id, base_dir=args.base_dir or DEFAULT_RUNS_DIR)
    result = compute_spatial_blockage(run_data)

    if args.json:
        payload = {
            "run_id": result.run_id,
            "total_blocked_events": result.total_blocked_events,
            "events_with_coordinates": result.events_with_coordinates,
            "coverage": round(result.coverage, 4),
            "cells": [
                {
                    "x": c.x,
                    "y": c.y,
                    "blocked_events": c.blocked_events,
                    "blocked_ticks": c.blocked_ticks,
                }
                for c in result.cells
            ],
        }
        print(json.dumps(payload, indent=2))
        return

    print(f"Spatial blockage analysis - run {result.run_id}")
    print(
        f"Blocked events: {result.total_blocked_events} total, "
        f"{result.events_with_coordinates} with coordinates "
        f"(coverage {result.coverage * 100.0:.1f}%)"
    )
    if not result.has_data:
        print(
            "No spatial data. Pre-v0.7.2 runs do not record blockage "
            "coordinates."
        )
        return

    print(f"\nTop {args.top} bottleneck cells by {args.by}:")
    print(f"{'rank':>4} {'cell':>10} {'events':>7} {'blocked_ticks':>14}")
    for rank, cell in enumerate(result.top_cells(args.top, by=args.by), 1):
        print(
            f"{rank:>4} ({cell.x:>3},{cell.y:>3}) "
            f"{cell.blocked_events:>7} {cell.blocked_ticks:>14}"
        )


if __name__ == "__main__":
    _cli()