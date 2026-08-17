from scripts.szdata_star_metadata_batch import (
    is_rate_limited,
    load_guid_overrides,
    parse_ddl_response,
    parse_table_response,
)


def test_parse_table_response_unwraps_array_and_nested_table():
    payload = [
        {
            "table": {
                "guid": "guid-1",
                "qualifiedName": "odata_n_tit.example",
                "description": "示例",
            },
            "structure": {"columnCount": 2},
            "lineage": {"upstream": []},
        }
    ]

    result = parse_table_response(payload)

    assert result == {
        "guid": "guid-1",
        "qualifiedName": "odata_n_tit.example",
        "description": "示例",
        "structure": {"columnCount": 2},
        "lineage": {"upstream": []},
    }


def test_parse_ddl_response_unwraps_array():
    payload = [
        {
            "guid": "guid-1",
            "qualifiedName": "odata_n_tit.example@gfhive",
            "ddl": "create table example(id string);",
        }
    ]

    result = parse_ddl_response(payload)

    assert result == {
        "guid": "guid-1",
        "qualifiedName": "odata_n_tit.example@gfhive",
        "ddl": "create table example(id string);",
    }


def test_is_rate_limited_only_matches_user_throttle_signals():
    assert is_rate_limited("dimension=USER threshold=5")
    assert is_rate_limited("MCP 全局限流")
    assert not is_rate_limited("Table not found in metadata MCP")


def test_load_guid_overrides_accepts_documented_object_shape(tmp_path):
    path = tmp_path / "overrides.json"
    path.write_text(
        '{"overrides": {"PDATA_N.REF_CD_CVT_MAP": {"guid": "guid-1"}}}',
        encoding="utf-8",
    )

    assert load_guid_overrides(path) == {"pdata_n.ref_cd_cvt_map": "guid-1"}
