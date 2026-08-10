"""V1B Gold Set evaluation with explicit draft and gate semantics."""

from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any

import yaml


def load_yaml_mapping(path: str | Path) -> dict[str, Any]:
    """Load a UTF-8 YAML mapping used for Gold Set or review input."""

    value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return value


def load_inference_directory(path: str | Path) -> dict[str, list[dict[str, object]]]:
    """Load the JSON V1B result tables without changing their row content."""

    root = Path(path) / "deep-cases" / "tradeflow"
    names = {
        "identity_candidates": root / "candidates" / "identity_candidates.json",
        "grain_candidates": root / "candidates" / "grain_candidates.json",
        "field_role_candidates": root / "candidates" / "field_role_candidates.json",
        "object_role_candidates": root / "candidates" / "object_role_candidates.json",
        "relation_candidates": root / "candidates" / "relation_candidates.json",
        "inference_results": root / "candidates" / "inference_results.json",
        "evidence_items": root / "evidence" / "evidence_items.json",
        "candidate_evidence": root / "evidence" / "candidate_evidence.json",
    }
    loaded: dict[str, list[dict[str, object]]] = {}
    for name, file_path in names.items():
        value = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
            raise ValueError(f"inference output is not a row list: {file_path}")
        loaded[name] = value
    return loaded


def evaluate_tradeflow(
    inference: dict[str, list[dict[str, object]]],
    gold_set: dict[str, Any],
    reviews: dict[str, Any],
) -> dict[str, object]:
    """Evaluate adjudicated Gold cases and report why Gate B is blocked."""

    cases = gold_set.get("cases", [])
    if not isinstance(cases, list):
        raise ValueError("Gold Set cases must be a list")
    evidence_items = inference.get("evidence_items", [])
    links_by_candidate: dict[str, list[dict[str, object]]] = defaultdict(list)
    for link in inference.get("candidate_evidence", []):
        links_by_candidate[str(link.get("candidate_id"))].append(link)
    evidence_by_id = {str(row.get("evidence_id")): row for row in evidence_items}
    candidates_by_task = _candidates_by_task(inference)

    case_reports: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    adjudicated_reports: list[dict[str, object]] = []
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("each Gold Set case must be a mapping")
        status = str(case.get("annotation_status", "DRAFT"))
        report = _evaluate_case(
            case,
            inference.get("inference_results", []),
            candidates_by_task,
            links_by_candidate,
            evidence_by_id,
        )
        report["annotation_status"] = status
        if status != "ADJUDICATED":
            report["evaluation_status"] = "DRAFT_NOT_COUNTED"
        else:
            report["evaluation_status"] = "COUNTED"
            adjudicated_reports.append(report)
            errors.extend(report.get("errors", []))
        case_reports.append(report)

    all_candidate_ids = {
        str(row.get("candidate_id"))
        for rows in candidates_by_task.values()
        for row in rows
    }
    linked_candidate_ids = set(links_by_candidate)
    unsupported_candidates = sorted(all_candidate_ids - linked_candidate_ids)
    holdout_tasks = gold_set.get("holdout_tasks", [])
    holdout_complete = bool(holdout_tasks) and all(
        isinstance(task, dict) and task.get("annotation_status") == "ADJUDICATED"
        for task in holdout_tasks
    )
    gate_b = {
        "status": "PASS"
        if (
            bool(adjudicated_reports)
            and not errors
            and not unsupported_candidates
            and holdout_complete
            and bool(reviews.get("gate_b", {}).get("efficiency_evidence_confirmed"))
            and bool(reviews.get("gate_b", {}).get("user_value_confirmed"))
        )
        else "BLOCKED",
        "reasons": [],
    }
    if not adjudicated_reports:
        gate_b["reasons"].append("no ADJUDICATED Gold Set cases")
    if errors:
        gate_b["reasons"].append("adjudicated cases contain errors")
    if unsupported_candidates:
        gate_b["reasons"].append("candidate evidence coverage is incomplete")
    if not holdout_complete:
        gate_b["reasons"].append("four holdout tasks are not adjudicated")
    if not reviews.get("gate_b", {}).get("efficiency_evidence_confirmed"):
        gate_b["reasons"].append("efficiency evidence is not confirmed")
    if not reviews.get("gate_b", {}).get("user_value_confirmed"):
        gate_b["reasons"].append("user value is not confirmed")

    counted_outcomes = Counter(
        str(report.get("actual_outcome")) for report in adjudicated_reports
    )
    return {
        "version": "v1",
        "case_id": gold_set.get("scope_id", "tradeflow-deep-v1"),
        "gold_set_status": gold_set.get("status", "DRAFT"),
        "gold_set_case_count": len(cases),
        "adjudicated_case_count": len(adjudicated_reports),
        "task_outcome_counts": dict(counted_outcomes),
        "case_reports": case_reports,
        "errors": errors,
        "evidence_quality": {
            "candidate_count": len(all_candidate_ids),
            "linked_candidate_count": len(all_candidate_ids & linked_candidate_ids),
            "unsupported_candidate_count": len(unsupported_candidates),
            "unknown_result_count": sum(
                row.get("outcome") == "UNKNOWN"
                for row in inference.get("inference_results", [])
            ),
        },
        "not_evaluable_results": [
            row
            for row in inference.get("inference_results", [])
            if row.get("evaluation_eligibility") == "NOT_EVALUABLE"
        ],
        "gate_a_status": "PASS",
        "gate_b": gate_b,
        "v1c_authorized": gate_b["status"] == "PASS",
    }


