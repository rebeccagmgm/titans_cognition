from titans_cognition.deep import derive_tradeflow_features, select_tradeflow_sample
from titans_cognition.extract import PhysicalFacts
from titans_cognition.inference import infer_tradeflow


def _facts() -> PhysicalFacts:
    objects = []
    columns = []
    constraints = []
    indexes = []
    for name, stratum, width in (
        ("A_COMPOSITE", "PK_COMPOSITE", 2),
        ("B_SINGLE", "PK_SINGLE", 1),
        ("C_UNIQUE", "UK_ONLY", 1),
        ("D_INDEX", "NO_KEY_WITH_INDEX", 1),
        ("E_NONE", "NO_DECLARED_KEY", 1),
        ("F_PEER", "NO_DECLARED_KEY", 1),
    ):
        asset = f"testdb:TITANS_TRADEFLOW:TABLE:{name}"
        objects.append(
            {
                "run_id": "run-1",
                "asset_id": asset,
                "schema_name": "TITANS_TRADEFLOW",
                "object_name": name,
                "object_type": "TABLE",
                "object_comment": "测试对象",
                "extraction_status": "SUCCESS",
                "is_boundary": False,
            }
        )
        for ordinal in range(1, width + 1):
            columns.append(
                {
                    "asset_id": asset,
                    "column_id": f"{asset}:COLUMN:ID{ordinal}",
                    "column_name": f"ID{ordinal}",
                    "ordinal_position": ordinal,
                    "data_type": "NUMBER",
                    "column_comment": "标识字段",
                    "nullable_declared": False,
                }
            )
        if stratum == "PK_COMPOSITE":
            constraints.append(
                {
                    "constraint_id": f"{asset}:CONSTRAINT:PK",
                    "asset_id": asset,
                    "constraint_type": "PRIMARY_KEY",
                    "column_ids": [f"{asset}:COLUMN:ID1", f"{asset}:COLUMN:ID2"],
                }
            )
        elif stratum == "PK_SINGLE":
            constraints.append(
                {
                    "constraint_id": f"{asset}:CONSTRAINT:PK",
                    "asset_id": asset,
                    "constraint_type": "PRIMARY_KEY",
                    "column_ids": [f"{asset}:COLUMN:ID1"],
                }
            )
        elif stratum == "UK_ONLY":
            constraints.append(
                {
                    "constraint_id": f"{asset}:CONSTRAINT:UK",
                    "asset_id": asset,
                    "constraint_type": "UNIQUE_KEY",
                    "column_ids": [f"{asset}:COLUMN:ID1"],
                }
            )
        elif stratum == "NO_KEY_WITH_INDEX":
            indexes.append(
                {
                    "asset_id": asset,
                    "index_id": f"{asset}:INDEX:I1",
                    "column_ids": [f"{asset}:COLUMN:ID1"],
                }
            )
    return PhysicalFacts(
        objects=objects,
        columns=columns,
        constraints=constraints,
        indexes=indexes,
    )


def test_tradeflow_sample_is_stratified_and_deterministic():
    first = select_tradeflow_sample(_facts())
    second = select_tradeflow_sample(_facts())
    assert first == second
    assert {row["stratum"] for row in first["selected_objects"]} == {
        "PK_COMPOSITE",
        "PK_SINGLE",
        "UK_ONLY",
        "NO_KEY_WITH_INDEX",
        "NO_DECLARED_KEY",
    }
    composite = next(
        row for row in first["selected_objects"] if row["stratum"] == "PK_COMPOSITE"
    )
    assert composite["object_name"] == "A_COMPOSITE"


