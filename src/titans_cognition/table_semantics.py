"""Bounded, evidence-linked table semantic projection for TRADEFLOW.

The module deliberately treats tables as the only classification subjects. Field,
Wiki, and structural inputs remain supporting or contradicting evidence and never
become automatic table labels through voting or propagation.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

import yaml


METHOD_ID = "table_semantics.bounded_projection.v1"
METHOD_VERSION = "v1"


@dataclass(frozen=True)
class InputSpec:
    """One fixed, content-addressed input."""

    name: str
    path: Path
    manifest: str
    manifest_sha256: str
    required: bool = True
    tree: str | None = None
    tree_sha256: str | None = None
    availability: str = "AVAILABLE"
    actual_manifest_sha256: str | None = None
    diagnostic: str | None = None


@dataclass(frozen=True)
class RelationPredicate:
    """Evidence requirement for one candidate table relation."""

    name: str
    directed: bool
    symmetric: bool
    min_direct_evidence: int


@dataclass(frozen=True)
class TableSemanticConfig:
    """Validated bounded configuration for one table-semantic run."""

    version: str
    scope_schema: str
    object_types: tuple[str, ...]
    expected_all_tables: int
    expected_subject_tables: int
    expected_variant_or_other_tables: int
    inputs: Mapping[str, InputSpec]
    limits: Mapping[str, int]
    variant_rules: tuple[tuple[str, str], ...]
    relation_registry_version: str
    relation_predicates: Mapping[str, RelationPredicate]
    semantic_seeds: Mapping[str, Mapping[str, tuple[str, ...]]]
    investigation_sets: tuple[Mapping[str, Any], ...] = ()
    approved_wiki_bodies: tuple[Mapping[str, Any], ...] = ()
    approved_test_aggregates: tuple[Mapping[str, Any], ...] = ()
    config_path: Path | None = None
    config_sha256: str = "test-config"

    @classmethod
    def for_tests(cls) -> "TableSemanticConfig":
        seeds = {
            "contexts": {
                "TRS": ("TRS", "收益互换"),
                "IRS": ("IRS", "利率互换"),
                "OPTION": ("OPTION", "期权"),
                "OTC_SHARED": ("OTC", "场外"),
            },
            "anchors": {
                "CONTRACT": ("CONTR", "CONTRACT", "DEAL", "合约"),
                "EVENT": ("EVENT", "事件"),
                "POSITION": ("POS", "POSITION", "持仓"),
                "MAPPING": ("MAPPING", "MAP", "映射"),
            },
            "responsibilities": {
                "MASTER_RECORD": ("REF", "MASTER", "主表", "主记录"),
                "DETAIL_OR_LEG": ("DETAIL", "LEG", "明细", "腿"),
                "LIFECYCLE_EVENT": ("EVENT", "事件"),
                "CURRENT_STATE": ("CURRENT", "CURR", "当前"),
                "HISTORY_STATE": ("HIS", "HISTORY", "历史"),
                "CONFIGURATION": ("CFG", "CONFIG", "PARAM", "参数", "配置"),
                "APPROVAL_OR_AUDIT_TRAIL": ("APPROVAL", "AUDIT", "审批", "审计"),
                "OPERATIONAL_LOG": ("LOG", "日志"),
                "VALIDATION_RECORD": ("VALIDATION", "CHECK", "校验"),
                "REPORT_OR_WRITEBACK": ("REPORT", "RESULT", "报表", "报送", "回写"),
                "MAPPING_DEFINITION": ("MAPPING", "MAP", "映射"),
            },
        }
        related = RelationPredicate("RELATED_TO", False, True, 1)
        return cls(
            version="v1",
            scope_schema="TITANS_TRADEFLOW",
            object_types=("TABLE",),
            expected_all_tables=0,
            expected_subject_tables=0,
            expected_variant_or_other_tables=0,
            inputs={},
            limits={
                "max_variant_candidates_per_table": 3,
                "max_context_candidates_per_table": 4,
                "max_anchor_candidates_per_table": 4,
                "max_responsibility_candidates_per_table": 4,
            },
            variant_rules=tuple(_DEFAULT_VARIANT_RULES),
            relation_registry_version="test-v1",
            relation_predicates={"RELATED_TO": related},
            semantic_seeds=seeds,
        )


@dataclass
class TableSemanticResult:
    """Typed row collections for a single bounded projection."""

    table_profiles: list[dict[str, Any]] = field(default_factory=list)
    context_candidates: list[dict[str, Any]] = field(default_factory=list)
    anchor_candidates: list[dict[str, Any]] = field(default_factory=list)
    responsibility_candidates: list[dict[str, Any]] = field(default_factory=list)
    table_groups: list[dict[str, Any]] = field(default_factory=list)
    group_memberships: list[dict[str, Any]] = field(default_factory=list)
    table_relations: list[dict[str, Any]] = field(default_factory=list)
    assertions: list[dict[str, Any]] = field(default_factory=list)
    evidence_refs: list[dict[str, Any]] = field(default_factory=list)
    review_decisions: list[dict[str, Any]] = field(default_factory=list)
    field_support_summaries: list[dict[str, Any]] = field(default_factory=list)
    structural_propagation_hints: list[dict[str, Any]] = field(default_factory=list)
    wiki_candidates: list[dict[str, Any]] = field(default_factory=list)
    investigation_cards: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    quality_gate: dict[str, Any] = field(default_factory=dict)
    input_states: list[dict[str, Any]] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    legacy_comparison: dict[str, Any] = field(default_factory=dict)


_DEFAULT_VARIANT_RULES: tuple[tuple[str, str], ...] = (
    ("backup", r"_BAK(?:_(?:19|20)?\d{6,8})?$"),
    ("version", r"_V\d+$"),
    ("dated_yyyymmdd", r"_(?:19|20)\d{6}$"),
    ("dated_yymmdd", r"_\d{6}$"),
    ("dated_yyyymm", r"_(?:19|20)\d{4}$"),
    ("numeric_revision", r"_?\d{1,5}$"),
)

_FIELD_MARKERS: Mapping[str, tuple[str, ...]] = {
    "ANCHOR_ID": (
        "CONTR_ID",
        "CONTRACT_ID",
        "DEAL_ID",
        "TRADE_ID",
        "TRS_ID",
        "LEG_ID",
    ),
    "EVENT_MARKER": ("EVENT_ID", "EVENT_TYPE", "EVENT_DATE", "EVENT_STATUS"),
    "BUSINESS_DATE": ("BIZ_DATE", "BUSINESS_DATE", "TRADE_DATE", "POSITION_DATE"),
    "SOURCE_TARGET": ("SOURCE_ID", "TARGET_ID", "SRC_ID", "DEST_ID"),
    "CONFIGURATION_ID": ("CONFIG_ID", "PARAM_ID", "RULE_ID"),
    "APPROVAL_AUDIT": ("APPROVAL", "AUDIT", "APPROVE", "REVIEW"),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_id(prefix: str, *parts: object) -> str:
    payload = "|".join(str(part) for part in parts)
    return f"{prefix}-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def _read_mapping(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"configuration must be a mapping: {path}")
    return value


def _bounded_positive_ints(raw: object) -> dict[str, int]:
    if not isinstance(raw, dict):
        raise ValueError("limits must be a mapping")
    result: dict[str, int] = {}
    for name, value in raw.items():
        number = int(value)
        if number < 0:
            raise ValueError(f"limit must be non-negative: {name}")
        result[str(name)] = number
    return result


def _resolve_input(name: str, raw: object) -> InputSpec:
    if not isinstance(raw, dict):
        raise ValueError(f"input {name} must be a mapping")
    base = InputSpec(
        name=name,
        path=Path(str(raw["path"])),
        manifest=str(raw["manifest"]),
        manifest_sha256=str(raw["manifest_sha256"]).lower(),
        required=bool(raw.get("required", True)),
        tree=str(raw["tree"]) if raw.get("tree") else None,
        tree_sha256=str(raw["tree_sha256"]).lower()
        if raw.get("tree_sha256")
        else None,
    )
    manifest_path = base.path / base.manifest
    if not manifest_path.exists():
        if base.required:
            raise ValueError(f"required input manifest is missing: {manifest_path}")
        return replace(base, availability="NOT_EVALUABLE", diagnostic="manifest missing")
    actual = _sha256(manifest_path)
    if actual != base.manifest_sha256:
        if base.required:
            raise ValueError(
                f"input manifest hash mismatch for {name}: expected "
                f"{base.manifest_sha256}, got {actual}"
            )
        return replace(
            base,
            availability="NOT_EVALUABLE",
            actual_manifest_sha256=actual,
            diagnostic="manifest hash mismatch",
        )
    if base.tree:
        tree_path = base.path / base.tree
        if not tree_path.exists():
            if base.required:
                raise ValueError(f"required tree input is missing: {tree_path}")
            return replace(base, availability="NOT_EVALUABLE", diagnostic="tree missing")
        if not base.tree_sha256 or _sha256(tree_path) != base.tree_sha256:
            if base.required:
                raise ValueError(f"input tree hash mismatch for {name}: {tree_path}")
            return replace(base, availability="NOT_EVALUABLE", diagnostic="tree hash mismatch")
    return replace(base, actual_manifest_sha256=actual)


def load_table_semantic_config(path: str | Path) -> TableSemanticConfig:
    """Load a bounded config and immediately reject input drift."""

    config_path = Path(path)
    raw = _read_mapping(config_path)
    scope = raw.get("scope")
    if not isinstance(scope, dict):
        raise ValueError("scope must be a mapping")
    inputs_raw = raw.get("inputs")
    if not isinstance(inputs_raw, dict):
        raise ValueError("inputs must be a mapping")
    inputs = {str(name): _resolve_input(str(name), value) for name, value in inputs_raw.items()}
    for required in ("physical_facts", "classification"):
        if required not in inputs:
            raise ValueError(f"missing required input configuration: {required}")

    registry = raw.get("relation_registry")
    if not isinstance(registry, dict) or not isinstance(registry.get("predicates"), dict):
        raise ValueError("relation_registry.predicates must be a mapping")
    predicates: dict[str, RelationPredicate] = {}
    for name, value in registry["predicates"].items():
        if not isinstance(value, dict):
            raise ValueError(f"relation predicate must be a mapping: {name}")
        predicate = RelationPredicate(
            name=str(name),
            directed=bool(value.get("directed", True)),
            symmetric=bool(value.get("symmetric", False)),
            min_direct_evidence=int(value.get("min_direct_evidence", 1)),
        )
        if predicate.directed and predicate.symmetric:
            raise ValueError(f"directed relation cannot be symmetric: {name}")
        if predicate.min_direct_evidence < 1:
            raise ValueError(f"precise relation needs direct evidence: {name}")
        predicates[predicate.name] = predicate
    if "RELATED_TO" not in predicates:
        raise ValueError("relation registry requires RELATED_TO fallback")

    seeds_raw = raw.get("semantic_seeds", {})
    if not isinstance(seeds_raw, dict):
        raise ValueError("semantic_seeds must be a mapping")
    seeds: dict[str, dict[str, tuple[str, ...]]] = {}
    for dimension in ("contexts", "anchors", "responsibilities"):
        values = seeds_raw.get(dimension, {})
        if not isinstance(values, dict):
            raise ValueError(f"semantic_seeds.{dimension} must be a mapping")
        seeds[dimension] = {
            str(label): tuple(str(term) for term in terms)
            for label, terms in values.items()
            if isinstance(terms, list)
        }

    variant_rules_raw = raw.get("variant_rules", [])
    if not isinstance(variant_rules_raw, list):
        raise ValueError("variant_rules must be a list")
    variant_rules = tuple(
        (str(item["id"]), str(item["pattern"]))
        for item in variant_rules_raw
        if isinstance(item, dict)
    )
    limits = _bounded_positive_ints(raw.get("limits", {}))
    if len(variant_rules) > limits.get("max_variant_rules", len(variant_rules)):
        raise ValueError("variant rule count exceeds configured hard limit")

    investigations = raw.get("investigation_sets", [])
    bodies = inputs_raw.get("approved_wiki_bodies", raw.get("approved_wiki_bodies", []))
    aggregates = raw.get("approved_test_aggregates", [])
    if not isinstance(investigations, list) or not all(isinstance(row, dict) for row in investigations):
        raise ValueError("investigation_sets must be a list of mappings")
    if not isinstance(bodies, list) or not all(isinstance(row, dict) for row in bodies):
        raise ValueError("approved_wiki_bodies must be a list of mappings")
    if not isinstance(aggregates, list) or not all(
        isinstance(row, dict) for row in aggregates
    ):
        raise ValueError("approved_test_aggregates must be a list of mappings")

    return TableSemanticConfig(
        version=str(raw.get("version", "v1")),
        scope_schema=str(scope["schema"]).upper(),
        object_types=tuple(str(value).upper() for value in scope.get("object_types", ["TABLE"])),
        expected_all_tables=int(scope.get("expected_all_tables", 0)),
        expected_subject_tables=int(scope.get("expected_subject_tables", 0)),
        expected_variant_or_other_tables=int(scope.get("expected_variant_or_other_tables", 0)),
        inputs=inputs,
        limits=limits,
        variant_rules=variant_rules or tuple(_DEFAULT_VARIANT_RULES),
        relation_registry_version=str(registry.get("version", "v1")),
        relation_predicates=predicates,
        semantic_seeds=seeds,
        investigation_sets=tuple(investigations),
        approved_wiki_bodies=tuple(bodies),
        approved_test_aggregates=tuple(aggregates),
        config_path=config_path,
        config_sha256=_sha256(config_path),
    )


def normalize_variant_name(
    object_name: str,
    rules: Iterable[tuple[str, str]] | None = None,
) -> tuple[str, str | None]:
    """Return one conservative base-name candidate and the matched rule."""

    normalized = object_name.strip().upper()
    configured = tuple(rules or _DEFAULT_VARIANT_RULES)
    priority = {name: index for index, (name, _) in enumerate(_DEFAULT_VARIANT_RULES)}
    ordered = sorted(configured, key=lambda item: priority.get(item[0], 100))
    for rule_id, pattern in ordered:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match and match.start() > 0:
            base = normalized[: match.start()].rstrip("_")
            if base:
                return base, rule_id
    return normalized, None


def _column_sets(columns: Iterable[Mapping[str, Any]]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for row in columns:
        result.setdefault(str(row.get("asset_id", "")), set()).add(
            str(row.get("column_name", "")).upper()
        )
    return result


def _key_sets(constraints: Iterable[Mapping[str, Any]]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for row in constraints:
        if str(row.get("constraint_type", "")).upper() not in {"PRIMARY_KEY", "UNIQUE"}:
            continue
        result.setdefault(str(row.get("asset_id", "")), set()).update(
            str(value).rsplit(":", 1)[-1].upper()
            for value in row.get("column_ids", [])
        )
    return result


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def classify_physical_variants(
    objects: Iterable[Mapping[str, Any]],
    columns: Iterable[Mapping[str, Any]],
    constraints: Iterable[Mapping[str, Any]],
    subject_asset_ids: set[str],
    *,
    rules: Iterable[tuple[str, str]] | None = None,
    max_candidates_per_table: int = 3,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Give every table an explicit subject/variant/standalone disposition."""

    object_rows = [dict(row) for row in objects]
    by_name = {str(row["object_name"]).upper(): row for row in object_rows}
    column_sets = _column_sets(columns)
    key_sets = _key_sets(constraints)
    dispositions: list[dict[str, Any]] = []
    grouped_members: dict[str, list[str]] = {}

    for row in sorted(object_rows, key=lambda item: str(item["asset_id"])):
        asset_id = str(row["asset_id"])
        name = str(row["object_name"]).upper()
        if asset_id in subject_asset_ids:
            dispositions.append(
                {
                    "asset_id": asset_id,
                    "object_name": name,
                    "disposition": "SUBJECT",
                    "base_name_candidate": name,
                    "variant_rule": None,
                    "candidate_parent_asset_ids": [],
                    "structure_similarity": None,
                    "limitations": [],
                }
            )
            continue

        base, rule_id = normalize_variant_name(name, rules)
        candidates: list[dict[str, Any]] = []
        direct = by_name.get(base)
        possible_parents = [direct] if direct else []
        if not direct and rule_id:
            possible_parents = [
                candidate
                for candidate_name, candidate in by_name.items()
                if candidate_name == base or candidate_name.startswith(base + "_")
                if str(candidate["asset_id"]) in subject_asset_ids
            ]
        for parent in possible_parents:
            if parent is None or str(parent["asset_id"]) == asset_id:
                continue
            parent_id = str(parent["asset_id"])
            column_similarity = _jaccard(column_sets.get(asset_id, set()), column_sets.get(parent_id, set()))
            key_similarity = _jaccard(key_sets.get(asset_id, set()), key_sets.get(parent_id, set()))
            comment_equal = bool(row.get("object_comment")) and row.get("object_comment") == parent.get("object_comment")
            candidates.append(
                {
                    "asset_id": parent_id,
                    "column_similarity": round(column_similarity, 6),
                    "key_similarity": round(key_similarity, 6),
                    "comment_equal": comment_equal,
                    "object_type_equal": row.get("object_type") == parent.get("object_type"),
                    "rank_score": round(column_similarity * 0.65 + key_similarity * 0.25 + (0.1 if comment_equal else 0.0), 6),
                }
            )
        candidates.sort(key=lambda item: (-float(item["rank_score"]), str(item["asset_id"])))
        candidates = candidates[:max_candidates_per_table]

        strong = [candidate for candidate in candidates if float(candidate["column_similarity"]) >= 0.8 and candidate["object_type_equal"]]
        if len(strong) == 1:
            disposition = "LIKELY_VARIANT"
        elif len(strong) > 1:
            disposition = "COMPETING_PARENT"
        elif rule_id and candidates:
            disposition = "UNKNOWN"
        else:
            disposition = "STANDALONE"
        parent_ids = [str(candidate["asset_id"]) for candidate in candidates]
        dispositions.append(
            {
                "asset_id": asset_id,
                "object_name": name,
                "disposition": disposition,
                "base_name_candidate": base,
                "variant_rule": rule_id,
                "candidate_parent_asset_ids": parent_ids,
                "structure_similarity": candidates,
                "limitations": [
                    "name normalization proposes a candidate; it does not prove backup, obsolescence, or equivalence"
                ],
            }
        )
        if parent_ids:
            grouped_members.setdefault(parent_ids[0], [parent_ids[0]]).append(asset_id)

    groups = [
        {
            "group_id": _stable_id("table-group", "PHYSICAL_VARIANT_GROUP", parent, *sorted(set(members))),
            "group_kind": "PHYSICAL_VARIANT_GROUP",
            "anchor_asset_id": parent,
            "member_asset_ids": sorted(set(members)),
            "status": "CANDIDATE",
            "method_id": "table_semantics.physical_variant.v1",
            "limitations": ["candidate physical variants are not declared equivalent"],
        }
        for parent, members in sorted(grouped_members.items())
        if len(set(members)) > 1
    ]
    return dispositions, groups


