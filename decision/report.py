from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from analysis.loader import load_run
from decision.spatial import compute_spatial_blockage

from analysis.metrics import distribution_stats
from analysis.loader import DEFAULT_RUNS_DIR, load_run
import pandas as pd


def df_to_markdown(df: pd.DataFrame) -> str:
    """Simple dependency-free Markdown table generator."""
    if df.empty:
        return "*No successful runs to display.*"

    headers = df.columns.tolist()
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")

    for _, row in df.iterrows():
        row_str = []
        for h in headers:
            val = row[h]
            if pd.isna(val):
                row_str.append("N/A")
            elif isinstance(val, float):
                row_str.append(f"{val:.3f}")
            else:
                row_str.append(str(val))
        lines.append("| " + " | ".join(row_str) + " |")

    return "\n".join(lines)

def _spatial_summary_rows(df: pd.DataFrame, factor_keys: list[str]) -> pd.DataFrame:
    """One row per successful run with its top bottleneck cells.

    Requires results.csv to carry a run_id column linking each row back
    to its data/runs/<run_id>/ artifacts.
    """
    records: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        run_id = row.get("run_id")
        if run_id is None or pd.isna(run_id):
            continue
        run_id = str(run_id)
        try:
            run_data = load_run(run_id)
            result = compute_spatial_blockage(run_data)
        except FileNotFoundError:
            continue
        if not result.has_data:
            cells_text = "no spatial data"
        else:
            top = result.top_cells(3, by="blocked_ticks")
            cells_text = ", ".join(
                f"({c.x},{c.y}): {c.blocked_ticks}" for c in top
            )
        record: dict[str, Any] = {"run_id": run_id}
        for key in factor_keys:
            record[key] = row.get(key)
        record["Top bottleneck cells (cell: blocked ticks)"] = cells_text
        records.append(record)
    return pd.DataFrame(records)


def get_best_config(df: pd.DataFrame, metric: str, ascending: bool = True) -> pd.Series | None:
    if metric not in df.columns or df[metric].isna().all():
        return None

    valid_df = df.dropna(subset=[metric])
    if valid_df.empty:
        return None

    best_idx = valid_df[metric].idxmin() if ascending else valid_df[metric].idxmax()
    return valid_df.loc[best_idx] # pyright: ignore[reportReturnType]


def _failed_mask(df: pd.DataFrame) -> pd.Series:
    if "error" not in df.columns:
        return pd.Series(False, index=df.index)

    errors = df["error"]
    return errors.notna() & (errors.astype(str).str.strip() != "")


