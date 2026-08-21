from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_RUNS_DIR = "data/runs"


@dataclass
class RunData:
    run_id: str
    run_dir: Path
    config: dict[str, Any]
    summary: dict[str, Any]
    timeseries: pd.DataFrame
    events: pd.DataFrame


def runs_dir(base_dir: str | Path = DEFAULT_RUNS_DIR) -> Path:
    return Path(base_dir)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _read_timeseries(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _read_events(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def list_runs(base_dir: str | Path = DEFAULT_RUNS_DIR) -> list[dict[str, Any]]:
    base = runs_dir(base_dir)

    if not base.exists():
        return []

    runs: list[dict[str, Any]] = []

    for run_dir in sorted(base.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue

        config = _read_json(run_dir / "config.json")
        summary = _read_json(run_dir / "summary.json")

        runs.append(
            {
                "run_id": run_dir.name,
                "run_dir": str(run_dir),
                "config": config,
                "summary": summary,
            }
        )

    return runs


def load_run(
    run_id: str,
    base_dir: str | Path = DEFAULT_RUNS_DIR,
) -> RunData:
    base = runs_dir(base_dir)
    run_dir = base / run_id

    if not run_dir.exists():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")

    config = _read_json(run_dir / "config.json")
    summary = _read_json(run_dir / "summary.json")
    timeseries = _read_timeseries(run_dir / "timeseries.csv")
    events = _read_events(run_dir / "events.csv")

    return RunData(
        run_id=run_id,
        run_dir=run_dir,
        config=config,
        summary=summary,
        timeseries=timeseries,
        events=events,
    )