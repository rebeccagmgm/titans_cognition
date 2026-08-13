import hashlib
import json
from pathlib import Path

import pytest

from titans_cognition.cli import main
from titans_cognition.context_semantics import (
    load_context_map_config,
    normalize_title,
    parse_wiki_tree,
    run_context_map,
    validate_context_map,
    write_context_map_results,
    _clean_expression_label,
    _column_comment_consensus,
    _consolidate_assertions,
    _observed_field_expression_label,
    _partition_facet_signature,
    _normalize_qualifier_axis,
    _remove_redundant_qualifiers,
    _semantic_label_compatible,
)


AXIS_MAPPINGS = {
    "party_role": {"SOURCE": "flow_side", "TARGET": "flow_side"},
    "measure_state": {
        "DYNAMIC": "variability",
        "AVAILABLE": "availability_state",
    },
    "direction": {
        "LONG": "position_side",
        "BUY": "trade_side",
        "PAY": "cashflow_direction",
    },
}


def test_direct_source_expression_wins_over_inherited_same_name_comment():
    label, provenance = _observed_field_expression_label(
        "名义本金",
        {
            "column_id": "target",
            "semantic_comment": "初始名义本金",
        },
        {"source_refs": ["target"]},
        {"target": [{"original_text": "动态名义本金"}]},
    )

    assert (label, provenance) == ("动态名义本金", "SOURCE_EXPRESSION")


def test_duplicate_assertion_support_is_consolidated_without_losing_evidence():
    base = {
        "assertion_id": "a",
        "subject_id": "s",
        "predicate": "RELATED_TO",
        "object_id": "o",
        "status": "CANDIDATE",
        "method_id": "m",
        "counterevidence_refs": [],
        "review_status": "UNREVIEWED",
    }
    assertions, relations = _consolidate_assertions(
        [
            {**base, "method_score": 0.4, "evidence_refs": ["e1"]},
            {**base, "method_score": 0.8, "evidence_refs": ["e2"]},
        ],
        [
            {
                "relation_id": "r",
                "subject_id": "s",
                "predicate": "RELATED_TO",
                "object_id": "o",
            },
            {
                "relation_id": "r",
                "subject_id": "s",
                "predicate": "RELATED_TO",
                "object_id": "o",
            },
        ],
    )

    assert assertions[0]["evidence_refs"] == ["e1", "e2"]
    assert assertions[0]["method_score"] == 0.8
    assert len(relations) == 1


def test_duplicate_assertion_status_keeps_the_stronger_conflict():
    base = {
        "assertion_id": "a",
        "subject_id": "s",
        "predicate": "QUALIFIED_BY",
        "object_id": "q",
        "method_id": "m",
        "method_score": 1.0,
        "evidence_refs": [],
        "review_status": "UNREVIEWED",
    }
    assertions, _ = _consolidate_assertions(
        [
            {**base, "status": "CANDIDATE", "counterevidence_refs": []},
            {**base, "status": "CONFLICT", "counterevidence_refs": ["e1"]},
        ],
        [],
    )

    assert assertions[0]["status"] == "CONFLICT"
    assert assertions[0]["counterevidence_refs"] == ["e1"]


def test_failed_review_generation_does_not_publish_bundle(tmp_path, monkeypatch):
    config_path, _, _ = _fixture(tmp_path / "fixture")
    config = load_context_map_config(config_path)
    result = run_context_map(config)
    output = tmp_path / "out"

    def fail_review(*_args, **_kwargs):
        raise RuntimeError("review generation failed")

    monkeypatch.setattr(
        "titans_cognition.context_review.write_review_projection", fail_review
    )
    with pytest.raises(RuntimeError, match="review generation failed"):
        write_context_map_results(output, result, config)

    assert not (output / "context-enriched-field-semantic-map").exists()