def render_review_pack(report: dict[str, object]) -> str:
    """Render a compact human-review document from an evaluation report."""

    gate_b = report.get("gate_b", {})
    lines = [
        "# TRADEFLOW V1B Review Pack",
        "",
        f"- Gold Set status: `{report.get('gold_set_status')}`",
        f"- Cases: `{report.get('gold_set_case_count')}`",
        f"- Adjudicated: `{report.get('adjudicated_case_count')}`",
        f"- Gate B: `{gate_b.get('status')}`",
        "",
        "This pack is a review aid. It does not create review decisions or authorize V1C.",
        "",
        "## Cases",
        "",
    ]
    for case in report.get("case_reports", []):
        status = case.get("annotation_status")
        lines.extend(
            [
                f"### {case.get('case_id')}",
                "",
                f"- Task: `{case.get('task')}`",
                f"- Subject: `{case.get('subject_ref')}`",
                f"- Annotation: `{status}`",
                f"- Expected: `{case.get('expected_outcome')}`",
                f"- Actual: `{case.get('actual_outcome')}`",
                f"- Draft match: `{case.get('correct')}`",
            ]
        )
        actual_values = case.get("actual_candidate_values", [])
        if actual_values:
            lines.append(f"- Actual candidate values: `{json.dumps(actual_values, ensure_ascii=False)}`")
        evidence = case.get("evidence_check", {})
        lines.append(f"- Evidence types observed: `{', '.join(evidence.get('actual_types', [])) or 'none'}`")
        if case.get("errors"):
            lines.append("- Review flags:")
            for error in case["errors"]:
                lines.append(f"  - `{error.get('error_category')}`: {error.get('message')}")
        else:
            lines.append("- Review flags: none from the current automated checks")
        lines.append("")
    lines.extend(
        [
            "## Gate B blockers",
            "",
        ]
    )
    for reason in gate_b.get("reasons", []):
        lines.append(f"- {reason}")
    lines.append("")
    return "\n".join(lines)


def _evaluate_case(
    case: dict[str, Any],
    results: list[dict[str, object]],
    candidates_by_task: dict[str, list[dict[str, object]]],
    links_by_candidate: dict[str, list[dict[str, object]]],
    evidence_by_id: dict[str, dict[str, object]],
) -> dict[str, object]:
    task = str(case.get("task", ""))
    subject = str(case.get("subject_ref", ""))
    expected = case.get("expected", {})
    expected_outcome = str(expected.get("outcome", ""))
    result = _find_result(results, task, subject)
    actual_outcome = str(result.get("outcome")) if result else "MISSING_RESULT"
    errors: list[dict[str, object]] = []
    accepted = [
        _value_key(_normalize_gold_value(task, value))
        for value in expected.get("accepted_values", [])
    ]
    unacceptable = [
        _value_key(_normalize_gold_value(task, value))
        for value in expected.get("unacceptable_values", [])
    ]
    actual_values = []
    candidate_rows = {str(row.get("candidate_id")): row for row in candidates_by_task.get(task, [])}
    if result:
        actual_values = [
            _candidate_value(task, candidate_rows[candidate_id])
            for candidate_id in result.get("candidate_ids", [])
            if candidate_id in candidate_rows
        ]
    actual_keys = {_value_key(value) for value in actual_values}
    correct = False
    if expected_outcome == "UNKNOWN":
        correct = actual_outcome == "UNKNOWN"
        if not correct and actual_outcome not in ("MISSING_RESULT", "NOT_EVALUABLE"):
            errors.append(
                {
                    "case_id": case.get("case_id"),
                    "error_category": _overclaim_category(task),
                    "message": "Gold expects UNKNOWN but the run published a candidate outcome.",
                }
            )
    elif expected_outcome in ("SINGLE_CANDIDATE", "COMPETING"):
        accepted_match = (
            bool(actual_keys & set(accepted))
            if expected_outcome == "SINGLE_CANDIDATE"
            else set(accepted) <= actual_keys
        )
        correct = actual_outcome == expected_outcome and accepted_match
        if not correct:
            errors.append(
                {
                    "case_id": case.get("case_id"),
                    "error_category": "INCORRECT_CANDIDATE",
                    "message": "Actual outcome or accepted candidate value does not match the adjudicated expectation.",
                }
            )
    else:
        errors.append(
            {
                "case_id": case.get("case_id"),
                "error_category": "INVALID_GOLD_SET",
                "message": f"Unsupported expected outcome: {expected_outcome}",
            }
        )
    if actual_keys & set(unacceptable):
        correct = False
        errors.append(
            {
                "case_id": case.get("case_id"),
                "error_category": _overclaim_category(task),
                "message": "The run published a value explicitly marked unacceptable by the Gold Set.",
            }
        )
    evidence_check = _evidence_check(
        result,
        candidate_rows,
        expected,
        links_by_candidate,
        evidence_by_id,
    )
    if evidence_check["missing"] and actual_outcome != "UNKNOWN":
        errors.append(
            {
                "case_id": case.get("case_id"),
                "error_category": "MISSING_EVIDENCE",
                "message": "The candidate does not cover the Gold Set evidence requirement.",
                "missing": evidence_check["missing"],
            }
        )
    return {
        "case_id": case.get("case_id"),
        "task": task,
        "subject_ref": subject,
        "expected_outcome": expected_outcome,
        "actual_outcome": actual_outcome,
        "actual_candidate_values": actual_values,
        "correct": correct,
        "evidence_check": evidence_check,
        "errors": errors,
    }


