"""Static, bounded review projection for table-semantic results."""

from __future__ import annotations

import html
import json
from collections.abc import Callable
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping


def _js_assignment(name: str, value: object) -> str:
    return f"window.TABLE_SEMANTIC_{name}={json.dumps(value, ensure_ascii=False, sort_keys=True)};\n"


def _candidate_values_by_asset(
    rows: list[dict[str, Any]],
    *,
    allowed_asset_ids: set[str],
    predicate: Callable[[dict[str, Any]], bool] | None = None,
) -> dict[str, list[str]]:
    values: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        asset_id = str(row.get("asset_id", ""))
        if asset_id not in allowed_asset_ids or row.get("outcome") == "REJECTED":
            continue
        if predicate is not None and not predicate(row):
            continue
        value = str(row.get("candidate_value", "")).strip()
        if value:
            values[asset_id].add(value)
    return {asset_id: sorted(items) for asset_id, items in values.items()}


def _candidate_facets(
    rows: list[dict[str, Any]], *, allowed_asset_ids: set[str]
) -> list[dict[str, Any]]:
    assets_by_value: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        asset_id = str(row.get("asset_id", ""))
        value = str(row.get("candidate_value", "")).strip()
        if (
            asset_id in allowed_asset_ids
            and value
            and row.get("outcome") != "REJECTED"
        ):
            assets_by_value[value].add(asset_id)
    facets = [
        {
            "value": value,
            "table_count": len(asset_ids),
            "asset_ids": sorted(asset_ids),
        }
        for value, asset_ids in assets_by_value.items()
    ]
    return sorted(facets, key=lambda row: (-row["table_count"], row["value"]))


