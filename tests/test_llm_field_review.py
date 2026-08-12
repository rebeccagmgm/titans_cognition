import hashlib
import json
from pathlib import Path

import pytest

from titans_cognition.cli import main
from titans_cognition.llm_field_review import (
    import_review_responses,
    load_review_config,
    prepare_review,
    provider_status,
    render_review,
)
from titans_cognition.render import _slug


def _jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def _baseline(tmp_path: Path) -> Path:
    root = tmp_path / "baseline" / "field-concepts"
    concepts = [
        {
            "concept_id": "c-mixed",
            "label": "金额",
            "level": 1,
            "parent_id": None,
            "member_count": 5,
            "method_id": "fixture",
        },
        {
            "concept_id": "c-clean",
            "label": "交易日期",
            "level": 2,
            "parent_id": None,
            "member_count": 2,
            "method_id": "fixture",
        },
    ]
    links = [
        _link("f-1", "c-mixed", "INITIAL_NOTIONAL", "初始名义本金", "T_A", "NUMBER"),
        _link("f-2", "c-mixed", "CURRENT_NOTIONAL", "当前名义本金", "T_B", "VARCHAR2"),
        _link("f-3", "c-mixed", "FEE_AMOUNT", "手续费金额", "T_C", "NUMBER"),
        _link("f-4", "c-mixed", "REPORT_AMOUNT", "报送金额", "T_D", "NUMBER"),
        _link("f-5", "c-mixed", "UNKNOWN_VALUE", None, "T_E", "NUMBER"),
        _link("f-6", "c-clean", "TRADE_DATE", "交易日期", "T_A", "DATE"),
        _link("f-7", "c-clean", "DEAL_DATE", "交易日期", "T_B", "VARCHAR2"),
        {
            **_link("f-3", "c-clean", "FEE_AMOUNT", "手续费金额", "T_C", "NUMBER"),
            "rank": 2,
            "status": "AMBIGUOUS",
            "method_score": 0.79,
        },
    ]
    _jsonl(root / "concepts.jsonl", concepts)
    _jsonl(root / "field_concept_links.jsonl", links)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "fixture-run",
                "config_sha256": "baseline-config",
                "method_id": "fixture",
                "outputs": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return root


def _link(
    field_id: str,
    concept_id: str,
    name: str,
    comment: str | None,
    table: str,
    data_type: str,
) -> dict[str, object]:
    return {
        "field_id": field_id,
        "asset_id": f"asset-{table}",
        "schema_name": "TITANS_TRADEFLOW",
        "object_name": table,
        "field_name": name,
        "field_comment": comment,
        "data_type": data_type,
        "type_family": "NUMBER" if data_type == "NUMBER" else "TEXT",
        "concept_id": concept_id,
        "rank": 1,
        "status": "CANDIDATE",
        "method_score": 0.7,
    }