def generate_report(study_dir: str | Path) -> Path:
    study_dir = Path(study_dir)
    results_path = study_dir / "results.csv"
    config_path = study_dir / "study_config.json"

    if not results_path.exists():
        raise FileNotFoundError(f"Results file not found: {results_path}")
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    df = pd.read_csv(results_path)
    with open(config_path, "r", encoding="utf-8") as f:
        study_config: dict[str, Any] = json.load(f)

    failed_mask = _failed_mask(df)
    success_df = df[~failed_mask]
    failed_df = df[failed_mask]

    factors = study_config.get("factors", {})
    factor_keys = list(factors.keys())

    report_lines = [
        f"# Study Report: {study_config.get('study_name', 'Unnamed Study')}",
        f"\n*Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        f"*Study ID: {study_dir.name}*",
        "\n## 1. Experiment Design",
    ]

    if factors:
        report_lines.append("The following factors were varied in this Design of Experiments (DoE):")
        for factor, levels in factors.items():
            report_lines.append(f"- **{factor}**: {', '.join(map(str, levels))}")
    else:
        report_lines.append("No variable factors were defined (single scenario run).")

    report_lines.extend(
        [
            f"\nTotal combinations tested: {len(df)}",
            f"Successful runs: {len(success_df)}",
            f"Failed runs: {len(failed_df)}",
        ]
    )

    if not failed_df.empty:
        report_lines.append("\n### Failed Runs")
        for idx, row in failed_df.iterrows():
            combo_parts = []
            for k in factor_keys:
                combo_parts.append(f"{k}={row.get(k, '?')}")

            combo_str = ", ".join(combo_parts) if combo_parts else f"row {idx}"
            report_lines.append(f"- {combo_str}: {row.get('error', 'Unknown error')}")

    if success_df.empty:
        report_lines.extend(
            [
                "\n## 2. Results",
                "\n**WARNING:** All simulation runs failed. No KPI analysis could be performed.",
            ]
        )
    else:
        report_lines.append("\n## 2. KPI Analysis & Trade-offs")

        best_cost_per_task = get_best_config(success_df, "cost_per_task", ascending=True)
        best_sla = get_best_config(success_df, "sla_compliance_rate", ascending=False)
        best_total_cost = get_best_config(success_df, "total_operating_cost", ascending=True)
        best_throughput = get_best_config(success_df, "tasks_completed", ascending=False)

        report_lines.append("\n### Optimal Configurations")
        report_lines.append("Depending on your operational priority, the following configurations performed best:")

        def append_best(title: str, row: pd.Series | None, metric_name: str) -> None:
            if row is None:
                report_lines.append(f"- **{title}**: N/A (metric unavailable)")
            else:
                f_str = ", ".join([f"`{k}={row.get(k, '?')}`" for k in factor_keys])
                val = row.get(metric_name, "N/A")
                if isinstance(val, float):
                    val = f"{val:.4f}"
                report_lines.append(f"- **{title}**: {f_str} *(Value: {val})*")

        append_best("Lowest Cost per Task", best_cost_per_task, "cost_per_task")
        append_best("Highest SLA Compliance", best_sla, "sla_compliance_rate")
        append_best("Lowest Total Operating Cost", best_total_cost, "total_operating_cost")
        append_best("Highest Throughput", best_throughput, "tasks_completed")

        report_lines.append("\n### Trade-off Observations")

        if best_cost_per_task is not None and best_throughput is not None:
            is_same = all(best_cost_per_task.get(k) == best_throughput.get(k) for k in factor_keys)
            if not is_same:
                report_lines.append(
                    "- **Cost vs. Throughput Trade-off:** The configuration that minimizes cost per task is "
                    "*different* from the one that maximizes throughput. This indicates diminishing returns "
                    "on fleet size or scheduling complexity at higher capacities."
                )
            else:
                report_lines.append(
                    "- **Cost vs. Throughput:** The most cost-efficient configuration also maximized throughput. "
                    "The system has not yet hit severe congestion bottlenecks for the tested factor levels."
                )

        if best_sla is not None and best_cost_per_task is not None:
            sla_best_rate = best_sla.get("sla_compliance_rate", 0.0)
            cost_best_rate = best_cost_per_task.get("sla_compliance_rate", 0.0)
            if sla_best_rate > cost_best_rate:
                report_lines.append(
                    f"- **SLA vs. Cost:** Achieving the highest SLA compliance ({sla_best_rate:.1%}) requires a "
                    f"different, likely more expensive, configuration than the absolute lowest cost per task "
                    f"({cost_best_rate:.1%} compliance)."
                )
    
        report_lines.append("\n## 3. Spatial Bottleneck Analysis")
        if "run_id" not in success_df.columns:
            report_lines.append(
                "_Skipped: results.csv has no `run_id` column. "
                "Update decision/study.py to record the run ID per row._"
            )
        else:
            if (
                "layout_preset" in factor_keys
                and success_df["layout_preset"].nunique() > 1
            ):
                report_lines.append(
                    "_Warning: this study varies `layout_preset`; bottleneck "
                    "cells are not comparable across runs._"
                )
            spatial_df = _spatial_summary_rows(success_df, factor_keys)
            if spatial_df.empty:
                report_lines.append(
                    "No spatial data available. Runs may predate v0.7.2 "
                    "coordinate recording, or run artifacts may be missing."
                )
            else:
                report_lines.append(df_to_markdown(spatial_df))
                report_lines.append(
                    "\n_Blocked ticks are attributed to the cell where blocking "
                    "started. Hotspots near chargers indicate capacity problems; "
                    "hotspots at aisle intersections indicate traffic-control "
                    "problems._"
                )

    report_lines.append("\n## 4. Raw Data Summary")

    cols_to_show = factor_keys + [
        "tasks_completed",
        "total_operating_cost",
        "cost_per_task",
        "sla_compliance_rate",
    ]
    cols_to_show = [c for c in cols_to_show if c in success_df.columns]

    if cols_to_show:
        report_lines.append("\n" + df_to_markdown(success_df[cols_to_show]))
    else:
        report_lines.append("\nNo numerical KPI columns found to summarize.")
        


    report_path = study_dir / "report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    return report_path

