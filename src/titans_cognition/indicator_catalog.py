"""Deterministic, snapshot-bound indicator catalog review projection."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable


UNAVAILABLE = "未采集（源快照没有该字段）"
UNCATALOGUED_PATH = ("未归类（源数据无目录）",)


def _without_expand_all_control(page_html: str) -> str:
    page_html = re.sub(r'<button id="expand">[^<]*</button>', "", page_html)
    return page_html.replace(
        "document.getElementById('expand').addEventListener('click',()=>"
        "treeEl.querySelectorAll('details').forEach(x=>x.open=true));",
        "",
    )


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


def _normalize_catalog(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return UNCATALOGUED_PATH
    parts = tuple(_text(item).strip() for item in value if _text(item).strip())
    if parts[:2] == ("分类", "指标标签目录"):
        parts = parts[2:]
    elif parts[:1] == ("指标标签目录",):
        parts = parts[1:]
    return parts or UNCATALOGUED_PATH


def _normalize_row(row: object, line_number: int) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError(f"indicator JSONL line {line_number} must be an object")
    index_id = _text(row.get("indexId")).strip()
    if not index_id:
        raise ValueError(f"indicator JSONL line {line_number} has no indexId")
    source_catalog = row.get("catalog") if isinstance(row.get("catalog"), list) else []
    fields = {
        "indexId": index_id,
        "chineseName": _text(row.get("chineseName")),
        "englishName": _text(row.get("englishName")),
        "abbreviation": _text(row.get("abbreviation")),
        "status": _text(row.get("status")),
        "indexType": _text(row.get("indexType")),
        "indexGran": _text(row.get("indexGran")),
        "horaeTaskId": _text(row.get("horaeTaskId")),
        "techDirector": _text(row.get("techDirector")),
        "businessDefinition": _text(row.get("businessDefinition")),
        "indicatorUnit": _text(row.get("indicatorUnit")),
        "dataLevel": _text(row.get("dataLevel")),
        "busiCyc": _text(row.get("busiCyc")),
        "dbName": _text(row.get("dbName")),
        "engTblName": _text(row.get("engTblName")),
        "dataSetConfigName": _text(row.get("dataSetConfigName")),
        "includeGroupTypes": _text(row.get("includeGroupTypes")),
        "includeTags": _text(row.get("includeTags")),
        "catalog": list(_normalize_catalog(row.get("catalog"))),
        "sourceCatalog": [_text(item) for item in source_catalog],
    }
    return fields


def _read_snapshot(snapshot_dir: Path) -> tuple[str, dict[str, Any], list[dict[str, Any]], Path, Path]:
    snapshot_dir = snapshot_dir.resolve()
    manifest_path = snapshot_dir / "manifest.json"
    records_path = snapshot_dir / "indicators.jsonl"
    if not manifest_path.is_file():
        raise ValueError(f"snapshot manifest not found: {manifest_path}")
    if not records_path.is_file():
        raise ValueError(f"indicator JSONL not found: {records_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read snapshot manifest: {manifest_path}") from exc
    if not isinstance(manifest, dict):
        raise ValueError("snapshot manifest must be an object")

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        lines = records_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"cannot read indicator JSONL: {records_path}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid indicator JSONL at line {line_number}") from exc
        row = _normalize_row(raw, line_number)
        if row["indexId"] in seen:
            raise ValueError(f"duplicate indicator indexId: {row['indexId']}")
        seen.add(row["indexId"])
        rows.append(row)

    declared = manifest.get("uniqueRows", manifest.get("recordCount"))
    if declared is not None:
        try:
            declared_count = int(declared)
        except (TypeError, ValueError) as exc:
            raise ValueError("snapshot manifest uniqueRows/recordCount must be numeric") from exc
        if declared_count != len(rows):
            raise ValueError(
                f"snapshot record count mismatch: manifest={declared_count}, jsonl={len(rows)}"
            )
    snapshot_id = _text(manifest.get("snapshotId")).strip() or snapshot_dir.name
    if not snapshot_id:
        raise ValueError("snapshot ID cannot be determined")
    return snapshot_id, manifest, rows, manifest_path, records_path


def _tree_for(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    root: dict[str, Any] = {"name": "指标标签目录", "children": {}, "indicatorIds": []}
    for row in rows:
        node = root
        for part in row["catalog"]:
            node = node["children"].setdefault(
                part, {"name": part, "children": {}, "indicatorIds": []}
            )
        node["indicatorIds"].append(row["indexId"])

    def freeze(node: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": node["name"],
            "children": [freeze(node["children"][key]) for key in sorted(node["children"])],
            "indicatorIds": sorted(node["indicatorIds"]),
        }

    return freeze(root)


def _html(snapshot_id: str, manifest: dict[str, Any], rows: list[dict[str, Any]], manifest_hash: str, records_hash: str) -> str:
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    tree = json.dumps(_tree_for(rows), ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    metadata = json.dumps(
        {
            "snapshotId": snapshot_id,
            "recordCount": len(rows),
            "manifestSha256": manifest_hash,
            "recordsSha256": records_hash,
            "sourceStatus": manifest.get("status", "UNKNOWN"),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).replace("<", "\\u003c")
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>指标目录树 · {snapshot_id}</title>
<style>
:root{{--ink:#152238;--muted:#60708a;--line:#dbe4f0;--soft:#f4f8fc;--accent:#1769aa;--accent-soft:#e8f3fc;--warn:#9a5b00}}
*{{box-sizing:border-box}}body{{margin:0;background:#eef3f9;color:var(--ink);font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif}}
.page{{max-width:1500px;margin:28px auto;padding:0 20px}}header{{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;margin-bottom:18px}}
h1{{margin:0 0 5px;font-size:28px;letter-spacing:.02em}}.sub{{color:var(--muted)}}.meta{{padding:10px 14px;border:1px solid #cbd9e9;background:#f8fbff;border-radius:12px;color:#435672;white-space:nowrap}}
.toolbar{{display:flex;gap:10px;align-items:center;margin-bottom:14px}}input{{flex:1;border:1px solid #c7d5e5;border-radius:10px;padding:11px 13px;font:inherit;outline:none;background:#fff}}input:focus{{border-color:#6aa7d8;box-shadow:0 0 0 3px #dceefb}}button{{border:1px solid #c7d5e5;background:#fff;border-radius:9px;padding:10px 13px;font:inherit;cursor:pointer}}button:hover{{border-color:#6aa7d8;background:var(--accent-soft)}}
.summary{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}}.pill{{background:#fff;border:1px solid var(--line);border-radius:999px;padding:5px 11px;color:#445775}}.pill strong{{color:var(--accent)}}
.layout{{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(330px,.75fr);gap:16px;align-items:start}}.panel{{background:#fff;border:1px solid var(--line);border-radius:14px;box-shadow:0 5px 20px #1d3a5d0c;overflow:hidden}}.panel-head{{padding:15px 18px;border-bottom:1px solid var(--line);font-weight:700}}.tree{{padding:12px 14px;max-height:calc(100vh - 230px);overflow:auto}}details{{margin:3px 0 3px 12px}}summary{{cursor:pointer;list-style:none;padding:7px 8px;border-radius:8px;display:flex;gap:8px;align-items:center}}summary::-webkit-details-marker{{display:none}}summary:before{{content:"▸";color:#7890aa}}details[open]>summary:before{{content:"▾"}}summary:hover{{background:var(--soft)}}.node-name{{flex:1;min-width:0;overflow-wrap:anywhere}}.count{{color:var(--muted);font-size:12px;white-space:nowrap}}.indicator-list{{margin:3px 0 8px 27px}}.indicator{{display:flex;gap:10px;align-items:center;padding:8px 10px;margin:4px 0;border:1px solid #e3eaf2;border-radius:9px;background:#fff;cursor:pointer}}.indicator:hover,.indicator.selected{{border-color:#79b3dc;background:var(--accent-soft)}}.indicator-name{{flex:1;min-width:0;overflow-wrap:anywhere}}.indicator-meta{{max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--muted);font-size:12px}}.empty{{padding:25px;color:var(--muted);text-align:center}}.detail{{position:sticky;top:15px;padding:18px;max-height:calc(100vh - 230px);overflow:auto}}.detail h2{{margin:0 0 4px;font-size:21px;overflow-wrap:anywhere}}.detail-sub{{color:var(--muted);margin-bottom:15px}}.row{{padding:9px 0;border-bottom:1px solid #edf1f5;overflow-wrap:anywhere}}.row strong{{display:inline-block;min-width:110px;color:#49617d}}.note{{margin-top:15px;padding:10px 12px;background:#fff7e8;border:1px solid #f0d8a7;border-radius:9px;color:var(--warn);font-size:13px}}footer{{margin:16px 2px;color:#73829a;font-size:12px;overflow-wrap:anywhere}}
@media(max-width:950px){{header{{display:block}}.meta{{display:inline-block;margin-top:10px}}.layout{{grid-template-columns:1fr}}.detail{{position:static;max-height:none}}.tree{{max-height:none}}}}
</style></head><body><main class="page"><header><div><h1>指标目录树（可视化）</h1><div class="sub">按分类查看指标目录，支持检索、展开和点击指标查看明细。</div></div><div class="meta">快照：{snapshot_id}<br>源状态：{str(manifest.get('status', 'UNKNOWN'))}</div></header>
<div class="toolbar"><input id="search" placeholder="搜索指标名称、英文名、指标ID、目录、状态或业务定义"><button id="expand">全部展开</button><button id="collapse">全部折叠</button><button id="clear">清空</button></div>
<div class="summary"><span class="pill">快照总数：<strong id="total">{len(rows):,}</strong></span><span class="pill">当前可见：<strong id="visible">{len(rows):,}</strong></span><span class="pill">可见目录节点：<strong id="nodes">0</strong></span></div>
<div class="layout"><section class="panel"><div class="panel-head">指标标签目录</div><div id="tree" class="tree"></div></section><aside class="panel detail" id="detail"><div class="empty">点击左侧指标项查看详情</div></aside></div>
<footer>当前页面只展示此快照字段；加工SQL等源快照未提供的字段显示为“{UNAVAILABLE}”。manifest sha256: {manifest_hash} · indicators.jsonl sha256: {records_hash}</footer></main>
<script>
const ROWS={payload};const TREE={tree};const META={metadata};const UNAVAILABLE={json.dumps(UNAVAILABLE, ensure_ascii=False)};const treeEl=document.getElementById('tree');const searchEl=document.getElementById('search');const detailEl=document.getElementById('detail');const selected={{id:null}};const byId=new Map(ROWS.map(row=>[row.indexId,row]));
const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[ch]));const fmt=new Intl.NumberFormat('zh-CN');
function matches(row){{const q=searchEl.value.trim().toLocaleLowerCase();if(!q)return true;return [row.indexId,row.chineseName,row.englishName,row.status,row.businessDefinition,(row.catalog||[]).join(' > '),(row.sourceCatalog||[]).join(' > ')].join(' ').toLocaleLowerCase().includes(q)}}
function visibleIds(){{return new Set(ROWS.filter(matches).map(row=>row.indexId))}}
function countNode(node,visible){{return node.indicatorIds.filter(id=>visible.has(id)).length+(node.children||[]).reduce((sum,child)=>sum+countNode(child,visible),0)}}
function nodeHtml(node,visible,depth){{const count=countNode(node,visible);if(!count)return '';const children=(node.children||[]).filter(child=>countNode(child,visible)>0);const own=node.indicatorIds.map(id=>byId.get(id)).filter(row=>row&&visible.has(row.indexId));let body='';if(children.length)body+=children.map(child=>nodeHtml(child,visible,depth+1)).join('');if(own.length)body+='<div class="indicator-list">'+own.map(row=>`<div class="indicator ${{selected.id===row.indexId?'selected':''}}" data-id="${{esc(row.indexId)}}"><span class="indicator-name">${{esc(row.chineseName||row.englishName||'(未命名)')}}</span><span class="indicator-meta">${{esc([row.status,row.englishName].filter(Boolean).join(' · '))}}</span></div>`).join('')+'</div>';const open=searchEl.value.trim()||depth<2;return `<details ${{open?'open':''}}><summary><span class="node-name">${{esc(node.name)}}</span><span class="count">${{fmt.format(count)}} 个指标</span></summary>${{body}}</details>`}}
function render(){{const visible=visibleIds();treeEl.innerHTML=nodeHtml(TREE,visible,0)||'<div class="empty">没有匹配的指标</div>';document.getElementById('visible').textContent=fmt.format(visible.size);document.getElementById('nodes').textContent=fmt.format(countVisibleNodes(TREE,visible));treeEl.querySelectorAll('[data-id]').forEach(el=>el.addEventListener('click',()=>showDetail(el.dataset.id)));}}
function countVisibleNodes(node,visible){{return (countNode(node,visible)>0?1:0)+(node.children||[]).reduce((sum,child)=>sum+countVisibleNodes(child,visible),0)}}
function display(value){{return value?value:UNAVAILABLE}}
function showDetail(id){{const row=byId.get(id);if(!row)return;selected.id=id;const fields=[['指标英文名',row.englishName],['业务定义',row.businessDefinition],['指标ID',row.indexId],['状态',row.status],['类型',row.indexType],['颗粒度',row.dataLevel||row.indexGran],['周期',row.busiCyc],['负责人',row.techDirector],['数据库',row.dbName],['英文表名',row.engTblName],['Horae任务ID',row.horaeTaskId],['指标单位',row.indicatorUnit],['数据集',row.dataSetConfigName],['包含组合类型',row.includeGroupTypes],['包含标签',row.includeTags],['目录',(row.catalog||[]).join(' > ')],['源目录',(row.sourceCatalog||[]).join(' > ')],['加工SQL',UNAVAILABLE]];detailEl.innerHTML=`<h2>${{esc(row.chineseName||row.englishName||'(未命名)')}}</h2><div class="detail-sub">当前快照字段 · 指标ID：${{esc(row.indexId)}}</div>${{fields.map(([key,value])=>`<div class="row"><strong>${{esc(key)}}：</strong>${{esc(display(value))}}</div>`).join('')}}<div class="note">详情仅反映当前快照；缺失字段不等于业务上不存在，也未进行SQL推断。</div>`;treeEl.querySelectorAll('.indicator.selected').forEach(el=>el.classList.remove('selected'));const selectedEl=treeEl.querySelector(`[data-id="${{CSS.escape(id)}}"]`);if(selectedEl)selectedEl.classList.add('selected');}}
searchEl.addEventListener('input',render);document.getElementById('clear').addEventListener('click',()=>{{searchEl.value='';render()}});document.getElementById('expand').addEventListener('click',()=>treeEl.querySelectorAll('details').forEach(x=>x.open=true));document.getElementById('collapse').addEventListener('click',()=>treeEl.querySelectorAll('details').forEach(x=>x.open=false));render();
</script></body></html>"""


