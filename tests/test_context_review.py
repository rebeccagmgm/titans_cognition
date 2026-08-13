import json
import os
from pathlib import Path
import re
import subprocess
from types import SimpleNamespace

import pytest

from titans_cognition.context_review import _navigation_paths


ROOT = Path(
    "output/stage3-tradeflow-context-semantic-map-v1-20260812/"
    "context-enriched-field-semantic-map/review"
)
BUNDLE_ROOT = ROOT.parent

real_output = pytest.mark.skipif(
    os.environ.get("RUN_REAL_OUTPUT_ACCEPTANCE") != "1"
    or not (ROOT / "data" / "catalog.js").exists(),
    reason="set RUN_REAL_OUTPUT_ACCEPTANCE=1 for generated-artifact acceptance",
)


def _catalog():
    text = (ROOT / "data" / "catalog.js").read_text(encoding="utf-8")
    return json.loads(
        text.removeprefix("window.FIELD_MAP_CATALOG=").removesuffix(";\n")
    )


def _shard(concept_id):
    text = (ROOT / "data" / "concepts" / f"{concept_id}.js").read_text(encoding="utf-8")
    payload = text.split("=", 2)[2].removesuffix(";\n")
    return json.loads(payload)


def _jsonl(name):
    return [
        json.loads(line)
        for line in (BUNDLE_ROOT / name).read_text(encoding="utf-8").splitlines()
        if line
    ]


@real_output
def test_real_review_first_load_is_bounded_and_sharded():
    assert (ROOT / "index.html").stat().st_size < 30_000
    assert (ROOT / "data" / "catalog.js").stat().st_size < 750_000
    catalog = _catalog()
    assert len(catalog) > 1000
    assert len(list((ROOT / "data" / "concepts").glob("*.js"))) == len(catalog)


@real_output
def test_real_nominal_principal_candidates_are_retained_and_publication_is_bounded():
    concept = next(row for row in _catalog() if row["label"] == "名义本金")
    shard = _shard(concept["id"])
    labels = {row["label"] for row in shard["expressions"]}
    hypotheses = [
        row
        for row in _jsonl("semantic_hypotheses.jsonl")
        if row["proposed_business_concept_id"] == concept["id"]
    ]
    all_fields = {field for row in hypotheses for field in row["field_refs"]}
    published_fields = {
        field
        for row in hypotheses
        if row["publication_status"] == "PUBLISHED"
        for field in row["field_refs"]
    }

    assert len(all_fields) >= 62
    assert concept["fieldCount"] == len(published_fields) == 55
    assert {"名义本金", "初始名义本金", "动态名义本金"} <= labels
    assert any("多头动态名义本金" in label for label in labels)
    assert any("空头动态名义本金" in label for label in labels)
    assert any(
        instance["objectUrl"]
        for row in shard["expressions"]
        for group in row["physicalGroups"]
        for instance in group["instances"]
    )
    assert all(row["status"] != "CONFLICT" for row in shard["expressions"])
    assert any(
        row["publication_status"] == "NOT_PUBLISHED"
        and row["publication_reason"]
        in {"COUNTEREVIDENCE_REQUIRES_REVIEW", "SEMANTIC_LINK_NOT_PROVEN"}
        for row in hypotheses
    )


@real_output
def test_real_second_concept_and_open_dimensions_are_present():
    concept = next(row for row in _catalog() if row["label"] == "交易对手")
    shard = _shard(concept["id"])
    assert concept["fieldCount"] >= 40
    assert ["业务主体"] in shard["concept"]["navigationPaths"]
    dimensions = {
        qualifier["dimension"]
        for row in shard["expressions"]
        for qualifier in row["qualifiers"]
    }
    assert {"attribute_kind", "flow_side"} <= dimensions
    assert "party_role" not in dimensions


@real_output
def test_real_navigation_keeps_entities_attributes_and_unknowns_separate():
    by_label = {row["label"]: row for row in _catalog()}

    assert by_label["交易对手"]["paths"] == [["业务主体"]]
    assert by_label["交易对手短名"]["paths"] == [
        ["业务主体", "交易对手属性"]
    ]
    assert by_label["是否二级交易商客户"]["paths"] == [
        ["字段属性", "状态标志"]
    ]
    assert by_label["是否生成保证金期权合约"]["paths"] == [
        ["字段属性", "状态标志"]
    ]
    assert by_label["保证金合约编号"]["paths"] == [["字段属性", "标识"]]
    assert by_label["清算机构"]["paths"] == [["待归类"]]


