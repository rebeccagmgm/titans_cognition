import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from titans_cognition.table_semantics import (
    apply_table_review_decisions,
    RelationPredicate,
    InputSpec,
    TableSemanticResult,
    TableSemanticConfig,
    classify_physical_variants,
    derive_name_comment_signals,
    extract_approved_wiki_body_evidence,
    load_table_semantic_config,
    normalize_variant_name,
    run_table_semantic_map,
    validate_relation_candidate,
    validate_result_contracts,
    write_table_semantic_results,
    build_physical_field_summaries,
)
from titans_cognition.table_semantics import (
    _augment_field_support,
    _build_collaboration_groups,
    _evaluate_model_gate,
    _aggregate_relation_is_eligible,
    _aggregate_scope_sha256,
    _link_field_support_to_assertions,
    _wiki_recall,
)


def _asset(name: str) -> str:
    return f"testdb:TITANS_TRADEFLOW:TABLE:{name}"


def _object(name: str, comment: str = "") -> dict[str, object]:
    return {
        "asset_id": _asset(name),
        "schema_name": "TITANS_TRADEFLOW",
        "object_name": name,
        "object_type": "TABLE",
        "object_comment": comment,
    }


def _columns(name: str, *column_names: str) -> list[dict[str, object]]:
    return [
        {
            "asset_id": _asset(name),
            "column_id": f"{_asset(name)}:COLUMN:{column}",
            "column_name": column,
            "column_comment": "",
            "data_type": "VARCHAR2",
        }
        for column in column_names
    ]


@pytest.mark.parametrize(
    ("name", "expected_base", "expected_rule"),
    [
        ("REF_TRS_20260812", "REF_TRS", "dated_yyyymmdd"),
        ("REF_TRS_260812", "REF_TRS", "dated_yymmdd"),
        ("REF_TRS_BAK", "REF_TRS", "backup"),
        ("REF_TRS_BAK_20260812", "REF_TRS", "backup"),
        ("REF_TRS_V2", "REF_TRS", "version"),
        ("REF_TRS_17", "REF_TRS", "numeric_revision"),
    ],
)
def test_normalize_variant_name_is_conservative(
    name: str, expected_base: str, expected_rule: str
):
    base, rule = normalize_variant_name(name)
    assert (base, rule) == (expected_base, expected_rule)


def test_variant_classification_covers_positive_ambiguous_and_standalone_cases():
    objects = [
        _object("REF_TRS", "TRS contract"),
        _object("REF_TRS_20260812", "TRS contract backup"),
        _object("ONLY_20260812", "standalone dated table"),
        _object("DUAL"),
        _object("DUAL_V2"),
        _object("DUAL_2"),
    ]
    columns = []
    columns += _columns("REF_TRS", "ID", "TRS_ID", "STATUS")
    columns += _columns("REF_TRS_20260812", "ID", "TRS_ID", "STATUS")
    columns += _columns("ONLY_20260812", "ID", "VALUE")
    columns += _columns("DUAL", "ID")
    columns += _columns("DUAL_V2", "ID")
    columns += _columns("DUAL_2", "ID", "OTHER")

    rows, groups = classify_physical_variants(
        objects,
        columns,
        constraints=[],
        subject_asset_ids={_asset("REF_TRS"), _asset("DUAL")},
        max_candidates_per_table=3,
    )
    by_name = {row["object_name"]: row for row in rows}

    assert len(rows) == len(objects)
    assert by_name["REF_TRS"]["disposition"] == "SUBJECT"
    assert by_name["REF_TRS_20260812"]["disposition"] == "LIKELY_VARIANT"
    assert by_name["ONLY_20260812"]["disposition"] in {"STANDALONE", "UNKNOWN"}
    assert by_name["DUAL_V2"]["candidate_parent_asset_ids"] == [_asset("DUAL")]
    assert all(group["group_kind"] == "PHYSICAL_VARIANT_GROUP" for group in groups)


