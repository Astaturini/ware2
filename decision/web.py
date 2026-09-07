from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import asdict, fields, is_dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, request

from analysis.loader import load_run
from decision.cost import CostConfig
from decision.kpis import compute_cost_kpis_for_run_id
from decision.spatial import compute_spatial_blockage


ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+$")


def _is_safe_id(value: str) -> bool:
    return bool(ID_PATTERN.match(str(value)))


def _sanitize(obj: Any) -> Any:
    """
    Make backend objects JSON-safe.

    NaN -> null
    Infinity -> null
    numpy scalars -> native Python values where possible
    Path -> POSIX string
    dataclasses -> dict
    """
    if obj is None:
        return None

    if isinstance(obj, Path):
        return obj.as_posix()

    if isinstance(obj, datetime):
        return obj.isoformat()

    if is_dataclass(obj):
        return _sanitize(
            {field.name: getattr(obj, field.name) for field in fields(obj)}
        )

    if isinstance(obj, dict):
        return {str(key): _sanitize(value) for key, value in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [_sanitize(item) for item in obj]

    if isinstance(obj, bool):
        return obj

    # Handles numpy scalar types when present.
    if hasattr(obj, "item"):
        try:
            return _sanitize(obj.item())
        except Exception:
            pass

    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None

    if isinstance(obj, (int, str)):
        return obj

    return str(obj)


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _mtime_iso(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).isoformat()
    except Exception:
        return None


def _generated_at_for_dir(path: Path) -> str | None:
    """
    Prefer generated_at from summary.json if it exists.
    Fall back to directory mtime.
    """
    summary = path / "summary.json"
    data = _read_json(summary)

    if isinstance(data, dict):
        value = data.get("generated_at")
        if value:
            return str(value)

    return _mtime_iso(path)


def _dir_artifact_summary(data_dir: Path, dirname: str) -> dict[str, Any]:
    empty = {
        "count": 0,
        "latest_id": None,
        "latest_generated_at": None,
    }

    root = data_dir / dirname
    if not root.exists():
        return empty

    entries = [
        path
        for path in root.iterdir()
        if path.is_dir() and _is_safe_id(path.name)
    ]

    if not entries:
        return empty

    latest = max(entries, key=lambda path: path.stat().st_mtime)

    return {
        "count": len(entries),
        "latest_id": latest.name,
        "latest_generated_at": _generated_at_for_dir(latest),
    }


def _reports_summary(data_dir: Path) -> dict[str, Any]:
    empty = {
        "count": 0,
        "latest_id": None,
        "latest_generated_at": None,
    }

    root = data_dir / "reports"
    if not root.exists():
        return empty

    files = [
        path
        for path in root.glob("*.md")
        if _is_safe_id(path.stem)
    ]

    if not files:
        return empty

    latest = max(files, key=lambda path: path.stat().st_mtime)

    return {
        "count": len(files),
        "latest_id": latest.stem,
        "latest_generated_at": _mtime_iso(latest),
    }


def _coerce_value(value: Any) -> Any:
    """
    Convert CSV strings into JSON-friendly values where possible.

    Empty strings become null.
    Numeric strings become numbers.
    NaN/Infinity become null.
    """
    if value is None:
        return None

    text = str(value).strip()
    if text == "":
        return None

    try:
        return int(text)
    except ValueError:
        pass

    try:
        number = float(text)
        return number if math.isfinite(number) else None
    except ValueError:
        return text


def _read_csv_page(
    path: Path,
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    total = 0

    if not path.exists():
        return rows, total

    start = (page - 1) * page_size

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)

        for index, row in enumerate(reader):
            if index >= start and len(rows) < page_size:
                clean_row: dict[str, Any] = {}

                for key, value in row.items():
                    if key is None:
                        continue
                    clean_row[str(key)] = _coerce_value(value)

                rows.append(clean_row)

            total = index + 1

    return rows, total


def _page_args() -> tuple[int, int]:
    try:
        page = max(1, int(request.args.get("page", 1)))
    except Exception:
        page = 1

    try:
        page_size = min(200, max(1, int(request.args.get("page_size", 50))))
    except Exception:
        page_size = 50

    return page, page_size


def _cost_config_from_request() -> CostConfig:
    """
    Temporary Phase 0 mechanism.

    Allows:
      GET /api/runs/<run_id>/cost-kpis?cost_config=<url-encoded-json>

    Later, the frontend will use a proper cost-config editor and job forms.
    """
    raw = request.args.get("cost_config")
    data: dict[str, Any] = {}

    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("cost_config must be valid URL-encoded JSON.") from exc

        if not isinstance(parsed, dict):
            raise ValueError("cost_config must be a JSON object.")

        data = parsed

    allowed_fields = {field.name for field in fields(CostConfig)}
    kwargs = {
        key: value
        for key, value in data.items()
        if key in allowed_fields
    }

    cost_config = CostConfig(**kwargs)

    sla_raw = request.args.get("sla_target_ticks")
    if sla_raw not in (None, ""):
        try:
            sla_target_ticks = int(sla_raw)
        except Exception as exc:
            raise ValueError("sla_target_ticks must be an integer.") from exc

        cost_config = replace(cost_config, sla_target_ticks=sla_target_ticks)

    return cost_config


def _list_artifact_dirs(data_dir: Path, dirname: str) -> list[Path]:
    root = data_dir / dirname

    if not root.exists():
        return []

    dirs = [
        path
        for path in root.iterdir()
        if path.is_dir() and _is_safe_id(path.name)
    ]

    dirs.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return dirs


def _get_artifact_dir(
    data_dir: Path,
    dirname: str,
    artifact_id: str,
) -> Path | None:
    if not _is_safe_id(artifact_id):
        return None

    path = data_dir / dirname / artifact_id
    return path if path.is_dir() else None


def _read_summary(path: Path) -> dict[str, Any]:
    data = _read_json(path / "summary.json")

    if isinstance(data, dict):
        return data

    return {}


def _paginate_list(
    items: list[Any],
    page: int,
    page_size: int,
) -> tuple[list[Any], int]:
    total = len(items)
    start = (page - 1) * page_size
    return items[start:start + page_size], total


def _read_json_list(path: Path) -> list[Any]:
    data = _read_json(path)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("trials", "rows", "results", "candidates"):
            value = data.get(key)
            if isinstance(value, list):
                return value

    return []


def _load_trials_from_artifact(path: Path) -> list[Any]:
    trials_path = path / "trials.json"

    if trials_path.exists():
        return _read_json_list(trials_path)

    summary = _read_summary(path)
    trials = summary.get("trials")

    if isinstance(trials, list):
        return trials

    return []


def _load_tornado_payload(study_dir: Path) -> dict[str, Any]:
    summary = _read_summary(study_dir)
    tornado = summary.get("tornado")

    if isinstance(tornado, dict):
        return tornado

    rows, _ = _read_csv_page(
        study_dir / "tornado.csv",
        page=1,
        page_size=1000,
    )

    if not rows:
        return {}

    grouped: dict[str, list[dict[str, Any]]] = {}

    for row in rows:
        target = row.get("target") or row.get("metric") or "unknown"
        grouped.setdefault(str(target), []).append(row)

    return grouped


def create_decision_blueprint(
    data_dir: Path | str,
    runs_dir: Path | str,
) -> Blueprint:
    """
    Create the decision API blueprint.

    data_dir:
        Root data directory, usually data/.

    runs_dir:
        Run artifact directory, usually data/runs/.
    """
    data_dir = Path(data_dir)
    runs_dir = Path(runs_dir)

    bp = Blueprint("decision_api", __name__)

    # ------------------------------------------------------------------
    # Helpers local to this blueprint
    # ------------------------------------------------------------------

    def _get_study_dir(study_id: str) -> Path | None:
        if not _is_safe_id(study_id):
            return None

        path = data_dir / "studies" / study_id
        return path if path.is_dir() else None

    def _get_report_path(report_id: str) -> Path | None:
        if not _is_safe_id(report_id):
            return None

        path = data_dir / "reports" / f"{report_id}.md"
        return path if path.is_file() else None

    # ------------------------------------------------------------------
    # Overview
    # ------------------------------------------------------------------

    @bp.get("/api/decision/overview")
    def decision_overview():
        payload = {
            "studies": _dir_artifact_summary(data_dir, "studies"),
            "reports": _reports_summary(data_dir),
            "monte_carlo": _dir_artifact_summary(data_dir, "monte_carlo"),
            "sensitivity": _dir_artifact_summary(data_dir, "sensitivity"),
            "optimizations": _dir_artifact_summary(data_dir, "optimizations"),
            "multiobjective": _dir_artifact_summary(data_dir, "multiobjective"),
            "robustness": _dir_artifact_summary(data_dir, "robustness"),
            "jobs": {
                "count": 0,
                "active_count": 0,
            },
        }

        return jsonify(_sanitize(payload))

    # ------------------------------------------------------------------
    # Studies
    # ------------------------------------------------------------------

    @bp.get("/api/decision/studies")
    def decision_studies():
        root = data_dir / "studies"
        studies: list[dict[str, Any]] = []

        if root.exists():
            dirs = [
                path
                for path in root.iterdir()
                if path.is_dir() and _is_safe_id(path.name)
            ]

            dirs.sort(key=lambda path: path.stat().st_mtime, reverse=True)

            for path in dirs:
                studies.append(
                    {
                        "study_id": path.name,
                        "generated_at": _generated_at_for_dir(path),
                        "config": _read_json(path / "study_config.json"),
                        "report_available": (path / "report.md").exists(),
                    }
                )

        return jsonify({"studies": _sanitize(studies)})

    @bp.get("/api/decision/studies/<study_id>")
    def decision_study_detail(study_id: str):
        study_dir = _get_study_dir(study_id)

        if study_dir is None:
            return jsonify({"error": "Study not found."}), 404

        payload = {
            "study_id": study_id,
            "generated_at": _generated_at_for_dir(study_dir),
            "config": _read_json(study_dir / "study_config.json"),
            "report_available": (study_dir / "report.md").exists(),
        }

        return jsonify(_sanitize(payload))

    @bp.get("/api/decision/studies/<study_id>/results")
    def decision_study_results(study_id: str):
        study_dir = _get_study_dir(study_id)

        if study_dir is None:
            return jsonify({"error": "Study not found."}), 404

        page, page_size = _page_args()
        rows, total_rows = _read_csv_page(
            study_dir / "results.csv",
            page=page,
            page_size=page_size,
        )

        payload = {
            "study_id": study_id,
            "page": page,
            "page_size": page_size,
            "total_rows": total_rows,
            "rows": rows,
        }

        return jsonify(_sanitize(payload))

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    @bp.get("/api/decision/reports")
    def decision_reports():
        root = data_dir / "reports"
        reports: list[dict[str, Any]] = []

        if root.exists():
            files = [
                path
                for path in root.glob("*.md")
                if _is_safe_id(path.stem)
            ]

            files.sort(key=lambda path: path.stat().st_mtime, reverse=True)

            for path in files:
                report_id = path.stem
                source_id = report_id.removesuffix("_report")

                reports.append(
                    {
                        "report_id": report_id,
                        "generated_at": _mtime_iso(path),
                        "source_type": "run",
                        "source_id": source_id,
                    }
                )

        return jsonify({"reports": _sanitize(reports)})

    @bp.get("/api/decision/reports/<report_id>")
    def decision_report_detail(report_id: str):
        path = _get_report_path(report_id)

        if path is None:
            return jsonify({"error": "Report not found."}), 404

        try:
            markdown = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            markdown = ""

        payload = {
            "report_id": report_id,
            "generated_at": _mtime_iso(path),
            "source_type": "run",
            "source_id": report_id.removesuffix("_report"),
            "markdown": markdown,
        }

        return jsonify(_sanitize(payload))

    # ------------------------------------------------------------------
    # Monte Carlo
    # ------------------------------------------------------------------

    @bp.get("/api/decision/monte-carlo")
    def decision_monte_carlo_list():
        items: list[dict[str, Any]] = []

        for path in _list_artifact_dirs(data_dir, "monte_carlo"):
            summary = _read_summary(path)

            items.append(
                {
                    "mc_id": path.name,
                    "generated_at": summary.get("generated_at") or _generated_at_for_dir(path),
                    "n_runs_requested": summary.get("n_runs_requested"),
                    "successful_runs": summary.get("successful_runs"),
                    "failed_runs": summary.get("failed_runs"),
                    "effective_sla_target_ticks": summary.get("effective_sla_target_ticks"),
                }
            )

        return jsonify({"monte_carlo": _sanitize(items)})

    @bp.get("/api/decision/monte-carlo/<mc_id>")
    def decision_monte_carlo_detail(mc_id: str):
        path = _get_artifact_dir(data_dir, "monte_carlo", mc_id)

        if path is None:
            return jsonify({"error": "Monte Carlo study not found."}), 404

        summary = _read_summary(path)

        payload = {
            "mc_id": mc_id,
            "generated_at": summary.get("generated_at") or _generated_at_for_dir(path),
            "summary": summary,
        }

        return jsonify(_sanitize(payload))

    @bp.get("/api/decision/monte-carlo/<mc_id>/results")
    def decision_monte_carlo_results(mc_id: str):
        path = _get_artifact_dir(data_dir, "monte_carlo", mc_id)

        if path is None:
            return jsonify({"error": "Monte Carlo study not found."}), 404

        page, page_size = _page_args()
        rows, total_rows = _read_csv_page(
            path / "results.csv",
            page=page,
            page_size=page_size,
        )

        payload = {
            "mc_id": mc_id,
            "page": page,
            "page_size": page_size,
            "total_rows": total_rows,
            "rows": rows,
        }

        return jsonify(_sanitize(payload))

    # ------------------------------------------------------------------
    # Sensitivity
    # ------------------------------------------------------------------

    @bp.get("/api/decision/sensitivity")
    def decision_sensitivity_list():
        items: list[dict[str, Any]] = []

        for path in _list_artifact_dirs(data_dir, "sensitivity"):
            summary = _read_summary(path)

            items.append(
                {
                    "study_id": path.name,
                    "generated_at": summary.get("generated_at") or _generated_at_for_dir(path),
                    "reps": summary.get("reps"),
                    "successful_runs": summary.get("successful_runs"),
                    "failed_runs": summary.get("failed_runs"),
                    "effective_sla_target_ticks": summary.get("effective_sla_target_ticks"),
                }
            )

        return jsonify({"sensitivity": _sanitize(items)})

    @bp.get("/api/decision/sensitivity/<study_id>")
    def decision_sensitivity_detail(study_id: str):
        path = _get_artifact_dir(data_dir, "sensitivity", study_id)

        if path is None:
            return jsonify({"error": "Sensitivity study not found."}), 404

        summary = _read_summary(path)

        payload = {
            "study_id": study_id,
            "generated_at": summary.get("generated_at") or _generated_at_for_dir(path),
            "summary": summary,
        }

        return jsonify(_sanitize(payload))

    @bp.get("/api/decision/sensitivity/<study_id>/results")
    def decision_sensitivity_results(study_id: str):
        path = _get_artifact_dir(data_dir, "sensitivity", study_id)

        if path is None:
            return jsonify({"error": "Sensitivity study not found."}), 404

        page, page_size = _page_args()
        rows, total_rows = _read_csv_page(
            path / "results.csv",
            page=page,
            page_size=page_size,
        )

        payload = {
            "study_id": study_id,
            "page": page,
            "page_size": page_size,
            "total_rows": total_rows,
            "rows": rows,
        }

        return jsonify(_sanitize(payload))

    @bp.get("/api/decision/sensitivity/<study_id>/tornado")
    def decision_sensitivity_tornado(study_id: str):
        path = _get_artifact_dir(data_dir, "sensitivity", study_id)

        if path is None:
            return jsonify({"error": "Sensitivity study not found."}), 404

        payload = {
            "study_id": study_id,
            "tornado": _load_tornado_payload(path),
        }

        return jsonify(_sanitize(payload))

    # ------------------------------------------------------------------
    # Optimization
    # ------------------------------------------------------------------

    @bp.get("/api/decision/optimizations")
    def decision_optimizations_list():
        items: list[dict[str, Any]] = []

        for path in _list_artifact_dirs(data_dir, "optimizations"):
            summary = _read_summary(path)

            items.append(
                {
                    "opt_id": path.name,
                    "generated_at": summary.get("generated_at") or _generated_at_for_dir(path),
                    "objective": summary.get("objective"),
                    "direction": summary.get("direction"),
                    "n_trials": summary.get("n_trials"),
                    "reps": summary.get("reps"),
                    "feasible_count": summary.get("feasible_count"),
                    "infeasible_count": summary.get("infeasible_count"),
                }
            )

        return jsonify({"optimizations": _sanitize(items)})

    @bp.get("/api/decision/optimizations/<opt_id>")
    def decision_optimization_detail(opt_id: str):
        path = _get_artifact_dir(data_dir, "optimizations", opt_id)

        if path is None:
            return jsonify({"error": "Optimization study not found."}), 404

        summary = _read_summary(path)

        payload = {
            "opt_id": opt_id,
            "generated_at": summary.get("generated_at") or _generated_at_for_dir(path),
            "summary": summary,
        }

        return jsonify(_sanitize(payload))

    @bp.get("/api/decision/optimizations/<opt_id>/trials")
    def decision_optimization_trials(opt_id: str):
        path = _get_artifact_dir(data_dir, "optimizations", opt_id)

        if path is None:
            return jsonify({"error": "Optimization study not found."}), 404

        page, page_size = _page_args()
        trials = _load_trials_from_artifact(path)
        rows, total_rows = _paginate_list(trials, page, page_size)

        payload = {
            "opt_id": opt_id,
            "page": page,
            "page_size": page_size,
            "total_rows": total_rows,
            "rows": rows,
        }

        return jsonify(_sanitize(payload))

    # ------------------------------------------------------------------
    # Multi-objective
    # ------------------------------------------------------------------

    @bp.get("/api/decision/multiobjective")
    def decision_multiobjective_list():
        items: list[dict[str, Any]] = []

        for path in _list_artifact_dirs(data_dir, "multiobjective"):
            summary = _read_summary(path)

            items.append(
                {
                    "study_id": path.name,
                    "generated_at": summary.get("generated_at") or _generated_at_for_dir(path),
                    "n_trials": summary.get("n_trials"),
                    "reps": summary.get("reps"),
                    "feasible_count": summary.get("feasible_count"),
                    "pareto_count": summary.get("pareto_count"),
                }
            )

        return jsonify({"multiobjective": _sanitize(items)})

    @bp.get("/api/decision/multiobjective/<study_id>")
    def decision_multiobjective_detail(study_id: str):
        path = _get_artifact_dir(data_dir, "multiobjective", study_id)

        if path is None:
            return jsonify({"error": "Multi-objective study not found."}), 404

        summary = _read_summary(path)

        payload = {
            "study_id": study_id,
            "generated_at": summary.get("generated_at") or _generated_at_for_dir(path),
            "summary": summary,
        }

        return jsonify(_sanitize(payload))

    @bp.get("/api/decision/multiobjective/<study_id>/trials")
    def decision_multiobjective_trials(study_id: str):
        path = _get_artifact_dir(data_dir, "multiobjective", study_id)

        if path is None:
            return jsonify({"error": "Multi-objective study not found."}), 404

        page, page_size = _page_args()
        trials = _load_trials_from_artifact(path)
        rows, total_rows = _paginate_list(trials, page, page_size)

        payload = {
            "study_id": study_id,
            "page": page,
            "page_size": page_size,
            "total_rows": total_rows,
            "rows": rows,
        }

        return jsonify(_sanitize(payload))

    @bp.get("/api/decision/multiobjective/<study_id>/pareto")
    def decision_multiobjective_pareto(study_id: str):
        path = _get_artifact_dir(data_dir, "multiobjective", study_id)

        if path is None:
            return jsonify({"error": "Multi-objective study not found."}), 404

        page, page_size = _page_args()
        pareto_csv = path / "pareto.csv"

        if pareto_csv.exists():
            rows, total_rows = _read_csv_page(
                pareto_csv,
                page=page,
                page_size=page_size,
            )
        else:
            summary = _read_summary(path)
            pareto_trials = summary.get("pareto_trials")

            if not isinstance(pareto_trials, list):
                pareto_trials = []

            rows, total_rows = _paginate_list(pareto_trials, page, page_size)

        payload = {
            "study_id": study_id,
            "page": page,
            "page_size": page_size,
            "total_rows": total_rows,
            "rows": rows,
        }

        return jsonify(_sanitize(payload))

    # ------------------------------------------------------------------
    # Robustness
    # ------------------------------------------------------------------

    @bp.get("/api/decision/robustness")
    def decision_robustness_list():
        items: list[dict[str, Any]] = []

        for path in _list_artifact_dirs(data_dir, "robustness"):
            summary = _read_summary(path)

            items.append(
                {
                    "robust_id": path.name,
                    "generated_at": summary.get("generated_at") or _generated_at_for_dir(path),
                    "reps": summary.get("reps"),
                    "objective": summary.get("objective"),
                    "direction": summary.get("direction"),
                    "min_pass_probability": summary.get("min_pass_probability"),
                    "successful_runs": summary.get("successful_runs"),
                    "failed_runs": summary.get("failed_runs"),
                    "recommended": summary.get("recommended"),
                }
            )

        return jsonify({"robustness": _sanitize(items)})

    @bp.get("/api/decision/robustness/<robust_id>")
    def decision_robustness_detail(robust_id: str):
        path = _get_artifact_dir(data_dir, "robustness", robust_id)

        if path is None:
            return jsonify({"error": "Robustness study not found."}), 404

        summary = _read_summary(path)

        payload = {
            "robust_id": robust_id,
            "generated_at": summary.get("generated_at") or _generated_at_for_dir(path),
            "summary": summary,
        }

        return jsonify(_sanitize(payload))

    @bp.get("/api/decision/robustness/<robust_id>/results")
    def decision_robustness_results(robust_id: str):
        path = _get_artifact_dir(data_dir, "robustness", robust_id)

        if path is None:
            return jsonify({"error": "Robustness study not found."}), 404

        page, page_size = _page_args()
        rows, total_rows = _read_csv_page(
            path / "results.csv",
            page=page,
            page_size=page_size,
        )

        payload = {
            "robust_id": robust_id,
            "page": page,
            "page_size": page_size,
            "total_rows": total_rows,
            "rows": rows,
        }

        return jsonify(_sanitize(payload))

    # ------------------------------------------------------------------
    # Run-level decision endpoints
    # ------------------------------------------------------------------

    @bp.get("/api/runs/<run_id>/cost-kpis")
    def run_cost_kpis(run_id: str):
        if not _is_safe_id(run_id):
            return jsonify({"error": "Invalid run id."}), 404

        try:
            cost_config = _cost_config_from_request()
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        try:
            kpis = compute_cost_kpis_for_run_id(
                run_id,
                cost_config,
                base_dir=str(runs_dir),
            )
        except FileNotFoundError:
            return jsonify({"error": "Run not found."}), 404
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify(_sanitize(kpis))

    @bp.get("/api/runs/<run_id>/spatial")
    def run_spatial(run_id: str):
        if not _is_safe_id(run_id):
            return jsonify({"error": "Invalid run id."}), 404

        try:
            top = max(1, min(100, int(request.args.get("top", 20))))
        except Exception:
            top = 20

        by = request.args.get("by", "blocked_ticks")
        if by not in {"blocked_ticks", "blocked_events"}:
            by = "blocked_ticks"

        try:
            run_data = load_run(run_id, base_dir=str(runs_dir))
            result = compute_spatial_blockage(run_data)
        except FileNotFoundError:
            return jsonify({"error": "Run not found."}), 404
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

        payload = {
            "run_id": result.run_id,
            "total_blocked_events": result.total_blocked_events,
            "events_with_coordinates": result.events_with_coordinates,
            "coverage": result.coverage,
            "has_data": result.has_data,
            "sort_by": by,
            "top_n": top,
            "top_cells": [
                {
                    "x": cell.x,
                    "y": cell.y,
                    "blocked_events": cell.blocked_events,
                    "blocked_ticks": cell.blocked_ticks,
                }
                for cell in result.top_cells(n=top, by=by)
            ],
        }

        return jsonify(_sanitize(payload))

    return bp