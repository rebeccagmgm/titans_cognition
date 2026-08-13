"""Context-enriched projection over frozen field semantics and Wiki tree snapshots."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import shutil
from string import Formatter
import tempfile
from typing import Mapping, Sequence

import yaml

from .semantic_cleaning import (
    build_review_batches,
    clean_concepts,
    discover_same_name_comment_reviews,
)


METHOD_ID = "context_semantics.cross_source_projection.v1"
METHOD_VERSION = "v1"
RELATIONS = {
    "BROADER",
    "NARROWER",
    "EXPRESSION_OF",
    "APPEARS_IN",
    "QUALIFIED_BY",
    "RELATED_TO",
    "IMPLEMENTED_BY",
}
STATUSES = {"CANDIDATE", "CONFIRMED", "REJECTED", "INSUFFICIENT_EVIDENCE", "CONFLICT"}
_NUMBERING = re.compile(r"^(?:\\?\d+(?:\.\d+)*|[A-Za-z]\d+)[.、\s\\-]*")
_TICKET = re.compile(r"\b[A-Z]{2,}-\d+\b", re.IGNORECASE)
_DATE = re.compile(r"\b(?:20\d{2}(?:[-/.]\d{1,2}){1,2}|20\d{2})\b")
_PARENS = re.compile(r"[（(][^()（）]{0,80}[）)]")
_SPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class ContextMapConfig:
    source_text: str
    config_hash: str
    field_semantics_dir: Path
    field_semantics_manifest_sha256: str
    wiki_tree_dir: Path
    wiki_manifest_sha256: str
    wiki_tree_sha256: str
    panorama_root: Path
    max_wiki_candidates_per_expression: int
    max_wiki_candidates_per_concept: int
    max_page_body_reads: int
    review_page_size: int
    initial_navigation_limit: int
    document_contexts: Mapping[str, tuple[str, ...]]
    products: Mapping[str, tuple[str, ...]]
    objects: tuple[str, ...]
    events: tuple[str, ...]
    processes: tuple[str, ...]
    subjects: tuple[str, ...]
    rules: tuple[str, ...]
    navigation_types: Mapping[str, tuple[str, ...]]
    family_labels: Mapping[str, str]
    navigation_terms: Mapping[str, tuple[str, ...]]
    attribute_navigation: Mapping[str, tuple[str, ...]] | None
    entity_attribute_template: str
    container_patterns: tuple[str, ...] | None
    semantic_family_order: tuple[str, ...]
    qualifier_axis_version: str
    qualifier_axis_mappings: Mapping[str, Mapping[str, str]]


@dataclass
class ContextMapResult:
    run_id: str
    business_concepts: list[dict[str, object]]
    business_contexts: list[dict[str, object]]
    attribute_expressions: list[dict[str, object]]
    qualifiers: list[dict[str, object]]
    semantic_relations: list[dict[str, object]]
    assertions: list[dict[str, object]]
    evidence_refs: list[dict[str, object]]
    semantic_observations: list[dict[str, object]]
    semantic_hypotheses: list[dict[str, object]]
    review_decisions: list[dict[str, object]]
    wiki_candidates: list[dict[str, object]]
    data_candidates: list[dict[str, object]]
    mapping_candidates: list[dict[str, object]]
    semantic_normalization_candidates: list[dict[str, object]]
    semantic_review_queue: list[dict[str, object]]
    diagnostics: list[dict[str, object]]
    stats: dict[str, object]
    quality_gate: dict[str, object]


def load_context_map_config(path: str | Path) -> ContextMapConfig:
    config_path = Path(path)
    source = config_path.read_text(encoding="utf-8")
    raw = yaml.safe_load(source)
    if not isinstance(raw, dict) or raw.get("version") != "v1":
        raise ValueError("context map config version must be v1")
    inputs = _mapping(raw, "inputs")
    limits = _mapping(raw, "limits")
    wiki = _mapping(raw, "wiki_semantics")
    nav = _mapping(raw, "navigation")
    qualifier_axes = _mapping(raw, "qualifier_axes")
    attribute_navigation = (
        _patterns(nav["attribute_types"]) if "attribute_types" in nav else None
    )
    for group, patterns in (attribute_navigation or {}).items():
        for pattern in patterns:
            if not str(pattern).strip().strip("*"):
                raise ValueError(
                    f"navigation.attribute_types.{group} contains an empty wildcard"
                )
    entity_attribute_template = str(
        nav.get("entity_attribute_template", "{entity}属性")
    )
    template_parts = [
        (field_name, format_spec, conversion)
        for _, field_name, format_spec, conversion in Formatter().parse(
            entity_attribute_template
        )
        if field_name is not None
    ]
    if template_parts != [("entity", "", None)]:
        raise ValueError(
            "navigation.entity_attribute_template must contain only {entity} exactly once"
        )
    container_patterns = (
        _strings(nav["container_patterns"]) if "container_patterns" in nav else None
    )
    if any(
        not pattern.strip().strip("*") for pattern in (container_patterns or ())
    ):
        raise ValueError("navigation.container_patterns contains an empty wildcard")
    return ContextMapConfig(
        source_text=source,
        config_hash=_sha256(source.encode("utf-8")),
        field_semantics_dir=Path(str(inputs["field_semantics_dir"])),
        field_semantics_manifest_sha256=str(
            inputs["field_semantics_manifest_sha256"]
        ).lower(),
        wiki_tree_dir=Path(str(inputs["wiki_tree_dir"])),
        wiki_manifest_sha256=str(inputs["wiki_manifest_sha256"]).lower(),
        wiki_tree_sha256=str(inputs["wiki_tree_sha256"]).lower(),
        panorama_root=Path(str(inputs["panorama_root"])),
        max_wiki_candidates_per_expression=_positive_int(
            limits, "max_wiki_candidates_per_expression"
        ),
        max_wiki_candidates_per_concept=_positive_int(
            limits, "max_wiki_candidates_per_concept"
        ),
        max_page_body_reads=_nonnegative_int(limits, "max_page_body_reads"),
        review_page_size=_positive_int(limits, "review_page_size"),
        initial_navigation_limit=_positive_int(limits, "initial_navigation_limit"),
        document_contexts=_patterns(_mapping(wiki, "document_contexts")),
        products=_patterns(_mapping(wiki, "products")),
        objects=_strings(wiki.get("objects")),
        events=_strings(wiki.get("events")),
        processes=_strings(wiki.get("processes")),
        subjects=_strings(wiki.get("subjects")),
        rules=_strings(wiki.get("rules")),
        navigation_types=_patterns(_mapping(nav, "concept_types")),
        family_labels={
            str(k): str(v) for k, v in _mapping(nav, "family_labels").items()
        },
        navigation_terms=_patterns(nav.get("family_terms", {})),
        attribute_navigation=attribute_navigation,
        entity_attribute_template=entity_attribute_template,
        container_patterns=container_patterns,
        semantic_family_order=_strings(
            nav.get(
                "semantic_family_order",
                ["TIME", "DATE", "RATE", "QUANTITY", "AMOUNT"],
            )
        ),
        qualifier_axis_version=str(qualifier_axes["version"]),
        qualifier_axis_mappings={
            str(dimension): {
                str(value): str(axis) for value, axis in values.items()
            }
            for dimension, values in _mapping(qualifier_axes, "mappings").items()
            if isinstance(values, Mapping)
        },
    )


def parse_wiki_tree(
    tree_path: str | Path,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Parse a tree snapshot deterministically while retaining malformed boundaries."""

    rows: list[dict[str, object]] = []
    diagnostics: list[dict[str, object]] = []
    seen: dict[str, dict[str, object]] = {}
    for line_number, line in enumerate(
        Path(tree_path).read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            diagnostics.append({"code": "INVALID_JSON", "line_number": line_number})
            continue
        if not isinstance(raw, Mapping):
            diagnostics.append({"code": "INVALID_NODE", "line_number": line_number})
            continue
        page_id = str(raw.get("pageId", ""))
        if not page_id or not raw.get("title"):
            diagnostics.append({"code": "INVALID_NODE", "line_number": line_number})
            continue
        try:
            depth = int(raw.get("depth", 0))
        except (TypeError, ValueError):
            diagnostics.append({"code": "INVALID_NODE", "line_number": line_number})
            continue
        row = {
            "page_id": page_id,
            "parent_page_id": str(raw["parentPageId"])
            if raw.get("parentPageId") is not None
            else None,
            "title": str(raw["title"]),
            "depth": depth,
        }
        if page_id in seen:
            code = (
                "DUPLICATE_IDENTICAL_NODE"
                if seen[page_id] == row
                else "DUPLICATE_CONFLICT_NODE"
            )
            diagnostics.append(
                {"code": code, "page_id": page_id, "line_number": line_number}
            )
            continue
        seen[page_id] = row
        rows.append(row)
    by_id = {str(row["page_id"]): row for row in rows}
    for row in rows:
        parent = row["parent_page_id"]
        if parent and parent not in by_id:
            diagnostics.append(
                {
                    "code": "MISSING_PARENT",
                    "page_id": row["page_id"],
                    "parent_page_id": parent,
                }
            )
        path, cycle = _ancestor_path(row, by_id)
        row["ancestor_path"] = path[:-1]
        row["normalized_title"] = normalize_title(str(row["title"]))
        if cycle:
            diagnostics.append({"code": "ANCESTOR_CYCLE", "page_id": row["page_id"]})
    return sorted(rows, key=lambda x: (int(x["depth"]), str(x["page_id"]))), diagnostics


def normalize_title(value: str) -> str:
    value = value.replace("\\.", ".").strip()
    value = _DATE.sub(" ", value)
    value = _TICKET.sub(" ", value)
    value = _NUMBERING.sub("", value)
    return _SPACE.sub(" ", value).strip(" .-_—")


def discover_wiki_candidates(
    rows: Sequence[Mapping[str, object]], config: ContextMapConfig, snapshot_id: str
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for row in rows:
        title = str(row["normalized_title"])
        path = [str(x) for x in row.get("ancestor_path", [])]
        combined = " > ".join((*path, title))
        doc_contexts = _matched_mapping(combined, config.document_contexts)
        typed: list[tuple[str, str]] = []
        typed.extend(
            ("DOMAIN_OR_PRODUCT", value)
            for value in _matched_mapping(combined, config.products)
        )
        typed.extend(
            ("BUSINESS_OBJECT", value)
            for value in _matched_terms(title, config.objects)
        )
        typed.extend(
            ("BUSINESS_EVENT", value) for value in _matched_terms(title, config.events)
        )
        typed.extend(
            ("BUSINESS_PROCESS", value)
            for value in _matched_terms(title, config.processes)
        )
        typed.extend(
            ("BUSINESS_SUBJECT", value)
            for value in _matched_terms(title, config.subjects)
        )
        typed.extend(
            ("BUSINESS_RULE", value) for value in _matched_terms(title, config.rules)
        )
        if not typed and title:
            typed.append(("UNRESOLVED", title))
        for candidate_type, label in dict.fromkeys(typed):
            candidates.append(
                {
                    "candidate_id": _stable_id(
                        "wiki", snapshot_id, str(row["page_id"]), candidate_type, label
                    ),
                    "candidate_type": candidate_type,
                    "label": label,
                    "page_id": row["page_id"],
                    "title": row["title"],
                    "normalized_title": title,
                    "ancestor_path": path,
                    "document_contexts": doc_contexts,
                    "snapshot_id": snapshot_id,
                    "status": "CANDIDATE",
                    "evidence_ref": f"wiki-tree:{snapshot_id}:page:{row['page_id']}",
                }
            )
    return sorted(
        candidates,
        key=lambda x: (str(x["label"]), str(x["page_id"]), str(x["candidate_type"])),
    )


def run_context_map(config: ContextMapConfig) -> ContextMapResult:
    """Build the bounded projection from frozen local inputs."""

    field_manifest_path = config.field_semantics_dir / "manifest.json"
    wiki_manifest_path = config.wiki_tree_dir / "manifest.json"
    wiki_tree_path = config.wiki_tree_dir / "tree.jsonl"
    _require_hash(field_manifest_path, config.field_semantics_manifest_sha256)
    _require_hash(wiki_manifest_path, config.wiki_manifest_sha256)
    _require_hash(wiki_tree_path, config.wiki_tree_sha256)
    field_manifest = _read_json(field_manifest_path)
    wiki_manifest = _read_json(wiki_manifest_path)
    snapshot_id = str(wiki_manifest.get("snapshotId", "unknown-snapshot"))
    run_id = (
        "context-map-"
        + _sha256(
            (
                config.config_hash
                + config.field_semantics_manifest_sha256
                + config.wiki_tree_sha256
            ).encode("utf-8")
        )[:16]
    )

    concepts = _read_jsonl(config.field_semantics_dir / "base_concepts.jsonl")
    source_expressions = _read_jsonl(
        config.field_semantics_dir / "concept_expressions.jsonl"
    )
    fields = _read_jsonl(config.field_semantics_dir / "field_semantic_results.jsonl")
    facets = _read_jsonl(config.field_semantics_dir / "field_facets.jsonl")
    wiki_rows, diagnostics = parse_wiki_tree(wiki_tree_path)
    wiki_candidates = discover_wiki_candidates(wiki_rows, config, snapshot_id)
    cleaned_concepts, family_reviews = clean_concepts(concepts)
    same_name_reviews = discover_same_name_comment_reviews(fields)
    result = _project_data(
        run_id,
        concepts,
        cleaned_concepts,
        source_expressions,
        fields,
        facets,
        wiki_candidates,
        config,
    )
    result.semantic_review_queue.extend([*family_reviews, *same_name_reviews])
    result.diagnostics.extend(diagnostics)
    result.stats.update(
        {
            "wiki_node_count": len(wiki_rows),
            "wiki_candidate_count": len(wiki_candidates),
            "wiki_error_count": int(
                wiki_manifest.get(
                    "errorCount", wiki_manifest.get("counts", {}).get("errors", 0)
                )
            ),
            "source_field_count": int(
                field_manifest.get("stats", {}).get("field_count", len(fields))
            ),
        }
    )
    validate_context_map(result)
    result.quality_gate = _quality_gate(result, config)
    return result


def _project_data(
    run_id: str,
    concepts: Sequence[Mapping[str, object]],
    cleaned_concepts: Sequence[object],
    source_expressions: Sequence[Mapping[str, object]],
    fields: Sequence[Mapping[str, object]],
    facets: Sequence[Mapping[str, object]],
    wiki_candidates: Sequence[Mapping[str, object]],
    config: ContextMapConfig,
) -> ContextMapResult:
    concept_by_id = {str(x["concept_id"]): x for x in concepts}
    facets_by_binding: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for facet in facets:
        facets_by_binding[str(facet["binding_id"])].append(facet)
    comment_consensus = _column_comment_consensus(
        fields, facets_by_binding, config.qualifier_axis_mappings
    )
    expr_by_ref: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for expr in source_expressions:
        expr_by_ref[str(expr.get("source_ref", ""))].append(expr)

    cleaned_by_source = {str(row.source_concept_id): row for row in cleaned_concepts}
    effective_family_by_source: dict[str, str] = {}
    source_by_family: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in concepts:
        source_id = str(row["concept_id"])
        cleaned = cleaned_by_source[source_id]
        use_candidate_family = (
            cleaned.method == "IDENTITY" or cleaned.attribute_kind == "IDENTIFIER"
        )
        effective_family = (
            str(cleaned.family_label)
            if use_candidate_family
            else str(cleaned.source_label)
        )
        effective_family_by_source[source_id] = effective_family
        source_by_family[effective_family].append(row)
    business_concepts = []
    business_id: dict[str, str] = {}
    for family_label, sources in sorted(source_by_family.items()):
        business_concept_id = _stable_id("business-concept", run_id, family_label)
        source_ids = sorted(str(row["concept_id"]) for row in sources)
        source_labels = sorted(str(row["label"]) for row in sources)
        support_status = (
            "SUPPORTED"
            if any(row.get("support_status") == "SUPPORTED" for row in sources)
            else "PROVISIONAL"
        )
        semantic_scopes = sorted(
            {str(row.get("semantic_scope", "UNRESOLVED")) for row in sources}
        )
        value_kinds = sorted(
            {str(value) for row in sources for value in row.get("value_kinds", [])}
        )
        language_alias_only = all(
            str(row["label"]) == family_label
            or cleaned_by_source[str(row["concept_id"])].attribute_kind == "IDENTIFIER"
            for row in sources
        )
        business_concepts.append(
            {
                "business_concept_id": business_concept_id,
                "source_concept_ids": source_ids,
                "source_labels": source_labels,
                "label": family_label,
                "support_status": support_status,
                "semantic_scope": (
                    semantic_scopes[0] if len(semantic_scopes) == 1 else "MIXED"
                ),
                "value_kinds": value_kinds,
                "status": "CANDIDATE",
                "normalization_status": (
                    "IDENTITY"
                    if source_labels == [family_label]
                    else "LANGUAGE_ALIAS"
                    if language_alias_only
                    else "NEEDS_REVIEW"
                ),
            }
        )
        for source_id in source_ids:
            business_id[source_id] = business_concept_id

    families_by_column: dict[str, set[str]] = defaultdict(set)
    for field in fields:
        for binding in field.get("candidate_bindings", []):
            if binding.get("relation_kind") != "EXPRESSES":
                continue
            source_id = str(binding["concept_id"])
            families_by_column[str(field["column_id"])].add(
                effective_family_by_source[source_id]
            )

    expression_groups: dict[
        tuple[str, str, tuple[tuple[str, str], ...], str],
        list[tuple[Mapping[str, object], Mapping[str, object]]],
    ] = defaultdict(list)
    facet_conflicts_by_binding: dict[str, list[dict[str, object]]] = {}
    contextual_facets_by_binding: dict[str, tuple[tuple[str, str], ...]] = {}
    related_pairs: list[tuple[Mapping[str, object], Mapping[str, object]]] = []
    semantic_observations: list[dict[str, object]] = []
    for field in fields:
        for binding in field.get("candidate_bindings", []):
            if binding.get("relation_kind") == "RELATED_TO":
                related_pairs.append((field, binding))
                continue
            signature, source_conflicts = _resolve_facet_signature(
                facets_by_binding.get(str(binding["binding_id"]), []),
                config.qualifier_axis_mappings,
            )
            facet_conflicts_by_binding[str(binding["binding_id"])] = source_conflicts
            concept_id = str(binding["concept_id"])
            observation_id = _stable_id(
                "semantic-observation",
                str(field["column_id"]),
                str(binding.get("binding_id", "")),
            )
            semantic_observations.append(
                {
                    "observation_id": observation_id,
                    "column_id": str(field["column_id"]),
                    "asset_id": str(field["asset_id"]),
                    "column_name": str(field.get("column_name", "")),
                    "column_comment": field.get("column_comment"),
                    "declared_type": field.get("declared_type"),
                    "value_kind": field.get("value_kind"),
                    "source_concept_id": concept_id,
                    "source_concept_label": str(concept_by_id[concept_id]["label"]),
                    "binding_id": str(binding.get("binding_id", "")),
                    "raw_facets": [
                        {
                            "dimension": str(facet.get("dimension", "")),
                            "value": str(facet.get("value", "")),
                            "raw_fragment": facet.get("raw_fragment"),
                        }
                        for facet in facets_by_binding.get(
                            str(binding.get("binding_id", "")), []
                        )
                    ],
                }
            )
            cleaned = cleaned_by_source[concept_id]
            enriched_field = dict(field)
            physical_name = _normalize_physical_field_name(field.get("column_name"))
            inherited = comment_consensus.get((physical_name, concept_id, signature))
            if not str(field.get("column_comment") or "").strip() and inherited:
                enriched_field["semantic_comment"] = inherited["label"]
                enriched_field["semantic_comment_method"] = (
                    "SAME_NAME_CONCEPT_COMMENT_CONSENSUS"
                )
                enriched_field["semantic_comment_source_refs"] = inherited[
                    "source_refs"
                ]
            observed_label, label_provenance = _observed_field_expression_label(
                str(concept_by_id[concept_id]["label"]),
                enriched_field,
                binding,
                expr_by_ref,
            )
            enriched_field["semantic_label_provenance"] = label_provenance
            family_label = effective_family_by_source[concept_id]
            signature = _augment_observed_qualifiers(observed_label, signature)
            is_identifier_expression = (
                cleaned.attribute_kind == "IDENTIFIER"
                or _has_identifier_suffix(observed_label)
            )
            if not _semantic_label_compatible(
                family_label,
                observed_label,
                identifier=is_identifier_expression,
                qualifier_signature=signature,
                axis_mappings=config.qualifier_axis_mappings,
            ):
                enriched_field["semantic_uncertainties"] = [
                    {
                        "reason": "OBSERVED_LABEL_BASE_NOT_PROVEN",
                        "business_concept_label": family_label,
                        "observed_label": observed_label,
                        "source_ref": str(field["column_id"]),
                        "label_provenance": label_provenance,
                    }
                ]
            signature, contextual_signature = _partition_facet_signature(
                observed_label,
                field.get("column_name"),
                signature,
                facets_by_binding.get(str(binding["binding_id"]), []),
            )
            contextual_facets_by_binding[str(binding["binding_id"])] = (
                contextual_signature
            )
            if is_identifier_expression:
                observed_label = _canonicalize_identifier_label(observed_label)
                signature = tuple(
                    sorted(
                        {
                            *signature,
                            ("attribute_kind", "IDENTIFIER"),
                        }
                    )
                )
            signature = _augment_observed_qualifiers(observed_label, signature)
            signature = _remove_redundant_qualifiers(
                effective_family_by_source[concept_id], observed_label, signature
            )
            conflict_partition = json.dumps(
                facet_conflicts_by_binding.get(str(binding["binding_id"]), []),
                ensure_ascii=False,
                sort_keys=True,
            )
            expression_groups[
                (
                    effective_family_by_source[concept_id],
                    observed_label,
                    signature,
                    conflict_partition,
                )
            ].append((enriched_field, binding))

    qualifiers: list[dict[str, object]] = []
    qualifier_ids: dict[tuple[str, str], str] = {}
    attribute_expressions: list[dict[str, object]] = []
    relations: list[dict[str, object]] = []
    assertions: list[dict[str, object]] = []
    evidence: dict[str, dict[str, object]] = {}
    data_candidates: list[dict[str, object]] = []
    contexts: dict[str, dict[str, object]] = {}

    business_by_label = {str(row["label"]): row for row in business_concepts}
    for (family_label, observed_label, signature, conflict_partition), members in sorted(
        expression_groups.items()
    ):
        business_concept = business_by_label[family_label]
        label = observed_label
        qualifier_conflicts = [
            conflict
            for _, binding in members
            for conflict in facet_conflicts_by_binding.get(
                str(binding["binding_id"]), []
            )
        ]
        for field, _ in members:
            competing_families = sorted(
                families_by_column.get(str(field["column_id"]), set())
            )
            if len(competing_families) > 1:
                qualifier_conflicts.append(
                    {
                        "reason": "MULTI_CONCEPT_PHYSICAL_COLUMN",
                        "source_ref": str(field["column_id"]),
                        "candidate_business_concepts": competing_families,
                    }
                )
        qualifier_conflicts = _deduplicate_conflicts(qualifier_conflicts)
        semantic_uncertainties = _deduplicate_conflicts(
            [
                uncertainty
                for field, _ in members
                for uncertainty in field.get("semantic_uncertainties", [])
            ]
        )
        counterevidence_ids: list[str] = []
        for conflict in qualifier_conflicts:
            reason = str(conflict.get("reason") or "SEMANTIC_CONFLICT")
            for source_ref in _conflict_source_refs(conflict):
                counterevidence_id = _stable_id(
                    "evidence", "semantic-counterevidence", source_ref, reason
                )
                evidence[counterevidence_id] = {
                    "evidence_id": counterevidence_id,
                    "evidence_type": "SEMANTIC_COUNTEREVIDENCE",
                    "source_ref": source_ref,
                    "label": f"{reason}: {source_ref}",
                }
                counterevidence_ids.append(counterevidence_id)
        contextual_signature = sorted(
            {
                item
                for _, binding in members
                for item in contextual_facets_by_binding.get(
                    str(binding["binding_id"]), ()
                )
            }
        )
        label = _display_expression_label(label, signature)
        expression_id = _stable_id(
            "attribute-expression",
            run_id,
            family_label,
            observed_label,
            json.dumps(signature, ensure_ascii=False),
            conflict_partition,
        )
        field_refs = sorted({str(field["column_id"]) for field, _ in members})
        asset_refs = sorted({str(field["asset_id"]) for field, _ in members})
        physical_names = sorted({str(field["column_name"]) for field, _ in members})
        semantic_support_count = sum(
            field.get("semantic_label_provenance")
            in {"COLUMN_COMMENT", "SOURCE_EXPRESSION"}
            for field, _ in members
        )
        attribute_expressions.append(
            {
                "attribute_expression_id": expression_id,
                "label": label,
                "business_concept_id": business_concept["business_concept_id"],
                "source_concept_ids": sorted(
                    {str(binding["concept_id"]) for _, binding in members}
                ),
                "qualifier_signature": [
                    {"dimension": d, "value": v} for d, v in signature
                ],
                "contextual_qualifiers": [
                    {"dimension": dimension, "value": value}
                    for dimension, value in contextual_signature
                ],
                "field_count": len(field_refs),
                "object_count": len(asset_refs),
                "physical_expression_count": len(physical_names),
                "semantic_support_count": semantic_support_count,
                "support_status": (
                    "SUPPORTED" if semantic_support_count >= 2 else "PROVISIONAL"
                ),
                "status": (
                    "CONFLICT"
                    if qualifier_conflicts
                    else "INSUFFICIENT_EVIDENCE"
                    if semantic_uncertainties
                    else "CANDIDATE"
                ),
                "conflicts": qualifier_conflicts,
                "uncertainties": semantic_uncertainties,
            }
        )
        _add_assertion(
            assertions,
            relations,
            run_id,
            expression_id,
            "EXPRESSION_OF",
            str(business_concept["business_concept_id"]),
            [],
            1.0,
            counterevidence_refs=counterevidence_ids,
            status="CONFLICT" if qualifier_conflicts else "CANDIDATE",
        )
        for dimension, value in signature:
            key = (dimension, value)
            qualifier_id = qualifier_ids.setdefault(
                key, _stable_id("qualifier", run_id, dimension, value)
            )
            _add_assertion(
                assertions,
                relations,
                run_id,
                expression_id,
                "QUALIFIED_BY",
                qualifier_id,
                [],
                1.0,
                counterevidence_refs=counterevidence_ids,
                status="CONFLICT" if qualifier_conflicts else "CANDIDATE",
            )
        for field, binding in members:
            evidence_id = _stable_id(
                "evidence", "physical-column", str(field["column_id"])
            )
            evidence[evidence_id] = {
                "evidence_id": evidence_id,
                "evidence_type": "PHYSICAL_COLUMN",
                "source_ref": field["column_id"],
                "label": field.get("column_comment") or field["column_name"],
            }
            donor_evidence_ids = []
            for donor_ref in field.get("semantic_comment_source_refs", []):
                donor_evidence_id = _stable_id(
                    "evidence", "physical-column", str(donor_ref)
                )
                evidence.setdefault(
                    donor_evidence_id,
                    {
                        "evidence_id": donor_evidence_id,
                        "evidence_type": "PHYSICAL_COLUMN",
                        "source_ref": donor_ref,
                        "label": "同名字段中文注释来源",
                    },
                )
                donor_evidence_ids.append(donor_evidence_id)
            _add_assertion(
                assertions,
                relations,
                run_id,
                expression_id,
                "IMPLEMENTED_BY",
                str(field["column_id"]),
                [evidence_id, *donor_evidence_ids],
                1.0,
            )
            semantic_evidence = [evidence_id, *donor_evidence_ids]
            _add_assertion(
                assertions,
                relations,
                run_id,
                expression_id,
                "EXPRESSION_OF",
                str(business_concept["business_concept_id"]),
                semantic_evidence,
                1.0,
            )
            for dimension, value in signature:
                _add_assertion(
                    assertions,
                    relations,
                    run_id,
                    expression_id,
                    "QUALIFIED_BY",
                    qualifier_ids[(dimension, value)],
                    semantic_evidence,
                    1.0,
                )
        context_keys = _context_hints(members, config)
        for key, context_type, context_label, refs in context_keys:
            context_id = _stable_id("business-context", run_id, key)
            contexts.setdefault(
                context_id,
                {
                    "business_context_id": context_id,
                    "context_type": context_type,
                    "label": context_label,
                    "status": "CANDIDATE",
                    "source_hints": sorted(refs),
                },
            )
            _add_assertion(
                assertions,
                relations,
                run_id,
                expression_id,
                "APPEARS_IN",
                context_id,
                [_stable_id("evidence", "physical-column", str(ref)) for ref in refs],
                0.6,
            )
        data_candidates.append(
            {
                "candidate_id": _stable_id("data-candidate", expression_id),
                "attribute_expression_id": expression_id,
                "label": label,
                "business_concept_id": business_concept["business_concept_id"],
                "source_concept_ids": sorted(
                    {str(binding["concept_id"]) for _, binding in members}
                ),
                "context_ids": sorted(
                    _stable_id("business-context", run_id, key)
                    for key, *_ in context_keys
                ),
                "contextual_qualifiers": [
                    {"dimension": dimension, "value": value}
                    for dimension, value in contextual_signature
                ],
                "physical_expressions": physical_names,
                "field_refs": field_refs,
                "observation_refs": sorted(
                    {
                        _stable_id(
                            "semantic-observation",
                            str(field["column_id"]),
                            str(binding.get("binding_id", "")),
                        )
                        for field, binding in members
                    }
                ),
                "physical_instances": [
                    {
                        "column_id": field["column_id"],
                        "asset_id": field["asset_id"],
                        "schema_name": field.get("schema_name", ""),
                        "object_name": field.get("object_name", ""),
                        "column_name": field.get("column_name", ""),
                        "column_comment": field.get("column_comment"),
                        "semantic_comment": field.get("semantic_comment"),
                        "semantic_comment_method": field.get("semantic_comment_method"),
                        "semantic_comment_source_refs": field.get(
                            "semantic_comment_source_refs", []
                        ),
                    }
                    for field, _ in members
                ],
                "status": (
                    "CONFLICT"
                    if qualifier_conflicts
                    else "INSUFFICIENT_EVIDENCE"
                    if semantic_uncertainties
                    else "CANDIDATE"
                ),
                "conflicts": qualifier_conflicts,
                "uncertainties": semantic_uncertainties,
            }
        )

    for dimension, value in sorted(qualifier_ids):
        qualifiers.append(
            {
                "qualifier_id": qualifier_ids[(dimension, value)],
                "dimension": dimension,
                "value": value,
                "status": "CANDIDATE",
            }
        )

    direct_concepts_by_column: dict[str, set[str]] = defaultdict(set)
    for field in fields:
        for binding in field.get("candidate_bindings", []):
            if binding.get("relation_kind") == "EXPRESSES":
                direct = business_id.get(str(binding["concept_id"]))
                if direct:
                    direct_concepts_by_column[str(field["column_id"])].add(direct)
    emitted_related: set[tuple[str, str]] = set()
    for field, binding in related_pairs:
        target = business_id.get(str(binding["concept_id"]))
        if not target:
            continue
        ev_id = _stable_id("evidence", "related-column", str(field["column_id"]))
        evidence[ev_id] = {
            "evidence_id": ev_id,
            "evidence_type": "PHYSICAL_COLUMN",
            "source_ref": field["column_id"],
            "label": field.get("column_comment") or field["column_name"],
        }
        for source in direct_concepts_by_column.get(str(field["column_id"]), set()):
            if source == target or (source, target) in emitted_related:
                continue
            emitted_related.add((source, target))
            _add_assertion(
                assertions,
                relations,
                run_id,
                source,
                "RELATED_TO",
                target,
                [ev_id],
                1.0,
            )

    mapping_candidates = _map_wiki_candidates(
        run_id,
        data_candidates,
        wiki_candidates,
        contexts,
        assertions,
        relations,
        evidence,
        config,
    )
    (
        business_concepts,
        contexts,
        attribute_expressions,
        qualifiers,
        relations,
        assertions,
        data_candidates,
        semantic_hypotheses,
    ) = _publish_projection(
        business_concepts,
        contexts,
        attribute_expressions,
        qualifiers,
        relations,
        assertions,
        data_candidates,
    )
    expression_tree = _expression_tree(attribute_expressions, business_concepts)
    for row in attribute_expressions:
        row["display_parent_expression_id"] = expression_tree.get(
            str(row["attribute_expression_id"])
        )

    assertions, relations = _consolidate_assertions(assertions, relations)
    stats = {
        "business_concept_count": len(business_concepts),
        "attribute_expression_count": len(attribute_expressions),
        "qualifier_count": len(qualifiers),
        "business_context_count": len(contexts),
        "semantic_relation_count": len(relations),
        "assertion_count": len(assertions),
        "mapping_candidate_count": len(mapping_candidates),
    }
    normalization_candidates = [
        {
            "source_concept_id": str(row.source_concept_id),
            "source_label": str(row.source_label),
            "candidate_family_label": str(row.family_label),
            "display_label": str(row.display_label),
            "attribute_kind": row.attribute_kind,
            "qualifiers": [
                {"dimension": dimension, "value": value}
                for dimension, value in row.qualifiers
            ],
            "method": str(row.method),
            "evidence_labels": list(row.evidence_labels),
            "review_status": (
                "UNREVIEWED" if row.family_label != row.source_label else "NOT_REQUIRED"
            ),
        }
        for row in cleaned_concepts
    ]
    return ContextMapResult(
        run_id=run_id,
        business_concepts=business_concepts,
        business_contexts=sorted(contexts.values(), key=lambda x: str(x["label"])),
        attribute_expressions=attribute_expressions,
        qualifiers=qualifiers,
        semantic_relations=relations,
        assertions=assertions,
        evidence_refs=sorted(evidence.values(), key=lambda x: str(x["evidence_id"])),
        semantic_observations=semantic_observations,
        semantic_hypotheses=semantic_hypotheses,
        review_decisions=[],
        wiki_candidates=list(wiki_candidates),
        data_candidates=data_candidates,
        mapping_candidates=mapping_candidates,
        semantic_normalization_candidates=normalization_candidates,
        semantic_review_queue=[],
        diagnostics=[],
        stats=stats,
        quality_gate={},
    )


def _publish_projection(
    business_concepts: list[dict[str, object]],
    contexts: dict[str, dict[str, object]],
    attribute_expressions: list[dict[str, object]],
    qualifiers: list[dict[str, object]],
    relations: list[dict[str, object]],
    assertions: list[dict[str, object]],
    data_candidates: list[dict[str, object]],
) -> tuple[
    list[dict[str, object]],
    dict[str, dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    """Publish only supported hypotheses while retaining every candidate.

    The projection is deliberately stricter than discovery: uncertainty is a
    review item, not a conflict and not a reader-facing semantic fact.
    """

    data_by_expression = {
        str(row["attribute_expression_id"]): row for row in data_candidates
    }
    hypotheses: list[dict[str, object]] = []
    published_expression_ids: set[str] = set()
    for expression in attribute_expressions:
        expression_id = str(expression["attribute_expression_id"])
        status = str(expression["status"])
        if status == "CANDIDATE":
            publication_status = "PUBLISHED"
            publication_reason = "DIRECT_OR_FACET_EXPLAINED_SEMANTIC_SUPPORT"
            published_expression_ids.add(expression_id)
        elif status == "CONFLICT":
            publication_status = "NOT_PUBLISHED"
            publication_reason = "COUNTEREVIDENCE_REQUIRES_REVIEW"
        else:
            publication_status = "NOT_PUBLISHED"
            publication_reason = "SEMANTIC_LINK_NOT_PROVEN"
        data = data_by_expression.get(expression_id, {})
        expression_assertions = [
            row for row in assertions if str(row["subject_id"]) == expression_id
        ]
        hypotheses.append(
            {
                "hypothesis_id": _stable_id("semantic-hypothesis", expression_id),
                "proposed_attribute_expression_id": expression_id,
                "proposed_business_concept_id": expression["business_concept_id"],
                "label": expression["label"],
                "qualifier_signature": expression.get("qualifier_signature", []),
                "field_refs": data.get("field_refs", []),
                "observation_refs": data.get("observation_refs", []),
                "method_id": METHOD_ID,
                "evidence_refs": sorted(
                    {
                        str(ref)
                        for row in expression_assertions
                        for ref in row.get("evidence_refs", [])
                    }
                ),
                "counterevidence_refs": sorted(
                    {
                        str(ref)
                        for row in expression_assertions
                        for ref in row.get("counterevidence_refs", [])
                    }
                ),
                "status": status,
                "publication_status": publication_status,
                "publication_reason": publication_reason,
                "conflicts": expression.get("conflicts", []),
                "uncertainties": expression.get("uncertainties", []),
            }
        )

    published_expressions = [
        row
        for row in attribute_expressions
        if str(row["attribute_expression_id"]) in published_expression_ids
    ]
    published_data = [
        row
        for row in data_candidates
        if str(row["attribute_expression_id"]) in published_expression_ids
    ]
    used_concepts = {
        str(row["business_concept_id"]) for row in published_expressions
    }
    published_concepts = [
        row
        for row in business_concepts
        if str(row["business_concept_id"]) in used_concepts
    ]
    published_assertions = [
        row
        for row in assertions
        if (
            str(row["subject_id"]) in published_expression_ids
            or (
                str(row["subject_id"]) in used_concepts
                and str(row["object_id"]) in used_concepts
            )
        )
    ]
    published_relations = [
        row
        for row in relations
        if (
            str(row["subject_id"]) in published_expression_ids
            or (
                str(row["subject_id"]) in used_concepts
                and str(row["object_id"]) in used_concepts
            )
        )
    ]
    used_contexts = {
        str(row["object_id"])
        for row in published_assertions
        if row["predicate"] == "APPEARS_IN"
    }
    used_qualifiers = {
        str(row["object_id"])
        for row in published_assertions
        if row["predicate"] == "QUALIFIED_BY"
    }
    published_contexts = {
        key: row for key, row in contexts.items() if key in used_contexts
    }
    published_qualifiers = [
        row for row in qualifiers if str(row["qualifier_id"]) in used_qualifiers
    ]
    return (
        published_concepts,
        published_contexts,
        published_expressions,
        published_qualifiers,
        published_relations,
        published_assertions,
        published_data,
        hypotheses,
    )


def validate_context_map(result: ContextMapResult) -> None:
    object_types: dict[str, str] = {}
    for row in result.business_concepts:
        object_types[str(row["business_concept_id"])] = "BusinessConcept"
    for row in result.business_contexts:
        object_types[str(row["business_context_id"])] = "BusinessContext"
    for row in result.attribute_expressions:
        object_types[str(row["attribute_expression_id"])] = "AttributeExpression"
    for row in result.qualifiers:
        object_types[str(row["qualifier_id"])] = "Qualifier"
    technical_ids = {
        str(instance["column_id"])
        for candidate in result.data_candidates
        for instance in candidate.get("physical_instances", [])
    }
    evidence_ids = {str(row["evidence_id"]) for row in result.evidence_refs}
    _require_unique_ids(result.business_concepts, "business_concept_id")
    _require_unique_ids(result.business_contexts, "business_context_id")
    _require_unique_ids(result.attribute_expressions, "attribute_expression_id")
    _require_unique_ids(result.qualifiers, "qualifier_id")
    _require_unique_ids(result.assertions, "assertion_id")
    _require_unique_ids(result.semantic_relations, "relation_id")
    _require_unique_ids(result.evidence_refs, "evidence_id")
    _require_unique_ids(result.semantic_observations, "observation_id")
    _require_unique_ids(result.semantic_hypotheses, "hypothesis_id")
    for assertion in result.assertions:
        predicate = str(assertion["predicate"])
        if predicate not in RELATIONS or assertion["status"] not in STATUSES:
            raise ValueError("invalid assertion enum")
        subject = str(assertion["subject_id"])
        obj = str(assertion["object_id"])
        if subject not in object_types:
            raise ValueError(f"unknown assertion subject: {subject}")
        allowed = {
            "EXPRESSION_OF": ("AttributeExpression", "BusinessConcept"),
            "APPEARS_IN": ("AttributeExpression", "BusinessContext"),
            "QUALIFIED_BY": ("AttributeExpression", "Qualifier"),
            "RELATED_TO": ("BusinessConcept", "BusinessConcept"),
            "BROADER": ("BusinessConcept", "BusinessConcept"),
            "NARROWER": ("BusinessConcept", "BusinessConcept"),
        }
        if (
            predicate in allowed
            and (object_types[subject], object_types.get(obj)) != allowed[predicate]
        ):
            raise ValueError(f"invalid endpoints for {predicate}")
        if (
            predicate == "IMPLEMENTED_BY"
            and object_types[subject] != "AttributeExpression"
        ):
            raise ValueError("IMPLEMENTED_BY subject must be AttributeExpression")
        if predicate == "IMPLEMENTED_BY" and obj not in technical_ids:
            raise ValueError(f"unknown technical implementation: {obj}")
        for evidence_ref in [
            *assertion.get("evidence_refs", []),
            *assertion.get("counterevidence_refs", []),
        ]:
            if str(evidence_ref) not in evidence_ids:
                raise ValueError(f"unknown assertion evidence: {evidence_ref}")
    assertions_by_triple = {
        (
            str(row["subject_id"]),
            str(row["predicate"]),
            str(row["object_id"]),
        )
        for row in result.assertions
    }
    for relation in result.semantic_relations:
        triple = (
            str(relation["subject_id"]),
            str(relation["predicate"]),
            str(relation["object_id"]),
        )
        if triple not in assertions_by_triple:
            raise ValueError(f"relation has no assertion: {triple}")
    expression_ids = {
        str(x["attribute_expression_id"]) for x in result.attribute_expressions
    }
    for row in result.attribute_expressions:
        parent = row.get("display_parent_expression_id")
        if parent and str(parent) not in expression_ids:
            raise ValueError("dangling expression display parent")


def _require_unique_ids(rows: Sequence[Mapping[str, object]], key: str) -> None:
    values = [str(row[key]) for row in rows]
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate {key}")


def write_context_map_results(
    output_dir: str | Path, result: ContextMapResult, config: ContextMapConfig
) -> dict[str, Path]:
    """Build a complete bundle off-path and publish it as one directory swap."""

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    final_root = output_root / "context-enriched-field-semantic-map"
    staging_parent = Path(
        tempfile.mkdtemp(prefix=".context-map-staging-", dir=output_root)
    )
    backup_root = output_root / ".context-map-previous"
    try:
        staged_paths = _write_context_map_results(staging_parent, result, config)
        staged_root = staging_parent / final_root.name
        if backup_root.exists():
            shutil.rmtree(backup_root)
        if final_root.exists():
            final_root.replace(backup_root)
        try:
            staged_root.replace(final_root)
        except Exception:
            if backup_root.exists() and not final_root.exists():
                backup_root.replace(final_root)
            raise
        if backup_root.exists():
            shutil.rmtree(backup_root)
        return {
            name: final_root / path.relative_to(staged_root)
            for name, path in staged_paths.items()
        }
    finally:
        if staging_parent.exists():
            shutil.rmtree(staging_parent)


def _write_context_map_results(
    output_dir: str | Path, result: ContextMapResult, config: ContextMapConfig
) -> dict[str, Path]:
    from .context_review import write_review_projection

    root = Path(output_dir) / "context-enriched-field-semantic-map"
    protected = {config.field_semantics_dir.resolve(), config.wiki_tree_dir.resolve()}
    if root.resolve() in protected or any(
        parent in root.resolve().parents for parent in protected
    ):
        raise ValueError("output must not be inside an input directory")
    root.mkdir(parents=True, exist_ok=True)
    datasets = {
        "semantic_observations": result.semantic_observations,
        "semantic_hypotheses": result.semantic_hypotheses,
        "review_decisions": result.review_decisions,
        "business_concepts": result.business_concepts,
        "business_contexts": result.business_contexts,
        "attribute_expressions": result.attribute_expressions,
        "qualifiers": result.qualifiers,
        "semantic_relations": result.semantic_relations,
        "assertions": result.assertions,
        "evidence_refs": result.evidence_refs,
    }
    paths: dict[str, Path] = {}
    outputs = []
    for name, rows in datasets.items():
        path = root / f"{name}.jsonl"
        path.write_text(_jsonl(rows), encoding="utf-8")
        paths[name] = path
        outputs.append(
            {
                "logical_name": name,
                "relative_path": path.name,
                "row_count": len(rows),
                "content_sha256": _sha256(path.read_bytes()),
            }
        )
    diag = root / "diagnostics"
    diag.mkdir(exist_ok=True)
    for name, rows in {
        "wiki_semantic_candidates": result.wiki_candidates,
        "data_semantic_candidates": result.data_candidates,
        "semantic_mapping_candidates": result.mapping_candidates,
        "semantic_normalization_candidates": (result.semantic_normalization_candidates),
        "semantic_review_queue": result.semantic_review_queue,
        "diagnostics": result.diagnostics,
    }.items():
        path = diag / f"{name}.jsonl"
        path.write_text(_jsonl(rows), encoding="utf-8")
        paths[name] = path
    review_pack_dir = diag / "semantic_review_packs"
    review_pack_dir.mkdir(exist_ok=True)
    for stale_pack in review_pack_dir.glob("*.json"):
        stale_pack.unlink()
    review_batches = build_review_batches(result.semantic_review_queue)
    for batch in review_batches:
        batch_path = review_pack_dir / f"{batch['batch_id']}.json"
        batch_path.write_text(
            json.dumps(batch, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    paths["semantic_review_packs"] = review_pack_dir
    manifest = {
        "schema_version": "context-enriched-field-semantic-map-v1",
        "run_id": result.run_id,
        "method_id": METHOD_ID,
        "method_version": METHOD_VERSION,
        "config_sha256": config.config_hash,
        "inputs": {
            "field_semantics_dir": str(config.field_semantics_dir),
            "field_semantics_manifest_sha256": config.field_semantics_manifest_sha256,
            "wiki_tree_dir": str(config.wiki_tree_dir),
            "wiki_manifest_sha256": config.wiki_manifest_sha256,
            "wiki_tree_sha256": config.wiki_tree_sha256,
        },
        "limits": {
            "max_wiki_candidates_per_expression": config.max_wiki_candidates_per_expression,
            "max_wiki_candidates_per_concept": config.max_wiki_candidates_per_concept,
            "max_page_body_reads": config.max_page_body_reads,
        },
        "stats": result.stats,
        "quality_gate": result.quality_gate,
        "outputs": outputs,
        "semantic_review": {
            "queue_count": len(result.semantic_review_queue),
            "batch_count": len(review_batches),
            "automatic_write_back": False,
        },
        "business_rows_read": False,
        "llm_mode": "disabled",
        "canonical_write_back": False,
    }
    paths.update(_write_investigation_cards(root, result))
    paths.update(write_review_projection(root, result, config))
    existing = {str(row["relative_path"]) for row in outputs}
    for logical_name, path in sorted(paths.items()):
        relative = path.relative_to(root).as_posix()
        if relative not in existing:
            outputs.append(_artifact_output_record(logical_name, path, root))
    manifest_path = root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths["manifest"] = manifest_path
    return paths


def _artifact_output_record(
    logical_name: str, path: Path, root: Path
) -> dict[str, object]:
    if path.is_file():
        record: dict[str, object] = {
            "logical_name": logical_name,
            "relative_path": path.relative_to(root).as_posix(),
            "content_sha256": _sha256(path.read_bytes()),
            "file_count": 1,
        }
        if path.suffix == ".jsonl":
            record["row_count"] = sum(
                1 for line in path.read_text(encoding="utf-8").splitlines() if line
            )
        return record
    files = sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
    digest = hashlib.sha256()
    for candidate in files:
        digest.update(candidate.relative_to(path).as_posix().encode("utf-8"))
        digest.update(bytes.fromhex(_sha256(candidate.read_bytes())))
    return {
        "logical_name": logical_name,
        "relative_path": path.relative_to(root).as_posix(),
        "content_sha256": digest.hexdigest(),
        "file_count": len(files),
    }


def _map_wiki_candidates(
    run_id,
    data_candidates,
    wiki_candidates,
    contexts,
    assertions,
    relations,
    evidence,
    config,
):
    token_index: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    ngram_index: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for wiki in wiki_candidates:
        for token in _semantic_tokens(str(wiki["normalized_title"])) | _semantic_tokens(
            str(wiki["label"])
        ):
            token_index[token].append(wiki)
        for gram in _semantic_ngrams(str(wiki["normalized_title"])):
            ngram_index[gram].append(wiki)
    mappings = []
    concept_counts: dict[str, int] = defaultdict(int)
    for data in data_candidates:
        tokens = _semantic_tokens(str(data["label"]))
        recalled: dict[str, tuple[Mapping[str, object], set[str]]] = {}
        for token in tokens:
            for wiki in token_index.get(token, []):
                item = recalled.setdefault(str(wiki["candidate_id"]), (wiki, set()))
                item[1].add("LABEL_TOKEN_OVERLAP")
        normalized_label = normalize_title(str(data["label"])).upper()
        if len(normalized_label) >= 2:
            lookup = (
                ngram_index.get(normalized_label, [])
                if len(normalized_label) <= 12
                else token_index.get(normalized_label, [])
            )
            for wiki in lookup:
                if normalized_label in str(wiki["normalized_title"]).upper():
                    item = recalled.setdefault(str(wiki["candidate_id"]), (wiki, set()))
                    item[1].add("EXPRESSION_IN_TITLE")
        ranked = sorted(
            recalled.values(), key=lambda x: (-len(x[1]), str(x[0]["page_id"]))
        )[: config.max_wiki_candidates_per_expression]
        concept_id = str(data["business_concept_id"])
        remaining = max(
            0,
            config.max_wiki_candidates_per_concept - concept_counts[concept_id],
        )
        for wiki, signals in ranked[:remaining]:
            ev_id = str(wiki["evidence_ref"])
            evidence.setdefault(
                ev_id,
                {
                    "evidence_id": ev_id,
                    "evidence_type": "WIKI_TREE_PATH",
                    "source_ref": ev_id,
                    "label": wiki["title"],
                    "ancestor_path": wiki["ancestor_path"],
                },
            )
            mapping_id = _stable_id(
                "mapping", run_id, str(data["candidate_id"]), str(wiki["candidate_id"])
            )
            mappings.append(
                {
                    "mapping_id": mapping_id,
                    "data_candidate_id": data["candidate_id"],
                    "wiki_candidate_id": wiki["candidate_id"],
                    "relation_candidate": "CONTEXT_SUPPORTS_EXPRESSION",
                    "signals": sorted(signals),
                    "counterevidence": [],
                    "method_score": 1.0,
                    "status": "CANDIDATE",
                    "review_status": "UNREVIEWED",
                    "evidence_refs": [ev_id],
                }
            )
            concept_counts[concept_id] += 1
            products = _matched_mapping(
                " > ".join(
                    [*map(str, wiki.get("ancestor_path", [])), str(wiki["title"])]
                ),
                config.products,
            )
            for product in products:
                context_id = _stable_id(
                    "business-context", run_id, f"PRODUCT:{product}"
                )
                contexts.setdefault(
                    context_id,
                    {
                        "business_context_id": context_id,
                        "context_type": "PRODUCT",
                        "label": product,
                        "status": "CANDIDATE",
                        "source_hints": [ev_id],
                    },
                )
                _add_assertion(
                    assertions,
                    relations,
                    run_id,
                    str(data["attribute_expression_id"]),
                    "APPEARS_IN",
                    context_id,
                    [ev_id],
                    1.0,
                )
    return mappings


def _context_hints(members, config):
    found: dict[str, tuple[str, str, set[str]]] = {}
    for field, _ in members:
        text = f"{field.get('object_name', '')} {field.get('column_name', '')} {field.get('column_comment', '')}"
        matched = _matched_mapping(text, config.products)
        for product in matched:
            key = f"PRODUCT:{product}"
            found.setdefault(key, ("PRODUCT", product, set()))[2].add(
                str(field["column_id"])
            )
    if not found:
        found["UNKNOWN"] = (
            "UNKNOWN",
            "上下文未确认",
            {str(field["column_id"]) for field, _ in members},
        )
    return [
        (key, kind, label, refs) for key, (kind, label, refs) in sorted(found.items())
    ]


def _observed_field_expression_label(
    concept_label,
    field,
    binding,
    expressions_by_ref,
):
    """Return one observed semantic expression, preferring the Chinese comment."""

    candidates: list[tuple[str, str]] = []
    comment = str(field.get("column_comment") or "").strip()
    if comment:
        candidates.append((comment, "COLUMN_COMMENT"))
    for source_ref in binding.get("source_refs", [field["column_id"]]):
        for expression in expressions_by_ref.get(str(source_ref), []):
            text = str(expression.get("original_text", "")).strip()
            if text:
                candidates.append((text, "SOURCE_EXPRESSION"))
    inherited_comment = str(field.get("semantic_comment") or "").strip()
    if inherited_comment:
        candidates.append((inherited_comment, "INHERITED_COMMENT"))
    for value, provenance in candidates:
        cleaned = _clean_expression_label(value)
        if cleaned and concept_label in cleaned:
            return cleaned, provenance
    for value, provenance in candidates:
        cleaned = _clean_expression_label(value)
        if cleaned:
            return cleaned, provenance
    return concept_label, "CONCEPT_FALLBACK"


def _normalize_physical_field_name(value: object) -> str:
    """Return a cross-schema key without changing the stored physical name."""

    return str(value or "").strip().strip('"').upper()


def _column_comment_consensus(
    fields: Sequence[Mapping[str, object]],
    facets_by_binding: Mapping[str, Sequence[Mapping[str, object]]] | None = None,
    axis_mappings: Mapping[str, Mapping[str, str]] | None = None,
) -> dict[
    tuple[str, str, tuple[tuple[str, str], ...]],
    dict[str, object],
]:
    """Find uniquely agreed comments for repeated physical field names.

    A consensus is deliberately absent when a name has multiple normalized
    comments.  Callers may use the result as candidate semantic evidence, but
    must not write it back into the source ``column_comment``.
    """

    facets_by_binding = facets_by_binding or {}
    comments_by_key: dict[
        tuple[str, str, tuple[tuple[str, str], ...]],
        dict[str, set[str]],
    ] = defaultdict(lambda: defaultdict(set))
    display_by_key: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for field in fields:
        name = _normalize_physical_field_name(field.get("column_name"))
        raw_comment = str(field.get("column_comment") or "").strip()
        if not name or not raw_comment:
            continue
        normalized_comment = _lossless_comment_key(raw_comment)
        if not normalized_comment:
            continue
        direct_bindings = [
            binding
            for binding in field.get("candidate_bindings", [])
            if binding.get("relation_kind") == "EXPRESSES"
        ]
        for binding in direct_bindings:
            concept_id = str(binding["concept_id"])
            signature, _ = _resolve_facet_signature(
                facets_by_binding.get(str(binding.get("binding_id", "")), []),
                axis_mappings or {},
            )
            signature = _augment_observed_qualifiers(raw_comment, signature)
            key = (name, concept_id, signature)
            comments_by_key[key][normalized_comment].add(str(field["column_id"]))
            display_by_key[key].setdefault(normalized_comment, normalized_comment)

    consensus: dict[
        tuple[str, str, tuple[tuple[str, str], ...]],
        dict[str, object],
    ] = {}
    for key, comments in sorted(comments_by_key.items()):
        if len(comments) != 1:
            continue
        normalized_comment, refs = next(iter(comments.items()))
        consensus[key] = {
            "label": display_by_key[key][normalized_comment],
            "source_refs": sorted(refs),
        }
    return consensus


def _lossless_comment_key(value: object) -> str:
    """Normalize spacing/case while retaining business qualifiers and punctuation."""

    text = _SPACE.sub(" ", str(value or "")).strip()
    return re.sub(
        r"[A-Za-z][A-Za-z0-9_]*",
        lambda match: match.group(0).upper(),
        text,
    )


def _augment_observed_qualifiers(
    label: object,
    signature: tuple[tuple[str, str], ...],
) -> tuple[tuple[str, str], ...]:
    """Add general qualifier evidence expressed in the observed field label."""

    augmented = set(signature)
    text = str(label or "").upper()
    if "绝对" in text or "ABSOLUTE" in text:
        augmented.add(("measure_basis", "ABSOLUTE"))
    return tuple(sorted(augmented))


def _clean_expression_label(value):
    value = _PARENS.sub("", value)
    value = value.split("，", 1)[0].split(",", 1)[0]
    value = value.split("；", 1)[0].split(";", 1)[0]
    value = _SPACE.sub(" ", value).strip(" .;；")
    # Normalize common identifier suffixes without changing their business core.
    value = re.sub(r"(?i)\s*id$", "ID", value)
    value = re.sub(r"(?i)\s*uuid$", "UUID", value)
    value = re.sub(r"(?i)\s*url$", "URL", value)
    value = re.sub(
        r"[A-Za-z][A-Za-z0-9_]*",
        lambda match: match.group(0).upper(),
        value,
    )
    return value


def _canonicalize_identifier_label(value: object) -> str:
    """Normalize language-level identifier aliases without changing the core."""

    text = str(value or "").strip()
    return re.sub(r"(?:编号|编码|(?i:ID))$", "ID", text)


def _has_identifier_suffix(value: object) -> bool:
    return bool(re.search(r"(?:编号|编码|(?i:ID))$", str(value or "").strip()))


def _semantic_label_compatible(
    business_concept_label: object,
    observed_label: object,
    *,
    identifier: bool = False,
    qualifier_signature: Sequence[tuple[str, str]] = (),
    axis_mappings: Mapping[str, Mapping[str, str]] | None = None,
) -> bool:
    """Return whether direct Chinese semantic evidence supports its base concept.

    English-only expressions remain provisional because this projection cannot
    prove a bilingual alias by spelling alone.  Chinese-to-Chinese disagreement
    is stronger counterevidence and must be exposed instead of silently wrapped
    as an expression of an unrelated base concept.
    """

    concept = _clean_expression_label(str(business_concept_label or ""))
    observed = _clean_expression_label(str(observed_label or ""))
    if identifier or (
        _has_identifier_suffix(concept) and _has_identifier_suffix(observed)
    ):
        concept = _canonicalize_identifier_label(concept)
        observed = _canonicalize_identifier_label(observed)
        if identifier and observed.endswith("ID") and observed[:-2] == concept:
            return True
    if not concept or not observed:
        return True
    chinese = re.compile(r"[\u3400-\u9fff]")
    if not chinese.search(concept) or not chinese.search(observed):
        return True
    if concept == observed:
        return True
    reduced = observed
    for item in qualifier_signature:
        normalized_item = _normalize_qualifier_axis(
            *item, axis_mappings=axis_mappings or {}
        )
        token = _QUALIFIER_ZH.get(normalized_item)
        if token:
            reduced = reduced.replace(token, "")
    if reduced == concept:
        return True
    if concept not in observed:
        return False
    # A bare substring is only an investigation lead.  Without Facet evidence
    # explaining the residual text, keep it as counterevidence.
    return False


def _normalize_qualifier_axis(
    dimension: object,
    value: object,
    *,
    axis_mappings: Mapping[str, Mapping[str, str]],
) -> tuple[str, str]:
    """Separate orthogonal meanings that upstream Facets stored on one axis."""

    normalized_dimension = str(dimension)
    normalized_value = str(value)
    target_axis = axis_mappings.get(normalized_dimension, {}).get(normalized_value)
    return target_axis or normalized_dimension, normalized_value


def _remove_redundant_qualifiers(
    business_concept_label: object,
    observed_label: object,
    signature: tuple[tuple[str, str], ...],
) -> tuple[tuple[str, str], ...]:
    """Avoid duplicate expressions when the base label already states the role."""

    concept = _clean_expression_label(str(business_concept_label or ""))
    observed = _clean_expression_label(str(observed_label or ""))
    comparison_observed = observed
    if ("attribute_kind", "IDENTIFIER") in signature:
        comparison_observed = re.sub(
            r"(?:编号|编码|(?i:ID))$", "", comparison_observed
        )
    if concept != comparison_observed:
        return signature
    return tuple(
        item
        for item in signature
        if not (
            item in _QUALIFIER_ZH
            and _QUALIFIER_ZH[item]
            and _QUALIFIER_ZH[item] in concept
        )
    )


def _deduplicate_conflicts(
    conflicts: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Keep conflict diagnostics deterministic without repeating member evidence."""

    unique: dict[str, dict[str, object]] = {}
    for conflict in conflicts:
        row = dict(conflict)
        key = json.dumps(row, ensure_ascii=False, sort_keys=True)
        unique.setdefault(key, row)
    return [unique[key] for key in sorted(unique)]


def _conflict_source_refs(conflict: Mapping[str, object]) -> list[str]:
    """Extract direct and nested source references from one conflict record."""

    refs = {str(conflict.get("source_ref") or "").strip()}
    for item in conflict.get("evidence", []):
        if isinstance(item, Mapping):
            refs.add(str(item.get("source_ref") or "").strip())
    return sorted(ref for ref in refs if ref)


_QUALIFIER_ZH = {
    ("currency_basis", "LOCAL_CURRENCY"): "本币",
    ("currency_basis", "ORIGINAL_CURRENCY"): "原币",
    ("currency_basis", "UNDERLYING_CURRENCY"): "标的币种",
    ("currency_basis", "SETTLEMENT_CURRENCY"): "结算币种",
    ("position_side", "LONG"): "多头",
    ("position_side", "SHORT"): "空头",
    ("trade_side", "BUY"): "买方",
    ("trade_side", "SELL"): "卖方",
    ("cashflow_direction", "PAY"): "支付",
    ("cashflow_direction", "RECEIVE"): "收取",
    ("flow_side", "SOURCE"): "源侧",
    ("flow_side", "TARGET"): "目标",
    ("party_role", "COUNTERPARTY"): "交易对手",
    ("party_role", "CLIENT"): "客户",
    ("party_role", "INTERNAL"): "内部",
    ("temporal_stage", "INITIAL"): "初始",
    ("temporal_stage", "CURRENT"): "当前",
    ("temporal_stage", "END"): "期末",
    ("temporal_stage", "BEFORE_ADJUSTMENT"): "调整前",
    ("temporal_stage", "AFTER_ADJUSTMENT"): "调整后",
    ("variability", "DYNAMIC"): "动态",
    ("variability", "FIXED"): "固定",
    ("availability_state", "AVAILABLE"): "可用",
    ("availability_state", "FROZEN"): "冻结",
    ("estimation_status", "ESTIMATED"): "预估",
    ("aggregation_state", "ACCUMULATED"): "累计",
    ("lifecycle_stage", "CLEARING"): "清算",
    ("lifecycle_stage", "EXECUTION"): "成交",
    ("lifecycle_stage", "ORDER"): "委托",
    ("lifecycle_stage", "POSITION"): "持仓",
    ("lifecycle_stage", "TERMINATION"): "终止",
    ("measure_basis", "ABSOLUTE"): "绝对",
}


def _display_expression_label(label, signature):
    """Disambiguate equal observed labels without inventing a new expression."""
    missing = [
        _QUALIFIER_ZH[item]
        for item in signature
        if item in _QUALIFIER_ZH and _QUALIFIER_ZH[item] not in label
    ]
    return f"{label}（{'、'.join(missing)}）" if missing else label


def _qualifier_conflicts(signature):
    values: dict[str, set[str]] = defaultdict(set)
    for dimension, value in signature:
        values[dimension].add(value)
    # Some dimensions (for example AVAILABLE + DYNAMIC state) are composable.
    exclusive = {
        "position_side",
        "trade_side",
        "cashflow_direction",
        "currency_basis",
        "temporal_stage",
        "party_role",
        "flow_side",
        "variability",
        "availability_state",
        "estimation_status",
    }
    return [
        {"dimension": dimension, "values": sorted(items)}
        for dimension, items in sorted(values.items())
        if dimension in exclusive and len(items) > 1
    ]


def _resolve_facet_signature(
    facets,
    axis_mappings: Mapping[str, Mapping[str, str]],
):
    """Prefer Chinese comment semantics while retaining name disagreement as counterevidence."""
    by_dimension: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for facet in facets:
        dimension, value = _normalize_qualifier_axis(
            facet["dimension"],
            facet["value"],
            axis_mappings=axis_mappings,
        )
        by_dimension[dimension].append(
            {**facet, "dimension": dimension, "value": value}
        )
    signature: list[tuple[str, str]] = []
    conflicts: list[dict[str, object]] = []
    exclusive = {
        "position_side",
        "trade_side",
        "cashflow_direction",
        "currency_basis",
        "temporal_stage",
        "party_role",
        "flow_side",
        "variability",
        "availability_state",
        "estimation_status",
    }
    for dimension, rows in sorted(by_dimension.items()):
        values = {str(row["value"]) for row in rows}
        if dimension not in exclusive or len(values) <= 1:
            signature.extend((dimension, value) for value in sorted(values))
            continue
        comment_rows = [
            row
            for row in rows
            if re.search(r"[\u3400-\u9fff]", str(row.get("raw_fragment", "")))
        ]
        chosen = sorted({str(row["value"]) for row in comment_rows} or values)
        # If the comment itself is ambiguous, retain all values; otherwise it wins.
        signature.extend((dimension, value) for value in chosen)
        conflicts.append(
            {
                "dimension": dimension,
                "chosen_values": chosen,
                "all_values": sorted(values),
                "reason": "COMMENT_NAME_DISAGREEMENT"
                if comment_rows
                else "SAME_SOURCE_DISAGREEMENT",
                "evidence": [
                    {
                        "value": str(row["value"]),
                        "raw_fragment": str(row.get("raw_fragment", "")),
                        "source_ref": row.get("source_ref"),
                    }
                    for row in rows
                ],
            }
        )
    return tuple(signature), conflicts


def _partition_facet_signature(
    observed_label: object,
    column_name: object,
    signature: tuple[tuple[str, str], ...],
    facet_rows: Sequence[Mapping[str, object]] = (),
) -> tuple[
    tuple[tuple[str, str], ...],
    tuple[tuple[str, str], ...],
]:
    """Separate expression-defining facets from incidental context hints.

    Lifecycle facets are especially prone to being inferred from explanatory
    notes.  They define an expression only when their lexical marker is also
    present in the observed expression or physical field name.  Other facet
    dimensions retain their established V2 behavior.
    """

    text = f"{observed_label or ''} {column_name or ''}".upper()
    identity: list[tuple[str, str]] = []
    contextual: list[tuple[str, str]] = []
    rows_by_item: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in facet_rows:
        rows_by_item[(str(row.get("dimension")), str(row.get("value")))].append(row)
    for item in signature:
        dimension, value = item
        markers = _lexical_markers(value, rows_by_item.get(item, []))
        if dimension == "lifecycle_stage":
            target = (
                identity if any(marker in text for marker in markers) else contextual
            )
            target.append(item)
            continue
        identity.append(item)
    return tuple(sorted(identity)), tuple(sorted(contextual))


def _lexical_markers(
    value: object,
    facet_rows: Sequence[Mapping[str, object]],
) -> set[str]:
    """Derive lexical evidence from the configured facet value and raw fragments."""

    markers = {str(value or "").strip().upper()}
    for row in facet_rows:
        raw = str(row.get("raw_fragment") or "").strip().upper()
        if raw:
            markers.add(raw)
    return {marker for marker in markers if len(marker) >= 2}


def _expression_tree(rows, concepts):
    concept_labels = {
        str(row["business_concept_id"]): str(row["label"]) for row in concepts
    }
    by_concept: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        by_concept[str(row["business_concept_id"])].append(row)
    parents = {}
    for concept_id, group in by_concept.items():
        base_label = concept_labels.get(concept_id, "")
        sig = {
            str(r["attribute_expression_id"]): frozenset(
                (q["dimension"], q["value"]) for q in r["qualifier_signature"]
            )
            for r in group
        }
        for row in group:
            child_id = str(row["attribute_expression_id"])
            child = sig[child_id]
            if str(row["label"]) == base_label:
                parents[child_id] = None
                continue
            options = [
                (
                    len(parent_sig),
                    int(str(parent_row["label"]) == base_label),
                    int(str(parent_row["label"]) in str(row["label"])),
                    -len(str(parent_row["label"])),
                    parent_id,
                )
                for parent_id, parent_sig in sig.items()
                for parent_row in group
                if str(parent_row["attribute_expression_id"]) == parent_id
                if parent_id != child_id and parent_sig < child
                if parent_sig or str(parent_row["label"]) == base_label
            ]
            if options:
                parents[child_id] = max(options)[4]
                continue
            canonical_root = next(
                (
                    str(candidate["attribute_expression_id"])
                    for candidate in group
                    if str(candidate["label"]) == base_label
                ),
                None,
            )
            parents[child_id] = canonical_root
    return parents


def _quality_gate(result, config):
    id_sets = [
        (result.business_concepts, "business_concept_id"),
        (result.business_contexts, "business_context_id"),
        (result.attribute_expressions, "attribute_expression_id"),
        (result.qualifiers, "qualifier_id"),
        (result.assertions, "assertion_id"),
        (result.semantic_relations, "relation_id"),
        (result.evidence_refs, "evidence_id"),
        (result.semantic_observations, "observation_id"),
        (result.semantic_hypotheses, "hypothesis_id"),
    ]
    unique_ids = all(
        len(rows) == len({str(row[key]) for row in rows}) for rows, key in id_sets
    )
    evidence_ids = {str(row["evidence_id"]) for row in result.evidence_refs}
    observation_by_id = {
        str(row["observation_id"]): row for row in result.semantic_observations
    }
    evidence_resolved = all(
        str(ref) in evidence_ids
        for assertion in result.assertions
        for ref in [
            *assertion.get("evidence_refs", []),
            *assertion.get("counterevidence_refs", []),
        ]
    )
    expression_ids = {
        str(row["attribute_expression_id"]) for row in result.attribute_expressions
    }
    expressions_by_id = {
        str(row["attribute_expression_id"]): row
        for row in result.attribute_expressions
    }
    context_subjects = {
        str(row["subject_id"])
        for row in result.assertions
        if row["predicate"] == "APPEARS_IN"
    }
    hashes_present = all(
        value and re.fullmatch(r"[0-9a-f]{64}", value)
        for value in (
            config.config_hash,
            config.field_semantics_manifest_sha256,
            config.wiki_manifest_sha256,
            config.wiki_tree_sha256,
        )
    )
    published_hypothesis_ids = {
        str(row["proposed_attribute_expression_id"])
        for row in result.semantic_hypotheses
        if row["publication_status"] == "PUBLISHED"
    }
    unpublished_hypothesis_ids = {
        str(row["proposed_attribute_expression_id"])
        for row in result.semantic_hypotheses
        if row["publication_status"] != "PUBLISHED"
    }
    checks = {
        "unique_object_and_assertion_ids": unique_ids,
        "assertion_evidence_resolved": evidence_resolved,
        "hypothesis_observations_resolved": all(
            row.get("observation_refs")
            and all(str(ref) in observation_by_id for ref in row["observation_refs"])
            and {str(ref) for ref in row.get("field_refs", [])}
            == {
                str(observation_by_id[str(ref)]["column_id"])
                for ref in row["observation_refs"]
            }
            for row in result.semantic_hypotheses
        ),
        "hypothesis_evidence_resolved": all(
            row.get("method_id") == METHOD_ID
            and all(
                str(ref) in evidence_ids
                for ref in [
                    *row.get("evidence_refs", []),
                    *row.get("counterevidence_refs", []),
                ]
            )
            for row in result.semantic_hypotheses
        ),
        "no_unobserved_expression_cartesian_product": all(
            int(x["field_count"]) > 0 for x in result.attribute_expressions
        ),
        "navigation_not_published_as_broader": not any(
            x["predicate"] in {"BROADER", "NARROWER"} for x in result.assertions
        ),
        "every_expression_has_context_or_unknown": expression_ids <= context_subjects,
        "source_qualifier_conflicts_exposed": all(
            row["status"] == "CONFLICT"
            for row in result.attribute_expressions
            if row.get("conflicts")
        ),
        "unreviewed_corpus_modifiers_not_published": not any(
            row.get("dimension") == "semantic_modifier"
            for row in result.qualifiers
        ),
        "orthogonal_qualifier_axes_published": not any(
            row.get("dimension") in {"direction", "measure_state"}
            or (
                row.get("dimension") == "party_role"
                and row.get("value") in {"SOURCE", "TARGET"}
            )
            for row in result.qualifiers
        ),
        "semantic_counterevidence_exposed": all(
            expressions_by_id[str(row["subject_id"])]["status"] == "CONFLICT"
            and bool(row.get("counterevidence_refs"))
            for row in result.assertions
            if row["predicate"] == "EXPRESSION_OF"
            and str(row["subject_id"]) in expressions_by_id
            and expressions_by_id[str(row["subject_id"])]["status"]
            == "CONFLICT"
        ),
        "conflicted_qualifier_relations_exposed": all(
            row["status"] == "CONFLICT" and bool(row.get("counterevidence_refs"))
            for row in result.assertions
            if row["predicate"] == "QUALIFIED_BY"
            and str(row["subject_id"]) in expressions_by_id
            and expressions_by_id[str(row["subject_id"])]["status"]
            == "CONFLICT"
        ),
        "replay_inputs_hashed": bool(hashes_present),
        "published_projection_matches_publication_decisions": (
            expression_ids == published_hypothesis_ids
            and not expression_ids.intersection(unpublished_hypothesis_ids)
        ),
        "source_to_publication_boundary_independent": all(
            (
                row["status"] == "CANDIDATE"
                and not row.get("conflicts")
                and not row.get("uncertainties")
                and not row.get("counterevidence_refs")
            )
            if row["publication_status"] == "PUBLISHED"
            else (
                row["status"] in {"CONFLICT", "INSUFFICIENT_EVIDENCE"}
                and bool(row.get("conflicts") or row.get("uncertainties"))
            )
            for row in result.semantic_hypotheses
        ),
        "unpublished_hypotheses_retained_for_review": all(
            row.get("publication_reason")
            and row.get("field_refs")
            for row in result.semantic_hypotheses
            if row["publication_status"] != "PUBLISHED"
        ),
        "qualifier_axis_registry_versioned": bool(
            config.qualifier_axis_version and config.qualifier_axis_mappings
        ),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "boundary": "information-model gate only; not business acceptance",
    }


def _write_investigation_cards(root, result):
    review = root / "review"
    review.mkdir(exist_ok=True)
    concepts = {str(x["business_concept_id"]): x for x in result.business_concepts}
    contexts = {str(x["business_context_id"]): x for x in result.business_contexts}
    relations_by_subject: dict[str, list[dict[str, object]]] = defaultdict(list)
    relations_by_object: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in result.semantic_relations:
        relations_by_subject[str(row["subject_id"])].append(row)
        relations_by_object[str(row["object_id"])].append(row)
    data_by_expression = {
        str(row["attribute_expression_id"]): row for row in result.data_candidates
    }
    wiki_by_id = {str(row["candidate_id"]): row for row in result.wiki_candidates}
    mapping_by_expression: dict[str, list[dict[str, object]]] = defaultdict(list)
    data_id_to_expression = {
        str(row["candidate_id"]): str(row["attribute_expression_id"])
        for row in result.data_candidates
    }
    for row in result.mapping_candidates:
        expression_id = data_id_to_expression.get(str(row["data_candidate_id"]))
        if expression_id:
            mapping_by_expression[expression_id].append(row)
    cards = []
    for concept in result.business_concepts:
        expressions = [
            x
            for x in result.attribute_expressions
            if x["business_concept_id"] == concept["business_concept_id"]
        ]
        if not expressions:
            continue
        expression_cards = []
        all_assets = set()
        for expression in expressions:
            expression_id = str(expression["attribute_expression_id"])
            data = data_by_expression.get(expression_id, {})
            instances = data.get("physical_instances", [])
            all_assets.update(str(row["asset_id"]) for row in instances)
            context_labels = [
                contexts[str(row["object_id"])]["label"]
                for row in relations_by_subject.get(expression_id, [])
                if row["predicate"] == "APPEARS_IN"
                and str(row["object_id"]) in contexts
            ]
            wiki_rows = []
            for mapping in mapping_by_expression.get(expression_id, []):
                candidate = wiki_by_id.get(str(mapping["wiki_candidate_id"]))
                if candidate:
                    wiki_rows.append(
                        {
                            "page_id": candidate["page_id"],
                            "title": candidate["title"],
                            "ancestor_path": candidate.get("ancestor_path", []),
                        }
                    )
            expression_cards.append(
                {
                    **expression,
                    "contexts": sorted(set(context_labels)),
                    "physical_expressions": data.get("physical_expressions", []),
                    "physical_instances": instances,
                    "wiki_evidence": wiki_rows[:8],
                }
            )
        concept_id = str(concept["business_concept_id"])
        related = set()
        for relation in relations_by_subject.get(
            concept_id, []
        ) + relations_by_object.get(concept_id, []):
            if relation["predicate"] != "RELATED_TO":
                continue
            other_id = str(
                relation["object_id"]
                if str(relation["subject_id"]) == concept_id
                else relation["subject_id"]
            )
            if other_id in concepts:
                related.add(str(concepts[other_id]["label"]))
        cards.append(
            {
                "business_concept_id": concept["business_concept_id"],
                "label": concept["label"],
                "field_count": sum(int(x["field_count"]) for x in expressions),
                "object_count": len(all_assets),
                "related_concepts": sorted(related),
                "expressions": expression_cards,
            }
        )
    cards.sort(key=lambda x: (-int(x["field_count"]), str(x["label"])))
    json_path = review / "investigation-cards.json"
    json_path.write_text(
        json.dumps(cards, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    selected = [
        next((x for x in cards if x["label"] == label), None)
        for label in ("名义本金", "交易对手")
    ]
    selected = [row for row in selected if row]
    lines = [
        "# 字段语义调查卡",
        "",
        "字段及中文注释是主数据源；Wiki 目录仅作辅助上下文证据。",
        "",
    ]
    for card in selected:
        lines.extend(
            [
                f"## {card['label']}",
                "",
                f"- 直接字段：{card['field_count']}",
                f"- 涉及表：{card['object_count']}",
                f"- 属性表达：{len(card['expressions'])}",
                f"- 相关概念：{'、'.join(card['related_concepts']) or '暂无'}",
                "",
                "| 属性表达 | 限定 | 上下文 | 物理表达 | 字段 | 表 | 状态 |",
                "|---|---|---|---|---:|---:|---|",
            ]
        )
        for expr in sorted(
            card["expressions"],
            key=lambda x: (len(x["qualifier_signature"]), str(x["label"])),
        ):
            qualifiers = (
                "、".join(
                    f"{q['dimension']}={q['value']}"
                    for q in expr["qualifier_signature"]
                )
                or "—"
            )
            lines.append(
                f"| {expr['label']} | {qualifiers} | {'、'.join(expr['contexts']) or '未确认'} | "
                f"{'、'.join(expr['physical_expressions']) or '—'} | {expr['field_count']} | "
                f"{expr['object_count']} | {expr['status']} |"
            )
        lines.append("")
    md_path = review / "investigation-card.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"investigation_cards": json_path, "investigation_card": md_path}


def _add_assertion(
    assertions,
    relations,
    run_id,
    subject,
    predicate,
    obj,
    evidence_refs,
    score,
    *,
    counterevidence_refs=(),
    status="CANDIDATE",
):
    assertion_id = _stable_id("assertion", run_id, subject, predicate, obj)
    relation = {
        "relation_id": _stable_id("relation", subject, predicate, obj),
        "subject_id": subject,
        "predicate": predicate,
        "object_id": obj,
    }
    relations.append(relation)
    assertions.append(
        {
            "assertion_id": assertion_id,
            **{k: relation[k] for k in ("subject_id", "predicate", "object_id")},
            "status": status,
            "method_id": METHOD_ID,
            "method_score": score,
            "evidence_refs": sorted(set(evidence_refs)),
            "counterevidence_refs": sorted(set(counterevidence_refs)),
            "review_status": "UNREVIEWED",
        }
    )


def _consolidate_assertions(assertions, relations):
    """Merge repeated support for one semantic triple without losing evidence."""

    merged: dict[str, dict[str, object]] = {}
    for assertion in assertions:
        assertion_id = str(assertion["assertion_id"])
        if assertion_id not in merged:
            merged[assertion_id] = dict(assertion)
            merged[assertion_id]["evidence_refs"] = list(
                assertion.get("evidence_refs", [])
            )
            merged[assertion_id]["counterevidence_refs"] = list(
                assertion.get("counterevidence_refs", [])
            )
            continue
        current = merged[assertion_id]
        for key in ("subject_id", "predicate", "object_id"):
            if current[key] != assertion[key]:
                raise ValueError(f"assertion id collision: {assertion_id}")
        current["evidence_refs"] = sorted(
            {
                *map(str, current.get("evidence_refs", [])),
                *map(str, assertion.get("evidence_refs", [])),
            }
        )
        current["counterevidence_refs"] = sorted(
            {
                *map(str, current.get("counterevidence_refs", [])),
                *map(str, assertion.get("counterevidence_refs", [])),
            }
        )
        current["method_score"] = max(
            float(current.get("method_score", 0.0)),
            float(assertion.get("method_score", 0.0)),
        )
        status_priority = {
            "REJECTED": 5,
            "CONFLICT": 4,
            "INSUFFICIENT_EVIDENCE": 3,
            "CONFIRMED": 2,
            "CANDIDATE": 1,
        }
        current_status = str(current.get("status", "CANDIDATE"))
        incoming_status = str(assertion.get("status", "CANDIDATE"))
        current["status"] = max(
            (current_status, incoming_status),
            key=lambda value: status_priority.get(value, 0),
        )

    unique_relations: dict[str, dict[str, object]] = {}
    for relation in relations:
        relation_id = str(relation["relation_id"])
        if (
            relation_id in unique_relations
            and unique_relations[relation_id] != relation
        ):
            raise ValueError(f"relation id collision: {relation_id}")
        unique_relations[relation_id] = dict(relation)
    return (
        sorted(merged.values(), key=lambda row: str(row["assertion_id"])),
        sorted(unique_relations.values(), key=lambda row: str(row["relation_id"])),
    )


def _ancestor_path(row, by_id):
    path = []
    seen = set()
    current = row
    while current:
        pid = str(current["page_id"])
        if pid in seen:
            return list(reversed(path)), True
        seen.add(pid)
        path.append(str(current["title"]))
        parent = current.get("parent_page_id")
        current = by_id.get(str(parent)) if parent else None
    return list(reversed(path)), False


def _matched_mapping(text, mapping):
    upper = text.upper()
    return sorted(
        key
        for key, patterns in mapping.items()
        if any(pattern.upper() in upper for pattern in patterns)
    )


def _matched_terms(text, terms):
    upper = text.upper()
    return sorted(term for term in terms if term.upper() in upper)


def _semantic_tokens(value):
    normalized = normalize_title(value).upper()
    tokens = set(re.findall(r"[A-Z]{2,}|[\u3400-\u9fff]{2,}", normalized))
    for marker in ("指引", "方案", "设计", "测试", "验收", "列表", "管理", "系统"):
        tokens = {x.replace(marker, "") for x in tokens if x.replace(marker, "")}
    return tokens


def _semantic_ngrams(value, minimum=2, maximum=12):
    normalized = re.sub(r"\s+", "", normalize_title(value).upper())
    grams = set()
    for size in range(minimum, min(maximum, len(normalized)) + 1):
        grams.update(
            normalized[index : index + size]
            for index in range(len(normalized) - size + 1)
        )
    return grams


def _mapping(raw, key):
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a mapping")
    return value


def _strings(value):
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise ValueError("expected a string list")
    return tuple(value)


def _patterns(value):
    return {str(k): _strings(v) for k, v in value.items()}


def _positive_int(raw, key):
    value = int(raw[key])
    if value <= 0:
        raise ValueError(f"{key} must be positive")
    return value


def _nonnegative_int(raw, key):
    value = int(raw[key])
    if value < 0:
        raise ValueError(f"{key} must be nonnegative")
    return value


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path):
    return [
        json.loads(x)
        for x in path.read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]


def _require_hash(path, expected):
    actual = _sha256(path.read_bytes())
    if actual != expected:
        raise ValueError(f"input hash drift: {path}: expected {expected}, got {actual}")


def _stable_id(prefix, *parts):
    return f"{prefix}-" + _sha256("\x1f".join(parts).encode("utf-8"))[:20]


def _sha256(value):
    return hashlib.sha256(value).hexdigest()


def _jsonl(rows):
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    )
