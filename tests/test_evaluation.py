import pytest

from titans_cognition.evaluation import evaluate_tradeflow, render_review_pack


REQUIRED_HOLDOUT_IDS = (
    "holdout_technical_vs_business_identity_001",
    "holdout_role_and_counterevidence_001",
    "holdout_relation_layer_direction_001",
    "holdout_unknown_no_key_001",
)


def _complete_measurements() -> dict:
    metrics = {
        "completed": True,
        "correct": True,
        "unsupported_high_confidence_claims": 0,
        "elapsed_seconds": 10,
        "opened_object_count": 5,
        "navigation_steps": 4,
        "subjective_misdirection_points": 0,
    }
    tasks = []
    for index, task_id in enumerate(REQUIRED_HOLDOUT_IDS):
        cognition = dict(metrics)
        cognition["elapsed_seconds"] = 5 if index < 3 else 10
        tasks.append(
            {"task_id": task_id, "baseline": metrics, "cognition_map": cognition}
        )
    return {
        "status": "MEASURED",
        "tasks": tasks,
        "user_value": {
            "status": "CONFIRMED",
            "confirmed": True,
            "rationale": "The map reduced undirected browsing and exposed evidence boundaries.",
        },
    }


def test_draft_gold_set_is_not_counted_or_promoted_to_gate_b():
    inference = {
        "identity_candidates": [],
        "grain_candidates": [],
        "field_role_candidates": [],
        "object_role_candidates": [],
        "relation_candidates": [],
        "inference_results": [],
        "evidence_items": [],
        "candidate_evidence": [],
    }
    gold = {
        "status": "DRAFT",
        "scope_id": "tradeflow-deep-v1",
        "cases": [
            {
                "case_id": "draft-unknown",
                "task": "IDENTITY",
                "subject_ref": "asset-1",
                "annotation_status": "DRAFT",
                "expected": {"outcome": "UNKNOWN", "accepted_values": []},
            }
        ],
        "holdout_tasks": [],
    }
    report = evaluate_tradeflow(
        inference,
        gold,
        {"gate_b": {"efficiency_evidence_confirmed": False, "user_value_confirmed": False}},
    )
    assert report["adjudicated_case_count"] == 0
    assert report["gate_b"]["status"] == "BLOCKED"
    assert report["v1c_authorized"] is False
    assert report["scale_authorization"]["status"] == "PROHIBITED"
    assert "no ADJUDICATED Gold Set cases" in report["gate_b"]["reasons"]
    assert report["case_reports"][0]["evaluation_status"] == "DRAFT_NOT_COUNTED"
    assert all(
        error["error_category"] != "INVALID_GOLD_SET"
        for error in report["case_reports"][0]["errors"]
    )


def test_evaluation_requires_all_competing_values_and_rejects_unacceptable_value():
    inference = {
        "identity_candidates": [],
        "grain_candidates": [],
        "field_role_candidates": [],
        "object_role_candidates": [
            {"candidate_id": "c1", "object_role": "EVENT_TRANSACTION"},
            {"candidate_id": "c2", "object_role": "STATE_HISTORY"},
            {"candidate_id": "c3", "object_role": "SNAPSHOT"},
        ],
        "relation_candidates": [],
        "inference_results": [
            {
                "task_type": "OBJECT_ROLE",
                "subject_id": "asset-1",
                "outcome": "COMPETING",
                "candidate_ids": ["c1", "c2", "c3"],
            }
        ],
        "evidence_items": [],
        "candidate_evidence": [],
    }
    report = evaluate_tradeflow(
        inference,
        {
            "status": "DRAFT",
            "cases": [
                {
                    "case_id": "strict-role",
                    "task": "OBJECT_ROLE",
                    "subject_ref": "asset-1",
                    "annotation_status": "DRAFT",
                    "expected": {
                        "outcome": "COMPETING",
                        "accepted_values": ["EVENT_TRANSACTION", "STATE_HISTORY"],
                        "unacceptable_values": ["SNAPSHOT"],
                    },
                }
            ],
            "holdout_tasks": [],
        },
        {"gate_b": {}},
    )
    assert report["case_reports"][0]["correct"] is False
    assert report["case_reports"][0]["errors"][0]["error_category"] == "ROLE_OVERCLASSIFICATION"


