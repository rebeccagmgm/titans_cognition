import json

import pytest

from titans_cognition.cli import main
from titans_cognition.extract import PhysicalFacts
from titans_cognition.field_concepts import (
    FieldConceptResult,
    load_field_concept_config,
    run_field_concepts,
    write_field_concept_results,
)
from titans_cognition.io import write_json_facts
from titans_cognition.render import _slug


def _facts() -> PhysicalFacts:
    objects = []
    columns = []
    rows = [
        (
            "REF_TRS",
            "互换合约要素",
            [
                ("NOTIONAL", "名义本金(本币)", "NUMBER"),
                ("INITIAL_NOTIONAL", "初始名义本金", "NUMBER"),
                ("NOTIONAL_STATUS", "名义本金审核状态", "VARCHAR2"),
                ("CURRENT_PRINCIPAL", "当前名义本金", "VARCHAR2"),
                ("NO_COMMENT_AMOUNT", None, "NUMBER"),
            ],
        ),
        (
            "REF_OPTION",
            "期权合约要素",
            [
                ("NOTIONAL", "当前名义本金", "NUMBER"),
                ("DYNAMIC_NOTIONAL", "动态名义本金", "NUMBER"),
                ("COLLATERAL", "保证金", "NUMBER"),
                ("BUSINESS_NO", "业务编号", "VARCHAR2"),
            ],
        ),
        (
            "REF_OPTION_20260101",
            "期权合约要素备份",
            [("NOTIONAL", "名义本金", "NUMBER")],
        ),
    ]
    for object_name, object_comment, field_rows in rows:
        asset_id = f"testdb:ALPHA:TABLE:{object_name}"
        objects.append(
            {
                "run_id": "run-001",
                "asset_id": asset_id,
                "schema_name": "ALPHA",
                "object_name": object_name,
                "object_type": "TABLE",
                "object_comment": object_comment,
                "in_panorama_scope": True,
                "is_boundary": False,
                "extraction_status": "SUCCESS",
            }
        )
        for position, (name, comment, data_type) in enumerate(field_rows, 1):
            columns.append(
                {
                    "asset_id": asset_id,
                    "column_id": f"{asset_id}:COLUMN:{name}",
                    "column_name": name,
                    "column_comment": comment,
                    "data_type": data_type,
                    "ordinal_position": position,
                }
            )
    return PhysicalFacts(objects=objects, columns=columns)


