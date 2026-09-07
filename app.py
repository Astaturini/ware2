from __future__ import annotations

import re
import shutil
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from analysis.web import (
    AnalysisApiError,
    get_compare_series,
    get_run_distributions,
    get_run_series,
    get_run_summary,
    list_runs_payload,
)
from decision.jobs import DecisionJobManager, create_decision_jobs_blueprint
from decision.web import create_decision_blueprint
from experiment.config import ExperimentConfig
from experiment.factory import create_simulation_from_config
from experiment.runner import ExperimentRunner


def create_app(
    base_data_dir: str = "data/runs",
    start_simulation: bool = False,
) -> Flask:
    base_dir = Path(base_data_dir)
    data_dir = base_dir.parent

    default_simulation = create_simulation_from_config(
        ExperimentConfig.default()
    )

    holder = {
        "simulation": default_simulation,
        "runner": None,
    }

    decision_job_manager = DecisionJobManager(
        data_dir=data_dir,
        runs_dir=base_dir,
        max_workers=1,
    )

    app = Flask(__name__)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/state")
    def state():
        simulation = holder["simulation"]
        payload = simulation.get_state()

        runner = holder.get("runner")

        if runner is None:
            payload["experiment"] = {
                "active": False,
                "finished": False,
                "runId": None,
                "stopReason": None,
                "fastMode": False,
            }
        else:
            payload["experiment"] = runner.get_state()

        return jsonify(payload)

    @app.post("/api/pause")
    def pause():
        simulation = holder["simulation"]
        simulation.pause()
        return jsonify({"paused": simulation.is_paused})

    @app.post("/api/resume")
    def resume():
        simulation = holder["simulation"]
        simulation.resume()
        return jsonify({"paused": simulation.is_paused})

    @app.post("/api/reset")
    def reset():
        runner = holder.get("runner")

        if runner is not None:
            runner.stop("reset_by_user")

        holder["simulation"] = create_simulation_from_config(
            ExperimentConfig.default()
        )
        holder["runner"] = None

        return jsonify({"paused": holder["simulation"].is_paused})

    # --------------------------------------------------------------
    # Experiment lifecycle
    # --------------------------------------------------------------

    @app.post("/api/experiment/start")
    def experiment_start():
        existing = holder.get("runner")

        if existing is not None and existing.is_active:
            return jsonify({"error": "An experiment is already running."}), 409

        payload = request.get_json(force=True, silent=True) or {}

        try:
            config = ExperimentConfig.from_dict(payload)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        runner = ExperimentRunner(base_dir=str(base_dir))

        try:
            run_id = runner.start(config, create_simulation_from_config)
        except (ValueError, RuntimeError) as exc:
            return jsonify({"error": str(exc)}), 400

        holder["runner"] = runner
        holder["simulation"] = runner.sim

        return jsonify({"runId": run_id})

    @app.get("/api/experiment/state")
    def experiment_state():
        runner = holder.get("runner")

        if runner is None:
            return jsonify(
                {
                    "active": False,
                    "finished": False,
                    "runId": None,
                    "stopReason": None,
                    "fastMode": False,
                }
            )

        return jsonify(runner.get_state())

    @app.post("/api/experiment/stop")
    def experiment_stop():
        runner = holder.get("runner")

        if runner is None:
            return jsonify({"error": "No experiment has been started."}), 404

        runner.stop("stopped_by_user")
        return jsonify(runner.get_state())

    @app.get("/api/experiment/summary")
    def experiment_summary():
        runner = holder.get("runner")

        if runner is None:
            return jsonify({"error": "No experiment has been started."}), 404

        summary = runner.get_summary()

        if summary is None:
            return jsonify({"error": "Experiment has not finished yet."}), 409

        return jsonify(summary)

    # --------------------------------------------------------------
    # Analysis API
    # --------------------------------------------------------------

    @app.get("/api/runs")
    def api_runs():
        return jsonify(list_runs_payload(str(base_dir)))

    @app.delete("/api/runs/<run_id>")
    def api_delete_run(run_id: str):
        if not re.match(r"^[A-Za-z0-9_\-]+$", run_id):
            return jsonify({"error": "Invalid run id."}), 400

        run_dir = base_dir / run_id

        if not run_dir.exists():
            return jsonify({"error": "Run not found."}), 404

        try:
            shutil.rmtree(run_dir)
            return jsonify({"success": True, "runId": run_id})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.get("/api/runs/compare/series")
    def api_compare_series():
        runs_param = request.args.get("runs", "")
        column = request.args.get("column", "throughput_rolling_100")
        max_points = request.args.get("max_points", 2000)

        run_ids = [
            part.strip()
            for part in runs_param.split(",")
            if part.strip()
        ]

        if not run_ids:
            return jsonify({"error": "No run ids provided."}), 400

        try:
            return jsonify(
                get_compare_series(run_ids, column, str(base_dir), max_points)
            )
        except AnalysisApiError as exc:
            return jsonify({"error": str(exc)}), 404

    @app.get("/api/runs/<run_id>/summary")
    def api_run_summary(run_id: str):
        try:
            return jsonify(get_run_summary(run_id, str(base_dir)))
        except AnalysisApiError as exc:
            return jsonify({"error": str(exc)}), 404

    @app.get("/api/runs/<run_id>/series")
    def api_run_series(run_id: str):
        columns = request.args.get("columns", "")
        max_points = request.args.get("max_points", 2000)

        try:
            return jsonify(
                get_run_series(run_id, columns, str(base_dir), max_points)
            )
        except AnalysisApiError as exc:
            return jsonify({"error": str(exc)}), 404

    @app.get("/api/runs/<run_id>/distributions")
    def api_run_distributions(run_id: str):
        bins = request.args.get("bins", 50)

        try:
            bins = max(10, min(100, int(bins)))
        except Exception:
            bins = 50

        try:
            return jsonify(get_run_distributions(run_id, str(base_dir), bins))
        except AnalysisApiError as exc:
            return jsonify({"error": str(exc)}), 404

    # --------------------------------------------------------------
    # Decision API (Read-only artifacts)
    # --------------------------------------------------------------

    app.register_blueprint(
        create_decision_blueprint(
            data_dir=data_dir,
            runs_dir=base_dir,
        )
    )

    # --------------------------------------------------------------
    # Decision Jobs API (Asynchronous execution)
    # --------------------------------------------------------------

    app.register_blueprint(
        create_decision_jobs_blueprint(decision_job_manager)
    )

    if start_simulation:
        default_simulation.start()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=False, use_reloader=False)