def test_review_pack_is_descriptive_and_does_not_adjudicate():
    report = {
        "gold_set_status": "DRAFT",
        "gold_set_case_count": 1,
        "adjudicated_case_count": 0,
        "gate_b": {"status": "BLOCKED", "reasons": ["needs review"]},
        "case_reports": [
            {
                "case_id": "c1",
                "task": "IDENTITY",
                "subject_ref": "asset-1",
                "annotation_status": "DRAFT",
                "expected_outcome": "UNKNOWN",
                "actual_outcome": "UNKNOWN",
                "correct": True,
                "actual_candidate_values": [],
                "evidence_check": {"actual_types": []},
                "errors": [],
            }
        ],
    }
    text = render_review_pack(report)
    assert "Gate B (structural regression only): `BLOCKED`" in text
    assert "Annotation: `DRAFT`" in text
    assert "does not create review decisions" in text


def test_gate_b_pass_does_not_authorize_scale():
    inference = {
        "identity_candidates": [],
        "grain_candidates": [],
        "field_role_candidates": [],
        "object_role_candidates": [],
        "relation_candidates": [],
        "inference_results": [
            {
                "task_type": "IDENTITY",
                "subject_id": "asset-unknown",
                "outcome": "UNKNOWN",
                "candidate_ids": [],
            }
        ],
        "evidence_items": [],
        "candidate_evidence": [],
    }
    gold = {
        "status": "ADJUDICATED",
        "scope_id": "tradeflow-deep-v1",
        "cases": [
            {
                "case_id": "adjudicated-unknown",
                "task": "IDENTITY",
                "subject_ref": "asset-unknown",
                "annotation_status": "ADJUDICATED",
                "expected": {"outcome": "UNKNOWN", "accepted_values": []},
            }
        ],
        "holdout_tasks": [
            {"case_id": case_id, "annotation_status": "ADJUDICATED"}
            for case_id in REQUIRED_HOLDOUT_IDS
        ],
    }
    report = evaluate_tradeflow(
        inference,
        gold,
        {
            "gate_b": {
                "efficiency_evidence_confirmed": True,
                "user_value_confirmed": True,
            }
        },
        _complete_measurements(),
    )

    assert report["gate_b"]["status"] == "PASS"
    assert report["gate_b"]["scope"] == "STRUCTURAL_REGRESSION_ONLY"
    assert report["structural_regression"]["reasons"] == []
    assert report["v1c_authorized"] is False
    assert report["scale_authorization"]["status"] == "PROHIBITED"
    assert report["business_acceptance"]["status"] == "NOT_ACCEPTED"
    assert report["delivery_status"] == {
        "physical_extraction": "NOT_EVALUATED_BY_THIS_REPORT",
        "structural_cognition": "PROTOTYPE_REGRESSION_PASS",
        "reader_delivery": "NOT_EVALUATED_BY_THIS_REPORT",
        "business_acceptance": "NOT_ACCEPTED",
        "scale_authorization": "PROHIBITED",
    }
    assert report["scale_authorization"]["reason"]
    assert report["business_acceptance"]["reason"]

    structural_only_report = evaluate_tradeflow(inference, gold, {"gate_b": {}}, None)
    assert structural_only_report["gate_b"]["status"] == "BLOCKED"
    assert structural_only_report["structural_regression"]["status"] == "PASS"
    assert structural_only_report["delivery_status"]["structural_cognition"] == (
        "PROTOTYPE_REGRESSION_PASS"
    )


