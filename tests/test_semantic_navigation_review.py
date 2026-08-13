from __future__ import annotations

import hashlib
import json
from pathlib import Path

from titans_cognition.cli import main
from titans_cognition.semantic_navigation_review import (
    build_semantic_navigation_review,
)


ROOT = Path(__file__).parents[1]
CONFIG = ROOT / "cases/tradeflow/reusable-semantic-navigation.yaml"


def _jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "source" / "context-enriched-field-semantic-map"
    _jsonl(
        source / "business_concepts.jsonl",
        [
            {
                "business_concept_id": "concept:notional",
                "label": "名义本金",
                "status": "CANDIDATE",
                "support_status": "SUPPORTED",
                "source_concept_ids": ["source:notional"],
                "source_labels": ["名义本金"],
            },
            {
                "business_concept_id": "concept:unattached",
                "label": "无法识别概念",
                "status": "CANDIDATE",
                "support_status": "PROVISIONAL",
                "source_concept_ids": ["source:unknown"],
                "source_labels": ["无法识别概念"],
            },
            *[
                {
                    "business_concept_id": f"concept:{key}",
                    "label": label,
                    "status": "CANDIDATE",
                    "support_status": "SUPPORTED",
                    "source_concept_ids": [f"source:{key}"],
                    "source_labels": [label],
                }
                for key, label in (
                    ("counterparty", "交易对手"),
                    ("trade", "交易"),
                    ("order", "订单编号"),
                    ("position", "持仓"),
                    ("position-quantity", "持仓数量"),
                    ("margin", "保证金"),
                )
            ],
        ],
    )
    _jsonl(
        source / "attribute_expressions.jsonl",
        [
            {
                "attribute_expression_id": "expression:dynamic-local",
                "business_concept_id": "concept:notional",
                "label": "动态名义本金（本币）",
                "field_count": 1,
                "object_count": 1,
                "qualifier_signature": [
                    {"dimension": "variability", "value": "DYNAMIC"},
                    {"dimension": "position_side", "value": "LONG"},
                    {"dimension": "currency_basis", "value": "LOCAL_CURRENCY"},
                ],
                "status": "CANDIDATE",
                "support_status": "SUPPORTED",
                "source_concept_ids": ["source:notional"],
                "conflicts": [],
                "uncertainties": [],
            },
            {
                "attribute_expression_id": "expression:unknown",
                "business_concept_id": "concept:unattached",
                "label": "无法识别概念",
                "field_count": 1,
                "object_count": 1,
                "qualifier_signature": [],
                "status": "CANDIDATE",
                "support_status": "PROVISIONAL",
                "source_concept_ids": ["source:unknown"],
                "conflicts": [],
                "uncertainties": ["UNKNOWN_SEMANTICS"],
            },
            *[
                {
                    "attribute_expression_id": f"expression:{key}",
                    "business_concept_id": f"concept:{key}",
                    "label": expression_label,
                    "field_count": 1,
                    "object_count": 1,
                    "qualifier_signature": qualifiers,
                    "status": "CANDIDATE",
                    "support_status": "SUPPORTED",
                    "source_concept_ids": [f"source:{key}"],
                    "conflicts": [],
                    "uncertainties": [],
                }
                for key, expression_label, qualifiers in (
                    ("counterparty", "交易对手ID", [{"dimension": "attribute_kind", "value": "IDENTIFIER"}]),
                    ("trade", "交易ID", [{"dimension": "lifecycle_stage", "value": "EXECUTION"}]),
                    ("order", "订单ID", [{"dimension": "lifecycle_stage", "value": "ORDER"}]),
                    ("position", "持仓ID", [{"dimension": "attribute_kind", "value": "IDENTIFIER"}]),
                    ("position-quantity", "持仓数量", []),
                    ("margin", "初始保证金", [{"dimension": "temporal_stage", "value": "INITIAL"}]),
                )
            ],
        ],
    )
    _jsonl(
        source / "business_contexts.jsonl",
        [
            {
                "business_context_id": "context:trs",
                "label": "TRS",
                "context_type": "PRODUCT",
                "status": "CANDIDATE",
            }
        ],
    )
    _jsonl(source / "assertions.jsonl", [])
    _jsonl(source / "evidence_refs.jsonl", [])
    _jsonl(
        source / "semantic_hypotheses.jsonl",
        [
            {"status": "INSUFFICIENT_EVIDENCE"},
            {"status": "CONFLICT"},
        ],
    )
    _jsonl(
        source / "diagnostics/data_semantic_candidates.jsonl",
        [
            {
                "attribute_expression_id": "expression:dynamic-local",
                "context_ids": ["context:trs"],
                "physical_instances": [
                    {
                        "schema_name": "TITANS_TRADEFLOW",
                        "object_name": "REF_TRS",
                        "column_name": "DYNAMIC_NOTIONAL",
                        "column_comment": "动态名义本金（本币）",
                        "column_id": "column:dynamic-notional",
                    }
                ],
            },
            {
                "attribute_expression_id": "expression:unknown",
                "context_ids": [],
                "physical_instances": [
                    {
                        "schema_name": "TITANS_TRADEFLOW",
                        "object_name": "UNKNOWN_TABLE",
                        "column_name": "MYSTERY_VALUE",
                        "column_comment": None,
                        "column_id": "column:mystery",
                    }
                ],
            },
            *[
                {
                    "attribute_expression_id": f"expression:{key}",
                    "context_ids": [],
                    "physical_instances": [
                        {
                            "schema_name": "TITANS_TRADEFLOW",
                            "object_name": f"{key.upper()}_TABLE",
                            "column_name": column,
                            "column_comment": label,
                            "column_id": f"column:{key}",
                        }
                    ],
                }
                for key, column, label in (
                    ("counterparty", "KEY_CTPTY_ID", "交易对手ID"),
                    ("trade", "TRADE_ID", "交易ID"),
                    ("order", "ORDER_ID", "订单ID"),
                    ("position", "POSITION_ID", "持仓ID"),
                    ("position-quantity", "POSITION_QTY", "持仓数量"),
                    ("margin", "INITIAL_MARGIN", "初始保证金"),
                )
            ],
        ],
    )
    _jsonl(
        source / "diagnostics/semantic_review_queue.jsonl",
        [
            {"reason": "RECURRENT_CORE_WITH_UNTYPED_MODIFIER"},
            {
                "review_type": "SAME_PHYSICAL_NAME_DIFFERENT_COMMENT",
                "physical_name": "SAME_NAME",
                "comment_variants": [
                    {"comment": "含义一", "source_refs": ["column:one"]},
                    {"comment": "含义二", "source_refs": ["column:two"]},
                ],
                "method_id": "semantic_cleaning.corpus_recurrence.v1",
                "status": "NEEDS_REVIEW",
            },
        ],
    )
    (source / "manifest.json").write_text("{}\n", encoding="utf-8")
    old_page = source / "review" / "index.html"
    old_page.parent.mkdir(parents=True)
    old_page.write_text("OLD PAGE MUST REMAIN", encoding="utf-8")
    return source


