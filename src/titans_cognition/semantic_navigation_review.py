"""Reader-facing lifecycle semantic-navigation projection.

This projection consumes an existing context-semantic result bundle. It does
not infer new canonical semantics and never modifies the source bundle.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any

from .semantic_navigation import (
    load_navigation_config,
    map_observed_concepts_to_business_areas,
)


REQUIRED_SOURCE_FILES = (
    "business_concepts.jsonl",
    "attribute_expressions.jsonl",
    "business_contexts.jsonl",
    "assertions.jsonl",
    "evidence_refs.jsonl",
    "semantic_hypotheses.jsonl",
    "diagnostics/data_semantic_candidates.jsonl",
    "diagnostics/semantic_review_queue.jsonl",
    "manifest.json",
)

EVENT_TERMS = (
    "询价",
    "报价",
    "成交",
    "生效",
    "重置",
    "平仓",
    "终止",
    "清算",
    "结算",
    "交割",
    "支付",
    "inquiry",
    "quote",
    "trade",
    "reset",
    "terminate",
    "settlement",
    "delivery",
)

QUALIFIER_LABELS = {
    "attribute_kind": "属性种类",
    "temporal_stage": "时点",
    "lifecycle_stage": "生命周期",
    "adjustment_state": "调整状态",
    "variability": "变化方式",
    "position_side": "持仓方向",
    "flow_side": "数据侧",
    "currency_basis": "币种",
    "measure_basis": "口径",
    "aggregation_state": "累计口径",
    "availability_state": "可用状态",
    "cashflow_direction": "收付方向",
    "estimation_status": "估算状态",
    "party_role": "主体角色",
    "trade_side": "交易方向",
}

VALUE_LABELS = {
    "IDENTIFIER": "标识",
    "INITIAL": "初始",
    "CURRENT": "当前",
    "AFTER_ADJUSTMENT": "调整后",
    "BEFORE_ADJUSTMENT": "调整前",
    "DYNAMIC": "动态",
    "FIXED": "固定",
    "LONG": "多头",
    "SHORT": "空头",
    "LOCAL_CURRENCY": "本币",
    "ORIGINAL_CURRENCY": "原币",
    "SETTLEMENT_CURRENCY": "结算币种",
    "UNDERLYING_CURRENCY": "标的币种",
    "ABSOLUTE": "绝对",
    "AVAILABLE": "可用",
    "ACCUMULATED": "累计",
    "TARGET": "目标",
    "SOURCE": "源侧",
    "FROZEN": "冻结",
    "PAY": "支付",
    "RECEIVE": "收取",
    "ESTIMATED": "预估",
    "CLIENT": "客户",
    "INTERNAL": "内部",
    "BUY": "买方",
    "SELL": "卖方",
    "CLEARING": "清算",
    "EXECUTION": "成交",
    "ORDER": "订单",
    "POSITION": "持仓",
    "TERMINATION": "终止",
    "END": "期末",
}


def build_semantic_navigation_review(
    source_root: str | Path,
    config_path: str | Path,
    output_root: str | Path,
) -> dict[str, Path]:
    """Build a deterministic, sharded review page from a source result bundle."""

    source = Path(source_root).resolve()
    output = Path(output_root).resolve()
    config_file = Path(config_path).resolve()
    _validate_source(source)
    config = load_navigation_config(config_file)

    concepts = _read_jsonl(source / "business_concepts.jsonl")
    expressions = _read_jsonl(source / "attribute_expressions.jsonl")
    contexts = {
        str(row["business_context_id"]): row
        for row in _read_jsonl(source / "business_contexts.jsonl")
    }
    data_candidates = _read_jsonl(
        source / "diagnostics/data_semantic_candidates.jsonl"
    )
    review_queue = _read_jsonl(
        source / "diagnostics/semantic_review_queue.jsonl"
    )
    hypotheses = _read_jsonl(source / "semantic_hypotheses.jsonl")
    assertions = _read_jsonl(source / "assertions.jsonl")
    evidence_by_id = {
        str(row["evidence_id"]): row
        for row in _read_jsonl(source / "evidence_refs.jsonl")
    }
    assertions_by_subject: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in assertions:
        assertions_by_subject[str(row["subject_id"])].append(row)

    expressions_by_concept: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in expressions:
        expressions_by_concept[str(row["business_concept_id"])].append(row)
    data_by_expression = {
        str(row["attribute_expression_id"]): row for row in data_candidates
    }

    concepts_by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in concepts:
        concepts_by_label[str(row["label"])].append(row)
    observed = [
        {
            "business_concept_id": row["id"],
            "label": row["label"],
            "source_concept_ids": row["source_labels"],
        }
        for row in config["reader_concepts"]
    ]
    area_candidates = {
        str(row["concept_id"]): row
        for row in map_observed_concepts_to_business_areas(config, observed)
    }
    area_labels = {row["id"]: row["label"] for row in config["business_areas"]}

    review_root = output / "semantic-navigation-review"
    data_root = review_root / "data"
    shard_root = data_root / "concepts"
    shard_root.mkdir(parents=True, exist_ok=True)
    for stale in shard_root.iterdir():
        if stale.is_file():
            stale.unlink()

    catalog: list[dict[str, Any]] = []
    stage_members: dict[str, dict[str, list[str]]] = {
        stage["id"]: {
            "CORE_OBJECT": [],
            "BUSINESS_EVENT": [],
            "CROSS_STAGE": [],
        }
        for stage in config["lifecycle_stages"]
    }

    mapped_source_ids: set[str] = set()
    for reader in config["reader_concepts"]:
        concept_id = str(reader["id"])
        source_concepts = [
            row
            for label in reader["source_labels"]
            for row in concepts_by_label.get(str(label), [])
        ]
        source_ids = {str(row["business_concept_id"]) for row in source_concepts}
        mapped_source_ids.update(source_ids)
        excluded = {str(label) for label in reader.get("excluded_expression_labels", [])}
        concept_expressions = [
            row
            for source_id in source_ids
            for row in expressions_by_concept.get(source_id, [])
            if str(row.get("label")) not in excluded
        ]
        if not concept_expressions:
            continue
        searchable = " ".join(
            [str(reader["label"])]
            + [str(row.get("label", "")) for row in concept_expressions]
            + [
                str(instance.get("column_name", ""))
                for expression in concept_expressions
                for instance in data_by_expression.get(
                    str(expression["attribute_expression_id"]), {}
                ).get("physical_instances", [])
            ]
        )
        area = area_candidates.get(concept_id, {})
        area_ids = list(area.get("candidate_area_ids", []))
        stage_ids = [str(entry["stage_id"]) for entry in reader["lifecycle_entries"]]
        lifecycle_entries = [dict(entry) for entry in reader["lifecycle_entries"]]
        field_count = sum(int(row.get("field_count", 0)) for row in concept_expressions)
        table_ids = {
            str(instance.get("asset_id", ""))
            for expression in concept_expressions
            for instance in data_by_expression.get(
                str(expression["attribute_expression_id"]), {}
            ).get("physical_instances", [])
        }
        catalog_row = {
            "id": concept_id,
            "shard": _safe_shard_name(concept_id),
            "label": reader["label"],
            "status": "CANDIDATE",
            "supportStatus": (
                "SUPPORTED"
                if any(row.get("support_status") == "SUPPORTED" for row in source_concepts)
                else "PROVISIONAL"
            ),
            "stageIds": stage_ids,
            "lifecycleEntries": lifecycle_entries,
            "areaIds": area_ids,
            "areaLabels": [area_labels[item] for item in area_ids if item in area_labels],
            "areaStatus": area.get("status", "UNKNOWN"),
            "navigationRole": lifecycle_entries[0]["role"],
            "expressionCount": len(concept_expressions),
            "fieldCount": field_count,
            "tableCount": len(table_ids),
            "search": searchable.upper(),
        }
        catalog.append(catalog_row)
        for entry in lifecycle_entries:
            stage_members[str(entry["stage_id"])][str(entry["role"])].append(concept_id)

        shard = _build_concept_shard(
            {
                "business_concept_id": concept_id,
                "label": reader["label"],
                "source_labels": [row["label"] for row in source_concepts],
                "source_concept_ids": sorted(source_ids),
            },
            concept_expressions,
            data_by_expression,
            contexts,
            catalog_row,
            assertions_by_subject,
            evidence_by_id,
        )
        (shard_root / catalog_row["shard"]).write_text(
            "window.SEMANTIC_NAV_SHARDS=window.SEMANTIC_NAV_SHARDS||{};"
            f"window.SEMANTIC_NAV_SHARDS[{json.dumps(concept_id)}]="
            + json.dumps(shard, ensure_ascii=False, separators=(",", ":"))
            + ";\n",
            encoding="utf-8",
        )

    catalog.sort(key=lambda row: (-row["fieldCount"], str(row["label"])))
    by_id = {row["id"]: row for row in catalog}
    for groups in stage_members.values():
        for role, member_ids in groups.items():
            groups[role] = sorted(
                set(member_ids),
                key=lambda item: (-by_id[item]["fieldCount"], str(by_id[item]["label"])),
            )

    queue_items: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in review_queue:
        reason = str(row.get("reason") or row.get("review_type") or "UNKNOWN")
        variant_refs = [
            str(source_ref)
            for variant in row.get("comment_variants", [])
            for source_ref in variant.get("source_refs", [])
        ]
        queue_items[reason].append(
            {
                "label": (
                    row.get("source_label")
                    or row.get("candidate_family_label")
                    or row.get("physical_name")
                ),
                "methodId": row.get("method_id"),
                "status": row.get("status"),
                "sourceRef": row.get("source_concept_id") or (variant_refs[0] if variant_refs else None),
                "sourceRefs": variant_refs,
            }
        )
    for row in hypotheses:
        if row.get("status") == "CANDIDATE":
            continue
        reason = str(row.get("status", "UNKNOWN"))
        queue_items[reason].append(
            {
                "label": row.get("label"),
                "methodId": row.get("method_id"),
                "status": row.get("status"),
                "sourceRef": row.get("hypothesis_id"),
            }
        )
    queue_counts = Counter({reason: len(rows) for reason, rows in queue_items.items()})
    queue_counts["NAVIGATION_CANDIDATE_NOT_PUBLISHED"] = len(concepts) - len(mapped_source_ids)
    queue_items["NAVIGATION_CANDIDATE_NOT_PUBLISHED"] = [
        {
            "label": row.get("label"),
            "methodId": "reader_concepts.configuration.v1",
            "status": "NOT_PUBLISHED",
            "sourceRef": row.get("business_concept_id"),
        }
        for row in concepts
        if str(row["business_concept_id"]) not in mapped_source_ids
    ]

    navigation = {
        "schemaVersion": "semantic-navigation-reader-v1",
        "sourceKind": "CURRENT_RUN_PROJECTION",
        "sourceRoot": source.name,
        "sourceManifestHash": _sha256(source / "manifest.json"),
        "configHash": _sha256(config_file),
        "stages": [
            {
                "id": stage["id"],
                "label": stage["label"],
                "groups": stage_members[stage["id"]],
            }
            for stage in config["lifecycle_stages"]
        ],
        "businessAreas": config["business_areas"],
        "attributeAxes": config["attribute_axes"],
        "governanceQueue": [
            {"reason": reason, "count": count, "items": queue_items[reason][:200]}
            for reason, count in sorted(queue_counts.items())
            if count
        ],
    }
    (data_root / "projection.js").write_text(
        "window.SEMANTIC_NAV_PROJECTION="
        + json.dumps(navigation, ensure_ascii=False, separators=(",", ":"))
        + ";\nwindow.SEMANTIC_NAV_CATALOG="
        + json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    (review_root / "index.html").write_text(_review_html(catalog), encoding="utf-8")

    output_files = [review_root / "index.html", data_root / "projection.js", *sorted(shard_root.glob("*.js"))]
    manifest = {
        "schema_version": "semantic-navigation-review-manifest-v1",
        "source_root": source.as_posix(),
        "config_path": config_file.as_posix(),
        "config_sha256": _sha256(config_file),
        "source_hashes": {
            name: _sha256(source / name) for name in REQUIRED_SOURCE_FILES
        },
        "stats": {
            "concept_count": len(catalog),
            "expression_count": sum(row["expressionCount"] for row in catalog),
            "source_concept_count": len(concepts),
            "stage_attached_count": len(catalog),
            "navigation_unattached_count": queue_counts["NAVIGATION_CANDIDATE_NOT_PUBLISHED"],
        },
        "outputs": [
            {
                "relative_path": path.relative_to(output).as_posix(),
                "content_sha256": _sha256(path),
            }
            for path in output_files
        ],
        "boundaries": [
            "CANDIDATE_PROJECTION_NOT_BUSINESS_ACCEPTANCE",
            "NO_CANONICAL_WRITE_BACK",
            "NO_BUSINESS_ROWS",
            "UNSUPPORTED_NAVIGATION_REMAINS_VISIBLE",
        ],
    }
    manifest_path = review_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "review_index": review_root / "index.html",
        "manifest": manifest_path,
        "projection": data_root / "projection.js",
    }


def _build_concept_shard(
    concept: dict[str, Any],
    expressions: list[dict[str, Any]],
    data_by_expression: dict[str, dict[str, Any]],
    contexts: dict[str, dict[str, Any]],
    catalog_row: dict[str, Any],
    assertions_by_subject: dict[str, list[dict[str, Any]]],
    evidence_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    expression_rows = []
    for expression in sorted(
        expressions,
        key=lambda row: (len(row.get("qualifier_signature", [])), str(row["label"])),
    ):
        data = data_by_expression.get(str(expression["attribute_expression_id"]), {})
        qualifiers = [
            {
                "dimension": item.get("dimension", "UNKNOWN"),
                "dimensionLabel": QUALIFIER_LABELS.get(
                    str(item.get("dimension")), str(item.get("dimension", "待确认"))
                ),
                "value": item.get("value", "UNKNOWN"),
                "valueLabel": VALUE_LABELS.get(
                    str(item.get("value")), str(item.get("value", "待确认"))
                ),
            }
            for item in expression.get("qualifier_signature", [])
        ]
        physical = [
            {
                "schema": item.get("schema_name"),
                "table": item.get("object_name"),
                "column": item.get("column_name"),
                "comment": item.get("column_comment"),
                "columnId": item.get("column_id"),
            }
            for item in data.get("physical_instances", [])
        ]
        context_rows = [
            {
                "id": context_id,
                "label": contexts[context_id]["label"],
                "type": contexts[context_id]["context_type"],
                "status": contexts[context_id].get("status", "CANDIDATE"),
            }
            for context_id in data.get("context_ids", [])
            if context_id in contexts
        ]
        evidence_rows: dict[str, dict[str, Any]] = {}
        assertion_rows = []
        for assertion in assertions_by_subject.get(
            str(expression["attribute_expression_id"]), []
        ):
            refs = [
                *assertion.get("evidence_refs", []),
                *assertion.get("counterevidence_refs", []),
            ]
            for evidence_id in refs:
                evidence = evidence_by_id.get(str(evidence_id))
                if evidence:
                    evidence_rows[str(evidence_id)] = {
                        "id": evidence_id,
                        "type": evidence.get("evidence_type"),
                        "label": evidence.get("label"),
                        "sourceRef": evidence.get("source_ref"),
                        "role": (
                            "COUNTEREVIDENCE"
                            if evidence_id in assertion.get("counterevidence_refs", [])
                            else "SUPPORT"
                        ),
                    }
            assertion_rows.append(
                {
                    "id": assertion.get("assertion_id"),
                    "predicate": assertion.get("predicate"),
                    "objectId": assertion.get("object_id"),
                    "methodId": assertion.get("method_id"),
                    "status": assertion.get("status"),
                    "evidenceRefs": assertion.get("evidence_refs", []),
                    "counterevidenceRefs": assertion.get("counterevidence_refs", []),
                }
            )
        expression_rows.append(
            {
                "id": expression["attribute_expression_id"],
                "label": expression["label"],
                "status": expression.get("status", "CANDIDATE"),
                "supportStatus": expression.get("support_status", "PROVISIONAL"),
                "fieldCount": expression.get("field_count", 0),
                "tableCount": expression.get("object_count", 0),
                "qualifiers": qualifiers,
                "contexts": context_rows,
                "physical": physical,
                "conflicts": expression.get("conflicts", []),
                "uncertainties": expression.get("uncertainties", []),
                "sourceConceptIds": expression.get("source_concept_ids", []),
                "assertions": assertion_rows,
                "evidence": sorted(evidence_rows.values(), key=lambda row: str(row["id"])),
            }
        )
    return {
        "concept": {
            **catalog_row,
            "sourceLabels": concept.get("source_labels", []),
            "sourceConceptIds": concept.get("source_concept_ids", []),
            "definition": (
                f"当前字段名、中文注释和物理实现支持的“{concept['label']}”语义候选；"
                "正式业务定义仍需业务审阅。"
            ),
        },
        "expressions": expression_rows,
    }


def _matching_stages(text: str, stages: list[dict[str, Any]]) -> list[str]:
    normalized = text.casefold()
    return [
        str(stage["id"])
        for stage in stages
        if any(str(term).casefold() in normalized for term in stage["concept_terms"])
    ]


def _navigation_role(label: str, stage_ids: list[str]) -> str:
    normalized = label.casefold()
    if normalized in {term.casefold() for term in EVENT_TERMS}:
        return "BUSINESS_EVENT"
    if len(stage_ids) > 1:
        return "CROSS_STAGE"
    return "CORE_OBJECT"


def _stage_anchor_role(label: str, stage: dict[str, Any]) -> str | None:
    normalized = label.strip().casefold()
    for role, key in (
        ("BUSINESS_EVENT", "business_event_terms"),
        ("CORE_OBJECT", "core_object_terms"),
        ("CROSS_STAGE", "cross_stage_terms"),
    ):
        if normalized in {str(term).strip().casefold() for term in stage[key]}:
            return role
    return None


def _validate_source(source: Path) -> None:
    if not source.is_dir():
        raise ValueError(f"semantic source root does not exist: {source}")
    missing = [name for name in REQUIRED_SOURCE_FILES if not (source / name).is_file()]
    if missing:
        raise ValueError(f"semantic source is incomplete: {missing}")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_shard_name(concept_id: str) -> str:
    stem = "".join(
        character if character.isalnum() or character in {"-", "_"} else "-"
        for character in concept_id
    ).strip("-")
    if not stem:
        stem = hashlib.sha256(concept_id.encode("utf-8")).hexdigest()[:16]
    suffix = hashlib.sha256(concept_id.encode("utf-8")).hexdigest()[:10]
    return f"{stem}-{suffix}.js"


def _review_html(catalog: list[dict[str, Any]]) -> str:
    shard_scripts = "".join(
        f'<script src="data/concepts/{row["shard"]}"></script>' for row in catalog
    )
    return r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>字段语义地图 · 业务主线</title>
<style>
:root{--ink:#15243a;--muted:#65758b;--line:#dce4ee;--soft:#f5f8fc;--blue:#1769aa;--blue2:#e9f2fb;--warn:#a26113;--bad:#a63b3b}*{box-sizing:border-box}body{margin:0;color:var(--ink);font:14px/1.5 system-ui,"Microsoft YaHei",sans-serif;background:#fff}header{display:flex;gap:22px;align-items:center;padding:14px 20px;border-bottom:1px solid var(--line)}h1{font-size:22px;margin:0;white-space:nowrap}input{width:min(760px,70vw);padding:10px 14px;border:1px solid #aebfd2;border-radius:8px}.spine{padding:13px 20px;border-bottom:1px solid var(--line);background:var(--soft)}.spine h2{font-size:13px;margin:0 0 8px}.stages{display:flex;align-items:center;gap:0}.stage{border:0;background:transparent;color:var(--muted);padding:7px 14px;cursor:pointer;font-weight:600}.stage.active{background:var(--blue);color:#fff;border-radius:16px}.arrow{color:#91a0b2}.layout{display:grid;grid-template-columns:minmax(240px,25%) minmax(420px,37%) 1fr;height:calc(100vh - 177px);min-height:560px}.panel{overflow:auto;border-right:1px solid var(--line);padding:16px}.panel:last-child{border-right:0}.panel h2{font-size:15px;margin:0 0 12px}.muted{color:var(--muted)}.technical-name{text-transform:lowercase}.section{margin:16px 0}.group-title{font-size:12px;color:var(--muted);font-weight:700;margin:16px 0 6px}.item{display:block;width:100%;text-align:left;border:0;background:transparent;padding:7px 9px;border-radius:6px;cursor:pointer}.item:hover,.item.active{background:var(--blue2);color:#0f568f}.count{float:right;color:var(--muted);font-size:12px}.chips{display:flex;gap:6px;flex-wrap:wrap}.chip,.tag{border:1px solid #bfd0e2;border-radius:999px;background:#fff;padding:3px 8px;font-size:12px}.chip{cursor:pointer}.chip.active{background:var(--blue);color:#fff;border-color:var(--blue)}.facet-row{display:grid;grid-template-columns:76px 1fr;gap:8px;padding:4px 0}.facet-row+.facet-row{border-top:1px dashed #e3eaf2}.facet-label{color:var(--muted);padding-top:3px}.matrix-wrap{overflow:auto;margin-top:10px;border:1px solid var(--line);border-radius:8px}.expression-matrix{width:100%;border-collapse:collapse;min-width:620px}.expression-matrix th,.expression-matrix td{border-bottom:1px solid var(--line);padding:7px;text-align:left;white-space:nowrap}.expression-matrix th{background:var(--soft)}.expression-matrix tbody tr{cursor:pointer}.expression-matrix tbody tr:hover,.expression-matrix tbody tr.active{background:var(--blue2)}.expression-matrix td:first-child{font-weight:600;color:#174f7b}.matrix-count{text-align:right!important}.detail h3{font-size:13px;margin:18px 0 7px}.physical{border-left:2px solid #cbd8e6;padding:4px 0 4px 10px;margin:6px 0}.field{font-family:ui-monospace,Consolas,monospace;color:#174f7b}.status{font-size:12px;padding:2px 7px;border-radius:10px;background:#edf4eb;color:#3e6f3b}.status.provisional{background:#fff4df;color:var(--warn)}.queue{position:fixed;left:0;right:0;bottom:0;border-top:1px solid var(--line);background:#fff;padding:10px 20px;white-space:nowrap;overflow:auto}.queue strong{margin-right:12px}.queue span{margin-right:15px;color:var(--warn)}.empty{color:var(--muted);padding:30px 8px}.boundary{font-size:12px;color:var(--muted);margin-top:4px}@media(max-width:900px){.layout{grid-template-columns:1fr;height:auto}.panel{border-right:0;border-bottom:1px solid var(--line);min-height:320px}.queue{position:static}.stages{overflow:auto}}
</style></head><body><header><h1>字段语义地图</h1><input id="search" placeholder="搜索业务概念、中文注释、字段名、表名"></header>
<section class="spine"><h2>OTC 业务主线</h2><div id="stages" class="stages"></div><div class="boundary">生命周期主线与业务区域正交；页面内容是当前运行候选，不是正式业务本体。</div></section>
<main class="layout"><section class="panel"><h2>① 业务地图</h2><div id="map"></div></section><section class="panel"><h2>② 语义索引</h2><div id="index" class="empty">请选择业务概念</div></section><section class="panel"><h2>③ 语义详情</h2><div id="detail" class="empty">请选择属性表达</div></section></main><footer id="queue" class="queue"></footer>
<script src="data/projection.js"></script>''' + shard_scripts + r'''<script>
const P=window.SEMANTIC_NAV_PROJECTION,C=window.SEMANTIC_NAV_CATALOG,S=window.SEMANTIC_NAV_SHARDS||{};let stage=P.stages.find(x=>x.id==='contract-lifecycle')?.id||P.stages[0].id,concept=null,expr=null,filters=new Map();const $=id=>document.getElementById(id),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function stageRow(){const a=P.stages.map((x,i)=>`${i?'<span class="arrow">──</span>':''}<button class="stage ${x.id===stage?'active':''}" data-stage="${x.id}">${esc(x.label)}</button>`).join('');$('stages').innerHTML=a;$('stages').querySelectorAll('[data-stage]').forEach(b=>b.onclick=()=>{stage=b.dataset.stage;renderStages();renderMap()})}function renderStages(){stageRow()}
function rowsForStage(){const q=$('search').value.trim().toUpperCase();return C.filter(x=>(!q||x.search.includes(q))&&(q||x.stageIds.includes(stage)))}
function renderMap(){const rows=rowsForStage(),byId=Object.fromEntries(rows.map(x=>[x.id,x])),st=P.stages.find(x=>x.id===stage),names={CORE_OBJECT:'核心对象',BUSINESS_EVENT:'业务事件',CROSS_STAGE:'跨环节关联'};let html=`<h3>${esc(st.label)}</h3>`;for(const [key,label] of Object.entries(names)){let ids=$('search').value.trim()?rows.filter(x=>x.navigationRole===key).map(x=>x.id):st.groups[key].filter(id=>byId[id]);html+=`<div class="group-title">${label}</div>`+(ids.slice(0,80).map(id=>{const x=byId[id]||C.find(y=>y.id===id);return `<button class="item ${concept===id?'active':''}" data-concept="${id}">${esc(x.label)}<span class="count">${x.fieldCount}处</span></button>`}).join('')||'<div class="muted">当前无物理证据</div>')}if(!rows.length)html+='<div class="empty">没有匹配概念</div>';$('map').innerHTML=html;$('map').querySelectorAll('[data-concept]').forEach(b=>b.onclick=()=>loadConcept(b.dataset.concept))}
function loadConcept(id){concept=id;expr=null;filters.clear();renderMap();const data=S[id];if(data)return showConcept(data);$('index').innerHTML='<div class="empty">概念明细加载失败，请重新生成页面。</div>';$('detail').innerHTML='<div class="empty">没有可展示的属性表达</div>'}
function showConcept(d){const c=d.concept,grouped={};d.expressions.flatMap(e=>e.qualifiers).forEach(q=>(grouped[q.dimension]??=new Map()).set(q.value,q));const stageName=id=>P.stages.find(x=>x.id===id)?.label||id;const roleName={CORE_OBJECT:'核心对象',BUSINESS_EVENT:'业务事件',CROSS_STAGE:'跨环节关联'};$('index').innerHTML=`<h3>当前概念：${esc(c.label)}</h3><div class="muted">${c.fieldCount}个字段实例 · ${c.tableCount}张表 · ${c.expressionCount}种属性表达</div><div class="muted">候选定义</div><p>${esc(c.definition)}</p><div class="chips"><span class="tag">${esc(c.areaLabels.join(' / ')||'导航待挂接')}</span><span class="tag">${esc(c.supportStatus)}</span></div><div class="boundary">来源概念：${esc(c.sourceLabels.join('、'))}</div><div class="group-title">生命周期入口</div>${c.lifecycleEntries.map(x=>`<div class="physical"><div><span class="tag">CONFIGURATION_SEED｜非证据</span> ${esc(stageName(x.stage_id))} · ${esc(roleName[x.role]||x.role)}</div><div class="boundary">${esc(x.seed_reason)}；尚无独立 Evidence ID 证明该阶段挂接。</div></div>`).join('')}<div class="section"><div class="group-title">属性表达筛选</div><div id="filters"><button class="chip ${filters.size?'':'active'}" data-reset="1">全部表达 ${d.expressions.length}</button>${Object.entries(grouped).map(([dim,values])=>`<div class="facet-row"><div class="facet-label">${esc([...values.values()][0].dimensionLabel)}</div><div class="chips">${[...values.values()].map(q=>`<button class="chip ${filters.get(dim)?.has(q.value)?'active':''}" data-dim="${esc(dim)}" data-value="${esc(q.value)}">${esc(q.valueLabel)}</button>`).join('')}</div></div>`).join('')}</div></div><div class="group-title">属性表达矩阵</div><div id="expressions"></div>`;$('filters').querySelector('[data-reset]').onclick=()=>{filters.clear();showConcept(d)};$('filters').querySelectorAll('[data-dim]').forEach(b=>b.onclick=()=>{const set=filters.get(b.dataset.dim)||new Set();set.has(b.dataset.value)?set.delete(b.dataset.value):set.add(b.dataset.value);set.size?filters.set(b.dataset.dim,set):filters.delete(b.dataset.dim);showConcept(d)});renderExpressions(d)}
function renderExpressions(d){const dims=[...new Set(d.expressions.flatMap(e=>e.qualifiers.map(q=>q.dimension)))];const rows=d.expressions.filter(e=>[...filters].every(([dim,values])=>e.qualifiers.some(q=>q.dimension===dim&&values.has(q.value)))).sort((a,b)=>(a.label===d.concept.label?-1:b.label===d.concept.label?1:a.label.localeCompare(b.label,'zh-CN')));$('expressions').innerHTML=rows.length?`<div class="matrix-wrap"><table class="expression-matrix"><thead><tr><th>属性表达</th>${dims.map(dim=>`<th>${esc(d.expressions.flatMap(e=>e.qualifiers).find(q=>q.dimension===dim)?.dimensionLabel||dim)}</th>`).join('')}<th>实现</th><th>表</th></tr></thead><tbody>${rows.map(e=>`<tr class="${expr===e.id?'active':''}" data-expr="${e.id}"><td>${esc(e.label)}</td>${dims.map(dim=>`<td>${esc(e.qualifiers.filter(q=>q.dimension===dim).map(q=>q.valueLabel).join('、')||'—')}</td>`).join('')}<td class="matrix-count">${e.fieldCount}</td><td class="matrix-count">${e.tableCount}</td></tr>`).join('')}</tbody></table></div>`:'<div class="empty">没有匹配表达</div>';$('expressions').querySelectorAll('[data-expr]').forEach(b=>b.onclick=()=>{expr=b.dataset.expr;renderExpressions(d);showExpression(d.expressions.find(x=>x.id===expr),d.concept)});if(rows.length&&!rows.some(e=>e.id===expr)){expr=rows[0].id;renderExpressions(d);showExpression(rows[0],d.concept)}}
function showExpression(e,c){const status=e.supportStatus==='SUPPORTED'?'status':'status provisional';$('detail').innerHTML=`<div class="detail"><h3>当前表达：${esc(e.label)}</h3><p>基础概念：<strong>${esc(c.label)}</strong></p><p>证据状态：<span class="${status}">${esc(e.supportStatus)}</span></p><h3>限定条件</h3>${e.qualifiers.length?e.qualifiers.map(q=>`<div>├─ ${esc(q.dimensionLabel)}：${esc(q.valueLabel)}</div>`).join(''):'<div class="muted">未识别明确限定</div>'}<h3>业务上下文</h3>${e.contexts.length?e.contexts.map(x=>`<div>├─ ${esc(x.label)} <span class="muted">${esc(x.type)}</span></div>`).join(''):'<div class="muted">当前无独立上下文证据</div>'}<h3>物理实现</h3>${e.physical.slice(0,120).map(x=>`<div class="physical"><div><span class="technical-name">${esc(x.schema)}</span> · <span class="technical-name">${esc(x.table)}</span></div><div class="field technical-name">└─ ${esc(x.column)}</div><div>${esc(x.comment||'无中文注释')}</div><div class="boundary">${esc(x.columnId)}</div></div>`).join('')||'<div class="muted">没有物理字段</div>'}<h3>逐项证据</h3>${e.evidence.length?e.evidence.slice(0,120).map(x=>`<div class="physical"><div>${esc(x.role)} · ${esc(x.type)} · ${esc(x.label)}</div><div class="boundary">${esc(x.id)} · ${esc(x.sourceRef)}</div></div>`).join(''):'<div class="muted">当前表达没有独立 Evidence 引用</div>'}<details><summary>断言与方法（${e.assertions.length}）</summary>${e.assertions.map(x=>`<div class="physical"><div>${esc(x.predicate)} · ${esc(x.status)}</div><div class="boundary">${esc(x.id)} · ${esc(x.methodId)} · ${esc(x.objectId)}</div></div>`).join('')}</details><h3>证据边界</h3>${e.conflicts.length?'<div>△ 存在证据冲突</div>':''}<div>△ 正式业务定义待确认</div></div>`}
function renderQueue(){const names={NAVIGATION_CANDIDATE_NOT_PUBLISHED:'导航候选未发布',UNKNOWN_BUSINESS_CONCEPT:'基础概念待确认',RECURRENT_CORE_WITH_UNTYPED_MODIFIER:'属性表达待确认',INSUFFICIENT_EVIDENCE:'证据不足',CONFLICT:'证据冲突'};$('queue').innerHTML='<strong>语义治理队列</strong>'+P.governanceQueue.map((x,i)=>`<button class="chip" data-queue="${i}">${esc(names[x.reason]||x.reason)} ${x.count}</button>`).join('')+`<span class="muted">来源 ${esc(P.sourceRoot)} · ${esc(P.sourceManifestHash.slice(0,12))}</span>`;$('queue').querySelectorAll('[data-queue]').forEach(b=>b.onclick=()=>showQueue(P.governanceQueue[Number(b.dataset.queue)]))}
function showQueue(q){$('detail').innerHTML=`<h3>治理队列：${esc(q.reason)}</h3><p class="muted">展示前 ${q.items.length} 条；完整计数 ${q.count}。</p>${q.items.map(x=>`<div class="physical"><div>${esc(x.label||'未命名候选')} · ${esc(x.status)}</div><div class="boundary">${esc(x.methodId||'无方法标识')} · ${esc((x.sourceRefs&&x.sourceRefs.length?x.sourceRefs.join('；'):x.sourceRef)||'无来源引用')}</div></div>`).join('')}`}
$('search').addEventListener('input',renderMap);renderStages();renderMap();renderQueue();const preferred=C.find(x=>x.label==='名义本金')||C.find(x=>x.label.includes('名义本金'))||C.find(x=>x.stageIds.includes(stage));if(preferred)loadConcept(preferred.id);
</script></body></html>'''