def _jsonl(path: Path, rows):
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _fixture(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    v2 = tmp_path / "v2"
    v2.mkdir()
    concepts = [
        {
            "concept_id": "c-notional",
            "label": "名义本金",
            "support_status": "SUPPORTED",
            "semantic_scope": "DOMAIN",
            "value_kinds": ["NUMBER"],
        },
        {
            "concept_id": "c-date",
            "label": "成交日期",
            "support_status": "SUPPORTED",
            "semantic_scope": "DOMAIN",
            "value_kinds": ["DATE"],
        },
    ]
    expressions = [
        {
            "concept_id": "c-notional",
            "original_text": "名义本金",
            "source_ref": "col:notional",
        },
        {
            "concept_id": "c-notional",
            "original_text": "动态名义本金",
            "source_ref": "col:dynamic",
        },
        {
            "concept_id": "c-notional",
            "original_text": "多头动态名义本金",
            "source_ref": "col:long",
        },
        {"concept_id": "c-date", "original_text": "成交日期", "source_ref": "col:date"},
    ]
    fields = []
    for column_id, name, comment, concept_id, binding_id, obj in [
        ("col:notional", "NOTIONAL", "名义本金", "c-notional", "b0", "TRD_SUMMARY"),
        (
            "col:dynamic",
            "DYNAMIC_NOTIONAL",
            "动态名义本金",
            "c-notional",
            "b1",
            "REF_TRS",
        ),
        (
            "col:long",
            "LONG_DYNAMIC_NOTIONAL",
            "多头动态名义本金",
            "c-notional",
            "b2",
            "REF_TRS",
        ),
        ("col:date", "TRADE_DATE", "成交日期", "c-date", "b3", "TRD_SUMMARY"),
    ]:
        fields.append(
            {
                "column_id": column_id,
                "asset_id": f"asset:{obj}",
                "schema_name": "ALPHA",
                "object_name": obj,
                "column_name": name,
                "column_comment": comment,
                "candidate_bindings": [
                    {
                        "binding_id": binding_id,
                        "concept_id": concept_id,
                        "relation_kind": "EXPRESSES",
                        "source_refs": [column_id],
                    }
                ],
                "outcome": "SINGLE_CANDIDATE",
            }
        )
    facets = [
        {"binding_id": "b1", "dimension": "measure_state", "value": "DYNAMIC"},
        {"binding_id": "b2", "dimension": "measure_state", "value": "DYNAMIC"},
        {"binding_id": "b2", "dimension": "direction", "value": "LONG"},
        {
            "binding_id": "b2",
            "dimension": "direction",
            "value": "SHORT",
            "raw_fragment": "SHORT",
            "source_ref": "col:long",
        },
        {
            "binding_id": "b2",
            "dimension": "direction",
            "value": "LONG",
            "raw_fragment": "多头",
            "source_ref": "col:long",
        },
    ]
    _jsonl(v2 / "base_concepts.jsonl", concepts)
    _jsonl(v2 / "concept_expressions.jsonl", expressions)
    _jsonl(v2 / "field_semantic_results.jsonl", fields)
    _jsonl(v2 / "field_facets.jsonl", facets)
    (v2 / "manifest.json").write_text(
        json.dumps({"stats": {"field_count": 4}}), encoding="utf-8"
    )

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    tree_rows = [
        {"pageId": "1", "parentPageId": None, "title": "Home", "depth": 0},
        {"pageId": "2", "parentPageId": "1", "title": "6\\. 系统测试", "depth": 1},
        {"pageId": "3", "parentPageId": "2", "title": "TRS验收指引", "depth": 2},
        {
            "pageId": "4",
            "parentPageId": "3",
            "title": "TRS动态名义本金列表验收指引",
            "depth": 3,
        },
        {
            "pageId": "4",
            "parentPageId": "3",
            "title": "TRS动态名义本金列表验收指引",
            "depth": 3,
        },
        {
            "pageId": "5",
            "parentPageId": "missing",
            "title": "2026-08-11 ZYTGXT-12345 期权合约终止方案",
            "depth": 3,
        },
    ]
    _jsonl(wiki / "tree.jsonl", tree_rows)
    (wiki / "manifest.json").write_text(
        json.dumps({"snapshotId": "snap-1", "errorCount": 1}), encoding="utf-8"
    )

    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    config = tmp_path / "config.yaml"
    config.write_text(
        f"""
version: v1
inputs:
  field_semantics_dir: {v2.as_posix()}
  field_semantics_manifest_sha256: {digest(v2 / "manifest.json")}
  wiki_tree_dir: {wiki.as_posix()}
  wiki_manifest_sha256: {digest(wiki / "manifest.json")}
  wiki_tree_sha256: {digest(wiki / "tree.jsonl")}
  panorama_root: {tmp_path.as_posix()}/panorama
limits:
  max_wiki_candidates_per_expression: 5
  max_wiki_candidates_per_concept: 10
  max_page_body_reads: 0
  review_page_size: 20
  initial_navigation_limit: 100
qualifier_axes:
  version: fixture-v1
  mappings:
    party_role: {{SOURCE: flow_side, TARGET: flow_side}}
    direction: {{LONG: position_side, SHORT: position_side, BUY: trade_side, SELL: trade_side, PAY: cashflow_direction, RECEIVE: cashflow_direction}}
    measure_state: {{DYNAMIC: variability, FIXED: variability, AVAILABLE: availability_state, FROZEN: availability_state, ESTIMATED: estimation_status, ACCUMULATED: aggregation_state}}
wiki_semantics:
  document_contexts: {{TEST: [测试, 验收], DESIGN: [方案, 设计]}}
  products: {{TRS: [TRS], OPTION: [期权]}}
  objects: [合约, 交易, 持仓]
  events: [成交, 终止, 重置]
  processes: [簿记, 估值]
  subjects: [客户, 交易对手]
  rules: [规则, 校验]
navigation:
  concept_types: {{业务度量: [AMOUNT], 业务对象: [OBJECT]}}
  family_labels: {{AMOUNT: 金额}}
""",
        encoding="utf-8",
    )
    return config, v2, wiki


def test_navigation_config_rejects_unbounded_wildcards_and_bad_templates(tmp_path):
    config_path, _, _ = _fixture(tmp_path)
    source = config_path.read_text(encoding="utf-8")

    config_path.write_text(
        source.replace(
            "  family_labels: {AMOUNT: 金额}",
            "  family_labels: {AMOUNT: 金额}\n  attribute_types: {标识: ['**']}",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="empty wildcard"):
        load_context_map_config(config_path)

    config_path.write_text(
        source.replace(
            "  family_labels: {AMOUNT: 金额}",
            "  family_labels: {AMOUNT: 金额}\n  entity_attribute_template: '{missing}属性'",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"must contain only \{entity\} exactly once"):
        load_context_map_config(config_path)

    config_path.write_text(
        source.replace(
            "  family_labels: {AMOUNT: 金额}",
            "  family_labels: {AMOUNT: 金额}\n  container_patterns: ['*']",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="container_patterns contains an empty wildcard"):
        load_context_map_config(config_path)


def test_navigation_config_preserves_explicit_empty_attribute_types(tmp_path):
    config_path, _, _ = _fixture(tmp_path)
    source = config_path.read_text(encoding="utf-8")
    config_path.write_text(
        source.replace(
            "  family_labels: {AMOUNT: 金额}",
            "  family_labels: {AMOUNT: 金额}\n  attribute_types: {}",
        ),
        encoding="utf-8",
    )

    assert load_context_map_config(config_path).attribute_navigation == {}


def test_navigation_config_distinguishes_missing_from_explicit_empty(tmp_path):
    config_path, _, _ = _fixture(tmp_path)
    config = load_context_map_config(config_path)

    assert config.attribute_navigation is None
    assert config.container_patterns is None


def test_tree_parser_retains_source_and_reports_boundaries(tmp_path):
    _, _, wiki = _fixture(tmp_path)
    rows, diagnostics = parse_wiki_tree(wiki / "tree.jsonl")
    assert len(rows) == 5
    assert any(
        row["ancestor_path"] == ["Home", "6\\. 系统测试", "TRS验收指引"]
        for row in rows
        if row["page_id"] == "4"
    )
    assert (
        normalize_title("2026-08-11 ZYTGXT-12345 期权合约终止方案")
        == "期权合约终止方案"
    )
    assert {row["code"] for row in diagnostics} >= {
        "DUPLICATE_IDENTICAL_NODE",
        "MISSING_PARENT",
    }


def test_tree_parser_retains_valid_json_shape_and_depth_errors(tmp_path):
    tree = tmp_path / "tree.jsonl"
    tree.write_text(
        '[1, 2]\n{"pageId":"x","title":"bad depth","depth":"many"}\n',
        encoding="utf-8",
    )

    rows, diagnostics = parse_wiki_tree(tree)

    assert rows == []
    assert [row["code"] for row in diagnostics] == ["INVALID_NODE", "INVALID_NODE"]


def test_projection_materializes_observed_expressions_and_reuses_context(tmp_path):
    config_path, _, _ = _fixture(tmp_path)
    result = run_context_map(load_context_map_config(config_path))
    labels = {row["label"] for row in result.attribute_expressions}
    assert {"名义本金", "动态名义本金"} <= labels
    assert "多头动态名义本金" not in labels
    assert "初始多头名义本金" not in labels
    long_hypothesis = next(
        row
        for row in result.semantic_hypotheses
        if row["label"] == "多头动态名义本金"
    )
    assert long_hypothesis["publication_status"] == "NOT_PUBLISHED"
    assert long_hypothesis["status"] == "CONFLICT"
    assert long_hypothesis["conflicts"][0]["reason"] == "COMMENT_NAME_DISAGREEMENT"
    assert any(row["predicate"] == "EXPRESSION_OF" for row in result.assertions)
    assert any(
        row["predicate"] == "APPEARS_IN"
        and row["object_id"]
        == next(
            x["business_context_id"]
            for x in result.business_contexts
            if x["context_type"] == "UNKNOWN"
        )
        for row in result.assertions
    )
    assert result.quality_gate["status"] == "PASS"


def test_context_is_not_published_as_hierarchy_and_score_is_governance(tmp_path):
    config_path, _, _ = _fixture(tmp_path)
    result = run_context_map(load_context_map_config(config_path))
    assert not any(
        row["predicate"] in {"BROADER", "NARROWER"} for row in result.assertions
    )
    assert all(row["review_status"] == "UNREVIEWED" for row in result.assertions)
    assert any(row["method_score"] is not None for row in result.assertions)


def test_validation_rejects_invalid_relation_endpoints(tmp_path):
    config_path, _, _ = _fixture(tmp_path)
    result = run_context_map(load_context_map_config(config_path))
    relation = next(
        row for row in result.assertions if row["predicate"] == "EXPRESSION_OF"
    )
    relation["object_id"] = result.business_contexts[0]["business_context_id"]
    with pytest.raises(ValueError, match="invalid endpoints"):
        validate_context_map(result)


def test_hash_drift_and_output_write_protection(tmp_path):
    config_path, v2, wiki = _fixture(tmp_path)
    config = load_context_map_config(config_path)
    (wiki / "tree.jsonl").write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="input hash drift"):
        run_context_map(config)


def test_cli_writes_independent_bundle(tmp_path, capsys):
    config_path, v2, wiki = _fixture(tmp_path)
    output = tmp_path / "out"
    assert (
        main(
            [
                "build-context-semantic-map",
                "--config",
                str(config_path),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    root = output / "context-enriched-field-semantic-map"
    assert payload["model_gate"] == "PASS"
    assert (root / "semantic_observations.jsonl").exists()
    assert (root / "semantic_hypotheses.jsonl").exists()
    assert (root / "review_decisions.jsonl").exists()
    assert (root / "attribute_expressions.jsonl").exists()
    assert (root / "review" / "investigation-card.md").exists()
    assert (root / "review" / "index.html").exists()
    assert (root / "review" / "data" / "catalog.js").exists()
    assert not (v2 / "context-enriched-field-semantic-map").exists()
    assert not (wiki / "context-enriched-field-semantic-map").exists()


def test_review_projection_is_sharded_and_field_primary(tmp_path, capsys):
    config_path, _, _ = _fixture(tmp_path)
    output = tmp_path / "out"
    assert (
        main(
            [
                "build-context-semantic-map",
                "--config",
                str(config_path),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    capsys.readouterr()
    review = output / "context-enriched-field-semantic-map" / "review"
    html = (review / "index.html").read_text(encoding="utf-8")
    catalog = (review / "data" / "catalog.js").read_text(encoding="utf-8")
    assert "字段发现为主" in html
    assert "data/concepts/${id}.js" in html
    assert "setTimeout(renderNav,180)" in html
    assert "physicalGroups" not in catalog
    assert len(list((review / "data" / "concepts").glob("*.js"))) == 2


def test_distinct_observed_labels_are_not_merged(tmp_path):
    config_path, v2, _ = _fixture(tmp_path)
    fields_path = v2 / "field_semantic_results.jsonl"
    fields = [
        json.loads(line)
        for line in fields_path.read_text(encoding="utf-8").splitlines()
    ]
    copied = dict(fields[0])
    copied.update(
        {
            "column_id": "col:absolute",
            "column_name": "ABS_NOTIONAL",
            "column_comment": "绝对名义本金",
            "asset_id": "asset:ABS_TABLE",
            "object_name": "ABS_TABLE",
            "candidate_bindings": [
                {
                    "binding_id": "b-absolute",
                    "concept_id": "c-notional",
                    "relation_kind": "EXPRESSES",
                    "source_refs": ["col:absolute"],
                }
            ],
        }
    )
    _jsonl(fields_path, [*fields, copied])
    manifest = v2 / "manifest.json"
    manifest.write_text(json.dumps({"stats": {"field_count": 5}}), encoding="utf-8")
    raw = config_path.read_text(encoding="utf-8")
    old_hash = hashlib.sha256(
        json.dumps({"stats": {"field_count": 4}}).encode()
    ).hexdigest()
    new_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
    config_path.write_text(raw.replace(old_hash, new_hash), encoding="utf-8")
    result = run_context_map(load_context_map_config(config_path))
    labels = {row["label"] for row in result.attribute_expressions}
    assert "名义本金" in labels
    assert "绝对名义本金" in labels
    by_label = {row["label"]: row for row in result.attribute_expressions}
    assert by_label["绝对名义本金"]["qualifier_signature"] == [
        {"dimension": "measure_basis", "value": "ABSOLUTE"}
    ]


@pytest.mark.parametrize(
    "source",
    ["交易对手 ID", "交易对手ID", "交易对手Id", "交易对手id"],
)
def test_identifier_suffix_variants_share_one_display_label(source):
    assert _clean_expression_label(source) == "交易对手ID"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("o32账号", "O32账号"),
        ("wind代码", "WIND代码"),
        ("交易市场：字典exchange", "交易市场：字典EXCHANGE"),
    ],
)
def test_latin_acronyms_use_one_display_case(source, expected):
    assert _clean_expression_label(source) == expected


def test_same_name_comment_consensus_fills_semantics_without_overwriting_source():
    fields = [
        {
            "column_id": "col:annotated",
            "column_name": "INITIAL_NOTIONAL",
            "column_comment": "初始名义本金",
            "candidate_bindings": [
                {"concept_id": "c-notional", "relation_kind": "EXPRESSES"}
            ],
        },
        {
            "column_id": "col:missing",
            "column_name": "initial_notional",
            "column_comment": None,
            "candidate_bindings": [
                {"concept_id": "c-notional", "relation_kind": "EXPRESSES"}
            ],
        },
    ]

    consensus = _column_comment_consensus(fields)

    assert consensus[("INITIAL_NOTIONAL", "c-notional", ())] == {
        "label": "初始名义本金",
        "source_refs": ["col:annotated"],
    }
    assert fields[1]["column_comment"] is None


def test_same_name_comment_consensus_rejects_conflicting_annotations():
    fields = [
        {
            "column_id": "col:a",
            "column_name": "AMOUNT",
            "column_comment": "成交金额",
            "candidate_bindings": [
                {"concept_id": "c-amount", "relation_kind": "EXPRESSES"}
            ],
        },
        {
            "column_id": "col:b",
            "column_name": "amount",
            "column_comment": "费用金额",
            "candidate_bindings": [
                {"concept_id": "c-amount", "relation_kind": "EXPRESSES"}
            ],
        },
    ]

    assert ("AMOUNT", "c-amount", ()) not in _column_comment_consensus(fields)


def test_comment_consensus_keeps_parenthetical_business_qualifiers_distinct():
    fields = [
        {
            "column_id": "col:local",
            "column_name": "NOTIONAL",
            "column_comment": "名义本金（本币）",
            "candidate_bindings": [
                {"concept_id": "c-notional", "relation_kind": "EXPRESSES"}
            ],
        },
        {
            "column_id": "col:original",
            "column_name": "NOTIONAL",
            "column_comment": "名义本金（原币）",
            "candidate_bindings": [
                {"concept_id": "c-notional", "relation_kind": "EXPRESSES"}
            ],
        },
    ]

    assert not _column_comment_consensus(fields)


def test_incidental_lifecycle_context_does_not_split_same_attribute():
    identity, contextual = _partition_facet_signature(
        "对手方对冲账户",
        "TARGET_HMS_ACCOUNT_ID",
        (("lifecycle_stage", "EXECUTION"), ("party_role", "TARGET")),
    )

    assert identity == (("party_role", "TARGET"),)
    assert contextual == (("lifecycle_stage", "EXECUTION"),)


def test_orthogonal_party_and_measure_axes_are_not_conflated():
    assert _normalize_qualifier_axis(
        "party_role", "TARGET", axis_mappings=AXIS_MAPPINGS
    ) == (
        "flow_side",
        "TARGET",
    )
    assert _normalize_qualifier_axis(
        "party_role", "COUNTERPARTY", axis_mappings=AXIS_MAPPINGS
    ) == (
        "party_role",
        "COUNTERPARTY",
    )
    assert _normalize_qualifier_axis(
        "measure_state", "DYNAMIC", axis_mappings=AXIS_MAPPINGS
    ) == (
        "variability",
        "DYNAMIC",
    )
    assert _normalize_qualifier_axis(
        "measure_state", "AVAILABLE", axis_mappings=AXIS_MAPPINGS
    ) == (
        "availability_state",
        "AVAILABLE",
    )
    assert _normalize_qualifier_axis(
        "direction", "LONG", axis_mappings=AXIS_MAPPINGS
    ) == (
        "position_side",
        "LONG",
    )
    assert _normalize_qualifier_axis(
        "direction", "BUY", axis_mappings=AXIS_MAPPINGS
    ) == (
        "trade_side",
        "BUY",
    )
    assert _normalize_qualifier_axis(
        "direction", "PAY", axis_mappings=AXIS_MAPPINGS
    ) == (
        "cashflow_direction",
        "PAY",
    )
    assert _remove_redundant_qualifiers(
        "交易对手",
        "交易对手",
        (("party_role", "COUNTERPARTY"),),
    ) == ()
    assert _remove_redundant_qualifiers(
        "合约内部",
        "合约内部ID",
        (
            ("attribute_kind", "IDENTIFIER"),
            ("party_role", "INTERNAL"),
        ),
    ) == (("attribute_kind", "IDENTIFIER"),)
    assert _semantic_label_compatible("业务方案编号", "业务方案ID")
    assert _semantic_label_compatible("交易对手", "交易对手ID", identifier=True)
    assert not _semantic_label_compatible("金额", "金额币种")
    assert not _semantic_label_compatible("名义本金", "名义本金币种")
    assert not _semantic_label_compatible("交易日期", "非交易日期")
    assert not _semantic_label_compatible("客户", "客户经理")
    assert not _semantic_label_compatible("交易金额", "金额")


def test_unreviewed_corpus_modifiers_are_not_published_as_qualifiers(tmp_path):
    config_path, v2, _ = _fixture(tmp_path)
    concepts_path = v2 / "base_concepts.jsonl"
    concepts = [
        json.loads(line)
        for line in concepts_path.read_text(encoding="utf-8").splitlines()
    ]
    concepts.extend(
        {
            "concept_id": f"c-party-{index}",
            "label": label,
            "support_status": "PROVISIONAL",
            "semantic_scope": "DOMAIN",
            "value_kinds": ["TEXT"],
        }
        for index, label in enumerate(
            ["交易对手", "源侧交易对手", "目标交易对手"], start=1
        )
    )
    _jsonl(concepts_path, concepts)

    result = run_context_map(load_context_map_config(config_path))

    assert not any(
        row["dimension"] == "semantic_modifier" for row in result.qualifiers
    )
    assert any(
        row.get("review_type") == "QUALIFIED_VARIANT"
        and row.get("source_label") == "源侧交易对手"
        for row in result.semantic_review_queue
    )


def test_multi_concept_physical_binding_is_exposed_as_conflict(tmp_path):
    config_path, v2, _ = _fixture(tmp_path)
    fields_path = v2 / "field_semantic_results.jsonl"
    fields = [
        json.loads(line)
        for line in fields_path.read_text(encoding="utf-8").splitlines()
    ]
    fields[0]["candidate_bindings"].append(
        {
            "binding_id": "b-cross-concept",
            "concept_id": "c-date",
            "relation_kind": "EXPRESSES",
            "source_refs": ["col:notional"],
        }
    )
    _jsonl(fields_path, fields)

    result = run_context_map(load_context_map_config(config_path))
    affected = [
        row
        for row in result.semantic_hypotheses
        if "col:notional" in row["field_refs"]
    ]

    assert len(affected) == 2
    assert all(row["status"] == "CONFLICT" for row in affected)
    assert all(row["publication_status"] == "NOT_PUBLISHED" for row in affected)
    assert all(
        any(
            conflict.get("reason") == "MULTI_CONCEPT_PHYSICAL_COLUMN"
            for conflict in row["conflicts"]
        )
        for row in affected
    )
    assert not any(
        row["attribute_expression_id"]
        in {item["proposed_attribute_expression_id"] for item in affected}
        for row in result.attribute_expressions
    )


def test_chinese_expression_base_mismatch_is_exposed_as_conflict(tmp_path):
    config_path, v2, _ = _fixture(tmp_path)
    expressions_path = v2 / "concept_expressions.jsonl"
    expressions = [
        json.loads(line)
        for line in expressions_path.read_text(encoding="utf-8").splitlines()
    ]
    expressions.append(
        {
            "concept_id": "c-notional",
            "original_text": "结算币种",
            "source_ref": "col:mismatch",
        }
    )
    _jsonl(expressions_path, expressions)
    fields_path = v2 / "field_semantic_results.jsonl"
    fields = [
        json.loads(line)
        for line in fields_path.read_text(encoding="utf-8").splitlines()
    ]
    fields.append(
        {
            "column_id": "col:mismatch",
            "asset_id": "asset:REF_TRS",
            "schema_name": "ALPHA",
            "object_name": "REF_TRS",
            "column_name": "LONG_DYNAMIC_NOTIONAL_ORG",
            "column_comment": "结算币种",
            "candidate_bindings": [
                {
                    "binding_id": "b-mismatch",
                    "concept_id": "c-notional",
                    "relation_kind": "EXPRESSES",
                    "source_refs": ["col:mismatch"],
                }
            ],
            "outcome": "SINGLE_CANDIDATE",
        }
    )
    _jsonl(fields_path, fields)

    result = run_context_map(load_context_map_config(config_path))
    mismatch = next(
        row for row in result.semantic_hypotheses if row["label"] == "结算币种"
    )

    assert mismatch["status"] == "INSUFFICIENT_EVIDENCE"
    assert mismatch["publication_status"] == "NOT_PUBLISHED"
    assert any(
        item.get("reason") == "OBSERVED_LABEL_BASE_NOT_PROVEN"
        for item in mismatch["uncertainties"]
    )


def test_lexicalized_lifecycle_remains_expression_qualifier():
    identity, contextual = _partition_facet_signature(
        "成交金额",
        "TRADE_AMOUNT",
        (("lifecycle_stage", "EXECUTION"),),
        (
            {
                "dimension": "lifecycle_stage",
                "value": "EXECUTION",
                "raw_fragment": "成交",
            },
        ),
    )

    assert identity == (("lifecycle_stage", "EXECUTION"),)
    assert contextual == ()
