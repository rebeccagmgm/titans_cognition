"""Deterministic faceted field semantic index built from physical metadata."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import re
import unicodedata
import math
from typing import Mapping, Sequence

import yaml

from .extract import PhysicalFacts


METHOD_ID = "field_semantics.faceted_index.v2"
METHOD_VERSION = "v2"
OUTCOMES = {"SINGLE_CANDIDATE", "COMPETING", "UNKNOWN"}
SUPPORT_STATUSES = {"SUPPORTED", "PROVISIONAL"}
SEMANTIC_SCOPES = {"DOMAIN", "TECHNICAL", "UNRESOLVED"}
EXPRESSION_KINDS = {"SOURCE_EXPRESSION", "ALIAS", "VARIANT"}

_NUMERIC_SUFFIX = re.compile(r"\d+$")
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z])(?=[A-Z])")
_CONNECTORS = re.compile(r"[_\-./\\:;|]+")
_SPACES = re.compile(r"\s+")
_VALUE_DOMAIN = re.compile(
    r"(?:^|[，,;；\s])(?:\d+\s*[^\d，,;；\s]{1,12}\s*){2,}$",
    re.IGNORECASE,
)
_DATE_FORMAT = re.compile(
    r"\b(?:YYYY|YY|MM|DD|HH24|HH|MI|SS){2,}\b", re.IGNORECASE
)
_UNIT = re.compile(r"(?:单位\s*[：:]?\s*)([\w万亿元股份手%％]+)", re.IGNORECASE)
_CURRENCY = re.compile(r"\b(?:CNY|RMB|USD|HKD|EUR|JPY|GBP)\b", re.IGNORECASE)
_PRECISION = re.compile(r"\b(?:NUMBER|DECIMAL|NUMERIC)\s*\(\s*\d+\s*,\s*\d+\s*\)", re.IGNORECASE)
_PAREN = re.compile(r"[（(]([^()（）]{1,80})[）)]")
_CHINESE = re.compile(r"[\u3400-\u9fff]+")
_ENGLISH = re.compile(r"[A-Za-z]+|\d+")
_LOW_INFORMATION = {
    "FIELD", "VALUE", "DATA", "INFO", "X", "Y", "Z", "字段", "值", "信息",
}
_TECH_SUFFIXES = {
    "ID", "CODE", "TYPE", "STATUS", "FLAG", "NAME", "NUMBER", "NO",
}


@dataclass(frozen=True)
class NormalizedExpression:
    original_text: str
    normalized_text: str
    tokens: tuple[str, ...]


@dataclass(frozen=True)
class BaselineReference:
    path: Path
    hashes: Mapping[str, str]


@dataclass(frozen=True)
class FieldSemanticConfig:
    source_text: str
    config_hash: str
    schemas: tuple[str, ...]
    object_types: tuple[str, ...]
    exclude_numeric_suffix: bool
    expected_object_count: int
    expected_excluded_count: int
    expected_field_count: int
    baselines: Mapping[str, BaselineReference]
    min_fields: int
    require_cross_object_or_multi_expression: bool
    max_competing_candidates: int
    max_approximate_neighbors: int
    max_approximate_pairs: int
    min_approximate_similarity: float
    review_page_size: int
    initial_concept_limit: int
    abbreviations: Mapping[str, str]
    bilingual_aliases: Mapping[str, str]
    field_families: Mapping[str, tuple[str, ...]]
    facets: Mapping[str, Mapping[str, tuple[str, ...]]]
    technical_patterns: Mapping[str, tuple[str, ...]]
    decorations: Mapping[str, tuple[str, ...]]

    def with_expected_object_count(self, count: int) -> "FieldSemanticConfig":
        return replace(self, expected_object_count=count)


@dataclass(frozen=True)
class ExpressionAnalysis:
    original_name: str
    original_comment: str | None
    normalized_name: str
    normalized_comment: str
    head_labels: tuple[str, ...]
    related_labels: tuple[str, ...]
    facets: tuple[dict[str, object], ...]
    decorations: tuple[dict[str, object], ...]
    value_kind: str
    semantic_scope: str
    field_family: str | None
    diagnostic_codes: tuple[str, ...]


@dataclass
class FieldSemanticResult:
    run_id: str
    config_hash: str
    baseline_hashes: dict[str, dict[str, str]]
    base_concepts: list[dict[str, object]]
    expressions: list[dict[str, object]]
    field_results: list[dict[str, object]]
    facets: list[dict[str, object]]
    diagnostics: list[dict[str, object]]
    approximate_candidates: list[dict[str, object]]
    stats: dict[str, object]
    quality_gate: dict[str, object]


def load_field_semantic_config(path: str | Path) -> FieldSemanticConfig:
    """Load and validate the bounded V2 configuration."""

    config_path = Path(path)
    source = config_path.read_text(encoding="utf-8")
    raw = yaml.safe_load(source)
    if not isinstance(raw, dict) or raw.get("version") != "v2":
        raise ValueError("field semantic config version must be v2")
    scope = _mapping(raw, "scope")
    support = _mapping(raw, "support_gate")
    limits = _mapping(raw, "limits")
    baseline_rows = _mapping(raw, "baselines")
    baselines: dict[str, BaselineReference] = {}
    for name, value in baseline_rows.items():
        if not isinstance(value, dict) or not value.get("path"):
            raise ValueError(f"baselines.{name} must contain path")
        hashes = {
            str(key): str(item).lower()
            for key, item in value.items()
            if str(key).endswith("sha256")
        }
        baselines[str(name)] = BaselineReference(Path(str(value["path"])), hashes)
    facets: dict[str, dict[str, tuple[str, ...]]] = {}
    for dimension, values in _mapping(raw, "facets").items():
        if not isinstance(values, dict):
            raise ValueError(f"facets.{dimension} must be a mapping")
        facets[str(dimension)] = {
            str(value): _tuple_of_strings(patterns, f"facets.{dimension}.{value}")
            for value, patterns in values.items()
        }
    return FieldSemanticConfig(
        source_text=source,
        config_hash=_sha256(source.encode("utf-8")),
        schemas=tuple(x.upper() for x in _tuple_of_strings(scope.get("schemas"), "scope.schemas")),
        object_types=tuple(x.upper() for x in _tuple_of_strings(scope.get("object_types"), "scope.object_types")),
        exclude_numeric_suffix=bool(scope.get("exclude_numeric_suffix", True)),
        expected_object_count=_positive_int(scope, "expected_object_count"),
        expected_excluded_count=_nonnegative_int(scope, "expected_excluded_count"),
        expected_field_count=_positive_int(scope, "expected_field_count"),
        baselines=baselines,
        min_fields=_positive_int(support, "min_fields"),
        require_cross_object_or_multi_expression=bool(
            support.get("require_cross_object_or_multi_expression", True)
        ),
        max_competing_candidates=_positive_int(limits, "max_competing_candidates"),
        max_approximate_neighbors=_positive_int(limits, "max_approximate_neighbors"),
        max_approximate_pairs=_positive_int(limits, "max_approximate_pairs", default=25000),
        min_approximate_similarity=_bounded_float(
            limits, "min_approximate_similarity", default=0.72
        ),
        review_page_size=_positive_int(limits, "review_page_size"),
        initial_concept_limit=_positive_int(limits, "initial_concept_limit"),
        abbreviations=_string_mapping(raw.get("abbreviations", {}), "abbreviations"),
        bilingual_aliases=_string_mapping(raw.get("bilingual_aliases", {}), "bilingual_aliases"),
        field_families={
            str(key): _tuple_of_strings(value, f"field_families.{key}")
            for key, value in _optional_mapping(raw, "field_families").items()
        },
        facets=facets,
        technical_patterns={
            str(key): _tuple_of_strings(value, f"technical_patterns.{key}")
            for key, value in _mapping(raw, "technical_patterns").items()
        },
        decorations={
            str(key): _tuple_of_strings(value, f"decorations.{key}")
            for key, value in _mapping(raw, "decorations").items()
        },
    )


def normalize_expression(value: str) -> NormalizedExpression:
    """Normalize formatting while preserving the exact source expression."""

    normalized = unicodedata.normalize("NFKC", value)
    normalized = _CAMEL_BOUNDARY.sub(" ", normalized)
    normalized = _CONNECTORS.sub(" ", normalized)
    normalized = re.sub(r"(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])", " ", normalized)
    normalized = re.sub(r"[()（）\[\]{}，,；;]+", " ", normalized)
    normalized = _SPACES.sub(" ", normalized).strip().lower()
    tokens = tuple(_ENGLISH.findall(normalized) + _CHINESE.findall(normalized))
    tokens = tuple(token.lower() for token in re.findall(r"[a-z]+|\d+|[\u3400-\u9fff]+", normalized))
    return NormalizedExpression(value, normalized, tokens)


def analyze_expression(
    column_name: str,
    column_comment: str | None,
    data_type: str,
    config: FieldSemanticConfig,
) -> ExpressionAnalysis:
    """Split a field expression into reusable head candidates and orthogonal facets."""

    name = normalize_expression(column_name)
    comment = normalize_expression(column_comment or "")
    combined = " ".join(part for part in (column_name, column_comment or "") if part)
    family_source = combined
    for match in _PAREN.finditer(combined):
        fragment = match.group(1).strip()
        if fragment:
            family_source = family_source.replace(match.group(0), f" {fragment} ")
    _, family_source = _extract_decorations(family_source, config)
    field_family, protected_fragments = _field_family_and_protected_fragments(
        column_name, family_source, config
    )
    facets, semantic_text = _extract_facets(
        combined, config, protected_fragments=protected_fragments
    )
    decorations, semantic_text = _extract_decorations(semantic_text, config)
    head_labels, related_labels = _head_candidates(
        column_name,
        semantic_text,
        config,
        comment_available=column_comment is not None,
    )
    if protected_fragments:
        protected_label = max(protected_fragments, key=lambda value: (len(value), value))
        shape_labels = {
            pattern
            for patterns in config.field_families.values()
            for pattern in patterns
        }
        related_labels = tuple(
            dict.fromkeys(
                label
                for label in (*head_labels, *related_labels)
                if label != protected_label and label not in shape_labels
            )
        )
        head_labels = (protected_label,)
    diagnostics = list(_noise_diagnostics(column_name, column_comment))
    scope = _semantic_scope(combined, config)
    return ExpressionAnalysis(
        original_name=column_name,
        original_comment=column_comment,
        normalized_name=name.normalized_text,
        normalized_comment=comment.normalized_text,
        head_labels=head_labels,
        related_labels=related_labels,
        facets=tuple(facets),
        decorations=tuple(decorations),
        value_kind=_value_kind(data_type, combined),
        semantic_scope=scope,
        field_family=field_family,
        diagnostic_codes=tuple(sorted(set(diagnostics))),
    )


def run_field_semantics(
    facts: PhysicalFacts, config: FieldSemanticConfig
) -> FieldSemanticResult:
    """Build a deterministic, run-scoped faceted semantic index."""

    selected, excluded = _select_objects(facts.objects, config)
    asset_rows = {str(row["asset_id"]): row for row in selected}
    columns = [row for row in facts.columns if str(row.get("asset_id")) in asset_rows]
    _validate_scope(config, selected, excluded, columns)
    baseline_hashes = _validate_baselines(config)
    run_id = _run_id(selected, config.config_hash)

    analyzed: list[tuple[dict[str, object], dict[str, object], ExpressionAnalysis]] = []
    for column in sorted(columns, key=lambda row: str(row.get("column_id", ""))):
        obj = asset_rows[str(column["asset_id"])]
        analysis = analyze_expression(
            str(column.get("column_name", "")),
            _optional_text(column.get("column_comment")),
            str(column.get("data_type", "")),
            config,
        )
        analyzed.append((obj, column, analysis))

    support: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {"fields": set(), "objects": set(), "expressions": set(), "facets": set()}
    )
    scopes: dict[str, Counter[str]] = defaultdict(Counter)
    value_kinds: dict[str, set[str]] = defaultdict(set)
    for obj, column, analysis in analyzed:
        for label in analysis.head_labels:
            key = _canonical_key(label)
            support[key]["fields"].add(str(column["column_id"]))
            support[key]["objects"].add(str(obj["asset_id"]))
            support[key]["expressions"].add(analysis.normalized_comment or analysis.normalized_name)
            support[key]["facets"].update(
                f"{row['dimension']}={row['value']}" for row in analysis.facets
            )
            scopes[key][analysis.semantic_scope] += 1
            value_kinds[key].add(analysis.value_kind)

    labels = {
        _canonical_key(label): label
        for _, _, analysis in analyzed
        for label in analysis.head_labels
    }
    concept_ids = {
        key: _stable_id("concept", run_id, key) for key in sorted(labels)
    }
    base_concepts: list[dict[str, object]] = []
    for key in sorted(labels):
        counts = support[key]
        second_view = len(counts["objects"]) >= 2 or (
            len(counts["expressions"]) >= 2 or len(counts["facets"]) >= 2
        )
        supported = len(counts["fields"]) >= config.min_fields and (
            second_view or not config.require_cross_object_or_multi_expression
        )
        scope = scopes[key].most_common(1)[0][0] if scopes[key] else "UNRESOLVED"
        base_concepts.append(
            {
                "concept_id": concept_ids[key],
                "canonical_key": key,
                "label": labels[key],
                "value_kinds": sorted(value_kinds[key]),
                "support_status": "SUPPORTED" if supported else "PROVISIONAL",
                "semantic_scope": scope,
                "method_id": METHOD_ID,
                "method_version": METHOD_VERSION,
                "support_counts": {
                    "field_count": len(counts["fields"]),
                    "object_count": len(counts["objects"]),
                    "expression_count": len(counts["expressions"]),
                    "facet_count": len(counts["facets"]),
                },
                "scope_reasons": sorted(scopes[key]),
            }
        )

    expressions: list[dict[str, object]] = []
    field_results: list[dict[str, object]] = []
    facet_rows: list[dict[str, object]] = []
    diagnostics: list[dict[str, object]] = []
    seen_expressions: set[tuple[str, str, str]] = set()
    for obj, column, analysis in analyzed:
        column_id = str(column["column_id"])
        bindings = []
        labels_for_field = analysis.head_labels[: config.max_competing_candidates]
        for rank, label in enumerate(labels_for_field, 1):
            key = _canonical_key(label)
            concept_id = concept_ids[key]
            binding_id = _stable_id("binding", run_id, column_id, concept_id)
            status = "CANDIDATE" if len(labels_for_field) == 1 else "CONFLICT"
            bindings.append(
                {
                    "binding_id": binding_id,
                    "concept_id": concept_id,
                    "rank": rank,
                    "status": status,
                    "relation_kind": "EXPRESSES",
                    "method_id": METHOD_ID,
                    "method_score": round(1.0 / rank, 6),
                    "source_refs": [f"physical-column:{column_id}"],
                    "limitations": ["metadata-only; no business rows were read"],
                }
            )
            raw_expression = analysis.original_comment or analysis.original_name
            kind = "VARIANT" if analysis.facets else (
                "ALIAS" if _is_configured_alias(column, label, config) else "SOURCE_EXPRESSION"
            )
            expression_key = (concept_id, kind, normalize_expression(raw_expression).normalized_text)
            if expression_key not in seen_expressions:
                seen_expressions.add(expression_key)
                expressions.append(
                    {
                        "expression_id": _stable_id("expression", run_id, *expression_key),
                        "concept_id": concept_id,
                        "expression_kind": kind,
                        "expression_status": "CANDIDATE",
                        "original_text": raw_expression,
                        "normalized_text": expression_key[2],
                        "language": _language(raw_expression),
                        "source_ref": f"physical-column:{column_id}",
                        "decorations": list(analysis.decorations),
                    }
                )
            for facet in analysis.facets:
                facet_rows.append(
                    {
                        "facet_id": _stable_id(
                            "facet", binding_id, str(facet["dimension"]), str(facet["value"])
                        ),
                        "binding_id": binding_id,
                        "dimension": facet["dimension"],
                        "value": facet["value"],
                        "raw_fragment": facet["raw_fragment"],
                        "status": "CANDIDATE",
                        "source_ref": f"physical-column:{column_id}",
                    }
                )
        for label in analysis.related_labels:
            key = _canonical_key(label)
            concept_id = concept_ids.get(key)
            if concept_id is None or any(
                binding["concept_id"] == concept_id for binding in bindings
            ):
                continue
            bindings.append(
                {
                    "binding_id": _stable_id("binding", run_id, column_id, concept_id, "RELATED_TO"),
                    "concept_id": concept_id,
                    "rank": None,
                    "status": "CANDIDATE",
                    "relation_kind": "RELATED_TO",
                    "method_id": METHOD_ID,
                    "method_score": None,
                    "source_refs": [f"physical-column:{column_id}"],
                    "limitations": ["related concept occurrence is not direct field semantics"],
                }
            )
        direct_bindings = [
            binding for binding in bindings if binding["relation_kind"] == "EXPRESSES"
        ]
        outcome = (
            "UNKNOWN"
            if not direct_bindings
            else "SINGLE_CANDIDATE"
            if len(direct_bindings) == 1
            else "COMPETING"
        )
        review_required = bool(analysis.diagnostic_codes) or outcome != "SINGLE_CANDIDATE"
        field_results.append(
            {
                "result_id": _stable_id("result", run_id, column_id),
                "column_id": column_id,
                "asset_id": str(column["asset_id"]),
                "schema_name": str(obj.get("schema_name", "")),
                "object_name": str(obj.get("object_name", "")),
                "column_name": str(column.get("column_name", "")),
                "column_comment": column.get("column_comment"),
                "declared_type": str(column.get("data_type", "")),
                "value_kind": analysis.value_kind,
                "field_family": analysis.field_family,
                "outcome": outcome,
                "candidate_bindings": bindings,
                "diagnostic_codes": list(analysis.diagnostic_codes),
                "review_status": "REVIEW_REQUIRED" if review_required else "NOT_REQUIRED",
                "method_id": METHOD_ID,
                "method_version": METHOD_VERSION,
            }
        )
        for code in analysis.diagnostic_codes:
            diagnostics.append(
                {
                    "column_id": column_id,
                    "code": code,
                    "source_text": analysis.original_comment or analysis.original_name,
                    "action": "QUARANTINE_REVIEW",
                }
            )

    base_concepts.sort(key=lambda row: (str(row["canonical_key"]), str(row["concept_id"])))
    expressions.sort(key=lambda row: str(row["expression_id"]))
    field_results.sort(key=lambda row: str(row["column_id"]))
    facet_rows.sort(key=lambda row: str(row["facet_id"]))
    diagnostics.sort(key=lambda row: (str(row["column_id"]), str(row["code"])))
    approximate_candidates = _approximate_recall(base_concepts, config)
    typo_concepts = {
        concept_id
        for row in approximate_candidates
        if row["candidate_kind"] == "POSSIBLE_TYPO"
        for concept_id in (str(row["left_concept_id"]), str(row["right_concept_id"]))
    }
    for concept_id in sorted(typo_concepts):
        diagnostics.append(
            {
                "concept_id": concept_id,
                "code": "POSSIBLE_TYPO",
                "action": "QUARANTINE_REVIEW",
            }
        )
    stats = {
        "object_count": len(selected),
        "excluded_object_count": len(excluded),
        "field_count": len(columns),
        "base_concept_count": len(base_concepts),
        "supported_concept_count": sum(row["support_status"] == "SUPPORTED" for row in base_concepts),
        "provisional_concept_count": sum(row["support_status"] == "PROVISIONAL" for row in base_concepts),
        "expression_count": len(expressions),
        "alias_count": sum(row["expression_kind"] == "ALIAS" for row in expressions),
        "variant_count": sum(row["expression_kind"] == "VARIANT" for row in expressions),
        "facet_count": len(facet_rows),
        "unknown_count": sum(row["outcome"] == "UNKNOWN" for row in field_results),
        "competing_count": sum(row["outcome"] == "COMPETING" for row in field_results),
        "conflict_count": sum(
            binding["status"] == "CONFLICT"
            for row in field_results
            for binding in row["candidate_bindings"]
            if binding.get("relation_kind") == "EXPRESSES"
        ),
        "approximate_candidate_count": len(approximate_candidates),
        "possible_typo_count": sum(
            row["candidate_kind"] == "POSSIBLE_TYPO"
            for row in approximate_candidates
        ),
    }
    quality_gate = _quality_gate(
        base_concepts, expressions, field_results, facet_rows, config=config
    )
    result = FieldSemanticResult(
        run_id=run_id,
        config_hash=config.config_hash,
        baseline_hashes=baseline_hashes,
        base_concepts=base_concepts,
        expressions=expressions,
        field_results=field_results,
        facets=facet_rows,
        diagnostics=diagnostics,
        approximate_candidates=approximate_candidates,
        stats=stats,
        quality_gate=quality_gate,
    )
    validate_field_semantic_result(result, facts)
    return result


def validate_field_semantic_result(
    result: FieldSemanticResult, facts: PhysicalFacts
) -> None:
    """Validate enums and every cross-file reference in a result bundle."""

    physical_columns = {str(row.get("column_id")) for row in facts.columns}
    concepts = {str(row["concept_id"]) for row in result.base_concepts}
    bindings: set[str] = set()
    canonical_keys: set[str] = set()
    for concept in result.base_concepts:
        if concept["support_status"] not in SUPPORT_STATUSES:
            raise ValueError("invalid support_status")
        if concept["semantic_scope"] not in SEMANTIC_SCOPES:
            raise ValueError("invalid semantic_scope")
        key = str(concept["canonical_key"])
        if key in canonical_keys:
            raise ValueError(f"duplicate canonical_key: {key}")
        canonical_keys.add(key)
    for row in result.field_results:
        if row["outcome"] not in OUTCOMES:
            raise ValueError("invalid inference outcome")
        if str(row["column_id"]) not in physical_columns:
            raise ValueError(f"unknown column_id: {row['column_id']}")
        candidates = row["candidate_bindings"]
        direct_candidates = [
            binding for binding in candidates if binding.get("relation_kind") == "EXPRESSES"
        ]
        if row["outcome"] == "UNKNOWN" and direct_candidates:
            raise ValueError("UNKNOWN must have no candidate bindings")
        for binding in candidates:
            if binding.get("relation_kind") not in {"EXPRESSES", "RELATED_TO"}:
                raise ValueError("invalid relation_kind")
            if str(binding["concept_id"]) not in concepts:
                raise ValueError(f"unknown concept_id: {binding['concept_id']}")
            binding_id = str(binding["binding_id"])
            if binding_id in bindings:
                raise ValueError(f"duplicate binding_id: {binding_id}")
            bindings.add(binding_id)
    for expression in result.expressions:
        if expression["expression_kind"] not in EXPRESSION_KINDS:
            raise ValueError("invalid expression_kind")
        if str(expression["concept_id"]) not in concepts:
            raise ValueError(f"unknown expression concept_id: {expression['concept_id']}")
    for facet in result.facets:
        if str(facet["binding_id"]) not in bindings:
            raise ValueError(f"unknown facet binding_id: {facet['binding_id']}")


def write_field_semantic_results(
    output_dir: str | Path,
    result: FieldSemanticResult,
    facts: PhysicalFacts,
    *,
    config: FieldSemanticConfig | None = None,
    investigation_queries: Sequence[str] = (),
) -> dict[str, Path]:
    """Write stable canonical V2 files and a replayable manifest."""

    validate_field_semantic_result(result, facts)
    root = Path(output_dir) / "field-semantic-index-v2"
    if root.resolve() == Path(output_dir).resolve():
        raise ValueError("V2 output must be an independent subdirectory")
    root.mkdir(parents=True, exist_ok=True)
    rows = {
        "base_concepts": result.base_concepts,
        "concept_expressions": result.expressions,
        "field_semantic_results": result.field_results,
        "field_facets": result.facets,
    }
    paths: dict[str, Path] = {}
    outputs = []
    for name, values in rows.items():
        path = root / f"{name}.jsonl"
        path.write_text(_jsonl(values), encoding="utf-8")
        paths[name] = path
        outputs.append(
            {
                "logical_name": name,
                "relative_path": path.name,
                "row_count": len(values),
                "content_sha256": _sha256(path.read_bytes()),
            }
        )
    diagnostics_root = root / "diagnostics"
    diagnostics_root.mkdir(exist_ok=True)
    diagnostics_path = diagnostics_root / "quarantine.jsonl"
    diagnostics_path.write_text(_jsonl(result.diagnostics), encoding="utf-8")
    paths["diagnostics"] = diagnostics_path
    approximate_path = diagnostics_root / "approximate_candidates.jsonl"
    approximate_path.write_text(
        _jsonl(result.approximate_candidates), encoding="utf-8"
    )
    paths["approximate_candidates"] = approximate_path
    manifest = {
        "schema_version": "field-semantic-index-v2",
        "stage_id": "field-semantic-index-v2",
        "stage_status": "SUCCESS" if result.quality_gate["status"] == "PASS" else "PARTIAL",
        "run_id": result.run_id,
        "method_id": METHOD_ID,
        "method_version": METHOD_VERSION,
        "config_sha256": result.config_hash,
        "inputs": result.baseline_hashes,
        "stats": result.stats,
        "support_gate": {
            "support_statuses": sorted(SUPPORT_STATUSES),
            "semantic_scopes": sorted(SEMANTIC_SCOPES),
        },
        "quality_gate": result.quality_gate,
        "outputs": outputs,
        "llm_mode": "disabled",
        "business_rows_read": False,
        "table_business_classification_read": False,
        "known_gaps": [
            "candidate semantic index, not a formal ontology or standard field registry",
            "declared types are non-authoritative hints",
            "TRADEFLOW-only validation does not prove cross-schema generalization",
        ],
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths["manifest"] = manifest_path
    if config is not None:
        comparison = build_field_semantic_comparison(
            result,
            config,
            investigation_queries,
        )
        review_root = root / "review"
        review_root.mkdir(exist_ok=True)
        comparison_json = review_root / "comparison.json"
        comparison_json.write_text(
            json.dumps(comparison, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        comparison_md = review_root / "comparison.md"
        comparison_md.write_text(_comparison_markdown(comparison), encoding="utf-8")
        paths["comparison_json"] = comparison_json
        paths["comparison_md"] = comparison_md
        paths.update(_write_review_projection(root, result, config))
    return paths


def _write_review_projection(
    root: Path,
    result: FieldSemanticResult,
    config: FieldSemanticConfig,
) -> dict[str, Path]:
    review_root = root / "review"
    review_root.mkdir(exist_ok=True)
    concept_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"direct": 0, "related": 0, "tables": 0}
    )
    concept_tables: dict[str, set[str]] = defaultdict(set)
    for row in result.field_results:
        for binding in row["candidate_bindings"]:
            concept_id = str(binding["concept_id"])
            key = "direct" if binding["relation_kind"] == "EXPRESSES" else "related"
            concept_counts[concept_id][key] += 1
            concept_tables[concept_id].add(str(row["asset_id"]))
    concepts = []
    for row in result.base_concepts:
        concept_id = str(row["concept_id"])
        concepts.append(
            {
                "concept_id": concept_id,
                "label": row["label"],
                "support_status": row["support_status"],
                "semantic_scope": row["semantic_scope"],
                "direct_field_count": concept_counts[concept_id]["direct"],
                "related_field_count": concept_counts[concept_id]["related"],
                "table_count": len(concept_tables[concept_id]),
            }
        )
    concepts.sort(
        key=lambda row: (
            0 if row["semantic_scope"] == "DOMAIN" else 1,
            0 if row["support_status"] == "SUPPORTED" else 1,
            -int(row["direct_field_count"]),
            str(row["label"]),
        )
    )
    facet_counts = Counter(
        (str(row["dimension"]), str(row["value"])) for row in result.facets
    )
    summary = {
        "run_id": result.run_id,
        "stats": result.stats,
        "quality_gate": result.quality_gate,
        "concepts": concepts,
        "facets": [
            {"dimension": dimension, "value": value, "binding_count": count}
            for (dimension, value), count in sorted(facet_counts.items())
        ],
        "page_size": config.review_page_size,
        "initial_concept_limit": config.initial_concept_limit,
        "table_business_classification_read": False,
    }
    summary_path = review_root / "summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    index_payload = _review_index_payload(result)
    index_path = review_root / "lookup.json"
    index_path.write_text(
        json.dumps(index_payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    catalog, concept_shards, table_shards = _build_review_catalog(result, config)
    data_root = review_root / "data"
    concept_root = data_root / "concepts"
    table_root = data_root / "tables"
    concept_root.mkdir(parents=True, exist_ok=True)
    table_root.mkdir(parents=True, exist_ok=True)
    for name, payload in concept_shards.items():
        (concept_root / name).write_text(
            "window.FIELD_SEMANTIC_SHARD="
            + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            + ";\n",
            encoding="utf-8",
        )
    for name, payload in table_shards.items():
        (table_root / name).write_text(
            "window.FIELD_SEMANTIC_SHARD="
            + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            + ";\n",
            encoding="utf-8",
        )
    field_catalog = catalog.pop("fields")
    field_catalog_path = review_root / "field-catalog.js"
    field_catalog_path.write_text(
        "window.FIELD_SEMANTIC_FIELDS="
        + json.dumps(field_catalog, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    catalog["field_catalog_url"] = field_catalog_path.name
    catalog_path = review_root / "catalog.js"
    catalog_path.write_text(
        "window.FIELD_SEMANTIC_CATALOG="
        + json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    worker_path = review_root / "worker.js"
    worker_path.write_text(_review_worker_script(), encoding="utf-8")
    html_path = review_root / "index.html"
    html_path.write_text(_review_html(summary, config), encoding="utf-8")
    return {
        "review_index": html_path,
        "review_summary": summary_path,
        "review_lookup": index_path,
        "review_worker": worker_path,
        "review_catalog": catalog_path,
        "review_field_catalog": field_catalog_path,
        "review_data_root": data_root,
    }


def _build_review_catalog(
    result: FieldSemanticResult,
    config: FieldSemanticConfig,
) -> tuple[dict[str, object], dict[str, dict[str, object]], dict[str, dict[str, object]]]:
    from .render import _slug

    physical_root = config.baselines.get("physical_facts")
    panorama_objects = (
        physical_root.path / "panorama" / "objects" if physical_root else None
    )
    v1_root = config.baselines.get("field_concepts_v1")
    v1_review = v1_root.path / "review" / "index.html" if v1_root else None
    concept_rows = {str(row["concept_id"]): row for row in result.base_concepts}
    expressions: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in result.expressions:
        expressions[str(row["concept_id"])].append(
            {
                "kind": row["expression_kind"],
                "text": row["original_text"],
                "normalized_text": row["normalized_text"],
                "status": row["expression_status"],
            }
        )
    facets_by_binding: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in result.facets:
        facets_by_binding[str(row["binding_id"])].append(
            {"dimension": row["dimension"], "value": row["value"]}
        )
    object_urls: dict[str, str] = {}
    if panorama_objects:
        for asset_id in {str(row["asset_id"]) for row in result.field_results}:
            target = (panorama_objects / f"{_slug(asset_id)}.html").resolve()
            if target.exists():
                object_urls[asset_id] = target.as_uri()

    concept_details: dict[str, dict[str, object]] = {}
    table_details: dict[str, dict[str, object]] = defaultdict(
        lambda: {"bindings": [], "unknown_fields": [], "object_name": "", "object_url": ""}
    )
    field_catalog: list[dict[str, object]] = []
    table_names: dict[str, str] = {}
    for row in result.field_results:
        asset_id = str(row["asset_id"])
        table_names[asset_id] = str(row["object_name"])
        table_details[asset_id]["object_name"] = row["object_name"]
        table_details[asset_id]["object_url"] = object_urls.get(asset_id, "")
        field_summary = {
            "column_id": row["column_id"],
            "asset_id": asset_id,
            "object_name": row["object_name"],
            "column_name": row["column_name"],
            "column_comment": row["column_comment"],
            "field_family": row.get("field_family"),
            "outcome": row["outcome"],
            "has_conflict": any(
                binding["status"] == "CONFLICT"
                for binding in row["candidate_bindings"]
                if binding["relation_kind"] == "EXPRESSES"
            ),
            "concept_ids": [],
            "search_text": (
                f"{row['column_name']} {row['column_comment']} {row['object_name']}"
            ).casefold(),
        }
        field_catalog.append(field_summary)
        if not row["candidate_bindings"]:
            table_details[asset_id]["unknown_fields"].append(field_summary)
        for binding in row["candidate_bindings"]:
            concept_id = str(binding["concept_id"])
            if (
                binding["relation_kind"] == "EXPRESSES"
                and concept_id not in field_summary["concept_ids"]
            ):
                field_summary["concept_ids"].append(concept_id)
            item = {
                **field_summary,
                "binding_id": binding["binding_id"],
                "concept_id": concept_id,
                "concept_label": concept_rows[concept_id]["label"],
                "relation_kind": binding["relation_kind"],
                "binding_status": binding["status"],
                "facets": facets_by_binding[str(binding["binding_id"])],
                "object_url": object_urls.get(asset_id, ""),
            }
            concept_details.setdefault(
                concept_id,
                {
                    "concept": concept_rows[concept_id],
                    "expressions": expressions[concept_id],
                    "bindings": [],
                },
            )["bindings"].append(item)
            table_details[asset_id]["bindings"].append(item)

    concept_shards = _bucket_review_rows(concept_details, "concepts")
    table_shards = _bucket_review_rows(dict(table_details), "tables")
    concept_shard_map = {
        key: f"data/concepts/{name}"
        for name, payload in concept_shards.items()
        for key in payload["rows"]
    }
    table_shard_map = {
        key: f"data/tables/{name}"
        for name, payload in table_shards.items()
        for key in payload["rows"]
    }
    concept_catalog = []
    for concept_id, row in concept_rows.items():
        details = concept_details.get(concept_id, {"bindings": []})
        bindings = details["bindings"]
        concept_catalog.append(
            {
                "concept_id": concept_id,
                "label": row["label"],
                "support_status": row["support_status"],
                "semantic_scope": row["semantic_scope"],
                "direct_count": sum(
                    item["relation_kind"] == "EXPRESSES" for item in bindings
                ),
                "related_count": sum(
                    item["relation_kind"] == "RELATED_TO" for item in bindings
                ),
                "search_text": " ".join(
                    [str(row["label"])]
                    + [str(item["text"]) for item in expressions[concept_id]]
                ).casefold(),
                "shard": concept_shard_map.get(concept_id, ""),
            }
        )
    concept_catalog.sort(
        key=lambda row: (
            0 if row["semantic_scope"] == "DOMAIN" else 1,
            0 if row["support_status"] == "SUPPORTED" else 1,
            -int(row["direct_count"]),
            str(row["label"]),
        )
    )
    tables = [
        {
            "asset_id": asset_id,
            "object_name": object_name,
            "search_text": f"{asset_id} {object_name}".casefold(),
            "field_count": sum(
                row["asset_id"] == asset_id for row in field_catalog
            ),
            "shard": table_shard_map[asset_id],
            "object_url": object_urls.get(asset_id, ""),
        }
        for asset_id, object_name in sorted(table_names.items(), key=lambda item: item[1])
    ]
    field_families = []
    for family in sorted(
        {str(row["field_family"]) for row in field_catalog if row.get("field_family")}
    ):
        family_fields = [row for row in field_catalog if row.get("field_family") == family]
        concept_ids = sorted(
            {
                str(concept_id)
                for row in family_fields
                for concept_id in row["concept_ids"]
            }
        )
        field_families.append(
            {
                "field_family": family,
                "field_count": len(family_fields),
                "concept_count": len(concept_ids),
                "concept_ids": concept_ids,
                "search_text": " ".join(
                    [family]
                    + [
                        str(concept_rows[concept_id]["label"])
                        for concept_id in concept_ids
                    ]
                ).casefold(),
            }
        )
    return (
        {
            "run_id": result.run_id,
            "page_size": config.review_page_size,
            "concepts": concept_catalog,
            "field_families": field_families,
            "tables": tables,
            "fields": field_catalog,
            "facets": sorted(
                {
                    f"{row['dimension']}={row['value']}"
                    for row in result.facets
                }
            ),
            "v1_review_url": v1_review.resolve().as_uri() if v1_review else "",
        },
        concept_shards,
        table_shards,
    )


def _bucket_review_rows(
    rows: Mapping[str, dict[str, object]], prefix: str, bucket_count: int = 32
) -> dict[str, dict[str, object]]:
    buckets: dict[int, dict[str, dict[str, object]]] = defaultdict(dict)
    for key, value in sorted(rows.items()):
        bucket = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16) % bucket_count
        buckets[bucket][key] = value
    return {
        f"{prefix}-{bucket:02d}.js": {"kind": prefix, "rows": values}
        for bucket, values in sorted(buckets.items())
    }


def _review_index_payload(result: FieldSemanticResult) -> dict[str, object]:
    concept_bindings: dict[str, list[dict[str, object]]] = defaultdict(list)
    table_bindings: dict[str, list[dict[str, object]]] = defaultdict(list)
    facet_bindings: dict[str, list[str]] = defaultdict(list)
    expression_concepts: dict[str, list[str]] = defaultdict(list)
    column_bindings: dict[str, list[dict[str, object]]] = defaultdict(list)
    scope_concepts: dict[str, list[str]] = defaultdict(list)
    facets_by_binding: dict[str, list[dict[str, object]]] = defaultdict(list)
    for facet in result.facets:
        binding_id = str(facet["binding_id"])
        facets_by_binding[binding_id].append(
            {"dimension": facet["dimension"], "value": facet["value"]}
        )
        facet_bindings[f"{facet['dimension']}={facet['value']}"].append(binding_id)
    for row in result.field_results:
        for binding in row["candidate_bindings"]:
            item = {
                "binding_id": binding["binding_id"],
                "relation_kind": binding["relation_kind"],
                "column_id": row["column_id"],
                "asset_id": row["asset_id"],
                "object_name": row["object_name"],
                "column_name": row["column_name"],
                "column_comment": row["column_comment"],
                "outcome": row["outcome"],
                "facets": facets_by_binding[str(binding["binding_id"])],
            }
            concept_bindings[str(binding["concept_id"])].append(item)
            table_bindings[str(row["asset_id"])].append(
                {**item, "concept_id": binding["concept_id"]}
            )
            column_bindings[str(row["column_id"])].append(
                {**item, "concept_id": binding["concept_id"]}
            )
    for concept in result.base_concepts:
        scope_concepts[str(concept["semantic_scope"])].append(
            str(concept["concept_id"])
        )
    for expression in result.expressions:
        expression_concepts[str(expression["normalized_text"])].append(
            str(expression["concept_id"])
        )
    return {
        "concept_bindings": dict(sorted(concept_bindings.items())),
        "table_bindings": dict(sorted(table_bindings.items())),
        "column_bindings": dict(sorted(column_bindings.items())),
        "facet_bindings": dict(sorted(facet_bindings.items())),
        "expression_concepts": dict(sorted(expression_concepts.items())),
        "scope_concepts": dict(sorted(scope_concepts.items())),
    }


def _review_worker_script() -> str:
    return """self.onmessage=event=>{
  const {type,rows=[],query='',page=0,pageSize=50}=event.data;
  const needle=String(query).trim().toLocaleLowerCase();
  const matched=type==='SEARCH'&&needle
    ?rows.filter(row=>String(row.search_text||'').includes(needle)):rows;
  const start=page*pageSize;
  self.postMessage({type,total:matched.length,page,rows:matched.slice(start,start+pageSize)});
};
// LOOKUP_CONCEPT LOOKUP_TABLE LOOKUP_COLUMN LOOKUP_FACET LOOKUP_SCOPE SEARCH_EXPRESSION
"""


def _review_html(
    summary: Mapping[str, object], config: FieldSemanticConfig
) -> str:
    return _review_application_html(config.review_page_size)

    # Legacy first-pass page retained below temporarily for diff readability.
    # It is unreachable and can be removed in a later cleanup.
    initial = summary["concepts"][: config.initial_concept_limit]
    cards = "".join(
        "<button class='concept' data-concept-id='{id}'><strong>{label}</strong>"
        "<span>{scope} · {support} · direct {direct} · related {related}</span></button>".format(
            id=_html(str(row["concept_id"])),
            label=_html(str(row["label"])),
            scope=_html(str(row["semantic_scope"])),
            support=_html(str(row["support_status"])),
            direct=row["direct_field_count"],
            related=row["related_field_count"],
        )
        for row in initial
    )
    return f"""<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>