def _config(tmp_path):
    path = tmp_path / "field-concepts.yaml"
    path.write_text(
        """
version: v1
scope:
  schemas: [ALPHA]
  object_types: [TABLE]
  exclude_numeric_suffix: true
  expected_object_count: 2
  expected_excluded_count: 1
limits:
  top_k: 5
  max_candidates_per_field: 100
  max_candidate_pairs: 1000
  max_feature_frequency: 50
similarity:
  min_similarity: 0.15
  base_cluster_threshold: 0.35
  qualified_cluster_threshold: 0.60
  weights: {name: 1.0, comment: 1.4, context: 0.1, type: 0.1}
abbreviations: {INIT: INITIAL, AMT: AMOUNT}
broad_categories:
  日期时间: {terms: [DATE, TIME, 日期, 时间], type_families: [DATE_TIME]}
  状态: {terms: [STATUS, STATE, 状态]}
  标识符: {terms: [ID, NUMBER, NO, 编号, 标识]}
  金额: {terms: [AMOUNT, NOTIONAL, PRINCIPAL, 金额, 本金, 保证金], type_families: [NUMBER]}
  文本: {terms: [DESC, 说明]}
base_concepts:
  名义本金: {terms: [NOTIONAL, 名义本金, 名本], broad_category: 金额}
  保证金: {terms: [COLLATERAL, 保证金], broad_category: 金额}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return load_field_concept_config(path)


def test_scope_is_config_driven_and_numeric_suffix_is_only_run_exclusion(tmp_path):
    result = run_field_concepts(_facts(), _config(tmp_path))

    assert result.stats["object_count"] == 2
    assert result.stats["excluded_object_count"] == 1
    assert result.stats["field_count"] == 9
    assert all("REF_OPTION_20260101" not in row["field_id"] for row in result.links)


def test_scope_drift_stops_the_run(tmp_path):
    config = _config(tmp_path)
    config = config.with_expected_object_count(3)

    with pytest.raises(ValueError, match="expected 3 objects, got 2"):
        run_field_concepts(_facts(), config)


def test_missing_comment_and_same_name_different_comment_remain_usable(tmp_path):
    result = run_field_concepts(_facts(), _config(tmp_path))
    by_field = {row["field_id"]: row for row in result.field_profiles}

    missing = next(row for key, row in by_field.items() if key.endswith("NO_COMMENT_AMOUNT"))
    assert missing["comment_available"] is False
    assert missing["status"] == "SUCCESS"

    notional_links = [
        row
        for row in result.links
        if row["field_id"].endswith(":NOTIONAL") and row["rank"] == 1
    ]
    assert len(notional_links) == 2
    assert len({row["concept_id"] for row in notional_links}) == 2

    current_links = [
        row
        for row in result.links
        if row["rank"] == 1
        and (
            row["field_id"].endswith(":CURRENT_PRINCIPAL")
            or row["field_id"].endswith(":NOTIONAL")
            and row["field_comment"] == "当前名义本金"
        )
    ]
    assert len(current_links) == 2
    assert len({row["concept_id"] for row in current_links}) == 1


def test_notional_principal_has_three_level_paths_and_status_is_separate(tmp_path):
    result = run_field_concepts(_facts(), _config(tmp_path))
    concepts = {row["concept_id"]: row for row in result.concepts}
    labels = {row["label"]: row for row in result.concepts}

    assert labels["名义本金"]["parent_id"] == labels["金额"]["concept_id"]
    assert labels["初始名义本金"]["parent_id"] == labels["名义本金"]["concept_id"]
    assert labels["当前名义本金"]["parent_id"] == labels["名义本金"]["concept_id"]
    status_links = [
        row for row in result.links if row["field_id"].endswith("NOTIONAL_STATUS")
    ]
    assert not status_links or all(
        concepts[row["concept_id"]]["label"] != "名义本金"
        for row in status_links
    )
    assert result.stats["unassigned_field_count"] > 0


def test_writer_emits_only_minimal_contract_and_replayable_manifest(tmp_path):
    result = run_field_concepts(_facts(), _config(tmp_path))
    panorama_root = tmp_path / "source" / "panorama"
    object_root = panorama_root / "objects"
    object_root.mkdir(parents=True)
    linked_asset_id = str(result.links[0]["asset_id"])
    object_page = object_root / f"{_slug(linked_asset_id)}.html"
    object_page.write_text("<html><body>object card</body></html>", encoding="utf-8")
    first = write_field_concept_results(
        tmp_path / "first",
        result,
        source_panorama_root=panorama_root,
    )
    second = write_field_concept_results(
        tmp_path / "second",
        result,
        source_panorama_root=panorama_root,
    )

    assert {path.name for key, path in first.items() if key != "review_index"} == {
        "concepts.jsonl",
        "field_concept_links.jsonl",
        "manifest.json",
    }
    first_manifest = json.loads(first["manifest"].read_text(encoding="utf-8"))
    second_manifest = json.loads(second["manifest"].read_text(encoding="utf-8"))
    assert first_manifest["outputs"] == second_manifest["outputs"]
    assert {
        "concept_id",
        "label",
        "level",
        "parent_id",
        "method_id",
        "member_count",
    }.issubset(result.concepts[0])
    assert {
        "field_id",
        "asset_id",
        "concept_id",
        "method_id",
        "method_score",
        "status",
        "rank",
    }.issubset(result.links[0])
    review_html = first["review_index"].read_text(encoding="utf-8")
    assert "名义本金" in review_html
    assert "字段反查概念路径" in review_html
    assert "new Worker" in review_html
    assert "FIELD_PAGE_SIZE=50" in review_html
    assert object_page.resolve().as_uri() in review_html
    assert "全部后代字段" in review_html

    write_field_concept_results(tmp_path / "first", result, write_diagnostics=True)
    assert (tmp_path / "first" / "field-concepts" / "diagnostics.jsonl").exists()
    write_field_concept_results(tmp_path / "first", result)
    assert not (tmp_path / "first" / "field-concepts" / "diagnostics.jsonl").exists()


def test_cli_discovers_field_concepts(tmp_path, capsys):
    facts_dir = tmp_path / "facts"
    write_json_facts(facts_dir, _facts())
    config_path = tmp_path / "field-concepts.yaml"
    source = _config(tmp_path)
    config_path.write_text(source.source_text, encoding="utf-8")

    assert (
        main(
            [
                "discover-field-concepts",
                "--facts-dir",
                str(facts_dir),
                "--config",
                str(config_path),
                "--output",
                str(tmp_path / "result"),
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["object_count"] == 2
    assert output["field_count"] == 9
    assert (tmp_path / "result" / "field-concepts" / "concepts.jsonl").exists()


def test_large_review_page_keeps_initial_dom_bounded(tmp_path):
    concepts = [
        {
            "concept_id": f"concept-{index}",
            "label": f"概念 {index}",
            "level": 1 if index < 10 else 2,
            "parent_id": None if index < 10 else f"concept-{index % 10}",
            "status": "CANDIDATE",
            "method_id": "test",
            "method_version": "v1",
            "member_count": 1,
        }
        for index in range(1_200)
    ]
    links = [
        {
            "field_id": f"field-{index}",
            "asset_id": f"asset-{index // 20}",
            "object_name": f"TABLE_{index // 20}",
            "field_name": f"FIELD_{index}",
            "field_comment": f"字段 {index}",
            "concept_id": f"concept-{index % 1_200}",
            "method_id": "test",
            "method_score": 0.8,
            "status": "CANDIDATE",
            "rank": 1,
        }
        for index in range(5_000)
    ]
    result = FieldConceptResult(
        run_id="large-run",
        config_hash="config-hash",
        concepts=concepts,
        links=links,
        stats={
            "object_count": 250,
            "field_count": 5_000,
            "concept_count": 1_200,
            "unassigned_field_count": 0,
            "candidate_pair_count": 25_000,
        },
    )

    paths = write_field_concept_results(tmp_path, result)
    review_html = paths["review_index"].read_text(encoding="utf-8")

    assert review_html.count("<details") == 0
    assert review_html.count("class='field-row'") == 0
    assert "new Worker" in review_html
    assert "FIELD_PAGE_SIZE" in review_html