def test_name_and_comment_are_separate_signals_and_counterexamples_are_retained():
    config = TableSemanticConfig.for_tests()
    signals = derive_name_comment_signals(
        _object("REF_OTC_CONTR_REPORT", "场外合约主记录"), config
    )

    sources = {row["source_kind"] for row in signals}
    assert sources == {"TABLE_NAME", "TABLE_COMMENT"}
    assert any(row["candidate_kind"] == "TableResponsibility" for row in signals)
    assert any(row["conflict_key"] == "responsibility" for row in signals)
    assert len({row["root_source_family"] for row in signals}) == 1


def test_comment_expression_is_preserved_outside_seed_registry():
    config = TableSemanticConfig.for_tests()
    signals = derive_name_comment_signals(
        _object("TRD_FAST_TRS_FEE_LOG", "极速互换合约费用审批记录"), config
    )

    observed = [row for row in signals if row.get("vocabulary_layer") == "DISCOVERY"]
    assert [row["candidate_value"] for row in observed] == ["极速互换合约费用审批记录"]
    assert observed[0]["observed_expression"] == "极速互换合约费用审批记录"
    name_seed = next(
        row
        for row in signals
        if row["source_kind"] == "TABLE_NAME"
        and row["candidate_kind"] == "TableResponsibility"
        and row["candidate_value"] == "OPERATIONAL_LOG"
    )
    assert name_seed["vocabulary_layer"] == "SEED"
    assert name_seed["recommended_profile_eligible"] is False


def test_field_combination_links_to_specific_responsibility_assertion():
    asset_id = _asset("APPROVAL_RECORD")
    assertion = {
        "assertion_id": "assertion-approval",
        "subject_id": asset_id,
        "predicate": "HAS_TABLE_RESPONSIBILITY_CANDIDATE",
        "object_value": "APPROVAL_OR_AUDIT_TRAIL",
        "method_id": "test",
        "method_version": "v1",
        "evidence_refs": [],
        "counterevidence_refs": [],
        "root_source_families": [],
        "method_score": 1.0,
        "outcome": "CANDIDATE",
        "review_decision_ref": None,
    }
    result = TableSemanticResult(assertions=[assertion])
    summaries = [
        {
            "asset_id": asset_id,
            "markers": {"APPROVAL_AUDIT": ["APPROVAL_USER", "APPROVAL_TIME"]},
            "semantic_assistance": {
                "availability": "AVAILABLE",
                "candidate_count": 2,
                "field_candidates": [
                    {
                        "column_name": "APPROVAL_USER",
                        "usage_status": "NOT_USED",
                        "table_assertion_links": [],
                    }
                ],
            },
        }
    ]

    _link_field_support_to_assertions(result, summaries)

    assert result.assertions[0]["evidence_refs"]
    assert summaries[0]["assertion_links"][0]["role"] == "SUPPORTS"
    assert summaries[0]["field_assistance_status"] == "USED"
    assert (
        summaries[0]["semantic_assistance"]["field_candidates"][0]["usage_status"]
        == "USED_AS_PHYSICAL_COMBINATION"
    )
    assert result.evidence_refs[0]["source_kind"] == "FIELD_COMBINATION"


def test_precise_relation_requires_valid_endpoints_and_direct_evidence():
    predicate = RelationPredicate(
        name="CURRENT_HISTORY",
        directed=True,
        symmetric=False,
        min_direct_evidence=2,
    )
    assets = {_asset("CURRENT_POS"), _asset("HIS_POS")}

    downgraded = validate_relation_candidate(
        predicate,
        _asset("CURRENT_POS"),
        _asset("HIS_POS"),
        direct_evidence_refs=["name:1"],
        counterevidence_refs=[],
        known_asset_ids=assets,
    )
    assert downgraded["predicate"] == "RELATED_TO"
    assert downgraded["outcome"] == "UNKNOWN"

    with pytest.raises(ValueError, match="unknown relation endpoint"):
        validate_relation_candidate(
            predicate,
            _asset("CURRENT_POS"),
            _asset("MISSING"),
            direct_evidence_refs=["name:1", "fields:1"],
            counterevidence_refs=[],
            known_asset_ids=assets,
        )