def build_indicator_catalog(snapshot_dir: Path, output_root: Path) -> dict[str, Path | int | str]:
    snapshot_id, manifest, rows, manifest_path, records_path = _read_snapshot(snapshot_dir)
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    target = output_root / snapshot_id
    stage = Path(tempfile.mkdtemp(prefix=f".{snapshot_id}-", dir=output_root))
    manifest_hash = _sha256(manifest_path)
    records_hash = _sha256(records_path)
    try:
        page_path = stage / "index.html"
        page_path.write_text(
            _without_expand_all_control(
                _html(snapshot_id, manifest, rows, manifest_hash, records_hash)
            ),
            encoding="utf-8",
        )
        projection_manifest = {
            "schemaVersion": "indicator-catalog-review-v1",
            "snapshotId": snapshot_id,
            "source": {
                "manifestPath": str(manifest_path),
                "manifestSha256": manifest_hash,
                "recordsPath": str(records_path),
                "recordsSha256": records_hash,
            },
            "recordCount": len(rows),
            "uncataloguedCount": sum(row["catalog"] == list(UNCATALOGUED_PATH) for row in rows),
            "page": "index.html",
            "pageSha256": _sha256(page_path),
        }
        projection_path = stage / "catalog-projection-manifest.json"
        projection_path.write_text(
            json.dumps(projection_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
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
    return {
        "snapshot_id": snapshot_id,
        "record_count": len(rows),
        "uncatalogued_count": projection_manifest["uncataloguedCount"],
        "page": target / "index.html",
        "manifest": target / "catalog-projection-manifest.json",
    }
