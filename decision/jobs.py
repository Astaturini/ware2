from __future__ import annotations

import json
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, request

from decision.cost import CostConfig
from decision.execution import (
    ALLOWED_TRIAL_ARTIFACT_MODES,
    MAX_MAX_WORKERS,
)


ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+$")

SUPPORTED_DECISION_JOB_MODULES = {
    "study",
    "report",
    "spatial",
    "monte_carlo",
    "sensitivity",
    "optimizer",
    "multiobjective",
    "robustness",
}

SUPPORTED_OPTIMIZER_OBJECTIVES = {
    "cost_per_task",
    "p95_cycle_time",
    "average_throughput",
    "tasks_completed",
}

SUPPORTED_METRICS = {
    "cost_per_task",
    "p95_cycle_time",
    "average_cycle_time",
    "average_throughput",
    "tasks_completed",
    "sla_compliance_rate",
    "total_blocked_ticks",
}

SUPPORTED_DIRECTIONS = {
    "minimize",
    "maximize",
}


class DecisionJobError(ValueError):
    """
    Bad request / invalid job configuration.
    """


class DecisionJobNotFoundError(DecisionJobError):
    """
    Job id does not exist.
    """


class DecisionJobConflictError(DecisionJobError):
    """
    Job exists but the requested action is invalid for its current state.
    """


def _is_safe_id(value: str) -> bool:
    return bool(ID_PATTERN.match(str(value)))


def _now_iso() -> str:
    return datetime.now().isoformat()


def _generate_job_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return f"job_{stamp}_{suffix}"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _dataclass_kwargs(cls: type, payload: dict[str, Any]) -> dict[str, Any]:
    if not is_dataclass(cls):
        return dict(payload)

    allowed = {field.name for field in fields(cls)}
    return {
        key: value
        for key, value in payload.items()
        if key in allowed
    }


def _extract_id(result: Any, keys: list[str]) -> str | None:
    if result is None:
        return None

    if isinstance(result, dict):
        for key in keys:
            value = result.get(key)
            if value not in (None, ""):
                return str(value)
        return None

    for key in keys:
        if hasattr(result, key):
            value = getattr(result, key)
            if value not in (None, ""):
                return str(value)

    return None


def _latest_dir_id(root: Path) -> str | None:
    if not root.exists():
        return None

    dirs = [
        path
        for path in root.iterdir()
        if path.is_dir() and _is_safe_id(path.name)
    ]

    if not dirs:
        return None

    latest = max(dirs, key=lambda path: path.stat().st_mtime)
    return latest.name


@dataclass
class DecisionJob:
    job_id: str
    module: str
    config: dict[str, Any]
    status: str = "queued"
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    artifact_type: str | None = None
    artifact_id: str | None = None
    progress: Any | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "module": self.module,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "artifact_type": self.artifact_type,
            "artifact_id": self.artifact_id,
            "progress": self.progress,
            "error": self.error,
        }


