from __future__ import annotations

ALLOWED_TRIAL_ARTIFACT_MODES = {"full", "metrics_only"}
DEFAULT_MAX_WORKERS = 1
MAX_MAX_WORKERS = 4


def validate_execution_options(max_workers: int, trial_artifact_mode: str) -> None:
    if max_workers < 1:
        raise ValueError("max_workers must be >= 1")
    if max_workers > MAX_MAX_WORKERS:
        raise ValueError(f"max_workers must be <= {MAX_MAX_WORKERS}")
    if trial_artifact_mode not in ALLOWED_TRIAL_ARTIFACT_MODES:
        raise ValueError("trial_artifact_mode must be 'full' or 'metrics_only'")
