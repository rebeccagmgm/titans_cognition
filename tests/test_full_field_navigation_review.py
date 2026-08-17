from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from titans_cognition.full_field_navigation_review import (
    build_full_field_navigation_review,
)
from titans_cognition.render import _slug


def _pack(object_name: str, field_name: str, comment: str = "") -> dict:
    column_id = f"testdb:TITANS_TRADEFLOW:TABLE:{object_name}:COLUMN:{field_name}"
    return {
        "physical_identity": {
            "schema_name": "TITANS_TRADEFLOW",
            "object_name": object_name,
            "physical_column_id": column_id,
        },
        "raw_physical_fact": {
            "object_comment_raw": object_name,
            "column_comment_raw": comment,
            "data_type_raw": "VARCHAR2(64)",
            "nullable": True,
            "ordinal_position": 1,
        },
        "preparation_disposition": {"status": "PREPARED", "reason_code": None},
        "candidate_qualifier_observations": [],
        "generic_attribute_observations": [],
        "technical_observations": [],
        "conflicts": [],
        "unresolved_items": [],
    }


def _write_source(source: Path, rows: list[dict]) -> None:
    source.mkdir()
    payload = b"".join(
        (json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
        for row in rows
    )
    (source / "field-evidence-packs.jsonl").write_bytes(payload)
    (source / "manifest.json").write_text(
        json.dumps(
            {
                "counts": {"evidence_packs": len(rows)},
                "field_evidence_packs_sha256": hashlib.sha256(payload).hexdigest(),
            }
        ),
        encoding="utf-8",
    )


def _write_config(tmp_path: Path, count: int) -> Path:
    config = yaml.safe_load(
        Path("cases/tradeflow/full-field-semantic-navigation.yaml").read_text(
            encoding="utf-8"
        )
    )
    config["panorama_root"] = str(tmp_path / "panorama")
    config["expected_field_count"] = count
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return config_path


def test_builds_original_page_with_six_readers_and_exact_full_corpus(
    tmp_path: Path,
) -> None:
    rows = [
        _pack("TRD_OTC_TRADE", "KEY_CTPTY_ID", "交易对手ID"),
        _pack("TRD_TRS_ORDER", "KEY_ORDER_ID", "订单ID"),
        _pack("TRD_OTC_TRADE", "KEY_OTC_TRADE_ID", "交易ID"),
        _pack("REF_TRS_LEG", "NOTIONAL", "名义本金"),
        _pack("POS_TRS_CURRENT", "KEY_POSITION_ID", "持仓ID"),
        _pack("TRD_MARGIN", "MARGIN_BALANCE", "保证金余额"),
        _pack("SYS_CONFIG", "UPDATED_BY", "更新人"),
        _pack("TRD_MARGIN", "UPDATED_BY", "更新人"),
    ]
    rows[-1]["preparation_disposition"] = {
        "status": "EXCLUDED",
        "reason_code": "TECHNICAL_AUDIT_FIELD",
    }
    source = tmp_path / "source"
    _write_source(source, rows)
    config_path = _write_config(tmp_path, len(rows))
    asset_id = "testdb:TITANS_TRADEFLOW:TABLE:TRD_OTC_TRADE"
    object_page = tmp_path / "panorama" / "objects" / f"{_slug(asset_id)}.html"
    object_page.parent.mkdir(parents=True)
    object_page.write_text("<title>trade</title>", encoding="utf-8")

    result = build_full_field_navigation_review(source, config_path, tmp_path / "out")

    html = result["review_index"].read_text(encoding="utf-8")
    projection = result["projection"].read_text(encoding="utf-8")
    manifest = json.loads(result["manifest"].read_text(encoding="utf-8"))
    utility_path = next(
        result["review_index"].parent.glob("data/concepts/utility-all-fields-*.js")
    )
    utility = utility_path.read_text(encoding="utf-8")
    assert "① 业务地图" in html
    assert "② 语义索引" in html
    assert "③ 语义详情" in html
    assert "expressionMatchesSearch" in html
    assert "Reader候选已抑制" in html
    assert '"id":"reader:order"' in projection
    assert '"id":"reader:trade"' in projection
    assert manifest["stats"]["reader_count"] == 6
    assert manifest["stats"]["field_count"] == 8
    assert manifest["stats"]["unique_field_count"] == 8
    assert manifest["stats"]["full_corpus_field_count"] == 8
    assert manifest["stats"]["unassigned_field_count"] == 2
    assert manifest["stats"]["reader_field_counts"]["reader:order"] == 1
    assert manifest["stats"]["reader_field_counts"]["reader:trade"] == 1
    assert manifest["stats"]["reader_field_counts"]["reader:margin"] == 1
    assert utility.count('"columnId":"testdb:TITANS_TRADEFLOW:') == 8
    assert '"preparationDisposition":"EXCLUDED"' in utility
    assert '"suppressedReaderAssignments":["reader:margin:OBJECT_CONTEXT"]' in utility
    assert object_page.resolve().as_uri() in utility


def test_rejects_duplicate_physical_field_ids(tmp_path: Path) -> None:
    row = _pack("TRD_OTC_TRADE", "KEY_OTC_TRADE_ID", "交易ID")
    source = tmp_path / "source"
    _write_source(source, [row, row])
    config_path = _write_config(tmp_path, 2)

    with pytest.raises(ValueError, match="unique fields"):
        build_full_field_navigation_review(source, config_path, tmp_path / "out")