def test_test_snapshot_aggregate_requires_complete_match_and_unique_target():
    aggregate = {
        "environment": "TEST",
        "query_sha256": "a" * 64,
        "observed_at": "2026-08-12T23:24:08+08:00",
        "event_rows": 213,
        "event_non_null": 213,
        "event_distinct_keys": 128,
        "contract_rows": 1228,
        "contract_non_null": 1228,
        "contract_distinct_keys": 1228,
        "matched_event_rows": 213,
        "unmatched_event_rows": 0,
        "contracts_with_events": 128,
        "deal_keys_with_multiple_events": 48,
        "max_events_per_deal": 7,
        "subject_table": "EVENT",
        "subject_key": "DEAL_ID",
        "predicate": "EVENT_OF",
        "object_table": "DEAL",
        "object_key": "ID",
    }
    aggregate["authorization_scope_sha256"] = _aggregate_scope_sha256(aggregate)

    assert _aggregate_relation_is_eligible(aggregate, {"DEAL_ID"}, {"ID"}) == (True, [])

    invalid = {**aggregate, "unmatched_event_rows": 1, "matched_event_rows": 212}
    eligible, reasons = _aggregate_relation_is_eligible(invalid, {"DEAL_ID"}, {"ID"})
    assert eligible is False
    assert "event keys are not fully matched" in reasons

    duplicate_target = {**aggregate, "contract_distinct_keys": 1227}
    eligible, reasons = _aggregate_relation_is_eligible(duplicate_target, {"DEAL_ID"}, {"ID"})
    assert eligible is False
    assert "contract target key is not unique" in reasons

    zero = {
        **aggregate,
        **{name: 0 for name in (
            "event_rows", "event_non_null", "event_distinct_keys", "contract_rows",
            "contract_non_null", "contract_distinct_keys", "matched_event_rows",
            "unmatched_event_rows", "contracts_with_events", "deal_keys_with_multiple_events",
            "max_events_per_deal",
        )},
    }
    eligible, reasons = _aggregate_relation_is_eligible(zero, {"DEAL_ID"}, {"ID"})
    assert eligible is False
    assert "aggregate contains no positive relationship evidence" in reasons

    eligible, reasons = _aggregate_relation_is_eligible(aggregate, {"OTHER"}, {"ID"})
    assert eligible is False
    assert "subject key is missing from the subject table" in reasons

    drifted_scope = {**aggregate, "subject_key": "OTHER"}
    eligible, reasons = _aggregate_relation_is_eligible(drifted_scope, {"OTHER"}, {"ID"})
    assert eligible is False
    assert "authorization scope does not match endpoints, keys and query fingerprint" in reasons

    contradictory = {
        **aggregate,
        "event_rows": 1,
        "event_non_null": 1,
        "matched_event_rows": 1,
        "event_distinct_keys": 2,
        "contracts_with_events": 2,
        "contract_rows": 1,
        "contract_non_null": 1,
        "contract_distinct_keys": 1,
    }
    eligible, reasons = _aggregate_relation_is_eligible(
        contradictory, {"DEAL_ID"}, {"ID"}
    )
    assert eligible is False
    assert "event distinct keys exceed event rows" in reasons
    assert "matched contracts exceed available unique contracts" in reasons


def test_leg_id_is_retained_as_a_table_relation_anchor():
    summaries = build_physical_field_summaries(
        [_object("REF_TRS_LEG"), _object("POS_TRS_LEG_CURRENT_POS")],
        _columns("REF_TRS_LEG", "KEY_LEG_ID", "KEY_OTC_TRADE_ID")
        + _columns("POS_TRS_LEG_CURRENT_POS", "KEY_LEG_ID", "KEY_LEG_POSITION_ID"),
    )
    by_asset = {row["asset_id"]: row for row in summaries}

    assert "KEY_LEG_ID" in by_asset[_asset("REF_TRS_LEG")]["markers"]["ANCHOR_ID"]
    assert "KEY_LEG_ID" in by_asset[_asset("POS_TRS_LEG_CURRENT_POS")]["markers"]["ANCHOR_ID"]