@pytest.mark.parametrize(
    "holdout_tasks",
    [
        [{"case_id": REQUIRED_HOLDOUT_IDS[0], "annotation_status": "ADJUDICATED"}],
        [
            {"case_id": REQUIRED_HOLDOUT_IDS[0], "annotation_status": "ADJUDICATED"}
            for _ in range(4)
        ],
        [
            *[
                {"case_id": case_id, "annotation_status": "ADJUDICATED"}
                for case_id in REQUIRED_HOLDOUT_IDS
            ],
            {"case_id": "unexpected-holdout", "annotation_status": "ADJUDICATED"},
        ],
        [
            *[
                {"case_id": case_id, "annotation_status": "ADJUDICATED"}
                for case_id in REQUIRED_HOLDOUT_IDS[:3]
            ],
            {"annotation_status": "ADJUDICATED"},
        ],
        [
            *[
                {"case_id": case_id, "annotation_status": "ADJUDICATED"}
                for case_id in REQUIRED_HOLDOUT_IDS
            ],
            "invalid-holdout-entry",
        ],
    ],
)
def test_gate_b_requires_exact_unique_holdout_cases(holdout_tasks):
    inference = {
        "identity_candidates": [],
        "grain_candidates": [],
        "field_role_candidates": [],
        "object_role_candidates": [],
        "relation_candidates": [],
        "inference_results": [
            {
                "task_type": "IDENTITY",
                "subject_id": "asset-unknown",
                "outcome": "UNKNOWN",
                "candidate_ids": [],
            }
        ],
        "evidence_items": [],
        "candidate_evidence": [],
    }
    gold = {
        "status": "ADJUDICATED",
        "cases": [
            {
                "case_id": "adjudicated-unknown",
                "task": "IDENTITY",
                "subject_ref": "asset-unknown",
                "annotation_status": "ADJUDICATED",
                "expected": {"outcome": "UNKNOWN", "accepted_values": []},
            }
        ],
        "holdout_tasks": holdout_tasks,
    }

    report = evaluate_tradeflow(
        inference,
        gold,
        {
            "gate_b": {
                "efficiency_evidence_confirmed": True,
                "user_value_confirmed": True,
            }
        },
        _complete_measurements(),
    )

    assert report["gate_b"]["status"] == "BLOCKED"
    assert "four required holdout cases are not uniquely adjudicated" in report[
        "gate_b"
    ]["reasons"]
    assert report["delivery_status"]["structural_cognition"] == (
        "PROTOTYPE_REGRESSION_BLOCKED"
    )
    assert report["structural_regression"]["reasons"]
    assert report["scale_authorization"]["status"] == "PROHIBITED"


def test_gate_b_measurements_require_real_values_and_three_efficiency_wins():
    from titans_cognition.measurements import evaluate_gate_b_measurements

    pending = evaluate_gate_b_measurements({"tasks": []})
    assert pending["efficiency_status"] == "PENDING"
    measured = evaluate_gate_b_measurements(_complete_measurements())
    assert measured["efficiency_status"] == "PASS"
    assert measured["efficiency_win_count"] == 3
    assert measured["user_value_status"] == "CONFIRMED"

    duplicate = _complete_measurements()
    duplicate["tasks"].append(dict(duplicate["tasks"][0]))
    duplicate_report = evaluate_gate_b_measurements(duplicate)
    assert duplicate_report["efficiency_status"] == "PENDING"
    assert "duplicate holdout measurements" in duplicate_report["reason"]

    unexpected = _complete_measurements()
    unexpected["tasks"].append({"task_id": "unexpected-holdout"})
    unexpected_report = evaluate_gate_b_measurements(unexpected)
    assert unexpected_report["efficiency_status"] == "PENDING"
    assert "unexpected holdout measurements" in unexpected_report["reason"]


def test_measurement_pack_keeps_all_four_holdouts_and_both_materials():
    from titans_cognition.measurements import render_measurement_pack

    text = render_measurement_pack(
        {
            "protocol": {"baseline_material": "baseline", "cognition_material": "map"},
            "tasks": [
                {"task_id": "holdout_technical_vs_business_identity_001"},
                {"task_id": "holdout_role_and_counterevidence_001"},
                {"task_id": "holdout_relation_layer_direction_001"},
                {"task_id": "holdout_unknown_no_key_001"},
            ],
        }
    )
    assert text.count("| `holdout_") == 8
    assert "Unsupported high-confidence claims" in text
    assert "At least three tasks" in text
