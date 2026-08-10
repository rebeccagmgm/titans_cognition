from titans_cognition.evaluation import evaluate_tradeflow, render_review_pack


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
    assert "Gate B: `BLOCKED`" in text
    assert "Annotation: `DRAFT`" in text
    assert "does not create review decisions" in text