def test_config_rejects_drifted_manifest_and_invalid_precise_registry(tmp_path: Path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    config_path = tmp_path / "table-map.yaml"
    config_path.write_text(
        f"""
version: v1
scope:
  schema: TITANS_TRADEFLOW
  object_types: [TABLE]
  expected_all_tables: 1
  expected_subject_tables: 1
  expected_variant_or_other_tables: 0
inputs:
  physical_facts: {{path: {tmp_path.as_posix()}, manifest: manifest.json, manifest_sha256: {digest}}}
  classification: {{path: {tmp_path.as_posix()}, manifest: manifest.json, manifest_sha256: {digest}}}
limits: {{max_variant_rules: 1, max_variant_candidates_per_table: 1}}
variant_rules: [{{id: dated, pattern: '_\\d{{8}}$'}}]
relation_registry:
  version: v1
  predicates:
    RELATED_TO: {{directed: false, symmetric: true, min_direct_evidence: 1}}
""",
        encoding="utf-8",
    )

    config = load_table_semantic_config(config_path)
    assert config.scope_schema == "TITANS_TRADEFLOW"

    manifest.write_text('{"drift": true}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_table_semantic_config(config_path)


def test_optional_field_input_drift_becomes_not_evaluable(tmp_path: Path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    config_path = tmp_path / "optional.yaml"
    config_path.write_text(
        f"""
version: v1
scope: {{schema: TITANS_TRADEFLOW, object_types: [TABLE]}}
inputs:
  physical_facts: {{path: {tmp_path.as_posix()}, manifest: manifest.json, manifest_sha256: {digest}}}
  classification: {{path: {tmp_path.as_posix()}, manifest: manifest.json, manifest_sha256: {digest}}}
  field_semantics: {{path: {tmp_path.as_posix()}, manifest: manifest.json, manifest_sha256: {'0' * 64}, required: false}}
  field_context: {{path: {(tmp_path / 'missing').as_posix()}, manifest: manifest.json, manifest_sha256: {'1' * 64}, required: false}}
limits: {{max_variant_rules: 1}}
variant_rules: [{{id: dated, pattern: '_\\d{{8}}$'}}]
relation_registry:
  version: v1
  predicates:
    RELATED_TO: {{directed: false, symmetric: true, min_direct_evidence: 1}}
""",
        encoding="utf-8",
    )

    config = load_table_semantic_config(config_path)
    assert config.inputs["field_semantics"].availability == "NOT_EVALUABLE"
    assert config.inputs["field_semantics"].diagnostic == "manifest hash mismatch"
    assert config.inputs["field_context"].availability == "NOT_EVALUABLE"
    assert config.inputs["field_context"].diagnostic == "manifest missing"


def test_partially_invalid_field_rows_do_not_block_table_evidence(tmp_path: Path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    (tmp_path / "field_semantic_results.jsonl").write_text(
        '{"asset_id":"asset:1"}\n{invalid-json}\n', encoding="utf-8"
    )
    spec = InputSpec(
        name="field_semantics",
        path=tmp_path,
        manifest="manifest.json",
        manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
        required=False,
    )
    config = replace(TableSemanticConfig.for_tests(), inputs={"field_semantics": spec})
    summaries = _augment_field_support(
        [{"asset_id": "asset:1", "markers": {}, "root_source_families": []}], config
    )
    assert summaries[0]["semantic_assistance"]["availability"] == "NOT_EVALUABLE"
    assert "partially invalid" in summaries[0]["semantic_assistance"]["diagnostic"]


def test_wiki_total_budget_is_input_order_invariant_and_reports_coverage(tmp_path: Path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    tree = tmp_path / "tree.jsonl"
    tree.write_text(
        "\n".join(
            json.dumps({"pageId": str(index), "title": f"{name} usage"})
            for index, name in enumerate(("ALPHAX", "BETAY", "GAMMAZ"), start=1)
        )
        + "\n",
        encoding="utf-8",
    )
    spec = InputSpec(
        name="wiki_tree",
        path=tmp_path,
        manifest="manifest.json",
        manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
        tree="tree.jsonl",
        tree_sha256=hashlib.sha256(tree.read_bytes()).hexdigest(),
    )
    config = replace(
        TableSemanticConfig.for_tests(),
        inputs={"wiki_tree": spec},
        limits={"max_wiki_candidates_per_table": 1, "max_wiki_candidates_total": 2},
    )
    tables = [_object("ALPHAX"), _object("BETAY"), _object("GAMMAZ")]
    summaries = [{"asset_id": row["asset_id"], "markers": {}} for row in tables]

    first, first_diagnostics = _wiki_recall(tables, summaries, [], config)
    second, _ = _wiki_recall(list(reversed(tables)), list(reversed(summaries)), [], config)

    assert {(row["asset_id"], row["page_id"]) for row in first} == {
        (row["asset_id"], row["page_id"]) for row in second
    }
    coverage = next(row for row in first_diagnostics if row["code"] == "WIKI_RECALL_COVERAGE")
    assert coverage["eligible_tables"] == 3
    assert coverage["covered_tables"] == 2
    assert coverage["truncated_tables"] == 1


def test_business_group_requires_responsibilities_evidence_and_connected_relations():
    tables = [_object("A"), _object("B"), _object("C")]
    candidates = []
    evidence = []
    for name in ("A", "B", "C"):
        evidence_id = f"e-{name}"
        evidence.append(
            {
                "evidence_id": evidence_id,
                "source_kind": "TABLE_COMMENT",
                "source_locator": name,
                "root_source_family": f"physical-table:{name}",
            }
        )
        candidates.append(
            {
                "candidate_id": f"c-{name}",
                "asset_id": _asset(name),
                "candidate_value": f"{name}责任",
                "candidate_value_kind": "OBSERVED_EXPRESSION",
                "source_kind": "TABLE_COMMENT",
                "evidence_refs": [evidence_id],
                "rank": 1,
                "recommended_profile_eligible": False,
            }
        )
    config = replace(
        TableSemanticConfig.for_tests(),
        investigation_sets=(
            {"id": "abc", "kind": "BUSINESS_COLLABORATION", "tables": ["A", "B", "C"]},
        ),
    )
    disconnected = TableSemanticResult(
        responsibility_candidates=candidates,
        evidence_refs=evidence,
        table_relations=[
            {
                "relation_id": "ab",
                "subject_asset_id": _asset("A"),
                "object_asset_id": _asset("B"),
                "predicate": "RELATED_TO",
                "evidence_refs": ["e-A"],
                "outcome": "CANDIDATE",
            }
        ],
    )
    _build_collaboration_groups(disconnected, tables, config)
    assert not [row for row in disconnected.table_groups if row["group_kind"] == "BUSINESS_COLLABORATION_GROUP"]
    assert any(row["code"] == "COLLABORATION_GROUP_REJECTED" for row in disconnected.diagnostics)

    connected = TableSemanticResult(
        responsibility_candidates=candidates,
        evidence_refs=evidence,
        table_relations=disconnected.table_relations
        + [
            {
                "relation_id": "bc",
                "subject_asset_id": _asset("B"),
                "object_asset_id": _asset("C"),
                "predicate": "RELATED_TO",
                "evidence_refs": ["e-B"],
                "outcome": "CANDIDATE",
            }
        ],
    )
    _build_collaboration_groups(connected, tables, config)
    groups = [row for row in connected.table_groups if row["group_kind"] == "BUSINESS_COLLABORATION_GROUP"]
    assert len(groups) == 1


def test_unknown_or_counterevidenced_relation_cannot_connect_business_group():
    tables = [_object("A", "A职责"), _object("B", "B职责")]
    config = replace(
        TableSemanticConfig.for_tests(),
        investigation_sets=(
            {"id": "ab", "kind": "BUSINESS_COLLABORATION", "tables": ["A", "B"]},
        ),
    )
    result = TableSemanticResult(
        responsibility_candidates=[
            {
                "candidate_id": f"c-{name}",
                "asset_id": _asset(name),
                "candidate_value": f"{name}职责",
                "candidate_value_kind": "OBSERVED_EXPRESSION",
                "source_kind": "TABLE_COMMENT",
                "evidence_refs": [f"e-{name}"],
                "rank": 1,
            }
            for name in ("A", "B")
        ],
        evidence_refs=[
            {
                "evidence_id": evidence_id,
                "source_kind": "TABLE_COMMENT",
                "source_locator": evidence_id,
                "root_source_family": evidence_id,
            }
            for evidence_id in ("e-A", "e-B", "counter")
        ],
        table_relations=[
            {
                "relation_id": "ab-unknown",
                "subject_asset_id": _asset("A"),
                "object_asset_id": _asset("B"),
                "predicate": "RELATED_TO",
                "evidence_refs": ["e-A"],
                "counterevidence_refs": ["counter"],
                "outcome": "UNKNOWN",
            }
        ],
    )

    _build_collaboration_groups(result, tables, config)

    assert not [row for row in result.table_groups if row["group_kind"] == "BUSINESS_COLLABORATION_GROUP"]
    rejected = next(row for row in result.diagnostics if row["code"] == "COLLABORATION_GROUP_REJECTED")
    assert rejected["disconnected_asset_ids"]


def test_gate_rejects_relation_empty_collaboration_card():
    config = replace(
        TableSemanticConfig.for_tests(),
        expected_all_tables=1,
        investigation_sets=(
            {"id": "journey", "kind": "BUSINESS_COLLABORATION", "tables": ["A", "B"]},
        ),
    )
    result = TableSemanticResult(
        table_profiles=[
            {
                "asset_id": _asset("A"),
                "disposition": "SUBJECT",
                "candidate_summary": {"has_conflict": False, "has_unknown": True},
            }
        ],
        investigation_cards=[
            {"card_id": "journey", "kind": "BUSINESS_COLLABORATION", "status": "READY", "members": []}
        ],
        field_support_summaries=[
            {
                "asset_id": _asset("A"),
                "semantic_assistance": {"availability": "AVAILABLE", "voting_enabled": False},
                "field_assistance_status": "NOT_USED",
            }
        ],
    )

    gate = _evaluate_model_gate(result, config)

    check = next(row for row in gate["checks"] if row["check_id"] == "business-collaboration-connected")
    assert check["status"] == "FAIL"
    assert gate["status"] == "FAIL"


def test_field_gate_requires_assertion_links_in_each_collaboration_card():
    config = replace(
        TableSemanticConfig.for_tests(),
        expected_all_tables=2,
        investigation_sets=(
            {"id": "one", "kind": "BUSINESS_COLLABORATION", "tables": ["A"]},
            {"id": "two", "kind": "BUSINESS_COLLABORATION", "tables": ["B"]},
        ),
    )
    result = TableSemanticResult(
        table_profiles=[
            {"asset_id": _asset(name), "disposition": "SUBJECT", "candidate_summary": {"has_conflict": False}}
            for name in ("A", "B")
        ],
        investigation_cards=[
            {"card_id": "one", "kind": "BUSINESS_COLLABORATION", "status": "READY", "members": [{"asset_id": _asset("A")}]},
            {"card_id": "two", "kind": "BUSINESS_COLLABORATION", "status": "READY", "members": [{"asset_id": _asset("B")}]},
        ],
        field_support_summaries=[
            {"asset_id": _asset("A"), "semantic_assistance": {"voting_enabled": False}, "field_assistance_status": "USED", "assertion_links": [{"assertion_id": "a"}]},
            {"asset_id": _asset("B"), "semantic_assistance": {"voting_enabled": False}, "field_assistance_status": "NOT_USED", "assertion_links": []},
        ],
    )

    gate = _evaluate_model_gate(result, config)

    check = next(row for row in gate["checks"] if row["check_id"] == "field-assistance-linked-to-assertions")
    assert check["status"] == "FAIL"
    assert "two" in check["detail"]


def test_real_frozen_run_covers_all_tables_and_preserves_group_boundaries(tmp_path: Path):
    config = load_table_semantic_config("cases/tradeflow/table-semantic-map.yaml")
    result = run_table_semantic_map(config)

    assert result.stats["all_table_count"] == 477
    assert result.stats["subject_table_count"] == 233
    assert result.stats["variant_or_other_count"] == 244
    assert result.stats["legacy_structural_hint_count"] == 903
    assert len({row["asset_id"] for row in result.table_profiles}) == 477
    assert len(result.investigation_cards) == 5
    for card in result.investigation_cards:
        member_ids = {row["asset_id"] for row in card["members"]}
        assert all(
            {row["subject_asset_id"], row["object_asset_id"]}.issubset(member_ids)
            for row in card["relations"]
        )
        assert all(
            relation in card["relations"]
            for member in card["members"]
            for relation in member["relations"]
        )
        assert "unknown_member_asset_ids" in card
        assert "conflict_member_asset_ids" in card
        assert "unknown_relation_ids" in card
        assert card["semantic_review_status"] in {"UNRESOLVED", "CANDIDATE_READY"}
    assert result.quality_gate["status"] == "PASS"
    business_groups = [
        row
        for row in result.table_groups
        if row["group_kind"] == "BUSINESS_COLLABORATION_GROUP"
    ]
    assert [row["anchor_value"] for row in business_groups] == [
        "trs-collaboration",
        "option-collaboration",
    ]
    collaboration_check = next(
        row
        for row in result.quality_gate["checks"]
        if row["check_id"] == "business-collaboration-connected"
    )
    assert collaboration_check["status"] == "PASS"
    assert all(row["outcome"] != "ACCEPTED" for row in result.assertions)
    assert all(
        row["status"] == "INVESTIGATION_HINT"
        for row in result.table_groups
        if row["group_kind"] == "STRUCTURAL_NEIGHBORHOOD"
    )
    assert all(
        not row["semantic_assistance"]["voting_enabled"]
        for row in result.field_support_summaries
    )
    holding_relation = next(
        row
        for row in result.table_relations
        if row["subject_asset_id"].endswith(":POS_TRS_LEG_CURRENT_POS")
        and row["object_asset_id"].endswith(":POS_TRS_LEG_HIS_POS")
    )
    assert holding_relation["predicate"] == "CURRENT_HISTORY"
    option_event_relation = next(
        row
        for row in result.table_relations
        if row["subject_asset_id"].endswith(":TRD_OPTION_EVENT")
        and row["object_asset_id"].endswith(":REF_OTC_OPTION_DEAL")
    )
    assert option_event_relation["predicate"] == "EVENT_OF"
    assert option_event_relation["outcome"] == "CANDIDATE"
    assert result.quality_gate["status"] == "PASS"
    assert result.legacy_comparison["recommended_from_propagation_only"] == 0

    paths = write_table_semantic_results(tmp_path, result, config)
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    assert manifest["business_rows_read"] is False
    assert manifest["test_data_query_executed_by_build"] is False
    assert manifest["test_data_aggregate_evidence_used"] is True
    assert manifest["upstream_writes"] is False
    assert manifest["reader_delivery"] == "NOT_REVIEWED"
    assert any(
        row["relative_path"] == "review/index.html"
        for row in manifest["outputs"]
    )
    assert paths["table_profiles"].exists()
    assert (paths["table_profiles"].with_suffix(".parquet")).exists()


def test_pinned_wiki_body_mentions_do_not_turn_directory_path_into_category(tmp_path: Path):
    body = tmp_path / "page.md"
    body.write_text(
        "# 持仓同步方案\n核心关联表：POS_TRS_LEG_CURRENT_POS、POS_TRS_LEG_HIS_POS。\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256(body.read_bytes()).hexdigest()
    rows, diagnostics = extract_approved_wiki_body_evidence(
        [
            {
                "page_id": "100",
                "version": "7",
                "title": "持仓同步方案",
                "ancestor_path": ["生产事件管理", "2026", "持仓同步方案"],
                "path": body.as_posix(),
                "sha256": digest,
                "section": "核心关联表",
            }
        ],
        [
            _object("POS_TRS_LEG_CURRENT_POS"),
            _object("POS_TRS_LEG_HIS_POS"),
        ],
        max_reads=1,
    )

    assert not diagnostics
    assert len(rows) == 2
    assert all(row["evidence_kind"] == "MULTI_TABLE_ASSOCIATION" for row in rows)
    assert all(row["document_context_only"] is False for row in rows)
    assert all("生产事件管理" in row["ancestor_path"] for row in rows)
    assert all("category" not in row for row in rows)


def test_single_pinned_wiki_body_distinguishes_usage_description(tmp_path: Path):
    body = tmp_path / "usage.md"
    body.write_text("REF_TRS 用于记录收益互换合约主信息。\n", encoding="utf-8")
    rows, diagnostics = extract_approved_wiki_body_evidence(
        [
            {
                "page_id": "101",
                "version": "1",
                "path": body.as_posix(),
                "sha256": hashlib.sha256(body.read_bytes()).hexdigest(),
            }
        ],
        [_object("REF_TRS")],
        max_reads=1,
    )
    assert not diagnostics
    assert rows[0]["evidence_kind"] == "USAGE_DESCRIPTION"


def test_contract_validation_rejects_missing_evidence_reference():
    from titans_cognition.table_semantics import TableSemanticResult

    result = TableSemanticResult(
        assertions=[
            {
                "assertion_id": "a1",
                "subject_id": _asset("REF_TRS"),
                "predicate": "HAS_TABLE_RESPONSIBILITY_CANDIDATE",
                "evidence_refs": ["missing"],
                "counterevidence_refs": [],
                "outcome": "CANDIDATE",
            }
        ]
    )
    with pytest.raises(ValueError, match="missing evidence references"):
        validate_result_contracts(result)


def test_rejected_review_preserves_original_candidate_and_evidence():
    from titans_cognition.table_semantics import TableSemanticResult

    assertion = {
        "assertion_id": "a1",
        "subject_id": _asset("SHARED_TABLE"),
        "predicate": "HAS_TABLE_RESPONSIBILITY_CANDIDATE",
        "object_value": "CONFIGURATION",
        "method_id": "test",
        "method_version": "v1",
        "evidence_refs": ["e1"],
        "counterevidence_refs": [],
        "root_source_families": ["physical-table:shared"],
        "method_score": 1.0,
        "outcome": "CANDIDATE",
        "review_decision_ref": None,
    }
    result = TableSemanticResult(
        assertions=[assertion],
        evidence_refs=[
            {
                "evidence_id": "e1",
                "source_kind": "TABLE_NAME",
                "source_locator": "shared",
                "root_source_family": "physical-table:shared",
            }
        ],
    )
    apply_table_review_decisions(
        result,
        [{"assertion_id": "a1", "decision": "REJECT", "reason": "shared cross-product table"}],
    )
    assert result.assertions[0]["outcome"] == "CANDIDATE"
    assert result.assertions[0]["evidence_refs"] == ["e1"]
    assert result.review_decisions[0]["decision"] == "REJECT"


def test_cli_builds_independent_table_semantic_directory(tmp_path: Path, capsys):
    from titans_cognition.cli import main

    exit_code = main(
        [
            "build-table-semantic-map",
            "--config",
            "cases/tradeflow/table-semantic-map.yaml",
            "--output",
            str(tmp_path),
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["all_table_count"] == 477
    assert payload["model_gate"] == "PASS"
    root = tmp_path / "table-semantic-map"
    assert (root / "manifest.json").exists()
    assert (root / "review/index.html").exists()
    assert not (tmp_path / "context-enriched-field-semantic-map").exists()