def _prepare_reader_catalog(
    profiles: list[dict[str, Any]],
    *,
    context_candidates: list[dict[str, Any]],
    anchor_candidates: list[dict[str, Any]],
    responsibility_candidates: list[dict[str, Any]],
    field_summaries: list[dict[str, Any]],
    assertions: list[dict[str, Any]],
    review_decisions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    asset_ids = [str(row.get("asset_id", "")) for row in profiles]
    if len(asset_ids) != len(set(asset_ids)):
        raise ValueError("duplicate asset_id in table profiles")
    allowed_asset_ids = set(asset_ids)

    contexts = _candidate_values_by_asset(
        context_candidates, allowed_asset_ids=allowed_asset_ids
    )
    anchors = _candidate_values_by_asset(
        anchor_candidates, allowed_asset_ids=allowed_asset_ids
    )
    recommended_responsibilities = _candidate_values_by_asset(
        responsibility_candidates,
        allowed_asset_ids=allowed_asset_ids,
        predicate=lambda row: row.get("recommended_profile_eligible") is True,
    )
    discovered_responsibilities = _candidate_values_by_asset(
        responsibility_candidates,
        allowed_asset_ids=allowed_asset_ids,
        predicate=lambda row: row.get("vocabulary_layer") == "DISCOVERY",
    )
    field_by_asset = {
        str(row.get("asset_id")): row for row in field_summaries if row.get("asset_id")
    }

    enriched_profiles: list[dict[str, Any]] = []
    for profile in profiles:
        asset_id = str(profile["asset_id"])
        field_status = str(
            field_by_asset.get(asset_id, {}).get(
                "field_assistance_status", "NOT_EVALUABLE"
            )
        )
        enriched = dict(profile)
        enriched["reader_summary"] = {
            "contexts": contexts.get(asset_id, []),
            "anchors": anchors.get(asset_id, []),
            "recommended_responsibilities": recommended_responsibilities.get(
                asset_id, []
            ),
            "discovered_responsibilities": discovered_responsibilities.get(
                asset_id, []
            ),
            "field_assistance_status": field_status,
        }
        enriched_profiles.append(enriched)

    assertion_subjects = {
        str(row.get("assertion_id")): str(row.get("subject_id"))
        for row in assertions
        if row.get("assertion_id") and row.get("subject_id") in allowed_asset_ids
    }
    reviewed_asset_ids = {
        assertion_subjects[str(decision.get("assertion_id"))]
        for decision in review_decisions
        if str(decision.get("assertion_id")) in assertion_subjects
    }
    disposition_counts = Counter(str(row.get("disposition", "UNKNOWN")) for row in profiles)
    field_counts = Counter(
        row["reader_summary"]["field_assistance_status"] for row in enriched_profiles
    )
    stats = {
        "scope": {"metric_kind": "scope", "total_tables": len(profiles)},
        "dispositions": {
            "metric_kind": "mutually_exclusive",
            "values": dict(sorted(disposition_counts.items())),
        },
        "candidate_coverage": {
            "metric_kind": "overlapping_status",
            "contexts": len(contexts),
            "anchors": len(anchors),
            "responsibilities": len(
                set(recommended_responsibilities) | set(discovered_responsibilities)
            ),
        },
        "states": {
            "metric_kind": "overlapping_status",
            "unknown": sum(
                bool(row.get("candidate_summary", {}).get("has_unknown"))
                for row in profiles
            ),
            "conflict": sum(
                bool(row.get("candidate_summary", {}).get("has_conflict"))
                for row in profiles
            ),
        },
        "field_assistance": {
            "metric_kind": "mutually_exclusive",
            "values": dict(sorted(field_counts.items())),
        },
        "review": {
            "metric_kind": "review_status",
            "decision_count": len(review_decisions),
            "reviewed_table_count": len(reviewed_asset_ids),
            "unreviewed_table_count": len(profiles) - len(reviewed_asset_ids),
        },
    }
    indexes = {
        "dispositions": {
            disposition: sorted(
                str(row["asset_id"])
                for row in profiles
                if str(row.get("disposition", "UNKNOWN")) == disposition
            )
            for disposition in sorted(disposition_counts)
        },
        "contexts": _candidate_facets(
            context_candidates, allowed_asset_ids=allowed_asset_ids
        ),
        "anchors": _candidate_facets(
            anchor_candidates, allowed_asset_ids=allowed_asset_ids
        ),
        "responsibilities": _candidate_facets(
            [
                row
                for row in responsibility_candidates
                if row.get("recommended_profile_eligible") is True
            ],
            allowed_asset_ids=allowed_asset_ids,
        ),
        "discovered_responsibilities": _candidate_facets(
            [
                row
                for row in responsibility_candidates
                if row.get("vocabulary_layer") == "DISCOVERY"
            ],
            allowed_asset_ids=allowed_asset_ids,
        ),
    }
    return enriched_profiles, stats, indexes


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
    profiles, reader_stats, reader_indexes = _prepare_reader_catalog(
        profiles,
        context_candidates=context_candidates,
        anchor_candidates=anchor_candidates,
        responsibility_candidates=responsibility_candidates,
        field_summaries=field_summaries,
        assertions=assertions,
        review_decisions=review_decisions,
    )
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
        "reader_stats": reader_stats,
        "indexes": {
            **reader_indexes,
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
    index_path.write_text(_reader_html_document(len(profiles), shard_size), encoding="utf-8")
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


def _reader_html_document(table_count: int, page_size: int) -> str:
    title = html.escape(f"TRADEFLOW 表语义地图（{table_count} 张表）")
    template = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#f4f6f4;--card:#fff;--ink:#1d2925;--muted:#66726d;--line:#d9e0dc;--accent:#27604f;--soft:#eaf2ee;--warn:#925d17;--bad:#8b3a3a}
*{box-sizing:border-box}body{margin:0;font:14px/1.55 system-ui,"Microsoft YaHei",sans-serif;background:var(--bg);color:var(--ink)}
header{padding:18px 24px;background:#173f35;color:white}header h1{font-size:22px;margin:0}header p{margin:5px 0 0;color:#d2e3dd}
.overview{padding:12px 16px 0}.overview-head{display:flex;justify-content:space-between;align-items:end;gap:12px}.overview-head h2{margin:0;font-size:16px}
.metric-grid{display:grid;grid-template-columns:repeat(5,minmax(150px,1fr));gap:10px;margin-top:10px}.metric{background:white;border:1px solid var(--line);border-radius:9px;padding:12px}.metric strong{display:block;font-size:22px}.metric small{display:block;color:var(--muted)}
.layout{display:grid;grid-template-columns:minmax(230px,22%) minmax(520px,42%) minmax(420px,36%);gap:10px;padding:10px 16px 16px;height:calc(100vh - 255px);min-height:520px}.panel{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:14px;overflow:auto}
h2{font-size:16px;margin:0 0 10px}h3{font-size:14px;margin:16px 0 7px}.hint,.muted{color:var(--muted)}
input,select,button{font:inherit;border:1px solid var(--line);border-radius:6px;background:white;padding:7px 9px}input{width:100%;margin:8px 0}button{cursor:pointer}button:hover{border-color:var(--accent)}button:disabled{cursor:default;opacity:.45}
.facet{display:flex;width:100%;align-items:center;justify-content:space-between;text-align:left;margin:5px 0}.facet.active{background:var(--soft);border-color:var(--accent)}.count{color:var(--muted);font-variant-numeric:tabular-nums}
.scope{padding:9px;border-radius:7px;background:var(--soft);margin:8px 0}.scope strong{display:block}.scope button{margin-top:7px}.loading{font-size:12px;color:var(--muted)}.loading.bad{color:var(--bad)}
.matrix{width:100%;border-collapse:collapse;table-layout:fixed}.matrix th:nth-child(1){width:37%}.matrix th:nth-child(2){width:41%}.matrix th:nth-child(3){width:22%}.matrix th,.matrix td{padding:8px 7px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left;overflow-wrap:anywhere}.matrix th{position:sticky;top:-14px;background:white;z-index:2;font-size:12px;color:var(--muted)}.matrix tr:hover td{background:#fafcfb}.table-link{border:0;padding:0;color:var(--accent);font-weight:650;text-align:left;background:transparent;overflow-wrap:anywhere}.comment{display:block;color:var(--muted);font-size:12px}
.tag{display:inline-block;padding:2px 6px;margin:2px;border-radius:999px;background:var(--soft);color:#254b40;font-size:12px;white-space:nowrap}.tag.warn{background:#f5e9d8;color:var(--warn)}.tag.bad{background:#f5dddd;color:var(--bad)}.tag.field{background:#edf0f7;color:#3f4e70}.semantic-cell small{display:block;color:var(--muted);margin-top:3px}.state-cell{min-width:0}
.pager{display:flex;align-items:center;justify-content:center;gap:8px;margin-top:10px}.empty{padding:20px;color:var(--muted);text-align:center}.boundary{border-left:3px solid #c7a35a;padding:8px 10px;background:#fbf7ed}
.assertion{border:1px solid var(--line);border-radius:8px;padding:10px;margin:9px 0}.assertion-head{display:flex;justify-content:space-between;gap:8px}.assertion h4{margin:0}.evidence{padding-left:18px;margin:5px 0}.evidence li{margin:4px 0}.field-use{background:#f0f3f9;padding:7px;border-radius:6px;margin-top:7px}
.special{border-top:1px solid var(--line);margin-top:16px;padding-top:4px}.special-item{display:block;width:100%;text-align:left;margin:5px 0}.special-item small{display:block;color:var(--muted)}details.tech{margin-top:14px}details.tech pre{white-space:pre-wrap;word-break:break-word;background:#f2f4f2;padding:8px}
@media(max-width:1150px){.metric-grid{grid-template-columns:repeat(2,1fr)}.layout{grid-template-columns:1fr;height:auto}.panel{max-height:none}}
</style></head><body>
<header><h1>__TITLE__</h1><p>候选 Projection；字段只作辅助证据。工程 Gate 通过不等于人工确认或业务验收。</p></header>
<section class="overview"><div class="overview-head"><h2>① 全貌</h2><span class="hint">统计分为互斥分布和可重叠状态，不能相加成“已分类总数”。</span></div><div id="overview" class="metric-grid"></div></section>
<main class="layout">
<aside class="panel"><h2>② 表语义导航</h2><p class="hint">树只用于浏览，候选允许多值；没有证据的分类轴不会补齐。</p><input id="search" placeholder="在当前范围内搜索表名、注释或 asset_id"><select id="filter"><option value="all">全部状态</option><option value="conflict">Conflict</option><option value="unknown">Unknown</option><option value="used">字段已用于判断</option><option value="not-used">字段未用于判断</option><option value="variant">变体或其他处置</option></select><div id="scope-summary" class="scope"></div><div id="loading-state" class="loading"></div><h3>业务上下文</h3><div id="contexts"></div><h3>业务锚点</h3><div id="anchors"></div><h3>推荐职责候选</h3><div id="responsibilities"></div><details><summary>语料发现职责表达</summary><p class="hint">保留真实表注释表达，尚未归入规范职责。</p><div id="discovered-responsibilities"></div></details><section class="special"><h3>专项复核</h3><p class="hint">保留完整物理清单和方法验证样本，但不让它们冒充默认业务目录。</p><div id="special-review"></div></section></aside>
<section class="panel"><h2>③ 表目录矩阵</h2><p class="hint">默认先看主体候选；后缀/变体或其他处置表仍完整保留。每张表始终使用同一 asset_id。</p><table class="matrix"><thead><tr><th>表</th><th>表级判断</th><th>证据与状态</th></tr></thead><tbody id="tables"></tbody></table><div class="pager"><button id="prev">上一页</button><span id="page"></span><button id="next">下一页</button></div></section>
<section class="panel"><h2>④ 单表画像与证据</h2><div id="detail" class="empty">从中间选择一张表，查看它可能承担什么职责、哪些字段支持或反驳，以及还缺什么证据。</div></section>
</main><script src="data/catalog.js"></script><script src="data/details.js"></script><script>
const catalog=window.TABLE_SEMANTIC_CATALOG,details=window.TABLE_SEMANTIC_DETAILS,pageSize=__PAGE_SIZE__,dispositionIndexes=catalog.indexes.dispositions||{},subjectAssetIds=dispositionIndexes.SUBJECT||[],otherAssetIds=Object.entries(dispositionIndexes).filter(([value])=>value!=='SUBJECT').flatMap(([,ids])=>ids);
const loadedRows=new Map(catalog.first_tables.map(row=>[row.asset_id,row]));let rows=[...loadedRows.values()],page=0,activeAssetIds=new Set(subjectAssetIds),activeScope=`主体候选 ${subjectAssetIds.length} 张`,failedShards=[],loadingDone=false;
const $=id=>document.getElementById(id),esc=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const uniq=items=>[...new Set(items)];
const fieldLabel=value=>({USED:'已用于具体判断',NOT_USED:'有字段信息，未用于判断',NOT_EVALUABLE:'字段辅助不可评估'}[value]||value);
const fieldShortLabel=value=>({USED:'字段已使用',NOT_USED:'字段未使用',NOT_EVALUABLE:'字段不可评估'}[value]||value);
const dispositionLabel=value=>({SUBJECT:'主体表',LIKELY_VARIANT:'可能变体',STANDALONE:'独立对象',UNKNOWN:'处置未知'}[value]||value);
const cardName=value=>({"trs-collaboration":'TRS 协作样本',"option-collaboration":'期权协作样本',"current-history-holding":'当前/历史持仓对照',"name-counterexamples":'名称反例',"mapping-contrast":'映射类对照'}[value]||value);
const semanticLabel=value=>({TRS:'收益互换（TRS）',OPTION:'场外期权（OPTION）',IRS:'利率互换（IRS）',OTC_SHARED:'场外共享（OTC_SHARED）',CONTRACT:'合约',POSITION:'持仓',EVENT:'事件',MAPPING:'映射',MASTER_RECORD:'主记录',DETAIL_OR_LEG:'明细或合约腿',CONFIGURATION:'配置或参数',REPORT_OR_WRITEBACK:'报表或回写',HISTORY_STATE:'历史状态',LIFECYCLE_EVENT:'存续期事件',CURRENT_STATE:'当前状态',APPROVAL_OR_AUDIT_TRAIL:'审批或审计轨迹',MAPPING_DEFINITION:'映射定义',OPERATIONAL_LOG:'操作日志'}[value]||value);
function chips(values,kind=''){return values.length?values.map(value=>`<span class="tag ${kind}">${esc(semanticLabel(value))}</span>`).join(''):'<span class="muted">未形成</span>'}
function renderOverview(){const s=catalog.reader_stats,d=s.dispositions.values,f=s.field_assistance.values,r=s.review;const subject=d.SUBJECT||0,other=s.scope.total_tables-subject;$('overview').innerHTML=`<div class="metric"><small>范围</small><strong>${s.scope.total_tables}</strong><span>张表</span><small>当前固定运行</small></div><div class="metric"><small>物理处置（互斥）</small><strong>${subject} / ${other}</strong><span>主体 / 变体或其他</span><small>合计等于全量</small></div><div class="metric"><small>业务切面（可重叠）</small><strong>${s.candidate_coverage.contexts} / ${s.candidate_coverage.anchors}</strong><span>上下文 / 锚点覆盖</span><small>一张表可重复出现</small></div><div class="metric"><small>证据状态（可重叠）</small><strong>${s.states.unknown} / ${s.states.conflict}</strong><span>Unknown / Conflict</span><small>不是错误率</small></div><div class="metric"><small>字段辅助与人工审阅</small><strong>${f.USED||0} / ${r.reviewed_table_count}</strong><span>字段已使用 / 已审表</span><small>人工审阅 ${r.decision_count} 条 · 读者交付：待用户确认</small></div>`}
function currentRows(){const q=$('search').value.trim().toUpperCase(),filter=$('filter').value;return rows.filter(row=>{const summary=row.reader_summary||{};if(activeAssetIds&&!activeAssetIds.has(row.asset_id))return false;if(q&&!JSON.stringify([row.object_name,row.object_comment,row.asset_id]).toUpperCase().includes(q))return false;if(filter==='conflict'&&!row.candidate_summary?.has_conflict)return false;if(filter==='unknown'&&!(row.candidate_summary?.has_unknown||row.disposition==='UNKNOWN'))return false;if(filter==='used'&&summary.field_assistance_status!=='USED')return false;if(filter==='not-used'&&summary.field_assistance_status!=='NOT_USED')return false;if(filter==='variant'&&row.disposition==='SUBJECT')return false;return true})}
function activeConditions(){const items=[activeScope];if($('search').value.trim())items.push(`搜索：${$('search').value.trim()}`);if($('filter').value!=='all')items.push(`状态：${$('filter').selectedOptions[0].textContent}`);return items}
function renderScope(){const data=currentRows(),conditions=activeConditions();$('scope-summary').innerHTML=`<strong>当前结果 ${data.length} / 全量 ${catalog.table_count}</strong><span>${conditions.length?esc(conditions.join('；')):'未应用筛选'}</span><br><button id="return-to-subjects">主体候选 ${subjectAssetIds.length}</button> <button id="scope-show-other">其他处置 ${otherAssetIds.length}</button> <button id="show-all-physical">全部物理表 ${catalog.table_count}</button>`;$('return-to-subjects').onclick=showSubjects;$('scope-show-other').onclick=showOtherTables;$('show-all-physical').onclick=showAllPhysical}
function renderLoading(){const complete=loadingDone&&!failedShards.length&&loadedRows.size===catalog.table_count;if(complete){$('loading-state').className='loading';$('loading-state').textContent=`全部分片加载完成：已加载 ${loadedRows.size} / ${catalog.table_count}`}else if(failedShards.length){$('loading-state').className='loading bad';$('loading-state').textContent=`加载不完整：已加载 ${loadedRows.size} / ${catalog.table_count}；失败 ${failedShards.join('、')}`}else{$('loading-state').className='loading';$('loading-state').textContent=`正在加载：已加载 ${loadedRows.size} / ${catalog.table_count}`}}
function tableRow(row){const s=row.reader_summary||{},state=[];if(row.candidate_summary?.has_unknown)state.push('<span class="tag warn">Unknown</span>');if(row.candidate_summary?.has_conflict)state.push('<span class="tag bad">Conflict</span>');state.push(`<span class="tag">${esc(dispositionLabel(row.disposition))}</span>`);const contexts=[...(s.contexts||[]),...(s.anchors||[])],responsibilities=s.recommended_responsibilities||[],discovered=(s.discovered_responsibilities||[]).length;return `<tr><td><button class="table-link" data-asset="${esc(row.asset_id)}">${esc(row.object_name)}</button><span class="comment">${esc(row.object_comment||'无表注释')}</span></td><td class="semantic-cell"><small>业务切面</small>${chips(contexts)}<small>推荐职责</small>${chips(responsibilities)}${discovered?`<small>另有 ${discovered} 条语料发现表达，进入详情查看</small>`:''}</td><td class="state-cell">${state.join('')}<br><span class="tag field">${esc(fieldShortLabel(s.field_assistance_status||'NOT_EVALUABLE'))}</span></td></tr>`}
function renderTables(){const data=currentRows(),max=Math.max(0,Math.ceil(data.length/pageSize)-1);page=Math.min(page,max);$('tables').innerHTML=data.length?data.slice(page*pageSize,(page+1)*pageSize).map(tableRow).join(''):'<tr><td colspan="3" class="empty">当前条件下没有表</td></tr>';$('page').textContent=`第 ${page+1} / ${max+1} 页`;$('prev').disabled=page<=0;$('next').disabled=page>=max;document.querySelectorAll('[data-asset]').forEach(button=>button.onclick=()=>showTable(button.dataset.asset));renderScope();renderLoading()}
function setScope(label,assetIds){activeScope=label;activeAssetIds=new Set(assetIds);page=0;renderTables()}
function resetScopeControls(){$('search').value='';$('filter').value='all';page=0;document.querySelectorAll('.facet.active').forEach(node=>node.classList.remove('active'))}
function showSubjects(){resetScopeControls();activeScope=`主体候选 ${subjectAssetIds.length} 张`;activeAssetIds=new Set(subjectAssetIds);renderTables()}
function showOtherTables(){resetScopeControls();activeScope=`后缀/变体或其他处置 ${otherAssetIds.length} 张`;activeAssetIds=new Set(otherAssetIds);renderTables()}
function showAllPhysical(){resetScopeControls();activeScope=`全部物理表 ${catalog.table_count} 张`;activeAssetIds=null;renderTables()}
function clearScope(){showSubjects()}
function renderFacetList(id,kind,facets){const visible=facets.slice(0,18),more=facets.slice(18);const button=row=>`<button class="facet" data-kind="${kind}" data-value="${esc(row.value)}"><span>${esc(semanticLabel(row.value))}</span><span class="count">${row.table_count} 张</span></button>`;$(id).innerHTML=visible.map(button).join('')+(more.length?`<details><summary>更多（${more.length}）</summary>${more.map(button).join('')}</details>`:'');document.querySelectorAll(`[data-kind="${kind}"]`).forEach(node=>node.onclick=()=>{document.querySelectorAll('.facet.active').forEach(item=>item.classList.remove('active'));node.classList.add('active');const row=facets.find(item=>item.value===node.dataset.value);setScope(`${kind==='context'?'业务上下文':kind==='anchor'?'业务锚点':'表职责'}：${semanticLabel(row.value)}`,row.asset_ids)})}
function limitationLabel(value){return ({'metadata text proposes a candidate; it is not business acceptance':'元数据文本仅提出候选，不代表业务确认','field combination supports a table-level candidate; it does not prove row-level behavior':'字段组合仅支持表级候选，不证明行级业务行为','test environment snapshot only':'仅为测试环境快照','not a declared foreign key, production rule, or business acceptance':'不是已声明外键、生产规则或业务确认','no business key values or row samples retained':'未保留业务键值或行样本'})[value]||value}
function evidenceItems(ids,emptyText){const rows=(ids||[]).map(id=>details.evidence.find(item=>item.evidence_id===id)).filter(Boolean);return rows.length?`<ul class="evidence">${rows.map(row=>`<li>${esc(row.content_excerpt||row.source_locator||row.evidence_id)}${(row.limitations||[]).length?`<small class="muted"> · 限制：${esc(row.limitations.map(limitationLabel).join('；'))}</small>`:''}</li>`).join('')}</ul>`:`<span class="muted">${emptyText}</span>`}
function mergeAssertions(items){const groups=new Map();items.forEach(item=>{const key=`${item.predicate}\u0000${item.object_value||''}`,group=groups.get(key)||{predicate:item.predicate,object_value:item.object_value,assertion_ids:[],evidence_refs:[],counterevidence_refs:[],method_ids:[],outcomes:[]};group.assertion_ids.push(item.assertion_id);group.evidence_refs.push(...(item.evidence_refs||[]));group.counterevidence_refs.push(...(item.counterevidence_refs||[]));group.method_ids.push(item.method_id||'未记录');group.outcomes.push(item.outcome||'CANDIDATE');groups.set(key,group)});return [...groups.values()].map(group=>({...group,assertion_ids:uniq(group.assertion_ids),evidence_refs:uniq(group.evidence_refs),counterevidence_refs:uniq(group.counterevidence_refs),method_ids:uniq(group.method_ids),outcomes:uniq(group.outcomes)}))}
function fieldRoleLabel(value){return ({SUPPORT:'支持',SUPPORTS:'支持',DISTINGUISH:'区分',DISTINGUISHES:'区分',COUNTER:'反驳',COUNTERS:'反驳'})[value]||value||'支持'}
function renderAssertion(assertion,fieldSummary){const ids=new Set(assertion.assertion_ids||[assertion.assertion_id]),fieldLinks=(fieldSummary?.assertion_links||[]).filter(link=>ids.has(link.assertion_id)),reviews=details.review_decisions.filter(item=>ids.has(item.assertion_id)),outcomes=assertion.outcomes||[assertion.outcome||'CANDIDATE'],methods=assertion.method_ids||[assertion.method_id||'未记录'];const fields=fieldLinks.length?fieldLinks.map(link=>`<div class="field-use"><strong>${esc(fieldRoleLabel(link.role))}</strong>：${esc((link.source_column_names||[]).join('、')||link.marker||'字段未定位')}<br><small>字段作用只针对这项判断，不参与表标签投票。</small></div>`).join(''):'<div class="field-use muted">字段未用于这项判断</div>';return `<article class="assertion"><div class="assertion-head"><h4>${esc(semanticLabel(assertion.object_value||assertion.predicate))}</h4><span class="tag ${outcomes.includes('UNKNOWN')?'warn':''}">${esc(outcomes.join(' / '))}</span></div><small class="muted">${esc(assertion.predicate)} · ${ids.size} 条来源断言 · 方法 ${esc(methods.join('、'))}</small><h4>直接证据</h4>${evidenceItems(assertion.evidence_refs,'没有直接证据')}<h4>反证</h4>${evidenceItems(assertion.counterevidence_refs,'没有显式反证')}${fields}<p><small>人工决定：${reviews.length?esc(reviews.map(review=>review.decision||review.outcome||review.decision_id).join('；')):'尚无人工审阅'}</small></p></article>`}
function relationCard(relation){return `<article class="assertion"><div class="assertion-head"><h4>${esc(relation.predicate||'RELATED_TO')}</h4><span class="tag">${esc(relation.outcome||'CANDIDATE')}</span></div><p><code>${esc(String(relation.subject_asset_id||'').split(':').pop())}</code> ${relation.directed?'→':'↔'} <code>${esc(String(relation.object_asset_id||'').split(':').pop())}</code></p><h4>直接证据</h4>${evidenceItems(relation.evidence_refs,'没有直接证据')}<h4>反证</h4>${evidenceItems(relation.counterevidence_refs,'没有显式反证')}</article>`}
function assertionSection(title,assertions,fieldSummary){return `<h3>${title}</h3>${assertions.length?assertions.map(item=>renderAssertion(item,fieldSummary)).join(''):'<p class="muted">未形成候选，保持 Unknown。</p>'}`}
function showTable(id,push=true){const row=loadedRows.get(id);if(!row)return;if(push)history.pushState({asset_id:id},'',`#${encodeURIComponent(id)}`);const fieldSummary=details.field_support.find(item=>item.asset_id===id),assertions=mergeAssertions(details.assertions.filter(item=>item.subject_id===id)),relations=details.relations.filter(item=>item.subject_asset_id===id||item.object_asset_id===id),groups=details.memberships.filter(item=>item.asset_id===id),responsibilityPredicates=new Set(['HAS_TABLE_RESPONSIBILITY_CANDIDATE','HAS_RESPONSIBILITY_CANDIDATE']),recommendedValues=new Set(row.reader_summary?.recommended_responsibilities||[]),discoveredValues=new Set(row.reader_summary?.discovered_responsibilities||[]);const contexts=assertions.filter(item=>item.predicate==='HAS_BUSINESS_CONTEXT_CANDIDATE'),anchors=assertions.filter(item=>item.predicate==='HAS_BUSINESS_ANCHOR_CANDIDATE'),allResponsibilities=assertions.filter(item=>responsibilityPredicates.has(item.predicate)),responsibilities=allResponsibilities.filter(item=>recommendedValues.has(item.object_value)),discovered=allResponsibilities.filter(item=>discoveredValues.has(item.object_value)),otherResponsibilities=allResponsibilities.filter(item=>![...responsibilities,...discovered].includes(item)),other=assertions.filter(item=>![...contexts,...anchors,...allResponsibilities].includes(item));$('detail').className='';$('detail').innerHTML=`<h3>${esc(row.object_name)}</h3><p>${esc(row.object_comment||'无表注释')}</p><p>${chips([dispositionLabel(row.disposition)])}${row.candidate_summary?.has_unknown?'<span class="tag warn">Unknown</span>':''}${row.candidate_summary?.has_conflict?'<span class="tag bad">Conflict</span>':''}</p><div class="boundary">这是表级候选画像，不是正式业务定义。字段只解释具体判断；当前字段状态：<strong>${esc(fieldLabel(row.reader_summary?.field_assistance_status||'NOT_EVALUABLE'))}</strong>。</div>${assertionSection('业务上下文候选',contexts,fieldSummary)}${assertionSection('业务锚点候选',anchors,fieldSummary)}${assertionSection('推荐职责候选',responsibilities,fieldSummary)}${discovered.length?assertionSection('语料发现职责表达',discovered,fieldSummary):''}${otherResponsibilities.length?assertionSection('其他职责线索',otherResponsibilities,fieldSummary):''}${other.length?assertionSection('其他表级判断',other,fieldSummary):''}<h3>表间关系</h3>${relations.length?relations.map(relationCard).join(''):'<p class="muted">没有已输出关系；共享字段不等于外键或正式业务关系。</p>'}<h3>参与的表组</h3>${groups.length?chips(groups.map(item=>item.group_id)):'<p class="muted">未进入已输出表组。</p>'}<h3>仍需确认</h3><p>${row.candidate_summary?.has_unknown||row.candidate_summary?.has_conflict?'存在 Unknown 或 Conflict，请结合反证和业务人员判断。':'当前无显式冲突，但候选仍未经过人工确认。'}</p><details class="tech"><summary>审计与调试数据（一般无需查看）</summary><pre>${esc(JSON.stringify({profile:row,field_support:fieldSummary||{availability:'NOT_EVALUABLE'}},null,2))}</pre></details><p class="muted">Panorama Object Card：${esc(row.panorama_object_card||'未提供')}（物理事实入口）</p>`}
function showSpecial(kind,item,assetIds,description){setScope(`专项复核：${item}`,assetIds);$('detail').className='';$('detail').innerHTML=`<h3>${esc(item)}</h3><div class="boundary">${esc(description)}；当前仅显示 ${assetIds.length} 张成员表，不代表全量分类。</div><button id="return-to-subjects-detail">返回主体候选 ${subjectAssetIds.length}</button> <button id="show-all-physical-detail">查看全部物理表 ${catalog.table_count}</button>`;$('return-to-subjects-detail').onclick=showSubjects;$('show-all-physical-detail').onclick=showAllPhysical}
function renderOtherScope(){const breakdown=Object.entries(dispositionIndexes).filter(([value])=>value!=='SUBJECT').map(([value,ids])=>`${dispositionLabel(value)} ${ids.length}`).join(' / ');$('special-review').insertAdjacentHTML('beforebegin',`<details><summary>后缀/变体或其他处置（${otherAssetIds.length}）</summary><p class="hint">数字后缀只是处置线索，不等于备份、停用或可删除。${esc(breakdown)}</p><button id="show-other-tables">查看 ${otherAssetIds.length} 张其他处置表</button></details>`);$('show-other-tables').onclick=showOtherTables}
function renderSpecial(){const groups=catalog.indexes.groups||[],variants=catalog.indexes.variants||[],structural=catalog.indexes.structural_neighborhoods||[],cards=details.investigation_cards||[],members=groupId=>uniq(details.memberships.filter(item=>item.group_id===groupId).map(item=>item.asset_id)),groupLabel=item=>{const ids=members(item.group_id),first=String(ids[0]||item.group_id).split(':').pop();return item.anchor_value||`${first}${ids.length>1?' 等':''}`},businessGroupLabel=id=>`候选业务协作组 ${groups.findIndex(item=>item.group_id===id)+1}`,groupButton=(item,index)=>`<button class="special-item" data-special-kind="group" data-special-id="${esc(item.group_id)}"><strong>候选业务协作组 ${index+1}</strong><small>${members(item.group_id).length} 张成员表 · 尚待人工确认</small></button>`,cardButton=item=>`<button class="special-item" data-special-kind="card" data-special-id="${esc(item.card_id)}"><strong>${esc(cardName(item.card_id))}</strong><small>调查卡 · ${(item.members||[]).length} 张表 · ${esc(item.semantic_review_status||'未决')}</small></button>`,structuralButton=item=>`<button class="special-item" data-special-kind="${item.group_kind==='PHYSICAL_VARIANT_GROUP'?'variant':'structural'}" data-special-id="${esc(item.group_id)}"><strong>${esc(groupLabel(item))}</strong><small>${item.group_kind==='PHYSICAL_VARIANT_GROUP'?'物理变体候选':'结构邻域：仅结构线索，不是业务分类'} · ${members(item.group_id).length} 张表</small></button>`;$('special-review').innerHTML=`<details><summary>候选业务协作组（${groups.length}）</summary>${groups.map(groupButton).join('')}</details><details><summary>调查卡（${cards.length}）</summary>${cards.map(cardButton).join('')}</details><details><summary>物理变体组（${variants.length}）</summary>${variants.map(structuralButton).join('')}</details><details><summary>结构邻域（${structural.length}）</summary>${structural.map(structuralButton).join('')}</details>`;document.querySelectorAll('[data-special-kind]').forEach(button=>button.onclick=()=>{const kind=button.dataset.specialKind,id=button.dataset.specialId;if(kind==='card'){const card=cards.find(item=>item.card_id===id),ids=uniq((card?.members||[]).map(item=>item.asset_id));showSpecial(kind,cardName(id),ids,'调查卡是方法验证样本，不是全量分类')}else{const ids=members(id),description=kind==='group'?'业务协作组是有证据门槛的候选关系':kind==='variant'?'物理变体是名称与结构候选，不表示等价或废弃':'结构邻域是仅结构线索，不是业务分类';showSpecial(kind,kind==='group'?businessGroupLabel(id):groupLabel([...variants,...structural].find(item=>item.group_id===id)||{group_id:id}),ids,description)}})}
async function loadAll(){for(let index=0;index<catalog.shards.length;index++){const name=`TABLE_SEMANTIC_SHARD_${index}`;try{if(!window[name])await new Promise((resolve,reject)=>{const script=document.createElement('script');script.src=catalog.shards[index];script.onload=resolve;script.onerror=()=>reject(new Error(catalog.shards[index]));document.head.appendChild(script)});(window[name]||[]).forEach(row=>loadedRows.set(row.asset_id,row));rows=[...loadedRows.values()].sort((a,b)=>String(a.object_name).localeCompare(String(b.object_name)));renderTables()}catch(error){failedShards.push(catalog.shards[index]);renderTables()}}loadingDone=true;renderTables();const id=decodeURIComponent(location.hash.slice(1));if(id)showTable(id,false)}
$('search').oninput=()=>{page=0;renderTables()};$('filter').onchange=()=>{if($('filter').value==='variant'){showOtherTables();$('filter').value='variant'}page=0;renderTables()};$('prev').onclick=()=>{page=Math.max(0,page-1);renderTables()};$('next').onclick=()=>{page++;renderTables()};
renderOverview();renderFacetList('contexts','context',catalog.indexes.contexts);renderFacetList('anchors','anchor',catalog.indexes.anchors);renderFacetList('responsibilities','responsibility',catalog.indexes.responsibilities);renderFacetList('discovered-responsibilities','discovered-responsibility',catalog.indexes.discovered_responsibilities||[]);renderOtherScope();renderSpecial();renderTables();loadAll();window.onpopstate=()=>{const id=decodeURIComponent(location.hash.slice(1));if(id)showTable(id,false)};
</script></body></html>"""
    return template.replace("__TITLE__", title).replace(
        "__PAGE_SIZE__", str(page_size)
    )
