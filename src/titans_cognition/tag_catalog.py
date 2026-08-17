"""Deterministic, read-only tag catalog projection from an SZData snapshot."""

from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

import sqlglot


UNCATALOGUED = "目录缺失（源快照未提供目录）"
DIMENSION_CATALOG_MISSING = "未分类（源快照）"
DIMENSION_NOT_IN_SNAPSHOT = "关联维度不在当前快照"
RELATION_NOT_CAPTURED = "未采集关联维度"
TYPE_NOT_CAPTURED = "类型未采集"
UNAVAILABLE = "未采集/不可用（源快照没有该字段或文件）"
SQL_STATUSES = {"FOUND", "GENERATED_LOCAL"}


def _without_expand_all_control(page_html: str) -> str:
    page_html = re.sub(r'<button id="expand">[^<]*</button>', "", page_html)
    return page_html.replace(
        "document.getElementById('expand').onclick=()=>"
        "treeEl.querySelectorAll('details').forEach(x=>x.open=true);",
        "",
    )


def _format_sql(sql_text: str) -> tuple[str, str]:
    """Format only the reader projection; always retain the raw source text."""
    if not sql_text.strip():
        return "", "UNAVAILABLE"
    try:
        return sqlglot.parse_one(sql_text, read="oracle").sql(pretty=True), "FORMATTED"
    except Exception:
        return sql_text, "FORMAT_FAILED"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _task_ids(value: object) -> list[str]:
    """Return stable unique task IDs from normalized or raw snapshot fields."""
    if isinstance(value, list):
        candidates = [item.get("taskId") if isinstance(item, dict) else item for item in value]
    else:
        text = _text(value).strip()
        for separator in ("、", ","):
            text = text.replace(separator, "/")
        candidates = text.split("/")
    result: list[str] = []
    for candidate in candidates:
        task_id = _text(candidate).strip()
        if task_id and task_id != "-" and task_id not in result:
            result.append(task_id)
    return result


def _catalog_parts(value: object) -> tuple[str, ...]:
    """Parse the observed underscore-delimited SZData catalog path.

    A path without the delimiter is retained as one node; an absent path is
    explicitly grouped instead of being inferred from the tag name.
    """
    raw = _text(value).strip()
    if not raw or raw == "-":
        return (UNCATALOGUED,)
    parts = tuple(part.strip() for part in raw.split("_") if part.strip())
    return parts or (UNCATALOGUED,)


def _display_catalog_parts(value: object) -> tuple[str, ...]:
    """Remove only the platform's redundant leading catalog container."""
    parts = _catalog_parts(value)
    if len(parts) > 1 and parts[0] == "分类":
        return parts[1:]
    return parts


def _platform_type_name(name: object, code: object) -> str:
    """Normalize the platform's holding/combination code without mutating source files."""
    code_text = _text(code).strip()
    name_text = _text(name).strip()
    normalized = code_text if code_text in {"1", "2"} else name_text
    if normalized == "1":
        return "持仓"
    if normalized == "2":
        return "组合"
    return name_text if name_text and name_text != "-" else TYPE_NOT_CAPTURED


def _resolve_sql(snapshot_dir: Path, row: dict[str, Any]) -> tuple[Path | None, str]:
    declared = _text(row.get("sqlFile")).strip()
    status = _text(row.get("sqlEvidenceStatus")).strip() or "UNAVAILABLE"
    if not declared:
        return None, "UNAVAILABLE"
    candidate = Path(declared)
    if not candidate.is_absolute():
        candidate = snapshot_dir / candidate
    try:
        resolved = candidate.resolve()
        resolved.relative_to(snapshot_dir.resolve())
    except (OSError, ValueError):
        return None, "INVALID_PATH"
    if not resolved.is_file():
        return None, "UNAVAILABLE"
    expected = _text(row.get("sqlSha256")).strip()
    if expected and _sha256(resolved) != expected:
        try:
            normalized = resolved.read_text(encoding="utf-8").lstrip("\ufeff").strip()
        except (OSError, UnicodeError):
            return resolved, "HASH_MISMATCH"
        normalized_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        if normalized_hash != expected:
            return resolved, "HASH_MISMATCH"
    return resolved, status


def _read_snapshot(snapshot_dir: Path) -> tuple[str, dict[str, Any], list[dict[str, Any]], Path]:
    snapshot_dir = snapshot_dir.resolve()
    manifest_path = snapshot_dir / "detail-manifest.json"
    records_path = snapshot_dir / "dimension-details.jsonl"
    tree_path = snapshot_dir / "catalog-tree.json"
    for path in (manifest_path, records_path, tree_path):
        if not path.is_file():
            raise ValueError(f"tag snapshot input not found: {path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        tree_payload = json.loads(tree_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("cannot read tag snapshot manifest or catalog tree") from exc
    if not isinstance(manifest, dict):
        raise ValueError("tag snapshot manifest must be an object")
    tree_catalog_paths = {
        _text(item.get("objectId")).strip(): _text(item.get("path")).strip()
        for item in (tree_payload.get("catalogTree", []) if isinstance(tree_payload, dict) else [])
        if isinstance(item, dict)
        and _text(item.get("objectId")).strip()
        and _text(item.get("path")).strip()
    }
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        lines = records_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"cannot read tag detail JSONL: {records_path}") from exc
    catalog_paths: dict[str, str] = {}
    catalog_rows: dict[str, dict[str, Any]] = {}
    listed_dimension_ids: set[str] = set()
    catalog_records_path = snapshot_dir / "tag-dimensions.jsonl"
    if catalog_records_path.is_file():
        for catalog_row in _read_jsonl(catalog_records_path):
            catalog_id = _text(catalog_row.get("tagDimId")).strip()
            if catalog_id:
                listed_dimension_ids.add(catalog_id)
                catalog_rows[catalog_id] = catalog_row
            catalog_path = _text(catalog_row.get("catalogPath")).strip()
            if catalog_id and catalog_path and catalog_path != "-":
                catalog_paths[catalog_id] = catalog_path
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid tag detail JSONL at line {line_number}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"tag detail line {line_number} must be an object")
        tag_id = _text(row.get("tagDimId")).strip()
        if not tag_id:
            raise ValueError(f"tag detail line {line_number} has no tagDimId")
        if tag_id in seen:
            raise ValueError(f"duplicate tagDimId: {tag_id}")
        seen.add(tag_id)
        row = dict(row)
        row["tagDimId"] = tag_id
        list_row = catalog_rows.get(tag_id, {})
        list_raw = list_row.get("_raw") if isinstance(list_row.get("_raw"), dict) else {}

        def supplement(field: str, *candidates: object) -> None:
            if _text(row.get(field)).strip() not in {"", "-"}:
                return
            for candidate in candidates:
                if _text(candidate).strip() not in {"", "-"}:
                    row[field] = candidate
                    return

        supplement("tagDimEnglishName", list_row.get("tagDimEnglishName"), list_raw.get("tagDimNo"))
        supplement("statusCode", list_row.get("statusCode"), list_raw.get("auditState"))
        supplement("statusName", list_row.get("statusName"))
        if _text(row.get("statusName")).strip() == _text(row.get("statusCode")).strip():
            row["statusName"] = "-"
        supplement("isCompositeTagDimension", list_row.get("isCompositeTagDimension"))
        supplement("isForGroupFiltering", list_row.get("isForGroupFiltering"))
        if _text(row.get("isForGroupFiltering")).strip() in {"", "-"} and list_raw.get("grpFltFlag") is not None:
            row["isForGroupFiltering"] = "Y" if str(list_raw["grpFltFlag"]).strip().lower() in {"1", "true", "y"} else "N"
        supplement("securityLevelCode", list_row.get("securityLevelCode"), list_raw.get("opsLvl"))
        supplement("securityLevelName", list_row.get("securityLevelName"))
        if _text(row.get("securityLevelName")).strip() in {"", "-"} and list_raw.get("opsLvl") is not None:
            row["securityLevelName"] = f"{list_raw['opsLvl']}级"
        supplement("resultDatabase", list_row.get("resultDatabase"), list_raw.get("dbName"))
        supplement("resultTable", list_row.get("resultTable"), list_raw.get("engTblName"))
        supplement("description", list_row.get("description"), list_raw.get("tagDesc"))
        for field, raw_field in (
            ("markingTaskIds", "markingTask"),
            ("systemTagTaskIds", "newTagingTask"),
        ):
            task_ids = _task_ids(row.get(field))
            if not task_ids:
                task_ids = _task_ids(list_row.get(field)) or _task_ids(list_raw.get(raw_field))
            row[field] = "/".join(task_ids) if task_ids else "-"
        row["tagClassName"] = _platform_type_name(row.get("tagClassName"), row.get("tagClassCode"))
        row["inDimensionList"] = tag_id in listed_dimension_ids
        if _text(row.get("catalogPath")).strip() in {"", "-"} and tag_id in tree_catalog_paths:
            row["catalogPath"] = tree_catalog_paths[tag_id]
            row["catalogPathSource"] = "catalog-tree"
        elif _text(row.get("catalogPath")).strip() in {"", "-"} and tag_id in catalog_paths:
            row["catalogPath"] = catalog_paths[tag_id]
            row["catalogPathSource"] = "tag-dimensions"
        row["catalogParts"] = list(_catalog_parts(row.get("catalogPath")))
        sql_path, sql_status = _resolve_sql(snapshot_dir, row)
        row["sqlResolvedPath"] = str(sql_path) if sql_path else ""
        row["sqlResolvedStatus"] = sql_status
        if sql_path and sql_status in SQL_STATUSES:
            raw_sql = sql_path.read_text(encoding="utf-8", errors="replace")
            row["sqlRawText"] = raw_sql
            row["sqlText"], row["sqlFormatStatus"] = _format_sql(raw_sql)
        else:
            row["sqlRawText"] = ""
            row["sqlText"] = ""
            row["sqlFormatStatus"] = "UNAVAILABLE"
        rows.append(row)
    declared = manifest.get("dimensionDetailsCount")
    if declared is not None and int(declared) != len(rows):
        raise ValueError(f"tag detail count mismatch: manifest={declared}, jsonl={len(rows)}")
    snapshot_id = _text(manifest.get("snapshotId")).strip() or snapshot_dir.name
    if snapshot_id in {".", ".."} or Path(snapshot_id).name != snapshot_id or any(char in snapshot_id for char in ("/", "\\", ":")):
        raise ValueError("snapshotId must be a safe path component")
    return snapshot_id, manifest, rows, records_path


