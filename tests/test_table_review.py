from pathlib import Path

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

    paths = render_table_semantic_review(
        tmp_path,
        table_profiles=[_profile(index) for index in range(7)],
        context_candidates=[],
        anchor_candidates=[],
        responsibility_candidates=[],
        table_groups=[
            {"group_id": "v1", "group_kind": "PHYSICAL_VARIANT_GROUP"},
            {"group_id": "s1", "group_kind": "STRUCTURAL_NEIGHBORHOOD"},
        ],
        memberships=[],
        relations=[],
        evidence_refs=[],
        assertions=[],
        review_decisions=[],
        structural_propagation_hints=[],
        field_summaries=[],
        wiki_candidates=[],
        investigation_cards=[{"card_id": "trs", "status": "READY", "members": []}],
        quality_gate={"status": "PASS", "checks": []},
        limits={"review_shard_size": 3, "first_load_table_limit": 4},
    )
    index = paths["review_index"].read_text(encoding="utf-8")
    catalog = paths["review_catalog"].read_text(encoding="utf-8")
    assert "字段只作辅助证据" in index
    assert "Conflict" in index and "Unknown" in index
    assert "r.disposition==='UNKNOWN'" in index
    assert "物理变体" in index and "结构邻域" in index
    assert "requestToken" in index
    assert "history.pushState" in index
    assert "Evidence / Counterevidence" in index
    assert "仅结构传播提示" in index
    assert "业务上下文" in index and "业务锚点" in index and "业务协作组" in index
    assert "成员职责" in index and "有方向含义的候选关系" in index
    assert "结构就绪 · 语义仍有 Unknown" in index and "尚未人工确认" in index
    assert "一般或未决关系" in index and "r.directed===true" in index
    assert "relationEvidence" in index and "反证：" in index
    assert "unknown_member_asset_ids" in index and "语义待审" in index
    assert "rel.flatMap" in index
    assert "缺口与 Unknown" in index and "完整技术详情" in index
    assert "card.relations" in index
    assert "activeAssetIds" in index
    assert '"first_load_limit": 4' in catalog
    assert len(list((tmp_path / "review/data/tables").glob("*.js"))) == 3