class DecisionJobManager:
    """
    Separate decision-layer job manager.

    This must not reuse the live Flask holder:
        holder = {
            "simulation": ...,
            "runner": ...
        }

    First version:
      - one concurrent decision job
      - queued jobs can be cancelled
      - running jobs cannot be cancelled yet
    """

    def __init__(
        self,
        data_dir: Path | str,
        runs_dir: Path | str,
        max_workers: int = 1,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.runs_dir = Path(runs_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._state_path = self.data_dir / "decision_jobs.json"

        self._lock = threading.Lock()
        self._jobs: dict[str, DecisionJob] = self._load_jobs()
        self._futures: dict[str, Any] = {}
        self._cancel_events: dict[str, threading.Event] = {
            job_id: threading.Event() for job_id in self._jobs
        }

        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="decision-job",
        )

    def _load_jobs(self) -> dict[str, DecisionJob]:
        payload = _read_json(self._state_path)
        jobs: dict[str, DecisionJob] = {}
        if not isinstance(payload, list):
            return jobs
        for item in payload:
            if not isinstance(item, dict) or not _is_safe_id(item.get("job_id", "")):
                continue
            if item.get("status") in {"queued", "running"}:
                item["status"] = "failed"
                item["error"] = "Interrupted by Flask restart."
                item["finished_at"] = _now_iso()
            try:
                job = DecisionJob(**{field.name: item.get(field.name) for field in fields(DecisionJob)})
            except TypeError:
                continue
            jobs[job.job_id] = job
        return jobs

    def _save_jobs_locked(self) -> None:
        temporary = self._state_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps([job.to_dict() | {"config": job.config} for job in self._jobs.values()], indent=2),
            encoding="utf-8",
        )
        temporary.replace(self._state_path)

    def _set_progress(self, job_id: str, percent: int | None, message: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                bounded = None if percent is None else max(0, min(100, percent))
                job.progress = {"percent": bounded, "message": message}
                self._save_jobs_locked()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_jobs(self) -> list[DecisionJob]:
        with self._lock:
            jobs = list(self._jobs.values())

        jobs.sort(key=lambda job: job.created_at or "", reverse=True)
        return jobs

    def get_job(self, job_id: str) -> DecisionJob:
        if not _is_safe_id(job_id):
            raise DecisionJobNotFoundError("Invalid job id.")

        with self._lock:
            job = self._jobs.get(job_id)

        if job is None:
            raise DecisionJobNotFoundError("Job not found.")

        return job

    def submit(
        self,
        module: str,
        config: dict[str, Any],
    ) -> DecisionJob:
        module = str(module or "").strip()

        if module not in SUPPORTED_DECISION_JOB_MODULES:
            supported = ", ".join(sorted(SUPPORTED_DECISION_JOB_MODULES))
            raise DecisionJobError(
                f"Unsupported decision module '{module}'. "
                f"Supported modules: {supported}."
            )

        if not isinstance(config, dict):
            raise DecisionJobError("Job config must be a JSON object.")

        self._validate_job_config(module, config)

        job = DecisionJob(
            job_id=_generate_job_id(),
            module=module,
            config=config,
            status="queued",
            created_at=_now_iso(),
        )

        with self._lock:
            self._jobs[job.job_id] = job
            self._cancel_events[job.job_id] = threading.Event()
            self._save_jobs_locked()

        future = self._executor.submit(self._run_job, job.job_id)

        with self._lock:
            self._futures[job.job_id] = future

        return job

    def cancel_job(self, job_id: str) -> DecisionJob:
        if not _is_safe_id(job_id):
            raise DecisionJobNotFoundError("Invalid job id.")

        with self._lock:
            job = self._jobs.get(job_id)

            if job is None:
                raise DecisionJobNotFoundError("Job not found.")

            if job.status == "queued":
                self._cancel_events.setdefault(job_id, threading.Event()).set()
                job.status = "cancelled"
                job.finished_at = _now_iso()
                job.error = "Cancelled before execution."
                self._save_jobs_locked()
                return job

            if job.status == "running":
                self._cancel_events.setdefault(job_id, threading.Event()).set()
                job.progress = {"percent": job.progress.get("percent", 0) if isinstance(job.progress, dict) else 0, "message": "Cancellation requested."}
                self._save_jobs_locked()
                return job

            raise DecisionJobConflictError(
                f"Cannot cancel job with status '{job.status}'."
            )

    # ------------------------------------------------------------------
    # Execution lifecycle
    # ------------------------------------------------------------------

    def _run_job(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)

            if job is None:
                return

            if job.status != "queued":
                return

            job.status = "running"
            job.started_at = _now_iso()
            job.progress = {"percent": None, "message": "Starting job."}
            self._save_jobs_locked()

        try:
            self._set_progress(job_id, None, "Validating and preparing job.")
            self._set_progress(job_id, None, f"Running {job.module}; progress is being measured.")
            artifact_type, artifact_id = self._execute_module(
                job.module,
                job.config,
                progress_callback=lambda percent, message: self._set_progress(
                    job_id, percent, message
                ),
            )
            self._set_progress(job_id, 95, "Finalizing artifact.")

            with self._lock:
                cancelled = self._cancel_events.get(job_id, threading.Event()).is_set()
                job.status = "cancelled" if cancelled else "finished"
                job.finished_at = _now_iso()
                job.artifact_type = artifact_type
                job.artifact_id = artifact_id
                job.progress = {"percent": 100, "message": "Cancellation requested after execution." if cancelled else "Completed."}
                job.error = "Cancellation requested; execution completed." if cancelled else None
                self._save_jobs_locked()

        except Exception as exc:
            with self._lock:
                job.status = "failed"
                job.finished_at = _now_iso()
                job.error = str(exc)
                job.progress = {"percent": 100, "message": "Failed."}
                self._save_jobs_locked()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_job_config(
        self,
        module: str,
        config: dict[str, Any],
    ) -> None:
        if module in {
            "monte_carlo",
            "sensitivity",
            "optimizer",
            "multiobjective",
            "robustness",
            "study",
        }:
            self._validate_execution_options(config)

        if module in {
            "monte_carlo",
            "sensitivity",
            "optimizer",
            "multiobjective",
        }:
            self._require_source_config(config)

        if module == "monte_carlo":
            self._validate_monte_carlo_config(config)

        elif module == "sensitivity":
            self._validate_sensitivity_config(config)

        elif module == "optimizer":
            self._validate_optimizer_config(config)

        elif module == "multiobjective":
            self._validate_multiobjective_config(config)

        elif module == "robustness":
            self._validate_robustness_config(config)

        elif module == "report":
            self._validate_report_config(config)

        elif module == "spatial":
            self._validate_spatial_config(config)

        elif module == "study":
            self._validate_study_config(config)

    def _validate_execution_options(self, config: dict[str, Any]) -> None:
        mode = config.get("trial_artifact_mode", "full")
        if mode not in ALLOWED_TRIAL_ARTIFACT_MODES:
            raise DecisionJobError(
                "trial_artifact_mode must be 'full' or 'metrics_only'."
            )

        try:
            max_workers = int(config.get("max_workers", 1))
        except Exception as exc:
            raise DecisionJobError("max_workers must be an integer.") from exc

        if max_workers < 1:
            raise DecisionJobError("max_workers must be >= 1.")
        if max_workers > MAX_MAX_WORKERS:
            raise DecisionJobError(
                f"max_workers must be <= {MAX_MAX_WORKERS}."
            )

    def _require_source_config(self, config: dict[str, Any]) -> None:
        if isinstance(config.get("base_config"), dict):
            return

        if config.get("from_run_id") not in (None, ""):
            self._load_run_config(str(config["from_run_id"]))
            return

        raise DecisionJobError(
            "Job config must include either base_config or from_run_id."
        )

    def _validate_monte_carlo_config(self, config: dict[str, Any]) -> None:
        try:
            n_runs = int(config.get("n_runs", config.get("n", 1)))
        except Exception as exc:
            raise DecisionJobError("n_runs must be an integer.") from exc

        if n_runs < 1:
            raise DecisionJobError("n_runs must be >= 1.")

        seeds = config.get("seeds")
        if seeds is not None:
            if not isinstance(seeds, list):
                raise DecisionJobError("seeds must be a list of integers.")

            if len(seeds) != n_runs:
                raise DecisionJobError(
                    "If explicit seeds are provided, seeds length must equal n_runs."
                )

    def _validate_sensitivity_config(self, config: dict[str, Any]) -> None:
        factors = config.get("factors")

        if not isinstance(factors, list) or not factors:
            raise DecisionJobError(
                "Sensitivity config must include a non-empty factors list."
            )

        for factor in factors:
            if not isinstance(factor, dict):
                raise DecisionJobError("Each sensitivity factor must be an object.")

            name = factor.get("name")
            values = factor.get("values")

            if not name:
                raise DecisionJobError("Each sensitivity factor needs a name.")

            if not isinstance(values, list) or not values:
                raise DecisionJobError(
                    f"Sensitivity factor '{name}' needs a non-empty values list."
                )

        try:
            reps = int(config.get("reps", 3))
        except Exception as exc:
            raise DecisionJobError("reps must be an integer.") from exc

        if reps < 1:
            raise DecisionJobError("reps must be >= 1.")

    def _validate_optimizer_config(self, config: dict[str, Any]) -> None:
        objective = str(config.get("objective", "cost_per_task"))
        direction = str(config.get("direction", "minimize"))

        if objective not in SUPPORTED_OPTIMIZER_OBJECTIVES:
            supported = ", ".join(sorted(SUPPORTED_OPTIMIZER_OBJECTIVES))
            raise DecisionJobError(
                f"Unsupported optimizer objective '{objective}'. "
                f"Supported objectives: {supported}."
            )

        if direction not in SUPPORTED_DIRECTIONS:
            raise DecisionJobError(
                "direction must be either minimize or maximize."
            )

        self._validate_search_space(config.get("search_space"))

        if objective == "cost_per_task" and not self._has_cost_config(config):
            raise DecisionJobError(
                "cost_per_task objective requires a valid cost_config."
            )

        try:
            n_trials = int(config.get("n_trials", 50))
        except Exception as exc:
            raise DecisionJobError("n_trials must be an integer.") from exc

        if n_trials < 1:
            raise DecisionJobError("n_trials must be >= 1.")

        try:
            reps = int(config.get("reps", 1))
        except Exception as exc:
            raise DecisionJobError("reps must be an integer.") from exc

        if reps < 1:
            raise DecisionJobError("reps must be >= 1.")

    def _validate_multiobjective_config(self, config: dict[str, Any]) -> None:
        objectives = config.get("objectives")

        if not isinstance(objectives, list) or len(objectives) < 2:
            raise DecisionJobError(
                "Multi-objective optimization requires at least two objectives."
            )

        has_cost_objective = False

        for objective in objectives:
            if not isinstance(objective, dict):
                raise DecisionJobError("Each objective must be an object.")

            metric = objective.get("metric")
            direction = objective.get("direction", "minimize")

            if metric not in SUPPORTED_METRICS:
                supported = ", ".join(sorted(SUPPORTED_METRICS))
                raise DecisionJobError(
                    f"Unsupported objective metric '{metric}'. "
                    f"Supported metrics: {supported}."
                )

            if direction not in SUPPORTED_DIRECTIONS:
                raise DecisionJobError(
                    "Each objective direction must be minimize or maximize."
                )

            if metric == "cost_per_task":
                has_cost_objective = True

        self._validate_search_space(config.get("search_space"))

        if has_cost_objective and not self._has_cost_config(config):
            raise DecisionJobError(
                "cost_per_task objective requires a valid cost_config."
            )

        try:
            n_trials = int(config.get("n_trials", 50))
        except Exception as exc:
            raise DecisionJobError("n_trials must be an integer.") from exc

        if n_trials < 1:
            raise DecisionJobError("n_trials must be >= 1.")

        try:
            reps = int(config.get("reps", 1))
        except Exception as exc:
            raise DecisionJobError("reps must be an integer.") from exc

        if reps < 1:
            raise DecisionJobError("reps must be >= 1.")

    def _validate_robustness_config(self, config: dict[str, Any]) -> None:
        try:
            reps = int(config.get("reps", 20))
        except Exception as exc:
            raise DecisionJobError("reps must be an integer.") from exc

        if reps < 1:
            raise DecisionJobError("reps must be >= 1.")

        try:
            min_pass_probability = float(
                config.get("min_pass_probability", 0.95)
            )
        except Exception as exc:
            raise DecisionJobError(
                "min_pass_probability must be a number."
            ) from exc

        if not (0.0 <= min_pass_probability <= 1.0):
            raise DecisionJobError(
                "min_pass_probability must be between 0 and 1."
            )

        candidates = config.get("candidates")
        from_multiobjective_id = config.get("from_multiobjective_id")

        if candidates is not None:
            if not isinstance(candidates, list) or not candidates:
                raise DecisionJobError(
                    "candidates must be a non-empty list when provided."
                )

            for candidate in candidates:
                if not isinstance(candidate, dict):
                    raise DecisionJobError("Each candidate must be an object.")

                if not candidate.get("label"):
                    raise DecisionJobError("Each candidate needs a label.")

                overrides = candidate.get("overrides", {})
                if not isinstance(overrides, dict):
                    raise DecisionJobError(
                        "Each candidate overrides field must be an object."
                    )

            if not isinstance(config.get("constraints"), dict) or not config.get("constraints"):
                raise DecisionJobError(
                    "Robustness verification requires a non-empty constraints object."
                )

        elif from_multiobjective_id not in (None, ""):
            if not _is_safe_id(str(from_multiobjective_id)):
                raise DecisionJobError("Invalid from_multiobjective_id.")

            summary_path = (
                self.data_dir
                / "multiobjective"
                / str(from_multiobjective_id)
                / "summary.json"
            )

            if not summary_path.exists():
                raise DecisionJobError(
                    "Multi-objective study not found for from_multiobjective_id."
                )

        else:
            raise DecisionJobError(
                "Robustness config must include either candidates or from_multiobjective_id."
            )

        objective = str(config.get("objective", "cost_per_task"))

        if objective not in SUPPORTED_METRICS:
            supported = ", ".join(sorted(SUPPORTED_METRICS))
            raise DecisionJobError(
                f"Unsupported robustness objective '{objective}'. "
                f"Supported metrics: {supported}."
            )

        if objective == "cost_per_task" and not self._has_cost_config(config):
            # For from_multiobjective jobs, cost config may be inherited later.
            if not config.get("from_multiobjective_id"):
                raise DecisionJobError(
                    "cost_per_task objective requires a valid cost_config."
                )

    def _validate_report_config(self, config: dict[str, Any]) -> None:
        run_id = config.get("run_id")
        study_id = config.get("study_id")

        if run_id not in (None, ""):
            if not _is_safe_id(str(run_id)):
                raise DecisionJobError("Invalid run id.")

            run_config_path = self.runs_dir / str(run_id) / "config.json"
            if not run_config_path.exists():
                raise DecisionJobError("Run id not found.")

            return

        if study_id not in (None, ""):
            if not _is_safe_id(str(study_id)):
                raise DecisionJobError("Invalid study id.")

            study_dir = self.data_dir / "studies" / str(study_id)
            if not study_dir.exists():
                raise DecisionJobError("Study id not found.")

            return

        raise DecisionJobError(
            "Report job config must include either run_id or study_id."
        )

    def _validate_spatial_config(self, config: dict[str, Any]) -> None:
        run_id = config.get("run_id")

        if run_id in (None, ""):
            raise DecisionJobError("Spatial job config must include run_id.")

        if not _is_safe_id(str(run_id)):
            raise DecisionJobError("Invalid run id.")

        run_config_path = self.runs_dir / str(run_id) / "config.json"
        if not run_config_path.exists():
            raise DecisionJobError("Run id not found.")

        try:
            top = int(config.get("top", 20))
        except Exception as exc:
            raise DecisionJobError("top must be an integer.") from exc

        if top < 1:
            raise DecisionJobError("top must be >= 1.")

        by = str(config.get("by", "blocked_ticks"))
        if by not in {"blocked_ticks", "blocked_events"}:
            raise DecisionJobError(
                "by must be either blocked_ticks or blocked_events."
            )

    def _validate_study_config(self, config: dict[str, Any]) -> None:
        if not config:
            raise DecisionJobError("Study job config must not be empty.")

        if (
            "base_config" not in config
            and "from_run_id" not in config
            and "study_config" not in config
        ):
            raise DecisionJobError(
                "Study job config must include study_config, base_config, or from_run_id."
            )

    def _validate_search_space(self, search_space: Any) -> None:
        if not isinstance(search_space, list) or not search_space:
            raise DecisionJobError(
                "search_space must be a non-empty list."
            )

        for spec in search_space:
            if not isinstance(spec, dict):
                raise DecisionJobError("Each search-space entry must be an object.")

            name = spec.get("name")
            spec_type = spec.get("type")

            if not name:
                raise DecisionJobError("Each search-space entry needs a name.")

            if spec_type not in {"int", "float", "categorical"}:
                raise DecisionJobError(
                    f"Search-space entry '{name}' has unsupported type '{spec_type}'."
                )

            if spec_type == "categorical":
                choices = spec.get("choices")
                if not isinstance(choices, list) or not choices:
                    raise DecisionJobError(
                        f"Categorical search-space entry '{name}' needs non-empty choices."
                    )
            else:
                if spec.get("low") is None or spec.get("high") is None:
                    raise DecisionJobError(
                        f"Numeric search-space entry '{name}' needs low and high."
                    )

    def _has_cost_config(self, config: dict[str, Any]) -> bool:
        return config.get("cost_config") not in (None, "", {}, [])

    # ------------------------------------------------------------------
    # Module execution
    # ------------------------------------------------------------------

    def _execute_module(
        self,
        module: str,
        config: dict[str, Any],
        progress_callback: Any | None = None,
    ) -> tuple[str | None, str | None]:
        if module == "monte_carlo":
            return self._run_monte_carlo_job(config, progress_callback=progress_callback)

        if module == "sensitivity":
            return self._run_sensitivity_job(config)

        if module == "optimizer":
            return self._run_optimizer_job(config)

        if module == "multiobjective":
            return self._run_multiobjective_job(config)

        if module == "robustness":
            return self._run_robustness_job(config)

        if module == "report":
            return self._run_report_job(config)

        if module == "spatial":
            return self._run_spatial_job(config)

        if module == "study":
            return self._run_study_job(config)

        raise DecisionJobError(f"Unsupported module '{module}'.")

    # ------------------------------------------------------------------
    # Shared config helpers
    # ------------------------------------------------------------------

    def _load_run_config(self, run_id: str) -> dict[str, Any]:
        if not _is_safe_id(run_id):
            raise DecisionJobError("Invalid run id.")

        path = self.runs_dir / run_id / "config.json"

        if not path.exists():
            raise DecisionJobError("Run id not found.")

        data = _read_json(path)

        if not isinstance(data, dict):
            raise DecisionJobError("Run config.json is missing or invalid.")

        return data

    def _base_config(self, config: dict[str, Any]) -> dict[str, Any]:
        base_config = config.get("base_config")

        if isinstance(base_config, dict):
            return dict(base_config)

        from_run_id = config.get("from_run_id")

        if from_run_id not in (None, ""):
            return self._load_run_config(str(from_run_id))

        raise DecisionJobError(
            "Job config must include either base_config or from_run_id."
        )

    def _cost_config(self, raw: Any) -> CostConfig | None:
        if raw in (None, "", {}, []):
            return None

        if isinstance(raw, CostConfig):
            return raw

        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise DecisionJobError(
                    "cost_config string must be valid JSON."
                ) from exc

        if not isinstance(raw, dict):
            raise DecisionJobError("cost_config must be a JSON object.")

        allowed = {field.name for field in fields(CostConfig)}
        kwargs = {
            key: value
            for key, value in raw.items()
            if key in allowed
        }

        try:
            return CostConfig(**kwargs)
        except Exception as exc:
            raise DecisionJobError(f"Invalid cost_config: {exc}") from exc

    def _search_space_specs(self, config: dict[str, Any]) -> list[Any]:
        from decision.optimizer import SearchSpaceSpec

        raw = config.get("search_space")

        if not isinstance(raw, list) or not raw:
            raise DecisionJobError("search_space must be a non-empty list.")

        specs = []

        for item in raw:
            if not isinstance(item, dict):
                raise DecisionJobError("Each search-space entry must be an object.")

            name = item.get("name")
            spec_type = item.get("type")

            if not name:
                raise DecisionJobError("Each search-space entry needs a name.")

            if spec_type not in {"int", "float", "categorical"}:
                raise DecisionJobError(
                    f"Search-space entry '{name}' has unsupported type '{spec_type}'."
                )

            if spec_type == "categorical":
                choices = item.get("choices")

                if not isinstance(choices, list) or not choices:
                    raise DecisionJobError(
                        f"Categorical search-space entry '{name}' needs non-empty choices."
                    )

                specs.append(
                    SearchSpaceSpec(
                        name=str(name),
                        type=spec_type,
                        choices=choices,
                    )
                )
            else:
                low = item.get("low")
                high = item.get("high")

                if low is None or high is None:
                    raise DecisionJobError(
                        f"Numeric search-space entry '{name}' needs low and high."
                    )

                specs.append(
                    SearchSpaceSpec(
                        name=str(name),
                        type=spec_type,
                        low=low,
                        high=high,
                    )
                )

        return specs

    # ------------------------------------------------------------------
    # Monte Carlo
    # ------------------------------------------------------------------

    def _run_monte_carlo_job(
        self,
        config: dict[str, Any],
        progress_callback: Any | None = None,
    ) -> tuple[str, str | None]:
        from decision.monte_carlo import MonteCarloConfig, run_monte_carlo

        base_config = self._base_config(config)

        try:
            n_runs = int(config.get("n_runs", config.get("n", 1)))
        except Exception as exc:
            raise DecisionJobError("n_runs must be an integer.") from exc

        if n_runs < 1:
            raise DecisionJobError("n_runs must be >= 1.")

        seeds = config.get("seeds")
        if seeds is not None and not isinstance(seeds, list):
            raise DecisionJobError("seeds must be a list of integers.")

        cost_config = self._cost_config(config.get("cost_config"))

        mc_config = MonteCarloConfig(
            base_config=base_config,
            n_runs=n_runs,
            base_seed=config.get("base_seed"),
            seeds=seeds,
            sla_target_ticks=config.get("sla_target_ticks"),
            cost_config=cost_config,
            force_fast_mode=bool(config.get("force_fast_mode", True)),
            output_dir=str(self.data_dir / "monte_carlo"),
            runs_base_dir=str(self.runs_dir),
            max_workers=int(config.get("max_workers", 1)),
            trial_artifact_mode=str(config.get("trial_artifact_mode", "full")),
        )

        result = run_monte_carlo(mc_config, progress_callback=progress_callback)
        artifact_id = _extract_id(result, ["mc_id", "id"])

        return "monte_carlo", artifact_id

    # ------------------------------------------------------------------
    # Sensitivity
    # ------------------------------------------------------------------

    def _run_sensitivity_job(
        self,
        config: dict[str, Any],
    ) -> tuple[str, str | None]:
        from decision.sensitivity import (
            FactorSpec,
            SensitivityConfig,
            run_sensitivity,
        )

        base_config = self._base_config(config)

        raw_factors = config.get("factors")
        if not isinstance(raw_factors, list) or not raw_factors:
            raise DecisionJobError(
                "Sensitivity config must include a non-empty factors list."
            )

        factors = []

        for item in raw_factors:
            if not isinstance(item, dict):
                raise DecisionJobError("Each sensitivity factor must be an object.")

            name = item.get("name")
            values = item.get("values")

            if not name:
                raise DecisionJobError("Each sensitivity factor needs a name.")

            if not isinstance(values, list) or not values:
                raise DecisionJobError(
                    f"Sensitivity factor '{name}' needs a non-empty values list."
                )

            factors.append(
                FactorSpec(
                    name=str(name),
                    values=values,
                )
            )

        try:
            reps = int(config.get("reps", 3))
        except Exception as exc:
            raise DecisionJobError("reps must be an integer.") from exc

        if reps < 1:
            raise DecisionJobError("reps must be >= 1.")

        cost_config = self._cost_config(config.get("cost_config"))

        sensitivity_config = SensitivityConfig(
            base_config=base_config,
            factors=factors,
            reps=reps,
            base_seed=config.get("base_seed"),
            sla_target_ticks=config.get("sla_target_ticks"),
            cost_config=cost_config,
            force_fast_mode=bool(config.get("force_fast_mode", True)),
            output_dir=str(self.data_dir / "sensitivity"),
            runs_base_dir=str(self.runs_dir),
            max_workers=int(config.get("max_workers", 1)),
            trial_artifact_mode=str(config.get("trial_artifact_mode", "full")),
        )

        result = run_sensitivity(sensitivity_config)
        artifact_id = _extract_id(result, ["study_id", "id"])

        return "sensitivity", artifact_id

    # ------------------------------------------------------------------
    # Single-objective optimizer
    # ------------------------------------------------------------------

    def _run_optimizer_job(
        self,
        config: dict[str, Any],
    ) -> tuple[str, str | None]:
        from decision.optimizer import OptimizerConfig, run_optimization

        base_config = self._base_config(config)
        search_space = self._search_space_specs(config)

        objective = str(config.get("objective", "cost_per_task"))
        direction = str(config.get("direction", "minimize"))

        if objective not in SUPPORTED_OPTIMIZER_OBJECTIVES:
            supported = ", ".join(sorted(SUPPORTED_OPTIMIZER_OBJECTIVES))
            raise DecisionJobError(
                f"Unsupported optimizer objective '{objective}'. "
                f"Supported objectives: {supported}."
            )

        if direction not in SUPPORTED_DIRECTIONS:
            raise DecisionJobError(
                "direction must be either minimize or maximize."
            )

        cost_config = self._cost_config(config.get("cost_config"))

        if objective == "cost_per_task" and cost_config is None:
            raise DecisionJobError(
                "cost_per_task objective requires a valid cost_config."
            )

        constraints = config.get("constraints") or {}
        if not isinstance(constraints, dict):
            raise DecisionJobError("constraints must be a JSON object.")

        try:
            n_trials = int(config.get("n_trials", 50))
        except Exception as exc:
            raise DecisionJobError("n_trials must be an integer.") from exc

        if n_trials < 1:
            raise DecisionJobError("n_trials must be >= 1.")

        try:
            reps = int(config.get("reps", 1))
        except Exception as exc:
            raise DecisionJobError("reps must be an integer.") from exc

        if reps < 1:
            raise DecisionJobError("reps must be >= 1.")

        optimizer_config = OptimizerConfig(
            base_config=base_config,
            search_space=search_space,
            objective=objective,
            direction=direction,
            n_trials=n_trials,
            reps=reps,
            base_seed=config.get("base_seed"),
            constraints=constraints,
            sla_target_ticks=config.get("sla_target_ticks"),
            cost_config=cost_config,
            force_fast_mode=bool(config.get("force_fast_mode", True)),
            output_dir=str(self.data_dir / "optimizations"),
            runs_base_dir=str(self.runs_dir),
            timeout=config.get("timeout"),
            max_workers=int(config.get("max_workers", 1)),
            trial_artifact_mode=str(config.get("trial_artifact_mode", "full")),
        )

        summary = run_optimization(optimizer_config)
        artifact_id = _extract_id(summary, ["opt_id", "id"])

        return "optimization", artifact_id

    # ------------------------------------------------------------------
    # Multi-objective
    # ------------------------------------------------------------------

    def _run_multiobjective_job(
        self,
        config: dict[str, Any],
    ) -> tuple[str, str | None]:
        from decision.multiobjective import (
            MultiObjectiveConfig,
            ObjectiveSpec,
            run_multiobjective,
        )

        base_config = self._base_config(config)
        search_space = self._search_space_specs(config)

        raw_objectives = config.get("objectives")
        if not isinstance(raw_objectives, list) or len(raw_objectives) < 2:
            raise DecisionJobError(
                "Multi-objective optimization requires at least two objectives."
            )

        objectives = []
        has_cost_objective = False

        for item in raw_objectives:
            if not isinstance(item, dict):
                raise DecisionJobError("Each objective must be an object.")

            metric = item.get("metric")
            direction = item.get("direction", "minimize")

            if metric not in SUPPORTED_METRICS:
                supported = ", ".join(sorted(SUPPORTED_METRICS))
                raise DecisionJobError(
                    f"Unsupported objective metric '{metric}'. "
                    f"Supported metrics: {supported}."
                )

            if direction not in SUPPORTED_DIRECTIONS:
                raise DecisionJobError(
                    "Each objective direction must be minimize or maximize."
                )

            if metric == "cost_per_task":
                has_cost_objective = True

            objectives.append(
                ObjectiveSpec(
                    metric=str(metric),
                    direction=str(direction),
                )
            )

        cost_config = self._cost_config(config.get("cost_config"))

        if has_cost_objective and cost_config is None:
            raise DecisionJobError(
                "cost_per_task objective requires a valid cost_config."
            )

        constraints = config.get("constraints") or {}
        if not isinstance(constraints, dict):
            raise DecisionJobError("constraints must be a JSON object.")

        try:
            n_trials = int(config.get("n_trials", 50))
        except Exception as exc:
            raise DecisionJobError("n_trials must be an integer.") from exc

        if n_trials < 1:
            raise DecisionJobError("n_trials must be >= 1.")

        try:
            reps = int(config.get("reps", 1))
        except Exception as exc:
            raise DecisionJobError("reps must be an integer.") from exc

        if reps < 1:
            raise DecisionJobError("reps must be >= 1.")

        population_size = config.get("population_size")

        multiobjective_config = MultiObjectiveConfig(
            base_config=base_config,
            search_space=search_space,
            objectives=objectives,
            constraints=constraints,
            n_trials=n_trials,
            reps=reps,
            base_seed=config.get("base_seed"),
            population_size=population_size,
            sla_target_ticks=config.get("sla_target_ticks"),
            cost_config=cost_config,
            force_fast_mode=bool(config.get("force_fast_mode", True)),
            output_dir=str(self.data_dir / "multiobjective"),
            runs_base_dir=str(self.runs_dir),
            timeout=config.get("timeout"),
            max_workers=int(config.get("max_workers", 1)),
            trial_artifact_mode=str(config.get("trial_artifact_mode", "full")),
        )

        summary = run_multiobjective(multiobjective_config)
        artifact_id = _extract_id(summary, ["study_id", "id"])

        return "multiobjective", artifact_id

    # ------------------------------------------------------------------
    # Robustness
    # ------------------------------------------------------------------

    def _run_robustness_job(
        self,
        config: dict[str, Any],
    ) -> tuple[str, str | None]:
        from decision.robustness import (
            RobustnessCandidate,
            RobustnessConfig,
            run_robustness,
        )

        base_config = None
        cost_config_raw = config.get("cost_config")
        constraints = config.get("constraints") or {}

        if not isinstance(constraints, dict):
            raise DecisionJobError("constraints must be a JSON object.")

        candidates: list[RobustnessCandidate] = []

        raw_candidates = config.get("candidates")
        from_multiobjective_id = config.get("from_multiobjective_id")

        if isinstance(raw_candidates, list) and raw_candidates:
            base_config = self._base_config(config)

            for item in raw_candidates:
                if not isinstance(item, dict):
                    raise DecisionJobError("Each candidate must be an object.")

                label = item.get("label")
                overrides = item.get("overrides", {})

                if not label:
                    raise DecisionJobError("Each candidate needs a label.")

                if not isinstance(overrides, dict):
                    raise DecisionJobError(
                        "Each candidate overrides field must be an object."
                    )

                candidates.append(
                    RobustnessCandidate(
                        label=str(label),
                        overrides=overrides,
                    )
                )

            if not constraints:
                raise DecisionJobError(
                    "Robustness verification requires a non-empty constraints object."
                )

        elif from_multiobjective_id not in (None, ""):
            if not _is_safe_id(str(from_multiobjective_id)):
                raise DecisionJobError("Invalid from_multiobjective_id.")

            summary_path = (
                self.data_dir
                / "multiobjective"
                / str(from_multiobjective_id)
                / "summary.json"
            )

            if not summary_path.exists():
                raise DecisionJobError(
                    "Multi-objective study not found for from_multiobjective_id."
                )

            mo_summary = _read_json(summary_path)

            if not isinstance(mo_summary, dict):
                raise DecisionJobError(
                    "Multi-objective summary.json is missing or invalid."
                )

            base_config = mo_summary.get("base_config")

            if not isinstance(base_config, dict):
                base_config = self._base_config(config)

            if not cost_config_raw and mo_summary.get("cost_config"):
                cost_config_raw = mo_summary.get("cost_config")

            if not constraints and isinstance(mo_summary.get("constraints"), dict):
                constraints = mo_summary.get("constraints")

            pareto_trials = mo_summary.get("pareto_trials")

            if not isinstance(pareto_trials, list) or not pareto_trials:
                raise DecisionJobError(
                    "Multi-objective study has no Pareto trials to verify."
                )

            try:
                max_candidates = int(config.get("max_candidates", 3))
            except Exception as exc:
                raise DecisionJobError("max_candidates must be an integer.") from exc

            if max_candidates < 1:
                raise DecisionJobError("max_candidates must be >= 1.")

            for index, trial in enumerate(pareto_trials[:max_candidates]):
                if not isinstance(trial, dict):
                    continue

                params = trial.get("params") or {}

                if not isinstance(params, dict):
                    params = {}

                label = trial.get("label") or f"pareto-{trial.get('number', index)}"

                candidates.append(
                    RobustnessCandidate(
                        label=str(label),
                        overrides=params,
                    )
                )

            if not candidates:
                raise DecisionJobError(
                    "No usable Pareto candidates were found in the multi-objective summary."
                )

        else:
            raise DecisionJobError(
                "Robustness config must include either candidates or from_multiobjective_id."
            )

        if not isinstance(base_config, dict):
            raise DecisionJobError(
                "Could not resolve base_config for robustness verification."
            )

        cost_config = self._cost_config(cost_config_raw)

        objective = str(config.get("objective", "cost_per_task"))
        direction = str(config.get("direction", "minimize"))

        if objective not in SUPPORTED_METRICS:
            supported = ", ".join(sorted(SUPPORTED_METRICS))
            raise DecisionJobError(
                f"Unsupported robustness objective '{objective}'. "
                f"Supported metrics: {supported}."
            )

        if direction not in SUPPORTED_DIRECTIONS:
            raise DecisionJobError(
                "direction must be either minimize or maximize."
            )

        if objective == "cost_per_task" and cost_config is None:
            raise DecisionJobError(
                "cost_per_task objective requires a valid cost_config."
            )

        if not constraints:
            raise DecisionJobError(
                "Robustness verification requires a non-empty constraints object."
            )

        try:
            reps = int(config.get("reps", 20))
        except Exception as exc:
            raise DecisionJobError("reps must be an integer.") from exc

        if reps < 1:
            raise DecisionJobError("reps must be >= 1.")

        try:
            min_pass_probability = float(
                config.get("min_pass_probability", 0.95)
            )
        except Exception as exc:
            raise DecisionJobError(
                "min_pass_probability must be a number."
            ) from exc

        if not (0.0 <= min_pass_probability <= 1.0):
            raise DecisionJobError(
                "min_pass_probability must be between 0 and 1."
            )

        robustness_config = RobustnessConfig(
            base_config=base_config,
            candidates=candidates,
            reps=reps,
            base_seed=config.get("base_seed"),
            constraints=constraints,
            objective=objective,
            direction=direction,
            min_pass_probability=min_pass_probability,
            sla_target_ticks=config.get("sla_target_ticks"),
            cost_config=cost_config,
            force_fast_mode=bool(config.get("force_fast_mode", True)),
            output_dir=str(self.data_dir / "robustness"),
            runs_base_dir=str(self.runs_dir),
            max_workers=int(config.get("max_workers", 1)),
            trial_artifact_mode=str(config.get("trial_artifact_mode", "full")),
        )

        summary = run_robustness(robustness_config)
        artifact_id = _extract_id(summary, ["robust_id", "id"])

        return "robustness", artifact_id

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

    def _run_report_job(
        self,
        config: dict[str, Any],
    ) -> tuple[str, str | None]:
        run_id = config.get("run_id")
        study_id = config.get("study_id")

        if run_id not in (None, ""):
            run_id = str(run_id)

            if not _is_safe_id(run_id):
                raise DecisionJobError("Invalid run id.")

            run_config_path = self.runs_dir / run_id / "config.json"
            if not run_config_path.exists():
                raise DecisionJobError("Run id not found.")

            from decision.report import generate_run_report

            generate_run_report(
                run_id,
                base_dir=str(self.runs_dir),
                output_dir=self.data_dir / "reports",
            )

            return "report", f"{run_id}_report"

        if study_id not in (None, ""):
            study_id = str(study_id)

            if not _is_safe_id(study_id):
                raise DecisionJobError("Invalid study id.")

            study_dir = self.data_dir / "studies" / study_id

            if not study_dir.exists():
                raise DecisionJobError("Study id not found.")

            from decision.report import generate_report

            generate_report(study_dir)

            return "report", f"study_report_{study_id}"

        raise DecisionJobError(
            "Report job config must include either run_id or study_id."
        )

    # ------------------------------------------------------------------
    # Spatial
    # ------------------------------------------------------------------

    def _run_spatial_job(
        self,
        config: dict[str, Any],
    ) -> tuple[str, str | None]:
        run_id = str(config.get("run_id") or "")

        if not _is_safe_id(run_id):
            raise DecisionJobError("Invalid run id.")

        try:
            top = int(config.get("top", 20))
        except Exception as exc:
            raise DecisionJobError("top must be an integer.") from exc

        if top < 1:
            raise DecisionJobError("top must be >= 1.")

        by = str(config.get("by", "blocked_ticks"))
        if by not in {"blocked_ticks", "blocked_events"}:
            raise DecisionJobError(
                "by must be either blocked_ticks or blocked_events."
            )

        from analysis.loader import load_run
        from decision.spatial import compute_spatial_blockage

        run_data = load_run(run_id, base_dir=str(self.runs_dir))
        compute_spatial_blockage(run_data)

        # Spatial analysis is currently computed on demand and not stored
        # as a separate artifact directory.
        return "spatial", run_id

    # ------------------------------------------------------------------
    # Study
    # ------------------------------------------------------------------

    def _run_study_job(
        self,
        config: dict[str, Any],
    ) -> tuple[str, str | None]:
        try:
            from decision import study as study_mod
        except Exception as exc:
            raise DecisionJobError("decision.study is unavailable.") from exc

        payload = dict(config)

        if (
            "base_config" not in payload
            and payload.get("from_run_id") not in (None, "")
        ):
            payload["base_config"] = self._load_run_config(
                str(payload["from_run_id"])
            )

        # Do not allow arbitrary user output paths.
        payload["output_dir"] = str(self.data_dir / "studies")
        payload["runs_base_dir"] = str(self.runs_dir)

        study_config_cls = getattr(study_mod, "StudyConfig", None)

        if study_config_cls is None:
            raise DecisionJobError("decision.study.StudyConfig is unavailable.")

        try:
            if hasattr(study_config_cls, "from_dict"):
                filtered_payload = (
                    _dataclass_kwargs(study_config_cls, payload)
                    if is_dataclass(study_config_cls)
                    else payload
                )
                study_config = study_config_cls.from_dict(filtered_payload)
            else:
                kwargs = _dataclass_kwargs(study_config_cls, payload)
                study_config = study_config_cls(**kwargs)
        except Exception as exc:
            raise DecisionJobError(f"Invalid study config: {exc}") from exc

        result = None

        if hasattr(study_mod, "run_study"):
            result = study_mod.run_study(study_config)
        else:
            runner_cls = getattr(study_mod, "StudyRunner", None)

            if runner_cls is None:
                raise DecisionJobError(
                    "decision.study has no runnable StudyRunner or run_study function."
                )

            try:
                runner = runner_cls(study_config)
            except TypeError:
                runner = runner_cls(config=study_config)

            if hasattr(runner, "run"):
                result = runner.run()
            elif hasattr(runner, "execute"):
                result = runner.execute()
            else:
                raise DecisionJobError(
                    "StudyRunner does not expose run() or execute()."
                )

        artifact_id = (
            _extract_id(result, ["study_id", "id"])
            or _latest_dir_id(self.data_dir / "studies")
        )

        return "study", artifact_id


# =====================================================================
# Flask blueprint
# =====================================================================

def create_decision_jobs_blueprint(manager: DecisionJobManager) -> Blueprint:
    bp = Blueprint("decision_jobs_api", __name__)

    @bp.get("/api/decision/templates/<module>")
    def decision_job_template(module: str):
        if module not in SUPPORTED_DECISION_JOB_MODULES:
            return jsonify({"error": "Unsupported decision module."}), 404
        templates: dict[str, dict[str, Any]] = {
            "monte_carlo": {"from_run_id": "REPLACE_WITH_RUN_ID", "n_runs": 20, "base_seed": 42},
            "sensitivity": {"from_run_id": "REPLACE_WITH_RUN_ID", "reps": 5, "base_seed": 42, "factors": []},
            "optimizer": {"from_run_id": "REPLACE_WITH_RUN_ID", "objective": "cost_per_task", "direction": "minimize", "n_trials": 20, "reps": 1, "search_space": []},
            "multiobjective": {"from_run_id": "REPLACE_WITH_RUN_ID", "n_trials": 20, "reps": 1, "objectives": [{"metric": "cost_per_task", "direction": "minimize"}, {"metric": "p95_cycle_time", "direction": "minimize"}], "search_space": []},
            "robustness": {"from_multiobjective_id": "REPLACE_WITH_ID", "max_candidates": 3, "reps": 20, "min_pass_probability": 0.9},
            "report": {"run_id": "REPLACE_WITH_RUN_ID"},
            "spatial": {"run_id": "REPLACE_WITH_RUN_ID", "top": 20, "by": "blocked_ticks"},
            "study": {"from_run_id": "REPLACE_WITH_RUN_ID", "factors": []},
        }
        return jsonify({"module": module, "config": templates[module]})

    @bp.get("/api/decision/files")
    def list_decision_files():
        root = manager.data_dir / "uploads"
        root.mkdir(parents=True, exist_ok=True)
        files = [{"name": path.name, "size": path.stat().st_size} for path in root.iterdir() if path.is_file() and _is_safe_id(path.stem)]
        return jsonify({"files": files})

    @bp.post("/api/decision/files")
    def upload_decision_file():
        uploaded = request.files.get("file")
        if uploaded is None or not uploaded.filename:
            return jsonify({"error": "A file field is required."}), 400
        filename = Path(uploaded.filename).name
        stem = re.sub(r"[^A-Za-z0-9_.-]", "_", filename)
        if not stem or stem.startswith("."):
            return jsonify({"error": "Invalid filename."}), 400
        root = manager.data_dir / "uploads"
        root.mkdir(parents=True, exist_ok=True)
        destination = root / stem
        uploaded.save(destination)
        return jsonify({"name": stem, "path": destination.as_posix()}), 201

    @bp.post("/api/decision/jobs")
    def create_decision_job():
        payload = request.get_json(force=True, silent=True)

        if not isinstance(payload, dict):
            return jsonify({"error": "Request body must be a JSON object."}), 400

        module = payload.get("module")
        config = payload.get("config")

        try:
            job = manager.submit(module, config)
        except DecisionJobError as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify(job.to_dict()), 201

    @bp.get("/api/decision/jobs")
    def list_decision_jobs():
        jobs = manager.list_jobs()
        return jsonify({"jobs": [job.to_dict() for job in jobs]})

    @bp.get("/api/decision/jobs/<job_id>")
    def get_decision_job(job_id: str):
        try:
            job = manager.get_job(job_id)
        except DecisionJobNotFoundError:
            return jsonify({"error": "Job not found."}), 404
        except DecisionJobError as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify(job.to_dict())

    @bp.post("/api/decision/jobs/<job_id>/cancel")
    def cancel_decision_job(job_id: str):
        try:
            job = manager.cancel_job(job_id)
        except DecisionJobNotFoundError:
            return jsonify({"error": "Job not found."}), 404
        except DecisionJobConflictError as exc:
            return jsonify({"error": str(exc)}), 409
        except DecisionJobError as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify(job.to_dict())

    return bp