def _tree(rows: list[dict[str, Any]]) -> dict[str, Any]:
    root: dict[str, Any] = {"name": "标签目录", "children": {}, "tagDimIds": []}
    for row in rows:
        type_name = _platform_type_name(row.get("tagClassName"), row.get("tagClassCode"))
        type_label = TYPE_NOT_CAPTURED if type_name == TYPE_NOT_CAPTURED else f"类型：{type_name}"
        node = root["children"].setdefault(type_label, {"name": type_label, "children": {}, "tagDimIds": []})
        catalog_parts = list(_display_catalog_parts(row.get("catalogPath")))
        if catalog_parts == [UNCATALOGUED]:
            catalog_parts = [DIMENSION_CATALOG_MISSING]
        for part in catalog_parts:
            node = node["children"].setdefault(part, {"name": part, "children": {}, "tagDimIds": []})
        node["tagDimIds"].append(row["tagDimId"])

    def freeze(node: dict[str, Any]) -> dict[str, Any]:
        evidence_gaps = {DIMENSION_CATALOG_MISSING, DIMENSION_NOT_IN_SNAPSHOT, RELATION_NOT_CAPTURED}
        child_names = sorted(node["children"], key=lambda name: (name in evidence_gaps, name))
        return {
            "name": node["name"],
            "children": [freeze(node["children"][key]) for key in child_names],
            "tagDimIds": sorted(node["tagDimIds"]),
        }

    return freeze(root)


