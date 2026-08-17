import hashlib
import json
from pathlib import Path

import pytest
import yaml

from titans_cognition.field_evidence import (
    BLOCK_NAMES,
    CURRENCY_BASIS_VALUES,
    build_evidence_pack,
    load_field_evidence_config,
    run_field_evidence,
    validate_evidence_pack,
)


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "cases" / "tradeflow" / "field-evidence-preparation.yaml"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_fixture(tmp_path: Path) -> Path:
    facts = tmp_path / "facts"
    facts.mkdir()
    objects = [
        {
            "asset_id": "testdb:TITANS_TRADEFLOW:TABLE:TRD_CLN_TRADE_DEAL",
            "schema_name": "TITANS_TRADEFLOW",
            "object_name": "TRD_CLN_TRADE_DEAL",
            "object_type": "TABLE",
            "object_comment": " CLN 认购流水",
            "in_panorama_scope": True,
            "is_boundary": False,
        },
        {
            "asset_id": "testdb:TITANS_TRADEFLOW:TABLE:TRANS_HKFT_ORIGINAL_DEAL",
            "schema_name": "TITANS_TRADEFLOW",
            "object_name": "TRANS_HKFT_ORIGINAL_DEAL",
            "object_type": "TABLE",
            "object_comment": "HKFT原始意向成交流水表",
            "in_panorama_scope": True,
            "is_boundary": False,
        },
        {
            "asset_id": "testdb:TITANS_TRADEFLOW:TABLE:REF_FAST_TRS",
            "schema_name": "TITANS_TRADEFLOW",
            "object_name": "REF_FAST_TRS",
            "object_type": "TABLE",
            "object_comment": "极速互换合约要素表",
            "in_panorama_scope": True,
            "is_boundary": False,
        },
        {
            "asset_id": "testdb:TITANS_TRADEFLOW:TABLE:REF_LS_TRS",
            "schema_name": "TITANS_TRADEFLOW",
            "object_name": "REF_LS_TRS",
            "object_type": "TABLE",
            "object_comment": "多空互换合约表",
            "in_panorama_scope": True,
            "is_boundary": False,
        },
        {
            "asset_id": "testdb:TITANS_TRADEFLOW:TABLE:ADM_UPDATE_AUDIT_LOG",
            "schema_name": "TITANS_TRADEFLOW",
            "object_name": "ADM_UPDATE_AUDIT_LOG",
            "object_type": "TABLE",
            "object_comment": "运营-TRS更新日志 ",
            "in_panorama_scope": True,
            "is_boundary": False,
        },
        {
            "asset_id": "testdb:TITANS_TRADEFLOW:TABLE:CURRENT_POS_202300213",
            "schema_name": "TITANS_TRADEFLOW",
            "object_name": "CURRENT_POS_202300213",
            "object_type": "TABLE",
            "object_comment": None,
            "in_panorama_scope": True,
            "is_boundary": False,
        },
    ]
    rows = [
        (objects[0], "CTPTY_SHORT_NAME", "客户短名", "VARCHAR2"),
        (objects[1], "SOURCE_TYPE", "委托类别(客户委托、强制召回)", "VARCHAR2"),
        (
            objects[2],
            "SHORT_DYNAMIC_NOTIONAL",
            "空头动态名义本金（结算币种）",
            "NUMBER",
        ),
        (
            objects[3],
            "SHORT_DYNAMIC_NOTIONAL_ORG",
            "多头动态名义本金（结算币种）",
            "NUMBER",
        ),
        (objects[4], "CREATED_BY", "创建人", "VARCHAR2"),
        (objects[5], "CURRENCY", None, "VARCHAR2"),
    ]
    columns = []
    for position, (object_row, name, comment, data_type) in enumerate(rows, 1):
        columns.append(
            {
                "asset_id": object_row["asset_id"],
                "column_id": f"{object_row['asset_id']}:COLUMN:{name}",
                "column_name": name,
                "column_comment": comment,
                "data_type": data_type,
                "nullable_declared": position % 2 == 0,
                "ordinal_position": 1,
            }
        )
    columns_path = facts / "columns.json"
    objects_path = facts / "objects.json"
    columns_path.write_text(
        json.dumps(columns, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    objects_path.write_text(
        json.dumps(objects, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    base = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    base["scope"]["expected_object_count"] = 6
    base["scope"]["expected_physical_column_count"] = 6
    base["scope"]["expected_prepared_count"] = 5
    base["scope"]["expected_excluded_count"] = 1
    base["source_artifacts"]["columns"]["path"] = columns_path.as_posix()
    base["source_artifacts"]["columns"]["sha256"] = _sha256(columns_path)
    base["source_artifacts"]["objects"]["path"] = objects_path.as_posix()
    base["source_artifacts"]["objects"]["sha256"] = _sha256(objects_path)
    base["contract"]["path"] = (
        ROOT
        / "openspec"
        / "changes"
        / "establish-reusable-semantic-navigation"
        / "research"
        / "06-field-evidence-preparation-contract.yaml"
    ).as_posix()
    base["schema"]["path"] = (
        ROOT / "schemas" / "field-evidence-pack.schema.json"
    ).as_posix()
    profile = tmp_path / "profile.yaml"
    profile.write_text(
        yaml.safe_dump(base, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return profile


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_profile_freezes_full_tradeflow_population_and_complete_registries():
    config = load_field_evidence_config(PROFILE)
    assert config.expected_object_count == 477
    assert config.expected_physical_column_count == 13_611
    assert config.expected_prepared_count == 5_512
    assert config.expected_excluded_count == 8_099
    assert len(config.rule_registry) == 77
    assert len({item.rule_id for item in config.rule_registry}) == 77
    assert BLOCK_NAMES == (
        "physical_identity",
        "raw_physical_fact",
        "preparation_disposition",
        "normalized_lexical_form",
        "tokens",
        "protected_phrases",
        "abbreviation_observations",
        "generic_attribute_observations",
        "technical_observations",
        "contextual_evidence",
        "candidate_qualifier_observations",
        "conflicts",
        "unresolved_items",
        "applied_rule_ids",
        "provenance",
        "evidence_status",
    )
    assert CURRENCY_BASIS_VALUES == (
        "ORIGINAL_CURRENCY",
        "LOCAL_CURRENCY",
        "UNDERLYING_CURRENCY",
        "SETTLEMENT_CURRENCY",
    )


def test_pack_preserves_raw_characters_and_blocks_naked_short_and_source(tmp_path):
    config = load_field_evidence_config(_write_fixture(tmp_path))
    source = json.loads(config.columns_path.read_text(encoding="utf-8"))[0]
    object_row = json.loads(config.objects_path.read_text(encoding="utf-8"))[0]

    pack = build_evidence_pack(source, object_row, config)

    assert tuple(pack) == BLOCK_NAMES
    assert pack["raw_physical_fact"]["object_comment_raw"] == " CLN 认购流水"
    assert pack["raw_physical_fact"]["column_comment_raw"] == "客户短名"
    assert [token["normalized_text"] for token in pack["tokens"]] == [
        "CTPTY",
        "SHORT_NAME",
    ]
    assert [item["phrase"] for item in pack["protected_phrases"]] == ["SHORT_NAME"]
    assert not any(
        item["dimension"] == "position_side"
        for item in pack["candidate_qualifier_observations"]
    )
    assert pack["provenance"]["source_artifacts"][0]["locator"].startswith(
        "physical_column_id="
    )
    assert {
        item["evidence_role"] for item in pack["provenance"]["source_artifacts"]
    } == {"COLUMN_PHYSICAL_FACT", "OBJECT_PHYSICAL_FACT"}
    validate_evidence_pack(pack, config)


def test_validator_rejects_missing_or_tampered_item_provenance(tmp_path):
    config = load_field_evidence_config(_write_fixture(tmp_path))
    source = json.loads(config.columns_path.read_text(encoding="utf-8"))[0]
    object_row = json.loads(config.objects_path.read_text(encoding="utf-8"))[0]
    pack = build_evidence_pack(source, object_row, config)

    missing_span = json.loads(json.dumps(pack, ensure_ascii=False))
    del missing_span["tokens"][0]["source_span"]
    with pytest.raises(ValueError, match="has no source span"):
        validate_evidence_pack(missing_span, config)

    tampered_raw = json.loads(json.dumps(pack, ensure_ascii=False))
    tampered_raw["normalized_lexical_form"][0]["raw_value"] = "TAMPERED"
    with pytest.raises(ValueError, match="does not match its source span"):
        validate_evidence_pack(tampered_raw, config)

    tampered_ref = json.loads(json.dumps(pack, ensure_ascii=False))
    tampered_ref["tokens"][0]["source_ref"] = "column_name:another-field"
    with pytest.raises(ValueError, match="source ref does not identify its source"):
        validate_evidence_pack(tampered_ref, config)

    empty_generic_span = json.loads(json.dumps(pack, ensure_ascii=False))
    empty_generic_span["generic_attribute_observations"][0]["source_span"] = [0, 0]
    with pytest.raises(ValueError, match="empty source span"):
        validate_evidence_pack(empty_generic_span, config)

    wrong_generic_rule = json.loads(json.dumps(pack, ensure_ascii=False))
    wrong_generic_rule["generic_attribute_observations"][0]["rule_id"] = "GEN-ID-001"
    with pytest.raises(ValueError, match="deterministic replay"):
        validate_evidence_pack(wrong_generic_rule, config)

    tampered_provenance = json.loads(json.dumps(pack, ensure_ascii=False))
    tampered_provenance["provenance"]["source_artifacts"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="does not match the frozen sources"):
        validate_evidence_pack(tampered_provenance, config)

    tampered_locator = json.loads(json.dumps(pack, ensure_ascii=False))
    tampered_locator["provenance"]["source_artifacts"][1]["locator"] = (
        "asset_id=another-object"
    )
    with pytest.raises(ValueError, match="does not match the frozen sources"):
        validate_evidence_pack(tampered_locator, config)

    injected_manifest = json.loads(json.dumps(pack, ensure_ascii=False))
    injected_manifest["provenance"]["injected_source_manifest_id"] = "forged"
    with pytest.raises(ValueError, match="does not match the frozen sources"):
        validate_evidence_pack(injected_manifest, config)


def test_unrecognized_abbreviation_emits_reviewable_conflict(tmp_path):
    config = load_field_evidence_config(_write_fixture(tmp_path))
    source = json.loads(config.columns_path.read_text(encoding="utf-8"))[0]
    object_row = json.loads(config.objects_path.read_text(encoding="utf-8"))[0]
    source["column_name"] = "XYZ_NAME"
    source["column_comment"] = None
    source["column_id"] = f"{source['asset_id']}:COLUMN:{source['column_name']}"

    pack = build_evidence_pack(source, object_row, config)

    assert {item["conflict_type"] for item in pack["conflicts"]} == {
        "MISSING_INFORMATION",
        "UNRECOGNIZED_ABBREVIATION",
    }
    conflict = next(
        item
        for item in pack["conflicts"]
        if item["conflict_type"] == "UNRECOGNIZED_ABBREVIATION"
    )
    assert conflict["rule_ids"] == ["GEN-CONFLICT-008", "GEN-CONFLICT-009"]
    assert len(conflict["source_spans"]) == 1
    assert conflict["evidence_b"] == (
        f"rule_registry:{config.contract_sha256}:GEN-ABBR-003:NO_MATCH"
    )
    assert {"GEN-CONFLICT-008", "GEN-CONFLICT-009"}.issubset(
        pack["applied_rule_ids"]["values"]
    )
    validate_evidence_pack(pack, config)


def test_run_emits_one_pack_per_field_closed_dispositions_and_stable_hash(tmp_path):
    profile = _write_fixture(tmp_path)
    first = tmp_path / "run-a"
    second = tmp_path / "run-b"

    first_manifest = run_field_evidence(profile, first)
    second_manifest = run_field_evidence(profile, second)

    assert first_manifest == second_manifest
    assert first_manifest["counts"] == {
        "physical_objects": 6,
        "physical_columns": 6,
        "evidence_packs": 6,
        "unique_physical_column_ids": 6,
        "missing_physical_column_ids": 0,
        "duplicate_physical_column_ids": 0,
        "PREPARED": 5,
        "EXCLUDED": 1,
        "DEFERRED": 0,
    }
    assert first_manifest["controls"] == {
        "model_calls": 0,
        "business_rows_read": False,
        "external_egress": False,
        "database_writes": 0,
        "suite_a_formal_status": "NOT_CLAIMED",
    }
    rule_registry = first_manifest["rule_registry"]
    assert rule_registry["coverage_status"] == "OBSERVED_APPLIED_RULES_ONLY"
    assert rule_registry["observed_applied_count"] == len(
        rule_registry["observed_applied_ids"]
    )
    assert set(rule_registry["observed_applied_ids"]).isdisjoint(
        rule_registry["unobserved_ids"]
    )
    assert set(rule_registry["observed_applied_ids"]) | set(
        rule_registry["unobserved_ids"]
    ) == set(rule_registry["ids"])
    assert first_manifest["field_evidence_packs_sha256"] == _sha256(
        first / "field-evidence-packs.jsonl"
    )
    assert first_manifest["field_evidence_packs_sha256"] == _sha256(
        second / "field-evidence-packs.jsonl"
    )

    packs = _jsonl(first / "field-evidence-packs.jsonl")
    by_name = {pack["raw_physical_fact"]["column_name_raw"]: pack for pack in packs}
    assert by_name["CURRENCY"]["preparation_disposition"]["status"] == "EXCLUDED"
    assert any(
        item["value"] == "SETTLEMENT_CURRENCY"
        for item in by_name["SHORT_DYNAMIC_NOTIONAL"][
            "candidate_qualifier_observations"
        ]
    )
    assert not any(
        item["dimension"] == "cashflow_direction"
        for item in by_name["SOURCE_TYPE"]["candidate_qualifier_observations"]
    )
    assert (
        by_name["CREATED_BY"]["technical_observations"][0]["technical_class"]
        == "AUDIT_ACTOR"
    )
    assert (
        by_name["SHORT_DYNAMIC_NOTIONAL_ORG"]["conflicts"][0]["conflict_type"]
        == "NAME_COMMENT_CONFLICT"
    )


def test_failed_run_does_not_publish_partial_output(tmp_path):
    profile = _write_fixture(tmp_path)
    payload = yaml.safe_load(profile.read_text(encoding="utf-8"))
    payload["scope"]["expected_prepared_count"] = 4
    payload["scope"]["expected_excluded_count"] = 2
    profile.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    destination = tmp_path / "failed-run"

    with pytest.raises(ValueError, match="preparation disposition drift"):
        run_field_evidence(profile, destination)

    assert not destination.exists()
    assert not list(tmp_path.glob(".failed-run-*.staging"))


def test_schema_declares_all_blocks_and_currency_values():
    schema = json.loads(
        (ROOT / "schemas" / "field-evidence-pack.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert schema["required"] == list(BLOCK_NAMES)
    qualifier = schema["properties"]["candidate_qualifier_observations"]["items"]
    currency_branch = next(
        branch
        for branch in qualifier["allOf"]
        if branch["if"]["properties"]["dimension"]["const"] == "currency_basis"
    )
    assert currency_branch["then"]["properties"]["value"]["enum"] == list(
        CURRENCY_BASIS_VALUES
    )


def test_frozen_23_gold_anchors_match_p1_without_claiming_suite_a():
    config = load_field_evidence_config(PROFILE)
    if not config.columns_path.exists() or not config.objects_path.exists():
        pytest.skip("local frozen Stage 0 artifacts are not present")
    objects = {
        row["asset_id"]: row
        for row in json.loads(config.objects_path.read_text(encoding="utf-8"))
        if row.get("schema_name") == "TITANS_TRADEFLOW"
    }
    columns = {
        row["column_id"]: row
        for row in json.loads(config.columns_path.read_text(encoding="utf-8"))
        if row.get("asset_id") in objects
    }
    gold = yaml.safe_load(config.gold_set_path.read_text(encoding="utf-8"))
    assert gold["metadata"]["case_count"] == 23
    assert gold["metadata"]["rule_execution_status"] == "RULE_EXECUTION_NOT_PERFORMED"

    packs = {}
    for case in gold["cases"]:
        _, object_name, column_name = case["physical_field"].split(".", 2)
        physical_column_id = (
            f"testdb:TITANS_TRADEFLOW:TABLE:{object_name}:COLUMN:{column_name}"
        )
        column = columns[physical_column_id]
        pack = build_evidence_pack(column, objects[column["asset_id"]], config)
        packs[case["case_id"]] = pack
        assert (
            pack["raw_physical_fact"]["object_comment_raw"]
            == case["object_comment_raw"]
        )
        assert (
            pack["raw_physical_fact"]["column_comment_raw"]
            == case["column_comment_raw"]
        )
        assert [row["normalized_text"] for row in pack["tokens"]] == case[
            "expected_tokens"
        ]
        assert [row["phrase"] for row in pack["protected_phrases"]] == case[
            "expected_protected_phrases"
        ]
        assert [
            row["attribute"] for row in pack["generic_attribute_observations"]
        ] == case["expected_generic_attributes"]
        technical = pack["technical_observations"]
        technical_class = (
            technical[0]["technical_class"] if technical else "NOT_APPLICABLE"
        )
        assert technical_class == case["expected_technical_class"]
        if "expected_technical_status" in case:
            assert technical[0]["status"] == case["expected_technical_status"]
        actual_conflicts = [row["conflict_type"] for row in pack["conflicts"]]
        assert [
            conflict
            for conflict in actual_conflicts
            if conflict != "UNRECOGNIZED_ABBREVIATION"
        ] == [
            conflict
            for conflict in case["expected_conflicts"]
            if conflict != "UNRECOGNIZED_ABBREVIATION"
        ]
        assert actual_conflicts.count("UNRECOGNIZED_ABBREVIATION") == sum(
            row["status"] == "UNRECOGNIZED_ABBREVIATION"
            for row in pack["abbreviation_observations"]
        )
        assert any(
            row["code"] == "SEMANTIC_LAYER_REQUIRED" for row in pack["unresolved_items"]
        )
        for forbidden in case["forbidden_semantic_inferences"]:
            if forbidden.startswith("position_side="):
                value = forbidden.split("=", 1)[1]
                assert not any(
                    row["dimension"] == "position_side"
                    and row["value"] == value
                    and row["status"] == "CANDIDATE"
                    for row in pack["candidate_qualifier_observations"]
                )
            if forbidden.startswith("flow_side="):
                assert not any(
                    row["dimension"] == "flow_side"
                    for row in pack["candidate_qualifier_observations"]
                )

    assert (
        packs["FEP-001"]["physical_identity"]["physical_column_id"]
        != packs["FEP-023"]["physical_identity"]["physical_column_id"]
    )
