import json

from titans_cognition.derive import derive_observations
from titans_cognition.extract import PhysicalFacts
from titans_cognition.render import render_panorama
from titans_cognition.scope import ScopeConfig


def test_render_panorama_creates_navigable_physical_projection(tmp_path):
    scope = ScopeConfig(
        scope_id="panorama",
        source_label="testdb",
        schemas=("TITANS_DM",),
        object_types=("TABLE",),
        excluded_schema_suffixes=(),
        excluded_schemas=(),
    )
    facts = PhysicalFacts(
        objects=[
            {
                "run_id": "run-001",
                "asset_id": "testdb:TITANS_DM:TABLE:T_EVENT",
                "source_label": "testdb",
                "schema_name": "TITANS_DM",
                "object_name": "T_EVENT",
                "object_type": "TABLE",
                "object_comment": "<physical comment>",
                "in_panorama_scope": True,
                "is_boundary": False,
                "boundary_for_case_ids": [],
                "extraction_status": "SUCCESS",
            }
        ],
        columns=[
            {
                "asset_id": "testdb:TITANS_DM:TABLE:T_EVENT",
                "column_name": "ID",
                "data_type": "NUMBER",
                "ordinal_position": 1,
                "column_comment": "identifier",
            }
        ],
        object_definitions=[
            {
                "asset_id": "testdb:TITANS_DM:TABLE:T_EVENT",
                "definition_type": "DDL",
                "definition_text": "CREATE TABLE T_EVENT (ID NUMBER);",
                "extraction_status": "SUCCESS",
                "error_category": None,
            }
        ],
    )

    paths = render_panorama(
        scope,
        facts,
        derive_observations(facts),
        tmp_path / "run-001",
        scope_config_sha256="scope-hash",
        code_version="test-commit",
    )

    index = paths["index"].read_text(encoding="utf-8")
    object_card = paths["object_cards"][0].read_text(encoding="utf-8")
    assert "TITANS Panorama" in index
    assert "TITANS_DM" in index
    assert "T_EVENT" in object_card
    assert "&lt;physical comment&gt;" in object_card
    assert "CREATE TABLE T_EVENT" not in object_card
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    assert manifest["code_version"] == "test-commit"
    assert manifest["outputs"]
    assert manifest["known_gaps"]
