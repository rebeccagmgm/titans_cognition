from titans_cognition.derive import derive_observations
from titans_cognition.extract import PhysicalFacts


def test_derive_observations_produces_structural_only_summaries():
    facts = PhysicalFacts(
        objects=[
            {
                "run_id": "run-001",
                "asset_id": "testdb:TITANS_DM:TABLE:T_EVENT",
                "source_label": "testdb",
                "schema_name": "TITANS_DM",
                "object_name": "T_EVENT",
                "object_type": "TABLE",
                "object_comment": "event table",
                "extraction_status": "SUCCESS",
            },
            {
                "run_id": "run-001",
                "asset_id": "testdb:TITANS_DM:VIEW:V_EVENT",
                "source_label": "testdb",
                "schema_name": "TITANS_DM",
                "object_name": "V_EVENT",
                "object_type": "VIEW",
                "object_comment": None,
                "extraction_status": "SUCCESS",
            },
        ],
        columns=[
            {
                "asset_id": "testdb:TITANS_DM:TABLE:T_EVENT",
                "column_name": "EVENT_ID",
                "data_type": "NUMBER",
                "nullable_declared": False,
            },
            {
                "asset_id": "testdb:TITANS_DM:TABLE:T_EVENT",
                "column_name": "EVENT_STATUS",
                "data_type": "VARCHAR2",
                "nullable_declared": True,
            },
        ],
        constraints=[
            {
                "asset_id": "testdb:TITANS_DM:TABLE:T_EVENT",
                "constraint_type": "PRIMARY_KEY",
            }
        ],
        indexes=[],
        object_definitions=[
            {
                "asset_id": "testdb:TITANS_DM:TABLE:T_EVENT",
                "extraction_status": "SUCCESS",
            },
            {
                "asset_id": "testdb:TITANS_DM:VIEW:V_EVENT",
                "extraction_status": "FAILED",
                "error_category": "NO_PERMISSION",
            },
        ],
        dependencies=[
            {
                "source_asset_id": "testdb:TITANS_DM:VIEW:V_EVENT",
                "target_asset_id": "testdb:TITANS_TRADEFLOW:TABLE:T_SOURCE",
                "target_is_boundary": True,
            }
        ],
        failures=[
            {
                "target_id": "testdb:TITANS_DM:VIEW:V_EVENT",
                "failure_status": "FAILED",
                "error_category": "NO_PERMISSION",
            }
        ],
    )

    derived = derive_observations(facts)

    schema = derived.schema_summary[0]
    assert schema["schema_name"] == "TITANS_DM"
    assert schema["object_count"] == 2
    assert schema["column_count"] == 2
    assert schema["definition_failure_count"] == 1

    profile = next(
        row
        for row in derived.object_inventory_profiles
        if row["object_name"] == "T_EVENT"
    )
    assert profile["column_count"] == 2
    assert profile["comment_present"] is True
    assert "identity" not in profile
    assert "grain" not in profile

    dependency = derived.dependency_summary[0]
    assert dependency["source_schema_name"] == "TITANS_DM"
    assert dependency["target_schema_name"] == "TITANS_TRADEFLOW"
    assert dependency["dependency_count"] == 1
