"""Static three-column review projection for context-enriched field semantics."""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path


AMOUNT_TERMS = (
    "金额",
    "本金",
    "保证金",
    "费用",
    "市值",
    "盈亏",
    "收益",
    "利息",
    "价格",
    "成本",
    "余额",
    "估值",
)
QUANTITY_TERMS = ("数量", "份额", "张数", "手数", "股数")
RATE_TERMS = ("比例", "比率", "汇率", "利率", "费率", "收益率", "波动率", "折扣率")
SUBJECT_TERMS = ("客户", "交易对手", "发行人", "主体", "机构", "账户")
EVENT_TERMS = ("成交", "平仓", "终止", "重置", "清算", "审批", "结算", "交割")
OBJECT_TERMS = ("合约", "交易", "持仓", "订单", "账簿", "产品", "标的")


def write_review_projection(root, result, config):
    """Write bounded indexes and concept shards usable directly over file://."""

    review = Path(root) / "review"
    data_dir = review / "data"
    shard_dir = data_dir / "concepts"
    shard_dir.mkdir(parents=True, exist_ok=True)
    for stale_shard in shard_dir.glob("*.js"):
        stale_shard.unlink()

    concepts = {
        str(row["business_concept_id"]): row for row in result.business_concepts
    }
    expressions_by_concept = defaultdict(list)
    for row in result.attribute_expressions:
        expressions_by_concept[str(row["business_concept_id"])].append(row)
    data_by_expression = {
        str(row["attribute_expression_id"]): row for row in result.data_candidates
    }
    contexts = {
        str(row["business_context_id"]): row for row in result.business_contexts
    }
    relations_by_subject = defaultdict(list)
    relations_by_object = defaultdict(list)
    for row in result.semantic_relations:
        relations_by_subject[str(row["subject_id"])].append(row)
        relations_by_object[str(row["object_id"])].append(row)
    assertions = {
        (str(row["subject_id"]), str(row["predicate"]), str(row["object_id"])): row
        for row in result.assertions
    }
    wiki = {str(row["candidate_id"]): row for row in result.wiki_candidates}
    data_by_candidate = {
        str(row["candidate_id"]): row for row in result.data_candidates
    }
    mappings_by_expression = defaultdict(list)
    object_comments = _load_object_comments(config.panorama_root)
    for row in result.mapping_candidates:
        data_candidate = data_by_candidate.get(str(row["data_candidate_id"]))
        if data_candidate:
            mappings_by_expression[
                str(data_candidate["attribute_expression_id"])
            ].append(row)

    catalog = []
    for concept_id, concept in concepts.items():
        expressions = expressions_by_concept.get(concept_id, [])
        if not expressions:
            continue
        field_count = sum(int(row["field_count"]) for row in expressions)
        object_ids = {
            str(instance["asset_id"])
            for row in expressions
            for instance in data_by_expression.get(
                str(row["attribute_expression_id"]), {}
            ).get("physical_instances", [])
        }
        paths = _navigation_paths(
            str(concept["label"]), concept.get("value_kinds", []), config
        )
        catalog.append(
            {
                "id": concept_id,
                "label": concept["label"],
                "status": concept.get("status", "CANDIDATE"),
                "normalizationStatus": concept.get("normalization_status", "IDENTITY"),
                "sourceConceptCount": len(concept.get("source_concept_ids", [])),
                "paths": paths,
                "expressionCount": len(expressions),
                "fieldCount": field_count,
                "tableCount": len(object_ids),
                "search": " ".join(
                    [str(concept["label"])]
                    + [str(row["label"]) for row in expressions]
                    + [
                        str(name)
                        for row in expressions
                        for name in data_by_expression.get(
                            str(row["attribute_expression_id"]), {}
                        ).get("physical_expressions", [])
                    ]
                ).upper(),
            }
        )
        shard = _concept_shard(
            concept,
            expressions,
            data_by_expression,
            contexts,
            relations_by_subject,
            relations_by_object,
            assertions,
            concepts,
            mappings_by_expression,
            wiki,
            object_comments,
            config,
        )
        shard_path = shard_dir / f"{concept_id}.js"
        shard_path.write_text(
            "window.FIELD_MAP_SHARDS=window.FIELD_MAP_SHARDS||{};"
            f"window.FIELD_MAP_SHARDS[{json.dumps(concept_id)}]="
            + json.dumps(shard, ensure_ascii=False, separators=(",", ":"))
            + ";\n",
            encoding="utf-8",
        )

    catalog.sort(key=lambda row: (-int(row["fieldCount"]), str(row["label"])))
    catalog_path = data_dir / "catalog.js"
    catalog_path.write_text(
        "window.FIELD_MAP_CATALOG="
        + json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    html_path = review / "index.html"
    html_path.write_text(
        _review_html(config.review_page_size, config.initial_navigation_limit),
        encoding="utf-8",
    )
    return {
        "review_index": html_path,
        "review_catalog": catalog_path,
        "review_shards": shard_dir,
    }


def _concept_shard(
    concept,
    expressions,
    data_by_expression,
    contexts,
    relations_by_subject,
    relations_by_object,
    assertions,
    concepts,
    mappings_by_expression,
    wiki,
    object_comments,
    config,
):
    expression_rows = []
    for expression in sorted(
        expressions,
        key=lambda row: (len(row.get("qualifier_signature", [])), str(row["label"])),
    ):
        expression_id = str(expression["attribute_expression_id"])
        data = data_by_expression.get(expression_id, {})
        context_rows = []
        seen_contexts = set()
        for relation in relations_by_subject.get(expression_id, []):
            if relation["predicate"] != "APPEARS_IN":
                continue
            context = contexts.get(str(relation["object_id"]))
            if not context:
                continue
            context_key = (str(context["label"]), str(context["context_type"]))
            if context_key in seen_contexts:
                continue
            seen_contexts.add(context_key)
            assertion = assertions.get(
                (expression_id, "APPEARS_IN", str(relation["object_id"])), {}
            )
            context_rows.append(
                {
                    "label": context["label"],
                    "type": context["context_type"],
                    "status": assertion.get("status", "CANDIDATE"),
                    "evidenceRefs": assertion.get("evidence_refs", []),
                }
            )
        physical = defaultdict(list)
        for instance in data.get("physical_instances", []):
            row = dict(instance)
            row["objectComment"] = object_comments.get(str(instance["asset_id"]), "")
            row["objectUrl"] = _object_url(
                config.panorama_root, str(instance["asset_id"])
            )
            physical[str(instance["column_name"])].append(row)
        wiki_rows = []
        seen_pages = set()
        for mapping in mappings_by_expression.get(expression_id, []):
            candidate = wiki.get(str(mapping["wiki_candidate_id"]))
            if not candidate or str(candidate["page_id"]) in seen_pages:
                continue
            seen_pages.add(str(candidate["page_id"]))
            wiki_rows.append(
                {
                    "pageId": candidate["page_id"],
                    "title": candidate["title"],
                    "path": candidate.get("ancestor_path", []),
                    "signals": mapping.get("signals", []),
                    "status": mapping.get("status", "CANDIDATE"),
                }
            )
        expression_rows.append(
            {
                "id": expression_id,
                "label": expression["label"],
                "parentId": expression.get("display_parent_expression_id"),
                "status": expression.get("status", "CANDIDATE"),
                "supportStatus": expression.get("support_status"),
                "qualifiers": expression.get("qualifier_signature", []),
                "contextualQualifiers": expression.get("contextual_qualifiers", []),
                "fieldCount": expression.get("field_count", 0),
                "tableCount": expression.get("object_count", 0),
                "contexts": sorted(context_rows, key=lambda row: str(row["label"])),
                "physicalGroups": [
                    {"name": name, "instances": rows}
                    for name, rows in sorted(physical.items())
                ],
                "wikiEvidence": wiki_rows[:8],
                "conflicts": expression.get("conflicts", []),
            }
        )
    concept_id = str(concept["business_concept_id"])
    related = {}
    for relation in relations_by_subject.get(concept_id, []) + relations_by_object.get(
        concept_id, []
    ):
        if relation["predicate"] != "RELATED_TO":
            continue
        other_id = (
            str(relation["object_id"])
            if str(relation["subject_id"]) == concept_id
            else str(relation["subject_id"])
        )
        other = concepts.get(other_id)
        if other:
            related[other_id] = {"id": other_id, "label": other["label"]}
    return {
        "concept": {
            "id": concept_id,
            "label": concept["label"],
            "status": concept.get("status", "CANDIDATE"),
            "supportStatus": concept.get("support_status"),
            "normalizationStatus": concept.get("normalization_status", "IDENTITY"),
            "sourceLabels": concept.get("source_labels", [concept["label"]]),
            "semanticScope": concept.get("semantic_scope"),
            "navigationPaths": _navigation_paths(
                str(concept["label"]), concept.get("value_kinds", []), config
            ),
        },
        "expressions": expression_rows,
        "relatedConcepts": sorted(related.values(), key=lambda row: str(row["label"])),
    }


def _navigation_paths(label, value_kinds, config=None):
    terms = config.navigation_terms if config else {}
    family_labels = config.family_labels if config else {}
    attribute_types = getattr(config, "attribute_navigation", None)
    if config is None or attribute_types is None:
        attribute_types = _DEFAULT_ATTRIBUTE_TYPES
    container_patterns = getattr(config, "container_patterns", None)
    if config is None or container_patterns is None:
        container_patterns = _DEFAULT_CONTAINER_PATTERNS
    navigation_label = _strip_navigation_pattern(
        str(label).strip(), container_patterns
    )
    attribute_patterns = tuple(
        pattern for patterns in attribute_types.values() for pattern in patterns
    )
    family = _semantic_head_family(
        navigation_label,
        value_kinds,
        terms,
        attribute_patterns,
        (),
        getattr(
            config,
            "semantic_family_order",
            ("TIME", "DATE", "RATE", "QUANTITY", "AMOUNT"),
        ),
    )
    if family:
        fallback_root = "日期时间" if family in {"DATE", "TIME"} else "业务度量"
        fallback_label = {
            "AMOUNT": "金额",
            "QUANTITY": "数量",
            "RATE": "比率",
            "DATE": "日期",
            "TIME": "时间",
        }[family]
        return [
            [
                _navigation_root(config, family, fallback_root),
                family_labels.get(family, fallback_label),
            ]
        ]
    subject_terms = config.subjects if config else SUBJECT_TERMS
    event_terms = config.events if config else EVENT_TERMS
    object_terms = config.objects if config else OBJECT_TERMS
    semantic_terms = (
        ("PARTY", "业务主体", subject_terms),
        ("EVENT", "业务事件", event_terms),
        ("OBJECT", "业务对象", object_terms),
    )
    attribute_type = _attribute_navigation_type(navigation_label, attribute_types)
    entity = _entity_navigation(navigation_label, semantic_terms, attribute_patterns)
    if entity:
        family, fallback_root, term, is_attribute = entity
        path = [_navigation_root(config, family, fallback_root)]
        if is_attribute:
            template = getattr(
                config, "entity_attribute_template", "{entity}属性"
            )
            path.append(template.format(entity=term))
        return [path]
    if attribute_type:
        return [
            [
                _navigation_root(config, "ATTRIBUTE", "字段属性"),
                attribute_type,
            ]
        ]
    return [["待归类"]]


_DEFAULT_ATTRIBUTE_TYPES = {
    "标识": ("*ID", "*编号", "*编码", "*主键", "*流水号"),
    "名称": ("*名称", "*短名", "*简称", "*缩写"),
    "说明备注": ("*备注", "*说明", "*描述"),
    "状态标志": ("*类型", "*状态", "*标志", "*结果", "*方式", "是否*"),
}
_DEFAULT_CONTAINER_PATTERNS = ("*列表", "*清单", "*集合")


def _semantic_head_family(
    label,
    value_kinds,
    terms,
    attribute_patterns=(),
    container_patterns=(),
    family_order=("TIME", "DATE", "RATE", "QUANTITY", "AMOUNT"),
):
    text = str(label).strip().upper()
    text = _strip_navigation_pattern(text, container_patterns)
    if any(_navigation_pattern_matches(text, pattern) for pattern in attribute_patterns):
        return None
    defaults = {
        "TIME": ("时间", "时刻"),
        "DATE": ("日期", "*日"),
        "RATE": RATE_TERMS,
        "QUANTITY": QUANTITY_TERMS,
        "AMOUNT": AMOUNT_TERMS,
    }
    candidates = tuple(
        (family, terms.get(family, defaults[family]))
        for family in family_order
        if family in defaults
    )
    matches = [
        family
        for family, family_terms in candidates
        if _matches_semantic_head(text, family_terms)
    ]
    if matches:
        return matches[0]
    if "TIME" in value_kinds:
        return "TIME"
    if "DATE" in value_kinds:
        return "DATE"
    return None


def _matches_semantic_head(text, terms):
    for raw_term in terms:
        term = str(raw_term).strip().upper().removeprefix("*")
        if term and text.endswith(term):
            return True
    return False


def _entity_navigation(label, semantic_terms, attribute_patterns=()):
    text = str(label).strip()
    upper = text.upper()
    exact_or_suffix = []
    for priority, (family, root, terms) in enumerate(semantic_terms):
        for index, raw_term in enumerate(terms):
            term = str(raw_term).strip()
            normalized = term.upper().removeprefix("*")
            if normalized and upper == normalized:
                exact_or_suffix.append(
                    (len(normalized), upper == normalized, -priority, -index, family, root, term)
                )
    if exact_or_suffix:
        _, _, _, _, family, root, term = max(exact_or_suffix)
        return family, root, term, False

    stripped = _strip_navigation_pattern_with_match(upper, attribute_patterns)
    if not stripped:
        return None
    stem, _ = stripped
    matches = []
    for priority, (family, root, terms) in enumerate(semantic_terms):
        for index, raw_term in enumerate(terms):
            term = str(raw_term).strip()
            normalized = term.upper().removeprefix("*")
            if normalized and stem.strip().upper() == normalized:
                matches.append(
                    (
                        len(normalized),
                        -priority,
                        -index,
                        family,
                        root,
                        term,
                        normalized,
                    )
                )
    if not matches:
        return None
    longest = max(item[0] for item in matches)
    most_specific = [item for item in matches if item[0] == longest]
    lexical_terms = {item[6] for item in most_specific}
    if len(lexical_terms) != 1:
        return None
    _, _, _, family, root, term, _ = max(most_specific)
    return family, root, term, True


def _attribute_navigation_type(label, attribute_types):
    text = str(label).strip().upper()
    matches = []
    for priority, (attribute_type, patterns) in enumerate(attribute_types.items()):
        for index, pattern in enumerate(patterns):
            if _navigation_pattern_matches(text, pattern):
                token = str(pattern).strip().strip("*")
                matches.append((len(token), -priority, -index, attribute_type))
    return max(matches)[3] if matches else None


def _strip_navigation_pattern(text, patterns):
    matched = _strip_navigation_pattern_with_match(text, patterns)
    return matched[0] if matched else text


def _strip_navigation_pattern_with_match(text, patterns):
    matches = []
    upper_text = text.upper()
    for index, raw_pattern in enumerate(patterns):
        pattern = str(raw_pattern).strip().upper()
        token = pattern.strip("*")
        if not token:
            continue
        if pattern.startswith("*") and upper_text.endswith(token):
            matches.append((len(token), -index, text[: -len(token)].strip(), token))
        elif pattern.endswith("*") and upper_text.startswith(token):
            matches.append((len(token), -index, text[len(token) :].strip(), token))
    if not matches:
        return None
    _, _, stem, token = max(matches)
    return stem, token


def _navigation_pattern_matches(text, raw_pattern):
    pattern = str(raw_pattern).strip().upper()
    if not pattern:
        return False
    if pattern.startswith("*") and pattern.endswith("*"):
        return pattern.strip("*") in text
    if pattern.startswith("*"):
        return text.endswith(pattern[1:])
    if pattern.endswith("*"):
        return text.startswith(pattern[:-1])
    return text == pattern


def _navigation_root(config, family, fallback):
    if config:
        for root, families in config.navigation_types.items():
            if family in families:
                return root
    return fallback


def _object_url(panorama_root, asset_id):
    from .render import _slug

    path = (Path(panorama_root) / "objects" / f"{_slug(asset_id)}.html").resolve()
    return path.as_uri() if path.exists() else ""


def _load_object_comments(panorama_root):
    path = Path(panorama_root) / "facts" / "objects.json"
    if not path.exists():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(row["asset_id"]): str(row.get("object_comment") or "")
        for row in rows
        if row.get("asset_id")
    }


