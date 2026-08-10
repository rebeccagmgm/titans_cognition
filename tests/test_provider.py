import json

from titans_cognition.extract import DefinitionMetadata
from titans_cognition.provider import (
    CommandResult,
    GfDerivativeDbProvider,
    _BatchDefinitionStore,
    _decode_adapter_output,
)
from titans_cognition.scope import ScopeConfig


def test_provider_decodes_gb18030_adapter_output_without_replacement_characters():
    encoded = "北上极速腿当前持仓表".encode("gb18030")

    assert _decode_adapter_output(encoded) == "北上极速腿当前持仓表"


def test_gf_provider_builds_provider_neutral_metadata_from_dictionary_rows():
    def runner(command, _timeout):
        if command[2] == "ddl-batch":
            return CommandResult(
                0,
                json.dumps(
                    [
                        {
                            "owner": "TITANS_TRADEFLOW",
                            "object_name": "T_EVENT",
                            "object_type": "TABLE",
                            "definition_type": "DDL",
                            "definition_text": "CREATE TABLE T_EVENT (ID NUMBER);",
                            "extraction_status": "SUCCESS",
                            "error_category": None,
                        }
                    ]
                ),
                "",
            )
        if command[2] == "ddl":
            assert command[command.index("--table") + 1] == (
                "TITANS_TRADEFLOW.T_EVENT"
            )
            return CommandResult(0, "CREATE TABLE T_EVENT (ID NUMBER);\n", "")
        sql = command[command.index("--sql") + 1]
        if "ALL_OBJECTS" in sql:
            rows = [
                {
                    "OWNER": "TITANS_TRADEFLOW",
                    "OBJECT_NAME": "T_EVENT",
                    "OBJECT_TYPE": "TABLE",
                }
            ]
        elif "ALL_TAB_COLUMNS" in sql:
            rows = [
                {
                    "OWNER": "TITANS_TRADEFLOW",
                    "TABLE_NAME": "T_EVENT",
                    "COLUMN_NAME": "ID",
                    "COLUMN_ID": "1",
                    "DATA_TYPE": "NUMBER",
                    "DATA_LENGTH": "22",
                    "DATA_PRECISION": None,
                    "DATA_SCALE": None,
                    "NULLABLE": "N",
                }
            ]
        elif "ALL_COL_COMMENTS" in sql:
            rows = [
                {
                    "OWNER": "TITANS_TRADEFLOW",
                    "TABLE_NAME": "T_EVENT",
                    "COLUMN_NAME": "ID",
                    "COMMENTS": "technical id",
                }
            ]
        elif "ALL_TAB_COMMENTS" in sql:
            rows = [
                {
                    "OWNER": "TITANS_TRADEFLOW",
                    "TABLE_NAME": "T_EVENT",
                    "COMMENTS": "event table",
                }
            ]
        elif "ALL_CONSTRAINTS" in sql:
            rows = [
                {
                    "OWNER": "TITANS_TRADEFLOW",
                    "TABLE_NAME": "T_EVENT",
                    "CONSTRAINT_NAME": "PK_EVENT",
                    "CONSTRAINT_TYPE": "P",
                    "STATUS": "ENABLED",
                    "R_OWNER": None,
                    "R_CONSTRAINT_NAME": None,
                }
            ]
        elif "ALL_CONS_COLUMNS" in sql:
            rows = [
                {
                    "OWNER": "TITANS_TRADEFLOW",
                    "TABLE_NAME": "T_EVENT",
                    "CONSTRAINT_NAME": "PK_EVENT",
                    "COLUMN_NAME": "ID",
                    "POSITION": "1",
                }
            ]
        elif "ALL_INDEXES" in sql:
            rows = [
                {
                    "OWNER": "TITANS_TRADEFLOW",
                    "INDEX_NAME": "PK_EVENT",
                    "TABLE_NAME": "T_EVENT",
                    "UNIQUENESS": "UNIQUE",
                    "INDEX_TYPE": "NORMAL",
                    "STATUS": "VALID",
                }
            ]
        elif "ALL_IND_COLUMNS" in sql:
            rows = [
                {
                    "INDEX_OWNER": "TITANS_TRADEFLOW",
                    "INDEX_NAME": "PK_EVENT",
                    "TABLE_NAME": "T_EVENT",
                    "COLUMN_NAME": "ID",
                    "COLUMN_POSITION": "1",
                }
            ]
        elif "ALL_DEPENDENCIES" in sql:
            rows = []
        elif "ALL_VIEWS" in sql:
            rows = []
        else:
            raise AssertionError(sql)
        return CommandResult(0, json.dumps(rows), "")

    scope = ScopeConfig(
        scope_id="tradeflow",
        source_label="testdb",
        schemas=("TITANS_TRADEFLOW",),
        object_types=("TABLE",),
        excluded_schema_suffixes=(),
        excluded_schemas=(),
    )
    provider = GfDerivativeDbProvider(
        python_executable="python",
        query_script="query.py",
        database="testdb",
        definition_mode="all",
        runner=runner,
    )

    objects = list(provider.iter_objects(scope))

    assert len(objects) == 1
    assert objects[0].object_comment == "event table"
    assert objects[0].columns[0].column_comment == "technical id"
    assert objects[0].constraints[0].constraint_type == "PRIMARY_KEY"
    assert objects[0].indexes[0].is_unique is True
    assert objects[0].definitions[0].definition_text == (
        "CREATE TABLE T_EVENT (ID NUMBER);"
    )


