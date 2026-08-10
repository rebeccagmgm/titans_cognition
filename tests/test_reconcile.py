from titans_cognition.extract import PhysicalFacts
from titans_cognition.reconcile import reconcile_facts
from titans_cognition.scope import ScopeConfig


def _scope() -> ScopeConfig:
    return ScopeConfig(
        scope_id="panorama",
        source_label="testdb",
        schemas=("TITANS_DM",),
        object_types=("TABLE",),
        excluded_schema_suffixes=(),
        excluded_schemas=(),
    )


def _facts() -> PhysicalFacts:
    return PhysicalFacts(
        objects=[
            {
                "asset_id": "testdb:TITANS_DM:TABLE:T_EVENT",
                "schema_name": "TITANS_DM",
                "object_name": "T_EVENT",
                "object_type": "TABLE",
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
            }
        ],
        object_definitions=[
            {
                "asset_id": "testdb:TITANS_DM:TABLE:T_EVENT",
                "extraction_status": "FAILED",
                "error_category": "NO_PERMISSION",
            }
        ],
        failures=[
            {
                "target_id": "testdb:TITANS_DM:TABLE:T_EVENT",
                "failure_status": "FAILED",
                "error_category": "NO_PERMISSION",
            }
        ],
    )


def test_reconcile_separates_data_pass_from_gate_a_blocked():
    report = reconcile_facts(
        _scope(),
        _facts(),
        {
            "objects": [
                {
                    "schema_name": "TITANS_DM",
                    "object_type": "TABLE",
                    "object_name": "T_EVENT",
                }
            ],
            "columns": [{"schema_name": "TITANS_DM", "column_count": 1}],
        },
        delivery_ready=False,
    )

    assert report["data_reconciliation_status"] == "PASS"
    assert report["gate_a_status"] == "BLOCKED"
    assert "PANORAMA_DELIVERY_NOT_IMPLEMENTED" in report["blockers"]
    assert report["definition_failure_count"] == 1


def test_reconcile_blocks_on_independent_count_mismatch():
    report = reconcile_facts(
        _scope(),
        _facts(),
        {
            "objects": [
                {
                    "schema_name": "TITANS_DM",
                    "object_type": "TABLE",
                    "object_name": "T_EVENT",
                },
                {
                    "schema_name": "TITANS_DM",
                    "object_type": "TABLE",
                    "object_name": "T_MISSING",
                },
            ],
            "columns": [{"schema_name": "TITANS_DM", "column_count": 2}],
        },
        delivery_ready=True,
    )

    assert report["data_reconciliation_status"] == "FAILED"
    assert report["gate_a_status"] == "BLOCKED"
    assert "OBJECT_COUNT_MISMATCH" in report["blockers"]
    assert "COLUMN_COUNT_MISMATCH" in report["blockers"]
