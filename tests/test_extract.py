from titans_cognition.extract import (
    ColumnMetadata,
    ObjectMetadata,
    extract_facts,
)
from titans_cognition.scope import ScopeConfig


def test_extract_normalizes_ids_and_preserves_physical_rows():
    scope = ScopeConfig(
        scope_id="test-scope",
        source_label="testdb",
        schemas=("TITANS_TRADEFLOW",),
        object_types=("TABLE",),
        excluded_schema_suffixes=("_PROD",),
        excluded_schemas=(),
    )
    objects = [
        ObjectMetadata(
            schema_name="titans_tradeflow",
            object_name="t_event",
            object_type="table",
            columns=(
                ColumnMetadata(
                    column_name="id",
                    ordinal_position=1,
                    data_type="NUMBER",
                    nullable_declared=False,
                ),
            ),
        ),
        ObjectMetadata(
            schema_name="TITANS_TRADEFLOW_PROD",
            object_name="T_EVENT_PROD",
            object_type="TABLE",
        ),
    ]

    result = extract_facts(scope, objects, run_id="run-001")

    assert len(result.objects) == 1
    assert result.objects[0]["asset_id"] == (
        "testdb:TITANS_TRADEFLOW:TABLE:T_EVENT"
    )
    assert result.columns[0]["column_id"] == (
        "testdb:TITANS_TRADEFLOW:TABLE:T_EVENT:COLUMN:ID"
    )
    assert result.objects[0]["extraction_status"] == "SUCCESS"


def test_extract_preserves_object_failure_as_a_failure_record():
    scope = ScopeConfig(
        scope_id="test-scope",
        source_label="testdb",
        schemas=("TITANS_TRADEFLOW",),
        object_types=("TABLE",),
        excluded_schema_suffixes=(),
        excluded_schemas=(),
    )
    failed = ObjectMetadata(
        schema_name="TITANS_TRADEFLOW",
        object_name="BROKEN_OBJECT",
        object_type="TABLE",
        extraction_status="NO_PERMISSION",
        error_category="COLUMN_METADATA",
    )

    result = extract_facts(scope, [failed], run_id="run-002")

    assert result.objects[0]["extraction_status"] == "NO_PERMISSION"
    assert result.failures == [
        {
            "run_id": "run-002",
            "stage": "panorama-extract",
            "target_id": "testdb:TITANS_TRADEFLOW:TABLE:BROKEN_OBJECT",
            "failure_status": "NO_PERMISSION",
            "error_category": "COLUMN_METADATA",
        }
    ]


def test_extract_keeps_boundary_object_records_for_out_of_scope_dependencies():
    scope = ScopeConfig(
        scope_id="test-scope",
        source_label="testdb",
        schemas=("TITANS_TRADEFLOW",),
        object_types=("TABLE",),
        excluded_schema_suffixes=(),
        excluded_schemas=(),
    )
    boundary = ObjectMetadata(
        schema_name="PUBLIC",
        object_name="DUAL",
        object_type="SYNONYM",
        is_boundary=True,
        boundary_for_case_ids=("test-scope",),
    )

    result = extract_facts(scope, [boundary], run_id="run-003")

    assert result.objects[0]["in_panorama_scope"] is False
    assert result.objects[0]["is_boundary"] is True
    assert result.objects[0]["boundary_for_case_ids"] == ["test-scope"]
