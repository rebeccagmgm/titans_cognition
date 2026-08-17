from pathlib import Path
import json

import pytest

from titans_cognition.table_review import render_table_semantic_review


def _profile(index: int) -> dict[str, object]:
    return {
        "asset_id": f"asset:{index}",
        "object_name": f"TABLE_{index:03d}",
        "object_comment": "测试表",
        "disposition": "SUBJECT" if index % 2 else "LIKELY_VARIANT",
        "candidate_summary": {
            "context_candidate_ids": [],
            "anchor_candidate_ids": [],
            "responsibility_candidate_ids": [],
            "has_conflict": index == 1,
            "has_unknown": index == 2,
        },
        "panorama_object_card": f"panorama/objects/{index}.html",
    }


def _read_assignment(path: Path, name: str) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    return json.loads(text.removeprefix(f"window.TABLE_SEMANTIC_{name}=").removesuffix(";\n"))


def test_review_is_gate_controlled_and_sharded(tmp_path: Path):
    with pytest.raises(ValueError, match="forbidden"):
        render_table_semantic_review(
            tmp_path,
            table_profiles=[],
            context_candidates=[],
            anchor_candidates=[],
            responsibility_candidates=[],
            table_groups=[],
            memberships=[],
            relations=[],
            evidence_refs=[],
            assertions=[],
            review_decisions=[],
            structural_propagation_hints=[],
            field_summaries=[],
            wiki_candidates=[],
            investigation_cards=[],
            quality_gate={"status": "FAIL"},
            limits={},
        )

    context_candidates = [
        {"asset_id": "asset:1", "candidate_value": "TRS", "outcome": "CANDIDATE"},
        {"asset_id": "asset:2", "candidate_value": "TRS", "outcome": "CANDIDATE"},
        {"asset_id": "asset:2", "candidate_value": "OPTION", "outcome": "CANDIDATE"},
    ]
    anchor_candidates = [
        {"asset_id": "asset:1", "candidate_value": "CONTRACT", "outcome": "CANDIDATE"}
    ]
    responsibility_candidates = [
        {
            "asset_id": "asset:1",
            "candidate_value": "CONFIGURATION",
            "candidate_id": "candidate:configuration",
            "outcome": "CANDIDATE",
            "recommended_profile_eligible": True,
            "vocabulary_layer": "SEED",
        },
        {
            "asset_id": "asset:2",
            "candidate_value": "审批记录",
            "candidate_id": "candidate:approval",
            "outcome": "CANDIDATE",
            "recommended_profile_eligible": False,
            "vocabulary_layer": "DISCOVERY",
        },
    ]
    assertions = [
        {
            "assertion_id": "assertion:configuration",
            "subject_id": "asset:1",
            "predicate": "HAS_RESPONSIBILITY_CANDIDATE",
            "object_value": "CONFIGURATION",
            "outcome": "CANDIDATE",
            "method_id": "fixture",
            "evidence_refs": ["evidence:table"],
            "counterevidence_refs": ["evidence:counter"],
        }
    ]
    field_summaries = [
        {
            "asset_id": "asset:1",
            "availability": "AVAILABLE",
            "field_assistance_status": "USED",
            "assertion_links": [
                {
                    "assertion_id": "assertion:configuration",
                    "candidate_value": "CONFIGURATION",
                    "role": "SUPPORTS",
                    "source_column_names": ["RULE_ID"],
                    "evidence_refs": ["evidence:field"],
                },
                {
                    "assertion_id": "assertion:configuration",
                    "candidate_value": "CONFIGURATION",
                    "role": "DISTINGUISH",
                    "source_column_names": ["RULE_TYPE"],
                    "evidence_refs": ["evidence:field"],
                },
                {
                    "assertion_id": "assertion:configuration",
                    "candidate_value": "CONFIGURATION",
                    "role": "COUNTER",
                    "source_column_names": ["EXECUTION_STATUS"],
                    "evidence_refs": ["evidence:counter"],
                },
            ],
            "semantic_assistance": {"field_candidates": []},
        },
        {
            "asset_id": "asset:2",
            "availability": "AVAILABLE",
            "field_assistance_status": "NOT_USED",
            "assertion_links": [],
            "semantic_assistance": {"field_candidates": []},
        },
    ]
    paths = render_table_semantic_review(
        tmp_path,
        table_profiles=[_profile(index) for index in range(7)],
        context_candidates=context_candidates,
        anchor_candidates=anchor_candidates,
        responsibility_candidates=responsibility_candidates,
        table_groups=[
            {"group_id": "v1", "group_kind": "PHYSICAL_VARIANT_GROUP"},
            {"group_id": "s1", "group_kind": "STRUCTURAL_NEIGHBORHOOD"},
        ],
        memberships=[],
        relations=[],
        evidence_refs=[
            {"evidence_id": "evidence:table", "content_excerpt": "配置规则表"},
            {"evidence_id": "evidence:counter", "content_excerpt": "名称也可能是运行规则"},
            {"evidence_id": "evidence:field", "content_excerpt": "RULE_ID"},
        ],
        assertions=assertions,
        review_decisions=[
            {"decision_id": "decision:1", "assertion_id": "assertion:configuration"}
        ],
        structural_propagation_hints=[],
        field_summaries=field_summaries,
        wiki_candidates=[],
        investigation_cards=[{"card_id": "trs", "status": "READY", "members": []}],
        quality_gate={"status": "PASS", "checks": []},
        limits={"review_shard_size": 3, "first_load_table_limit": 4},
    )
    index = paths["review_index"].read_text(encoding="utf-8")
    catalog_text = paths["review_catalog"].read_text(encoding="utf-8")
    catalog = _read_assignment(paths["review_catalog"], "CATALOG")
    stats = catalog["reader_stats"]
    assert stats["scope"] == {"metric_kind": "scope", "total_tables": 7}
    assert stats["dispositions"]["metric_kind"] == "mutually_exclusive"
    assert stats["dispositions"]["values"] == {"LIKELY_VARIANT": 4, "SUBJECT": 3}
    assert stats["candidate_coverage"] == {
        "metric_kind": "overlapping_status",
        "anchors": 1,
        "contexts": 2,
        "responsibilities": 2,
    }
    assert stats["states"] == {
        "metric_kind": "overlapping_status",
        "conflict": 1,
        "unknown": 1,
    }
    assert stats["field_assistance"] == {
        "metric_kind": "mutually_exclusive",
        "values": {"NOT_EVALUABLE": 5, "NOT_USED": 1, "USED": 1},
    }
    assert stats["review"] == {
        "decision_count": 1,
        "metric_kind": "review_status",
        "reviewed_table_count": 1,
        "unreviewed_table_count": 6,
    }
    assert catalog["indexes"]["contexts"] == [
        {"asset_ids": ["asset:1", "asset:2"], "table_count": 2, "value": "TRS"},
        {"asset_ids": ["asset:2"], "table_count": 1, "value": "OPTION"},
    ]
    assert catalog["indexes"]["dispositions"] == {
        "LIKELY_VARIANT": ["asset:0", "asset:2", "asset:4", "asset:6"],
        "SUBJECT": ["asset:1", "asset:3", "asset:5"],
    }
    first_rows = {row["asset_id"]: row for row in catalog["first_tables"]}
    assert first_rows["asset:1"]["reader_summary"] == {
        "anchors": ["CONTRACT"],
        "contexts": ["TRS"],
        "discovered_responsibilities": [],
        "field_assistance_status": "USED",
        "recommended_responsibilities": ["CONFIGURATION"],
    }
    assert "字段只作辅助证据" in index
    assert "Conflict" in index and "Unknown" in index
    assert "① 全貌" in index
    assert "② 表语义导航" in index
    assert "③ 表目录矩阵" in index
    assert "④ 单表画像与证据" in index
    assert "树只用于浏览，候选允许多值" in index
    assert "当前结果" in index and "已加载" in index
    assert "物理处置（互斥）" in index and "业务切面（可重叠）" in index
    assert "人工审阅" in index and "读者交付：待用户确认" in index
    assert "全部分片加载完成" in index and "加载不完整" in index
    assert "物理变体" in index and "结构邻域" in index and "专项复核" in index
    assert "方法验证样本，不是全量分类" in index
    assert "history.pushState" in index
    assert "renderAssertion" in index
    assert "fieldRoleLabel" in index
    assert "limitationLabel" in index
    details_text = paths["review_details"].read_text(encoding="utf-8")
    assert '"role": "SUPPORTS"' in details_text
    assert '"role": "DISTINGUISH"' in details_text
    assert '"role": "COUNTER"' in details_text
    assert "直接证据" in index and "反证" in index
    assert "字段未用于这项判断" in index
    assert "仅结构线索，不是业务分类" in index
    assert "业务上下文" in index and "业务锚点" in index and "业务协作组" in index
    assert "activeAssetIds" in index
    assert "scope-summary" in index and "loading-state" in index
    assert "return-to-subjects" in index
    assert "show-other-tables" in index
    assert "show-all-physical" in index
    assert "后缀/变体或其他处置" in index
    assert "审计与调试数据（一般无需查看）" in index
    assert "技术详情与未使用字段摘要" not in index
    assert '"first_load_limit": 4' in catalog_text
    assert len(list((tmp_path / "review/data/tables").glob("*.js"))) == 3


def test_review_rejects_duplicate_assets(tmp_path: Path):
    duplicate = _profile(1)
    with pytest.raises(ValueError, match="duplicate asset_id"):
        render_table_semantic_review(
            tmp_path,
            table_profiles=[duplicate, dict(duplicate)],
            context_candidates=[],
            anchor_candidates=[],
            responsibility_candidates=[],
            table_groups=[],
            memberships=[],
            relations=[],
            evidence_refs=[],
            assertions=[],
            review_decisions=[],
            structural_propagation_hints=[],
            field_summaries=[],
            wiki_candidates=[],
            investigation_cards=[],
            quality_gate={"status": "PASS"},
            limits={},
        )
