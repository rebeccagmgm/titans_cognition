import json
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]


def test_navigation_fixture_has_separate_layers_and_is_schema_valid():
    schema = json.loads(
        (ROOT / "schemas/reusable-semantic-navigation.schema.json").read_text(
            encoding="utf-8"
        )
    )
    fixture = json.loads(
        (ROOT / "tests/fixtures/reusable_semantic_navigation.json").read_text(
            encoding="utf-8"
        )
    )

    assert schema["$id"] == "reusable-semantic-navigation.schema.json"
    assert set(schema["required"]) <= set(fixture)
    for section in schema["required"]:
        assert isinstance(fixture[section], (str, list))
    assert fixture["published_entries"] == []
    assert fixture["attribute_expressions"][0]["concept_id"] == "concept:notional"
    assert fixture["field_attributes"][0]["concept_id"] == "concept:counterparty"
    assert fixture["qualifiers"][0]["axis"] == "STATE"


def test_tradeflow_navigation_config_is_open_and_read_only():
    config = yaml.safe_load(
        (ROOT / "cases/tradeflow/reusable-semantic-navigation.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert config["schema_version"] == "reusable-semantic-navigation-v1"
    assert len(config["business_areas"]) == 10
    assert {axis["id"] for axis in config["attribute_axes"]} >= {
        "IDENTIFIER",
        "ROLE",
        "STATE",
        "MEASURE",
        "TIME",
    }
    assert config["extension_policy"]["wiki_only_hierarchy"] == "NOT_PUBLISHED"
    assert config["publication"]["canonical_write_back"] is False
    assert config["publication"]["business_rows_read"] is False


def test_fixture_keeps_wiki_counterevidence_separate_from_field_support():
    fixture = json.loads(
        (ROOT / "tests/fixtures/reusable_semantic_navigation.json").read_text(
            encoding="utf-8"
        )
    )
    evidence = {row["evidence_id"]: row for row in fixture["evidence"]}

    assert evidence["ev:field"]["role"] == "SUPPORT"
    assert evidence["ev:wiki-conflict"]["role"] == "COUNTEREVIDENCE"
    assert fixture["review_decisions"][0]["disposition"] == "REWORK"