def test_gf_provider_preserves_definition_permission_failure():
    def runner(command, _timeout):
        return CommandResult(1, "", "ERROR: ORA-01031 insufficient privileges")

    provider = GfDerivativeDbProvider(
        python_executable="python",
        query_script="query.py",
        database="testdb",
        runner=runner,
    )

    definition = provider._fetch_adapter_definition(
        "TITANS_TRADEFLOW",
        "T_EVENT",
    )

    assert definition.extraction_status == "NO_PERMISSION"
    assert definition.error_category == "ADAPTER_PERMISSION"


def test_gf_provider_maps_view_dictionary_text_to_view_sql_definition():
    def runner(command, _timeout):
        sql = command[command.index("--sql") + 1]
        assert "ALL_VIEWS" in sql
        return CommandResult(
            0,
            json.dumps(
                [
                    {
                        "OWNER": "TITANS_DM",
                        "VIEW_NAME": "V_EVENT",
                        "TEXT": "SELECT ID FROM T_EVENT",
                    }
                ]
            ),
            "",
        )

    scope = ScopeConfig(
        scope_id="tradeflow",
        source_label="testdb",
        schemas=("TITANS_DM",),
        object_types=("VIEW",),
        excluded_schema_suffixes=(),
        excluded_schemas=(),
    )
    provider = GfDerivativeDbProvider(
        python_executable="python",
        query_script="query.py",
        database="testdb",
        definition_mode="all",
        runner=runner,
    )

    view_sql = provider._fetch_view_sql(scope)
    definition = provider._definition_for_object(
        "TITANS_DM",
        "V_EVENT",
        "VIEW",
        view_sql,
        None,
    )

    assert definition.definition_type == "VIEW_SQL"
    assert definition.definition_text == "SELECT ID FROM T_EVENT"
    assert definition.extraction_status == "SUCCESS"


def test_batch_definition_store_loads_one_chunk_at_a_time(tmp_path):
    chunk_a = tmp_path / "definitions-00001.json"
    chunk_b = tmp_path / "definitions-00002.json"
    chunk_a.write_text(
        json.dumps(
            [
                {
                    "owner": "TITANS_TRADEFLOW",
                    "object_name": "T_EVENT_A",
                    "definition_type": "DDL",
                    "definition_text": "CREATE TABLE A (ID NUMBER);",
                    "extraction_status": "SUCCESS",
                }
            ]
        ),
        encoding="utf-8",
    )
    chunk_b.write_text(
        json.dumps(
            [
                {
                    "owner": "TITANS_TRADEFLOW",
                    "object_name": "T_EVENT_B",
                    "definition_type": "DDL",
                    "definition_text": "CREATE TABLE B (ID NUMBER);",
                    "extraction_status": "SUCCESS",
                }
            ]
        ),
        encoding="utf-8",
    )

    store = _BatchDefinitionStore.from_manifest(
        tmp_path,
        [chunk_a.name, chunk_b.name],
    )
    default = DefinitionMetadata(
        definition_type="DDL",
        extraction_status="MISSING",
        error_category="NOT_FOUND",
    )

    assert store.get(("TITANS_TRADEFLOW", "T_EVENT_A"), default).definition_text == (
        "CREATE TABLE A (ID NUMBER);"
    )
    assert store.get(("TITANS_TRADEFLOW", "T_EVENT_B"), default).definition_text == (
        "CREATE TABLE B (ID NUMBER);"
    )