<title>Field Semantic Index V2</title><style>
body{{font:14px/1.5 system-ui;margin:0;background:#f5f6f8;color:#172033}}header{{padding:18px 24px;background:#fff;border-bottom:1px solid #ddd}}
main{{display:grid;grid-template-columns:minmax(280px,38%) 1fr;gap:16px;padding:16px}}#concepts,#detail{{background:#fff;border-radius:10px;padding:14px;max-height:78vh;overflow:auto}}
.concept{{display:block;width:100%;text-align:left;border:0;border-bottom:1px solid #eee;background:#fff;padding:10px;cursor:pointer}}.concept span{{display:block;color:#667085;font-size:12px}}
.row{{padding:9px 0;border-bottom:1px solid #eee}}.kind{{font-size:11px;padding:2px 5px;border-radius:4px;background:#eef2ff}}@media(max-width:800px){{main{{grid-template-columns:1fr}}}}
</style></head><body><header><h1>字段语义索引 V2</h1><div>候选索引；直接表达与相关字段分开。首屏最多 {config.initial_concept_limit} 个概念，每次最多 {config.review_page_size} 条。</div></header>
<main><section id='concepts'>{cards}</section><section id='detail'>选择概念查看字段和表。</section></main>
<script>const PAGE_SIZE={config.review_page_size};const worker=new Worker('worker.js');const detail=document.querySelector('#detail');
worker.onmessage=e=>{{const d=e.data;detail.innerHTML=`<h2>${{d.total}} 条</h2>`+d.rows.map(r=>`<div class='row'><span class='kind'>${{r.relation_kind}}</span> <b>${{r.column_name||''}}</b> · ${{r.object_name||''}}<div>${{r.column_comment||''}}</div><small>${{r.column_id||''}}</small></div>`).join('')}};
document.querySelectorAll('.concept').forEach(button=>button.onclick=()=>worker.postMessage({{type:'LOOKUP_CONCEPT',key:button.dataset.conceptId,page:0,pageSize:PAGE_SIZE}}));</script></body></html>"""


def _review_application_html(page_size: int) -> str:
    template = r"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>字段语义调查索引</title>
<style>:root{font-family:Arial,"Microsoft YaHei",sans-serif;color:#172033;background:#f3f5f8}*{box-sizing:border-box}body{margin:0}header{background:#fff;padding:18px 22px;border-bottom:1px solid #d9dee8}.muted{color:#667085}.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}input,select,button{font:inherit;padding:8px;border:1px solid #cbd3df;border-radius:7px;background:#fff}input{min-width:260px;flex:1}button{cursor:pointer}button.active{background:#244f8f;color:#fff}main{display:grid;grid-template-columns:minmax(310px,36%) 1fr;gap:14px;padding:14px}.panel{background:#fff;border:1px solid #dce1e9;border-radius:10px;padding:13px;min-height:70vh}#results,#detail-list{max-height:68vh;overflow:auto}.item,.row{border-bottom:1px solid #edf0f4;padding:10px 6px}.item{display:block;width:100%;text-align:left;border-width:0 0 1px}.badge{display:inline-block;font-size:12px;padding:2px 7px;margin:3px;border-radius:12px;background:#edf2fa}.related{background:#fff2d8}.field{font-family:Consolas,monospace;font-weight:700}a{color:#245ea8}.pager{display:flex;gap:8px;margin-top:10px}details{margin-top:8px;color:#667085}@media(max-width:850px){main{grid-template-columns:1fr}.panel{min-height:0}}</style></head>
<body><header><h1>字段语义调查索引</h1><div class="muted">先看字段族，再看稳定业务概念和限定条件；可反查具体字段、表和 Panorama 详情。</div><div class="toolbar"><input id="search" placeholder="搜索业务概念、字段、中文注释或表名"><select id="scope-filter"><option value="ALL">全部范围</option><option value="DOMAIN">业务概念</option><option value="TECHNICAL">技术概念</option><option value="UNRESOLVED">待判断</option></select><select id="relation-filter"><option value="ALL">全部字段</option><option value="EXPRESSES">直接表达</option><option value="RELATED_TO">相关字段</option></select><button data-view="FAMILY">字段族</button><button data-view="CONCEPT">业务概念</button><button data-view="TABLE">表</button><button data-view="UNKNOWN">待判断</button><button data-view="CONFLICT">有冲突</button><a id="v1-link" target="_blank">查看旧版</a></div></header>
<main><section class="panel"><h2 id="list-title">字段族</h2><div id="results"></div><div id="list-pager" class="pager"></div></section><section class="panel"><div id="detail"><h2>怎么使用</h2><p>例如进入“日期类”，先看到支付日期、终止日期、交易日期等不同业务概念；再点概念查看实际字段及所在表。“实际、预计、初始”等只作为限定条件。</p></div><div id="facet-filters"></div><div id="detail-list"></div><div id="detail-pager" class="pager"></div></section></main>
<script src="catalog.js"></script><script>
const C=window.FIELD_SEMANTIC_CATALOG,SIZE=__PAGE_SIZE__;let view='FAMILY',lp=0,dp=0,current=null,facetSet=new Set(),shardRequest=0,searchTimer=null,fieldsLoading=null;const $=id=>document.getElementById(id),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));$('v1-link').href=C.v1_review_url||'#';
const FAMILY={DATE:'日期类',TIME:'时间类',AMOUNT:'金额类',QUANTITY:'数量类',RATE:'比率类',CODE:'代码类',NAME:'名称类'},REL={EXPRESSES:'直接表达',RELATED_TO:'相关字段',UNKNOWN:'待判断'},DIM={temporal_stage:'时点',direction:'方向',currency_basis:'币种口径',party_role:'参与方角色',lifecycle_stage:'业务阶段',measure_state:'状态'},VAL={INITIAL:'初始',CURRENT:'当前',END:'期末',BEFORE_ADJUSTMENT:'调整前',AFTER_ADJUSTMENT:'调整后',LONG:'多头',SHORT:'空头',BUY:'买入',SELL:'卖出',PAY:'支付',RECEIVE:'收取',ORIGINAL_CURRENCY:'原币',LOCAL_CURRENCY:'本币',UNDERLYING_CURRENCY:'标的币种',SETTLEMENT_CURRENCY:'结算币种',CLIENT:'客户',INTERNAL:'我方',COUNTERPARTY:'交易对手',SOURCE:'来源方',TARGET:'目标方',ORDER:'委托',EXECUTION:'成交',POSITION:'持仓',CLEARING:'清算',TERMINATION:'终止',DYNAMIC:'动态',FIXED:'固定',AVAILABLE:'可用',FROZEN:'冻结',ACCUMULATED:'累计',ESTIMATED:'预计',ACTUAL:'实际'};
function loadShard(path,key,done){const request=++shardRequest,slot=`FIELD_SEMANTIC_SHARD_${request}`;const script=document.createElement('script');script.src=path;script.onload=()=>{if(request!==shardRequest)return;const payload=window.FIELD_SEMANTIC_SHARD;window[slot]=payload;if(payload?.rows?.[key])done(payload.rows[key]);else $('detail').innerHTML='<p>明细不存在或已过期。</p>';script.remove()};script.onerror=()=>{if(request===shardRequest)$('detail').innerHTML='<p>明细加载失败。</p>';script.remove()};document.body.appendChild(script)}
const take=(rows,page)=>rows.slice(page*SIZE,(page+1)*SIZE);function pager(id,total,page,setter){const pages=Math.max(1,Math.ceil(total/SIZE));$(id).innerHTML=total>SIZE?`<button data-page="${page-1}" ${page===0?'disabled':''}>上一页</button><span>${page+1} / ${pages} · ${total} 条</span><button data-page="${page+1}" ${page+1>=pages?'disabled':''}>下一页</button>`:`<span>${total} 条</span>`;$(id).querySelectorAll('button').forEach(b=>b.onclick=()=>setter(Number(b.dataset.page)))}
function needFields(done){if(window.FIELD_SEMANTIC_FIELDS){done();return}if(fieldsLoading){fieldsLoading.push(done);return}fieldsLoading=[done];const s=document.createElement('script');s.src=C.field_catalog_url;s.onload=()=>{const callbacks=fieldsLoading||[];fieldsLoading=null;callbacks.forEach(fn=>fn());s.remove()};s.onerror=()=>{fieldsLoading=null;s.remove();$('results').innerHTML='<p>字段搜索目录加载失败。</p>'};document.body.appendChild(s)}
function listRows(){const q=$('search').value.trim().toLocaleLowerCase(),scope=$('scope-filter').value;if(view==='FAMILY')return C.field_families.filter(r=>!q||r.search_text.includes(q)||String(FAMILY[r.field_family]||r.field_family).includes(q));if(view==='CONCEPT'){const direct=C.concepts.filter(r=>(!q||r.search_text.includes(q))&&(scope==='ALL'||r.semantic_scope===scope));if(q&&window.FIELD_SEMANTIC_FIELDS){const ids=new Set(window.FIELD_SEMANTIC_FIELDS.filter(r=>r.search_text.includes(q)).flatMap(r=>r.concept_ids));return C.concepts.filter(r=>(direct.includes(r)||ids.has(r.concept_id))&&(scope==='ALL'||r.semantic_scope===scope))}return direct}if(view==='TABLE')return C.tables.filter(r=>!q||r.search_text.includes(q));return (window.FIELD_SEMANTIC_FIELDS||[]).filter(r=>(view==='UNKNOWN'?r.outcome==='UNKNOWN':r.has_conflict)&&(!q||r.search_text.includes(q)))}
function renderList(){const all=listRows();$('list-title').textContent={FAMILY:'字段族',CONCEPT:'业务概念',TABLE:'表',UNKNOWN:'待判断字段',CONFLICT:'有冲突字段'}[view];$('results').innerHTML=take(all,lp).map(r=>view==='FAMILY'?`<button class="item" data-family="${esc(r.field_family)}"><strong>${esc(FAMILY[r.field_family]||r.field_family)}</strong><div>${r.concept_count} 个概念 · ${r.field_count} 个字段</div></button>`:view==='CONCEPT'?`<button class="item" data-key="${esc(r.concept_id)}" data-shard="${esc(r.shard)}" data-kind="concept"><strong>${esc(r.label)}</strong><div><span class="badge">${r.semantic_scope==='DOMAIN'?'业务':'技术/待判断'}</span><span class="badge">直接 ${r.direct_count}</span><span class="badge related">相关 ${r.related_count}</span></div></button>`:view==='TABLE'?`<button class="item" data-key="${esc(r.asset_id)}" data-shard="${esc(r.shard)}" data-kind="table"><strong>${esc(r.object_name)}</strong><div>${r.field_count} 个字段</div></button>`:`<button class="item" data-key="${esc(r.asset_id)}" data-shard="${esc(C.tables.find(t=>t.asset_id===r.asset_id)?.shard||'')}" data-kind="table"><span class="field">${esc(r.column_name)}</span> · ${esc(r.object_name)}<div>${esc(r.column_comment||'—')}</div></button>`).join('')||'<p class="muted">没有匹配结果</p>';$('results').querySelectorAll('[data-family]').forEach(b=>b.onclick=()=>showFamily(b.dataset.family));$('results').querySelectorAll('[data-key]').forEach(b=>b.onclick=()=>loadShard(b.dataset.shard,b.dataset.key,d=>showDetail(b.dataset.kind,d)));pager('list-pager',all.length,lp,p=>{lp=p;renderList()})}
function showFamily(family,page=0){const f=C.field_families.find(x=>x.field_family===family),rows=C.concepts.filter(c=>f.concept_ids.includes(c.concept_id));current=null;dp=page;$('detail').innerHTML=`<h2>${esc(FAMILY[family]||family)}</h2><p>${f.concept_count} 个不同概念，合计 ${f.field_count} 个字段。属于同一字段族不表示它们可以合并。</p>`;$('facet-filters').innerHTML='';$('detail-list').innerHTML=take(rows,dp).map(c=>`<button class="item" data-key="${esc(c.concept_id)}" data-shard="${esc(c.shard)}"><strong>${esc(c.label)}</strong><div>直接 ${c.direct_count} · 相关 ${c.related_count}</div></button>`).join('');$('detail-list').querySelectorAll('button').forEach(b=>b.onclick=()=>loadShard(b.dataset.shard,b.dataset.key,d=>showDetail('concept',d)));pager('detail-pager',rows.length,dp,p=>showFamily(family,p))}
function allBindings(){const d=current.data;return current.kind==='concept'?d.bindings:[...d.bindings,...d.unknown_fields.map(x=>({...x,relation_kind:'UNKNOWN',facets:[]}))]}
function showDetail(kind,data){current={kind,data};dp=0;facetSet.clear();if(kind==='concept'){$('detail').innerHTML=`<h2>${esc(data.concept.label)}</h2><p>${data.concept.semantic_scope==='DOMAIN'?'业务概念':'技术或待判断概念'} · ${data.concept.support_status==='SUPPORTED'?'多处结构支持':'证据较少'}</p><h3>相关表达</h3>${data.expressions.map(e=>`<span class="badge">${esc(e.text)}</span>`).join(' ')||'—'}<details><summary>技术详情</summary>${data.expressions.map(e=>`${esc(e.kind)} · ${esc(e.text)}`).join('<br>')}</details>`}else $('detail').innerHTML=`<h2>${esc(data.object_name||'表字段反查')}</h2>${data.object_url?`<a href="${esc(data.object_url)}" target="_blank">打开 Panorama 表详情</a>`:''}`;renderFacets(allBindings());renderDetail(allBindings())}
function facetText(f){return `${DIM[f.dimension]||f.dimension}：${VAL[f.value]||f.value}`}function renderFacets(all){const map=new Map();all.flatMap(r=>r.facets).forEach(f=>map.set(`${f.dimension}=${f.value}`,f));const values=[...map.entries()].sort();$('facet-filters').innerHTML=values.length?'<h3>限定条件（可组合）</h3>'+values.map(([k,f])=>`<label><input type="checkbox" value="${esc(k)}">${esc(facetText(f))}</label>`).join(' '):'';$('facet-filters').querySelectorAll('input').forEach(x=>x.onchange=()=>{x.checked?facetSet.add(x.value):facetSet.delete(x.value);dp=0;renderDetail(all)})}
function renderDetail(all){const relation=$('relation-filter').value,filtered=all.filter(r=>(relation==='ALL'||r.relation_kind===relation)&&[...facetSet].every(f=>r.facets.some(x=>`${x.dimension}=${x.value}`===f)));$('detail-list').innerHTML=take(filtered,dp).map(r=>`<article class="row"><span class="badge ${r.relation_kind==='RELATED_TO'?'related':''}">${REL[r.relation_kind]||r.relation_kind}</span> <span class="field">${esc(r.column_name)}</span> · ${r.object_url?`<a href="${esc(r.object_url)}" target="_blank">${esc(r.object_name)}</a>`:esc(r.object_name)}<div>${esc(r.column_comment||'—')}</div>${r.concept_label?`<div>业务概念：<strong>${esc(r.concept_label)}</strong>${r.field_family?` · ${esc(FAMILY[r.field_family]||r.field_family)}`:''}</div>`:''}<div>${r.facets.map(f=>`<span class="badge">${esc(facetText(f))}</span>`).join('')}</div><details><summary>技术详情</summary>${esc(r.column_id||'')} · ${esc(r.relation_kind||'')}</details></article>`).join('')||'<p class="muted">当前筛选下没有字段</p>';pager('detail-pager',filtered.length,dp,p=>{dp=p;renderDetail(all)})}
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-view]').forEach(x=>x.classList.remove('active'));b.classList.add('active');view=b.dataset.view;lp=0;(view==='UNKNOWN'||view==='CONFLICT'?needFields(renderList):renderList())});$('search').oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>{lp=0;const q=$('search').value.trim();q&&view==='CONCEPT'?needFields(renderList):renderList()},180)};$('scope-filter').onchange=()=>{lp=0;renderList()};$('relation-filter').onchange=()=>{if(current)renderDetail(allBindings())};document.querySelector('[data-view="FAMILY"]').classList.add('active');renderList();
</script></body></html>"""
    return template.replace("__PAGE_SIZE__", str(page_size))


def _html(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def build_field_semantic_comparison(
    result: FieldSemanticResult,
    config: FieldSemanticConfig,
    investigation_queries: Sequence[str],
) -> dict[str, object]:
    """Build a lightweight V1-to-V2 and result-level investigation projection."""

    concepts = {str(row["concept_id"]): row for row in result.base_concepts}
    facets_by_binding: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in result.facets:
        facets_by_binding[str(row["binding_id"])].append(row)
    investigations = []
    for query in investigation_queries:
        query_analysis = analyze_expression("QUERY", query, "", config)
        query_heads = {_canonical_key(label) for label in query_analysis.head_labels}
        query_facets = {
            (str(row["dimension"]), str(row["value"])) for row in query_analysis.facets
        }
        matching_concepts = {
            concept_id
            for concept_id, concept in concepts.items()
            if str(concept["canonical_key"]) in query_heads
        }
        matched_rows = []
        direct_rows = []
        related_rows = []
        matched_facets: set[tuple[str, str]] = set()
        for row in result.field_results:
            matched_bindings = []
            for binding in row["candidate_bindings"]:
                if str(binding["concept_id"]) not in matching_concepts:
                    continue
                binding_facets = {
                    (str(facet["dimension"]), str(facet["value"]))
                    for facet in facets_by_binding[str(binding["binding_id"])]
                }
                if query_facets and not query_facets.issubset(binding_facets):
                    continue
                matched_bindings.append(binding)
                matched_facets.update(binding_facets)
            if matched_bindings:
                matched_rows.append(row)
                if any(binding["relation_kind"] == "EXPRESSES" for binding in matched_bindings):
                    direct_rows.append(row)
                if any(binding["relation_kind"] == "RELATED_TO" for binding in matched_bindings):
                    related_rows.append(row)
        investigations.append(
            {
                "query": query,
                "resolved_head_labels": list(query_analysis.head_labels),
                "resolved_facets": [
                    {"dimension": dimension, "value": value}
                    for dimension, value in sorted(query_facets)
                ],
                "concept_count": len(matching_concepts),
                "field_count": len(matched_rows),
                "direct_field_count": len(direct_rows),
                "related_field_count": len(related_rows),
                "table_count": len({str(row["asset_id"]) for row in matched_rows}),
                "available_facets": [
                    {"dimension": dimension, "value": value}
                    for dimension, value in sorted(matched_facets)
                ],
                "sample_fields": [
                    {
                        "column_id": row["column_id"],
                        "asset_id": row["asset_id"],
                        "object_name": row["object_name"],
                        "column_name": row["column_name"],
                        "column_comment": row["column_comment"],
                    }
                    for row in matched_rows[:20]
                ],
                "status": "FOUND" if matched_rows else "NOT_FOUND",
            }
        )
    v1 = _v1_alignment(result, config)
    investigation_pass = all(row["status"] == "FOUND" for row in investigations)
    gate_status = (
        "PASS" if result.quality_gate["status"] == "PASS" and investigation_pass else "FAIL"
    )
    return {
        "run_id": result.run_id,
        "summary": result.stats,
        "quality_gate": result.quality_gate,
        "v1_v2": v1,
        "investigations": investigations,
        "gate": {
            "status": gate_status,
            "structural_gate": result.quality_gate["status"],
            "investigation_gate": "PASS" if investigation_pass else "FAIL",
            "boundary": "queryability and structural invariants only; not overall semantic accuracy",
        },
    }


def _v1_alignment(
    result: FieldSemanticResult, config: FieldSemanticConfig
) -> dict[str, object]:
    reference = config.baselines.get("field_concepts_v1")
    if reference is None or not reference.path.is_dir():
        return {"status": "NOT_AVAILABLE", "aligned_field_count": 0}
    concepts = {
        str(row.get("concept_id")): str(row.get("label", ""))
        for row in _read_jsonl(reference.path / "concepts.jsonl")
    }
    primary = {}
    for row in _read_jsonl(reference.path / "field_concept_links.jsonl"):
        if int(row.get("rank", 1)) == 1:
            primary[str(row.get("field_id"))] = concepts.get(str(row.get("concept_id")), "")
    v2_labels = {
        str(row["concept_id"]): str(row["label"]) for row in result.base_concepts
    }
    transitions = Counter()
    aligned = 0
    for row in result.field_results:
        column_id = str(row["column_id"])
        if column_id not in primary:
            continue
        aligned += 1
        labels = sorted(
            v2_labels[str(binding["concept_id"])] for binding in row["candidate_bindings"]
        )
        transition = "UNCHANGED" if primary[column_id] in labels else (
            "TO_UNKNOWN" if not labels else "RESTRUCTURED"
        )
        transitions[transition] += 1
    return {
        "status": "SUCCESS",
        "aligned_field_count": aligned,
        "transition_counts": dict(sorted(transitions.items())),
        "v1_is_baseline_not_truth": True,
    }


def _comparison_markdown(comparison: Mapping[str, object]) -> str:
    lines = [
        "# Field Semantic Index V2 Comparison",
        "",
        f"- Run: `{comparison['run_id']}`",
        f"- Semantic-shape Gate: **{comparison['gate']['status']}**",
        "- Boundary: structural queryability only; this is not overall semantic accuracy or business acceptance.",
        "",
        "## Investigations",
        "",
        "| Query | Resolved head | Facets | Direct | Related | Total | Tables | Status |",
        "|---|---|---|---:|---:|---:|---:|---|",
    ]
    for row in comparison["investigations"]:
        facets = ", ".join(
            f"{item['dimension']}={item['value']}" for item in row["resolved_facets"]
        ) or "-"
        lines.append(
            f"| {row['query']} | {', '.join(row['resolved_head_labels']) or '-'} | "
            f"{facets} | {row['direct_field_count']} | {row['related_field_count']} | "
            f"{row['field_count']} | {row['table_count']} | {row['status']} |"
        )
    lines.extend(
        [
            "",
            "## V1 to V2 alignment",
            "",
            f"- Aligned fields: {comparison['v1_v2']['aligned_field_count']}",
            f"- Transitions: `{json.dumps(comparison['v1_v2'].get('transition_counts', {}), ensure_ascii=False, sort_keys=True)}`",
            "- V1 is a historical candidate baseline, not accepted truth.",
            "",
            "## Current GPT structural review",
            "",
            "- Improvement: EXPRESSES and RELATED_TO now separate direct concept members from merely related fields.",
            "- Improvement: nominal principal, margin rate/payment time, and execution time can be investigated without merging all related fields into one direct concept.",
            "- Remaining gap: many PROVISIONAL concepts still reproduce long source comments and require later review; node-count reduction is not treated as accuracy.",
            "- Remaining gap: approximate TF-IDF edges and typo candidates are review-only and are never auto-merged.",
            "- UI boundary: the lightweight page supports bounded concept drill-down; the JSON/Markdown report remains the primary delivery until complete Facet/Unknown/Conflict filtering and Object Card links are implemented.",
            "",
        ]
    )
    return "\n".join(lines)


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"JSONL row must be an object: {path}:{line_number}")
        rows.append(value)
    return rows


def _extract_decorations(
    text: str, config: FieldSemanticConfig
) -> tuple[list[dict[str, object]], str]:
    rows: list[dict[str, object]] = []
    semantic = text
    configured = {
        "dictionary_markers": "DICTIONARY_MARKER",
        "implementation_markers": "IMPLEMENTATION_NOTE",
        "deprecation_markers": "DEPRECATION",
    }
    for config_key, kind in configured.items():
        for pattern in config.decorations.get(config_key, ()):
            if _contains(semantic, pattern):
                rows.append({"kind": kind, "raw_fragment": pattern})
                semantic = _remove(semantic, pattern)
    regexes = (
        (_VALUE_DOMAIN, "VALUE_DOMAIN"),
        (_DATE_FORMAT, "FORMAT"),
        (_UNIT, "UNIT"),
        (_CURRENCY, "CURRENCY_CODE"),
        (_PRECISION, "PRECISION"),
    )
    for pattern, kind in regexes:
        for match in list(pattern.finditer(semantic)):
            rows.append({"kind": kind, "raw_fragment": match.group(0).strip()})
        semantic = pattern.sub(" ", semantic)
    for match in list(_PAREN.finditer(semantic)):
        fragment = match.group(1).strip()
        if fragment:
            rows.append({"kind": "PARENTHETICAL_NOTE", "raw_fragment": fragment})
    semantic = _PAREN.sub(" ", semantic)
    return rows, _SPACES.sub(" ", semantic).strip()


def _extract_facets(
    text: str,
    config: FieldSemanticConfig,
    *,
    protected_fragments: Sequence[str] = (),
) -> tuple[list[dict[str, object]], str]:
    rows: list[dict[str, object]] = []
    semantic = text
    for dimension, values in config.facets.items():
        for value, patterns in values.items():
            protected_value = any(
                any(_contains(fragment, pattern) for pattern in patterns)
                for fragment in protected_fragments
            )
            if protected_value:
                continue
            for pattern in sorted(patterns, key=len, reverse=True):
                if _contains(semantic, pattern):
                    rows.append(
                        {"dimension": dimension, "value": value, "raw_fragment": pattern}
                    )
                    semantic = _remove(semantic, pattern)
                    break
    unique = {
        (str(row["dimension"]), str(row["value"])): row for row in rows
    }
    return [unique[key] for key in sorted(unique)], _SPACES.sub(" ", semantic).strip()


def _field_family_and_protected_fragments(
    column_name: str,
    column_comment: str,
    config: FieldSemanticConfig,
) -> tuple[str | None, tuple[str, ...]]:
    comment = _SPACES.sub("", unicodedata.normalize("NFKC", column_comment))
    has_chinese_comment = bool(_CHINESE.search(comment))
    name_tokens = [token.upper() for token in normalize_expression(column_name).tokens]
    expanded = [config.abbreviations.get(token, token) for token in name_tokens]
    candidates: list[tuple[int, int, str, str]] = []
    for family, patterns in config.field_families.items():
        for pattern in sorted(patterns, key=len, reverse=True):
            normalized_pattern = _SPACES.sub("", unicodedata.normalize("NFKC", pattern))
            if not normalized_pattern:
                continue
            if normalized_pattern.isascii():
                if not has_chinese_comment and normalized_pattern.upper() in expanded:
                    candidates.append((0, len(normalized_pattern), family, normalized_pattern))
            else:
                position = comment.rfind(normalized_pattern)
                if position >= 0 and position + len(normalized_pattern) == len(comment):
                    candidates.append((1, len(normalized_pattern), family, normalized_pattern))
    if not candidates:
        return None, ()
    _, _, family, shape = max(
        candidates, key=lambda row: (row[0], row[1], row[2], row[3])
    )
    protected: list[str] = []
    if comment and shape in comment:
        shape_start = comment.rfind(shape)
        prefix = comment[:shape_start]
        identity_patterns = sorted(
            {
                pattern
                for dimension, values in config.facets.items()
                if dimension in {"direction", "lifecycle_stage", "party_role"}
                for patterns in values.values()
                for pattern in patterns
                if not pattern.isascii()
            },
            key=len,
            reverse=True,
        )
        identity = next(
            (pattern for pattern in identity_patterns if prefix.endswith(pattern)), None
        )
        if identity:
            protected.append(identity + shape)
        else:
            chinese_prefix = re.search(r"([\u3400-\u9fff]{1,8})$", prefix)
            if chinese_prefix:
                token = chinese_prefix.group(1)
                # Preserve a short adjacent identity phrase while leaving common
                # outer qualifiers available to the regular Facet extractor.
                qualifier_patterns = {
                    pattern
                    for dimension, values in config.facets.items()
                    if dimension in {"temporal_stage", "measure_state", "currency_basis"}
                    for patterns in values.values()
                    for pattern in patterns
                    if not pattern.isascii()
                }
                while True:
                    removed = next(
                        (item for item in sorted(qualifier_patterns, key=len, reverse=True) if token.startswith(item)),
                        None,
                    )
                    if not removed:
                        break
                    token = token[len(removed) :]
                if token:
                    # Chinese metadata often concatenates an entity and an event,
                    # e.g. 名义本金重置日期.  Preserve the adjacent event phrase
                    # as the core and leave the leading entity available as a
                    # related navigation clue instead of minting an over-specific
                    # whole-comment concept.
                    identity_token = token if len(token) <= 4 else token[-2:]
                    protected.append(identity_token + shape)
    if not protected:
        family_tokens = {
            pattern.upper()
            for pattern in config.field_families.get(family, ())
            if pattern.isascii()
        }
        for index, token in enumerate(expanded):
            if token not in family_tokens or index == 0:
                continue
            identity_token = expanded[index - 1]
            identity_label = config.bilingual_aliases.get(identity_token)
            if not identity_label:
                for dimension in ("direction", "lifecycle_stage", "party_role"):
                    for patterns in config.facets.get(dimension, {}).values():
                        if identity_token in {pattern.upper() for pattern in patterns if pattern.isascii()}:
                            identity_label = next(
                                (pattern for pattern in patterns if not pattern.isascii()), None
                            )
                            break
                    if identity_label:
                        break
            shape_label = next(
                (
                    pattern
                    for pattern in config.field_families.get(family, ())
                    if not pattern.isascii()
                ),
                None,
            )
            if identity_label and shape_label:
                protected.append(identity_label + shape_label)
                break
    return family, tuple(protected)


def _head_candidates(
    column_name: str,
    semantic_text: str,
    config: FieldSemanticConfig,
    *,
    comment_available: bool,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    comment_aliases = [
        label
        for label in set(config.bilingual_aliases.values())
        if label and label in semantic_text
    ]
    if comment_aliases:
        alias = max(comment_aliases, key=lambda value: (len(value), value))
        alias_start = semantic_text.find(alias)
        trailing = semantic_text[alias_start + len(alias) :].strip(" ：:,，")
        if trailing:
            chinese = "".join(_CHINESE.findall(semantic_text)).strip()
            direct = chinese or semantic_text.strip()
            return (direct,), (alias,)
        return (alias,), ()
    name_tokens = [token.upper() for token in normalize_expression(column_name).tokens if token.isascii()]
    expanded = [config.abbreviations.get(token, token) for token in name_tokens]
    mapped = [config.bilingual_aliases[token] for token in expanded if token in config.bilingual_aliases]
    meaningful_mapped = [label for label in mapped if label]
    chinese_phrases = _CHINESE.findall(semantic_text)
    candidates = [phrase.strip() for phrase in chinese_phrases if phrase.strip() not in _LOW_INFORMATION]
    if comment_available and candidates:
        return (max(candidates, key=lambda value: (len(value), value)),), ()
    if meaningful_mapped:
        # Prefer the longest mapped center; remaining mapped terms become competitors.
        return (
            tuple(dict.fromkeys(sorted(meaningful_mapped, key=lambda value: (-len(value), value)))),
            (),
        )
    if candidates:
        return (max(candidates, key=lambda value: (len(value), value)),), ()
    if not comment_available and not meaningful_mapped:
        return (), ()
    remaining = [
        token for token in expanded
        if token not in _TECH_SUFFIXES and token not in _LOW_INFORMATION and not token.isdigit()
    ]
    if not remaining:
        return (), ()
    return (" ".join(remaining).title(),), ()


def _noise_diagnostics(name: str, comment: str | None) -> tuple[str, ...]:
    rows = []
    if re.search(r"\d+$", name) and not re.search(r"\d{4,}$", name):
        rows.append("NUMERIC_SLOT")
    if comment and (comment.endswith("…") or comment.endswith("...") or len(comment.strip()) <= 1):
        rows.append("TRUNCATED_EXPRESSION")
    if not re.search(r"[_\-.]", name) and re.fullmatch(r"[A-Za-z]{12,}", name):
        rows.append("POSSIBLE_CONCATENATION")
    tokens = [token for token in normalize_expression(name).tokens if token.isascii()]
    if comment is None and any(len(token) <= 3 and token.upper() not in _TECH_SUFFIXES for token in tokens):
        rows.append("UNRESOLVED_ABBREVIATION")
    return tuple(rows)


def _semantic_scope(text: str, config: FieldSemanticConfig) -> str:
    for patterns in config.technical_patterns.values():
        if any(_contains(text, pattern) for pattern in patterns):
            return "TECHNICAL"
    return "DOMAIN" if text.strip() else "UNRESOLVED"


def _value_kind(data_type: str, text: str) -> str:
    upper = data_type.upper()
    signal = text.upper()
    if any(token in upper for token in ("DATE", "TIME", "TIMESTAMP")):
        return "DATE_TIME"
    if any(token in upper for token in ("NUMBER", "DECIMAL", "NUMERIC", "FLOAT", "DOUBLE", "INT")):
        if any(token in signal for token in ("RATE", "RATIO", "%", "比例", "比率")):
            return "RATIO"
        return "NUMBER"
    if any(token in upper for token in ("CHAR", "CLOB", "TEXT")):
        return "TEXT"
    return "UNKNOWN"


def _approximate_recall(
    concepts: Sequence[dict[str, object]],
    config: FieldSemanticConfig,
) -> list[dict[str, object]]:
    """Return bounded TF-IDF character n-gram neighbors without publishing hierarchy."""

    documents = [str(row["canonical_key"]) for row in concepts]
    term_counts: list[Counter[str]] = []
    document_frequency: Counter[str] = Counter()
    for document in documents:
        compact = document.replace("_", " ")
        grams = [
            compact[index : index + size]
            for size in (2, 3)
            for index in range(max(0, len(compact) - size + 1))
        ]
        counts = Counter(grams)
        term_counts.append(counts)
        document_frequency.update(counts)
    vectors: list[dict[str, float]] = []
    postings: dict[str, list[tuple[int, float]]] = defaultdict(list)
    total = len(documents)
    for index, counts in enumerate(term_counts):
        weighted = {
            gram: (1.0 + math.log(count))
            * (math.log((1 + total) / (1 + document_frequency[gram])) + 1.0)
            for gram, count in counts.items()
        }
        norm = math.sqrt(sum(value * value for value in weighted.values())) or 1.0
        vector = {gram: value / norm for gram, value in weighted.items()}
        vectors.append(vector)
        for gram, value in vector.items():
            postings[gram].append((index, value))
    pairs: dict[tuple[int, int], float] = {}
    for left, vector in enumerate(vectors):
        scores: dict[int, float] = defaultdict(float)
        for gram, left_weight in vector.items():
            for right, right_weight in postings[gram]:
                if right > left:
                    scores[right] += left_weight * right_weight
        for right, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[
            : config.max_approximate_neighbors
        ]:
            if score >= config.min_approximate_similarity:
                pairs[(left, right)] = score
                if len(pairs) >= config.max_approximate_pairs:
                    break
        if len(pairs) >= config.max_approximate_pairs:
            break
    rows = []
    for (left, right), score in sorted(
        pairs.items(), key=lambda item: (-item[1], item[0])
    ):
        left_text = documents[left]
        right_text = documents[right]
        candidate_kind = (
            "POSSIBLE_TYPO"
            if _single_edit_apart(left_text, right_text) and left_text != right_text
            else "APPROXIMATE_COMPETITOR"
        )
        rows.append(
            {
                "left_concept_id": concepts[left]["concept_id"],
                "right_concept_id": concepts[right]["concept_id"],
                "candidate_kind": candidate_kind,
                "method_id": "field_semantics.char_tfidf_recall.v1",
                "method_score": round(score, 6),
                "status": "REVIEW_CANDIDATE",
                "published_relation": False,
            }
        )
    return rows


def _single_edit_apart(left: str, right: str) -> bool:
    if abs(len(left) - len(right)) > 1 or left == right:
        return False
    if len(left) > len(right):
        left, right = right, left
    if len(left) == len(right):
        return sum(a != b for a, b in zip(left, right, strict=True)) == 1
    index_left = index_right = differences = 0
    while index_left < len(left) and index_right < len(right):
        if left[index_left] == right[index_right]:
            index_left += 1
            index_right += 1
        else:
            differences += 1
            index_right += 1
            if differences > 1:
                return False
    return True


def _select_objects(
    objects: Sequence[dict[str, object]], config: FieldSemanticConfig
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    selected = []
    excluded = []
    for row in objects:
        schema = str(row.get("schema_name", "")).upper()
        object_type = str(row.get("object_type", "")).upper()
        if schema not in config.schemas or object_type not in config.object_types:
            continue
        if not bool(row.get("in_panorama_scope", True)) or bool(row.get("is_boundary", False)):
            continue
        if config.exclude_numeric_suffix and _NUMERIC_SUFFIX.search(str(row.get("object_name", ""))):
            excluded.append(row)
        else:
            selected.append(row)
    return selected, excluded


def _validate_scope(
    config: FieldSemanticConfig,
    selected: Sequence[dict[str, object]],
    excluded: Sequence[dict[str, object]],
    columns: Sequence[dict[str, object]],
) -> None:
    if len(selected) != config.expected_object_count:
        raise ValueError(f"scope drift: expected {config.expected_object_count} objects, got {len(selected)}")
    if len(excluded) != config.expected_excluded_count:
        raise ValueError(f"scope drift: expected {config.expected_excluded_count} excluded objects, got {len(excluded)}")
    if len(columns) != config.expected_field_count:
        raise ValueError(f"scope drift: expected {config.expected_field_count} fields, got {len(columns)}")


def _validate_baselines(config: FieldSemanticConfig) -> dict[str, dict[str, str]]:
    resolved: dict[str, dict[str, str]] = {}
    file_names = {
        "manifest_sha256": "manifest.json",
        "concepts_sha256": "concepts.jsonl",
        "links_sha256": "field_concept_links.jsonl",
        "revisions_sha256": "revision_candidates.jsonl",
    }
    for name, reference in config.baselines.items():
        actuals: dict[str, str] = {"path": str(reference.path)}
        for hash_key, expected in reference.hashes.items():
            target = reference.path if reference.path.is_file() else reference.path / file_names[hash_key]
            if not target.exists():
                raise ValueError(f"missing baseline file: {target}")
            actual = _sha256(target.read_bytes())
            if actual != expected:
                raise ValueError(f"baseline hash drift for {name}.{hash_key}")
            actuals[hash_key] = actual
        resolved[name] = actuals
    return resolved


def _quality_gate(
    concepts: Sequence[dict[str, object]],
    expressions: Sequence[dict[str, object]],
    field_results: Sequence[dict[str, object]],
    facets: Sequence[dict[str, object]],
    config: FieldSemanticConfig | None = None,
) -> dict[str, object]:
    keys = [str(row["canonical_key"]) for row in concepts]
    concept_labels = {
        str(row["concept_id"]): str(row["label"]) for row in concepts
    }
    collapsed_compound_fields: list[str] = []
    if config is not None:
        family_labels_by_key = {
            family: {
                pattern
                for pattern in patterns
                if _CHINESE.search(pattern)
            }
            for family, patterns in config.field_families.items()
        }
        identity_name_tokens = set(config.bilingual_aliases)
        for row in field_results:
            family = row.get("field_family")
            if not family:
                continue
            family_labels = family_labels_by_key.get(str(family), set())
            direct_labels = {
                concept_labels.get(str(binding.get("concept_id")), "")
                for binding in row.get("candidate_bindings", [])
                if binding.get("relation_kind") == "EXPRESSES"
            }
            if not direct_labels & family_labels:
                continue
            comment = _SPACES.sub(
                "", unicodedata.normalize("NFKC", str(row.get("column_comment") or ""))
            )
            has_compound_comment = False
            for shape in family_labels:
                if not comment.endswith(shape) or len(comment) <= len(shape):
                    continue
                prefix = comment[: -len(shape)]
                for dimension in ("temporal_stage", "measure_state", "currency_basis"):
                    for patterns in config.facets.get(dimension, {}).values():
                        for pattern in sorted(patterns, key=len, reverse=True):
                            prefix = _remove(prefix, pattern)
                prefix = _CURRENCY.sub("", prefix)
                prefix = re.sub(r"[^\u3400-\u9fff]+", "", prefix)
                if prefix:
                    has_compound_comment = True
                    break
            name_tokens = [
                token.upper()
                for token in normalize_expression(str(row.get("column_name", ""))).tokens
                if token.isascii()
            ]
            family_name_tokens = {
                pattern.upper()
                for pattern in config.field_families.get(str(family), ())
                if pattern.isascii()
            }
            has_named_identity = any(
                token in identity_name_tokens
                and index + 1 < len(name_tokens)
                and name_tokens[index + 1] in family_name_tokens
                for index, token in enumerate(name_tokens)
            )
            if has_compound_comment or has_named_identity:
                collapsed_compound_fields.append(str(row.get("column_id", "")))
    decoration_labels = {
        "数据字典", "字典项", "yyyyMMdd", "YYYYMMDD", "万元", "单位"
    }
    checks = {
        "unique_canonical_keys": len(keys) == len(set(keys)),
        "no_hierarchy_artifacts": all("parent_id" not in row for row in concepts),
        "no_decoration_base_concepts": not any(str(row["label"]) in decoration_labels for row in concepts),
        "all_fields_have_results": bool(field_results),
        "unknowns_have_no_direct_candidates": all(
            row["outcome"] != "UNKNOWN"
            or not any(
                binding.get("relation_kind") == "EXPRESSES"
                for binding in row["candidate_bindings"]
            )
            for row in field_results
        ),
        "bidirectional_keys_present": all(row.get("column_id") and row.get("asset_id") for row in field_results),
        "expressions_and_facets_reference_bindings": bool(expressions) and isinstance(facets, Sequence),
        "no_compound_core_collapsed_to_family": not collapsed_compound_fields,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "collapsed_compound_field_ids": collapsed_compound_fields[:50],
        "boundary": "structural invariants only; does not prove member semantics",
    }


def _is_configured_alias(
    column: Mapping[str, object], label: str, config: FieldSemanticConfig
) -> bool:
    tokens = [token.upper() for token in normalize_expression(str(column.get("column_name", ""))).tokens]
    expanded = [config.abbreviations.get(token, token) for token in tokens]
    return any(config.bilingual_aliases.get(token) == label for token in expanded)


def _canonical_key(label: str) -> str:
    return normalize_expression(label).normalized_text.replace(" ", "_")


def _contains(text: str, pattern: str) -> bool:
    if not pattern:
        return False
    if pattern.isascii():
        return re.search(rf"(?<![A-Za-z0-9]){re.escape(pattern)}(?![A-Za-z0-9])", text, re.IGNORECASE) is not None
    return pattern in text


def _remove(text: str, pattern: str) -> str:
    if pattern.isascii():
        return re.sub(rf"(?<![A-Za-z0-9]){re.escape(pattern)}(?![A-Za-z0-9])", " ", text, flags=re.IGNORECASE)
    return text.replace(pattern, " ")


def _language(value: str) -> str:
    has_zh = bool(_CHINESE.search(value))
    has_en = bool(re.search(r"[A-Za-z]", value))
    return "MIXED" if has_zh and has_en else "ZH" if has_zh else "EN" if has_en else "UNKNOWN"


def _run_id(objects: Sequence[dict[str, object]], config_hash: str) -> str:
    source_runs = sorted({str(row.get("run_id", "unknown")) for row in objects})
    return "field-semantic-v2-" + _sha256(("|".join(source_runs) + config_hash).encode("utf-8"))[:16]


def _stable_id(prefix: str, *parts: str) -> str:
    return f"{prefix}-" + _sha256("\x1f".join(parts).encode("utf-8"))[:20]


def _jsonl(rows: Sequence[dict[str, object]]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def _mapping(value: Mapping[str, object], key: str) -> dict[str, object]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise ValueError(f"{key} must be a mapping")
    return item


def _optional_mapping(value: Mapping[str, object], key: str) -> dict[str, object]:
    item = value.get(key, {})
    if not isinstance(item, dict):
        raise ValueError(f"{key} must be a mapping")
    return item


def _tuple_of_strings(value: object, key: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, (str, int, float)) for item in value):
        raise ValueError(f"{key} must be a list")
    return tuple(str(item) for item in value)


def _string_mapping(value: object, key: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a mapping")
    return {str(name).upper(): str(item) for name, item in value.items()}


def _positive_int(
    value: Mapping[str, object], key: str, *, default: int = 0
) -> int:
    result = int(value.get(key, default))
    if result <= 0:
        raise ValueError(f"{key} must be positive")
    return result


def _nonnegative_int(value: Mapping[str, object], key: str) -> int:
    result = int(value.get(key, -1))
    if result < 0:
        raise ValueError(f"{key} must be nonnegative")
    return result


def _bounded_float(
    value: Mapping[str, object], key: str, *, default: float
) -> float:
    result = float(value.get(key, default))
    if not 0.0 <= result <= 1.0:
        raise ValueError(f"{key} must be between 0 and 1")
    return result