def test_tradeflow_sample_can_exclude_numeric_suffix_objects():
    facts = _facts()
    facts.objects.append(
        {
            "run_id": "run-1",
            "asset_id": "testdb:TITANS_TRADEFLOW:TABLE:Z_NONE_20250101",
            "schema_name": "TITANS_TRADEFLOW",
            "object_name": "Z_NONE_20250101",
            "object_type": "TABLE",
            "extraction_status": "SUCCESS",
            "is_boundary": False,
        }
    )
    facts.columns.append(
        {
            "asset_id": "testdb:TITANS_TRADEFLOW:TABLE:Z_NONE_20250101",
            "column_id": "testdb:TITANS_TRADEFLOW:TABLE:Z_NONE_20250101:COLUMN:ID",
            "column_name": "ID",
            "ordinal_position": 1,
            "data_type": "NUMBER",
        }
    )
    facts.columns.append(
        {
            "asset_id": "testdb:TITANS_TRADEFLOW:TABLE:Z_NONE_20250101",
            "column_id": "testdb:TITANS_TRADEFLOW:TABLE:Z_NONE_20250101:COLUMN:ID2",
            "column_name": "ID2",
            "ordinal_position": 2,
            "data_type": "NUMBER",
        }
    )
    sample = select_tradeflow_sample(facts)
    assert all(
        not str(row["object_name"]).endswith(tuple(str(value) for value in range(10)))
        for row in sample["selected_objects"]
    )


def test_tradeflow_features_keep_unknown_business_meaning_out():
    sample = select_tradeflow_sample(_facts())
    derived = derive_tradeflow_features(_facts(), sample)
    assert derived.object_features
    assert derived.column_features
    assert derived.structure_similarity
    assert all("identity" not in row for row in derived.object_features)
    assert all(row["method_id"].startswith("feature.") for row in derived.column_features)
    assert all(row["object_comment"] == "测试对象" for row in derived.object_features)
    assert all(row["column_comment"] == "标识字段" for row in derived.column_features)


def test_tradeflow_inference_links_candidates_to_evidence_and_keeps_unknown():
    facts = _facts()
    sample = select_tradeflow_sample(facts)
    derived = derive_tradeflow_features(facts, sample)
    inference = infer_tradeflow(facts, derived)

    assert inference.identity_candidates
    assert inference.grain_candidates
    assert inference.candidate_evidence
    candidate_ids = {
        row["candidate_id"]
        for rows in (
            inference.identity_candidates,
            inference.grain_candidates,
            inference.field_role_candidates,
            inference.object_role_candidates,
            inference.relation_candidates,
        )
        for row in rows
    }
    linked_ids = {row["candidate_id"] for row in inference.candidate_evidence}
    assert candidate_ids
    assert candidate_ids <= linked_ids
    assert inference.relation_candidates == []
    assert inference.object_role_candidates == []
    assert any(
        row["evidence_type"] == "COMMENT"
        and row["summary"] == "测试对象"
        for row in inference.evidence_items
    )
    assert any(
        row["task_type"] == "IDENTITY"
        and row["outcome"] == "UNKNOWN"
        and row["subject_id"].endswith(":E_NONE")
        for row in inference.inference_results
    )
    assert all(row["evaluation_eligibility"] == "EVALUABLE" for row in inference.inference_results)


def test_comment_signals_create_weak_role_candidates_with_comment_evidence():
    facts = _facts()
    facts.objects[1]["object_comment"] = "历史持仓表"
    facts.columns[1]["column_comment"] = "数量"
    sample = select_tradeflow_sample(facts)
    derived = derive_tradeflow_features(facts, sample)
    inference = infer_tradeflow(facts, derived)

    assert any(
        row.get("object_role") == "STATE_HISTORY"
        and row.get("evidence_grade") == "WEAK"
        for row in inference.object_role_candidates
    )
    assert any(
        row.get("field_role") == "QUANTITY"
        and row.get("evidence_grade") == "WEAK"
        for row in inference.field_role_candidates
    )
    assert any(
        row["evidence_type"] == "COMMENT" and row["summary"] in {"历史持仓表", "数量"}
        for row in inference.evidence_items
    )
