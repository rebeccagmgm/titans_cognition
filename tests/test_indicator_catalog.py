import json
from pathlib import Path

import pytest

from titans_cognition.cli import main
from titans_cognition.indicator_catalog import build_indicator_catalog


def _snapshot(tmp_path: Path, rows: list[dict], unique_rows: int | None = None) -> Path:
    snapshot = tmp_path / "snapshot-001"
    snapshot.mkdir()
    snapshot.joinpath("manifest.json").write_text(
        json.dumps(
            {
                "status": "PARTIAL",
                "uniqueRows": len(rows) if unique_rows is None else unique_rows,
                "expectedTotal": len(rows),
            }
        ),
        encoding="utf-8",
    )
    snapshot.joinpath("indicators.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    return snapshot


def _row(index_id: str, *, catalog=None, definition="业务定义") -> dict:
    return {
        "indexId": index_id,
        "chineseName": f"客户指标 {index_id}",
        "englishName": f"IND_{index_id}",
        "status": "ONLINE",
        "businessDefinition": definition,
        "catalog": catalog,
        "techDirector": "负责人",
    }


def test_build_indicator_catalog_preserves_gap_and_source_metadata(tmp_path):
    snapshot = _snapshot(
        tmp_path,
        [
            _row("ind-1", catalog=["分类", "指标标签目录", "客户"]),
            _row("ind-2", catalog=[], definition=""),
        ],
    )

    result = build_indicator_catalog(snapshot, tmp_path / "output")
    page = Path(result["page"])
    projection = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))

    assert result["record_count"] == 2
    assert result["uncatalogued_count"] == 1
    assert page.exists()
    assert projection["recordCount"] == 2
    assert projection["uncataloguedCount"] == 1
    html = page.read_text(encoding="utf-8")
    assert "业务定义" in html
    assert "未归类（源数据无目录）" in html
    assert "未采集（源快照没有该字段）" in html
    assert "function matches" in html
    assert "document.getElementById('visible')" in html


def test_build_indicator_catalog_rejects_duplicate_ids_without_publishing(tmp_path):
    snapshot = _snapshot(tmp_path, [_row("same"), _row("same")])
    output = tmp_path / "output"

    with pytest.raises(ValueError, match="duplicate indicator indexId"):
        build_indicator_catalog(snapshot, output)
    assert not output.exists()


def test_build_indicator_catalog_cli_writes_snapshot_scoped_page(tmp_path, capsys):
    snapshot = _snapshot(tmp_path, [_row("ind-1", catalog=["分类", "指标标签目录", "客户"])])
    output = tmp_path / "review"

    assert (
        main(
            [
                "build-indicator-catalog-review",
                "--snapshot-dir",
                str(snapshot),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["snapshot_id"] == "snapshot-001"
    assert (output / "snapshot-001" / "index.html").exists()
    assert (output / "snapshot-001" / "catalog-projection-manifest.json").exists()
