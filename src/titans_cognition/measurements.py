"""Gate B measurement validation without inventing user-study results."""

from __future__ import annotations

from numbers import Real
from typing import Any, Mapping


REQUIRED_TASK_IDS = {
    "holdout_technical_vs_business_identity_001",
    "holdout_role_and_counterevidence_001",
    "holdout_relation_layer_direction_001",
    "holdout_unknown_no_key_001",
}


def evaluate_gate_b_measurements(
    measurements: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Validate measured Gate B inputs and return a conservative report."""

    if not isinstance(measurements, Mapping):
        return _pending("measurement artifact is missing")

    tasks = measurements.get("tasks")
    if not isinstance(tasks, list):
        return _pending("measurement artifact has no task list")

    by_id = {
        str(task.get("task_id")): task
        for task in tasks
        if isinstance(task, Mapping) and task.get("task_id")
    }
    missing = sorted(REQUIRED_TASK_IDS - set(by_id))
    if missing:
        return _pending(f"missing holdout measurements: {', '.join(missing)}")

    task_reports: list[dict[str, Any]] = []
    efficiency_wins = 0
    for task_id in sorted(REQUIRED_TASK_IDS):
        task = by_id[task_id]
        baseline = task.get("baseline")
        cognition = task.get("cognition_map")
        if not isinstance(baseline, Mapping) or not isinstance(cognition, Mapping):
            task_reports.append({"task_id": task_id, "status": "PENDING"})
            continue
        fields = (
            "completed",
            "correct",
            "unsupported_high_confidence_claims",
            "elapsed_seconds",
            "opened_object_count",
            "navigation_steps",
            "subjective_misdirection_points",
        )
        missing_fields = sorted(
            field for field in fields if field not in baseline or field not in cognition
        )
        if missing_fields or not _valid_measurement_pair(baseline, cognition):
            task_reports.append(
                {
                    "task_id": task_id,
                    "status": "PENDING",
                    "missing_fields": missing_fields,
                }
            )
            continue

        correctness_preserved = bool(cognition["correct"]) >= bool(baseline["correct"])
        no_unsupported = cognition["unsupported_high_confidence_claims"] == 0
        efficiency_win = (
            correctness_preserved
            and no_unsupported
            and (
                cognition["elapsed_seconds"] < baseline["elapsed_seconds"]
                or cognition["opened_object_count"] < baseline["opened_object_count"]
            )
        )
        if efficiency_win:
            efficiency_wins += 1
        task_reports.append(
            {
                "task_id": task_id,
                "status": "MEASURED",
                "correctness_preserved": correctness_preserved,
                "no_unsupported_high_confidence": no_unsupported,
                "efficiency_win": efficiency_win,
            }
        )

    all_measured = all(row["status"] == "MEASURED" for row in task_reports)
    efficiency_status = "PASS" if all_measured and efficiency_wins >= 3 else "PENDING"
    user_value = measurements.get("user_value")
    user_value_confirmed = (
        isinstance(user_value, Mapping)
        and user_value.get("status") == "CONFIRMED"
        and user_value.get("confirmed") is True
        and bool(str(user_value.get("rationale", "")).strip())
    )
    return {
        "status": "MEASURED" if all_measured else "PENDING",
        "efficiency_status": efficiency_status,
        "efficiency_win_count": efficiency_wins,
        "user_value_status": "CONFIRMED" if user_value_confirmed else "PENDING",
        "task_reports": task_reports,
    }


def _pending(reason: str) -> dict[str, Any]:
    return {
        "status": "PENDING",
        "efficiency_status": "PENDING",
        "efficiency_win_count": 0,
        "user_value_status": "PENDING",
        "task_reports": [],
        "reason": reason,
    }


def _valid_measurement_pair(
    baseline: Mapping[str, Any], cognition: Mapping[str, Any]
) -> bool:
    for values in (baseline, cognition):
        if not isinstance(values["completed"], bool) or not isinstance(
            values["correct"], bool
        ):
            return False
        for field in (
            "unsupported_high_confidence_claims",
            "elapsed_seconds",
            "opened_object_count",
            "navigation_steps",
            "subjective_misdirection_points",
        ):
            value = values[field]
            if isinstance(value, bool) or not isinstance(value, Real) or value < 0:
                return False
    return bool(baseline["completed"]) and bool(cognition["completed"])