@real_output
def test_unproven_hedge_account_expression_is_retained_but_not_published():
    concept = next(row for row in _catalog() if row["label"] == "对冲账户")
    shard = _shard(concept["id"])
    rows = [
        row for row in shard["expressions"] if row["label"].startswith("对手方对冲账户")
    ]

    assert rows == []
    hypotheses = [
        row
        for row in _jsonl("semantic_hypotheses.jsonl")
        if row["proposed_business_concept_id"] == concept["id"]
        and row["label"].startswith("对手方对冲账户")
    ]
    assert len(hypotheses) == 1
    assert hypotheses[0]["publication_status"] == "NOT_PUBLISHED"
    assert hypotheses[0]["publication_reason"] == "SEMANTIC_LINK_NOT_PROVEN"
    assert len(hypotheses[0]["field_refs"]) == 2


@real_output
def test_review_html_javascript_is_valid(tmp_path):
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    scripts = re.findall(r"<script(?: [^>]*)?>(.*?)</script>", html, re.S)
    script = tmp_path / "review-inline.js"
    script.write_text("\n".join(scripts), encoding="utf-8")
    result = subprocess.run(
        ["node", "--check", str(script)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "setTimeout(renderNav,180)" in html
    assert "s.remove()" in html
    assert "没有真实出现的匹配表达" in html
    assert ".technical-name{text-transform:lowercase}" in html
    assert "currency_basis:'币种'" in html
    assert "measure_basis:'口径'" in html
    assert "ABSOLUTE:'绝对'" in html
    assert "PAY:'支付'" in html
    assert "EXECUTION:'成交'" in html
    assert "ACCUMULATED:'累计'" in html
    assert "ESTIMATED:'预估'" in html
    assert "FIXED:'固定'" in html
    assert "FROZEN:'冻结'" in html
    assert "attribute_kind:'属性种类'" in html
    assert "flow_side:'数据侧'" in html
    assert "variability:'变化方式'" in html
    assert "position_side:'持仓方向'" in html
    assert "trade_side:'交易方向'" in html
    assert "cashflow_direction:'收付方向'" in html
    assert "semantic_modifier:'修饰词'" not in html
    assert "候选归拢" in html
    assert "结算币种" in html
    assert "activeFacets" in html
    assert "Object.entries(activeFacets).every" in html
    assert ".facet-option.active" in html
    assert "② 属性表达矩阵" in html
    assert "expression-matrix" in html
    assert "facetCount(d,v)" in html
    assert "contextualQualifiers" in html
    assert "上下文提示" in html
    assert "data-group-page" in html
    assert "当前限定组合没有真实属性表达" in html
    assert "<th>实现</th><th>表</th>" in html
    assert "表注释" in html
    assert "<th>Schema</th>" in html
    assert "objectComment" in html
    assert "同名字段共识" in html
    assert "NAV_LIMIT=" in html
    assert "显示其余 ${more} 项" in html
    assert "v.slice(0,200)" not in html


def test_semantic_head_wins_over_event_modifier_for_navigation():
    assert _navigation_paths("结算汇率", ["NUMBER"]) == [["业务度量", "比率"]]
    assert _navigation_paths("重置汇率", ["NUMBER"]) == [["业务度量", "比率"]]
    assert ["业务事件"] in _navigation_paths("重置", ["TEXT"])


def test_entity_attributes_are_nested_and_subject_precedes_object():
    config = SimpleNamespace(
        navigation_terms={},
        family_labels={},
        navigation_types={
            "业务主体": ("PARTY",),
            "业务对象": ("OBJECT",),
        },
        subjects=("客户", "交易对手"),
        events=(),
        objects=("合约", "交易", "交易对手"),
    )

    assert _navigation_paths("交易对手", ["TEXT"], config) == [["业务主体"]]
    assert _navigation_paths("交易对手短名", ["TEXT"], config) == [
        ["业务主体", "交易对手属性"]
    ]
    assert _navigation_paths("交易对手佣金费率", ["NUMBER"], config) == [
        ["业务度量", "比率"]
    ]
    assert _navigation_paths("合约交易流水号", ["TEXT"], config) == [
        ["字段属性", "标识"]
    ]


@pytest.mark.parametrize(
    ("label", "value_kinds", "expected"),
    [
        ("保证金合约编号", ["TEXT"], [["字段属性", "标识"]]),
        ("是否生成保证金期权合约", ["TEXT"], [["字段属性", "状态标志"]]),
        ("收益率", ["NUMBER"], [["业务度量", "比率"]]),
        ("费用比率", ["NUMBER"], [["业务度量", "比率"]]),
        ("保证金比例", ["NUMBER"], [["业务度量", "比率"]]),
        ("估值日期", ["DATE"], [["日期时间", "日期"]]),
        ("名义本金重置时间列表", ["TEXT"], [["日期时间", "时间"]]),
        ("清算机构", ["TEXT"], [["待归类"]]),
        ("意向成交流水原始汇总表主键", ["TEXT"], [["字段属性", "标识"]]),
        ("场外合约交易流水号", ["TEXT"], [["字段属性", "标识"]]),
    ],
)
def test_navigation_uses_semantic_head_and_abstains_on_ambiguous_contains(
    label, value_kinds, expected
):
    assert _navigation_paths(label, value_kinds) == expected


def test_navigation_families_and_roots_are_config_driven_across_languages():
    config = SimpleNamespace(
        navigation_terms={
            "AMOUNT": ("AMOUNT",),
            "QUANTITY": ("QUANTITY",),
            "RATE": ("RATE",),
            "DATE": ("DATE",),
            "TIME": ("TIMESTAMP",),
        },
        family_labels={"DATE": "Date", "TIME": "Timestamp", "AMOUNT": "Amount"},
        navigation_types={"Measures": ("AMOUNT",), "Temporal": ("DATE", "TIME")},
        subjects=(),
        events=(),
        objects=(),
        attribute_navigation={"Identifier": ("* ID", "* Code")},
        entity_attribute_template="{entity} Attributes",
    )

    assert _navigation_paths("Settlement Date", ["TEXT"], config) == [
        ["Temporal", "Date"]
    ]
    assert _navigation_paths("Trade Timestamp", ["TEXT"], config) == [
        ["Temporal", "Timestamp"]
    ]
    assert _navigation_paths("Gross Amount", ["NUMBER"], config) == [
        ["Measures", "Amount"]
    ]

    config.subjects = ("Customer",)
    config.navigation_types["Parties"] = ("PARTY",)
    config.attribute_navigation = {"Names": ("* Name",)}
    assert _navigation_paths("Customer Name", ["TEXT"], config) == [
        ["Parties", "Customer Attributes"]
    ]
    config.attribute_navigation = {"Names": ("Name *",)}
    assert _navigation_paths("Name Customer", ["TEXT"], config) == [
        ["Parties", "Customer Attributes"]
    ]
    config.container_patterns = ("* List", "* Collection")
    config.semantic_family_order = ("TIME", "DATE", "AMOUNT")
    assert _navigation_paths("Payment Date List", ["TEXT"], config) == [
        ["Temporal", "Date"]
    ]
    config.subjects = ("Customer",)
    config.navigation_types["Parties"] = ("PARTY",)
    config.attribute_navigation = {"Names": ("* Name",)}
    assert _navigation_paths("Customer Name List", ["TEXT"], config) == [
        ["Parties", "Customer Attributes"]
    ]
    config.attribute_navigation = {"Names": ("Name *",)}
    assert _navigation_paths("Name Customer Collection", ["TEXT"], config) == [
        ["Parties", "Customer Attributes"]
    ]


def test_missing_navigation_options_keep_backward_compatible_defaults():
    config = SimpleNamespace(
        navigation_terms={},
        family_labels={},
        navigation_types={},
        subjects=(),
        events=(),
        objects=(),
        attribute_navigation=None,
        container_patterns=None,
    )

    assert _navigation_paths("合约编号", ["TEXT"], config) == [
        ["字段属性", "标识"]
    ]
    assert _navigation_paths("交易日期列表", ["TEXT"], config) == [
        ["日期时间", "日期"]
    ]


def test_explicit_empty_attribute_navigation_disables_default_rules():
    config = SimpleNamespace(
        navigation_terms={},
        family_labels={},
        navigation_types={},
        subjects=(),
        events=(),
        objects=(),
        attribute_navigation={},
    )

    assert _navigation_paths("Contract ID", ["TEXT"], config) == [["待归类"]]
