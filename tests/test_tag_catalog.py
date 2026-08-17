import hashlib
import json
import re
import subprocess
from pathlib import Path

import pytest

from titans_cognition.cli import main
from titans_cognition.tag_catalog import (
    DIMENSION_CATALOG_MISSING,
    DIMENSION_NOT_IN_SNAPSHOT,
    RELATION_NOT_CAPTURED,
    TYPE_NOT_CAPTURED,
    _display_catalog_parts,
    _format_sql,
    _read_snapshot,
    _tag_value_tree,
    build_tag_catalog,
)


def test_format_sql_accepts_representative_oracle_expression():
    formatted, status = _format_sql("WITH t AS (SELECT NVL(a, 0) a FROM dual) SELECT DECODE(a, 1, 'Y', 'N') FROM t")
    assert status == "FORMATTED"
    assert "WITH t AS" in formatted and "DECODE" in formatted


def test_display_catalog_parts_hides_only_the_leading_container_root():
    assert _display_catalog_parts("分类_指标标签目录_客户") == ("指标标签目录", "客户")
    assert _display_catalog_parts("业务域_分类_客户") == ("业务域", "分类", "客户")
    assert _display_catalog_parts("分类") == ("分类",)


def test_dimension_list_supplements_do_not_overwrite_detail_values(tmp_path):
    detail = {
        **_row("dim-detail"),
        "tagDimEnglishName": "detail_name",
        "statusCode": "4",
        "statusName": "详情状态",
        "securityLevelCode": "3",
        "securityLevelName": "3级",
        "resultDatabase": "detail_db",
        "resultTable": "detail_table",
        "markingTaskIds": "999999",
    }
    snapshot = _snapshot(tmp_path, [detail], tags=[])
    list_row = {
        **detail,
        "tagDimEnglishName": "list_name",
        "statusName": "列表状态",
        "securityLevelName": "2级",
        "resultDatabase": "list_db",
        "resultTable": "list_table",
        "markingTaskIds": "243650",
        "_raw": {"tagDimNo": "raw_name", "opsLvl": 1, "dbName": "raw_db", "engTblName": "raw_table"},
    }
    (snapshot / "tag-dimensions.jsonl").write_text(json.dumps(list_row, ensure_ascii=False) + "\n", encoding="utf-8")

    _, _, rows, _ = _read_snapshot(snapshot)

    assert rows[0]["tagDimEnglishName"] == "detail_name"
    assert rows[0]["statusName"] == "详情状态"
    assert rows[0]["securityLevelName"] == "3级"
    assert rows[0]["resultDatabase"] == "detail_db"
    assert rows[0]["resultTable"] == "detail_table"
    assert rows[0]["markingTaskIds"] == "999999"