def _contains_term(text: str, term: str) -> bool:
    normalized = text.upper()
    candidate = term.upper()
    if re.fullmatch(r"[A-Z0-9_]+", candidate):
        return candidate in {token for token in re.split(r"[^A-Z0-9]+", normalized) if token}
    return candidate in text


def derive_name_comment_signals(
    table: Mapping[str, Any], config: TableSemanticConfig
) -> list[dict[str, Any]]:
    """Extract name and comment signals separately under one physical root."""

    asset_id = str(table["asset_id"])
    sources = (
        ("TABLE_NAME", str(table.get("object_name", ""))),
        ("TABLE_COMMENT", str(table.get("object_comment") or "")),
    )
    dimension_names = {
        "contexts": "BusinessContext",
        "anchors": "BusinessAnchor",
        "responsibilities": "TableResponsibility",
    }
    signals: list[dict[str, Any]] = []
    responsibility_by_source: dict[str, set[str]] = {}
    for source_kind, text in sources:
        for dimension, candidate_kind in dimension_names.items():
            matches: list[str] = []
            for label, terms in config.semantic_seeds.get(dimension, {}).items():
                if any(_contains_term(text, term) for term in terms):
                    matches.append(label)
            limit = int(config.limits.get(f"max_{dimension[:-1]}_candidates_per_table", 4))
            for rank, label in enumerate(sorted(matches)[:limit], start=1):
                signals.append(
                    {
                        "signal_id": _stable_id("table-signal", asset_id, source_kind, candidate_kind, label),
                        "asset_id": asset_id,
                        "candidate_kind": candidate_kind,
                        "candidate_value": label,
                        "source_kind": source_kind,
                        "source_text": text,
                        "root_source_family": f"physical-table:{asset_id}",
                        "rank": rank,
                        "method_score": round(1.0 / rank, 6),
                        "outcome": "CANDIDATE",
                        "conflict_key": None,
                        "vocabulary_layer": "SEED",
                        "observed_expression": text,
                        "recommended_profile_eligible": source_kind == "TABLE_COMMENT",
                    }
                )
                if candidate_kind == "TableResponsibility":
                    responsibility_by_source.setdefault(source_kind, set()).add(label)
    name_values = responsibility_by_source.get("TABLE_NAME", set())
    comment_values = responsibility_by_source.get("TABLE_COMMENT", set())
    if name_values and comment_values and name_values != comment_values:
        for signal in signals:
            if signal["candidate_kind"] == "TableResponsibility":
                signal["conflict_key"] = "responsibility"
                signal["outcome"] = "COMPETING"
    comment = str(table.get("object_comment") or "").strip()
    if comment:
        signals.append(
            {
                "signal_id": _stable_id(
                    "table-signal", asset_id, "TABLE_COMMENT", "TableResponsibility", comment
                ),
                "asset_id": asset_id,
                "candidate_kind": "TableResponsibility",
                "candidate_value": comment,
                "candidate_value_kind": "OBSERVED_EXPRESSION",
                "source_kind": "TABLE_COMMENT",
                "source_text": comment,
                "root_source_family": f"physical-table:{asset_id}",
                "rank": 1,
                "method_score": None,
                "outcome": "CANDIDATE",
                "conflict_key": None,
                "vocabulary_layer": "DISCOVERY",
                "observed_expression": comment,
                "recommended_profile_eligible": False,
            }
        )
    return signals


def validate_relation_candidate(
    predicate: RelationPredicate,
    subject_asset_id: str,
    object_asset_id: str,
    *,
    direct_evidence_refs: list[str],
    counterevidence_refs: list[str],
    known_asset_ids: set[str],
) -> dict[str, Any]:
    """Validate endpoints and downgrade unsupported precision safely."""

    missing = {subject_asset_id, object_asset_id} - known_asset_ids
    if missing:
        raise ValueError(f"unknown relation endpoint: {sorted(missing)}")
    enough = len(set(direct_evidence_refs)) >= predicate.min_direct_evidence
    effective = predicate.name if enough else "RELATED_TO"
    return {
        "relation_id": _stable_id("table-relation", subject_asset_id, effective, object_asset_id),
        "subject_asset_id": subject_asset_id,
        "predicate": effective,
        "requested_predicate": predicate.name,
        "object_asset_id": object_asset_id,
        "directed": predicate.directed if enough else False,
        "symmetric": predicate.symmetric if enough else True,
        "evidence_refs": sorted(set(direct_evidence_refs)),
        "counterevidence_refs": sorted(set(counterevidence_refs)),
        "outcome": "CANDIDATE" if enough and not counterevidence_refs else "UNKNOWN",
        "method_id": METHOD_ID,
        "method_version": METHOD_VERSION,
        "limitations": [] if enough else ["precise predicate lacked minimum direct evidence and was downgraded"],
    }