def generate_run_report(run_id: str, base_dir: str | None = None) -> Path:
    """Generate a Markdown engineering report for a single saved run.

    Reports are written to data/reports/, never inside data/runs/ —
    run artifacts are immutable by design.
    """
    run_data = load_run(run_id, base_dir=base_dir or DEFAULT_RUNS_DIR)
    summary = run_data.summary or {}
    config = run_data.config or {}

    lines: list[str] = [
        f"# Run Report: {run_id}",
        f"\n*Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        "\n## 1. Configuration",
    ]

    config_keys = [
        "num_robots", "seed", "stop_mode", "target_tasks", "max_ticks",
        "scheduler", "path_planner", "conflict_manager",
        "demand_mode", "layout_preset", "charger_capacity",
        "failure_enabled", "fast_mode",
    ]
    config_rows = [
        {"parameter": k, "value": config.get(k, "N/A")} for k in config_keys
    ]
    lines.append("\n" + df_to_markdown(pd.DataFrame(config_rows)))

    lines.append("\n## 2. Performance KPIs")
    kpi_keys = [
        "stop_reason", "simulation_ticks", "tasks_created", "tasks_assigned",
        "tasks_completed", "tasks_failed", "average_throughput",
        "average_wait_time", "average_cycle_time", "average_robot_utilization",
        "total_replans", "total_blocked_ticks", "blocked_time_seconds",
        "charging_events", "charger_wait_ticks",
        "battery_task_interruptions", "failure_task_interruptions",
        "task_reassignments",
    ]
    kpi_rows = [{"metric": k, "value": summary.get(k, "N/A")} for k in kpi_keys]
    lines.append("\n" + df_to_markdown(pd.DataFrame(kpi_rows)))

    lines.append("\n## 3. Distributions")
    try:
        stats = distribution_stats(run_data)  
    except Exception as exc:
        stats = {}
        lines.append(f"\nDistribution analysis unavailable: {exc}")
    dist_rows = []
    for name, s in stats.items():
        if not isinstance(s, dict):
            continue
        dist_rows.append(
            {
                "metric": name,
                "count": s.get("count", "N/A"),
                "mean": s.get("mean", "N/A"),
                "median": s.get("median", "N/A"),
                "p90": s.get("p90", "N/A"),
                "p95": s.get("p95", "N/A"),
                "max": s.get("max", "N/A"),
            }
        )
    if dist_rows:
        lines.append("\n" + df_to_markdown(pd.DataFrame(dist_rows)))

    lines.append("\n## 4. Spatial Bottleneck Analysis")
    result = compute_spatial_blockage(run_data)
    if not result.has_data:
        lines.append(
            "No spatial data. This run predates v0.7.2 coordinate "
            "recording, or no robot was ever blocked."
        )
    else:
        lines.append(
            f"Coverage: {result.events_with_coordinates}/"
            f"{result.total_blocked_events} blocked events "
            f"({result.coverage:.1%})."
        )
        cell_rows = [
            {
                "rank": rank,
                "cell": f"({c.x}, {c.y})",
                "blocked_events": c.blocked_events,
                "blocked_ticks": c.blocked_ticks,
            }
            for rank, c in enumerate(result.top_cells(5, by="blocked_ticks"), 1)
        ]
        lines.append("\n" + df_to_markdown(pd.DataFrame(cell_rows)))
        lines.append(
            "\n_Blocked ticks are attributed to the cell where blocking "
            "started. Hotspots near chargers indicate capacity problems; "
            "hotspots at aisle intersections indicate traffic-control "
            "problems._"
        )

    reports_dir = Path("data/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"{run_id}_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return report_path




def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Markdown engineering reports from studies or single runs."
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument(
        "--study-dir",
        help="Path to the study directory (e.g., data/studies/20260903_.../)",
    )
    target.add_argument(
        "--run-id",
        help="Single run id under data/runs/ (e.g., 20260903_065649_ef7246)",
    )
    parser.add_argument(
        "--base-dir",
        default=None,
        help="Runs directory override (only used with --run-id).",
    )
    args = parser.parse_args()
    if args.study_dir:
        report_path = generate_report(args.study_dir)
    else:
        report_path = generate_run_report(args.run_id, base_dir=args.base_dir)
    print(f"Report generated: {report_path}")


if __name__ == "__main__":
    main()