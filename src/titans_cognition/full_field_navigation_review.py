"""Build the Stage-3-style semantic-navigation page for every P1 field pack."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any

import yaml

from .semantic_navigation_review import (
    QUALIFIER_LABELS,
    VALUE_LABELS,
    _object_url,
    _review_html,
    _safe_shard_name,
)


def build_full_field_navigation_review(
    source_root: str | Path,
    config_path: str | Path,
    output_root: str | Path,
) -> dict[str, Path]:
    """Render six Reader candidates plus a complete non-Reader field corpus."""

    source = Path(source_root).resolve()
    config_file = Path(config_path).resolve()
    output = Path(output_root).resolve()
    packs_path = source / "field-evidence-packs.jsonl"
    source_manifest_path = source / "manifest.json"
    if not packs_path.is_file() or not source_manifest_path.is_file():
        raise ValueError(f"P1 evidence source is incomplete: {source}")
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")

    config = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    readers = _compile_readers(config)
    if len(readers) != 6 or {row["id"] for row in readers} != {
        "reader:counterparty",
        "reader:order",
        "reader:trade",
        "reader:notional",
        "reader:position",
        "reader:margin",
    }:
        raise ValueError("The full-field page requires the exact six Reader IDs")
    panorama_root = Path(config["panorama_root"]).resolve()
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    expected_count = int(source_manifest["counts"]["evidence_packs"])
    configured_count = int(config["expected_field_count"])
    if expected_count != configured_count:
        raise ValueError(
            f"Configured field count {configured_count} does not match "
            f"the source manifest count {expected_count}"
        )
    expected_hash = str(source_manifest["field_evidence_packs_sha256"])

    fields, actual_hash = _load_fields(packs_path, readers, panorama_root)
    field_ids = [row["id"] for row in fields]
    if actual_hash != expected_hash:
        raise ValueError(f"P1 pack hash mismatch: {actual_hash}")
    if len(fields) != expected_count or len(set(field_ids)) != expected_count:
        raise ValueError(
            f"Expected {expected_count} unique fields, got "
            f"{len(fields)}/{len(set(field_ids))}"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
    try:
        review_root = staging / "semantic-navigation-review"
        data_root = review_root / "data"
        shard_root = data_root / "concepts"
        shard_root.mkdir(parents=True)

        catalog, shards = _reader_catalog_and_shards(readers, fields)
        utility_catalog, utility_shard = _full_corpus_shard(
            fields, config["lifecycle_stages"]
        )
        catalog.append(utility_catalog)
        shards[utility_catalog["id"]] = utility_shard
        stage_rows = _stage_rows(config["lifecycle_stages"], catalog)
        governance_queue = _governance_queue(fields)
        projection = {
            "schemaVersion": "semantic-navigation-reader-v1",
            "sourceKind": "P1_FULL_FIELD_EVIDENCE_PROJECTION",
            "sourceRoot": source.name,
            "sourceManifestHash": _sha256(source_manifest_path),
            "sourcePackHash": actual_hash,
            "stages": stage_rows,
            "businessAreas": [],
            "attributeAxes": [],
            "governanceQueue": governance_queue,
            "corpus": {
                "fieldCount": len(fields),
                "uniqueFieldCount": len(set(field_ids)),
                "readerCount": len(readers),
                "utilityConceptId": utility_catalog["id"],
            },
        }
        (data_root / "projection.js").write_text(
            "window.SEMANTIC_NAV_PROJECTION="
            + json.dumps(projection, ensure_ascii=False, separators=(",", ":"))
            + ";\nwindow.SEMANTIC_NAV_CATALOG="
            + json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
            + ";\n",
            encoding="utf-8",
            newline="\n",
        )
        for catalog_row in catalog:
            concept_id = catalog_row["id"]
            (shard_root / catalog_row["shard"]).write_text(
                "window.SEMANTIC_NAV_SHARDS=window.SEMANTIC_NAV_SHARDS||{};"
                f"window.SEMANTIC_NAV_SHARDS[{json.dumps(concept_id)}]="
                + json.dumps(
                    shards[concept_id], ensure_ascii=False, separators=(",", ":")
                )
                + ";\n",
                encoding="utf-8",
                newline="\n",
            )
        written_corpus_count = _validate_written_full_corpus_shard(
            shard_root / utility_catalog["shard"], set(field_ids)
        )
        (review_root / "index.html").write_text(
            _review_html(catalog), encoding="utf-8", newline="\n"
        )

        reader_counts = {
            reader["id"]: sum(
                any(item["reader"] == reader["id"] for item in row["assignments"])
                for row in fields
            )
            for reader in readers
        }
        stats = {
            "reader_count": len(readers),
            "catalog_entry_count": len(catalog),
            "field_count": len(fields),
            "unique_field_count": len(set(field_ids)),
            "full_corpus_field_count": written_corpus_count,
            "prepared_field_count": sum(
                row["disposition"] == "PREPARED" for row in fields
            ),
            "excluded_field_count": sum(
                row["disposition"] == "EXCLUDED" for row in fields
            ),
            "unassigned_field_count": sum(not row["assignments"] for row in fields),
            "multi_reader_field_count": sum(
                len(row["assignments"]) > 1 for row in fields
            ),
            "conflict_field_count": sum(row["conflictCount"] > 0 for row in fields),
            "unresolved_field_count": sum(row["unresolvedCount"] > 0 for row in fields),
            "reader_field_counts": reader_counts,
            "reader_expression_count": sum(
                row["expressionCount"]
                for row in catalog
                if row["id"].startswith("reader:")
            ),
            "full_corpus_expression_count": utility_catalog["expressionCount"],
        }
        output_files = [
            review_root / "index.html",
            data_root / "projection.js",
            *sorted(shard_root.glob("*.js")),
        ]
        manifest = {
            "schema_version": "tradeflow-full-field-navigation-review-v1",
            "source_root": source.as_posix(),
            "source_manifest_sha256": _sha256(source_manifest_path),
            "source_pack_sha256": actual_hash,
            "config_path": config_file.as_posix(),
            "config_sha256": _sha256(config_file),
            "stats": stats,
            "outputs": [
                {
                    "relative_path": path.relative_to(staging).as_posix(),
                    "content_sha256": _sha256(path),
                }
                for path in output_files
            ],
            "boundaries": [
                f"ALL_{len(fields)}_FIELDS_VISIBLE_IN_FULL_CORPUS_ENTRY",
                "EXACTLY_SIX_READER_CANDIDATES",
                "ORDER_AND_TRADE_NOT_MERGED",
                "UNASSIGNED_EXCLUDED_CONFLICT_UNRESOLVED_REMAIN_VISIBLE",
                "CANDIDATE_PROJECTION_NOT_BUSINESS_ACCEPTANCE",
                "NO_CANONICAL_WRITE_BACK",
                "NO_BUSINESS_ROWS",
                "NO_MODEL_EGRESS",
            ],
        }
        manifest_path = review_root / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        staging.replace(output)
        final_root = output / "semantic-navigation-review"
        return {
            "review_index": final_root / "index.html",
            "manifest": final_root / "manifest.json",
            "projection": final_root / "data" / "projection.js",
        }
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _compile_readers(config: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for row in config["reader_concepts"]:
        result.append(
            {
                **row,
                "direct_regex": [
                    re.compile(str(pattern), re.I) for pattern in row["direct_patterns"]
                ],
                "context_regex": [
                    re.compile(str(pattern), re.I)
                    for pattern in row["context_patterns"]
                ],
            }
        )
    return result


def _load_fields(
    path: Path, readers: list[dict[str, Any]], panorama_root: Path
) -> tuple[list[dict[str, Any]], str]:
    fields = []
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for raw_line in handle:
            digest.update(raw_line)
            fields.append(
                _field_record(
                    json.loads(raw_line.decode("utf-8")), readers, panorama_root
                )
            )
    return fields, digest.hexdigest()


def _field_record(
    pack: dict[str, Any], readers: list[dict[str, Any]], panorama_root: Path
) -> dict[str, Any]:
    identity = pack["physical_identity"]
    raw = pack["raw_physical_fact"]
    column_id = str(identity["physical_column_id"])
    field_name = column_id.rsplit(":", 1)[-1]
    asset_id = column_id.rsplit(":COLUMN:", 1)[0]
    field_text = f"{field_name} {raw.get('column_comment_raw') or ''}"
    object_text = (
        f"{identity.get('object_name') or ''} {raw.get('object_comment_raw') or ''}"
    )
    direct = [
        reader["id"]
        for reader in readers
        if any(pattern.search(field_text) for pattern in reader["direct_regex"])
    ]
    specific_direct = {
        "reader:counterparty",
        "reader:notional",
        "reader:position",
        "reader:margin",
    }.intersection(direct)
    strong_trade_field = bool(
        re.search(r"(?:^|_)TRD(?:_|$)|TRADE|DEAL|成交", field_text, re.I)
    )
    if "reader:trade" in direct and specific_direct and not strong_trade_field:
        direct.remove("reader:trade")
    if direct:
        candidate_assignments = [
            {"reader": reader_id, "mode": "DIRECT_FIELD_LEXICAL"}
            for reader_id in direct
        ]
    else:
        context = [
            reader["id"]
            for reader in readers
            if any(pattern.search(object_text) for pattern in reader["context_regex"])
        ]
        if "reader:order" in context and "reader:trade" in context:
            context.remove("reader:trade")
        specific = {
            "reader:counterparty",
            "reader:notional",
            "reader:position",
            "reader:margin",
        }
        if specific.intersection(context):
            context = [
                reader_id for reader_id in context if reader_id != "reader:trade"
            ]
        candidate_assignments = [
            {"reader": reader_id, "mode": "OBJECT_CONTEXT"} for reader_id in context
        ]

    disposition = pack["preparation_disposition"]["status"]
    assignments = candidate_assignments if disposition == "PREPARED" else []
    suppressed_assignments = candidate_assignments if disposition != "PREPARED" else []

    qualifiers = [
        {
            "dimension": row.get("dimension", "UNKNOWN"),
            "value": row.get("value", "UNKNOWN"),
        }
        for row in pack.get("candidate_qualifier_observations", [])
    ]
    conflict_types = sorted(
        {
            str(row.get("conflict_type"))
            for row in pack.get("conflicts", [])
            if row.get("conflict_type")
        }
    )
    unresolved_codes = sorted(
        {
            str(row.get("code"))
            for row in pack.get("unresolved_items", [])
            if row.get("code")
        }
    )
    return {
        "id": column_id,
        "assetId": asset_id,
        "schema": identity["schema_name"],
        "object": identity["object_name"],
        "objectComment": raw.get("object_comment_raw") or "",
        "field": field_name,
        "fieldComment": raw.get("column_comment_raw") or "",
        "dataType": raw.get("data_type_raw") or "",
        "nullable": raw.get("nullable"),
        "ordinal": raw.get("ordinal_position"),
        "disposition": disposition,
        "dispositionReason": pack["preparation_disposition"].get("reason_code"),
        "assignments": assignments,
        "suppressedAssignments": suppressed_assignments,
        "qualifiers": qualifiers,
        "conflictCount": len(pack.get("conflicts", [])),
        "conflictTypes": conflict_types,
        "unresolvedCount": len(pack.get("unresolved_items", [])),
        "unresolvedCodes": unresolved_codes,
        "objectUrl": _object_url(panorama_root, asset_id),
    }


def _reader_catalog_and_shards(
    readers: list[dict[str, Any]], fields: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    catalog = []
    shards = {}
    for reader in readers:
        reader_fields = [
            row
            for row in fields
            if any(item["reader"] == reader["id"] for item in row["assignments"])
        ]
        expressions = _expressions_by_field_name(reader_fields, reader["id"])
        table_count = len({row["assetId"] for row in reader_fields})
        catalog_row = {
            "id": reader["id"],
            "shard": _safe_shard_name(reader["id"]),
            "label": reader["label"],
            "status": "CANDIDATE",
            "supportStatus": "PROVISIONAL",
            "stageIds": reader["stages"],
            "lifecycleEntries": [
                {
                    "stage_id": stage_id,
                    "role": "CORE_OBJECT"
                    if len(reader["stages"]) == 1
                    else "CROSS_STAGE",
                    "seed_reason": "六 Reader 固定导航入口；字段归属由 P1 元数据候选投影产生",
                }
                for stage_id in reader["stages"]
            ],
            "areaIds": [],
            "areaLabels": reader["area_labels"],
            "areaStatus": "CANDIDATE",
            "navigationRole": (
                "CORE_OBJECT" if len(reader["stages"]) == 1 else "CROSS_STAGE"
            ),
            "expressionCount": len(expressions),
            "fieldCount": len(reader_fields),
            "tableCount": table_count,
            "search": " ".join(
                [reader["label"]]
                + [row["field"] for row in reader_fields]
                + [row["fieldComment"] for row in reader_fields]
                + [row["object"] for row in reader_fields]
            ).upper(),
        }
        catalog.append(catalog_row)
        shards[reader["id"]] = {
            "concept": {
                **catalog_row,
                "sourceLabels": ["P1 字段名", "P1 字段注释", "P1 对象上下文"],
                "sourceConceptIds": [],
                "definition": (
                    f"“{reader['label']}”Reader 下的字段级候选投影。字段直接命中优先；"
                    "对象上下文仅作为候选挂接，冲突与未解决项不被隐藏。"
                ),
            },
            "expressions": expressions,
        }
    return catalog, shards


def _expressions_by_field_name(
    fields: list[dict[str, Any]], reader_id: str
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in fields:
        groups[row["field"]].append(row)
    result = []
    for field_name, rows in sorted(groups.items()):
        comments = Counter(row["fieldComment"] for row in rows if row["fieldComment"])
        label = comments.most_common(1)[0][0] if comments else field_name
        qualifier_pairs = sorted(
            {
                (item["dimension"], item["value"])
                for row in rows
                for item in row["qualifiers"]
            }
        )
        direct_count = sum(
            any(
                item["reader"] == reader_id and item["mode"] == "DIRECT_FIELD_LEXICAL"
                for item in row["assignments"]
            )
            for row in rows
        )
        result.append(
            _expression(
                f"{reader_id}:expression:{hashlib.sha256(field_name.encode()).hexdigest()[:16]}",
                label,
                rows,
                qualifier_pairs,
                support_status="PROVISIONAL",
                assertions=[
                    {
                        "id": f"{reader_id}:{field_name}:assignment",
                        "predicate": "CANDIDATE_READER_ASSIGNMENT",
                        "objectId": reader_id,
                        "methodId": "p1.lexical_and_object_context.v1",
                        "status": "CANDIDATE",
                        "evidenceRefs": [],
                        "counterevidenceRefs": [],
                    },
                    {
                        "id": f"{reader_id}:{field_name}:mode-count",
                        "predicate": f"DIRECT={direct_count};CONTEXT={len(rows) - direct_count}",
                        "objectId": reader_id,
                        "methodId": "p1.assignment_mode_count.v1",
                        "status": "OBSERVED",
                        "evidenceRefs": [],
                        "counterevidenceRefs": [],
                    },
                ],
            )
        )
    return result


def _full_corpus_shard(
    fields: list[dict[str, Any]], stages: list[dict[str, str]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    concept_id = "utility:all-fields"
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in fields:
        groups[row["object"]].append(row)
    expressions = []
    observed_ids = set()
    for object_name, rows in sorted(groups.items()):
        observed_ids.update(row["id"] for row in rows)
        label = rows[0]["objectComment"] or object_name
        expressions.append(
            _expression(
                f"utility:object:{hashlib.sha256(object_name.encode()).hexdigest()[:16]}",
                f"{label} · {object_name}",
                rows,
                [],
                support_status="SUPPORTED",
                assertions=[
                    {
                        "id": f"utility:{object_name}:completeness",
                        "predicate": "P1_PHYSICAL_FIELD_MEMBERSHIP",
                        "objectId": object_name,
                        "methodId": "p1.exact_physical_identity.v1",
                        "status": "OBSERVED",
                        "evidenceRefs": [],
                        "counterevidenceRefs": [],
                    }
                ],
            )
        )
    if len(observed_ids) != len(fields):
        raise ValueError("Full corpus shard lost or duplicated field identities")
    stage_ids = [str(row["id"]) for row in stages]
    catalog = {
        "id": concept_id,
        "shard": _safe_shard_name(concept_id),
        "label": "全量字段（治理视图，非 Reader）",
        "status": "PHYSICAL_FACT_PROJECTION",
        "supportStatus": "SUPPORTED",
        "stageIds": stage_ids,
        "lifecycleEntries": [
            {
                "stage_id": stage_id,
                "role": "CROSS_STAGE",
                "seed_reason": "全量字段核对入口，不代表业务阶段归属",
            }
            for stage_id in stage_ids
        ],
        "areaIds": [],
        "areaLabels": ["治理与全量核对"],
        "areaStatus": "UTILITY_NOT_BUSINESS_AREA",
        "navigationRole": "CROSS_STAGE",
        "expressionCount": len(expressions),
        "fieldCount": len(fields),
        "tableCount": len(groups),
        "search": f"全量字段 治理视图 {len(fields)} "
        + " ".join(
            f"{row['object']} {row['objectComment']} {row['field']} {row['fieldComment']}"
            for row in fields
        ).upper(),
    }
    return catalog, {
        "concept": {
            **catalog,
            "sourceLabels": ["P1 全量物理字段"],
            "sourceConceptIds": [],
            "definition": (
                f"{len(fields):,} 个 P1 字段的完整核对入口，按表组织。"
                "此入口不是第七个 Reader，"
                "也不把未归属或 EXCLUDED 字段提升为业务语义。"
            ),
        },
        "expressions": expressions,
    }


def _expression(
    expression_id: str,
    label: str,
    rows: list[dict[str, Any]],
    qualifier_pairs: list[tuple[str, str]],
    *,
    support_status: str,
    assertions: list[dict[str, Any]],
) -> dict[str, Any]:
    physical_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        physical_groups[row["field"]].append(
            {
                "schema": row["schema"],
                "table": row["object"],
                "column": row["field"],
                "fieldComment": row["fieldComment"],
                "commentFromConsensus": False,
                "tableComment": row["objectComment"],
                "columnId": row["id"],
                "assetId": row["assetId"],
                "objectUrl": row["objectUrl"],
                "dataType": row["dataType"],
                "nullable": row["nullable"],
                "ordinal": row["ordinal"],
                "preparationDisposition": row["disposition"],
                "preparationReason": row["dispositionReason"],
                "readerAssignments": [
                    f"{item['reader']}:{item['mode']}" for item in row["assignments"]
                ],
                "suppressedReaderAssignments": [
                    f"{item['reader']}:{item['mode']}"
                    for item in row["suppressedAssignments"]
                ],
                "conflictCount": row["conflictCount"],
                "conflictTypes": row["conflictTypes"],
                "unresolvedCount": row["unresolvedCount"],
                "unresolvedCodes": row["unresolvedCodes"],
            }
        )
    conflict_types = sorted({kind for row in rows for kind in row["conflictTypes"]})
    unresolved_codes = sorted({code for row in rows for code in row["unresolvedCodes"]})
    return {
        "id": expression_id,
        "label": label,
        "status": "CANDIDATE" if support_status != "SUPPORTED" else "OBSERVED",
        "supportStatus": support_status,
        "fieldCount": len(rows),
        "tableCount": len({row["assetId"] for row in rows}),
        "qualifiers": [
            {
                "dimension": dimension,
                "dimensionLabel": QUALIFIER_LABELS.get(dimension, dimension),
                "value": value,
                "valueLabel": VALUE_LABELS.get(value, value),
            }
            for dimension, value in qualifier_pairs
        ],
        "contexts": [],
        "physicalGroups": [
            {"name": name, "instances": instances}
            for name, instances in sorted(physical_groups.items())
        ],
        "conflicts": (
            [
                {
                    "types": conflict_types,
                    "fieldCount": sum(row["conflictCount"] > 0 for row in rows),
                }
            ]
            if conflict_types
            else []
        ),
        "uncertainties": (
            [
                {
                    "codes": unresolved_codes,
                    "fieldCount": sum(row["unresolvedCount"] > 0 for row in rows),
                }
            ]
            if unresolved_codes
            else []
        ),
        "sourceConceptIds": [],
        "assertions": assertions,
        "evidence": [
            {
                "id": row["id"],
                "type": "P1_FIELD_EVIDENCE_PACK",
                "label": f"{row['object']}.{row['field']}",
                "sourceRef": row["id"],
                "role": "SUPPORT" if row["disposition"] == "PREPARED" else "BOUNDARY",
            }
            for row in rows[:120]
        ],
    }


def _stage_rows(
    stages: list[dict[str, str]], catalog: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    for stage in stages:
        groups = {"CORE_OBJECT": [], "BUSINESS_EVENT": [], "CROSS_STAGE": []}
        for item in catalog:
            if stage["id"] in item["stageIds"]:
                groups[item["navigationRole"]].append(item["id"])
        rows.append({"id": stage["id"], "label": stage["label"], "groups": groups})
    return rows


def _governance_queue(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    definitions = [
        ("UNASSIGNED_FIELD", lambda row: not row["assignments"]),
        ("EXCLUDED", lambda row: row["disposition"] == "EXCLUDED"),
        ("CONFLICT", lambda row: row["conflictCount"] > 0),
        ("UNRESOLVED", lambda row: row["unresolvedCount"] > 0),
        ("MULTI_READER_CANDIDATE", lambda row: len(row["assignments"]) > 1),
    ]
    result = []
    for reason, predicate in definitions:
        rows = [row for row in fields if predicate(row)]
        if not rows:
            continue
        result.append(
            {
                "reason": reason,
                "count": len(rows),
                "items": [
                    {
                        "label": f"{row['object']}.{row['field']}",
                        "methodId": "p1.full_field_governance_projection.v1",
                        "status": reason,
                        "sourceRef": row["id"],
                    }
                    for row in rows[:200]
                ],
            }
        )
    return result


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_written_full_corpus_shard(
    shard_path: Path, expected_ids: set[str]
) -> int:
    text = shard_path.read_text(encoding="utf-8")
    marker = 'window.SEMANTIC_NAV_SHARDS["utility:all-fields"]='
    if marker not in text or not text.endswith(";\n"):
        raise ValueError("Generated full-corpus shard has an invalid wrapper")
    payload = json.loads(text.split(marker, 1)[1][:-2])
    observed_ids = [
        str(instance["columnId"])
        for expression in payload["expressions"]
        for group in expression["physicalGroups"]
        for instance in group["instances"]
    ]
    if len(observed_ids) != len(expected_ids) or set(observed_ids) != expected_ids:
        raise ValueError(
            "Generated full-corpus shard does not contain the exact physical field set"
        )
    return len(observed_ids)
