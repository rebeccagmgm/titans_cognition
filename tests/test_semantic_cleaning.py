import json

import pytest

from titans_cognition.semantic_cleaning import (
    build_review_batches,
    clean_concepts,
    discover_same_name_comment_reviews,
    import_review_decisions,
)


def _concept(concept_id, label):
    return {"concept_id": concept_id, "label": label}


def test_identifier_aliases_share_one_semantic_family():
    cleaned, review = clean_concepts(
        [
            _concept("party", "交易对手"),
            _concept("party-number", "交易对手编号"),
            _concept("party-id", "交易对手ID"),
        ]
    )

    assert {row.family_label for row in cleaned} == {"交易对手"}
    identifiers = [row for row in cleaned if row.attribute_kind == "IDENTIFIER"]
    assert len(identifiers) == 2
    assert {row.display_label for row in identifiers} == {"交易对手ID"}
    assert not review


def test_role_variants_are_qualifiers_not_separate_families():
    cleaned, _ = clean_concepts(
        [
            _concept("party", "交易对手"),
            _concept("source", "源侧交易对手"),
            _concept("target", "目标交易对手"),
        ]
    )

    assert {row.family_label for row in cleaned} == {"交易对手"}
    by_source = {row.source_label: row for row in cleaned}
    assert by_source["源侧交易对手"].qualifiers == (("semantic_modifier", "源侧"),)
    assert by_source["目标交易对手"].qualifiers == (("semantic_modifier", "目标"),)


def test_processing_variants_share_transaction_stream_family():
    cleaned, _ = clean_concepts(
        [
            _concept("original", "原始交易流水"),
            _concept("manual", "手工交易流水"),
            _concept("merged", "合并交易流水"),
            _concept("after", "合并后交易流水"),
        ]
    )

    assert {row.family_label for row in cleaned} == {"交易流水"}
    assert {qualifier for row in cleaned for qualifier in row.qualifiers} >= {
        ("semantic_modifier", "原始"),
        ("semantic_modifier", "手工"),
        ("semantic_modifier", "合并"),
        ("semantic_modifier", "合并后"),
    }


def test_nonrecurring_candidate_is_queued_instead_of_forced():
    cleaned, review = clean_concepts([_concept("only", "源侧孤立对象")])

    assert cleaned[0].family_label == "源侧孤立对象"
    assert not review


def test_unseen_business_vocabulary_is_discovered_from_recurrence():
    cleaned, _ = clean_concepts(
        [
            _concept("a", "盘前神秘余额"),
            _concept("b", "盘后神秘余额"),
            _concept("c", "预测神秘余额"),
        ]
    )

    assert {row.family_label for row in cleaned} == {"神秘余额"}
    assert {row.qualifiers for row in cleaned} == {
        (("semantic_modifier", "盘前"),),
        (("semantic_modifier", "盘后"),),
        (("semantic_modifier", "预测"),),
    }


def test_same_physical_name_with_different_comments_enters_review_queue():
    reviews = discover_same_name_comment_reviews(
        [
            {"column_id": "a", "column_name": "KEY_ID", "column_comment": "交易编号"},
            {"column_id": "b", "column_name": "key_id", "column_comment": "合约编号"},
        ]
    )

    assert reviews[0]["review_type"] == "SAME_PHYSICAL_NAME_DIFFERENT_COMMENT"
    assert reviews[0]["status"] == "NEEDS_REVIEW"


def test_review_batches_are_bounded_and_cannot_write_back_automatically():
    reviews = [
        {
            "review_type": "QUALIFIED_VARIANT",
            "source_concept_id": f"c-{index}",
            "source_label": f"来源{index}",
            "candidate_family_label": "候选族",
            "modifier": str(index),
        }
        for index in range(5)
    ]

    batches = build_review_batches(reviews, batch_size=2)

    assert [len(batch["items"]) for batch in batches] == [2, 2, 1]
    assert all(
        batch["decision_contract"]["automatic_write_back"] is False for batch in batches
    )


def test_review_import_is_validated_and_never_applied(tmp_path):
    packs = tmp_path / "packs"
    packs.mkdir()
    (packs / "batch-1.json").write_text(
        json.dumps(
            {
                "batch_id": "batch-1",
                "items": [{"item_key": "source-concept:c-1"}],
            }
        ),
        encoding="utf-8",
    )
    responses = tmp_path / "responses.jsonl"
    responses.write_text(
        json.dumps(
            {
                "item_key": "source-concept:c-1",
                "decision": "qualified_variant",
                "rationale": "the modifier changes the expression",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "decisions.jsonl"

    stats = import_review_decisions(
        packs, responses, output, model_id="approved-test-model"
    )

    assert stats == {
        "available_item_count": 1,
        "imported_decision_count": 1,
        "unreviewed_item_count": 0,
    }
    imported = json.loads(output.read_text(encoding="utf-8"))
    assert imported["status"] == "IMPORTED_NOT_APPLIED"
    assert imported["automatic_write_back"] is False


def test_review_import_rejects_unknown_items(tmp_path):
    packs = tmp_path / "packs"
    packs.mkdir()
    (packs / "batch-1.json").write_text(
        json.dumps({"batch_id": "batch-1", "items": [{"item_key": "known"}]}),
        encoding="utf-8",
    )
    responses = tmp_path / "responses.jsonl"
    responses.write_text(
        json.dumps(
            {
                "item_key": "unknown",
                "decision": "DEFER",
                "rationale": "insufficient evidence",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown item_key"):
        import_review_decisions(
            packs,
            responses,
            tmp_path / "out.jsonl",
            model_id="approved-test-model",
        )