def _candidates_by_task(inference: dict[str, list[dict[str, object]]]) -> dict[str, list[dict[str, object]]]:
    return {
        "IDENTITY": inference.get("identity_candidates", []),
        "GRAIN": inference.get("grain_candidates", []),
        "FIELD_ROLE": inference.get("field_role_candidates", []),
        "OBJECT_ROLE": inference.get("object_role_candidates", []),
        "RELATION": inference.get("relation_candidates", []),
    }


def _find_result(results: list[dict[str, object]], task: str, subject: str) -> dict[str, object] | None:
    exact = [row for row in results if row.get("task_type") == task and row.get("subject_id") == subject]
    if exact:
        return exact[0]
    if task == "RELATION":
        relation_results = [row for row in results if row.get("task_type") == "RELATION"]
        return relation_results[0] if relation_results else None
    return None


def _candidate_value(task: str, candidate: dict[str, object]) -> object:
    if task == "IDENTITY":
        return sorted(candidate.get("column_ids", []))
    if task == "GRAIN":
        return sorted(candidate.get("grain_column_ids", []))
    if task == "FIELD_ROLE":
        return candidate.get("field_role")
    if task == "OBJECT_ROLE":
        return candidate.get("object_role")
    if task == "RELATION":
        return {
            "source_id": candidate.get("source_id"),
            "predicate": candidate.get("predicate"),
            "target_id": candidate.get("target_id"),
        }
    return candidate.get("candidate_id")


def _evidence_check(
    result: dict[str, object] | None,
    candidate_rows: dict[str, dict[str, object]],
    expected: dict[str, Any],
    links_by_candidate: dict[str, list[dict[str, object]]],
    evidence_by_id: dict[str, dict[str, object]],
) -> dict[str, object]:
    if result is None:
        return {"required": True, "missing": ["RESULT"]}
    required_types = set(expected.get("required_evidence_types", []))
    required_sources = set(expected.get("required_source_refs", []))
    actual_types: set[str] = set()
    actual_sources: set[str] = set()
    for candidate_id in result.get("candidate_ids", []):
        for link in links_by_candidate.get(str(candidate_id), []):
            evidence = evidence_by_id.get(str(link.get("evidence_id")))
            if evidence:
                actual_types.add(str(evidence.get("evidence_type")))
                actual_sources.add(str(evidence.get("source_id")))
    return {
        "required": bool(required_types or required_sources),
        "actual_types": sorted(actual_types),
        "actual_sources": sorted(actual_sources),
        "missing": sorted(
            [f"evidence_type:{value}" for value in required_types - actual_types]
            + [f"source_ref:{value}" for value in required_sources - actual_sources]
        ),
    }


def _value_key(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _normalize_gold_value(task: str, value: object) -> object:
    if task in ("IDENTITY", "GRAIN") and isinstance(value, list):
        return sorted(value)
    return value


def _overclaim_category(task: str) -> str:
    return {
        "IDENTITY": "TECHNICAL_KEY_CONFUSION",
        "GRAIN": "GRAIN_OVERREACH",
        "FIELD_ROLE": "ROLE_OVERCLASSIFICATION",
        "OBJECT_ROLE": "ROLE_OVERCLASSIFICATION",
        "RELATION": "FALSE_RELATION",
    }.get(task, "SHOULD_ABSTAIN")
