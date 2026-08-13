"""Reusable business-navigation configuration and candidate projection."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Iterable

import yaml


REQUIRED_CONFIG_KEYS = {
    "schema_version",
    "business_skeleton_version",
    "attribute_axes_version",
    "reader_concepts",
    "lifecycle_stages",
    "business_areas",
    "attribute_axes",
    "extension_policy",
    "publication",
}


def load_navigation_config(path: str | Path) -> dict[str, Any]:
    """Load and validate an open, candidate-only navigation configuration."""

    config_path = Path(path)
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    _validate_config(payload)
    return payload


def project_business_area_entries(
    config: dict[str, Any],
    concepts: Iterable[dict[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Project configured areas and explicitly evidenced concept candidates.

    The skeleton alone produces only area entries. A concept entry requires an
    explicit ``navigation_area`` and at least one evidence reference.
    """

    entries: list[dict[str, Any]] = []
    for area in config["business_areas"]:
        entries.append(
            {
                "entry_id": f"nav:{area['id']}",
                "label": area["label"],
                "path": [area["label"]],
                "entry_kind": "BUSINESS_AREA",
                "status": "CANDIDATE",
                "evidence_refs": [],
            }
        )

    area_by_id = {area["id"]: area for area in config["business_areas"]}
    for concept in concepts:
        area_id = concept.get("navigation_area")
        evidence_refs = list(concept.get("evidence_refs", []))
        if area_id not in area_by_id or not evidence_refs:
            continue
        area = area_by_id[area_id]
        entries.append(
            {
                "entry_id": f"nav:{area_id}:{concept['concept_id']}",
                "label": concept["label"],
                "path": [area["label"], concept["label"]],
                "entry_kind": "CONCEPT",
                "target_id": concept["concept_id"],
                "status": concept.get("status", "CANDIDATE"),
                "evidence_refs": evidence_refs,
            }
        )
    return entries


def discover_open_attribute_shapes(
    labels: Iterable[str], *, min_support: int = 2
) -> list[dict[str, Any]]:
    """Find repeated lexical shapes as open candidates, never as published axes."""

    normalized = [str(label).strip() for label in labels if str(label).strip()]
    counts: dict[str, set[str]] = {}
    for label in normalized:
        token = _candidate_tail(label)
        if token and token != label:
            counts.setdefault(token, set()).add(label)
    return [
        {
            "candidate_id": f"open-attribute:{token}",
            "observed_shape": token,
            "source_labels": sorted(source_labels),
            "support_count": len(source_labels),
            "status": "OPEN_CANDIDATE",
            "publication_status": "NOT_PUBLISHED",
        }
        for token, source_labels in sorted(counts.items())
        if len(source_labels) >= min_support
    ]


