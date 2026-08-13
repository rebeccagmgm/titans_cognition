from pathlib import Path

import pytest

from titans_cognition.semantic_navigation import (
    bounded_wiki_context_candidates,
    build_concept_detail_projection,
    discover_open_attribute_shapes,
    load_navigation_config,
    project_business_area_entries,
    separate_concept_layers,
    map_observed_concepts_to_business_areas,
)


ROOT = Path(__file__).parents[1]
CONFIG = ROOT / "cases/tradeflow/reusable-semantic-navigation.yaml"


def test_skeleton_projects_areas_without_inventing_concepts():
    config = load_navigation_config(CONFIG)
    entries = project_business_area_entries(config)

    assert len(entries) == 10
    assert {entry["entry_kind"] for entry in entries} == {"BUSINESS_AREA"}
    assert all(entry.get("target_id") is None for entry in entries)


def test_concept_requires_explicit_area_and_evidence():
    config = load_navigation_config(CONFIG)
    entries = project_business_area_entries(
        config,
        [
            {
                "concept_id": "concept:notional",
                "label": "名义本金",
                "navigation_area": "valuation-collateral-cashflow",
                "evidence_refs": ["field:NOTIONAL"],
            },
            {
                "concept_id": "concept:unsupported",
                "label": "未经证实",
                "navigation_area": "valuation-collateral-cashflow",
                "evidence_refs": [],
            },
        ],
    )

    concept_entries = [entry for entry in entries if entry["entry_kind"] == "CONCEPT"]
    assert [entry["target_id"] for entry in concept_entries] == ["concept:notional"]


def test_invalid_config_cannot_enable_canonical_write_back(tmp_path):
    raw = CONFIG.read_text(encoding="utf-8").replace(
        "  canonical_write_back: false", "  canonical_write_back: true"
    )
    path = tmp_path / "bad.yaml"
    path.write_text(raw, encoding="utf-8")

    with pytest.raises(ValueError, match="cannot write canonical facts"):
        load_navigation_config(path)


def test_attribute_shapes_are_corpus_discovered_but_not_published():
    candidates = discover_open_attribute_shapes(
        ["Customer Name", "Trade Name", "Contract Name", "Customer ID"],
        min_support=2,
    )

    names = {candidate["observed_shape"] for candidate in candidates}
    assert "NAME" in names
    assert all(candidate["status"] == "OPEN_CANDIDATE" for candidate in candidates)
    assert all(candidate["publication_status"] == "NOT_PUBLISHED" for candidate in candidates)


def test_concept_detail_keeps_expression_attribute_and_qualifier_layers_separate():
    detail = separate_concept_layers(
        "concept:notional",
        {"expression_id": "expr:dynamic", "label": "动态名义本金"},
        [
            {
                "attribute_id": "attr:notional-amount",
                "concept_id": "concept:notional",
                "axis": "MEASURE",
            }
        ],
        [{"qualifier_id": "q:dynamic", "axis": "STATE", "value": "动态"}],
    )

    assert detail["concept"]["concept_id"] == "concept:notional"
    assert detail["attribute_expression"]["expression_id"] == "expr:dynamic"
    assert detail["field_attributes"][0]["axis"] == "MEASURE"
    assert detail["qualifiers"][0]["axis"] == "STATE"


def test_wiki_context_is_bounded_and_never_publishes_hierarchy():
    candidates, diagnostics = bounded_wiki_context_candidates(
        [{"concept_id": "concept:notional", "label": "名义本金"}],
        [
            {
                "page_id": "wiki:1",
                "title": "TRS动态名义本金验收指引",
                "ancestor_path": ["测试", "TRS"],
                "source_ref": "wiki:1",
            }
        ],
    )

    assert not diagnostics
    assert candidates[0]["role"] == "CONTEXT"
    assert candidates[0]["publication_status"] == "NOT_PUBLISHED"
    assert candidates[0]["ancestor_path"] == ["测试", "TRS"]
    assert "predicate" not in candidates[0]


def test_missing_wiki_is_explicitly_not_evaluable():
    candidates, diagnostics = bounded_wiki_context_candidates(
        [{"concept_id": "concept:notional", "label": "名义本金"}], None
    )

    assert candidates == []
    assert diagnostics == [{"code": "WIKI_NOT_EVALUABLE", "status": "NOT_EVALUABLE"}]


@pytest.mark.parametrize(
    "concept_id",
    ["concept:notional", "concept:counterparty", "concept:trade", "concept:position", "concept:margin"],
)
def test_concept_detail_projection_is_generic_across_representative_concepts(concept_id):
    projection = build_concept_detail_projection(
        {"concept_id": concept_id, "label": concept_id},
        expressions=[{"expression_id": f"expr:{concept_id}", "concept_id": concept_id}],
        field_attributes=[{"attribute_id": f"attr:{concept_id}", "concept_id": concept_id}],
        physical_implementations=[
            {"implementation_id": f"impl:{concept_id}", "concept_id": concept_id},
            {"implementation_id": f"impl:{concept_id}", "concept_id": concept_id},
        ],
        unresolved=[{"reason": "UNKNOWN_ATTRIBUTE", "label": "待确认"}],
    )

    assert len(projection["attribute_expressions"]) == 1
    assert len(projection["field_attributes"]) == 1
    assert len(projection["physical_implementations"]) == 1
    assert "UNKNOWN_ATTRIBUTE" in projection["unresolved"]


def test_observed_area_mapping_keeps_multi_match_and_unknown_open():
    config = load_navigation_config(CONFIG)
    rows = map_observed_concepts_to_business_areas(
        config,
        [
            {"business_concept_id": "c1", "label": "Dynamic Notional", "source_concept_ids": ["s1"]},
            {"business_concept_id": "c2", "label": "Trade Position", "source_concept_ids": ["s2"]},
            {"business_concept_id": "c3", "label": "UnseenThing", "source_concept_ids": ["s3"]},
        ],
    )

    by_id = {row["concept_id"]: row for row in rows}
    assert by_id["c1"]["status"] == "CANDIDATE"
    assert by_id["c2"]["status"] == "CONFLICT"
    assert by_id["c3"]["reason"] == "UNKNOWN_BUSINESS_CONCEPT"


def test_area_terms_are_configuration_scoped_not_global_rules():
    config = load_navigation_config(CONFIG)
    config["business_area_terms"] = {"participants": ["counterparty"]}

    rows = map_observed_concepts_to_business_areas(
        config,
        [{"business_concept_id": "c1", "label": "Notional", "source_concept_ids": ["s1"]}],
    )

    assert rows[0]["status"] == "UNKNOWN"
    assert rows[0]["candidate_area_ids"] == []
