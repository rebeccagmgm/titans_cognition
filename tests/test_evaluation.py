from titans_cognition.evaluation import evaluate_tradeflow


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