def separate_concept_layers(
    concept_id: str,
    expression: dict[str, Any],
    field_attributes: Iterable[dict[str, Any]],
    qualifiers: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Return separate concept, expression, field-attribute and qualifier layers."""

    return {
        "concept": {"concept_id": concept_id},
        "attribute_expression": dict(expression),
        "field_attributes": [
            dict(item) for item in field_attributes if item.get("concept_id") == concept_id
        ],
        "qualifiers": [dict(item) for item in qualifiers],
    }


def bounded_wiki_context_candidates(
    concepts: Iterable[dict[str, Any]],
    wiki_rows: Iterable[dict[str, Any]] | None,
    *,
    max_per_concept: int = 8,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return bounded Wiki context candidates without publishing hierarchy."""

    if wiki_rows is None:
        return [], [{"code": "WIKI_NOT_EVALUABLE", "status": "NOT_EVALUABLE"}]

    rows = list(wiki_rows)
    candidates: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for concept in concepts:
        label = str(concept.get("label", "")).strip().lower()
        if not label:
            continue
        matched = 0
        for row in rows:
            title = str(row.get("title", "")).strip()
            if not title or label not in title.lower():
                continue
            if matched >= max_per_concept:
                diagnostics.append(
                    {
                        "code": "WIKI_CANDIDATE_BUDGET_EXCEEDED",
                        "concept_id": concept.get("concept_id"),
                        "limit": max_per_concept,
                    }
                )
                break
            candidates.append(
                {
                    "candidate_id": f"wiki:{concept['concept_id']}:{row['page_id']}",
                    "concept_id": concept["concept_id"],
                    "page_id": row["page_id"],
                    "title": title,
                    "ancestor_path": list(row.get("ancestor_path", [])),
                    "role": "CONTEXT",
                    "status": "CANDIDATE",
                    "publication_status": "NOT_PUBLISHED",
                    "method_id": "bounded-title-context-v1",
                    "evidence_refs": [str(row.get("source_ref", row["page_id"]))],
                }
            )
            matched += 1
    return candidates, diagnostics


def build_concept_detail_projection(
    concept: dict[str, Any],
    *,
    expressions: Iterable[dict[str, Any]] = (),
    field_attributes: Iterable[dict[str, Any]] = (),
    qualifiers: Iterable[dict[str, Any]] = (),
    contexts: Iterable[dict[str, Any]] = (),
    related_concepts: Iterable[dict[str, Any]] = (),
    physical_implementations: Iterable[dict[str, Any]] = (),
    unresolved: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Build a reader-facing concept projection without merging its layers."""

    concept_id = concept["concept_id"]
    physical: dict[str, dict[str, Any]] = {}
    for item in physical_implementations:
        if item.get("concept_id", concept_id) != concept_id:
            continue
        physical.setdefault(item["implementation_id"], dict(item))

    unresolved_by_reason: dict[str, list[dict[str, Any]]] = {}
    for item in unresolved:
        reason = str(item.get("reason", "UNKNOWN"))
        unresolved_by_reason.setdefault(reason, []).append(dict(item))

    return {
        "concept": dict(concept),
        "attribute_expressions": [
            dict(item)
            for item in expressions
            if item.get("concept_id") == concept_id
        ],
        "field_attributes": [
            dict(item)
            for item in field_attributes
            if item.get("concept_id") == concept_id
        ],
        "qualifiers": [dict(item) for item in qualifiers],
        "business_contexts": [dict(item) for item in contexts],
        "related_concepts": [dict(item) for item in related_concepts],
        "physical_implementations": list(physical.values()),
        "unresolved": unresolved_by_reason,
    }


def map_observed_concepts_to_business_areas(
    config: dict[str, Any], concepts: Iterable[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Create bounded area candidates from observed labels and configured seeds."""

    terms_by_area = config.get("business_area_terms", {})
    results: list[dict[str, Any]] = []
    for concept in concepts:
        label = str(concept.get("label", "")).strip().lower()
        scored = {
            area_id: _business_area_match_score(label, terms)
            for area_id, terms in terms_by_area.items()
        }
        best_score = max(scored.values(), default=0)
        matches = [
            area_id
            for area_id, score in scored.items()
            if score and score == best_score
        ]
        if len(matches) == 1:
            results.append(
                {
                    "concept_id": concept["business_concept_id"],
                    "label": concept.get("label", ""),
                    "candidate_area_ids": matches,
                    "status": "CANDIDATE",
                    "reason": "LEXICAL_RECALL_REQUIRES_EVIDENCE_REVIEW",
                    "evidence_refs": list(concept.get("source_concept_ids", [])),
                }
            )
        elif len(matches) > 1:
            results.append(
                {
                    "concept_id": concept["business_concept_id"],
                    "label": concept.get("label", ""),
                    "candidate_area_ids": matches,
                    "status": "CONFLICT",
                    "reason": "MULTI_AREA_CANDIDATE",
                    "evidence_refs": list(concept.get("source_concept_ids", [])),
                }
            )
        else:
            results.append(
                {
                    "concept_id": concept["business_concept_id"],
                    "label": concept.get("label", ""),
                    "candidate_area_ids": [],
                    "status": "UNKNOWN",
                    "reason": "UNKNOWN_BUSINESS_CONCEPT",
                    "evidence_refs": list(concept.get("source_concept_ids", [])),
                }
            )
    return results


def _validate_config(config: dict[str, Any]) -> None:
    missing = REQUIRED_CONFIG_KEYS - set(config)
    if missing:
        raise ValueError(f"navigation config missing keys: {sorted(missing)}")
    if config["schema_version"] != "reusable-semantic-navigation-v1":
        raise ValueError("unsupported navigation schema version")
    _validate_unique_ids(config["business_areas"], "business area")
    _validate_unique_ids(config["lifecycle_stages"], "lifecycle stage")
    _validate_unique_ids(config["attribute_axes"], "attribute axis")
    _validate_unique_ids(config["reader_concepts"], "reader concept")
    if len(config["lifecycle_stages"]) != 6:
        raise ValueError("semantic navigation requires exactly six lifecycle stages")
    for stage in config["lifecycle_stages"]:
        if not isinstance(stage.get("concept_terms"), list) or not stage["concept_terms"]:
            raise ValueError("each lifecycle stage requires open concept terms")
        for key in ("core_object_terms", "business_event_terms", "cross_stage_terms"):
            if not isinstance(stage.get(key), list):
                raise ValueError(f"each lifecycle stage requires {key}")
    stage_ids = {stage["id"] for stage in config["lifecycle_stages"]}
    for concept in config["reader_concepts"]:
        if not concept.get("source_labels") or not concept.get("lifecycle_entries"):
            raise ValueError("reader concepts require sources and lifecycle entries")
        for entry in concept["lifecycle_entries"]:
            if entry.get("stage_id") not in stage_ids:
                raise ValueError("reader concept references an unknown lifecycle stage")
            if entry.get("role") not in {"CORE_OBJECT", "BUSINESS_EVENT", "CROSS_STAGE"}:
                raise ValueError("reader concept has an invalid lifecycle role")
            if not entry.get("seed_reason"):
                raise ValueError("reader concept lifecycle entry requires a configuration seed reason")
    if config["publication"].get("canonical_write_back") is not False:
        raise ValueError("navigation projection cannot write canonical facts")
    if config["publication"].get("business_rows_read") is not False:
        raise ValueError("navigation projection cannot read business rows")
    if config["extension_policy"].get("wiki_only_hierarchy") != "NOT_PUBLISHED":
        raise ValueError("Wiki-only hierarchy must remain unpublished")


def _validate_unique_ids(rows: list[dict[str, Any]], label: str) -> None:
    ids = [row.get("id") for row in rows]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError(f"{label} ids must be non-empty and unique")


def _candidate_tail(label: str) -> str | None:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]*$", label)
    if words:
        return words[0].upper()
    if re.search(r"[\u4e00-\u9fff]", label):
        return label[-2:] if len(label) >= 2 else None
    return None


def _business_area_match_score(label: str, terms: Iterable[str]) -> int:
    """Prefer the most specific Chinese phrase; keep English token ties open."""

    score = 0
    for raw_term in terms:
        term = str(raw_term).strip().lower()
        if not term:
            continue
        if re.search(r"[\u4e00-\u9fff]", term):
            if term in label:
                score = max(score, len(term))
        elif re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", label):
            score = max(score, 1)
    return score
