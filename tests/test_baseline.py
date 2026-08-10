import json

from titans_cognition.baseline import CommandResult, build_independent_baseline
from titans_cognition.scope import ScopeConfig


def test_independent_baseline_reads_object_names_and_column_counts():
    def runner(command, _timeout):
        sql = command[command.index("--sql") + 1]
        if "ALL_TAB_COLUMNS" in sql:
            rows = [{"OWNER": "TITANS_DM", "COLUMN_COUNT": "1"}]
        elif "ALL_OBJECTS" in sql:
            rows = [
                {
                    "OWNER": "TITANS_DM",
                    "OBJECT_NAME": "T_EVENT",
                    "OBJECT_TYPE": "TABLE",
                }
            ]
        else:
            raise AssertionError(sql)
        return CommandResult(0, json.dumps(rows), "")

    scope = ScopeConfig(
        scope_id="panorama",
        source_label="testdb",
        schemas=("TITANS_DM",),
        object_types=("TABLE",),
        excluded_schema_suffixes=(),
        excluded_schemas=(),
    )

    baseline = build_independent_baseline(
        scope,
        python_executable="python",
        query_script="query.py",
        database="testdb",
        runner=runner,
    )

    assert baseline["objects"] == [
        {
            "schema_name": "TITANS_DM",
            "object_name": "T_EVENT",
            "object_type": "TABLE",
        }
    ]
    assert baseline["columns"] == [
        {"schema_name": "TITANS_DM", "column_count": 1}
    ]
