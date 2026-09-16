from __future__ import annotations

import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any

from experiment.headless import HeadlessTrialResult, run_headless_trial


def _worker(spec: dict[str, Any]) -> HeadlessTrialResult:
    return run_headless_trial(
        spec["config"],
        sla_target_ticks=spec.get("sla_target_ticks"),
        cost_config=spec.get("cost_config"),
    )


def run_trial_specs(
    specs: list[dict[str, Any]],
    *,
    max_workers: int = 1,
    progress_callback: Any | None = None,
) -> list[HeadlessTrialResult]:
    ordered_specs = list(specs)
    if not ordered_specs:
        return []
    if max_workers <= 1:
        results = []
        for completed, spec in enumerate(ordered_specs, start=1):
            results.append(_worker(spec))
            if progress_callback is not None:
                progress_callback(completed, len(ordered_specs))
        return results # type: ignore

    results: list[HeadlessTrialResult | None] = [None] * len(ordered_specs)
    context = multiprocessing.get_context("spawn")

    with ProcessPoolExecutor(
        max_workers=max_workers,
        mp_context=context,
    ) as executor:
        future_to_index = {
            executor.submit(_worker, spec): index
            for index, spec in enumerate(ordered_specs)
        }
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                results[index] = future.result()
            except Exception as exc:
                results[index] = HeadlessTrialResult(
                    ok=False,
                    metrics={},
                    summary={},
                    task_lifecycles=(),
                    error=str(exc),
                )
            if progress_callback is not None:
                completed = sum(result is not None for result in results)
                progress_callback(completed, len(ordered_specs))

    return [
        result
        if result is not None
        else HeadlessTrialResult(
            ok=False,
            metrics={},
            summary={},
            task_lifecycles=(),
            error="Missing parallel trial result",
        )
        for result in results
    ]