def _catalog(path: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
    text = path.read_text(encoding="utf-8")
    projection_text, catalog_text = text.split(
        ";\nwindow.SEMANTIC_NAV_CATALOG=", 1
    )
    projection = json.loads(
        projection_text.removeprefix("window.SEMANTIC_NAV_PROJECTION=")
    )
    catalog = json.loads(catalog_text.rsplit(";", 1)[0])
    return projection, catalog


def test_target_page_consumes_real_projection_and_preserves_old_page(tmp_path: Path):
    source = _source(tmp_path)
    old_hash = hashlib.sha256((source / "review/index.html").read_bytes()).hexdigest()

    paths = build_semantic_navigation_review(source, CONFIG, tmp_path / "out")

    html = paths["review_index"].read_text(encoding="utf-8")
    projection, catalog = _catalog(paths["projection"])
    shard = (
        paths["review_index"].parent
        / "data/concepts"
        / next(row["shard"] for row in catalog if row["id"] == "reader:notional")
    ).read_text(encoding="utf-8")
    assert "OTC 业务主线" in html
    assert "① 业务地图" in html
    assert "② 语义索引" in html
    assert "③ 语义详情" in html
    assert "语义治理队列" in html
    assert len(projection["stages"]) == 6
    assert projection["sourceKind"] == "CURRENT_RUN_PROJECTION"
    assert any(row["label"] == "名义本金" for row in catalog)
    assert "DYNAMIC_NOTIONAL" in shard
    assert "动态名义本金（本币）" in shard
    assert "正式业务定义仍需业务审阅" in shard
    assert "CONFIGURATION_SEED｜非证据" in html
    assert "属性表达矩阵" in html
    assert ".technical-name{text-transform:lowercase}" in html
    assert "function physicalGroup(g)" in html
    assert all(label in html for label in ("表注释", "字段注释", "表详情", "目标缺失"))
    assert "e.physical.slice" not in html
    assert '"physicalGroups"' in shard
    assert '"physical":' not in shard
    assert "变化方式" in shard
    assert "持仓方向" in shard
    assert "币种基准" not in shard
    assert "变化形态" not in shard
    assert hashlib.sha256((source / "review/index.html").read_bytes()).hexdigest() == old_hash
    by_label = {row["label"]: row for row in catalog}
    assert set(by_label) == {"名义本金", "交易对手", "交易 / 订单", "持仓", "保证金"}
    assert by_label["交易对手"]["stageIds"] == ["trade-preparation"]
    assert by_label["交易 / 订单"]["stageIds"] == ["trade-agreement"]
    assert by_label["持仓"]["expressionCount"] == 2
    assert by_label["保证金"]["stageIds"] == ["valuation-risk"]
    shards = sorted((paths["review_index"].parent / "data/concepts").glob("*.js"))
    assert len(shards) == 5
    for row in catalog:
        assert f'<script src="data/concepts/{row["shard"]}"></script>' in html
    assert "document.createElement('script')" not in html
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    assert manifest["config_sha256"]
    assert manifest["panorama_root"].endswith("panorama")
    assert manifest["panorama_objects_sha256"]
    assert len([row for row in manifest["outputs"] if "/concepts/" in row["relative_path"]]) == 5


def test_unattached_concept_is_visible_in_governance_queue(tmp_path: Path):
    source = _source(tmp_path)
    paths = build_semantic_navigation_review(source, CONFIG, tmp_path / "out")

    projection, catalog = _catalog(paths["projection"])
    queue = {row["reason"]: row["count"] for row in projection["governanceQueue"]}
    assert all(row["id"] != "concept:unattached" for row in catalog)
    assert queue["NAVIGATION_CANDIDATE_NOT_PUBLISHED"] == 1
    assert queue["INSUFFICIENT_EVIDENCE"] == 1
    assert queue["CONFLICT"] == 1
    same_name = next(
        row
        for row in projection["governanceQueue"]
        if row["reason"] == "SAME_PHYSICAL_NAME_DIFFERENT_COMMENT"
    )
    assert same_name["items"][0]["label"] == "SAME_NAME"
    assert same_name["items"][0]["sourceRefs"] == ["column:one", "column:two"]


def test_projection_replay_is_content_equivalent(tmp_path: Path):
    source = _source(tmp_path)
    first = build_semantic_navigation_review(source, CONFIG, tmp_path / "first")
    second = build_semantic_navigation_review(source, CONFIG, tmp_path / "second")

    assert first["review_index"].read_bytes() == second["review_index"].read_bytes()
    assert first["projection"].read_bytes() == second["projection"].read_bytes()
    first_shards = sorted((first["review_index"].parent / "data/concepts").glob("*.js"))
    second_shards = sorted((second["review_index"].parent / "data/concepts").glob("*.js"))
    assert [path.read_bytes() for path in first_shards] == [
        path.read_bytes() for path in second_shards
    ]


def test_cli_builds_independent_semantic_navigation_review(tmp_path: Path, capsys):
    source = _source(tmp_path)
    output = tmp_path / "cli-output"

    assert main(
        [
            "build-semantic-navigation-review",
            "--source",
            str(source),
            "--config",
            str(CONFIG),
            "--output",
            str(output),
        ]
    ) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["concept_count"] == 5
    assert result["expression_count"] == 7
    assert Path(result["review_index"]).is_file()
    assert (source / "review/index.html").read_text(encoding="utf-8") == "OLD PAGE MUST REMAIN"