def test_dimension_list_supplements_empty_detail_task_ids(tmp_path):
    detail = {
        **_row("tagdim102837"),
        "markingTaskIds": "-",
        "systemTagTaskIds": "-",
    }
    snapshot = _snapshot(tmp_path, [detail], tags=[])
    list_row = {
        **detail,
        "markingTaskIds": "243650/243650",
        "systemTagTaskIds": "-",
        "_raw": {
            "markingTask": [
                {"taskId": "243650", "editPurpose": 0},
                {"taskId": "243650", "editPurpose": 1},
            ],
            "newTagingTask": [],
        },
    }
    (snapshot / "tag-dimensions.jsonl").write_text(
        json.dumps(list_row, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    _, _, rows, _ = _read_snapshot(snapshot)

    assert rows[0]["markingTaskIds"] == "243650"
    assert rows[0]["systemTagTaskIds"] == "-"


def _snapshot(tmp_path: Path, rows: list[dict], *, declared: int | None = None, tags: list[dict] | None = None, links: list[dict] | None = None) -> Path:
    snapshot = tmp_path / "tag-snapshot"
    snapshot.mkdir(parents=True)
    (snapshot / "dimension-sql").mkdir()
    (snapshot / "detail-manifest.json").write_text(
        json.dumps({"snapshotId": "tag-test-001", "status": "COMPLETE", "dimensionDetailsCount": len(rows) if declared is None else declared}),
        encoding="utf-8",
    )
    (snapshot / "catalog-tree.json").write_text(json.dumps({"catalogTree": []}), encoding="utf-8")
    (snapshot / "dimension-details.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    if tags is not None:
        (snapshot / "tag-values.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in tags), encoding="utf-8")
        (snapshot / "tag-dimensions.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )
        (snapshot / "tag-value-dimension-links.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in (links or [])), encoding="utf-8")
        (snapshot / "manifest.json").write_text(json.dumps({"snapshotId": "tag-test-001", "status": "COMPLETE", "scope": "all", "fetchedTagValues": len(tags), "fetchedDimensions": len(rows)}), encoding="utf-8")
    return snapshot


def _row(tag_id: str, path: str = "分类_指标标签目录_客户", *, sql_status: str = "FOUND") -> dict:
    return {
        "tagDimId": tag_id,
        "tagDimName": f"客户标签 {tag_id}",
        "tagDimEnglishName": f"TAG_{tag_id}",
        "tagClassCode": "1",
        "tagClassName": "持仓",
        "realTimeTypeName": "OFFLINE",
        "statusName": "ONLINE",
        "catalogPath": path,
        "description": "标签描述",
        "resultDatabase": "DM",
        "resultTable": "TAG_RESULT",
        "detailEvidenceStatus": "FOUND",
        "sqlEvidenceStatus": sql_status,
    }


def test_build_tag_catalog_builds_nested_tree_and_sql_evidence(tmp_path):
    snapshot = _snapshot(tmp_path, [_row("tag-1"), _row("tag-2", "-")])
    sql = snapshot / "dimension-sql" / "tag-1.sql"
    sql.write_text("select 1", encoding="utf-8")
    rows = [json.loads(line) for line in (snapshot / "dimension-details.jsonl").read_text(encoding="utf-8").splitlines()]
    rows[0]["sqlFile"] = str(sql)
    rows[0]["sqlSha256"] = hashlib.sha256(sql.read_bytes()).hexdigest()
    (snapshot / "dimension-details.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")

    result = build_tag_catalog(snapshot, tmp_path / "output")
    projection = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
    html = Path(result["page"]).read_text(encoding="utf-8")

    assert result["record_count"] == 2
    assert result["uncatalogued_count"] == 1
    assert projection["sqlEvidenceCounts"]["FOUND"] == 1
    assert "指标标签目录" in html and "客户" in html
    assert "GENERATED_LOCAL" in html
    assert "调度任务 SQL 未纳入" in html
    assert "select 1" in html
    assert "sqlFormatStatus" in html
    assert "sql-keyword" in html
    assert "SQL 已格式化并高亮" in html


def test_build_tag_catalog_accepts_snapshot_normalized_sql_hash(tmp_path):
    snapshot = _snapshot(tmp_path, [_row("tag-1")])
    sql = snapshot / "dimension-sql" / "tag-1.sql"
    sql.write_text("select 1\n", encoding="utf-8")
    rows = [
        json.loads(line)
        for line in (snapshot / "dimension-details.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    rows[0]["sqlFile"] = str(sql)
    rows[0]["sqlSha256"] = hashlib.sha256(b"select 1").hexdigest()
    (snapshot / "dimension-details.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )

    result = build_tag_catalog(snapshot, tmp_path / "output")
    projection = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))

    assert projection["sqlEvidenceCounts"]["FOUND"] == 1


def test_build_tag_catalog_does_not_render_hash_mismatched_sql(tmp_path):
    snapshot = _snapshot(tmp_path, [_row("tag-1")])
    sql = snapshot / "dimension-sql" / "tag-1.sql"
    sql.write_text("select mismatch_sentinel\n", encoding="utf-8")
    rows = [
        json.loads(line)
        for line in (snapshot / "dimension-details.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    rows[0]["sqlFile"] = str(sql)
    rows[0]["sqlSha256"] = hashlib.sha256(b"different sql").hexdigest()
    (snapshot / "dimension-details.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )

    result = build_tag_catalog(snapshot, tmp_path / "output")
    html = Path(result["page"]).read_text(encoding="utf-8")

    assert "HASH_MISMATCH" in html
    assert "mismatch_sentinel" not in html


def test_build_tag_catalog_rejects_duplicate_or_mismatched_input(tmp_path):
    snapshot = _snapshot(tmp_path, [_row("same"), _row("same")])
    with pytest.raises(ValueError, match="duplicate tagDimId"):
        build_tag_catalog(snapshot, tmp_path / "output")
    assert not (tmp_path / "output").exists()

    snapshot = _snapshot(tmp_path / "mismatch", [_row("one")], declared=2)
    with pytest.raises(ValueError, match="count mismatch"):
        build_tag_catalog(snapshot, tmp_path / "mismatch-output")


def test_build_tag_catalog_falls_back_to_dimension_catalog_snapshot(tmp_path):
    snapshot = _snapshot(tmp_path, [_row("tagdim-1", "-")])
    (snapshot / "tag-dimensions.jsonl").write_text(
        json.dumps({"tagDimId": "tagdim-1", "catalogPath": "catalog_fallback"}) + "\n",
        encoding="utf-8",
    )

    result = build_tag_catalog(snapshot, tmp_path / "catalog-fallback-output")
    projection = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
    html = Path(result["page"]).read_text(encoding="utf-8")

    assert projection["uncataloguedCount"] == 0
    assert "catalog_fallback" in html


def test_build_tag_catalog_uses_catalog_tree_before_dimension_rows(tmp_path):
    snapshot = _snapshot(tmp_path, [_row("tagdim-1", "-")])
    (snapshot / "catalog-tree.json").write_text(
        json.dumps({"catalogTree": [{"objectId": "tagdim-1", "path": "tree_catalog"}]}),
        encoding="utf-8",
    )

    result = build_tag_catalog(snapshot, tmp_path / "tree-catalog-output")
    projection = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
    html = Path(result["page"]).read_text(encoding="utf-8")

    assert projection["uncataloguedCount"] == 0
    assert "tree_catalog" in html


def test_build_tag_catalog_keeps_generated_and_unavailable_sql_states(tmp_path):
    snapshot = _snapshot(tmp_path, [_row("local", sql_status="GENERATED_LOCAL"), _row("missing")])
    sql = snapshot / "dimension-sql" / "local.sql"
    sql.write_text("select local_value", encoding="utf-8")
    rows = [json.loads(line) for line in (snapshot / "dimension-details.jsonl").read_text(encoding="utf-8").splitlines()]
    rows[0]["sqlFile"] = str(sql)
    (snapshot / "dimension-details.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")

    result = build_tag_catalog(snapshot, tmp_path / "output")
    projection = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
    assert projection["sqlEvidenceCounts"]["GENERATED_LOCAL"] == 1
    assert projection["sqlEvidenceCounts"]["UNAVAILABLE"] == 1


def test_build_tag_catalog_cli_writes_snapshot_scoped_page(tmp_path, capsys):
    snapshot = _snapshot(tmp_path, [_row("tag-1", "分类_指标标签目录_客户")])
    assert main(["build-tag-catalog-review", "--snapshot-dir", str(snapshot), "--output", str(tmp_path / "review")]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["snapshot_id"] == "tag-test-001"
    assert (tmp_path / "review" / "tag-test-001" / "index.html").exists()


def test_invalid_rebuild_does_not_replace_existing_projection(tmp_path):
    snapshot = _snapshot(tmp_path, [_row("tag-1")])
    output = tmp_path / "review"
    build_tag_catalog(snapshot, output)
    page = output / "tag-test-001" / "index.html"
    original = page.read_bytes()
    (snapshot / "dimension-details.jsonl").write_text("not-json\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid tag detail"):
        build_tag_catalog(snapshot, output)
    assert page.read_bytes() == original


def test_build_tag_catalog_keeps_tag_values_and_dimensions_separate(tmp_path):
    dimensions = [{
        **_row("tagdim-1", "分类_客户"),
        "tagDimEnglishName": "-",
        "isCompositeTagDimension": "N",
        "_raw": {"tagDimNo": "customer_dim", "opsLvl": 2, "grpFltFlag": 0},
    }]
    tags = [{
        "tagId": "tag-1",
        "tagName": "客户标签一",
        "tagTypeName": "持仓",
        "statusName": "生效",
        "catalogPath": "分类_客户",
        "tagDimensionCount": "1",
        "generationCondition": "客户标签一 = 1",
        "tagDimIds": ["tagdim-1"],
    }]
    links = [{"tagId": "tag-1", "tagDimId": "tagdim-1", "dimensionEvidenceStatus": "FOUND"}]
    snapshot = _snapshot(tmp_path, dimensions, tags=tags, links=links)

    result = build_tag_catalog(snapshot, tmp_path / "dual-output")
    projection = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
    html = Path(result["page"]).read_text(encoding="utf-8")

    assert projection["schemaVersion"] == "tag-catalog-review-v2"
    assert projection["tagValueCount"] == 1
    assert projection["tagDimensionLinkCount"] == 1
    assert projection["tagTypeCounts"] == {"持仓": 1}
    assert projection["tagDimensionTypeCounts"] == {"持仓": 1}
    assert projection["listedDimensionCount"] == 1
    assert projection["relationOnlyDimensionDetailCount"] == 0
    assert "tag-1" in html and "tagdim-1" in html
    assert "const DATA=" in html and ",TREE=" in html
    assert "统一标签目录" in html
    assert 'class="badge dim">维度' in html
    assert 'class="badge tag">标签' in html
    assert "类型（持仓/组合）" in html
    assert "类型：持仓" in html
    assert DIMENSION_CATALOG_MISSING in html
    assert "customer_dim" in html
    assert "SQL格式化" in html
    assert "安全等级" in html and "2级" in html
    assert "是否复合标签维度" in html and "是否用于组合筛选" in html
    assert DIMENSION_CATALOG_MISSING in html
    assert DIMENSION_NOT_IN_SNAPSHOT in html
    assert "highlight();render()" not in html
    assert "el.dataset.kind===kind&&el.dataset.id===id" in html
    assert "维度管理列表" in html and "关系补充详情" in html
    assert "管理列表收录" in html
    assert 'id="tagsTab"' not in html and 'id="dimsTab"' not in html
    assert 'id="expand"' not in html
    assert "getElementById('expand')" not in html
    assert "['打标调度ID',taskIds(r.markingTaskIds)]" in html
    assert "['系统标签调度ID',taskIds(r.systemTagTaskIds)]" in html
    assert "function taskIds(v)" in html and "'未配置'" in html
    assert "ID_ONLY（未采集任务详情/运行记录）" in html
    assert "任务 ID 不代表任务详情、执行结果或授权" in html
    dimension_source = snapshot / "tag-dimensions.jsonl"
    assert projection["source"]["tagDimensionsPath"] == str(dimension_source)
    assert projection["source"]["tagDimensionsSha256"] == hashlib.sha256(dimension_source.read_bytes()).hexdigest()
    assert projection["taskEvidence"] == {"status": "ID_ONLY", "workflowRecordsFetched": 0}
    assert "'<h3>关联标签</h3>'" not in html
    scripts = re.findall(r"<script>(.*?)</script>", html, flags=re.DOTALL)
    script_path = tmp_path / "generated-tag-catalog.js"
    script_path.write_text("\n".join(scripts), encoding="utf-8")
    subprocess.run(["node", "--check", str(script_path)], check=True, capture_output=True, text=True)
    task_ids_function = re.search(r"function taskIds\(v\).*?(?=function links)", html).group(0)
    runtime_check = task_ids_function + "\nconsole.log(JSON.stringify([taskIds(),taskIds(null),taskIds(''),taskIds('-'),taskIds([]),taskIds(['','-']),taskIds(['245549','']),taskIds('245550')]))"
    rendered = subprocess.run(
        ["node", "-e", runtime_check], check=True, capture_output=True, text=True, encoding="utf-8"
    )
    assert json.loads(rendered.stdout) == ["未配置"] * 6 + ["245549", "245550"]


def test_tag_tree_uses_cataloged_dimension_then_tag_catalog_then_missing():
    dimensions = [
        _row("dim-good", "分类_客户"),
        _row("dim-blank", "-"),
    ]
    tags = [
        {"tagId": "tag-mixed", "tagName": "mixed", "catalogPath": "-"},
        {"tagId": "tag-fallback", "tagName": "fallback", "catalogPath": "分类_产品"},
        {"tagId": "tag-missing", "tagName": "missing", "catalogPath": "-"},
        {"tagId": "tag-absent", "tagName": "absent", "catalogPath": "-"},
        {"tagId": "tag-unlinked", "tagName": "unlinked", "catalogPath": "-"},
    ]
    relations = {
        "tag-mixed": [
            {"tagId": "tag-mixed", "tagDimId": "dim-blank", "tagDimNameFromTag": "blank"},
            {"tagId": "tag-mixed", "tagDimId": "dim-good", "tagDimNameFromTag": "good"},
        ],
        "tag-fallback": [{"tagId": "tag-fallback", "tagDimId": "dim-blank", "tagDimNameFromTag": "blank"}],
        "tag-missing": [{"tagId": "tag-missing", "tagDimId": "dim-blank", "tagDimNameFromTag": "blank"}],
        "tag-absent": [{"tagId": "tag-absent", "tagDimId": "dim-absent", "tagDimNameFromTag": "absent"}],
    }

    tree = _tag_value_tree(dimensions, {"tags": tags, "tagToDim": relations})

    def ids(node):
        found = set(node["tagIds"])
        for child in node["children"]:
            found.update(ids(child))
        return found

    by_type = {child["name"]: child for child in tree["children"]}
    assert set(by_type) == {TYPE_NOT_CAPTURED, "类型：持仓"}
    by_name = {child["name"]: child for child in by_type[TYPE_NOT_CAPTURED]["children"]}
    assert ids(by_name["客户"]) == {"tag-mixed"}
    assert ids(by_name["产品"]) == {"tag-fallback"}
    assert ids(by_name[DIMENSION_CATALOG_MISSING]) == {"tag-missing", "tag-unlinked"}
    assert ids(by_name[DIMENSION_NOT_IN_SNAPSHOT]) == {"tag-absent"}
    assert by_name[DIMENSION_CATALOG_MISSING]["tagIds"] == []
    assert any(child["name"] == f"维度：{RELATION_NOT_CAPTURED}" for child in by_name[DIMENSION_CATALOG_MISSING]["children"])


def test_unified_tree_reuses_one_tag_and_keeps_same_name_dimensions_distinct():
    dimensions = [
        {**_row("dim-a", "分类_客户"), "tagDimName": "同名维度"},
        {**_row("dim-b", "分类_客户"), "tagDimName": "同名维度"},
    ]
    tags = [{"tagId": "tag-shared", "tagName": "shared", "catalogPath": "-"}]
    relations = {
        "tag-shared": [
            {"tagId": "tag-shared", "tagDimId": "dim-a"},
            {"tagId": "tag-shared", "tagDimId": "dim-b"},
        ]
    }

    tree = _tag_value_tree(dimensions, {"tags": tags, "tagToDim": relations})

    def entries(node):
        found = list(node["tagIds"])
        for child in node["children"]:
            found.extend(entries(child))
        return found

    assert entries(tree).count("tag-shared") == 2
    dimension_nodes = []

    def collect_dimensions(node):
        if node.get("nodeKind") == "dimension":
            dimension_nodes.append(node)
        for child in node["children"]:
            collect_dimensions(child)

    collect_dimensions(tree)
    same_name = [node for node in dimension_nodes if node["name"] == "维度：同名维度"]
    assert len(same_name) == 4  # each object also retains its own platform-type placement
    assert [tuple(node["tagDimIds"]) for node in same_name].count(("dim-a",)) == 2
    assert [tuple(node["tagDimIds"]) for node in same_name].count(("dim-b",)) == 2
    assert {tuple(node["tagDimIds"]) for node in same_name if node["tagIds"]} == {("dim-a",), ("dim-b",)}
    assert all(len(node["tagDimIds"]) <= 1 for node in dimension_nodes)


def test_tag_tree_uses_type_code_before_missing_catalog():
    dimensions = [{**_row("dim-holding", "-"), "tagClassCode": "1", "tagClassName": "1"}]
    tags = [{
        "tagId": "tag-holding",
        "tagName": "holding",
        "tagTypeCode": "1",
        "tagTypeName": "标签",
        "catalogPath": "-",
    }]
    relations = {
        "tag-holding": [{"tagId": "tag-holding", "tagDimId": "dim-holding"}],
    }

    tree = _tag_value_tree(dimensions, {"tags": tags, "tagToDim": relations})

    holding = next(child for child in tree["children"] if child["name"] == "类型：持仓")
    missing = next(child for child in holding["children"] if child["name"] == DIMENSION_CATALOG_MISSING)
    assert missing["tagIds"] == []
    assert missing["children"][0]["tagDimIds"] == ["dim-holding"]
    assert missing["children"][0]["tagIds"] == ["tag-holding"]


def test_dimension_only_projection_does_not_invent_tag_values(tmp_path):
    snapshot = _snapshot(tmp_path, [_row("tagdim-1")])
    result = build_tag_catalog(snapshot, tmp_path / "dimension-output")
    projection = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
    assert projection["schemaVersion"] == "tag-catalog-review-v1"
    assert "tagValueCount" not in projection


def test_missing_relation_file_keeps_an_explicit_dimension_evidence_node(tmp_path):
    snapshot = _snapshot(
        tmp_path,
        [_row("tagdim-1", "分类_客户")],
        tags=[{"tagId": "tag-1", "tagName": "客户标签", "catalogPath": "分类_客户"}],
    )
    (snapshot / "tag-value-dimension-links.jsonl").unlink()

    result = build_tag_catalog(snapshot, tmp_path / "missing-links-output")
    html = Path(result["page"]).read_text(encoding="utf-8")

    assert f'"name":"维度：{RELATION_NOT_CAPTURED}","nodeKind":"dimension"' in html


def test_snapshot_id_cannot_escape_output_root(tmp_path):
    snapshot = _snapshot(tmp_path, [_row("tagdim-1")])
    manifest_path = snapshot / "detail-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["snapshotId"] = "..\\escaped"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="safe path component"):
        build_tag_catalog(snapshot, tmp_path / "output")