def build_physical_field_summaries(
    tables: Iterable[Mapping[str, Any]],
    columns: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Summarize bounded field patterns without declaring keys or table labels."""

    by_asset: dict[str, list[Mapping[str, Any]]] = {}
    for column in columns:
        by_asset.setdefault(str(column.get("asset_id", "")), []).append(column)
    summaries: list[dict[str, Any]] = []
    for table in sorted(tables, key=lambda row: str(row["asset_id"])):
        asset_id = str(table["asset_id"])
        table_columns = by_asset.get(asset_id, [])
        column_names = sorted(
            {str(row.get("column_name", "")).upper() for row in table_columns}
        )
        markers: dict[str, list[str]] = {}
        for marker, terms in _FIELD_MARKERS.items():
            names = sorted(
                {
                    str(row.get("column_name", "")).upper()
                    for row in table_columns
                    if any(term in str(row.get("column_name", "")).upper() for term in terms)
                }
            )
            if names:
                markers[marker] = names
        summaries.append(
            {
                "asset_id": asset_id,
                "availability": "AVAILABLE",
                "field_count": len(table_columns),
                "column_names": column_names,
                "column_signature_sha256": hashlib.sha256(
                    "|".join(column_names).encode("utf-8")
                ).hexdigest(),
                "markers": markers,
                "root_source_families": [f"physical-table:{asset_id}"],
                "interpretation": "bounded recall support only; shared fields are not declared foreign keys or table-label votes",
            }
        )
    return summaries


def _read_json_rows(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise ValueError(f"expected JSON row list: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"expected JSON object at {path}:{line_number}")
        rows.append(value)
    return rows


def inspect_input_states(config: TableSemanticConfig) -> list[dict[str, Any]]:
    """Return logical locations, hashes, sizes, and availability without secrets."""

    states: list[dict[str, Any]] = []
    for name, spec in sorted(config.inputs.items()):
        manifest_path = spec.path / spec.manifest
        available = manifest_path.exists()
        states.append(
            {
                "input_name": name,
                "logical_path": spec.path.as_posix(),
                "manifest_name": spec.manifest,
                "manifest_sha256": spec.manifest_sha256,
                "actual_manifest_sha256": spec.actual_manifest_sha256,
                "availability": spec.availability if available else "NOT_EVALUABLE",
                "diagnostic": spec.diagnostic,
                "required": spec.required,
                "tree_name": spec.tree,
                "tree_sha256": spec.tree_sha256,
            }
        )
    states.append(
        {
            "input_name": "approved_wiki_bodies",
            "logical_path": "configured-page-list",
            "availability": "AVAILABLE" if config.approved_wiki_bodies else "NOT_EVALUABLE",
            "approved_page_count": len(config.approved_wiki_bodies),
            "required": False,
        }
    )
    for aggregate in config.approved_test_aggregates:
        states.append(
            {
                "input_name": "approved_test_aggregate",
                "logical_path": "configured-aggregate:" + str(aggregate.get("evidence_id", "UNKNOWN")),
                "availability": "CONFIGURED_UNVALIDATED",
                "adoption_status": "PENDING_VALIDATION",
                "required": False,
                "environment": aggregate.get("environment"),
                "observed_at": aggregate.get("observed_at"),
                "query_sha256": aggregate.get("query_sha256"),
                "contains_business_key_values": False,
                "contains_business_rows": False,
            }
        )
    return states


def validate_result_contracts(result: TableSemanticResult) -> None:
    """Validate required fields and cross-file references before writing."""

    required = {
        "table_profiles": {"asset_id", "object_name", "disposition", "candidate_summary"},
        "context_candidates": {"candidate_id", "asset_id", "candidate_value", "outcome"},
        "anchor_candidates": {"candidate_id", "asset_id", "candidate_value", "outcome"},
        "responsibility_candidates": {"candidate_id", "asset_id", "candidate_value", "outcome"},
        "table_groups": {"group_id", "group_kind", "status"},
        "group_memberships": {"membership_id", "group_id", "asset_id", "responsibility"},
        "table_relations": {"relation_id", "subject_asset_id", "predicate", "object_asset_id", "outcome"},
        "assertions": {"assertion_id", "subject_id", "predicate", "evidence_refs", "outcome"},
        "evidence_refs": {"evidence_id", "source_kind", "source_locator", "root_source_family"},
        "review_decisions": {"decision_id", "assertion_id", "decision", "reason"},
    }
    evidence_ids = {str(row["evidence_id"]) for row in result.evidence_refs}
    group_ids = {str(row["group_id"]) for row in result.table_groups}
    assertion_ids = {str(row["assertion_id"]) for row in result.assertions}
    for collection_name, fields in required.items():
        for index, row in enumerate(getattr(result, collection_name)):
            missing = fields - row.keys()
            if missing:
                raise ValueError(f"{collection_name}[{index}] missing fields: {sorted(missing)}")
    for assertion in result.assertions:
        dangling = set(assertion.get("evidence_refs", [])) | set(assertion.get("counterevidence_refs", []))
        dangling -= evidence_ids
        if dangling:
            raise ValueError(f"assertion has missing evidence references: {sorted(dangling)}")
        if assertion.get("outcome") == "ACCEPTED" and not assertion.get("review_decision_ref"):
            raise ValueError("automatic ACCEPTED assertion is forbidden")
    for membership in result.group_memberships:
        if str(membership["group_id"]) not in group_ids:
            raise ValueError(f"membership references unknown group: {membership['group_id']}")
    for decision in result.review_decisions:
        if str(decision["assertion_id"]) not in assertion_ids:
            raise ValueError(f"review decision references unknown assertion: {decision['assertion_id']}")


def apply_table_review_decisions(
    result: TableSemanticResult,
    decisions: Iterable[Mapping[str, Any]],
) -> TableSemanticResult:
    """Attach human dispositions without rewriting machine candidates or evidence."""

    assertions = {str(row["assertion_id"]): row for row in result.assertions}
    allowed = {"ACCEPT", "REJECT", "REVISE", "DEFER"}
    for raw in decisions:
        assertion_id = str(raw.get("assertion_id", ""))
        if assertion_id not in assertions:
            raise ValueError(f"review decision references unknown assertion: {assertion_id}")
        decision = str(raw.get("decision", "")).upper()
        if decision not in allowed:
            raise ValueError(f"unsupported review decision: {decision}")
        reason = str(raw.get("reason", "")).strip()
        if not reason:
            raise ValueError("review decision reason is required")
        decision_id = _stable_id("review-decision", assertion_id, decision, reason)
        review = {
            "decision_id": decision_id,
            "assertion_id": assertion_id,
            "decision": decision,
            "reason": reason,
            "reviewer": str(raw.get("reviewer", "human-review")),
            "revised_value": raw.get("revised_value"),
        }
        result.review_decisions.append(review)
        assertions[assertion_id]["review_decision_ref"] = decision_id
    validate_result_contracts(result)
    return result


def _evidence_from_signal(signal: Mapping[str, Any]) -> dict[str, Any]:
    evidence_id = _stable_id("evidence", signal["signal_id"])
    return {
        "evidence_id": evidence_id,
        "source_kind": signal["source_kind"],
        "source_locator": f"{signal['asset_id']}#{signal['source_kind']}",
        "root_source_family": signal["root_source_family"],
        "content_excerpt": signal["source_text"],
        "availability": "AVAILABLE",
        "supports": [signal["candidate_value"]],
        "limitations": ["metadata text proposes a candidate; it is not business acceptance"],
    }


def _candidate_from_signal(signal: Mapping[str, Any], evidence_id: str) -> dict[str, Any]:
    candidate_id = _stable_id(
        "table-candidate",
        signal["asset_id"],
        signal["candidate_kind"],
        signal["candidate_value"],
        signal["source_kind"],
    )
    return {
        "candidate_id": candidate_id,
        "asset_id": signal["asset_id"],
        "candidate_value": signal["candidate_value"],
        "source_kind": signal["source_kind"],
        "evidence_refs": [evidence_id],
        "counterevidence_refs": [],
        "root_source_families": [signal["root_source_family"]],
        "method_id": "table_semantics.table_text_signal.v1",
        "method_version": METHOD_VERSION,
        "method_score": signal["method_score"],
        "rank": signal["rank"],
        "outcome": signal["outcome"],
        "review_status": "UNREVIEWED",
        "conflict_key": signal["conflict_key"],
        "candidate_value_kind": signal.get("candidate_value_kind", "NORMALIZED_SEED"),
        "vocabulary_layer": signal.get("vocabulary_layer", "SEED"),
        "observed_expression": signal.get("observed_expression"),
        "recommended_profile_eligible": bool(
            signal.get("recommended_profile_eligible", False)
        ),
    }


def _assertion_from_candidate(
    candidate: Mapping[str, Any], predicate: str
) -> dict[str, Any]:
    assertion_id = _stable_id("assertion", candidate["candidate_id"])
    return {
        "assertion_id": assertion_id,
        "subject_id": candidate["asset_id"],
        "predicate": predicate,
        "object_value": candidate["candidate_value"],
        "method_id": candidate["method_id"],
        "method_version": candidate["method_version"],
        "evidence_refs": list(candidate["evidence_refs"]),
        "counterevidence_refs": list(candidate["counterevidence_refs"]),
        "root_source_families": list(candidate["root_source_families"]),
        "method_score": candidate["method_score"],
        "outcome": candidate["outcome"],
        "review_decision_ref": None,
    }


def _load_structural_groups(
    classification_root: Path,
    known_asset_ids: set[str],
    max_neighbors: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    candidates_path = classification_root / "panorama/candidates/family_candidates.json"
    memberships_path = classification_root / "panorama/candidates/family_memberships.json"
    edges_path = classification_root / "panorama/derived/similarity_edges.json"
    if not candidates_path.exists() or not memberships_path.exists() or not edges_path.exists():
        return [], [], [{"code": "STRUCTURAL_INPUT_NOT_EVALUABLE", "severity": "WARNING"}]
    candidates = _read_json_rows(candidates_path)
    memberships = _read_json_rows(memberships_path)
    edges = _read_json_rows(edges_path)
    by_family: dict[str, list[dict[str, Any]]] = {}
    for row in memberships:
        if str(row.get("asset_id")) in known_asset_ids:
            by_family.setdefault(str(row["family_candidate_id"]), []).append(row)
    groups: list[dict[str, Any]] = []
    output_memberships: list[dict[str, Any]] = []
    candidate_by_id = {str(row["family_candidate_id"]): row for row in candidates}
    for family_id, member_rows in sorted(by_family.items()):
        group_id = _stable_id("table-group", "STRUCTURAL_NEIGHBORHOOD", family_id)
        source = candidate_by_id.get(family_id, {})
        groups.append(
            {
                "group_id": group_id,
                "group_kind": "STRUCTURAL_NEIGHBORHOOD",
                "source_group_id": family_id,
                "status": "INVESTIGATION_HINT",
                "method_id": source.get("clustering_method", "family.panorama.leiden.v1"),
                "method_score": None,
                "limitations": ["structural neighborhood is not a business collaboration group"],
            }
        )
        for member in sorted(member_rows, key=lambda item: str(item["asset_id"])):
            output_memberships.append(
                {
                    "membership_id": _stable_id("membership", group_id, member["asset_id"]),
                    "group_id": group_id,
                    "asset_id": member["asset_id"],
                    "responsibility": "STRUCTURAL_NEIGHBOR",
                    "status": "INVESTIGATION_HINT",
                    "evidence_refs": [],
                    "method_score": member.get("membership_score"),
                    "limitations": ["membership score is method-local and not a business probability"],
                }
            )
    edge_counts: dict[str, int] = {}
    bounded_edges: list[dict[str, Any]] = []
    for edge in sorted(edges, key=lambda row: (-float(row.get("combined_score", 0.0)), str(row.get("left_asset_id")), str(row.get("right_asset_id")))):
        left = str(edge.get("left_asset_id"))
        right = str(edge.get("right_asset_id"))
        if left not in known_asset_ids or right not in known_asset_ids:
            continue
        if edge_counts.get(left, 0) >= max_neighbors or edge_counts.get(right, 0) >= max_neighbors:
            continue
        edge_counts[left] = edge_counts.get(left, 0) + 1
        edge_counts[right] = edge_counts.get(right, 0) + 1
        bounded_edges.append(
            {
                "code": "STRUCTURAL_EDGE_HINT",
                "left_asset_id": left,
                "right_asset_id": right,
                "method_id": edge.get("method_id"),
                "method_score": edge.get("combined_score"),
                "graph_run_id": edge.get("graph_run_id"),
                "interpretation": "investigation recall only",
            }
        )
    return groups, output_memberships, bounded_edges


def _load_structural_propagation_hints(
    classification_root: Path,
    known_asset_ids: set[str],
) -> list[dict[str, Any]]:
    """Import legacy labels as visibly separate, non-recommended hints."""

    path = classification_root / "panorama/candidates/business_class_candidates.json"
    if not path.exists():
        return []
    hints: list[dict[str, Any]] = []
    for row in _read_json_rows(path):
        subject_id = str(row.get("subject_id", ""))
        if subject_id not in known_asset_ids:
            continue
        hints.append(
            {
                "hint_id": _stable_id("structural-propagation-hint", row.get("candidate_id")),
                "asset_id": subject_id,
                "dimension": row.get("dimension"),
                "label": row.get("label"),
                "source_candidate_id": row.get("candidate_id"),
                "source_method_id": row.get("method_id"),
                "source_method_version": row.get("method_version"),
                "method_score": row.get("raw_method_score"),
                "propagated_from_asset_ids": row.get("propagated_from_asset_ids", []),
                "status": "STRUCTURAL_PROPAGATION_HINT",
                "recommended_profile_eligible": False,
                "limitations": [
                    "legacy taxonomy/propagation result is retained for comparison only",
                    "method score is not a probability and does not independently support a table semantic label",
                ],
            }
        )
    return hints


def _augment_field_support(
    summaries: list[dict[str, Any]],
    config: TableSemanticConfig,
) -> list[dict[str, Any]]:
    """Attach optional field candidates without creating table candidates."""

    spec = config.inputs.get("field_semantics")
    if not spec or spec.availability != "AVAILABLE" or not (spec.path / spec.manifest).exists():
        for summary in summaries:
            summary["semantic_assistance"] = {"availability": "NOT_EVALUABLE", "candidate_count": 0}
            summary["context_assistance"] = {"availability": "NOT_EVALUABLE", "assertion_count": 0}
            summary["field_assistance_status"] = "NOT_EVALUABLE"
            summary["assertion_links"] = []
        return summaries
    results_path = spec.path / "field_semantic_results.jsonl"
    if not results_path.exists():
        for summary in summaries:
            summary["semantic_assistance"] = {"availability": "NOT_EVALUABLE", "candidate_count": 0}
            summary["context_assistance"] = {"availability": "NOT_EVALUABLE", "assertion_count": 0}
            summary["field_assistance_status"] = "NOT_EVALUABLE"
            summary["assertion_links"] = []
        return summaries
    counts: dict[str, int] = {}
    outcomes: dict[str, set[str]] = {}
    candidate_details: dict[str, list[dict[str, Any]]] = {}
    try:
        field_rows = _read_jsonl(results_path)
    except (OSError, ValueError, json.JSONDecodeError):
        for summary in summaries:
            summary["semantic_assistance"] = {
                "availability": "NOT_EVALUABLE",
                "candidate_count": 0,
                "diagnostic": "field semantic rows are partially invalid",
            }
            summary["context_assistance"] = {"availability": "NOT_EVALUABLE", "assertion_count": 0}
            summary["field_assistance_status"] = "NOT_EVALUABLE"
            summary["assertion_links"] = []
        return summaries
    for row in field_rows:
        asset_id = str(row.get("asset_id", ""))
        counts[asset_id] = counts.get(asset_id, 0) + len(row.get("candidate_bindings", []))
        outcomes.setdefault(asset_id, set()).add(str(row.get("outcome", "UNKNOWN")))
        candidate_details.setdefault(asset_id, []).append(
            {
                "column_id": row.get("column_id"),
                "column_name": row.get("column_name"),
                "column_comment": row.get("column_comment"),
                "outcome": row.get("outcome", "UNKNOWN"),
                "review_status": row.get("review_status"),
                "usage_status": "NOT_USED",
                "table_assertion_links": [],
                "candidate_bindings": [
                    {
                        "binding_id": binding.get("binding_id"),
                        "concept_id": binding.get("concept_id"),
                        "relation_kind": binding.get("relation_kind"),
                        "status": binding.get("status"),
                        "source_refs": list(binding.get("source_refs", [])),
                    }
                    for binding in row.get("candidate_bindings", [])
                    if isinstance(binding, dict)
                ],
            }
        )
    for summary in summaries:
        asset_id = str(summary["asset_id"])
        summary["semantic_assistance"] = {
            "availability": "AVAILABLE",
            "candidate_count": counts.get(asset_id, 0),
            "source_outcomes": sorted(outcomes.get(asset_id, set())),
            "field_candidates": candidate_details.get(asset_id, [])[:24],
            "field_candidates_truncated": max(
                0, len(candidate_details.get(asset_id, [])) - 24
            ),
            "role": "SUPPORT_DISTINGUISH_OR_COUNTEREVIDENCE_ONLY",
            "voting_enabled": False,
        }
        summary["field_assistance_status"] = "NOT_USED"
        summary["assertion_links"] = []
    context_spec = config.inputs.get("field_context")
    context_path = context_spec.path / "assertions.jsonl" if context_spec else None
    context_counts: dict[str, int] = {}
    context_statuses: dict[str, set[str]] = {}
    summary_asset_ids = {str(summary["asset_id"]) for summary in summaries}
    if context_spec and context_spec.availability == "AVAILABLE" and context_path and context_path.exists():
        try:
            context_rows = _read_jsonl(context_path)
        except (OSError, ValueError, json.JSONDecodeError):
            context_rows = []
            context_available = False
        else:
            context_available = True
        for row in context_rows:
            physical_ids = [str(row.get("subject_id", "")), str(row.get("object_id", ""))]
            for value in physical_ids:
                asset_id = value.split(":COLUMN:", 1)[0] if ":COLUMN:" in value else ""
                if asset_id in summary_asset_ids:
                    context_counts[asset_id] = context_counts.get(asset_id, 0) + 1
                    context_statuses.setdefault(asset_id, set()).add(str(row.get("status", "UNKNOWN")))
    else:
        context_available = False
    for summary in summaries:
        asset_id = str(summary["asset_id"])
        summary["context_assistance"] = {
            "availability": "AVAILABLE" if context_available else "NOT_EVALUABLE",
            "assertion_count": context_counts.get(asset_id, 0),
            "source_statuses": sorted(context_statuses.get(asset_id, set())),
            "source_manifest_sha256": context_spec.manifest_sha256 if context_spec else None,
            "role": "SUPPORT_DISTINGUISH_OR_COUNTEREVIDENCE_ONLY",
            "voting_enabled": False,
        }
    return summaries


_FIELD_RESPONSIBILITY_SUPPORT: Mapping[str, tuple[str, int]] = {
    "APPROVAL_AUDIT": ("APPROVAL_OR_AUDIT_TRAIL", 2),
    "EVENT_MARKER": ("LIFECYCLE_EVENT", 2),
    "CONFIGURATION_ID": ("CONFIGURATION", 1),
    "SOURCE_TARGET": ("MAPPING_DEFINITION", 2),
}


def _link_field_support_to_assertions(
    result: TableSemanticResult,
    summaries: list[dict[str, Any]],
) -> None:
    """Attach physical field combinations to the exact assertions they support."""

    assertions_by_subject_value = {
        (str(row.get("subject_id")), str(row.get("object_value"))): row
        for row in result.assertions
        if row.get("predicate") == "HAS_TABLE_RESPONSIBILITY_CANDIDATE"
    }
    candidates_by_assertion = {
        _stable_id("assertion", row["candidate_id"]): row
        for row in result.responsibility_candidates
    }
    for summary in summaries:
        asset_id = str(summary["asset_id"])
        links: list[dict[str, Any]] = []
        for marker, (responsibility, minimum_fields) in _FIELD_RESPONSIBILITY_SUPPORT.items():
            column_names = sorted(set(summary.get("markers", {}).get(marker, [])))
            if len(column_names) < minimum_fields:
                continue
            assertion = assertions_by_subject_value.get((asset_id, responsibility))
            if not assertion:
                continue
            evidence_id = _stable_id(
                "evidence", "FIELD_COMBINATION", asset_id, marker, *column_names
            )
            if not any(row.get("evidence_id") == evidence_id for row in result.evidence_refs):
                result.evidence_refs.append(
                    {
                        "evidence_id": evidence_id,
                        "source_kind": "FIELD_COMBINATION",
                        "source_locator": f"{asset_id}#{marker}",
                        "root_source_family": f"physical-fields:{asset_id}:{marker}",
                        "content_excerpt": ", ".join(column_names),
                        "availability": "AVAILABLE",
                        "supports": [responsibility],
                        "source_column_names": column_names,
                        "limitations": [
                            "field combination supports a table-level candidate; it does not prove row-level behavior"
                        ],
                    }
                )
            if evidence_id not in assertion["evidence_refs"]:
                assertion["evidence_refs"].append(evidence_id)
            root_family = f"physical-fields:{asset_id}:{marker}"
            if root_family not in assertion["root_source_families"]:
                assertion["root_source_families"].append(root_family)
            candidate = candidates_by_assertion.get(str(assertion["assertion_id"]))
            if candidate:
                if evidence_id not in candidate["evidence_refs"]:
                    candidate["evidence_refs"].append(evidence_id)
                if root_family not in candidate["root_source_families"]:
                    candidate["root_source_families"].append(root_family)
            links.append(
                {
                    "assertion_id": assertion["assertion_id"],
                    "candidate_value": responsibility,
                    "role": "SUPPORTS",
                    "marker": marker,
                    "source_column_names": column_names,
                    "evidence_refs": [evidence_id],
                }
            )
            for field_candidate in summary.get("semantic_assistance", {}).get(
                "field_candidates", []
            ):
                if str(field_candidate.get("column_name", "")).upper() not in set(
                    column_names
                ):
                    continue
                field_candidate["usage_status"] = "USED_AS_PHYSICAL_COMBINATION"
                field_candidate.setdefault("table_assertion_links", []).append(
                    {
                        "assertion_id": assertion["assertion_id"],
                        "role": "SUPPORTS",
                        "evidence_refs": [evidence_id],
                    }
                )
        summary["assertion_links"] = links
        if links:
            summary["field_assistance_status"] = "USED"
        elif summary.get("semantic_assistance", {}).get("availability") == "AVAILABLE":
            summary["field_assistance_status"] = "NOT_USED"
        else:
            summary["field_assistance_status"] = "NOT_EVALUABLE"


def extract_approved_wiki_body_evidence(
    approved_pages: Iterable[Mapping[str, Any]],
    tables: Iterable[Mapping[str, Any]],
    *,
    max_reads: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read only explicitly pinned body files and extract table mentions."""

    table_by_name = {str(row["object_name"]).upper(): row for row in tables}
    evidence: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for index, page in enumerate(approved_pages):
        if index >= max_reads:
            diagnostics.append({"code": "WIKI_BODY_BUDGET_EXCEEDED", "severity": "WARNING", "limit": max_reads})
            break
        path = Path(str(page.get("path", "")))
        if not path.exists():
            diagnostics.append({"code": "WIKI_BODY_MISSING", "page_id": page.get("page_id"), "path": path.as_posix()})
            continue
        expected_hash = str(page.get("sha256", "")).lower()
        if not expected_hash or _sha256(path) != expected_hash:
            diagnostics.append({"code": "WIKI_BODY_HASH_MISMATCH", "page_id": page.get("page_id"), "path": path.as_posix()})
            continue
        text = path.read_text(encoding="utf-8")
        mentioned = sorted(name for name in table_by_name if name in text.upper())
        usage_terms = ("用途", "用于", "承载", "记录", "输入", "输出", "同步", "usage", "used for")
        for name in mentioned:
            table = table_by_name[name]
            evidence.append(
                {
                    "wiki_candidate_id": _stable_id("wiki-body", page.get("page_id"), name),
                    "asset_id": table["asset_id"],
                    "page_id": str(page.get("page_id")),
                    "page_version": page.get("version"),
                    "title": page.get("title"),
                    "ancestor_path": list(page.get("ancestor_path", [])),
                    "document_context_only": False,
                    "body_sha256": expected_hash,
                    "section": page.get("section"),
                    "evidence_kind": (
                        "MULTI_TABLE_ASSOCIATION"
                        if len(mentioned) > 1
                        else "USAGE_DESCRIPTION"
                        if any(term in text.lower() for term in usage_terms)
                        else "MENTIONS_TABLE"
                    ),
                    "mentioned_table_names": mentioned,
                    "outcome": "CANDIDATE",
                    "limitations": ["documented association is not automatic human confirmation or production truth"],
                }
            )
    return evidence, diagnostics


def _wiki_paths(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(row.get("pageId")): row for row in rows}
    output: list[dict[str, Any]] = []
    for row in rows:
        path: list[str] = []
        current: Mapping[str, Any] | None = row
        seen: set[str] = set()
        while current:
            page_id = str(current.get("pageId"))
            if page_id in seen:
                break
            seen.add(page_id)
            path.append(str(current.get("title", "")))
            parent = current.get("parentPageId")
            current = by_id.get(str(parent)) if parent else None
        output.append({**row, "ancestor_path": list(reversed(path))})
    return output


def _wiki_recall(
    tables: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    anchor_candidates: list[dict[str, Any]],
    config: TableSemanticConfig,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    spec = config.inputs.get("wiki_tree")
    diagnostics: list[dict[str, Any]] = []
    if not spec or spec.availability != "AVAILABLE" or not spec.tree or not (spec.path / spec.tree).exists():
        return [], [{"code": "WIKI_TREE_NOT_EVALUABLE", "severity": "WARNING"}]
    wiki_rows = _wiki_paths(_read_jsonl(spec.path / spec.tree))
    summary_by_asset = {str(row["asset_id"]): row for row in summaries}
    anchors_by_asset: dict[str, set[str]] = {}
    for candidate in anchor_candidates:
        anchors_by_asset.setdefault(str(candidate["asset_id"]), set()).add(
            str(candidate["candidate_value"]).upper()
        )
    per_table = config.limits.get("max_wiki_candidates_per_table", 5)
    total_limit = config.limits.get("max_wiki_candidates_total", 800)
    candidates_by_asset: dict[str, list[dict[str, Any]]] = {}
    for table in sorted(tables, key=lambda row: str(row["asset_id"])):
        asset_id = str(table["asset_id"])
        name_tokens = {token for token in re.split(r"[^A-Z0-9]+", str(table["object_name"]).upper()) if len(token) >= 3}
        comment = str(table.get("object_comment") or "")
        marker_tokens = set(summary_by_asset.get(asset_id, {}).get("markers", {}))
        marker_tokens.update(
            column_name
            for names in summary_by_asset.get(asset_id, {}).get("markers", {}).values()
            for column_name in names
        )
        marker_tokens.update(anchors_by_asset.get(asset_id, set()))
        ranked: list[tuple[int, str, dict[str, Any], list[str]]] = []
        for page in wiki_rows:
            title = str(page.get("title", ""))
            title_upper = title.upper()
            hits = sorted(token for token in name_tokens if token in title_upper)
            if comment and len(comment) >= 3 and comment in title:
                hits.append("TABLE_COMMENT")
            hits.extend(sorted(marker for marker in marker_tokens if marker in title_upper))
            if hits:
                ranked.append((-len(set(hits)), str(page.get("pageId")), page, sorted(set(hits))))
        table_candidates: list[dict[str, Any]] = []
        for rank, (_, page_id, page, hits) in enumerate(sorted(ranked)[:per_table], start=1):
            table_candidates.append(
                {
                    "wiki_candidate_id": _stable_id("wiki-candidate", asset_id, page_id),
                    "asset_id": asset_id,
                    "page_id": page_id,
                    "title": page.get("title"),
                    "ancestor_path": page.get("ancestor_path", []),
                    "document_context_only": True,
                    "match_terms": hits,
                    "rank": rank,
                    "evidence_kind": "NAVIGATION_CONTEXT",
                    "outcome": "CANDIDATE",
                    "limitations": ["directory parentage is not a table category or business hierarchy"],
                }
            )
        candidates_by_asset[asset_id] = table_candidates
    candidates: list[dict[str, Any]] = []
    asset_ids = sorted(candidates_by_asset)
    for rank_index in range(per_table):
        for asset_id in asset_ids:
            rows = candidates_by_asset[asset_id]
            if rank_index >= len(rows):
                continue
            if len(candidates) >= total_limit:
                break
            candidates.append(rows[rank_index])
        if len(candidates) >= total_limit:
            break
    eligible_tables = sum(bool(rows) for rows in candidates_by_asset.values())
    covered_tables = len({str(row["asset_id"]) for row in candidates})
    selected_ids = {str(row["wiki_candidate_id"]) for row in candidates}
    available_count = sum(len(rows) for rows in candidates_by_asset.values())
    diagnostics.append(
        {
            "code": "WIKI_RECALL_COVERAGE",
            "severity": "INFO",
            "eligible_tables": eligible_tables,
            "covered_tables": covered_tables,
            "truncated_tables": max(0, eligible_tables - covered_tables),
            "available_candidates": available_count,
            "selected_candidates": len(candidates),
            "total_limit": total_limit,
            "selection_method": "DETERMINISTIC_ROUND_ROBIN_BY_RANK",
        }
    )
    if available_count > len(selected_ids):
        diagnostics.append(
            {
                "code": "WIKI_RECALL_TRUNCATED",
                "severity": "WARNING",
                "limit": total_limit,
                "omitted_candidates": available_count - len(selected_ids),
            }
        )
    body_candidates, body_diagnostics = extract_approved_wiki_body_evidence(
        config.approved_wiki_bodies,
        tables,
        max_reads=config.limits.get("max_wiki_body_reads", 0),
    )
    candidates.extend(body_candidates)
    diagnostics.extend(body_diagnostics)
    if not config.approved_wiki_bodies:
        diagnostics.append(
            {
                "code": "WIKI_BODY_NOT_EVALUABLE",
                "severity": "INFO",
                "reason": "no fixed body page was explicitly approved; no body read was attempted",
            }
        )
    return candidates, diagnostics


def _relation_evidence(
    result: TableSemanticResult,
    source_kind: str,
    locator: str,
    root_family: str,
    excerpt: str,
) -> str:
    evidence_id = _stable_id("evidence", source_kind, locator, excerpt)
    if not any(row["evidence_id"] == evidence_id for row in result.evidence_refs):
        result.evidence_refs.append(
            {
                "evidence_id": evidence_id,
                "source_kind": source_kind,
                "source_locator": locator,
                "root_source_family": root_family,
                "content_excerpt": excerpt,
                "availability": "AVAILABLE",
                "supports": [],
                "limitations": [],
            }
        )
    return evidence_id


def _aggregate_scope_sha256(aggregate: Mapping[str, Any]) -> str:
    payload = {
        name: str(aggregate.get(name, ""))
        for name in (
            "environment",
            "subject_table",
            "subject_key",
            "predicate",
            "object_table",
            "object_key",
            "query_sha256",
        )
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _aggregate_relation_is_eligible(
    aggregate: Mapping[str, Any],
    subject_columns: set[str],
    object_columns: set[str],
) -> tuple[bool, list[str]]:
    """Validate a frozen test snapshot without treating it as production truth."""

    reasons: list[str] = []
    if str(aggregate.get("environment", "")).upper() != "TEST":
        reasons.append("aggregate environment is not TEST")
    if not re.fullmatch(r"[0-9a-f]{64}", str(aggregate.get("query_sha256", ""))):
        reasons.append("query fingerprint is missing or invalid")
    if not str(aggregate.get("observed_at", "")).strip():
        reasons.append("snapshot timestamp is missing")
    subject_key = str(aggregate.get("subject_key", "")).upper()
    object_key = str(aggregate.get("object_key", "")).upper()
    if not subject_key or subject_key not in subject_columns:
        reasons.append("subject key is missing from the subject table")
    if not object_key or object_key not in object_columns:
        reasons.append("object key is missing from the object table")
    if aggregate.get("authorization_scope_sha256") != _aggregate_scope_sha256(aggregate):
        reasons.append("authorization scope does not match endpoints, keys and query fingerprint")
    prohibited = {"rows", "samples", "sample_values", "key_values", "business_rows"}
    if prohibited & set(aggregate):
        reasons.append("aggregate contains prohibited row or key samples")

    def count(name: str) -> int:
        try:
            value = int(aggregate.get(name, -1))
        except (TypeError, ValueError):
            reasons.append(f"{name} is not an integer")
            return -1
        if value < 0:
            reasons.append(f"{name} is missing or negative")
        return value

    event_rows = count("event_rows")
    event_non_null = count("event_non_null")
    matched_event_rows = count("matched_event_rows")
    unmatched_event_rows = count("unmatched_event_rows")
    contract_rows = count("contract_rows")
    contract_non_null = count("contract_non_null")
    contract_distinct_keys = count("contract_distinct_keys")
    event_distinct_keys = count("event_distinct_keys")
    contracts_with_events = count("contracts_with_events")
    deal_keys_with_multiple_events = count("deal_keys_with_multiple_events")
    max_events_per_deal = count("max_events_per_deal")

    if min(
        event_rows,
        event_distinct_keys,
        contract_rows,
        matched_event_rows,
        contracts_with_events,
    ) <= 0:
        reasons.append("aggregate contains no positive relationship evidence")
    if event_rows != event_non_null:
        reasons.append("event keys contain nulls")
    if matched_event_rows != event_rows or unmatched_event_rows != 0:
        reasons.append("event keys are not fully matched")
    if contract_rows != contract_non_null or contract_distinct_keys != contract_rows:
        reasons.append("contract target key is not unique")
    if event_distinct_keys != contracts_with_events:
        reasons.append("matched contract cardinality is inconsistent")
    if event_distinct_keys > event_rows:
        reasons.append("event distinct keys exceed event rows")
    if contracts_with_events > contract_distinct_keys:
        reasons.append("matched contracts exceed available unique contracts")
    if deal_keys_with_multiple_events > event_distinct_keys:
        reasons.append("multi-event key count exceeds event distinct keys")
    if event_rows > event_distinct_keys and max_events_per_deal < 2:
        reasons.append("maximum event multiplicity contradicts repeated event keys")
    return not reasons, reasons


def _build_approved_aggregate_relations(
    result: TableSemanticResult,
    tables: list[dict[str, Any]],
    config: TableSemanticConfig,
) -> None:
    """Build precise candidates from explicitly frozen, bounded test aggregates."""

    known = {str(row["asset_id"]) for row in tables}
    by_name = {str(row["object_name"]).upper(): row for row in tables}
    fields = {
        str(row["asset_id"]): {str(name).upper() for name in row.get("column_names", [])}
        for row in result.field_support_summaries
    }
    for aggregate in config.approved_test_aggregates:
        evidence_id = str(aggregate.get("evidence_id", "UNKNOWN"))
        subject = by_name.get(str(aggregate.get("subject_table", "")).upper())
        target = by_name.get(str(aggregate.get("object_table", "")).upper())
        predicate = config.relation_predicates.get(str(aggregate.get("predicate", "")))
        subject_id = str(subject["asset_id"]) if subject else ""
        target_id = str(target["asset_id"]) if target else ""
        eligible, reasons = _aggregate_relation_is_eligible(
            aggregate,
            fields.get(subject_id, set()),
            fields.get(target_id, set()),
        )
        if not subject or not target or not predicate:
            reasons.append("relation endpoint or predicate is not registered")
            eligible = False
        metadata_refs = sorted(
            {
                evidence_ref
                for candidate in result.responsibility_candidates
                if str(candidate.get("asset_id")) == subject_id
                and candidate.get("candidate_value") == "LIFECYCLE_EVENT"
                and candidate.get("source_kind") == "TABLE_COMMENT"
                for evidence_ref in candidate.get("evidence_refs", [])
            }
        )
        if not metadata_refs:
            reasons.append("independent lifecycle-event metadata evidence is missing")
            eligible = False
        if not eligible:
            result.diagnostics.append(
                {
                    "code": "TEST_AGGREGATE_RELATION_NOT_ELIGIBLE",
                    "severity": "WARNING",
                    "evidence_id": evidence_id,
                    "reasons": sorted(set(reasons)),
                }
            )
            continue
        aggregate_ref = _stable_id("evidence", "TEST_DATA_AGGREGATE", evidence_id)
        if not any(row.get("evidence_id") == aggregate_ref for row in result.evidence_refs):
            result.evidence_refs.append(
                {
                    "evidence_id": aggregate_ref,
                    "source_kind": "TEST_DATA_AGGREGATE",
                    "source_locator": "configured-aggregate:" + evidence_id,
                    "root_source_family": "test-snapshot:" + evidence_id,
                    "content_excerpt": (
                        f"TEST snapshot {aggregate.get('observed_at')}: "
                        f"event_rows={aggregate.get('event_rows')}, "
                        f"matched={aggregate.get('matched_event_rows')}, "
                        f"unmatched={aggregate.get('unmatched_event_rows')}, "
                        f"event_distinct_keys={aggregate.get('event_distinct_keys')}, "
                        f"contracts_with_events={aggregate.get('contracts_with_events')}, "
                        f"max_events_per_deal={aggregate.get('max_events_per_deal')}"
                    ),
                    "availability": "AVAILABLE",
                    "supports": [
                        f"{aggregate.get('subject_table')} {aggregate.get('predicate')} {aggregate.get('object_table')}"
                    ],
                    "query_sha256": aggregate.get("query_sha256"),
                    "environment": "TEST",
                    "observed_at": aggregate.get("observed_at"),
                    "contains_business_key_values": False,
                    "contains_business_rows": False,
                    "limitations": list(aggregate.get("limitations", [])),
                }
            )
        relation = validate_relation_candidate(
            predicate,
            subject_id,
            str(target["asset_id"]),
            direct_evidence_refs=metadata_refs + [aggregate_ref],
            counterevidence_refs=[],
            known_asset_ids=known,
        )
        relation["limitations"] = sorted(
            set(relation.get("limitations", []))
            | {
                "test environment snapshot only; not a declared foreign key or production rule"
            }
        )
        result.table_relations.append(relation)


def _finalize_aggregate_input_states(result: TableSemanticResult) -> None:
    used = {
        str(row.get("source_locator", "")).removeprefix("configured-aggregate:")
        for row in result.evidence_refs
        if row.get("source_kind") == "TEST_DATA_AGGREGATE"
    }
    rejected = {
        str(row.get("evidence_id"))
        for row in result.diagnostics
        if row.get("code") == "TEST_AGGREGATE_RELATION_NOT_ELIGIBLE"
    }
    for state in result.input_states:
        if state.get("input_name") != "approved_test_aggregate":
            continue
        evidence_id = str(state.get("logical_path", "")).removeprefix(
            "configured-aggregate:"
        )
        if evidence_id in used:
            state["availability"] = "AVAILABLE"
            state["adoption_status"] = "USED"
        elif evidence_id in rejected:
            state["availability"] = "NOT_EVALUABLE"
            state["adoption_status"] = "REJECTED"


def _build_relations(
    result: TableSemanticResult,
    tables: list[dict[str, Any]],
    variants: list[dict[str, Any]],
    field_summaries: list[dict[str, Any]],
    config: TableSemanticConfig,
) -> None:
    known = {str(row["asset_id"]) for row in tables}
    by_name = {str(row["object_name"]).upper(): row for row in tables}
    fields = {str(row["asset_id"]): row for row in field_summaries}

    variant_predicate = config.relation_predicates.get("PHYSICAL_VARIANT")
    if variant_predicate:
        for row in variants:
            if row["disposition"] not in {"LIKELY_VARIANT", "COMPETING_PARENT"}:
                continue
            for parent in row["candidate_parent_asset_ids"]:
                name_ref = _relation_evidence(
                    result,
                    "TABLE_NAME",
                    str(row["asset_id"]),
                    f"physical-table:{row['asset_id']}",
                    f"{row['object_name']} -> {row['base_name_candidate']} via {row['variant_rule']}",
                )
                structure_ref = _relation_evidence(
                    result,
                    "COLUMN_SIGNATURE",
                    f"{row['asset_id']}|{parent}",
                    f"physical-pair:{row['asset_id']}|{parent}",
                    json.dumps(row.get("structure_similarity", []), ensure_ascii=False, sort_keys=True),
                )
                result.table_relations.append(
                    validate_relation_candidate(
                        variant_predicate,
                        str(row["asset_id"]),
                        str(parent),
                        direct_evidence_refs=[name_ref, structure_ref],
                        counterevidence_refs=[],
                        known_asset_ids=known,
                    )
                )

    history_predicate = config.relation_predicates.get("CURRENT_HISTORY")
    if history_predicate:
        for name, current in sorted(by_name.items()):
            if "CURRENT" not in name:
                continue
            history_name = name.replace("CURRENT", "HIS")
            history = by_name.get(history_name) or by_name.get(name.replace("CURRENT", "HISTORY"))
            if not history:
                continue
            current_id = str(current["asset_id"])
            history_id = str(history["asset_id"])
            name_ref = _relation_evidence(
                result,
                "TABLE_NAME_PAIR",
                f"{current_id}|{history_id}",
                f"physical-pair:{current_id}|{history_id}",
                f"{name} contrasts with {history.get('object_name')}",
            )
            current_markers = fields.get(current_id, {}).get("markers", {})
            history_markers = fields.get(history_id, {}).get("markers", {})
            direct_refs = [name_ref]
            current_columns = set(fields.get(current_id, {}).get("column_names", []))
            history_columns = set(fields.get(history_id, {}).get("column_names", []))
            signature_similarity = _jaccard(current_columns, history_columns)
            if (current_markers and history_markers) or signature_similarity >= 0.5:
                direct_refs.append(
                    _relation_evidence(
                        result,
                        "FIELD_SUMMARY_PAIR",
                        f"{current_id}|{history_id}",
                        f"physical-pair:{current_id}|{history_id}",
                        f"bounded column-signature similarity={signature_similarity:.6f}; no row-level history completeness tested",
                    )
                )
            result.table_relations.append(
                validate_relation_candidate(
                    history_predicate,
                    current_id,
                    history_id,
                    direct_evidence_refs=direct_refs,
                    counterevidence_refs=[],
                    known_asset_ids=known,
                )
            )

    _build_approved_aggregate_relations(result, tables, config)

    related_predicate = config.relation_predicates.get("RELATED_TO")
    if related_predicate:
        existing_pairs = {
            frozenset((str(row["subject_asset_id"]), str(row["object_asset_id"])))
            for row in result.table_relations
        }
        relation_counts: dict[str, int] = {}
        per_table_limit = config.limits.get("max_relations_per_table", 12)
        for investigation in config.investigation_sets:
            if investigation.get("kind") != "BUSINESS_COLLABORATION":
                continue
            members = [by_name.get(str(name).upper()) for name in investigation.get("tables", [])]
            members = [row for row in members if row]
            for left_index, left in enumerate(members):
                for right in members[left_index + 1 :]:
                    left_id = str(left["asset_id"])
                    right_id = str(right["asset_id"])
                    pair = frozenset((left_id, right_id))
                    if pair in existing_pairs:
                        continue
                    if relation_counts.get(left_id, 0) >= per_table_limit or relation_counts.get(right_id, 0) >= per_table_limit:
                        continue
                    left_anchors = set(
                        fields.get(left_id, {}).get("markers", {}).get("ANCHOR_ID", [])
                    )
                    right_anchors = set(
                        fields.get(right_id, {}).get("markers", {}).get("ANCHOR_ID", [])
                    )
                    shared = sorted(left_anchors & right_anchors)
                    if not shared:
                        continue
                    evidence_ref = _relation_evidence(
                        result,
                        "SHARED_ANCHOR_FIELDS",
                        f"{left_id}|{right_id}",
                        f"physical-pair:{left_id}|{right_id}",
                        "shared bounded anchor fields: " + ", ".join(shared),
                    )
                    result.table_relations.append(
                        validate_relation_candidate(
                            related_predicate,
                            left_id,
                            right_id,
                            direct_evidence_refs=[evidence_ref],
                            counterevidence_refs=[],
                            known_asset_ids=known,
                        )
                    )
                    existing_pairs.add(pair)
                    relation_counts[left_id] = relation_counts.get(left_id, 0) + 1
                    relation_counts[right_id] = relation_counts.get(right_id, 0) + 1

    for relation in result.table_relations:
        assertion = {
            "assertion_id": _stable_id("assertion", relation["relation_id"]),
            "subject_id": relation["subject_asset_id"],
            "predicate": relation["predicate"],
            "object_value": relation["object_asset_id"],
            "method_id": relation["method_id"],
            "method_version": relation["method_version"],
            "evidence_refs": relation["evidence_refs"],
            "counterevidence_refs": relation["counterevidence_refs"],
            "root_source_families": sorted(
                {
                    str(evidence["root_source_family"])
                    for evidence in result.evidence_refs
                    if evidence["evidence_id"] in relation["evidence_refs"]
                }
            ),
            "method_score": None,
            "outcome": relation["outcome"],
            "review_decision_ref": None,
        }
        result.assertions.append(assertion)


def _best_responsibility(
    asset_id: str, candidates: list[dict[str, Any]]
) -> tuple[str, list[str]]:
    rows = [
        row
        for row in candidates
        if str(row["asset_id"]) == asset_id
        and row.get("evidence_refs")
        and row.get("source_kind") != "TABLE_NAME"
        and (
            row.get("recommended_profile_eligible") is True
            or row.get("vocabulary_layer") == "DISCOVERY"
            or row.get("candidate_value_kind") == "OBSERVED_EXPRESSION"
        )
    ]
    if not rows:
        return "UNKNOWN", []
    direct = sorted(
        rows,
        key=lambda row: (
            0 if row.get("recommended_profile_eligible") is True else 1,
            int(row.get("rank", 999)),
            str(row["candidate_value"]),
        ),
    )
    return str(direct[0]["candidate_value"]), list(direct[0]["evidence_refs"])


def _connected_member_ids(
    member_ids: set[str], relations: Iterable[Mapping[str, Any]]
) -> set[str]:
    adjacency: dict[str, set[str]] = {asset_id: set() for asset_id in member_ids}
    for relation in relations:
        left = str(relation.get("subject_asset_id", ""))
        right = str(relation.get("object_asset_id", ""))
        if left not in member_ids or right not in member_ids:
            continue
        if (
            not relation.get("evidence_refs")
            or relation.get("counterevidence_refs")
            or relation.get("outcome") != "CANDIDATE"
        ):
            continue
        adjacency[left].add(right)
        adjacency[right].add(left)
    if not member_ids:
        return set()
    visited: set[str] = set()
    pending = [sorted(member_ids)[0]]
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        pending.extend(sorted(adjacency[current] - visited))
    return visited


def _build_collaboration_groups(
    result: TableSemanticResult,
    tables: list[dict[str, Any]],
    config: TableSemanticConfig,
) -> None:
    by_name = {str(row["object_name"]).upper(): row for row in tables}
    for investigation in config.investigation_sets:
        if investigation.get("kind") != "BUSINESS_COLLABORATION":
            continue
        members = [by_name[name] for name in investigation.get("tables", []) if name in by_name]
        if len(members) < 2:
            result.diagnostics.append(
                {
                    "code": "COLLABORATION_SET_NOT_EVALUABLE",
                    "investigation_id": investigation.get("id"),
                    "available_members": len(members),
                }
            )
            continue
        responsibilities = {
            str(member["asset_id"]): _best_responsibility(
                str(member["asset_id"]), result.responsibility_candidates
            )
            for member in members
        }
        missing_responsibilities = sorted(
            asset_id
            for asset_id, (responsibility, evidence_refs) in responsibilities.items()
            if responsibility == "UNKNOWN" or not evidence_refs
        )
        member_ids = set(responsibilities)
        connected_ids = _connected_member_ids(member_ids, result.table_relations)
        disconnected_members = sorted(member_ids - connected_ids)
        if missing_responsibilities or disconnected_members:
            result.diagnostics.append(
                {
                    "code": "COLLABORATION_GROUP_REJECTED",
                    "severity": "WARNING",
                    "investigation_id": investigation.get("id"),
                    "missing_responsibility_asset_ids": missing_responsibilities,
                    "disconnected_asset_ids": disconnected_members,
                    "available_members": len(members),
                    "interpretation": "configured journey remains an investigation set and is not a business collaboration group",
                }
            )
            continue
        group_id = _stable_id("table-group", "BUSINESS_COLLABORATION_GROUP", investigation["id"], *(row["asset_id"] for row in members))
        result.table_groups.append(
            {
                "group_id": group_id,
                "group_kind": "BUSINESS_COLLABORATION_GROUP",
                "anchor_value": str(investigation["id"]),
                "status": "CANDIDATE",
                "method_id": "table_semantics.evidence_connected_group.v1",
                "limitations": ["evidence-connected candidate group; not a formal ontology or accepted business family"],
            }
        )
        for member in members:
            asset_id = str(member["asset_id"])
            responsibility, evidence_refs = responsibilities[asset_id]
            relation_refs = sorted(
                {
                    evidence_ref
                    for relation in result.table_relations
                    if asset_id
                    in {
                        str(relation.get("subject_asset_id")),
                        str(relation.get("object_asset_id")),
                    }
                    and {
                        str(relation.get("subject_asset_id")),
                        str(relation.get("object_asset_id")),
                    }
                    <= member_ids
                    for evidence_ref in relation.get("evidence_refs", [])
                }
            )
            membership_evidence = sorted(set(evidence_refs) | set(relation_refs))
            membership_id = _stable_id("membership", group_id, asset_id)
            membership = {
                "membership_id": membership_id,
                "group_id": group_id,
                "asset_id": asset_id,
                "responsibility": responsibility,
                "status": "CANDIDATE",
                "evidence_refs": membership_evidence,
                "limitations": ["membership is supported by responsibility and connected-relation evidence"],
            }
            result.group_memberships.append(membership)
            result.assertions.append(
                {
                    "assertion_id": _stable_id("assertion", membership_id),
                    "subject_id": asset_id,
                    "predicate": "MEMBER_OF_BUSINESS_COLLABORATION_GROUP",
                    "object_value": group_id,
                    "method_id": "table_semantics.evidence_connected_group.v1",
                    "method_version": METHOD_VERSION,
                    "evidence_refs": membership_evidence,
                    "counterevidence_refs": [],
                    "root_source_families": sorted(
                        {
                            str(evidence["root_source_family"])
                            for evidence in result.evidence_refs
                            if evidence["evidence_id"] in membership_evidence
                        }
                    ),
                    "method_score": None,
                    "outcome": membership["status"],
                    "review_decision_ref": None,
                }
            )


def _build_investigation_cards(
    result: TableSemanticResult,
    tables: list[dict[str, Any]],
    config: TableSemanticConfig,
) -> None:
    by_name = {str(row["object_name"]).upper(): row for row in tables}
    profiles = {str(row["asset_id"]): row for row in result.table_profiles}
    for investigation in config.investigation_sets[: config.limits.get("max_investigation_cards", 5)]:
        requested = [str(name).upper() for name in investigation.get("tables", [])]
        present = [by_name[name] for name in requested if name in by_name]
        missing = sorted(set(requested) - by_name.keys())
        member_ids = {str(row["asset_id"]) for row in present}
        card_relations = [
            row
            for row in result.table_relations
            if {
                str(row["subject_asset_id"]),
                str(row["object_asset_id"]),
            }.issubset(member_ids)
        ]
        members: list[dict[str, Any]] = []
        for table in present:
            asset_id = str(table["asset_id"])
            members.append(
                {
                    "asset_id": asset_id,
                    "object_name": table["object_name"],
                    "profile": profiles.get(asset_id, {}),
                    "responsibilities": [
                        row for row in result.responsibility_candidates if row["asset_id"] == asset_id
                    ],
                    "relations": [
                        row
                        for row in card_relations
                        if asset_id in {row["subject_asset_id"], row["object_asset_id"]}
                    ],
                    "field_support": next(
                        (row for row in result.field_support_summaries if row["asset_id"] == asset_id),
                        {"availability": "NOT_EVALUABLE"},
                    ),
                }
            )
        missing_responsibilities = sorted(
            asset_id
            for asset_id in member_ids
            if _best_responsibility(asset_id, result.responsibility_candidates)[0]
            == "UNKNOWN"
        )
        connected_ids = _connected_member_ids(member_ids, result.table_relations)
        disconnected_members = (
            sorted(member_ids - connected_ids)
            if investigation.get("kind") == "BUSINESS_COLLABORATION"
            else []
        )
        field_link_count = sum(
            len(row.get("assertion_links", []))
            for row in result.field_support_summaries
            if str(row.get("asset_id")) in member_ids
        )
        unknown_members = sorted(
            asset_id
            for asset_id in member_ids
            if profiles.get(asset_id, {}).get("candidate_summary", {}).get("has_unknown")
        )
        conflict_members = sorted(
            asset_id
            for asset_id in member_ids
            if profiles.get(asset_id, {}).get("candidate_summary", {}).get("has_conflict")
        )
        unknown_relations = sorted(
            str(row["relation_id"])
            for row in card_relations
            if row.get("outcome") == "UNKNOWN"
        )
        ready = bool(present) and not missing and not missing_responsibilities and not disconnected_members
        result.investigation_cards.append(
            {
                "card_id": str(investigation["id"]),
                "kind": investigation.get("kind"),
                "requested_tables": requested,
                "missing_tables": missing,
                "missing_responsibility_asset_ids": missing_responsibilities,
                "disconnected_asset_ids": disconnected_members,
                "unknown_member_asset_ids": unknown_members,
                "conflict_member_asset_ids": conflict_members,
                "unknown_relation_ids": unknown_relations,
                "semantic_review_status": (
                    "UNRESOLVED"
                    if unknown_members or conflict_members or unknown_relations
                    else "CANDIDATE_READY"
                ),
                "field_assertion_link_count": field_link_count,
                "relations": card_relations,
                "members": members,
                "status": "READY" if ready else "REWORK",
                "boundary": "metadata-only investigation; no row-level completeness or business acceptance claim",
            }
        )


def _evaluate_model_gate(result: TableSemanticResult, config: TableSemanticConfig) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def record(check_id: str, passed: bool, detail: str) -> None:
        checks.append({"check_id": check_id, "status": "PASS" if passed else "FAIL", "detail": detail})

    disposition_count = len(result.table_profiles)
    record(
        "no-silent-variant-loss",
        disposition_count == config.expected_all_tables,
        f"profiles={disposition_count}, expected={config.expected_all_tables}",
    )
    structural_groups = [row for row in result.table_groups if row["group_kind"] == "STRUCTURAL_NEIGHBORHOOD"]
    record(
        "structure-is-not-business",
        all(row.get("status") == "INVESTIGATION_HINT" for row in structural_groups),
        f"structural_groups={len(structural_groups)}",
    )
    record(
        "field-voting-disabled",
        all(not row.get("semantic_assistance", {}).get("voting_enabled", False) for row in result.field_support_summaries),
        "field summaries do not emit table labels",
    )
    collaboration_cards = [
        row
        for row in result.investigation_cards
        if row.get("kind") == "BUSINESS_COLLABORATION"
    ]
    used_field_assets = {
        str(row.get("asset_id"))
        for row in result.field_support_summaries
        if row.get("field_assistance_status") == "USED"
        and row.get("assertion_links")
    }
    cards_without_field_links = [
        str(card.get("card_id"))
        for card in collaboration_cards
        if not {
            str(member.get("asset_id")) for member in card.get("members", [])
        }
        & used_field_assets
    ]
    record(
        "field-assistance-linked-to-assertions",
        not cards_without_field_links,
        "collaboration_cards="
        + str(len(collaboration_cards))
        + ", cards_without_links="
        + str(cards_without_field_links),
    )
    record(
        "wiki-directory-is-context-only",
        all(
            row.get("document_context_only") is True
            for row in result.wiki_candidates
            if row.get("evidence_kind") == "NAVIGATION_CONTEXT"
        )
        and all(
            row.get("document_context_only") is False
            for row in result.wiki_candidates
            if row.get("evidence_kind") in {"MENTIONS_TABLE", "USAGE_DESCRIPTION", "MULTI_TABLE_ASSOCIATION"}
        ),
        f"wiki_candidates={len(result.wiki_candidates)}",
    )
    record(
        "no-automatic-accepted",
        all(row.get("outcome") != "ACCEPTED" for row in result.assertions),
        f"assertions={len(result.assertions)}",
    )
    unsupported = []
    for relation in result.table_relations:
        if relation["predicate"] == "RELATED_TO":
            continue
        predicate = config.relation_predicates.get(str(relation["predicate"]))
        if predicate and len(set(relation["evidence_refs"])) < predicate.min_direct_evidence:
            unsupported.append(relation["relation_id"])
    record("precise-relations-evidence-gated", not unsupported, f"unsupported={len(unsupported)}")
    card_ids = {row["card_id"] for row in result.investigation_cards}
    expected_cards = {str(row["id"]) for row in config.investigation_sets}
    record("five-investigation-cards", card_ids == expected_cards, f"cards={len(card_ids)}")
    expected_collaboration_ids = {
        str(row["id"])
        for row in config.investigation_sets
        if row.get("kind") == "BUSINESS_COLLABORATION"
    }
    published_collaboration_ids = {
        str(row.get("anchor_value"))
        for row in result.table_groups
        if row.get("group_kind") == "BUSINESS_COLLABORATION_GROUP"
    }
    collaboration_ready = (
        published_collaboration_ids == expected_collaboration_ids
        and all(row.get("status") == "READY" for row in collaboration_cards)
        and all(not row.get("disconnected_asset_ids") for row in collaboration_cards)
    )
    record(
        "business-collaboration-connected",
        collaboration_ready,
        "expected="
        + str(len(expected_collaboration_ids))
        + ", published="
        + str(len(published_collaboration_ids))
        + ", ready_cards="
        + str(sum(row.get("status") == "READY" for row in collaboration_cards)),
    )
    semantic_relation_count = sum(
        row.get("predicate") not in {"PHYSICAL_VARIANT", "CURRENT_HISTORY"}
        for row in result.table_relations
    )
    record(
        "collaboration-relations-not-vacuous",
        not expected_collaboration_ids or semantic_relation_count > 0,
        f"semantic_relations={semantic_relation_count}",
    )
    wiki_coverage = next(
        (row for row in result.diagnostics if row.get("code") == "WIKI_RECALL_COVERAGE"),
        None,
    )
    record(
        "wiki-recall-order-independent",
        wiki_coverage is None
        or wiki_coverage.get("selection_method")
        == "DETERMINISTIC_ROUND_ROBIN_BY_RANK",
        "selection_method=" + str((wiki_coverage or {}).get("selection_method", "NOT_EVALUABLE")),
    )
    visible_unknown = any(
        row.get("disposition") == "UNKNOWN" or row.get("candidate_summary", {}).get("has_conflict")
        for row in result.table_profiles
    )
    record("conflict-and-unknown-visible", visible_unknown, "profiles retain unresolved outcomes")
    critical_failures = [row for row in checks if row["status"] == "FAIL"]
    return {
        "status": "PASS" if not critical_failures else "FAIL",
        "checks": checks,
        "critical_failure_count": len(critical_failures),
        "boundary": "engineering information-model gate only; not reader delivery or business acceptance",
    }


def run_table_semantic_map(config: TableSemanticConfig) -> TableSemanticResult:
    """Build one deterministic table-semantic projection from fixed inputs."""

    result = TableSemanticResult(input_states=inspect_input_states(config))
    physical_root = config.inputs["physical_facts"].path
    facts_root = physical_root / "panorama/facts"
    objects = [
        row
        for row in _read_json_rows(facts_root / "objects.json")
        if str(row.get("schema_name", "")).upper() == config.scope_schema
        and str(row.get("object_type", "")).upper() in config.object_types
    ]
    known_asset_ids = {str(row["asset_id"]) for row in objects}
    columns = [row for row in _read_json_rows(facts_root / "columns.json") if str(row.get("asset_id")) in known_asset_ids]
    constraints = [row for row in _read_json_rows(facts_root / "constraints.json") if str(row.get("asset_id")) in known_asset_ids]
    classification_root = config.inputs["classification"].path
    classification_rows = _read_json_rows(
        classification_root / "panorama/candidates/business_classification_results.json"
    )
    subject_asset_ids = {
        str(row["subject_id"])
        for row in classification_rows
        if str(row.get("subject_id")) in known_asset_ids
    }
    if len(objects) != config.expected_all_tables:
        raise ValueError(f"TRADEFLOW table count mismatch: expected {config.expected_all_tables}, got {len(objects)}")
    if len(subject_asset_ids) != config.expected_subject_tables:
        raise ValueError(
            f"subject table count mismatch: expected {config.expected_subject_tables}, got {len(subject_asset_ids)}"
        )
    if len(objects) - len(subject_asset_ids) != config.expected_variant_or_other_tables:
        raise ValueError("variant/other table count does not match frozen scope")

    dispositions, variant_groups = classify_physical_variants(
        objects,
        columns,
        constraints,
        subject_asset_ids,
        rules=config.variant_rules,
        max_candidates_per_table=config.limits.get("max_variant_candidates_per_table", 3),
    )
    disposition_by_asset = {str(row["asset_id"]): row for row in dispositions}
    result.table_groups.extend(variant_groups)
    for group in variant_groups:
        for asset_id in group["member_asset_ids"]:
            result.group_memberships.append(
                {
                    "membership_id": _stable_id("membership", group["group_id"], asset_id),
                    "group_id": group["group_id"],
                    "asset_id": asset_id,
                    "responsibility": "VARIANT_MEMBER" if asset_id != group["anchor_asset_id"] else "VARIANT_ANCHOR",
                    "status": "CANDIDATE",
                    "evidence_refs": [],
                    "limitations": ["physical variant membership is not equivalence"],
                }
            )

    structural_groups, structural_memberships, structural_diagnostics = _load_structural_groups(
        classification_root,
        known_asset_ids,
        config.limits.get("max_structural_neighbors_per_table", 8),
    )
    result.table_groups.extend(structural_groups)
    result.group_memberships.extend(structural_memberships)
    result.diagnostics.extend(structural_diagnostics)
    result.structural_propagation_hints = _load_structural_propagation_hints(
        classification_root, known_asset_ids
    )

    for table in objects:
        for signal in derive_name_comment_signals(table, config):
            evidence = _evidence_from_signal(signal)
            if not any(row["evidence_id"] == evidence["evidence_id"] for row in result.evidence_refs):
                result.evidence_refs.append(evidence)
            candidate = _candidate_from_signal(signal, str(evidence["evidence_id"]))
            if signal["candidate_kind"] == "BusinessContext":
                result.context_candidates.append(candidate)
                predicate = "HAS_BUSINESS_CONTEXT_CANDIDATE"
            elif signal["candidate_kind"] == "BusinessAnchor":
                result.anchor_candidates.append(candidate)
                predicate = "HAS_BUSINESS_ANCHOR_CANDIDATE"
            else:
                result.responsibility_candidates.append(candidate)
                predicate = "HAS_TABLE_RESPONSIBILITY_CANDIDATE"
            result.assertions.append(_assertion_from_candidate(candidate, predicate))

    result.field_support_summaries = _augment_field_support(
        build_physical_field_summaries(objects, columns), config
    )
    _link_field_support_to_assertions(result, result.field_support_summaries)
    wiki_candidates, wiki_diagnostics = _wiki_recall(
        objects,
        result.field_support_summaries,
        result.anchor_candidates,
        config,
    )
    result.wiki_candidates = wiki_candidates
    result.diagnostics.extend(wiki_diagnostics)

    _build_relations(result, objects, dispositions, result.field_support_summaries, config)
    _finalize_aggregate_input_states(result)
    _build_collaboration_groups(result, objects, config)

    for table in sorted(objects, key=lambda row: str(row["asset_id"])):
        asset_id = str(table["asset_id"])
        contexts = [row for row in result.context_candidates if row["asset_id"] == asset_id]
        anchors = [row for row in result.anchor_candidates if row["asset_id"] == asset_id]
        responsibilities = [row for row in result.responsibility_candidates if row["asset_id"] == asset_id]
        recommended_responsibilities = [
            row
            for row in responsibilities
            if row.get("recommended_profile_eligible") is True
        ]
        discovered_responsibilities = [
            row
            for row in responsibilities
            if row.get("vocabulary_layer") == "DISCOVERY"
        ]
        result.table_profiles.append(
            {
                "asset_id": asset_id,
                "schema_name": table.get("schema_name"),
                "object_name": table.get("object_name"),
                "object_type": table.get("object_type"),
                "object_comment": table.get("object_comment"),
                "disposition": disposition_by_asset[asset_id]["disposition"],
                "variant_summary": disposition_by_asset[asset_id],
                "candidate_summary": {
                    "context_candidate_ids": [row["candidate_id"] for row in contexts],
                    "anchor_candidate_ids": [row["candidate_id"] for row in anchors],
                    "responsibility_candidate_ids": [row["candidate_id"] for row in responsibilities],
                    "recommended_responsibility_candidate_ids": [
                        row["candidate_id"] for row in recommended_responsibilities
                    ],
                    "discovered_responsibility_candidate_ids": [
                        row["candidate_id"] for row in discovered_responsibilities
                    ],
                    "has_conflict": any(row.get("conflict_key") for row in contexts + anchors + responsibilities),
                    "has_unknown": not recommended_responsibilities,
                    "responsibility_unknown": not recommended_responsibilities,
                },
                "panorama_object_card": f"panorama/objects/{asset_id}",
                "review_status": "UNREVIEWED",
            }
        )

    _build_investigation_cards(result, objects, config)
    result.quality_gate = _evaluate_model_gate(result, config)
    unresolved_profiles = [
        row
        for row in result.table_profiles
        if row["candidate_summary"]["has_unknown"]
        or row["candidate_summary"]["has_conflict"]
        or row["disposition"] == "UNKNOWN"
    ]
    result.legacy_comparison = {
        "legacy_candidate_count": len(result.structural_propagation_hints),
        "legacy_result_count": len(classification_rows),
        "legacy_subject_count": len(subject_asset_ids),
        "new_table_profile_count": len(result.table_profiles),
        "new_direct_candidate_count": (
            len(result.context_candidates)
            + len(result.anchor_candidates)
            + len(result.responsibility_candidates)
        ),
        "retained_useful_hints": len(result.structural_propagation_hints),
        "recommended_from_propagation_only": 0,
        "unresolved_profile_count": len(unresolved_profiles),
        "corrected_distinctions": [
            "structural neighborhoods remain separate from business collaboration groups",
            "parameter, log, validation, report, result, and mapping responsibilities remain competing candidates where signals differ",
            "current/history is represented as a candidate relation without row-level history completeness",
            "244 suffix tables retain explicit subject/variant/standalone/unknown disposition",
        ],
        "evidence_source_changes": [
            "table name and table comment are separate direct signals under one physical root",
            "field semantics supports or distinguishes assertions but never votes a table label",
            "Wiki Tree is navigation context; only pinned body mentions may add document evidence",
            "legacy propagated labels are non-recommended structural hints",
        ],
        "boundary": "comparison is descriptive; no accuracy rate is reported without independent business truth",
    }
    result.stats = {
        "all_table_count": len(objects),
        "subject_table_count": len(subject_asset_ids),
        "variant_or_other_count": len(objects) - len(subject_asset_ids),
        "likely_variant_count": sum(row["disposition"] == "LIKELY_VARIANT" for row in dispositions),
        "standalone_count": sum(row["disposition"] == "STANDALONE" for row in dispositions),
        "unknown_variant_count": sum(row["disposition"] == "UNKNOWN" for row in dispositions),
        "context_candidate_count": len(result.context_candidates),
        "anchor_candidate_count": len(result.anchor_candidates),
        "responsibility_candidate_count": len(result.responsibility_candidates),
        "table_relation_count": len(result.table_relations),
        "business_collaboration_group_count": sum(row["group_kind"] == "BUSINESS_COLLABORATION_GROUP" for row in result.table_groups),
        "physical_variant_group_count": sum(row["group_kind"] == "PHYSICAL_VARIANT_GROUP" for row in result.table_groups),
        "structural_neighborhood_count": sum(row["group_kind"] == "STRUCTURAL_NEIGHBORHOOD" for row in result.table_groups),
        "assertion_count": len(result.assertions),
        "legacy_structural_hint_count": len(result.structural_propagation_hints),
        "wiki_candidate_count": len(result.wiki_candidates),
        "investigation_card_count": len(result.investigation_cards),
        "model_gate": result.quality_gate["status"],
    }
    validate_result_contracts(result)
    return result


def _jsonl_text(rows: Iterable[Mapping[str, Any]]) -> str:
    return "".join(
        json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_jsonl_text(rows), encoding="utf-8")


def _write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), path)


def write_table_semantic_results(
    output_dir: str | Path,
    result: TableSemanticResult,
    config: TableSemanticConfig,
) -> dict[str, Path]:
    """Write deterministic JSONL/Parquet datasets, diagnostics, cards, and Manifest."""

    validate_result_contracts(result)
    root = Path(output_dir) / "table-semantic-map"
    datasets = {
        "table_profiles": result.table_profiles,
        "table_context_candidates": result.context_candidates,
        "table_anchor_candidates": result.anchor_candidates,
        "table_responsibility_candidates": result.responsibility_candidates,
        "table_groups": result.table_groups,
        "table_group_memberships": result.group_memberships,
        "table_relations": result.table_relations,
        "assertions": result.assertions,
        "evidence_refs": result.evidence_refs,
        "review_decisions": result.review_decisions,
        "field_support_summaries": result.field_support_summaries,
        "structural_propagation_hints": result.structural_propagation_hints,
        "wiki_candidates": result.wiki_candidates,
    }
    paths: dict[str, Path] = {}
    output_entries: list[dict[str, Any]] = []
    for logical_name, rows in datasets.items():
        jsonl_path = root / f"{logical_name}.jsonl"
        parquet_path = root / f"{logical_name}.parquet"
        _write_jsonl(jsonl_path, rows)
        _write_parquet(parquet_path, rows)
        paths[logical_name] = jsonl_path
        for format_name, path in (("jsonl", jsonl_path), ("parquet", parquet_path)):
            output_entries.append(
                {
                    "logical_name": logical_name,
                    "format": format_name,
                    "relative_path": path.relative_to(root).as_posix(),
                    "row_count": len(rows),
                    "content_sha256": _sha256(path),
                    "bytes": path.stat().st_size,
                }
            )
    diagnostics_path = root / "diagnostics/diagnostics.jsonl"
    gate_path = root / "diagnostics/model-gate.json"
    cards_path = root / "investigation-cards/cards.json"
    legacy_path = root / "diagnostics/legacy-classification-comparison.json"
    _write_jsonl(diagnostics_path, result.diagnostics)
    gate_path.parent.mkdir(parents=True, exist_ok=True)
    gate_path.write_text(json.dumps(result.quality_gate, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    cards_path.parent.mkdir(parents=True, exist_ok=True)
    cards_path.write_text(json.dumps(result.investigation_cards, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    legacy_path.write_text(json.dumps(result.legacy_comparison, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    paths.update({"diagnostics": diagnostics_path, "model_gate": gate_path, "investigation_cards": cards_path, "legacy_comparison": legacy_path})
    for logical_name, path, count in (
        ("diagnostics", diagnostics_path, len(result.diagnostics)),
        ("model_gate", gate_path, len(result.quality_gate.get("checks", []))),
        ("investigation_cards", cards_path, len(result.investigation_cards)),
        ("legacy_comparison", legacy_path, 1),
    ):
        output_entries.append(
            {
                "logical_name": logical_name,
                "format": path.suffix.lstrip("."),
                "relative_path": path.relative_to(root).as_posix(),
                "row_count": count,
                "content_sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
        )

    if result.quality_gate.get("status") == "PASS":
        from .table_review import render_table_semantic_review

        paths.update(
            render_table_semantic_review(
                root,
                table_profiles=result.table_profiles,
                context_candidates=result.context_candidates,
                anchor_candidates=result.anchor_candidates,
                responsibility_candidates=result.responsibility_candidates,
                table_groups=result.table_groups,
                memberships=result.group_memberships,
                relations=result.table_relations,
                evidence_refs=result.evidence_refs,
                assertions=result.assertions,
                review_decisions=result.review_decisions,
                structural_propagation_hints=result.structural_propagation_hints,
                field_summaries=result.field_support_summaries,
                wiki_candidates=result.wiki_candidates,
                investigation_cards=result.investigation_cards,
                quality_gate=result.quality_gate,
                limits=config.limits,
            )
        )
        for review_path in sorted((root / "review").rglob("*")):
            if not review_path.is_file():
                continue
            output_entries.append(
                {
                    "logical_name": "review_projection",
                    "format": review_path.suffix.lstrip("."),
                    "relative_path": review_path.relative_to(root).as_posix(),
                    "row_count": None,
                    "content_sha256": _sha256(review_path),
                    "bytes": review_path.stat().st_size,
                }
            )

    manifest = {
        "schema_version": "table-semantic-map-v1",
        "stage_id": "table-semantic-map",
        "run_id": _stable_id("table-semantic-run", config.config_sha256, *(row["manifest_sha256"] for row in result.input_states if row.get("manifest_sha256"))),
        "method_id": METHOD_ID,
        "method_version": METHOD_VERSION,
        "config_path": config.config_path.as_posix() if config.config_path else None,
        "config_sha256": config.config_sha256,
        "inputs": result.input_states,
        "relation_registry_version": config.relation_registry_version,
        "stats": result.stats,
        "model_gate": result.quality_gate,
        "outputs": sorted(output_entries, key=lambda row: (row["logical_name"], row["format"])),
        "upstream_writes": False,
        "business_rows_read": False,
        "test_data_query_executed_by_build": False,
        "test_data_aggregate_evidence_used": any(
            row.get("source_kind") == "TEST_DATA_AGGREGATE"
            for row in result.evidence_refs
        ),
        "field_semantics_modified": False,
        "reader_delivery": "NOT_REVIEWED",
        "business_acceptance": "NOT_REQUESTED",
        "scale_authorization": "NOT_GRANTED",
        "known_boundaries": [
            "candidate projection only",
            "method scores are not probabilities",
            "structural neighborhoods are investigation hints",
            "Wiki directory context is not business classification",
            "frozen TEST aggregate evidence is not production truth or a declared foreign key",
        ],
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    paths["manifest"] = manifest_path
    return paths
