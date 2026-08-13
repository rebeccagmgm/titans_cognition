import hashlib
import json
from dataclasses import replace

import pytest

from titans_cognition.cli import main
from titans_cognition.extract import PhysicalFacts
from titans_cognition.field_semantics import (
    _quality_gate,
    analyze_expression,
    build_field_semantic_comparison,
    load_field_semantic_config,
    normalize_expression,
    run_field_semantics,
    validate_field_semantic_result,
    write_field_semantic_results,
)
from titans_cognition.io import write_json_facts


def _facts() -> PhysicalFacts:
    objects = []
    columns = []
    rows = {
        "REF_CONTRACT": [
            ("INITIAL_NOTIONAL", "初始名义本金(本币)", "VARCHAR2"),
            ("DYNAMIC_NOTIONAL", "动态名义本金，单位：万元", "NUMBER"),
            ("TRADE_DIRECTION", "交易方向 1买 2卖", "VARCHAR2"),
            ("CP_ID", "交易对手ID", "NUMBER"),
            ("EXECUTION_TIME", "成交时间 YYYYMMDDHH24MISS", "VARCHAR2"),
            ("CREATED_BY", "创建人", "VARCHAR2"),
            ("MYSTERY_X", None, "NUMBER"),
            ("NOTIONAL_RESET_DATE", "名义本金重置日期", "DATE"),
        ],
        "REF_POSITION": [
            ("NOTIONAL", "名义本金", "NUMBER"),
            ("COUNTERPARTY", "交易对手", "VARCHAR2"),
            ("MARGIN", "保证金 数据字典", "VARCHAR2"),
            ("PRICE1", "价格1", "NUMBER"),
            ("PRICE2", "价格2", "NUMBER"),
        ],
        "REF_POSITION_2": [("NOTIONAL", "名义本金", "NUMBER")],
    }
    for object_name, field_rows in rows.items():
        asset_id = f"testdb:ALPHA:TABLE:{object_name}"
        objects.append(
            {
                "run_id": "physical-run",
                "asset_id": asset_id,
                "schema_name": "ALPHA",
                "object_name": object_name,
                "object_type": "TABLE",
                "object_comment": "合约持仓",
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


def _config_path(tmp_path):
    physical_manifest = tmp_path / "physical-manifest.json"
    physical_manifest.write_text('{"run_id":"physical-run"}\n', encoding="utf-8")
    baseline_dir = tmp_path / "v1"
    baseline_dir.mkdir()
    (baseline_dir / "manifest.json").write_text("{}\n", encoding="utf-8")
    (baseline_dir / "concepts.jsonl").write_text(
        '{"concept_id":"v1-notional","label":"初始名义本金"}\n',
        encoding="utf-8",
    )
    (baseline_dir / "field_concept_links.jsonl").write_text(
        '{"field_id":"testdb:ALPHA:TABLE:REF_CONTRACT:COLUMN:INITIAL_NOTIONAL",'
        '"concept_id":"v1-notional","rank":1}\n',
        encoding="utf-8",
    )

    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    path = tmp_path / "semantic.yaml"
    path.write_text(
        f"""
version: v2
scope:
  schemas: [ALPHA]
  object_types: [TABLE]
  exclude_numeric_suffix: true
  expected_object_count: 2
  expected_excluded_count: 1
  expected_field_count: 13
baselines:
  physical_facts:
    path: {physical_manifest.as_posix()}
    manifest_sha256: {digest(physical_manifest)}
  field_concepts_v1:
    path: {baseline_dir.as_posix()}
    manifest_sha256: {digest(baseline_dir / 'manifest.json')}
    concepts_sha256: {digest(baseline_dir / 'concepts.jsonl')}
    links_sha256: {digest(baseline_dir / 'field_concept_links.jsonl')}
support_gate:
  min_fields: 2
  require_cross_object_or_multi_expression: true
limits:
  max_competing_candidates: 3
  max_approximate_neighbors: 5
  max_approximate_pairs: 100
  min_approximate_similarity: 0.60
  review_page_size: 20
  initial_concept_limit: 30
abbreviations: {{CP: COUNTERPARTY, INIT: INITIAL}}
bilingual_aliases:
  COUNTERPARTY: 交易对手
  NOTIONAL: 名义本金
  MARGIN: 保证金
  TIME: 时间
  DIRECTION: 方向
  FEE: 费用
  INTEREST: 利息
  INCOME: 收益
  CAPITAL: 资金
  PAYMENT: 支付
  TRADE: 交易
  KNOCKIN: 敲入
  SETTLEMENT: 结算
  WIND: 万得
facets:
  temporal_stage:
    INITIAL: [初始, INITIAL]
    DYNAMIC: [动态, DYNAMIC]
  lifecycle_stage:
    EXECUTION: [成交, EXECUTION]
    TERMINATION: [终止, TERMINATION]
    CLEARING: [结算, CLEARING]
  direction:
    PAY: [支付, PAY]
  currency_basis:
    LOCAL_CURRENCY: [本币, LOCAL_CURRENCY]
  measure_state:
    ACTUAL: [实际, ACTUAL]
field_families:
  DATE: [日期, 日, DATE]
  TIME: [时间, TIME]
  AMOUNT: [金额, AMOUNT]
  CODE: [代码, CODE]
  NAME: [名称, NAME]
technical_patterns:
  audit: [创建人, CREATED_BY]
decorations:
  dictionary_markers: [数据字典]
  implementation_markers: [预留]
  deprecation_markers: [废弃]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return path


def test_normalization_tokenizes_unicode_case_connectors_camel_and_digits():
    normalized = normalize_expression("  Initial-Notional_Amount2（本币） ")
    assert normalized.normalized_text == "initial notional amount 2 本币"
    assert normalized.tokens == ("initial", "notional", "amount", "2", "本币")
    assert normalized.original_text == "  Initial-Notional_Amount2（本币） "


@pytest.mark.parametrize(
    ("text", "decoration_kind"),
    [
        ("交易方向 数据字典", "DICTIONARY_MARKER"),
        ("交易方向 1买 2卖", "VALUE_DOMAIN"),
        ("成交日期 YYYYMMDD", "FORMAT"),
        ("金额 单位：万元", "UNIT"),
        ("金额 CNY", "CURRENCY_CODE"),
        ("金额 NUMBER(18,2)", "PRECISION"),
        ("旧字段 已废弃", "DEPRECATION"),
        ("内部字段 预留", "IMPLEMENTATION_NOTE"),
    ],
)
def test_decorations_are_typed_and_not_promoted_to_head(tmp_path, text, decoration_kind):
    config = load_field_semantic_config(_config_path(tmp_path))
    analysis = analyze_expression("FIELD", text, "NUMBER", config)
    assert decoration_kind in {row["kind"] for row in analysis.decorations}
    assert "数据字典" not in analysis.head_labels
    assert all("YYYYMMDD" not in label for label in analysis.head_labels)


def test_head_concept_wins_over_prefix_and_facets_are_orthogonal(tmp_path):
    config = load_field_semantic_config(_config_path(tmp_path))
    analysis = analyze_expression(
        "INITIAL_NOTIONAL", "调整前多头动态名义本金(本币)", "VARCHAR2", config
    )
    assert analysis.head_labels[0] == "名义本金"
    assert {(row["dimension"], row["value"]) for row in analysis.facets} >= {
        ("temporal_stage", "DYNAMIC"),
        ("currency_basis", "LOCAL_CURRENCY"),
    }
    assert analysis.value_kind == "TEXT"


@pytest.mark.parametrize(
    ("name", "comment", "expected_core", "expected_family", "excluded_facet"),
    [
        ("PAYMENT_DATE", "期权每年支付日期", "支付日期", "DATE", ("direction", "PAY")),
        ("TERMINATION_DATE", "实际终止日期", "终止日期", "DATE", ("lifecycle_stage", "TERMINATION")),
        ("TRADE_DATE", "交易日期", "交易日期", "DATE", ("lifecycle_stage", "EXECUTION")),
        ("SETTLEMENT_DATE", "结算日期", "结算日期", "DATE", ("lifecycle_stage", "CLEARING")),
        ("KNOCK_IN_DATE", "敲入日期", "敲入日期", "DATE", None),
        ("OBSERVATION_DATE", "观察日", "观察日", "DATE", None),
        ("AGREEMENT_SIGNING_DATE", "补充协议签订日", "签订日", "DATE", None),
    ],
)
def test_compound_business_core_is_not_flattened_to_shape_family(
    tmp_path, name, comment, expected_core, expected_family, excluded_facet
):
    analysis = analyze_expression(
        name, comment, "DATE", load_field_semantic_config(_config_path(tmp_path))
    )

    assert analysis.head_labels == (expected_core,)
    assert analysis.field_family == expected_family
    assert expected_core != "日期"
    if excluded_facet:
        assert excluded_facet not in {
            (row["dimension"], row["value"]) for row in analysis.facets
        }


def test_outer_qualifiers_remain_facets_around_compound_core(tmp_path):
    analysis = analyze_expression(
        "ACTUAL_TERMINATION_DATE",
        "实际终止日期",
        "DATE",
        load_field_semantic_config(_config_path(tmp_path)),
    )

    assert analysis.head_labels == ("终止日期",)
    assert ("measure_state", "ACTUAL") in {
        (row["dimension"], row["value"]) for row in analysis.facets
    }


@pytest.mark.parametrize(
    ("name", "expected_core"),
    [
        ("PAYMENT_DATE", "支付日期"),
        ("TRADE_DATE", "交易日期"),
        ("KNOCKIN_DATE", "敲入日期"),
        ("SETTLEMENT_DATE", "结算日期"),
        ("WIND_CODE", "万得代码"),
    ],
)
def test_name_only_compound_core_is_not_flattened(tmp_path, name, expected_core):
    analysis = analyze_expression(
        name, None, "DATE", load_field_semantic_config(_config_path(tmp_path))
    )

    assert analysis.head_labels == (expected_core,)
    assert analysis.field_family in {"DATE", "CODE"}


def test_quality_gate_independently_rejects_collapsed_named_compound(tmp_path):
    config = load_field_semantic_config(_config_path(tmp_path))
    concepts = [{"concept_id": "date", "canonical_key": "日期", "label": "日期"}]
    fields = [
        {
            "column_id": "c1",
            "asset_id": "a1",
            "column_name": "PAYMENT_DATE",
            "column_comment": None,
            "field_family": "DATE",
            "outcome": "SINGLE_CANDIDATE",
            "candidate_bindings": [
                {"concept_id": "date", "relation_kind": "EXPRESSES"}
            ],
        }
    ]

    gate = _quality_gate(concepts, [{}], fields, [], config=config)

    assert gate["checks"]["no_compound_core_collapsed_to_family"] is False
    assert gate["status"] == "FAIL"


@pytest.mark.parametrize(
    ("name", "comment", "expected"),
    [
        ("TODAY_FEE", "当日费用", "费用"),
        ("INITIAL_INTEREST", "期初利息", "利息"),
        ("CURRENT_INCOME", "当前收益", "收益"),
        ("END_CAPITAL", "期末资金", "资金"),
    ],
)
def test_center_word_beats_temporal_prefix(tmp_path, name, comment, expected):
    analysis = analyze_expression(
        name, comment, "NUMBER", load_field_semantic_config(_config_path(tmp_path))
    )
    assert analysis.head_labels == (expected,)


def test_tfidf_recall_is_bounded_and_never_publishes_hierarchy(tmp_path):
    result = run_field_semantics(_facts(), load_field_semantic_config(_config_path(tmp_path)))
    assert len(result.approximate_candidates) <= 100
    assert all(row["published_relation"] is False for row in result.approximate_candidates)
    assert all("parent_id" not in row for row in result.base_concepts)


def test_specific_comment_alias_beats_broader_name_token(tmp_path):
    config = load_field_semantic_config(_config_path(tmp_path))
    config = replace(
        config,
        bilingual_aliases={**config.bilingual_aliases, "PRINCIPAL": "本金"},
    )
    analysis = analyze_expression(
        "NAME_OF_PRINCIPAL", "名义本金", "NUMBER", config
    )
    assert analysis.head_labels == ("名义本金",)
    assert "POSSIBLE_CONCATENATION" not in analysis.diagnostic_codes


def test_pipeline_preserves_unknown_competing_support_and_scope(tmp_path):
    config = load_field_semantic_config(_config_path(tmp_path))
    result = run_field_semantics(_facts(), config)
    by_column = {row["column_id"]: row for row in result.field_results}

    mystery = next(row for key, row in by_column.items() if key.endswith("MYSTERY_X"))
    assert mystery["outcome"] == "UNKNOWN"
    assert mystery["candidate_bindings"] == []

    notional = next(
        row for key, row in by_column.items() if key.endswith("INITIAL_NOTIONAL")
    )
    assert notional["outcome"] == "SINGLE_CANDIDATE"
    direct = [
        row for row in notional["candidate_bindings"] if row["relation_kind"] == "EXPRESSES"
    ]
    assert len(direct) == 1
    assert len([row for row in result.facets if row["binding_id"] == direct[0]["binding_id"]]) >= 2

    concepts = {row["label"]: row for row in result.base_concepts}
    assert concepts["名义本金"]["support_status"] == "SUPPORTED"
    assert concepts["名义本金"]["semantic_scope"] == "DOMAIN"
    assert concepts["创建人"]["semantic_scope"] == "TECHNICAL"
    assert all(row["label"] not in {"数据字典", "万元", "YYYYMMDDHH24MISS"} for row in result.base_concepts)

    reset = next(
        row for key, row in by_column.items() if key.endswith("NOTIONAL_RESET_DATE")
    )
    relation_kinds = {row["relation_kind"] for row in reset["candidate_bindings"]}
    assert relation_kinds == {"EXPRESSES", "RELATED_TO"}
    direct_labels = {
        next(c["label"] for c in result.base_concepts if c["concept_id"] == row["concept_id"])
        for row in reset["candidate_bindings"]
        if row["relation_kind"] == "EXPRESSES"
    }
    assert "名义本金" not in direct_labels


def test_unknown_quality_gate_allows_related_navigation(tmp_path):
    result = run_field_semantics(_facts(), load_field_semantic_config(_config_path(tmp_path)))
    unknown = next(row for row in result.field_results if row["outcome"] == "UNKNOWN")
    related = next(
        binding
        for row in result.field_results
        for binding in row["candidate_bindings"]
        if binding["relation_kind"] == "RELATED_TO"
    )
    unknown["candidate_bindings"] = [related]

    gate = _quality_gate(
        result.base_concepts,
        result.expressions,
        result.field_results,
        result.facets,
    )

    assert gate["checks"]["unknowns_have_no_direct_candidates"] is True


def test_numeric_slots_and_same_label_conflicts_are_not_auto_merged(tmp_path):
    result = run_field_semantics(_facts(), load_field_semantic_config(_config_path(tmp_path)))
    price_rows = [row for row in result.field_results if row["column_name"].startswith("PRICE")]
    assert all("NUMERIC_SLOT" in row["diagnostic_codes"] for row in price_rows)
    assert all(row["review_status"] == "REVIEW_REQUIRED" for row in price_rows)


def test_metamorphic_head_replacement_keeps_facet_shape(tmp_path):
    config = load_field_semantic_config(_config_path(tmp_path))
    first = analyze_expression("INITIAL_FOO", "初始动态星云额度(本币)", "NUMBER", config)
    second = analyze_expression("INITIAL_BAR", "初始动态量子额度(本币)", "NUMBER", config)
    assert [(x["dimension"], x["value"]) for x in first.facets] == [
        (x["dimension"], x["value"]) for x in second.facets
    ]
    assert first.head_labels != second.head_labels


def test_contract_validation_rejects_dangling_references(tmp_path):
    config = load_field_semantic_config(_config_path(tmp_path))
    result = run_field_semantics(_facts(), config)
    validate_field_semantic_result(result, _facts())
    result.field_results[0]["candidate_bindings"][0]["concept_id"] = "missing"
    with pytest.raises(ValueError, match="unknown concept_id"):
        validate_field_semantic_result(result, _facts())


def test_writer_is_deterministic_and_cli_refuses_scope_drift(tmp_path, capsys):
    config_path = _config_path(tmp_path)
    config = load_field_semantic_config(config_path)
    result = run_field_semantics(_facts(), config)
    first = write_field_semantic_results(
        tmp_path / "first",
        result,
        _facts(),
        config=config,
        investigation_queries=("初始名义本金", "交易方向"),
    )
    second = write_field_semantic_results(
        tmp_path / "second",
        result,
        _facts(),
        config=config,
        investigation_queries=("初始名义本金", "交易方向"),
    )
    assert json.loads(first["manifest"].read_text(encoding="utf-8"))["outputs"] == json.loads(
        second["manifest"].read_text(encoding="utf-8")
    )["outputs"]
    assert {path.name for path in first.values()} >= {
        "base_concepts.jsonl",
        "concept_expressions.jsonl",
        "field_semantic_results.jsonl",
        "field_facets.jsonl",
        "manifest.json",
        "comparison.json",
        "comparison.md",
    }
    comparison = json.loads(first["comparison_json"].read_text(encoding="utf-8"))
    notional = next(row for row in comparison["investigations"] if row["query"] == "初始名义本金")
    assert notional["resolved_head_labels"] == ["名义本金"]
    assert {row["dimension"] for row in notional["resolved_facets"]} >= {"temporal_stage"}
    assert notional["field_count"] >= 1
    assert comparison["v1_v2"]["aligned_field_count"] == 1

    facts_dir = tmp_path / "facts"
    write_json_facts(facts_dir, _facts())
    assert main([
        "discover-field-semantics",
        "--facts-dir", str(facts_dir),
        "--config", str(config_path),
        "--output", str(tmp_path / "cli-result"),
        "--investigation-query", "初始名义本金",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["field_count"] == 13
    assert payload["semantic_shape_gate"] in {"PASS", "FAIL"}

    drift = load_field_semantic_config(config_path).with_expected_object_count(3)
    with pytest.raises(ValueError, match="expected 3 objects, got 2"):
        run_field_semantics(_facts(), drift)


def test_comparison_query_uses_head_and_facet_decomposition(tmp_path):
    config = load_field_semantic_config(_config_path(tmp_path))
    result = run_field_semantics(_facts(), config)
    comparison = build_field_semantic_comparison(
        result,
        config,
        ("初始名义本金", "成交时间", "交易方向"),
    )
    initial = comparison["investigations"][0]
    assert initial["resolved_head_labels"] == ["名义本金"]
    assert initial["field_count"] >= 1
    assert comparison["gate"]["status"] == "PASS", json.dumps(
        comparison, ensure_ascii=False, indent=2
    )


def test_review_projection_is_bounded_and_keeps_bidirectional_links(tmp_path):
    config = load_field_semantic_config(_config_path(tmp_path))
    result = run_field_semantics(_facts(), config)
    paths = write_field_semantic_results(
        tmp_path,
        result,
        _facts(),
        config=config,
        investigation_queries=("名义本金",),
    )
    html = paths["review_index"].read_text(encoding="utf-8")
    worker = paths["review_worker"].read_text(encoding="utf-8")
    summary = json.loads(paths["review_summary"].read_text(encoding="utf-8"))
    assert "catalog.js" in html
    assert "SIZE=20" in html
    assert "field_semantic_results.jsonl" not in html
    assert "window.FIELD_SEMANTIC_CATALOG=" not in html
    assert "LOOKUP_CONCEPT" in worker
    assert "LOOKUP_TABLE" in worker
    assert "LOOKUP_COLUMN" in worker
    assert "LOOKUP_FACET" in worker
    assert "LOOKUP_SCOPE" in worker
    assert summary["table_business_classification_read"] is False
    assert summary["concepts"][0]["concept_id"]


def test_review_page_supports_search_facets_status_and_local_shards(tmp_path):
    config = load_field_semantic_config(_config_path(tmp_path))
    result = run_field_semantics(_facts(), config)
    paths = write_field_semantic_results(
        tmp_path,
        result,
        _facts(),
        config=config,
        investigation_queries=("鍚嶄箟鏈噾",),
    )

    html = paths["review_index"].read_text(encoding="utf-8")
    catalog = paths["review_catalog"].read_text(encoding="utf-8")
    assert 'id="search"' in html
    assert 'id="relation-filter"' in html
    assert 'id="facet-filters"' in html
    assert 'data-view="FAMILY"' in html
    assert 'data-view="UNKNOWN"' in html
    assert 'data-view="CONFLICT"' in html
    assert "相关表达" in html
    assert "技术详情" in html
    assert "字段族" in html
    assert "Panorama" in html
    assert "field_semantic_results.jsonl" not in html
    assert "window.FIELD_SEMANTIC_CATALOG" in catalog
    assert paths["review_field_catalog"].exists()
    assert "fetch(" not in html
    assert "fetch(" not in paths["review_worker"].read_text(encoding="utf-8")

    shard_root = paths["review_data_root"]
    concept_shards = list((shard_root / "concepts").glob("*.js"))
    table_shards = list((shard_root / "tables").glob("*.js"))
    assert concept_shards
    assert table_shards
    shard_text = "\n".join(path.read_text(encoding="utf-8") for path in concept_shards)
    assert "EXPRESSES" in shard_text
    assert "facets" in shard_text
    assert "object_url" in shard_text


def test_review_catalog_contains_reverse_lookup_and_frozen_v1_link(tmp_path):
    config = load_field_semantic_config(_config_path(tmp_path))
    result = run_field_semantics(_facts(), config)
    paths = write_field_semantic_results(tmp_path, result, _facts(), config=config)
    catalog_text = paths["review_catalog"].read_text(encoding="utf-8")
    payload = json.loads(catalog_text.split("=", 1)[1].rstrip(";\n"))
    assert "field_families" in payload

    assert payload["concepts"]
    assert payload["tables"]
    fields_text = paths["review_field_catalog"].read_text(encoding="utf-8")
    fields = json.loads(fields_text.split("=", 1)[1].rstrip(";\n"))
    assert fields
    assert payload["v1_review_url"].endswith("review/index.html")
    assert all(row["shard"] for row in payload["concepts"])
    assert all(row["shard"] for row in payload["tables"])
    assert any(row["column_name"] == "INITIAL_NOTIONAL" for row in fields)
