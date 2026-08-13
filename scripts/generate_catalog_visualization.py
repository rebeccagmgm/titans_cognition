from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = (
    ROOT.parents[1]
    / "股衍数据-Cookbook"
    / ".evidence-cache"
    / "indicator-dictionary-snapshots"
    / "20260812-refresh"
    / "indicators.jsonl"
)
OUTPUT = (
    ROOT
    / "output"
    / "stage3-tradeflow-context-semantic-map-v1-20260812"
    / "context-enriched-field-semantic-map"
    / "review"
    / "catalog-tree-visualization.html"
)


def normalize(row: dict) -> dict:
    return {
        "indexId": row.get("indexId", ""),
        "chineseName": row.get("chineseName", ""),
        "englishName": row.get("englishName", ""),
        "status": row.get("status", ""),
        "indexType": row.get("indexType", ""),
        "dataLevel": row.get("dataLevel", ""),
        "indexGran": row.get("indexGran", ""),
        "dataSetConfigName": row.get("dataSetConfigName", ""),
        "busiCycle": row.get("busiCyc", ""),
        "techDirector": row.get("techDirector", ""),
        "businessDefinition": row.get("businessDefinition", ""),
        "dbName": row.get("dbName", ""),
        "engTblName": row.get("engTblName", ""),
        "horaeTaskId": row.get("horaeTaskId", ""),
        "indicatorUnit": row.get("indicatorUnit", ""),
        "includeGroupTypes": row.get("includeGroupTypes", ""),
        "includeTags": row.get("includeTags", ""),
        "catalog": row.get("catalog") or [],
    }


def build_tree(rows: list[dict]) -> tuple[dict, dict[str, list[dict]]]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        indicator = normalize(row)
        path = ">".join(indicator["catalog"]) if indicator["catalog"] else "分类>指标标签目录>未分类"
        grouped.setdefault(path, []).append(indicator)

    root = {"name": "指标标签目录", "path": "分类>指标标签目录", "children": []}
    nodes = {root["path"]: root}
    for path in sorted(grouped):
        parts = path.split(">")
        parent = None
        for index in range(2, len(parts) + 1):
            current_path = ">".join(parts[:index])
            node = nodes.get(current_path)
            if node is None:
                node = {"name": parts[index - 1], "path": current_path, "children": []}
                nodes[current_path] = node
                (parent or root)["children"].append(node)
            parent = node
    return root, grouped