def _config(tmp_path: Path, *, budget: int = 10_000) -> Path:
    path = tmp_path / "llm-review.yaml"
    path.write_text(
        f"""
version: v1
selection:
  min_members: 2
  low_cohesion_threshold: 0.55
  outlier_similarity_threshold: 0.20
  outlier_ratio_threshold: 0.20
  weak_label_support_threshold: 0.45
  ambiguity_ratio_threshold: 0.10
  mixed_qualifier_count: 2
limits:
  max_packs: 4
  max_fields_per_pack: 12
  max_pack_tokens: 2000
  token_budget: {budget}
  chars_per_token: 2.0
sampling:
  representative_count: 2
  boundary_count: 2
  outlier_count: 2
qualifier_dimensions:
  stage:
    initial: [INITIAL, 初始]
    current: [CURRENT, 当前]
  direction:
    before: [BEFORE, 调整前]
    after: [AFTER, 调整后]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return path


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_prepare_selects_only_algorithmic_issues_and_is_replayable(tmp_path):
    baseline = _baseline(tmp_path)
    config = load_review_config(_config(tmp_path))

    first = prepare_review(baseline, config, tmp_path / "first")
    second = prepare_review(baseline, config, tmp_path / "second")

    selection = _read_jsonl(first["selection"])
    assert [row["concept_id"] for row in selection] == ["c-mixed"]
    assert {"LOW_COHESION", "OUTLIER_MEMBERS", "WEAK_LABEL_SUPPORT"} & set(
        selection[0]["reasons"]
    )
    assert first["packs"].read_bytes() == second["packs"].read_bytes()
    pack = _read_jsonl(first["packs"])[0]
    assert pack["pack_hash"]
    assert pack["known_gaps"]["missing_comments"] == 1
    assert all("column_value" not in item for item in pack["evidence"])
    assert any(item["data_type"] == "VARCHAR2" for item in pack["evidence"])


def test_token_budget_truncates_without_changing_rank_order(tmp_path):
    baseline = _baseline(tmp_path)
    generous = prepare_review(
        baseline,
        load_review_config(_config(tmp_path, budget=10_000)),
        tmp_path / "generous",
    )
    first_pack = _read_jsonl(generous["packs"])[0]
    tiny_budget = max(1, int(first_pack["estimated_tokens"]) - 1)

    bounded = prepare_review(
        baseline,
        load_review_config(_config(tmp_path, budget=tiny_budget)),
        tmp_path / "bounded",
    )
    manifest = json.loads(bounded["manifest"].read_text(encoding="utf-8"))

    assert _read_jsonl(bounded["packs"]) == []
    assert manifest["stats"]["budget_skipped_count"] == 1


def test_equivalent_competing_labels_do_not_create_false_conflict(tmp_path):
    root = tmp_path / "equivalent" / "field-concepts"
    _jsonl(
        root / "concepts.jsonl",
        [
            {
                "concept_id": "c-rate",
                "label": "保证金追保线(%)",
                "level": 2,
                "parent_id": None,
                "member_count": 3,
            },
            {
                "concept_id": "c-rate-format",
                "label": "保证金追保线",
                "level": 2,
                "parent_id": None,
                "member_count": 0,
            },
        ],
    )
    links = []
    for index in range(3):
        field_id = f"rate-{index}"
        links.append(
            _link(
                field_id,
                "c-rate",
                "MARGIN_CALL",
                "保证金追保线(%)",
                f"T_{index}",
                "NUMBER",
            )
        )
        links.append(
            {
                **_link(
                    field_id,
                    "c-rate-format",
                    "MARGIN_CALL",
                    "保证金追保线(%)",
                    f"T_{index}",
                    "NUMBER",
                ),
                "rank": 2,
                "status": "AMBIGUOUS",
            }
        )
    _jsonl(root / "field_concept_links.jsonl", links)
    (root / "manifest.json").write_text(
        json.dumps({"run_id": "equivalent-run", "config_sha256": "fixture"}),
        encoding="utf-8",
    )

    result = prepare_review(
        root,
        load_review_config(_config(tmp_path)),
        tmp_path / "equivalent-review",
    )

    assert _read_jsonl(result["selection"]) == []


def _response(pack: dict[str, object], action: str) -> dict[str, object]:
    evidence_ids = [item["evidence_id"] for item in pack["evidence"]]
    base = {
        "pack_id": pack["pack_id"],
        "pack_hash": pack["pack_hash"],
        "action": action,
        "evidence_ids": evidence_ids[:2],
        "counterevidence_ids": evidence_ids[2:3],
        "rationale": "候选判断",
    }
    if action == "RENAME":
        base["candidate_label"] = "金额相关字段"
    elif action == "SPLIT":
        base["groups"] = [
            {"label": "组一", "member_evidence_ids": evidence_ids[:2]},
            {"label": "组二", "member_evidence_ids": evidence_ids[2:4]},
        ]
        base["undecided_evidence_ids"] = evidence_ids[4:]
    elif action == "PARENT_CHILD":
        base.update(
            {
                "parent_label": "金额",
                "child_label": "名义本金",
                "member_evidence_ids": evidence_ids[:2],
            }
        )
    elif action == "FACET":
        base.update(
            {
                "base_label": "名义本金",
                "dimension": "stage",
                "value": "initial",
                "member_evidence_ids": evidence_ids[:1],
            }
        )
    elif action == "ABSTAIN":
        base["missing_evidence"] = ["缺少生产数据语义"]
    return base


@pytest.mark.parametrize(
    "action", ["KEEP", "RENAME", "SPLIT", "PARENT_CHILD", "FACET", "ABSTAIN"]
)
def test_import_accepts_all_bounded_actions_and_preserves_baseline(tmp_path, action):
    baseline = _baseline(tmp_path)
    review = prepare_review(
        baseline, load_review_config(_config(tmp_path)), tmp_path / "review"
    )
    pack = _read_jsonl(review["packs"])[0]
    response_path = tmp_path / f"{action}.jsonl"
    _jsonl(response_path, [_response(pack, action)])
    baseline_before = (baseline / "concepts.jsonl").read_bytes()

    stats = import_review_responses(
        review["root"], response_path, model_id="current-gpt-session-test"
    )

    assert stats["valid_count"] == 1
    candidates = _read_jsonl(review["root"] / "revision_candidates.jsonl")
    assert candidates[0]["action"] == action
    assert candidates[0]["status"] == "CANDIDATE"
    assert (baseline / "concepts.jsonl").read_bytes() == baseline_before


@pytest.mark.parametrize(
    "mutation,error_code",
    [
        (lambda row: row.update(pack_hash="stale"), "STALE_PACK_HASH"),
        (lambda row: row.update(evidence_ids=["FIELD::unknown"]), "UNKNOWN_EVIDENCE"),
        (lambda row: row.update(action="FREE_FORM"), "INVALID_ACTION"),
    ],
)
def test_import_isolates_invalid_responses(tmp_path, mutation, error_code):
    baseline = _baseline(tmp_path)
    review = prepare_review(
        baseline, load_review_config(_config(tmp_path)), tmp_path / "review"
    )
    pack = _read_jsonl(review["packs"])[0]
    invalid = _response(pack, "KEEP")
    mutation(invalid)
    response_path = tmp_path / "invalid.jsonl"
    _jsonl(response_path, [invalid, _response(pack, "ABSTAIN")])

    stats = import_review_responses(review["root"], response_path, model_id="test")

    assert stats == {"response_count": 2, "valid_count": 1, "error_count": 1}
    errors = _read_jsonl(review["root"] / "errors.jsonl")
    assert errors[0]["error_code"] == error_code


def test_split_rejects_duplicate_members(tmp_path):
    review = prepare_review(
        _baseline(tmp_path),
        load_review_config(_config(tmp_path)),
        tmp_path / "review",
    )
    pack = _read_jsonl(review["packs"])[0]
    response = _response(pack, "SPLIT")
    response["groups"][1]["member_evidence_ids"][0] = response["groups"][0][
        "member_evidence_ids"
    ][0]
    response_path = tmp_path / "duplicate.jsonl"
    _jsonl(response_path, [response])

    import_review_responses(review["root"], response_path, model_id="test")

    error = _read_jsonl(review["root"] / "errors.jsonl")[0]
    assert error["error_code"] == "DUPLICATE_MEMBER"


def test_non_abstain_requires_evidence_and_bad_cache_is_isolated(tmp_path):
    review = prepare_review(
        _baseline(tmp_path),
        load_review_config(_config(tmp_path)),
        tmp_path / "review",
    )
    pack = _read_jsonl(review["packs"])[0]
    response = _response(pack, "KEEP")
    response["evidence_ids"] = []
    response["counterevidence_ids"] = []
    response_path = tmp_path / "no-evidence.jsonl"
    _jsonl(response_path, [response])

    stats = import_review_responses(review["root"], response_path, model_id="test")
    assert stats == {"response_count": 1, "valid_count": 0, "error_count": 1}
    assert _read_jsonl(review["root"] / "errors.jsonl")[0]["error_code"] == (
        "MISSING_EVIDENCE"
    )

    cache = tmp_path / "bad-cache"
    cache.mkdir()
    cache_key = hashlib.sha256(
        "|".join(
            [
                str(pack["pack_hash"]),
                "field-concept-review-prompt-v1",
                "field-concept-review-response-v1",
                "test",
            ]
        ).encode("utf-8")
    ).hexdigest()
    (cache / f"{cache_key}.json").write_text("not json", encoding="utf-8")
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    cached_stats = import_review_responses(
        review["root"], empty, model_id="test", cache_dir=cache
    )
    assert cached_stats == {"response_count": 1, "valid_count": 0, "error_count": 1}
    assert _read_jsonl(review["root"] / "errors.jsonl")[0]["error_code"] == (
        "INVALID_CACHE"
    )


def test_cache_is_content_addressed_and_run_keeps_response_copy(tmp_path):
    review = prepare_review(
        _baseline(tmp_path),
        load_review_config(_config(tmp_path)),
        tmp_path / "review",
    )
    pack = _read_jsonl(review["packs"])[0]
    response_path = tmp_path / "response.jsonl"
    response = _response(pack, "KEEP")
    _jsonl(response_path, [response])
    cache = tmp_path / "cache"

    import_review_responses(
        review["root"], response_path, model_id="test-model", cache_dir=cache
    )

    cache_files = list(cache.glob("*.json"))
    assert len(cache_files) == 1
    assert hashlib.sha256(cache_files[0].read_bytes()).hexdigest()
    assert _read_jsonl(review["root"] / "responses.jsonl")[0]["model_id"] == "test-model"

    replay = prepare_review(
        _baseline(tmp_path),
        load_review_config(_config(tmp_path)),
        tmp_path / "replay",
    )
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    replay_stats = import_review_responses(
        replay["root"], empty, model_id="test-model", cache_dir=cache
    )
    assert replay_stats == {"response_count": 1, "valid_count": 1, "error_count": 0}
    assert _read_jsonl(replay["root"] / "responses.jsonl")[0]["cache_hit"] is True


def test_provider_remains_not_evaluable_without_d005_approval(tmp_path):
    config = load_review_config(_config(tmp_path))

    assert provider_status(config) == {
        "status": "NOT_EVALUABLE",
        "reason": "D-005 provider SDK approval is absent",
    }


def test_render_is_lazy_and_links_to_object_cards(tmp_path):
    panorama = tmp_path / "panorama"
    object_root = panorama / "objects"
    object_root.mkdir(parents=True)
    object_page = object_root / f"{_slug('asset-T_A')}.html"
    object_page.write_text("object", encoding="utf-8")
    review = prepare_review(
        _baseline(tmp_path),
        load_review_config(_config(tmp_path)),
        tmp_path / "review",
    )
    pack = _read_jsonl(review["packs"])[0]
    response_path = tmp_path / "response.jsonl"
    _jsonl(response_path, [_response(pack, "SPLIT")])
    import_review_responses(review["root"], response_path, model_id="test")

    page = render_review(review["root"], source_panorama_root=panorama)
    html = page.read_text(encoding="utf-8")

    assert "基线与 LLM 修订候选" in html
    assert "new Worker" in html
    assert "FIELD_PAGE_SIZE=50" in html
    assert html.count("class='field-row'") == 0
    assert object_page.resolve().as_uri() in html
    assert "CANDIDATE" in html


def test_cli_prepare_import_and_render(tmp_path, capsys):
    baseline = _baseline(tmp_path)
    config_path = _config(tmp_path)
    output = tmp_path / "cli-review"
    assert main(
        [
            "prepare-field-concept-llm-review",
            "--field-concepts-dir",
            str(baseline),
            "--config",
            str(config_path),
            "--output",
            str(output),
            "--max-packs",
            "1",
            "--token-budget",
            "5000",
        ]
    ) == 0
    prepare_output = json.loads(capsys.readouterr().out)
    pack = _read_jsonl(Path(prepare_output["packs"]))[0]
    response_path = tmp_path / "response.jsonl"
    _jsonl(response_path, [_response(pack, "KEEP")])

    assert main(
        [
            "import-field-concept-llm-review",
            "--review-dir",
            prepare_output["root"],
            "--responses",
            str(response_path),
            "--model-id",
            "current-gpt-session-test",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["valid_count"] == 1
    assert main(
        [
            "render-field-concept-llm-review",
            "--review-dir",
            prepare_output["root"],
        ]
    ) == 0
    assert Path(json.loads(capsys.readouterr().out)["review_index"]).exists()