def _review_html(page_size, initial_navigation_limit):
    return _HTML.replace("__PAGE_SIZE__", str(page_size)).replace(
        "__NAVIGATION_LIMIT__", str(initial_navigation_limit)
    )


_HTML = r"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>字段语义地图</title><style>
:root{--blue:#215da8;--line:#dbe3ee;--muted:#66758a;--bg:#f5f7fa;--chip:#edf3fb}*{box-sizing:border-box}body{margin:0;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;color:#182230;background:var(--bg)}header{position:sticky;top:0;z-index:5;background:white;border-bottom:1px solid var(--line);padding:12px 18px;display:flex;align-items:center;gap:18px}h1{font-size:22px;margin:0;white-space:nowrap}input{width:100%;padding:10px 12px;border:1px solid #b9c6d6;border-radius:8px;font-size:15px}.layout{display:grid;grid-template-columns:minmax(240px,23%) minmax(420px,37%) minmax(420px,40%);height:calc(100vh - 66px);gap:1px;background:var(--line)}.panel{background:white;overflow:auto;padding:16px}.panel h2{font-size:17px;margin:0 0 12px}.muted{color:var(--muted)}.technical-name{text-transform:lowercase}.nav-root,.nav-branch{margin:6px 0}.nav-root>summary{font-size:15px;padding:7px 4px}.nav-branch{margin-left:12px}.nav-branch>summary{padding:5px 4px;color:#34465c}.concept-list{margin-left:16px;border-left:1px solid var(--line);padding-left:5px}.concept{display:block;width:100%;text-align:left;border:0;background:transparent;padding:7px 9px;border-radius:6px;cursor:pointer}.concept:hover,.selected{background:var(--chip);color:#174e8c}.count{float:right;color:var(--muted);font-size:12px}.facet-panel{display:block}.facet-row{display:grid;grid-template-columns:72px 1fr;gap:8px;align-items:start;width:100%;padding:4px 0}.facet-row+.facet-row{border-top:1px dashed #e3eaf2}.facet-label{color:var(--muted);padding-top:3px}.facet-options{display:flex;flex-wrap:wrap;gap:5px}.facet-option{border:1px solid #cbd7e5;background:#f7f9fc;color:#34465c;padding:3px 9px;border-radius:999px;cursor:pointer}.facet-option:hover{border-color:#6e9bd0}.facet-option.active{background:var(--blue);border-color:var(--blue);color:white}.facet-reset{margin-bottom:5px}.facet-count{margin-left:4px;font-size:11px;opacity:.75}.matrix-wrap{overflow:auto;margin-top:10px;border:1px solid var(--line);border-radius:8px}.expression-matrix{margin:0;min-width:620px}.expression-matrix th{position:sticky;top:0;background:#f5f8fc;white-space:nowrap}.expression-matrix tr{cursor:pointer}.expression-matrix tbody tr:hover,.expression-matrix tbody tr.selected{background:var(--chip)}.expression-matrix td:first-child{font-weight:600;color:#214e7f}.matrix-count{text-align:right;white-space:nowrap}.detail-head{padding:4px 0 12px;border-bottom:1px solid var(--line)}.detail-head h2{font-size:22px;margin:0 0 3px;color:#183d68}.breadcrumb{color:var(--blue);margin:4px 0 9px}.metrics{font-weight:600;color:#43546a}.semantic-card{background:#f6f9fd;border:1px solid #d9e5f3;border-radius:9px;padding:11px 13px;margin-top:12px}.semantic-row{display:grid;grid-template-columns:72px 1fr;gap:8px;padding:5px 0}.semantic-row+.semantic-row{border-top:1px solid #e5edf6}.semantic-key{color:var(--muted)}.section{border-top:1px solid var(--line);padding-top:11px;margin-top:12px;text-align:left}.section h3{font-size:15px;margin:0 0 8px;text-align:left}.chips{display:flex;flex-wrap:wrap;gap:6px}.chip{background:var(--chip);border:0;padding:3px 8px;border-radius:999px}.status{display:inline-block;padding:2px 7px;border-radius:999px;background:#fff5d6;color:#735600}.conflict{background:#fdebec;color:#a42b32}.physical{border:1px solid var(--line);border-radius:8px;margin:7px 0;padding:9px 11px}.physical summary{text-align:left;color:#264d78}.physical table{font-size:13px}details{margin:6px 0}summary{cursor:pointer;font-weight:600;text-align:left}table{width:100%;border-collapse:collapse;margin-top:6px}td,th{border-bottom:1px solid var(--line);padding:6px;text-align:left;vertical-align:top}a{color:var(--blue)}.pager{display:flex;gap:8px;align-items:center;margin-top:8px}.empty{padding:30px;color:var(--muted);text-align:center}.folded-info{padding:8px 0}.folded-info summary{color:#52657b}.related-preview{color:var(--muted);font-size:13px;margin-left:6px}@media(max-width:1000px){.layout{grid-template-columns:1fr;height:auto}.panel{max-height:none;min-height:260px}}
</style></head><body><header><h1>字段语义地图</h1><input id="search" placeholder="搜索业务概念、属性表达或英文字段名，例如：名义本金"></header>
<main class="layout"><section class="panel"><h2>① 业务语义导航</h2><div class="muted">字段发现为主；分类树仅用于浏览</div><div id="nav"></div></section><section class="panel"><h2>② 属性表达矩阵</h2><div id="concept-summary" class="muted">请选择概念</div><div id="facet-filter" class="chips section"></div><div id="expressions"></div></section><section class="panel"><h2>③ 当前表达详情</h2><div id="detail" class="empty">从中栏选择一个真实属性表达</div></section></main>
<script src="data/catalog.js"></script><script>
const PAGE=__PAGE_SIZE__,NAV_LIMIT=__NAVIGATION_LIMIT__,catalog=window.FIELD_MAP_CATALOG||[];let currentConcept='',currentExpr='',currentShard=null,activeFacets={},requestNo=0,searchTimer=0,matrixPage=0,physicalPages={};const expandedBranches=new Set(),byId=Object.fromEntries(catalog.map(x=>[x.id,x]));
function esc(x){return String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}function statusLabel(x){return x==='CONFLICT'?'存在冲突':x==='CONFIRMED'?'已确认':x==='REJECTED'?'已否定':x==='INSUFFICIENT_EVIDENCE'?'证据不足':'候选'}const DIM_ZH={currency_basis:'币种',measure_basis:'口径',position_side:'持仓方向',trade_side:'交易方向',cashflow_direction:'收付方向',variability:'变化方式',availability_state:'可用状态',estimation_status:'估算状态',aggregation_state:'累计口径',temporal_stage:'时点',party_role:'主体角色',flow_side:'数据侧',lifecycle_stage:'生命周期',attribute_kind:'属性种类'};const VALUE_ZH={UNDERLYING_CURRENCY:'标的币种',SETTLEMENT_CURRENCY:'结算币种',LOCAL_CURRENCY:'本币',ORIGINAL_CURRENCY:'原币',ABSOLUTE:'绝对',LONG:'多头',SHORT:'空头',BUY:'买方',SELL:'卖方',PAY:'支付',RECEIVE:'收取',DYNAMIC:'动态',AVAILABLE:'可用',ACCUMULATED:'累计',ESTIMATED:'预估',FIXED:'固定',FROZEN:'冻结',INITIAL:'初始',CURRENT:'当前',END:'期末',BEFORE_ADJUSTMENT:'调整前',AFTER_ADJUSTMENT:'调整后',COUNTERPARTY:'交易对手',CLIENT:'客户',INTERNAL:'内部',SOURCE:'源侧',TARGET:'目标',PRODUCT:'产品',CLEARING:'清算',EXECUTION:'成交',ORDER:'订单',POSITION:'持仓',TERMINATION:'终止',IDENTIFIER:'标识',UNKNOWN:'未确认'};function qvalue(q){return VALUE_ZH[q.value]||q.value}function qzh(q){return `${DIM_ZH[q.dimension]||q.dimension}：${qvalue(q)}`}function czh(c){return c.type==='PRODUCT'?`${c.label}产品`:c.label}
function filtered(){const q=document.getElementById('search').value.trim().toUpperCase();return q?catalog.filter(x=>x.search.includes(q)):catalog}
function renderNav(){const rows=filtered(),tree={};rows.forEach(x=>x.paths.forEach(p=>{const root=p[0]||'其他概念',branch=p[1]||'';tree[root]??={};(tree[root][branch]??=[]).push(x)}));const searching=document.getElementById('search').value.trim().length>0;document.getElementById('nav').innerHTML=Object.entries(tree).sort().map(([root,branches],rootIndex)=>{const total=[...new Set(Object.values(branches).flat().map(x=>x.id))].length;const body=Object.entries(branches).sort().map(([branch,v])=>{const branchKey=`${root}\u0000${branch}`,expanded=searching||expandedBranches.has(branchKey),visible=expanded?v:v.slice(0,NAV_LIMIT),more=v.length-visible.length,list=`<div class="concept-list">${visible.map(x=>`<button class="concept ${x.id===currentConcept?'selected':''}" data-id="${x.id}">${esc(x.label)}<span class="count">${x.fieldCount}处</span></button>`).join('')}${more?`<button class="concept" data-expand-nav="${encodeURIComponent(branchKey)}">显示其余 ${more} 项</button>`:''}</div>`;return branch?`<details class="nav-branch" ${searching||v.some(x=>x.id===currentConcept)?'open':''}><summary>${esc(branch)} <span class="count">${v.length}</span></summary>${list}</details>`:list}).join('');return `<details class="nav-root" ${searching||rootIndex===0||Object.values(branches).flat().some(x=>x.id===currentConcept)?'open':''}><summary>${esc(root)} <span class="count">${total}</span></summary>${body}</details>`}).join('')||'<div class="empty">没有匹配概念</div>';document.querySelectorAll('.concept[data-id]').forEach(b=>b.onclick=()=>loadConcept(b.dataset.id));document.querySelectorAll('[data-expand-nav]').forEach(b=>b.onclick=()=>{expandedBranches.add(decodeURIComponent(b.dataset.expandNav));renderNav()})}
function loadConcept(id){currentConcept=id;currentExpr='';activeFacets={};matrixPage=0;physicalPages={};renderNav();const seq=++requestNo,old=document.getElementById('concept-shard');if(old)old.remove();if(window.FIELD_MAP_SHARDS&&window.FIELD_MAP_SHARDS[id])return showConcept(window.FIELD_MAP_SHARDS[id]);const s=document.createElement('script');s.id='concept-shard';s.src=`data/concepts/${id}.js`;s.onload=()=>{s.remove();if(seq===requestNo&&window.FIELD_MAP_SHARDS[id])showConcept(window.FIELD_MAP_SHARDS[id])};s.onerror=()=>{s.remove();if(seq===requestNo)document.getElementById('expressions').innerHTML='<div class="empty">概念分片加载失败</div>'};document.head.appendChild(s)}
function showConcept(shard){currentShard=shard;const c=byId[shard.concept.id],candidate=shard.concept.normalizationStatus==='NEEDS_REVIEW'?`<br><span class="status">候选归拢 · ${shard.concept.sourceLabels.length}个来源概念待复核</span>`:'';document.getElementById('concept-summary').innerHTML=`<strong>${esc(shard.concept.label)}</strong><br>${c.fieldCount}个字段实例 · ${c.tableCount}张表 · ${c.expressionCount}种属性表达${candidate}`;renderFacetPanel();renderExpressions()}
function matchesFacets(x,skipDimension=''){return Object.entries(activeFacets).every(([dimension,values])=>dimension===skipDimension||x.qualifiers.some(q=>q.dimension===dimension&&values.has(q.value)))}
function facetCount(d,v){return currentShard.expressions.filter(x=>matchesFacets(x,d)&&x.qualifiers.some(q=>q.dimension===d&&q.value===v)).length}
function renderFacetPanel(){const grouped={};currentShard.expressions.flatMap(x=>x.qualifiers).forEach(q=>{(grouped[q.dimension]??=new Set()).add(q.value)});const dims=Object.keys(grouped).sort((a,b)=>(DIM_ZH[a]||a).localeCompare(DIM_ZH[b]||b,'zh-CN'));document.getElementById('facet-filter').className='section facet-panel';document.getElementById('facet-filter').innerHTML=dims.length?`<button class="facet-option facet-reset ${Object.keys(activeFacets).length?'':'active'}" data-reset="1">全部表达 <span class="facet-count">${currentShard.expressions.length}</span></button>`+dims.map(d=>`<div class="facet-row"><div class="facet-label">${esc(DIM_ZH[d]||d)}</div><div class="facet-options">${[...grouped[d]].sort((a,b)=>qvalue({value:a}).localeCompare(qvalue({value:b}),'zh-CN')).map(v=>`<button class="facet-option ${(activeFacets[d]||new Set()).has(v)?'active':''}" data-dim="${esc(d)}" data-value="${esc(v)}">${esc(qvalue({value:v}))} <span class="facet-count">${facetCount(d,v)}</span></button>`).join('')}</div></div>`).join(''):'<span class="muted">当前概念没有已识别限定</span>';const reset=document.querySelector('[data-reset]');if(reset)reset.onclick=()=>{activeFacets={};matrixPage=0;renderFacetPanel();renderExpressions()};document.querySelectorAll('[data-dim]').forEach(b=>b.onclick=()=>{const d=b.dataset.dim,v=b.dataset.value,set=activeFacets[d]||new Set();set.has(v)?set.delete(v):set.add(v);if(set.size)activeFacets[d]=set;else delete activeFacets[d];matrixPage=0;renderFacetPanel();renderExpressions()})}
function renderExpressions(){const shard=currentShard,dims=[...new Set(shard.expressions.flatMap(x=>x.qualifiers.map(q=>q.dimension)))].sort((a,b)=>(DIM_ZH[a]||a).localeCompare(DIM_ZH[b]||b,'zh-CN')),rows=shard.expressions.filter(x=>matchesFacets(x)).sort((a,b)=>(a.label===shard.concept.label?-1:b.label===shard.concept.label?1:a.label.localeCompare(b.label,'zh-CN'))),pages=Math.max(1,Math.ceil(rows.length/PAGE));matrixPage=Math.min(matrixPage,pages-1);const visible=rows.slice(matrixPage*PAGE,(matrixPage+1)*PAGE);document.getElementById('expressions').innerHTML=rows.length?`<div class="matrix-wrap"><table class="expression-matrix"><thead><tr><th>属性表达</th>${dims.map(d=>`<th>${esc(DIM_ZH[d]||d)}</th>`).join('')}<th>实现</th><th>表</th></tr></thead><tbody>${visible.map(x=>`<tr class="expression-row ${x.id===currentExpr?'selected':''}" data-id="${x.id}"><td>${esc(x.label)}</td>${dims.map(d=>{const values=x.qualifiers.filter(q=>q.dimension===d).map(q=>qvalue(q));return `<td>${esc(values.join('、')||'—')}</td>`}).join('')}<td class="matrix-count">${x.fieldCount}</td><td class="matrix-count">${x.tableCount}</td></tr>`).join('')}</tbody></table></div>${pages>1?`<div class="pager"><button data-matrix-page="${Math.max(0,matrixPage-1)}" ${matrixPage===0?'disabled':''}>上一页</button><span>${matrixPage+1}/${pages} · 共${rows.length}种表达</span><button data-matrix-page="${Math.min(pages-1,matrixPage+1)}" ${matrixPage>=pages-1?'disabled':''}>下一页</button></div>`:''}`:'<div class="empty">没有真实出现的匹配表达</div>';document.querySelectorAll('.expression-row').forEach(r=>r.onclick=()=>showExpression(shard,r.dataset.id,0));document.querySelectorAll('[data-matrix-page]').forEach(b=>b.onclick=()=>{matrixPage=Number(b.dataset.matrixPage);renderExpressions()});if(!rows.length){currentExpr='';physicalPages={};document.getElementById('detail').innerHTML='<div class="empty">当前限定组合没有真实属性表达</div>'}else if(!rows.some(x=>x.id===currentExpr))showExpression(shard,visible[0].id)}
function showExpression(shard,id){if(currentExpr!==id)physicalPages={};currentExpr=id;document.querySelectorAll('.expression-row').forEach(x=>x.classList.toggle('selected',x.dataset.id===id));const x=shard.expressions.find(e=>e.id===id);if(!x)return;const qPath=x.qualifiers.map(q=>qvalue(q)),breadcrumb=[shard.concept.label,...qPath].join(' › '),qualifiers=x.qualifiers.length?x.qualifiers.map(q=>`<span class="chip">${esc(qzh(q))}</span>`).join(''):'<span class="muted">无已识别限定</span>',contextualQualifiers=(x.contextualQualifiers||[]).length?x.contextualQualifiers.map(q=>`<span class="chip">${esc(qzh(q))}</span>`).join(''):'<span class="muted">无</span>',contexts=x.contexts.length?x.contexts.map(c=>`<span class="chip">${esc(czh(c))}</span>`).join(''):'<span class="muted">上下文未确认</span>',groups=x.physicalGroups.map(g=>physicalGroup(g,physicalPages[g.name]||0)).join(''),tables=new Set(x.physicalGroups.flatMap(g=>g.instances.map(i=>i.asset_id))).size,instances=x.physicalGroups.reduce((n,g)=>n+g.instances.length,0),related=shard.relatedConcepts.length?shard.relatedConcepts.map(r=>`<button class="chip" data-related="${r.id}">${esc(r.label)}</button>`).join(''):'<span class="muted">暂无</span>',relatedPreview=shard.relatedConcepts.slice(0,3).map(r=>r.label).join('、'),wiki=x.wikiEvidence.length?x.wikiEvidence.map(w=>`<li>${esc(w.title)}<br><span class="muted">${esc(w.path.join(' › '))}</span></li>`).join(''):'<span class="muted">无匹配目录；不影响字段语义</span>',conflicts=x.conflicts.length?`<div class="section"><h3>待人工确认的冲突</h3><pre>${esc(JSON.stringify(x.conflicts,null,2))}</pre></div>`:'';document.getElementById('detail').innerHTML=`<div class="detail-head"><h2>${esc(x.label)}</h2><div class="breadcrumb">${esc(breadcrumb)}</div><span class="status ${x.status==='CONFLICT'?'conflict':''}">${statusLabel(x.status)}</span> <span class="metrics">${x.physicalGroups.length}种物理字段名 · ${instances}处实现 · ${tables}张表</span></div><div class="semantic-card"><div class="semantic-row"><div class="semantic-key">核心限定</div><div class="chips">${qualifiers}</div></div><div class="semantic-row"><div class="semantic-key">上下文提示</div><div class="chips">${contextualQualifiers}</div></div><div class="semantic-row"><div class="semantic-key">业务上下文</div><div class="chips">${contexts}</div></div></div><div class="section"><h3>物理字段</h3>${groups||'<span class="muted">无物理实现</span>'}</div><details class="section folded-info"><summary>相关概念 · ${shard.relatedConcepts.length}<span class="related-preview">${esc(relatedPreview)}</span></summary><div class="chips">${related}</div></details><details class="section folded-info"><summary>Wiki 目录辅助证据 · ${x.wikiEvidence.length}</summary><ul>${wiki}</ul></details>${conflicts}`;document.querySelectorAll('[data-group-page]').forEach(b=>b.onclick=()=>{physicalPages[decodeURIComponent(b.dataset.group)]=Number(b.dataset.groupPage);showExpression(shard,id)});document.querySelectorAll('[data-related]').forEach(b=>b.onclick=()=>loadConcept(b.dataset.related))}
function physicalGroup(g,page){const start=page*PAGE,rows=g.instances.slice(start,start+PAGE),pages=Math.ceil(g.instances.length/PAGE),tables=new Set(g.instances.map(x=>x.asset_id)).size,key=encodeURIComponent(g.name);return `<div class="physical"><details open><summary><span class="technical-name">${esc(g.name)}</span> · ${g.instances.length}处实现 · ${tables}张表</summary><table><thead><tr><th>Schema</th><th>表名</th><th>表注释</th><th>字段注释</th><th>入口</th></tr></thead><tbody>${rows.map(r=>{const fieldComment=r.column_comment||r.semantic_comment,marker=!r.column_comment&&r.semantic_comment?' <span class="muted">（同名字段共识）</span>':'';return `<tr><td class="technical-name">${esc(r.schema_name)}</td><td class="technical-name">${esc(r.object_name)}</td><td>${esc(r.objectComment||'—')}</td><td>${esc(fieldComment||'—')}${marker}</td><td>${r.objectUrl?`<a href="${esc(r.objectUrl)}">表详情</a>`:'目标缺失'}</td></tr>`}).join('')}</tbody></table>${pages>1?`<div class="pager"><button data-group="${key}" data-group-page="${Math.max(0,page-1)}" ${page===0?'disabled':''}>上一页</button><span>${page+1}/${pages}</span><button data-group="${key}" data-group-page="${Math.min(pages-1,page+1)}" ${page>=pages-1?'disabled':''}>下一页</button></div>`:''}</details></div>`}
document.getElementById('search').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(renderNav,180)});renderNav();const nominal=catalog.find(x=>x.label==='名义本金');if(nominal)loadConcept(nominal.id);
</script></body></html>"""
