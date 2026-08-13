"""Static, bounded review projection for table-semantic results."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Mapping


def _js_assignment(name: str, value: object) -> str:
    return f"window.TABLE_SEMANTIC_{name}={json.dumps(value, ensure_ascii=False, sort_keys=True)};\n"


def render_table_semantic_review(
    root: str | Path,
    *,
    table_profiles: list[dict[str, Any]],
    context_candidates: list[dict[str, Any]],
    anchor_candidates: list[dict[str, Any]],
    responsibility_candidates: list[dict[str, Any]],
    table_groups: list[dict[str, Any]],
    memberships: list[dict[str, Any]],
    relations: list[dict[str, Any]],
    evidence_refs: list[dict[str, Any]],
    assertions: list[dict[str, Any]],
    review_decisions: list[dict[str, Any]],
    structural_propagation_hints: list[dict[str, Any]],
    field_summaries: list[dict[str, Any]],
    wiki_candidates: list[dict[str, Any]],
    investigation_cards: list[dict[str, Any]],
    quality_gate: Mapping[str, Any],
    limits: Mapping[str, int],
) -> dict[str, Path]:
    """Render a replaceable navigation projection after the model Gate passes."""

    if quality_gate.get("status") != "PASS":
        raise ValueError("review projection is forbidden before the model Gate passes")
    review_root = Path(root) / "review"
    data_root = review_root / "data"
    table_root = data_root / "tables"
    table_root.mkdir(parents=True, exist_ok=True)
    shard_size = max(1, int(limits.get("review_shard_size", 50)))
    first_limit = max(1, int(limits.get("first_load_table_limit", 100)))
    profiles = sorted(table_profiles, key=lambda row: (str(row.get("object_name")), str(row.get("asset_id"))))
    shard_files: list[str] = []
    for index in range(0, len(profiles), shard_size):
        shard_id = index // shard_size
        relative = f"data/tables/tables-{shard_id:02d}.js"
        path = review_root / relative
        path.write_text(
            _js_assignment(f"SHARD_{shard_id}", profiles[index : index + shard_size]),
            encoding="utf-8",
        )
        shard_files.append(relative)
    catalog = {
        "table_count": len(profiles),
        "first_load_limit": first_limit,
        "page_size": shard_size,
        "shards": shard_files,
        "first_tables": profiles[:first_limit],
        "gate": dict(quality_gate),
        "indexes": {
            "contexts": sorted(
                {
                    str(row["candidate_value"])
                    for row in context_candidates
                }
            ),
            "anchors": sorted({str(row["candidate_value"]) for row in anchor_candidates}),
            "responsibilities": sorted(
                {
                    str(row["candidate_value"])
                    for row in responsibility_candidates
                    if row.get("recommended_profile_eligible") is True
                }
            ),
            "discovered_responsibility_expression_count": sum(
                row.get("vocabulary_layer") == "DISCOVERY"
                for row in responsibility_candidates
            ),
            "groups": [row for row in table_groups if row.get("group_kind") == "BUSINESS_COLLABORATION_GROUP"],
            "variants": [row for row in table_groups if row.get("group_kind") == "PHYSICAL_VARIANT_GROUP"],
            "structural_neighborhoods": [row for row in table_groups if row.get("group_kind") == "STRUCTURAL_NEIGHBORHOOD"],
            "unknown_asset_ids": [
                row["asset_id"]
                for row in profiles
                if row.get("candidate_summary", {}).get("has_unknown")
            ],
            "conflict_asset_ids": [
                row["asset_id"]
                for row in profiles
                if row.get("candidate_summary", {}).get("has_conflict")
            ],
        },
    }
    catalog_path = data_root / "catalog.js"
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(_js_assignment("CATALOG", catalog), encoding="utf-8")
    details_path = data_root / "details.js"
    details_path.write_text(
        _js_assignment(
            "DETAILS",
            {
                "groups": table_groups,
                "memberships": memberships,
                "relations": relations,
                "context_candidates": context_candidates,
                "anchor_candidates": anchor_candidates,
                "responsibility_candidates": responsibility_candidates,
                "evidence": evidence_refs,
                "assertions": assertions,
                "review_decisions": review_decisions,
                "structural_propagation_hints": structural_propagation_hints,
                "field_support": field_summaries,
                "wiki_candidates": wiki_candidates,
                "investigation_cards": investigation_cards,
            },
        ),
        encoding="utf-8",
    )
    index_path = review_root / "index.html"
    index_path.write_text(_html_document(len(profiles), shard_size), encoding="utf-8")
    return {"review_index": index_path, "review_catalog": catalog_path, "review_details": details_path}


def _html_document(table_count: int, page_size: int) -> str:
    title = html.escape(f"TRADEFLOW 表语义审阅（{table_count} 张表）")
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root{{--bg:#f6f4ef;--card:#fff;--ink:#20231f;--muted:#687066;--line:#d9ddd4;--accent:#28594b;--warn:#925d17}}
*{{box-sizing:border-box}}body{{margin:0;font:14px/1.55 system-ui,"Microsoft YaHei",sans-serif;background:var(--bg);color:var(--ink)}}
header{{padding:18px 24px;background:#173f35;color:white}}header p{{margin:5px 0 0;color:#cfe0da}}
.layout{{display:grid;grid-template-columns:280px minmax(360px,1fr) minmax(360px,1.2fr);gap:12px;padding:12px;min-height:calc(100vh - 94px)}}
.panel{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px;overflow:auto}}h1{{font-size:20px;margin:0}}h2{{font-size:15px;margin:0 0 10px}}h3{{font-size:14px;margin:16px 0 8px}}
input,select,button{{font:inherit;padding:7px 9px;border:1px solid var(--line);border-radius:5px;background:white}}input{{width:100%;margin-bottom:8px}}button{{cursor:pointer}}button:hover{{border-color:var(--accent)}}
.item{{display:block;width:100%;text-align:left;margin:5px 0;padding:8px;border:1px solid var(--line);border-radius:6px;background:white}}.item small{{display:block;color:var(--muted)}}
.tag{{display:inline-block;padding:2px 6px;margin:2px;border-radius:999px;background:#e9efeb;color:#254b40;font-size:12px}}.unknown{{background:#f4e9d8;color:var(--warn)}}
pre{{white-space:pre-wrap;word-break:break-word;background:#f2f3ef;padding:9px;border-radius:6px}}.muted{{color:var(--muted)}}.card-list{{padding-left:20px}}.card-list li{{margin:7px 0}}details{{margin-top:14px}}summary{{cursor:pointer;color:var(--accent)}}nav button{{margin-right:5px}}@media(max-width:1050px){{.layout{{grid-template-columns:1fr}}}}
</style></head>
<body><header><h1>{title}</h1><p>候选 Projection；字段只作辅助证据，结构邻域不是业务分类，工程 Gate 通过不等于业务验收。</p></header>
<main class="layout">
<section class="panel"><h2>导航与筛选</h2><input id="search" placeholder="搜索表名、注释、asset_id"><select id="filter"><option value="all">全部</option><option value="conflict">Conflict</option><option value="unknown">Unknown</option><option value="variant">物理变体</option></select><button id="clear-nav">清除导航条件</button><h3>业务上下文</h3><div id="contexts"></div><h3>业务锚点</h3><div id="anchors"></div><h3>业务协作组</h3><div id="groups"></div><h3>调查卡</h3><div id="cards"></div><h3>独立入口</h3><button data-view="variants">物理变体</button><button data-view="structural">结构邻域</button></section>
<section class="panel"><h2>表目录</h2><div id="tables"></div><nav><button id="prev">上一页</button><span id="page"></span><button id="next">下一页</button></nav></section>
<section class="panel"><h2>表语义画像</h2><div id="detail" class="muted">选择一张表。多入口始终复用同一 asset_id。</div></section>
</main><script src="data/catalog.js"></script><script src="data/details.js"></script>
<script>
const catalog=window.TABLE_SEMANTIC_CATALOG,details=window.TABLE_SEMANTIC_DETAILS;let rows=catalog.first_tables.slice(),page=0,requestToken=0,activeAssetIds=null;const pageSize={page_size};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
function filtered(){{const q=document.querySelector('#search').value.toUpperCase(),f=document.querySelector('#filter').value;return rows.filter(r=>{{if(activeAssetIds&&!activeAssetIds.has(r.asset_id))return false;if(q&&!JSON.stringify([r.object_name,r.object_comment,r.asset_id]).toUpperCase().includes(q))return false;if(f==='conflict'&&!r.candidate_summary.has_conflict)return false;if(f==='unknown'&&!(r.candidate_summary.has_unknown||r.disposition==='UNKNOWN'))return false;if(f==='variant'&&r.disposition==='SUBJECT')return false;return true}})}}
function renderTables(){{const data=filtered(),max=Math.max(0,Math.ceil(data.length/pageSize)-1);page=Math.min(page,max);document.querySelector('#tables').innerHTML=data.slice(page*pageSize,(page+1)*pageSize).map(r=>`<button class="item" data-id="${{esc(r.asset_id)}}">${{esc(r.object_name)}}<small>${{esc(r.disposition)}} · ${{esc(r.object_comment||'无注释')}}</small></button>`).join('')||'<p class="muted">无匹配结果</p>';document.querySelector('#page').textContent=`${{page+1}} / ${{max+1}}`;document.querySelectorAll('[data-id]').forEach(b=>b.onclick=()=>show(b.dataset.id));}}
 function show(id,push=true){{const r=rows.find(x=>x.asset_id===id);if(!r)return;if(push)history.pushState({{asset_id:id}},'',`#${{encodeURIComponent(id)}}`);const rel=details.relations.filter(x=>x.subject_asset_id===id||x.object_asset_id===id),fs=details.field_support.find(x=>x.asset_id===id),groups=details.memberships.filter(x=>x.asset_id===id),candidates=[...details.context_candidates,...details.anchor_candidates,...details.responsibility_candidates].filter(x=>x.asset_id===id),recommended=candidates.filter(x=>x.vocabulary_layer!=='DISCOVERY'),discovered=candidates.filter(x=>x.vocabulary_layer==='DISCOVERY'),assertions=details.assertions.filter(x=>x.subject_id===id),evidenceIds=new Set([...assertions.flatMap(x=>[...(x.evidence_refs||[]),...(x.counterevidence_refs||[])]),...rel.flatMap(x=>[...(x.evidence_refs||[]),...(x.counterevidence_refs||[])])]),evidence=details.evidence.filter(x=>evidenceIds.has(x.evidence_id)),reviews=details.review_decisions.filter(x=>assertions.some(a=>a.assertion_id===x.assertion_id)),hints=details.structural_propagation_hints.filter(x=>x.asset_id===id);document.querySelector('#detail').innerHTML=`<h3>${{esc(r.object_name)}}</h3><p>${{esc(r.object_comment||'无注释')}}</p><p><span class="tag">${{esc(r.disposition)}}</span>${{r.candidate_summary.has_conflict?'<span class="tag unknown">Conflict</span>':''}}${{r.candidate_summary.has_unknown?'<span class="tag unknown">Unknown</span>':''}}</p><h3>规范候选与种子召回</h3><pre>${{esc(JSON.stringify(recommended,null,2))}}</pre><h3>语料发现职责表达</h3><pre>${{esc(JSON.stringify(discovered,null,2))}}</pre><h3>表组职责</h3><pre>${{esc(JSON.stringify(groups,null,2))}}</pre><h3>关系与端点</h3><pre>${{esc(JSON.stringify(rel,null,2))}}</pre><h3>Evidence / Counterevidence</h3><pre>${{esc(JSON.stringify(evidence,null,2))}}</pre><h3>Review Decision</h3><pre>${{esc(JSON.stringify(reviews,null,2))}}</pre><h3>仅结构传播提示</h3><pre>${{esc(JSON.stringify(hints,null,2))}}</pre><h3>字段辅助</h3><pre>${{esc(JSON.stringify(fs||{{availability:'NOT_EVALUABLE'}},null,2))}}</pre><p class="muted">技术分数只保留在详情中，均为方法内排序信号，不是概率。Panorama Object Card：${{esc(r.panorama_object_card)}}（缺失目标仅显示，不伪造链接成功）</p>`;}}
async function loadAll(){{const token=++requestToken;for(let i=0;i<catalog.shards.length;i++){{if(window[`TABLE_SEMANTIC_SHARD_${{i}}`])continue;await new Promise((ok,fail)=>{{const s=document.createElement('script');s.src=catalog.shards[i];s.onload=ok;s.onerror=fail;document.head.appendChild(s)}});if(token!==requestToken)return}}rows=catalog.shards.flatMap((_,i)=>window[`TABLE_SEMANTIC_SHARD_${{i}}`]||[]);renderTables();const id=decodeURIComponent(location.hash.slice(1));if(id)show(id,false)}}
document.querySelector('#search').oninput=()=>{{page=0;renderTables()}};document.querySelector('#filter').onchange=()=>{{page=0;renderTables()}};document.querySelector('#prev').onclick=()=>{{page=Math.max(0,page-1);renderTables()}};document.querySelector('#next').onclick=()=>{{page++;renderTables()}};
function navigateByCandidate(kind,value){{const source=kind==='context'?details.context_candidates:details.anchor_candidates;activeAssetIds=new Set(source.filter(x=>x.candidate_value===value).map(x=>x.asset_id));page=0;renderTables();document.querySelector('#detail').innerHTML=`<h3>${{esc(kind==='context'?'业务上下文':'业务锚点')}}：${{esc(value)}}</h3><p>当前入口引用 ${{activeAssetIds.size}} 个唯一 asset_id；导航位置不会写回候选。</p>`;}}
document.querySelector('#contexts').innerHTML=catalog.indexes.contexts.map(v=>`<button class="tag" data-context="${{esc(v)}}">${{esc(v)}}</button>`).join('');document.querySelectorAll('[data-context]').forEach(b=>b.onclick=()=>navigateByCandidate('context',b.dataset.context));
document.querySelector('#anchors').innerHTML=catalog.indexes.anchors.map(v=>`<button class="tag" data-anchor="${{esc(v)}}">${{esc(v)}}</button>`).join('');document.querySelectorAll('[data-anchor]').forEach(b=>b.onclick=()=>navigateByCandidate('anchor',b.dataset.anchor));
document.querySelector('#groups').innerHTML=catalog.indexes.groups.map(g=>`<button class="item" data-group="${{esc(g.group_id)}}">${{esc(g.anchor_value||g.group_id)}}<small>候选协作组</small></button>`).join('');document.querySelectorAll('[data-group]').forEach(b=>b.onclick=()=>{{const ids=details.memberships.filter(x=>x.group_id===b.dataset.group).map(x=>x.asset_id);activeAssetIds=new Set(ids);page=0;renderTables();document.querySelector('#detail').innerHTML=`<h3>业务协作组</h3><pre>${{esc(JSON.stringify(details.groups.find(x=>x.group_id===b.dataset.group),null,2))}}</pre>`}});
document.querySelector('#clear-nav').onclick=()=>{{activeAssetIds=null;page=0;renderTables()}};
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{{document.querySelector('#detail').innerHTML=`<h3>${{esc(b.textContent)}}</h3><pre>${{esc(JSON.stringify(catalog.indexes[b.dataset.view==='variants'?'variants':'structural_neighborhoods'],null,2))}}</pre>`}});
const shortAsset=id=>String(id??'').split(':').pop();
const cardStatus=card=>card.status==='READY'?(card.semantic_review_status==='UNRESOLVED'?'结构就绪 · 语义仍有 Unknown':'结构就绪（候选）'):'需要返工';
function cardResponsibility(member){{const candidates=member.responsibilities||[];const selected=candidates.find(x=>x.recommended_profile_eligible===true)||candidates.find(x=>x.vocabulary_layer==='DISCOVERY'&&x.source_kind==='TABLE_COMMENT')||candidates[0];return {{value:selected?.candidate_value||'Unknown',kind:selected?.recommended_profile_eligible===true?'推荐候选':'发现表达'}};}}
function relationEvidence(relation){{const direct=details.evidence.filter(x=>(relation.evidence_refs||[]).includes(x.evidence_id)),counter=details.evidence.filter(x=>(relation.counterevidence_refs||[]).includes(x.evidence_id));const summarize=rows=>rows.map(x=>x.content_excerpt||x.source_locator||x.evidence_id).join('；');return `<small class="muted">证据：${{esc(summarize(direct)||'无')}}</small>${{counter.length?`<small class="muted">反证：${{esc(summarize(counter))}}</small>`:''}}`}}
function relationList(relations){{return relations.map(r=>`<li><code>${{esc(shortAsset(r.subject_asset_id))}}</code> ${{r.directed?'→':'↔'}} <strong>${{esc(r.predicate)}}</strong> ${{r.directed?'→':'↔'}} <code>${{esc(shortAsset(r.object_asset_id))}}</code> <span class="tag">${{esc(r.outcome)}}</span>${{(r.limitations||[]).length?`<small class="muted">限制：${{esc(r.limitations.join('；'))}}</small>`:''}}${{relationEvidence(r)}}</li>`).join('')}}
function renderCard(card){{const unknownMembers=new Set(card.unknown_member_asset_ids||[]),conflictMembers=new Set(card.conflict_member_asset_ids||[]);const members=(card.members||[]).map(m=>{{const role=cardResponsibility(m);return `<li><button class="tag" data-card-asset="${{esc(m.asset_id)}}">${{esc(m.object_name)}}</button> · ${{esc(role.value)}} <small class="muted">${{esc(role.kind)}}，尚未人工确认</small>${{unknownMembers.has(m.asset_id)?'<span class="tag unknown">Unknown</span>':''}}${{conflictMembers.has(m.asset_id)?'<span class="tag unknown">Conflict</span>':''}}</li>`}}).join('');const precise=(card.relations||[]).filter(r=>r.directed===true&&r.outcome==='CANDIDATE'&&r.predicate!=='RELATED_TO'),other=(card.relations||[]).filter(r=>!precise.includes(r)),preciseHtml=relationList(precise)||'<li class="muted">没有满足精确有向谓词门槛的旅程内关系</li>',otherHtml=relationList(other)||'<li class="muted">无一般或未决关系</li>';const structuralGaps=[...(card.missing_tables||[]),...(card.missing_responsibility_asset_ids||[]),...(card.disconnected_asset_ids||[])],semanticGaps=[...(card.unknown_member_asset_ids||[]),...(card.conflict_member_asset_ids||[]),...(card.unknown_relation_ids||[])];document.querySelector('#detail').innerHTML=`<h3>${{esc(card.card_id)}}</h3><p><span class="tag">${{esc(cardStatus(card))}}</span> ${{esc(card.boundary||'')}}</p><p>字段辅助已连接到 <strong>${{Number(card.field_assertion_link_count||0)}}</strong> 条表级断言；字段不参与投票。</p><h3>成员职责</h3><ul class="card-list">${{members}}</ul><h3>有方向含义的候选关系</h3><ul class="card-list">${{preciseHtml}}</ul><details><summary>一般或未决关系（${{other.length}}）</summary><ul class="card-list">${{otherHtml}}</ul></details><h3>缺口与 Unknown</h3><p>${{structuralGaps.length?'结构缺口：'+esc(structuralGaps.join('；')):'结构缺口：无。'}}</p><p class="${{semanticGaps.length?'':'muted'}}">${{semanticGaps.length?'语义待审：'+esc(semanticGaps.join('；')):'语义待审：当前卡没有显式 Unknown/Conflict；候选仍不等于业务确认。'}}</p><details><summary>完整技术详情</summary><pre>${{esc(JSON.stringify(card,null,2))}}</pre></details>`;document.querySelectorAll('[data-card-asset]').forEach(b=>b.onclick=()=>show(b.dataset.cardAsset));}}
document.querySelector('#cards').innerHTML=details.investigation_cards.map(c=>`<button class="item" data-card="${{esc(c.card_id)}}">${{esc(c.card_id)}}<small>${{esc(cardStatus(c))}} · ${{c.members.length}} 张可见表</small></button>`).join('');document.querySelectorAll('[data-card]').forEach(b=>b.onclick=()=>{{const c=details.investigation_cards.find(x=>x.card_id===b.dataset.card);renderCard(c)}});
renderTables();loadAll().catch(e=>document.querySelector('#detail').textContent=`分片加载失败：${{e.message}}`);window.onpopstate=()=>{{const id=decodeURIComponent(location.hash.slice(1));if(id)show(id,false);else document.querySelector('#detail').textContent='选择一张表。多入口始终复用同一 asset_id。'}};
</script></body></html>"""