def render(rows: list[dict], tree: dict, grouped: dict[str, list[dict]]) -> str:
    payload = json.dumps({"tree": tree, "grouped": grouped}, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")
    html = '''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>指标目录树可视化</title>
<style>
:root{{--bg:#f4f7fb;--panel:#fff;--line:#d9e2ef;--text:#172235;--muted:#66758a;--accent:#1d64ad;--soft:#eef5fd}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 "Segoe UI","Microsoft YaHei",sans-serif}}
.page{{max-width:1500px;margin:0 auto;padding:18px}} .card{{background:var(--panel);border:1px solid var(--line);border-radius:14px}}
.header{{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;padding:20px;border-bottom:1px solid var(--line)}}
h1{{font-size:22px;margin:0 0 4px}} .subtitle{{color:var(--muted)}} .summary{{background:var(--soft);border:1px solid #c9ddf4;border-radius:9px;padding:9px 12px;color:#315a85;white-space:nowrap}}
.toolbar{{display:flex;gap:10px;align-items:center;padding:14px 20px;border-bottom:1px solid var(--line);flex-wrap:wrap}}
input{{flex:1;min-width:260px;padding:10px 12px;border:1px solid #b9c8da;border-radius:8px;font:inherit}}button{{font:inherit;cursor:pointer}}
.btn{{padding:9px 12px;border:1px solid var(--line);border-radius:8px;background:#fff;color:var(--text)}} .btn:hover{{border-color:var(--accent);color:var(--accent)}}
.layout{{display:grid;grid-template-columns:minmax(500px,1fr) 390px;gap:14px;padding:14px}} .tree{{min-height:620px;max-height:calc(100vh - 190px);overflow:auto;padding:8px;background:#fbfcfe;border:1px solid var(--line);border-radius:10px}}
ul{{list-style:none;margin:0;padding-left:18px}} .node{{margin:2px 0}} .node-head{{display:flex;align-items:center;gap:8px;padding:7px 8px;border-radius:8px}} .node-head:hover{{background:var(--soft)}}
summary{{cursor:pointer}} summary::marker{{color:var(--muted)}} .name{{min-width:0;flex:1}} .count{{color:var(--muted);white-space:nowrap;font-size:12px}} .indicator-list{{padding-left:22px}}
.indicator{{display:flex;gap:10px;align-items:center;padding:8px 10px;margin:3px 0;border:1px solid #e1e8f1;border-radius:8px;background:#fff;cursor:pointer}} .indicator:hover,.indicator.selected{{border-color:#8eb9e4;background:var(--soft)}}
.indicator-name{{flex:1;min-width:0;overflow-wrap:anywhere}} .meta{{color:var(--muted);white-space:nowrap;font-size:12px;max-width:300px;overflow:hidden;text-overflow:ellipsis}}
.detail{{position:sticky;top:14px;align-self:start;border:1px solid var(--line);border-radius:10px;padding:14px;max-height:calc(100vh - 190px);overflow:auto}} .detail h2{{font-size:17px;margin:0 0 4px}} .detail-sub{{color:var(--muted);font-size:12px;margin-bottom:12px}}
.row{{padding:9px 10px;background:var(--soft);border:1px solid #d9e7f5;border-radius:8px;margin:7px 0;white-space:pre-wrap;overflow-wrap:anywhere}} .empty{{padding:30px;color:var(--muted);text-align:center}}
@media(max-width:1000px){{.layout{{grid-template-columns:1fr}}.detail{{position:static;max-height:none}}.tree{{max-height:none}}.header{{flex-direction:column}}.summary{{white-space:normal}}}}
</style></head>
<body><main class="page"><section class="card"><header class="header"><div><h1>指标目录树（可视化）</h1><div class="subtitle">按分类浏览指标；筛选后目录数量和指标数量同步重算。点击具体指标查看快照字段。</div></div><div id="summary" class="summary">加载中…</div></header>
<div class="toolbar"><button id="expand" class="btn">全部展开</button><button id="collapse" class="btn">全部折叠</button><input id="search" type="search" placeholder="搜索指标名称、英文名、状态、业务定义或目录"><button id="clear" class="btn">清空</button></div>
<div class="layout"><div id="tree" class="tree"></div><aside id="detail" class="detail"><div class="empty">点击左侧指标查看明细</div></aside></div></section></main>
<script>
const DATA=__PAYLOAD__;
const treeRoot=DATA.tree, grouped=DATA.grouped, treeEl=document.getElementById('tree'), summaryEl=document.getElementById('summary'), detailEl=document.getElementById('detail'), searchEl=document.getElementById('search');
const allRows=Object.values(grouped).flat(), byId=Object.fromEntries(allRows.map(x=>[x.indexId,x])); let selectedId='';
const fmt=new Intl.NumberFormat('zh-CN');
function esc(v){{return String(v??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]))}}
function matchingRows(){{const q=searchEl.value.trim().toLocaleLowerCase();if(!q)return allRows;return allRows.filter(x=>[x.chineseName,x.englishName,x.status,x.businessDefinition,(x.catalog||[]).join('>')].join(' ').toLocaleLowerCase().includes(q))}}
function rowsFor(path,visible){{return (grouped[path]||[]).filter(x=>visible.has(x.indexId))}}
function countTree(node,visible){{const own=rowsFor(node.path,visible).length;return own+(node.children||[]).reduce((n,c)=>n+countTree(c,visible),0)}}
function nodeHtml(node,visible,depth){{const count=countTree(node,visible), own=rowsFor(node.path,visible), children=(node.children||[]).filter(c=>countTree(c,visible)>0);if(!count)return '';const isOpen=searchEl.value.trim()||depth<2;let body='';if(children.length)body+=`<ul>${children.map(c=>nodeHtml(c,visible,depth+1)).join('')}</ul>`;if(own.length)body+=`<ul class="indicator-list">${own.map(ind=>`<li class="indicator ${{ind.indexId===selectedId?'selected':''}}" data-id="${{esc(ind.indexId)}}"><span class="indicator-name">${{esc(ind.chineseName||ind.englishName||'(未命名)')}}</span><span class="meta">${{esc([ind.status,ind.englishName].filter(Boolean).join(' · '))}}</span></li>`).join('')}</ul>`;if(!body)return '';return `<details class="node" ${{isOpen?'open':''}}><summary class="node-head"><span class="name">${{esc(node.name)}}</span><span class="count">${{fmt.format(count)}} 个指标</span></summary>${{body}}</details>`}}
function render(){{const visible=new Set(matchingRows().map(x=>x.indexId));const count=visible.size;treeEl.innerHTML=count?nodeHtml(treeRoot,visible,0):'<div class="empty">未匹配到指标</div>';summaryEl.textContent=`当前可见指标：${{fmt.format(count)}} / ${{fmt.format(allRows.length)}} 条`;treeEl.querySelectorAll('[data-id]').forEach(el=>el.onclick=()=>showDetail(byId[el.dataset.id]));}}
function showDetail(ind){{selectedId=ind.indexId;const fields=[['指标英文名',ind.englishName],['业务定义',ind.businessDefinition],['指标ID',ind.indexId],['状态',ind.status],['类型',ind.indexType],['颗粒度',ind.dataLevel],['指标粒度',ind.indexGran],['周期',ind.busiCycle],['负责人',ind.techDirector],['数据库',ind.dbName],['英文表名',ind.engTblName],['Horae任务ID',ind.horaeTaskId],['指标单位',ind.indicatorUnit],['数据集',ind.dataSetConfigName],['包含组合类型',ind.includeGroupTypes],['包含标签',ind.includeTags],['目录',(ind.catalog||[]).join(' > ')],['加工SQL','未采集（源快照没有该字段）']];detailEl.innerHTML=`<h2>${{esc(ind.chineseName||ind.englishName)}}</h2><div class="detail-sub">当前快照字段 · 点击左侧其他指标可切换</div>${{fields.map(([k,v])=>`<div class="row"><strong>${{esc(k)}}：</strong>${{esc(v||'未采集')}}</div>`).join('')}}`;render();}}
searchEl.oninput=render;document.getElementById('clear').onclick=()=>{{searchEl.value='';render()}};document.getElementById('expand').onclick=()=>treeEl.querySelectorAll('details').forEach(x=>x.open=true);document.getElementById('collapse').onclick=()=>treeEl.querySelectorAll('details').forEach(x=>x.open=false);render();
</script></body></html>'''
    html = html.replace("{{", "{").replace("}}", "}")
    return html.replace("__PAYLOAD__", payload)


def main() -> None:
    rows = [json.loads(line) for line in SNAPSHOT.read_text(encoding="utf-8").splitlines() if line.strip()]
    tree, grouped = build_tree(rows)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render(rows, tree, grouped), encoding="utf-8")
    print(f"wrote {OUTPUT} ({len(rows)} indicators, {len(grouped)} paths)")


if __name__ == "__main__":
    main()