def _page(snapshot_id: str, manifest: dict[str, Any], rows: list[dict[str, Any]], records_hash: str) -> str:
    safe_rows = []
    for row in rows:
        safe_rows.append({key: value for key, value in row.items() if key != "sqlResolvedPath"})
    payload = json.dumps(safe_rows, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    tree = json.dumps(_tree(rows), ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    meta = json.dumps({"snapshotId": snapshot_id, "recordCount": len(rows), "recordsSha256": records_hash}, ensure_ascii=False)
    unavailable = json.dumps(UNAVAILABLE, ensure_ascii=False)
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>标签目录树 · {html.escape(snapshot_id)}</title>
<style>:root{{--ink:#152238;--muted:#60708a;--line:#dbe4f0;--soft:#f4f8fc;--accent:#1769aa;--warn:#9a5b00}}*{{box-sizing:border-box}}body{{margin:0;background:#eef3f9;color:var(--ink);font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif}}.page{{max-width:1500px;margin:28px auto;padding:0 20px}}header{{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;margin-bottom:18px}}h1{{margin:0 0 5px;font-size:28px}}.sub,.muted{{color:var(--muted)}}.meta{{padding:10px 14px;border:1px solid #cbd9e9;background:#f8fbff;border-radius:12px;white-space:nowrap}}.toolbar{{display:flex;gap:10px;margin-bottom:14px}}input{{flex:1;border:1px solid #c7d5e5;border-radius:10px;padding:11px 13px;font:inherit}}button{{border:1px solid #c7d5e5;background:#fff;border-radius:9px;padding:10px 13px;cursor:pointer}}.summary{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}}.pill{{background:#fff;border:1px solid var(--line);border-radius:999px;padding:5px 11px}}.pill strong{{color:var(--accent)}}.layout{{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(380px,.75fr);gap:16px}}.panel{{background:#fff;border:1px solid var(--line);border-radius:14px;overflow:hidden}}.panel-head{{padding:15px 18px;border-bottom:1px solid var(--line);font-weight:700}}.tree{{padding:12px 14px;max-height:calc(100vh - 230px);overflow:auto}}details{{margin:3px 0 3px 12px}}summary{{cursor:pointer;padding:7px 8px;border-radius:8px;display:flex;gap:8px}}summary:hover{{background:var(--soft)}}.name{{flex:1;overflow-wrap:anywhere}}.count{{color:var(--muted);font-size:12px}}.list{{margin:3px 0 8px 27px}}.tag{{display:flex;gap:10px;padding:8px 10px;margin:4px 0;border:1px solid #e3eaf2;border-radius:9px;cursor:pointer}}.tag:hover,.tag.selected{{border-color:#79b3dc;background:#e8f3fc}}.tag-name{{flex:1;overflow-wrap:anywhere}}.detail{{position:sticky;top:15px;padding:18px;max-height:calc(100vh - 230px);overflow:auto}}.detail h2{{margin:0 0 4px;font-size:21px;overflow-wrap:anywhere}}.row{{padding:9px 0;border-bottom:1px solid #edf1f5;white-space:pre-wrap;overflow-wrap:anywhere}}.row strong{{display:inline-block;min-width:125px;color:#49617d}}.sql{{margin-top:16px;padding:12px;background:#101923;color:#e6edf5;border-radius:9px;white-space:pre-wrap;overflow:auto;max-height:420px;font:12px/1.5 Consolas,monospace}}.note{{margin-top:15px;padding:10px 12px;background:#fff7e8;border:1px solid #f0d8a7;border-radius:9px;color:var(--warn)}}.empty{{padding:25px;color:var(--muted);text-align:center}}footer{{margin:16px 2px;color:#73829a;font-size:12px;overflow-wrap:anywhere}}@media(max-width:950px){{header{{display:block}}.layout{{grid-template-columns:1fr}}.detail{{position:static;max-height:none}}.tree{{max-height:none}}}}</style></head><body><main class="page"><header><div><h1>标签目录树</h1><div class="sub">按平台目录浏览标签维度，详情展示源字段和维度 SQL 证据。</div></div><div class="meta">快照：{html.escape(snapshot_id)}<br>状态：{html.escape(_text(manifest.get("status")) or "UNKNOWN")}</div></header><div class="toolbar"><input id="search" placeholder="搜索标签名称、ID、目录、状态或描述"><button id="expand">全部展开</button><button id="collapse">全部折叠</button><button id="clear">清空</button></div><div class="summary"><span class="pill">快照总数：<strong id="total">{len(rows):,}</strong></span><span class="pill">当前可见：<strong id="visible">{len(rows):,}</strong></span><span class="pill">可见目录节点：<strong id="nodes">0</strong></span></div><div class="layout"><section class="panel"><div class="panel-head">标签目录</div><div id="tree" class="tree"></div></section><aside class="panel detail" id="detail"><div class="empty">点击左侧标签查看详情</div></aside></div><footer>目录来自标签快照字段，不能替代业务分类。调度任务 SQL 未纳入本投影。dimension-details.jsonl sha256：{records_hash}</footer></main><script>
const ROWS={payload};const TREE={tree};const META={meta};const UNAVAILABLE={unavailable};const byId=new Map(ROWS.map(row=>[row.tagDimId,row]));const treeEl=document.getElementById('tree'),searchEl=document.getElementById('search'),detailEl=document.getElementById('detail'),selected={{id:null}};const fmt=new Intl.NumberFormat('zh-CN');const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
function matches(row){{const q=searchEl.value.trim().toLocaleLowerCase();if(!q)return true;return [row.tagDimId,row.tagDimName,row.tagDimEnglishName,row.statusName,row.description,row.catalogPath].join(' ').toLocaleLowerCase().includes(q)}}function countNode(node,visible){{return node.tagDimIds.filter(id=>visible.has(id)).length+(node.children||[]).reduce((n,c)=>n+countNode(c,visible),0)}}function nodeHtml(node,visible,depth){{const count=countNode(node,visible);if(!count)return '';const children=(node.children||[]).filter(c=>countNode(c,visible));const own=node.tagDimIds.map(id=>byId.get(id)).filter(r=>r&&visible.has(r.tagDimId));let body=children.map(c=>nodeHtml(c,visible,depth+1)).join('');if(own.length)body+='<div class="list">'+own.map(r=>`<div class="tag ${{selected.id===r.tagDimId?'selected':''}}" data-id="${{esc(r.tagDimId)}}"><span class="tag-name">${{esc(r.tagDimName||r.tagDimEnglishName||'(未命名)')}}</span><span class="muted">${{esc([r.statusName,r.realTimeTypeName].filter(Boolean).join(' · '))}}</span></div>`).join('')+'</div>';return `<details ${{searchEl.value.trim()||depth<2?'open':''}}><summary><span class="name">${{esc(node.name)}}</span><span class="count">${{fmt.format(count)}} 个标签</span></summary>${{body}}</details>`}}function countVisibleNodes(node,visible){{return countNode(node,visible)?1:0+(node.children||[]).reduce((n,c)=>n+countVisibleNodes(c,visible),0)}}function render(){{const visible=new Set(ROWS.filter(matches).map(r=>r.tagDimId));treeEl.innerHTML=nodeHtml(TREE,visible,0)||'<div class="empty">没有匹配的标签</div>';document.getElementById('visible').textContent=fmt.format(visible.size);document.getElementById('nodes').textContent=fmt.format(countVisibleNodes(TREE,visible));treeEl.querySelectorAll('[data-id]').forEach(el=>el.onclick=()=>showDetail(el.dataset.id))}}function val(v){{return v===undefined||v===null||v===''||v==='-'?UNAVAILABLE:String(v)}}function showDetail(id){{const r=byId.get(id);if(!r)return;selected.id=id;const fields=[['标签ID',r.tagDimId],['英文名称',r.tagDimEnglishName],['类别',r.tagClassName],['实时类型',r.realTimeTypeName],['状态',r.statusName],['更新方式',r.tagIdUpdateMethodName],['结果数据库',r.resultDatabase],['结果表',r.resultTable],['目录',r.catalogPath],['描述',r.description],['详情证据',r.detailEvidenceStatus],['SQL证据',r.sqlResolvedStatus]];detailEl.innerHTML=`<h2>${{esc(val(r.tagDimName))}}</h2><div class="muted">当前快照字段 · 选择其他标签可切换</div>${{fields.map(([k,v])=>`<div class="row"><strong>${{esc(k)}}：</strong>${{esc(val(v))}}</div>`).join('')}}<div class="row"><strong>SQL文件：</strong>${{esc(val(r.sqlFile))}}</div>${{r.sqlText?`<div class="sql">${{esc(r.sqlText)}}</div>`:''}}<div class="note">SQL证据状态为 GENERATED_LOCAL 时，仅表示本地生成文件，不代表平台原始调度 SQL。调度任务 SQL 未纳入。</div>`;render()}}searchEl.oninput=render;document.getElementById('clear').onclick=()=>{{searchEl.value='';render()}};document.getElementById('expand').onclick=()=>treeEl.querySelectorAll('details').forEach(x=>x.open=true);document.getElementById('collapse').onclick=()=>treeEl.querySelectorAll('details').forEach(x=>x.open=false);render();</script></body></html>'''


def _add_sql_highlighting(page: str) -> str:
    """Add display-only SQL highlighting without changing the raw SQL payload."""
    script = r'''<style>
.sql-highlight-label{margin-top:14px;color:#73829a;font-size:12px}
.sql .sql-keyword{color:#7dd3fc}.sql .sql-string{color:#fbbf24}.sql .sql-comment{color:#94a3b8}.sql .sql-number{color:#c4b5fd}
</style><script>
(function(){
  const sqlKeywords=/^(select|from|where|join|left|right|full|inner|outer|cross|on|and|or|not|in|is|null|as|case|when|then|else|end|group|by|order|having|union|all|distinct|with|insert|into|update|delete|create|alter|drop|table|view|over|partition|row_number|count|sum|min|max|avg|decode|nvl|coalesce|exists)$/i;
  const escapeSql=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function highlightSql(raw){
    const token=/\/\*[\s\S]*?\*\/|--[^\n]*|'(?:''|[^'])*'|"(?:""|[^"])*"|\b\d+(?:\.\d+)?\b|\b[A-Za-z_][A-Za-z0-9_$#]*\b/g;
    return String(raw??'').replace(token,match=>{
      const kind=match.startsWith('--')||match.startsWith('/*')?'sql-comment':(match.startsWith("'")||match.startsWith('"')?'sql-string':(/^\d/.test(match)?'sql-number':(sqlKeywords.test(match)?'sql-keyword':'')));
      return kind?'<span class="'+kind+'">'+escapeSql(match)+'</span>':escapeSql(match);
    });
  }
  function apply(){
    document.querySelectorAll('.sql:not([data-sql-highlighted])').forEach(box=>{
      const raw=box.textContent||'';
      box.innerHTML=highlightSql(raw);
      box.dataset.sqlHighlighted='true';
      const label=document.createElement('div');
      label.className='sql-highlight-label';
      label.textContent='SQL 已格式化并高亮（仅展示层处理，原始 SQL 保留）';
      box.parentNode.insertBefore(label,box);
    });
  }
  new MutationObserver(apply).observe(document.getElementById('detail'),{childList:true,subtree:true});
  apply();
})();
</script>'''
    return page.replace("</body>", script + "</body>")


def _tag_value_tree(dimensions: list[dict[str, Any]], dual: dict[str, Any]) -> dict[str, Any]:
    """Project tags through the strongest available catalog evidence."""
    root: dict[str, Any] = {"name": "标签目录", "children": {}, "tagIds": [], "tagDimIds": []}
    dimensions_by_id = {row["tagDimId"]: row for row in dimensions}

    for dimension in dimensions:
        type_name = _platform_type_name(dimension.get("tagClassName"), dimension.get("tagClassCode"))
        type_label = TYPE_NOT_CAPTURED if type_name == TYPE_NOT_CAPTURED else f"类型：{type_name}"
        node = root["children"].setdefault(
            type_label,
            {"name": type_label, "children": {}, "tagIds": [], "tagDimIds": []},
        )
        catalog_parts = _display_catalog_parts(dimension.get("catalogPath"))
        if catalog_parts == (UNCATALOGUED,):
            catalog_parts = (DIMENSION_CATALOG_MISSING,)
        for part in catalog_parts:
            node = node["children"].setdefault(
                part,
                {"name": part, "children": {}, "tagIds": [], "tagDimIds": []},
            )
        label = f"维度：{dimension.get('tagDimName') or dimension['tagDimId']}"
        dimension_key = f"{label}｜{dimension['tagDimId']}"
        node = node["children"].setdefault(
            dimension_key,
            {"name": label, "nodeKind": "dimension", "children": {}, "tagIds": [], "tagDimIds": []},
        )
        node["tagDimIds"].append(dimension["tagDimId"])

    for tag in dual["tags"]:
        type_name = _platform_type_name(tag.get("tagTypeName"), tag.get("tagTypeCode"))
        type_label = TYPE_NOT_CAPTURED if type_name == TYPE_NOT_CAPTURED else f"类型：{type_name}"
        relations = dual["tagToDim"].get(tag["tagId"], [])
        linked = []
        for relation in relations:
            dimension = dimensions_by_id.get(relation["tagDimId"], {})
            linked.append(
                {
                    "tagDimId": relation["tagDimId"],
                    "tagDimName": dimension.get("tagDimName") or relation.get("tagDimNameFromTag") or relation["tagDimId"],
                    "catalogPath": dimension.get("catalogPath") or "-",
                    "dimensionKnown": bool(dimension),
                }
            )

        cataloged = [row for row in linked if _text(row.get("catalogPath")).strip() not in {"", "-"}]
        own_catalog = _text(tag.get("catalogPath")).strip()
        if cataloged:
            targets = cataloged
        elif own_catalog and own_catalog != "-":
            targets = [{**row, "catalogPath": own_catalog} for row in linked] or [{**tag, "catalogPath": own_catalog}]
        else:
            known = [row for row in linked if row["dimensionKnown"]]
            if known:
                targets = [{**row, "catalogPath": DIMENSION_CATALOG_MISSING} for row in known]
            elif linked:
                targets = [{**row, "catalogPath": DIMENSION_NOT_IN_SNAPSHOT} for row in linked]
            else:
                targets = [{**tag, "catalogPath": DIMENSION_CATALOG_MISSING}]

        for target in targets:
            node = root["children"].setdefault(
                type_label,
                {"name": type_label, "children": {}, "tagIds": [], "tagDimIds": []},
            )
            for part in _display_catalog_parts(target.get("catalogPath")):
                node = node["children"].setdefault(part, {"name": part, "children": {}, "tagIds": [], "tagDimIds": []})
            dimension_id = _text(target.get("tagDimId")).strip()
            if dimension_id:
                dimension_name = _text(target.get("tagDimName")).strip() or dimension_id
                label = f"维度：{dimension_name}"
                dimension_key = f"{label}｜{dimension_id}"
                node = node["children"].setdefault(
                    dimension_key,
                    {"name": label, "nodeKind": "dimension", "children": {}, "tagIds": [], "tagDimIds": []},
                )
                if target.get("dimensionKnown"):
                    node["tagDimIds"].append(dimension_id)
            else:
                label = f"维度：{RELATION_NOT_CAPTURED}"
                node = node["children"].setdefault(
                    label,
                    {"name": label, "nodeKind": "dimension", "children": {}, "tagIds": [], "tagDimIds": []},
                )
            node["tagIds"].append(tag["tagId"])

    def freeze(node: dict[str, Any]) -> dict[str, Any]:
        evidence_gaps = {DIMENSION_CATALOG_MISSING, DIMENSION_NOT_IN_SNAPSHOT, RELATION_NOT_CAPTURED}
        child_names = sorted(node["children"], key=lambda name: (name in evidence_gaps, name))
        return {
            "name": node["name"],
            "nodeKind": node.get("nodeKind"),
            "children": [freeze(node["children"][key]) for key in child_names],
            "tagIds": sorted(set(node["tagIds"])),
            "tagDimIds": sorted(set(node["tagDimIds"])),
        }

    return freeze(root)


def _unified_dual_page(snapshot_id: str, manifest: dict[str, Any], dimensions: list[dict[str, Any]], dual: dict[str, Any], records_hash: str) -> str:
    safe_dimensions = [{key: value for key, value in row.items() if key != "sqlResolvedPath"} for row in dimensions]
    listed_count = sum(bool(row.get("inDimensionList")) for row in dimensions)
    relation_only_count = len(dimensions) - listed_count
    payload = json.dumps(
        {"tags": dual["tags"], "dimensions": safe_dimensions, "tagToDim": dual["tagToDim"], "dimToTag": dual["dimToTag"]},
        ensure_ascii=False,
        separators=(",", ":"),
    ).replace("<", "\\u003c")
    tree = json.dumps(_tag_value_tree(dimensions, dual), ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return rf'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>标签目录树 · {html.escape(snapshot_id)}</title><style>
:root{{--ink:#152238;--muted:#60708a;--line:#dbe4f0;--soft:#f4f8fc;--accent:#1769aa;--dim:#8059a8;--dim-soft:#f5f0fb;--tag:#16857b;--tag-soft:#eef9f7;--warn:#9a5b00}}*{{box-sizing:border-box}}body{{margin:0;background:#eef3f9;color:var(--ink);font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif}}.page{{max-width:1600px;margin:28px auto;padding:0 20px}}header{{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;margin-bottom:18px}}h1{{margin:0 0 5px;font-size:28px}}.muted,.sub{{color:var(--muted)}}.meta{{padding:10px 14px;border:1px solid #cbd9e9;background:#f8fbff;border-radius:12px;white-space:nowrap}}.toolbar,.summary{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}}button,input{{border:1px solid #c7d5e5;border-radius:9px;padding:10px 13px;background:#fff;font:inherit}}button{{cursor:pointer}}input{{flex:1;min-width:240px}}.pill{{background:#fff;border:1px solid var(--line);border-radius:999px;padding:5px 11px}}.pill strong{{color:var(--accent)}}.legend{{display:flex;gap:8px;align-items:center;margin-left:auto}}.badge{{display:inline-block;border-radius:999px;padding:1px 7px;font-size:12px;font-weight:700}}.badge.dim{{color:var(--dim);background:var(--dim-soft)}}.badge.tag{{color:var(--tag);background:var(--tag-soft)}}.layout{{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(420px,.75fr);gap:16px}}.panel{{background:#fff;border:1px solid var(--line);border-radius:14px;overflow:hidden}}.panel-head{{display:flex;padding:15px 18px;border-bottom:1px solid var(--line);font-weight:700}}.tree{{padding:12px 14px;max-height:calc(100vh - 260px);overflow:auto}}details{{margin:3px 0 3px 12px}}summary{{cursor:pointer;padding:7px 8px;border-radius:8px;display:flex;gap:8px;align-items:center}}summary:hover{{background:var(--soft)}}summary.dimension{{border-left:3px solid var(--dim);background:var(--dim-soft)}}.name{{flex:1;overflow-wrap:anywhere}}.count{{color:var(--muted);font-size:12px}}.list{{margin:4px 0 8px 27px}}.tag-item{{display:flex;gap:10px;padding:8px 10px;margin:4px 0;border:1px solid #cfe7e3;border-left:3px solid var(--tag);border-radius:9px;background:var(--tag-soft);cursor:pointer}}.tag-item:hover,.tag-item.selected,summary.dimension.selected{{border-color:#64aaa2;background:#e1f4f1}}.item-name{{flex:1;overflow-wrap:anywhere}}.detail{{position:sticky;top:15px;padding:18px;max-height:calc(100vh - 260px);overflow:auto}}.detail h2{{margin:0 0 4px;font-size:21px;overflow-wrap:anywhere}}.row{{padding:9px 0;border-bottom:1px solid #edf1f5;white-space:pre-wrap;overflow-wrap:anywhere}}.row strong{{display:inline-block;min-width:140px;color:#49617d}}.link{{color:var(--accent);cursor:pointer;text-decoration:underline}}.sql{{margin-top:16px;padding:12px;background:#101923;color:#e6edf5;border-radius:9px;white-space:pre-wrap;overflow:auto;max-height:420px;font:12px/1.5 Consolas,monospace}}.sql-keyword{{color:#7dd3fc}}.sql-string{{color:#fbbf24}}.sql-comment{{color:#94a3b8}}.sql-number{{color:#c4b5fd}}.note{{margin-top:15px;padding:10px 12px;background:#fff7e8;border:1px solid #f0d8a7;border-radius:9px;color:var(--warn)}}.empty{{padding:25px;color:var(--muted);text-align:center}}footer{{margin:16px 2px;color:#73829a;font-size:12px;overflow-wrap:anywhere}}@media(max-width:950px){{header{{display:block}}.layout{{grid-template-columns:1fr}}.detail{{position:static;max-height:none}}.tree{{max-height:none}}}}
</style></head><body><main class="page"><header><div><h1>标签目录树</h1><div class="sub">目录、标签维度与标签统一浏览；对象身份和关联证据保持独立。</div></div><div class="meta">快照：{html.escape(snapshot_id)}<br>范围：{html.escape(dual["scope"])}<br>标签数据：{html.escape(dual["tagValueEvidence"])}</div></header><div class="toolbar"><input id="search" placeholder="搜索标签、维度、ID、目录、状态或生成条件"><button id="expand">全部展开</button><button id="collapse">全部折叠</button><button id="clear">清空</button></div><div class="summary"><span class="pill">标签：<strong>{dual["valuesCount"]:,}</strong></span><span class="pill">维度管理列表：<strong>{listed_count:,}</strong></span><span class="pill">关系补充详情：<strong>{relation_only_count:,}</strong></span><span class="pill">关联：<strong>{dual["relationCount"]:,}</strong></span><span class="pill">当前可见标签：<strong id="visibleTags">0</strong></span><span class="legend"><span class="badge dim">维度</span><span class="badge tag">标签</span></span></div><div class="layout"><section class="panel"><div class="panel-head">统一标签目录</div><div id="tree" class="tree"></div></section><aside class="panel detail" id="detail"><div class="empty">点击维度节点或标签记录查看详情</div></aside></div><footer>标签文件：{html.escape(dual["valuesPath"])}；维度列表文件：{html.escape(dual["dimensionsPath"])}；关联文件：{html.escape(dual["linksPath"] or "未采集")}；维度详情 sha256：{records_hash}<br>任务 ID 证据：ID_ONLY；任务运行记录采集数：{dual["workflowRecordsFetched"]}。任务 ID 不代表任务详情、执行结果或授权。SQL 只展示维度快照证据。</footer></main><script>
const DATA={payload},TREE={tree};const byTag=new Map(DATA.tags.map(x=>[x.tagId,x])),byDim=new Map(DATA.dimensions.map(x=>[x.tagDimId,x]));const tagToDim=new Map(Object.entries(DATA.tagToDim)),dimToTag=new Map(Object.entries(DATA.dimToTag));const selected={{kind:null,id:null}},treeEl=document.getElementById('tree'),detailEl=document.getElementById('detail'),searchEl=document.getElementById('search');const fmt=new Intl.NumberFormat('zh-CN');const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));const val=v=>v===undefined||v===null||v===''||v==='-'?'未采集/不可用':String(v);const text=r=>[r.tagId,r.tagName,r.tagDimId,r.tagDimName,r.tagDimEnglishName,r.catalogPath,r.statusName,r.generationCondition,r.description].join(' ').toLocaleLowerCase();
function visibleSets(){{const q=searchEl.value.trim().toLocaleLowerCase();if(!q)return {{tags:new Set(byTag.keys()),dims:new Set(byDim.keys())}};const tags=new Set(DATA.tags.filter(r=>text(r).includes(q)).map(r=>r.tagId)),dims=new Set(DATA.dimensions.filter(r=>text(r).includes(q)).map(r=>r.tagDimId));for(const id of [...tags])for(const link of tagToDim.get(id)||[])dims.add(link.tagDimId);for(const id of [...dims])for(const link of dimToTag.get(id)||[])tags.add(link.tagId);return {{tags,dims}}}}
function treePart(node,visible,depth){{const tags=new Set((node.tagIds||[]).filter(id=>visible.tags.has(id))),dims=new Set((node.tagDimIds||[]).filter(id=>visible.dims.has(id)));const children=[];for(const child of node.children||[]){{const part=treePart(child,visible,depth+1);if(part){{children.push(part.html);for(const id of part.tags)tags.add(id);for(const id of part.dims)dims.add(id)}}}}if(!tags.size&&!dims.size)return null;const dimId=(node.tagDimIds||[]).find(id=>visible.dims.has(id));const isDim=node.nodeKind==='dimension';const badge=isDim?'<span class="badge dim">'+(dimId?'维度':'维度证据')+'</span>':'';const summary='<summary class="'+(isDim?'dimension ':'')+(selected.kind==='dim'&&selected.id===dimId?'selected':'')+'"'+(dimId?' data-kind="dim" data-id="'+esc(dimId)+'"':'')+'>'+badge+'<span class="name">'+esc(isDim?node.name.replace(/^维度：/,''):node.name)+'</span><span class="count">'+(dims.size?fmt.format(dims.size)+' 维度 · ':'')+fmt.format(tags.size)+' 标签</span></summary>';const own=(node.tagIds||[]).filter(id=>visible.tags.has(id));const leaves=own.length?'<div class="list">'+own.map(id=>{{const r=byTag.get(id);return '<div class="tag-item '+(selected.kind==='tag'&&selected.id===id?'selected':'')+'" data-kind="tag" data-id="'+esc(id)+'"><span class="badge tag">标签</span><span class="item-name">'+esc(r?.tagName||id)+'</span><span class="muted">'+esc(id)+'</span></div>'}}).join('')+'</div>':'';const gap=['未分类（源快照）','关联维度不在当前快照','未采集关联维度'].includes(node.name);return {{html:'<details '+(searchEl.value.trim()||(depth<2&&!gap)?'open':'')+'>'+summary+children.join('')+leaves+'</details>',tags,dims}}}}
function bind(){{treeEl.querySelectorAll('[data-kind]').forEach(el=>el.onclick=()=>show(el.dataset.kind,el.dataset.id))}}function render(){{const visible=visibleSets(),part=treePart(TREE,visible,0);treeEl.innerHTML=part?.html||'<div class="empty">没有匹配记录</div>';document.getElementById('visibleTags').textContent=fmt.format(visible.tags.size);bind()}}
function rows(fields){{return fields.map(([k,v])=>'<div class="row"><strong>'+esc(k)+'：</strong>'+esc(val(v))+'</div>').join('')}}function taskIds(v){{const ids=(Array.isArray(v)?v:[v]).map(x=>String(x??'').trim()).filter(x=>x&&x!=='-');return ids.length?ids.join('、'):'未配置'}}function links(list,kind){{return (list||[]).map(link=>{{const id=kind==='tag'?link.tagId:link.tagDimId,known=kind==='tag'?byTag.has(id):byDim.has(id),label=known?'<span class="link" data-link-kind="'+kind+'" data-link-id="'+esc(id)+'">'+esc(id)+'</span>':esc(id)+'（对象未在本快照中）';return '<div class="row">'+label+'：'+esc(link.status||link.dimensionEvidenceStatus||'UNAVAILABLE')+'</div>'}}).join('')||'<div class="row">未采集关联记录</div>'}}
function show(kind,id){{selected.kind=kind;selected.id=id;if(kind==='tag'){{const r=byTag.get(id);if(!r)return;detailEl.innerHTML='<h2>'+esc(val(r.tagName))+'</h2><div class="badge tag">标签</div>'+rows([['标签ID',r.tagId],['类型（持仓/组合）',r.tagTypeName],['状态',r.statusName],['目录',r.catalogPath],['标签维度数量',r.tagDimensionCount],['计算符号',r.calculateSymbol],['生成条件',r.generationCondition],['技术负责人',r.techLeads],['开发者',r.developers],['创建时间',r.createTime],['更新时间',r.updateTime]])+'<h3>关联标签维度</h3>'+links(tagToDim.get(id),'dim')}}else{{const r=byDim.get(id);if(!r)return;detailEl.innerHTML='<h2>'+esc(val(r.tagDimName))+'</h2><div class="badge dim">标签维度</div>'+rows([['标签维度ID',r.tagDimId],['管理列表收录',r.inDimensionList?'是':'否（关系补充详情）'],['英文名称',r.tagDimEnglishName],['类型（持仓/组合）',r.tagClassName],['是否复合标签维度',r.isCompositeTagDimension],['实时类型',r.realTimeTypeName],['状态名称',r.statusName],['状态代码',r.statusCode],['安全等级',r.securityLevelName],['是否用于组合筛选',r.isForGroupFiltering],['打标调度ID',taskIds(r.markingTaskIds)],['系统标签调度ID',taskIds(r.systemTagTaskIds)],['任务证据','ID_ONLY（未采集任务详情/运行记录）'],['结果数据库',r.resultDatabase],['结果表',r.resultTable],['目录',r.catalogPath],['描述',r.description],['详情证据',r.detailEvidenceStatus],['SQL证据',r.sqlResolvedStatus],['SQL格式化',r.sqlFormatStatus]])+(r.sqlText?'<div class="sql" data-raw="'+esc(r.sqlText)+'">'+esc(r.sqlText)+'</div>':'')}}detailEl.querySelectorAll('[data-link-kind]').forEach(el=>el.onclick=()=>show(el.dataset.linkKind,el.dataset.linkId));highlight();treeEl.querySelectorAll('[data-kind]').forEach(el=>el.classList.toggle('selected',el.dataset.kind===kind&&el.dataset.id===id))}}
function highlight(){{const re=/\/\*[\s\S]*?\*\/|--[^\n]*|'(?:''|[^'])*'|\b\d+(?:\.\d+)?\b|\b[A-Za-z_][A-Za-z0-9_$#]*\b/g,kw=/^(select|from|where|join|left|right|full|inner|outer|on|and|or|not|in|is|null|as|case|when|then|else|end|group|by|order|having|union|all|distinct|with|over|partition|row_number|count|sum|min|max|avg|decode|nvl)$/i;document.querySelectorAll('.sql').forEach(box=>{{const raw=box.getAttribute('data-raw')||box.textContent;box.innerHTML=raw.replace(re,m=>{{const k=m.startsWith('--')||m.startsWith('/*')?'sql-comment':m.startsWith("'")?'sql-string':/^\d/.test(m)?'sql-number':kw.test(m)?'sql-keyword':'';return k?'<span class="'+k+'">'+esc(m)+'</span>':esc(m)}})}})}}searchEl.oninput=render;document.getElementById('clear').onclick=()=>{{searchEl.value='';render()}};document.getElementById('expand').onclick=()=>treeEl.querySelectorAll('details').forEach(x=>x.open=true);document.getElementById('collapse').onclick=()=>treeEl.querySelectorAll('details').forEach(x=>x.open=false);render();
</script></body></html>'''


def _dual_page_with_dimension_tree(snapshot_id: str, manifest: dict[str, Any], dimensions: list[dict[str, Any]], dual: dict[str, Any], records_hash: str) -> str:
    return _unified_dual_page(snapshot_id, manifest, dimensions, dual, records_hash)


def build_tag_catalog(snapshot_dir: Path, output_root: Path) -> dict[str, Path | int | str]:
    snapshot_dir = snapshot_dir.resolve()
    snapshot_id, manifest, rows, records_path = _read_snapshot(snapshot_dir)
    dual = _read_dual_snapshot(snapshot_dir, manifest, rows)
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    target = output_root / snapshot_id
    stage = Path(tempfile.mkdtemp(prefix=f".{snapshot_id}-", dir=output_root))
    records_hash = _sha256(records_path)
    try:
        page = stage / "index.html"
        if dual is None:
            page_html = _add_sql_highlighting(
                _page(snapshot_id, manifest, rows, records_hash)
            )
        else:
            page_html = _dual_page_with_dimension_tree(
                snapshot_id, manifest, rows, dual, records_hash
            )
        page.write_text(_without_expand_all_control(page_html), encoding="utf-8")
        statuses = sorted({r["sqlResolvedStatus"] for r in rows})
        projection = {"schemaVersion": "tag-catalog-review-v2" if dual else "tag-catalog-review-v1", "snapshotId": snapshot_id, "recordCount": len(rows), "catalogNodeCount": _node_count(_tree(rows)), "uncataloguedCount": sum(r["catalogParts"] == [UNCATALOGUED] for r in rows), "sqlEvidenceCounts": {status: sum(r["sqlResolvedStatus"] == status for r in rows) for status in statuses}, "source": {"recordsPath": str(records_path), "recordsSha256": records_hash}, "page": "index.html", "pageSha256": _sha256(page)}
        if dual is not None:
            projection["tagValueCount"] = dual["valuesCount"]
            projection["tagDimensionLinkCount"] = dual["relationCount"]
            projection["tagValueEvidence"] = dual["tagValueEvidence"]
            projection["tagTypeCounts"] = {
                type_name: sum(row.get("tagTypeName") == type_name for row in dual["tags"])
                for type_name in sorted({row.get("tagTypeName") for row in dual["tags"]})
            }
            projection["tagDimensionTypeCounts"] = {
                type_name: sum(row.get("tagClassName") == type_name for row in rows)
                for type_name in sorted({row.get("tagClassName") for row in rows})
            }
            projection["listedDimensionCount"] = sum(bool(row.get("inDimensionList")) for row in rows)
            projection["relationOnlyDimensionDetailCount"] = len(rows) - projection["listedDimensionCount"]
            projection["source"]["tagValuesPath"] = dual["valuesPath"]
            projection["source"]["tagDimensionsPath"] = dual["dimensionsPath"]
            projection["source"]["tagDimensionsSha256"] = dual["dimensionsSha256"]
            projection["source"]["tagDimensionLinksPath"] = dual["linksPath"]
            projection["taskEvidence"] = {
                "status": "ID_ONLY",
                "workflowRecordsFetched": dual["workflowRecordsFetched"],
            }
        (stage / "tag-catalog-projection-manifest.json").write_text(json.dumps(projection, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        backup = output_root / f".{snapshot_id}.previous"
        if backup.exists():
            shutil.rmtree(backup)
        if target.exists():
            target.replace(backup)
        stage.replace(target)
        if backup.exists():
            shutil.rmtree(backup)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return {"snapshot_id": snapshot_id, "record_count": len(rows), "catalog_node_count": projection["catalogNodeCount"], "uncatalogued_count": projection["uncataloguedCount"], "page": target / "index.html", "manifest": target / "tag-catalog-projection-manifest.json"}


def _node_count(node: dict[str, Any]) -> int:
    return 1 + sum(_node_count(child) for child in node.get("children", []))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at line {line_number}: {path.name}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"JSONL row must be an object: {path.name}:{line_number}")
        rows.append(row)
    return rows


def _read_dual_snapshot(snapshot_dir: Path, manifest: dict[str, Any], dimensions: list[dict[str, Any]]) -> dict[str, Any] | None:
    values_path = snapshot_dir / "tag-values.jsonl"
    if not values_path.is_file():
        return None
    values = _read_jsonl(values_path)
    links_path = snapshot_dir / "tag-value-dimension-links.jsonl"
    dimensions_path = snapshot_dir / "tag-dimensions.jsonl"
    links = _read_jsonl(links_path) if links_path.is_file() else []
    tags: list[dict[str, Any]] = []
    seen_tags: set[str] = set()
    for line_number, row in enumerate(values, start=1):
        tag_id = _text(row.get("tagId")).strip()
        if not tag_id:
            raise ValueError(f"tag value line {line_number} has no tagId")
        if tag_id in seen_tags:
            raise ValueError(f"duplicate tagId: {tag_id}")
        seen_tags.add(tag_id)
        raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
        dim_ids = row.get("tagDimIds") or raw.get("tagDimIds") or raw.get("tagDimIdList") or []
        tags.append({
            **row,
            "tagId": tag_id,
            "tagTypeName": _platform_type_name(row.get("tagTypeName"), row.get("tagTypeCode")),
            "tagDimIds": [str(value).strip() for value in dim_ids if str(value).strip()],
        })
    relation_rows: list[dict[str, Any]] = []
    seen_relations: set[tuple[str, str]] = set()
    for line_number, row in enumerate(links, start=1):
        tag_id = _text(row.get("tagId")).strip()
        dim_id = _text(row.get("tagDimId")).strip()
        if not tag_id or not dim_id:
            raise ValueError(f"relation line {line_number} has incomplete tagId/tagDimId")
        key = (tag_id, dim_id)
        if key in seen_relations:
            raise ValueError(f"duplicate tag relation: {tag_id}|{dim_id}")
        seen_relations.add(key)
        relation_rows.append({**row, "tagId": tag_id, "tagDimId": dim_id, "status": _text(row.get("dimensionEvidenceStatus")).strip() or "UNAVAILABLE"})
    dim_ids = {row["tagDimId"] for row in dimensions}
    for relation in relation_rows:
        relation["dimensionKnown"] = relation["tagDimId"] in dim_ids
    tag_by_id = {row["tagId"]: row for row in tags}
    dim_by_id = {row["tagDimId"]: row for row in dimensions}
    tag_to_dim: dict[str, list[dict[str, Any]]] = {tag_id: [] for tag_id in tag_by_id}
    dim_to_tag: dict[str, list[dict[str, Any]]] = {dim_id: [] for dim_id in dim_by_id}
    for relation in relation_rows:
        tag_to_dim.setdefault(relation["tagId"], []).append(relation)
        dim_to_tag.setdefault(relation["tagDimId"], []).append(relation)
    scope = _text(manifest.get("scope")).strip().lower() or "unknown"
    return {
        "tags": tags,
        "links": relation_rows,
        "tagToDim": tag_to_dim,
        "dimToTag": dim_to_tag,
        "scope": scope,
        "valuesPath": str(values_path),
        "dimensionsPath": str(dimensions_path),
        "dimensionsSha256": _sha256(dimensions_path),
        "linksPath": str(links_path) if links_path.is_file() else "",
        "valuesCount": len(tags),
        "relationCount": len(relation_rows),
        "tagValueEvidence": "FOUND" if tags else "TAG_VALUES_NOT_CAPTURED",
        "workflowRecordsFetched": int(manifest.get("workflowRecordsFetched") or 0),
    }


def _dual_page(snapshot_id: str, manifest: dict[str, Any], dimensions: list[dict[str, Any]], dual: dict[str, Any], records_hash: str) -> str:
    safe_dimensions = [{key: value for key, value in row.items() if key != "sqlResolvedPath"} for row in dimensions]
    listed_dimension_count = sum(bool(row.get("inDimensionList")) for row in dimensions)
    relation_only_dimension_count = len(dimensions) - listed_dimension_count
    payload = json.dumps({"tags": dual["tags"], "dimensions": safe_dimensions, "links": dual["links"], "tagToDim": dual["tagToDim"], "dimToTag": dual["dimToTag"]}, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    tree = json.dumps(_tree(dimensions), ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    meta = json.dumps({"snapshotId": snapshot_id, "scope": dual["scope"], "tagCount": dual["valuesCount"], "dimensionCount": len(dimensions), "listedDimensionCount": listed_dimension_count, "relationOnlyDimensionCount": relation_only_dimension_count, "relationCount": dual["relationCount"], "tagValueEvidence": dual["tagValueEvidence"], "recordsSha256": records_hash}, ensure_ascii=False)
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>标签目录树 · {html.escape(snapshot_id)}</title><style>:root{{--ink:#152238;--muted:#60708a;--line:#dbe4f0;--soft:#f4f8fc;--accent:#1769aa;--warn:#9a5b00}}*{{box-sizing:border-box}}body{{margin:0;background:#eef3f9;color:var(--ink);font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif}}.page{{max-width:1600px;margin:28px auto;padding:0 20px}}header{{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;margin-bottom:18px}}h1{{margin:0 0 5px;font-size:28px}}.sub,.muted{{color:var(--muted)}}.meta{{padding:10px 14px;border:1px solid #cbd9e9;background:#f8fbff;border-radius:12px;white-space:nowrap}}.tabs,.toolbar,.summary{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}}button,input{{border:1px solid #c7d5e5;border-radius:9px;padding:10px 13px;background:#fff;font:inherit}}button{{cursor:pointer}}button.active{{background:#1769aa;color:#fff;border-color:#1769aa}}input{{flex:1;min-width:240px}}.pill{{background:#fff;border:1px solid var(--line);border-radius:999px;padding:5px 11px}}.pill strong{{color:var(--accent)}}.layout{{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(420px,.75fr);gap:16px}}.panel{{background:#fff;border:1px solid var(--line);border-radius:14px;overflow:hidden}}.panel-head{{padding:15px 18px;border-bottom:1px solid var(--line);font-weight:700}}.tree{{padding:12px 14px;max-height:calc(100vh - 280px);overflow:auto}}details{{margin:3px 0 3px 12px}}summary{{cursor:pointer;padding:7px 8px;border-radius:8px;display:flex;gap:8px}}summary:hover{{background:var(--soft)}}.name{{flex:1;overflow-wrap:anywhere}}.count{{color:var(--muted);font-size:12px}}.list{{margin:3px 0 8px 27px}}.item{{display:flex;gap:10px;padding:8px 10px;margin:4px 0;border:1px solid #e3eaf2;border-radius:9px;cursor:pointer}}.item:hover,.item.selected{{border-color:#79b3dc;background:#e8f3fc}}.item-name{{flex:1;overflow-wrap:anywhere}}.detail{{position:sticky;top:15px;padding:18px;max-height:calc(100vh - 280px);overflow:auto}}.detail h2{{margin:0 0 4px;font-size:21px;overflow-wrap:anywhere}}.row{{padding:9px 0;border-bottom:1px solid #edf1f5;white-space:pre-wrap;overflow-wrap:anywhere}}.row strong{{display:inline-block;min-width:140px;color:#49617d}}.link{{color:#1769aa;cursor:pointer;text-decoration:underline}}.sql{{margin-top:16px;padding:12px;background:#101923;color:#e6edf5;border-radius:9px;white-space:pre-wrap;overflow:auto;max-height:420px;font:12px/1.5 Consolas,monospace}}.sql-keyword{{color:#7dd3fc}}.sql-string{{color:#fbbf24}}.sql-comment{{color:#94a3b8}}.sql-number{{color:#c4b5fd}}.note{{margin-top:15px;padding:10px 12px;background:#fff7e8;border:1px solid #f0d8a7;border-radius:9px;color:var(--warn)}}.empty{{padding:25px;color:var(--muted);text-align:center}}footer{{margin:16px 2px;color:#73829a;font-size:12px;overflow-wrap:anywhere}}@media(max-width:950px){{header{{display:block}}.layout{{grid-template-columns:1fr}}.detail{{position:static;max-height:none}}.tree{{max-height:none}}}}</style></head><body><main class="page"><header><div><h1>标签目录树</h1><div class="sub">标签管理与标签维度管理分开展示，关联只来自快照记录。</div></div><div class="meta">快照：{html.escape(snapshot_id)}<br>范围：{html.escape(dual["scope"])}<br>标签数据：{html.escape(dual["tagValueEvidence"])}</div></header><div class="tabs"><button id="tagsTab" class="active">标签管理</button><button id="dimsTab">标签维度管理</button></div><div class="toolbar"><input id="search" placeholder="搜索名称、ID、目录、状态或生成条件"><button id="expand">全部展开</button><button id="collapse">全部折叠</button><button id="clear">清空</button></div><div class="summary"><span class="pill">标签：<strong id="tagTotal">{dual["valuesCount"]:,}</strong></span><span class="pill">维度：<strong id="dimTotal">{len(dimensions):,}</strong></span><span class="pill">关联：<strong id="linkTotal">{dual["relationCount"]:,}</strong></span><span class="pill">当前可见：<strong id="visible">0</strong></span></div><div class="layout"><section class="panel"><div class="panel-head" id="treeTitle">标签目录</div><div id="tree" class="tree"></div></section><aside class="panel detail" id="detail"><div class="empty">点击左侧记录查看详情</div></aside></div><footer>标签文件：{html.escape(dual["valuesPath"])}；关联文件：{html.escape(dual["linksPath"] or "未采集")}；维度详情 sha256：{records_hash}<br>SQL 只展示维度快照中的证据，不代表标签实际生效或业务数据结果。</footer></main><script>const DATA={payload};const TREE={tree};const META={meta};const mode={{value:'tag'}};const selected={{id:null}};const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));const fmt=new Intl.NumberFormat('zh-CN');const byTag=new Map(DATA.tags.map(x=>[x.tagId,x]));const byDim=new Map(DATA.dimensions.map(x=>[x.tagDimId,x]));const tagToDim=new Map(Object.entries(DATA.tagToDim));const dimToTag=new Map(Object.entries(DATA.dimToTag));const treeEl=document.getElementById('tree'),detailEl=document.getElementById('detail'),searchEl=document.getElementById('search');const qtext=r=>[r.tagId,r.tagName,r.tagDimId,r.tagDimName,r.catalogPath,r.statusName,r.generationCondition,r.description].join(' ').toLocaleLowerCase();function matches(r){{const q=searchEl.value.trim().toLocaleLowerCase();return !q||qtext(r).includes(q)}}function rows(){{return mode.value==='tag'?DATA.tags:DATA.dimensions}}function nodeCount(node,visible){{const ids=mode.value==='tag'?node.tagIds||[]:node.tagDimIds||[];return ids.filter(id=>visible.has(id)).length+(node.children||[]).reduce((n,c)=>n+nodeCount(c,visible),0)}}function treeHtml(node,visible,depth){{const count=nodeCount(node,visible);if(!count)return '';const own=(mode.value==='tag'?node.tagIds||[]:node.tagDimIds||[]).filter(id=>visible.has(id));const children=(node.children||[]).map(c=>treeHtml(c,visible,depth+1)).join('');const body=children+(own.length?'<div class="list">'+own.map(id=>{{const r=mode.value==='tag'?byTag.get(id):byDim.get(id);const name=mode.value==='tag'?(r.tagName||r.tagId):(r.tagDimName||r.tagDimId);return '<div class="item '+(selected.id===id?'selected':'')+'" data-id="'+esc(id)+'"><span class="item-name">'+esc(name)+'</span><span class="muted">'+esc(mode.value==='tag'?r.tagId:r.tagDimId)+'</span></div>'}}).join('')+'</div>':'');return '<details '+(searchEl.value.trim()||depth<2?'open':'')+'><summary><span class="name">'+esc(node.name)+'</span><span class="count">'+fmt.format(count)+'</span></summary>'+body+'</details>'}}function buildTree(){{const root={{name:'标签目录',children:[],tagIds:[],tagDimIds:[]}};const groups=new Map();for(const r of rows()){{const raw=r.catalogPath||'';const parts=raw&&raw!=='-'?raw.split('_').filter(Boolean):['未归类/源数据无目录'];let node=root;for(const part of parts){{let child=(node.children||[]).find(x=>x.name===part);if(!child){{child={{name:part,children:[],tagIds:[],tagDimIds:[]}};node.children.push(child)}}node=child}}(mode.value==='tag'?node.tagIds:node.tagDimIds).push(mode.value==='tag'?r.tagId:r.tagDimId)}}return root}}function render(){{const visible=new Set(rows().filter(matches).map(r=>mode.value==='tag'?r.tagId:r.tagDimId));treeEl.innerHTML=treeHtml(buildTree(),visible,0)||'<div class="empty">没有匹配记录</div>';document.getElementById('visible').textContent=fmt.format(visible.size);treeEl.querySelectorAll('[data-id]').forEach(el=>el.onclick=()=>show(el.dataset.id))}}function val(v){{return v===undefined||v===null||v===''||v==='-'?'未采集/不可用':String(v)}}function relationLinks(list,reverse){{return (list||[]).map(link=>{{const id=reverse?link.tagId:link.tagDimId;const known=reverse?byTag.has(id):byDim.has(id);return '<div class="row"><span class="link" data-link="'+esc(id)+'">'+esc(id)+'</span>：'+esc(link.status||link.dimensionEvidenceStatus||'UNAVAILABLE')+(known?'':'（对象未在本快照中）')+'</div>'}}).join('')||'<div class="row">未采集关联记录</div>'}}function show(id){{selected.id=id;if(mode.value==='tag'){{const r=byTag.get(id);if(!r)return;detailEl.innerHTML='<h2>'+esc(val(r.tagName))+'</h2><div class="muted">标签管理对象</div>'+[['标签ID',r.tagId],['标签类型',r.tagTypeName],['状态',r.statusName],['目录',r.catalogPath],['标签维度数量',r.tagDimensionCount],['计算符号',r.calculateSymbol],['生成条件',r.generationCondition],['技术负责人',r.techLeads],['开发者',r.developers],['创建时间',r.createTime],['更新时间',r.updateTime]].map(([k,v])=>'<div class="row"><strong>'+esc(k)+'：</strong>'+esc(val(v))+'</div>').join('')+'<h3>关联标签维度</h3>'+relationLinks(tagToDim.get(id),false)}}else{{const r=byDim.get(id);if(!r)return;detailEl.innerHTML='<h2>'+esc(val(r.tagDimName))+'</h2><div class="muted">标签维度管理对象</div>'+[['标签维度ID',r.tagDimId],['英文名称',r.tagDimEnglishName],['类别',r.tagClassName],['实时类型',r.realTimeTypeName],['状态',r.statusName],['结果数据库',r.resultDatabase],['结果表',r.resultTable],['目录',r.catalogPath],['描述',r.description],['详情证据',r.detailEvidenceStatus],['SQL证据',r.sqlResolvedStatus]].map(([k,v])=>'<div class="row"><strong>'+esc(k)+'：</strong>'+esc(val(v))+'</div>').join('')+'<h3>关联标签</h3>'+relationLinks(dimToTag.get(id),true)+(r.sqlText?'<div class="sql" data-raw="'+esc(r.sqlText)+'">'+esc(r.sqlText)+'</div>':'')}}detailEl.querySelectorAll('[data-link]').forEach(el=>el.onclick=()=>{{mode.value=mode.value==='tag'?'dim':'tag';render();show(el.dataset.link)}});highlight();render()}}function highlight(){{const re=/\/\\*[\\s\\S]*?\\*\\/|--[^\\n]*|'(?:''|[^'])*'|\\b\\d+(?:\\.\\d+)?\\b|\\b[A-Za-z_][A-Za-z0-9_$#]*\\b/g;const kw=/^(select|from|where|join|left|right|full|inner|outer|on|and|or|not|in|is|null|as|case|when|then|else|end|group|by|order|having|union|all|distinct|with|over|partition|row_number|count|sum|min|max|avg|decode|nvl)$/i;document.querySelectorAll('.sql').forEach(box=>{{const raw=box.getAttribute('data-raw')||box.textContent;box.innerHTML=raw.replace(re,m=>{{const k=m.startsWith('--')||m.startsWith('/*')?'sql-comment':m.startsWith("'")?'sql-string':/^\\d/.test(m)?'sql-number':kw.test(m)?'sql-keyword':'';return k?'<span class="'+k+'">'+esc(m)+'</span>':esc(m)}})}})}}document.getElementById('tagsTab').onclick=()=>{{mode.value='tag';selected.id=null;document.getElementById('tagsTab').classList.add('active');document.getElementById('dimsTab').classList.remove('active');document.getElementById('treeTitle').textContent='标签目录';render()}};document.getElementById('dimsTab').onclick=()=>{{mode.value='dim';selected.id=null;document.getElementById('dimsTab').classList.add('active');document.getElementById('tagsTab').classList.remove('active');document.getElementById('treeTitle').textContent='标签维度目录';render()}};searchEl.oninput=render;document.getElementById('clear').onclick=()=>{{searchEl.value='';render()}};document.getElementById('expand').onclick=()=>treeEl.querySelectorAll('details').forEach(x=>x.open=true);document.getElementById('collapse').onclick=()=>treeEl.querySelectorAll('details').forEach(x=>x.open=false);render();</script></body></html>'''
