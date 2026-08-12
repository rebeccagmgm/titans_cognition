"""Bounded Panorama family discovery and candidate business classification."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from html import escape
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Callable, Iterable

import yaml

from .extract import PhysicalFacts


MATCH_METHOD_ID = "similarity.panorama.multi_view.v1"
FAMILY_METHOD_ID = "family.panorama.leiden.v1"
PROPAGATION_METHOD_ID = "classification.panorama.label_propagation.v1"
LLM_PROMPT_ID = "classification.family_interpretation.current_gpt.v1"
METHOD_VERSION = "v1"

_ASCII_TOKEN = re.compile(r"[A-Z0-9]+")
_CHINESE_TEXT = re.compile(r"[\u4e00-\u9fff]+")
_NUMERIC_SUFFIX = re.compile(r"\d+$")
_COMMON_TOKENS = {
    "ID",
    "CODE",
    "NAME",
    "TYPE",
    "STATUS",
    "DATE",
    "TIME",
    "FLAG",
    "CREATE",
    "UPDATE",
    "USER",
    "DATA",
    "INFO",
    "TABLE",
    "TITANS",
}


@dataclass(frozen=True)
class ClassificationConfig:
    """Validated, content-addressed runtime configuration."""

    raw: dict[str, object]
    config_hash: str
    wiki_page_id: str
    exclude_numeric_suffix: bool
    top_k: int
    max_candidate_pairs: int
    max_edges: int
    rare_token_max_frequency: int
    min_edge_score: float
    cross_schema_min_signals: int
    weights: dict[str, float]
    leiden_seed: int
    leiden_resolution: float
    min_family_size: int
    min_multi_view_edges: int
    propagation_alpha: float
    propagation_tolerance: float
    propagation_max_iterations: int
    candidate_threshold: float
    competition_margin: float
    max_candidates_per_dimension: int
    llm_max_families: int
    llm_max_pack_chars: int
    llm_max_retries: int
    taxonomy: dict[str, dict[str, dict[str, object]]]


@dataclass
class ClassificationResult:
    """Typed row collections for one bounded classification run."""

    run_id: str
    graph_run_id: str
    config_hash: str
    wiki_metadata: dict[str, object]
    schema_match_signals: list[dict[str, object]] = field(default_factory=list)
    similarity_edges: list[dict[str, object]] = field(default_factory=list)
    community_partitions: list[dict[str, object]] = field(default_factory=list)
    family_candidates: list[dict[str, object]] = field(default_factory=list)
    family_memberships: list[dict[str, object]] = field(default_factory=list)
    label_source_outputs: list[dict[str, object]] = field(default_factory=list)
    business_class_candidates: list[dict[str, object]] = field(default_factory=list)
    classification_results: list[dict[str, object]] = field(default_factory=list)
    wiki_sources: list[dict[str, object]] = field(default_factory=list)
    evidence_packs: list[dict[str, object]] = field(default_factory=list)
    llm_task_results: list[dict[str, object]] = field(default_factory=list)
    stats: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class _Profile:
    asset_id: str
    schema_name: str
    object_name: str
    object_type: str
    object_comment: str
    name_tokens: frozenset[str]
    comment_tokens: frozenset[str]
    column_tokens: frozenset[str]
    type_counts: tuple[tuple[str, int], ...]
    key_tokens: frozenset[str]
    dependency_neighbors: frozenset[str]
    root_source_refs: tuple[str, ...]


def load_classification_config(path: str | Path) -> ClassificationConfig:
    """Load and validate the bounded classification YAML configuration."""

    config_path = Path(path)
    value = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("classification config must be a mapping")
    limits = _mapping(value, "limits")
    matching = _mapping(value, "matching")
    families = _mapping(value, "families")
    propagation = _mapping(value, "propagation")
    wiki_source = _mapping(value, "wiki_source")
    object_filter = _mapping(value, "object_filter")
    taxonomy_raw = _mapping(value, "taxonomy")
    taxonomy: dict[str, dict[str, dict[str, object]]] = {}
    for dimension, labels in taxonomy_raw.items():
        if not isinstance(labels, dict) or not labels:
            raise ValueError(f"taxonomy dimension {dimension!r} must contain labels")
        taxonomy[str(dimension)] = {}
        for label, rule in labels.items():
            if not isinstance(rule, dict):
                raise ValueError(f"taxonomy rule {dimension}.{label} must be a mapping")
            taxonomy[str(dimension)][str(label)] = rule
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    weights_raw = matching.get("weights") or {
        "physical_name": 0.25,
        "physical_comment": 0.10,
        "column_structure": 0.35,
        "type_structure": 0.10,
        "declared_key": 0.15,
        "declared_dependency": 0.05,
    }
    if not isinstance(weights_raw, dict):
        raise ValueError("matching.weights must be a mapping")
    weights = {str(key): float(number) for key, number in weights_raw.items()}
    if not weights or any(number < 0 for number in weights.values()):
        raise ValueError("matching.weights must be non-negative")
    return ClassificationConfig(
        raw=value,
        config_hash=_sha256_text(canonical),
        wiki_page_id=str(wiki_source.get("page_id", "")),
        exclude_numeric_suffix=bool(object_filter.get("exclude_numeric_suffix", False)),
        top_k=_positive_int(limits, "top_k", 8),
        max_candidate_pairs=_positive_int(limits, "max_candidate_pairs", 250_000),
        max_edges=_positive_int(limits, "max_edges", 30_000),
        rare_token_max_frequency=_positive_int(limits, "rare_token_max_frequency", 120),
        min_edge_score=float(matching.get("min_edge_score", 0.24)),
        cross_schema_min_signals=int(matching.get("cross_schema_min_signals", 2)),
        weights=weights,
        leiden_seed=int(families.get("random_seed", 42)),
        leiden_resolution=float(families.get("resolution", 1.0)),
        min_family_size=_positive_int(families, "min_size", 2),
        min_multi_view_edges=_positive_int(families, "min_multi_view_edges", 1),
        propagation_alpha=float(propagation.get("alpha", 0.75)),
        propagation_tolerance=float(propagation.get("tolerance", 0.000001)),
        propagation_max_iterations=_positive_int(
            limits, "propagation_max_iterations", 30
        ),
        candidate_threshold=float(propagation.get("candidate_threshold", 0.32)),
        competition_margin=float(propagation.get("competition_margin", 0.08)),
        max_candidates_per_dimension=_positive_int(
            propagation,
            "max_candidates_per_dimension",
            int(limits.get("max_candidates_per_dimension", 3)),
        ),
        llm_max_families=_positive_int(limits, "llm_max_families", 50),
        llm_max_pack_chars=_positive_int(limits, "llm_max_pack_chars", 12_000),
        llm_max_retries=int(limits.get("llm_max_retries", 1)),
        taxonomy=taxonomy,
    )


def run_classification(
    facts: PhysicalFacts,
    config: ClassificationConfig,
    wiki_metadata: dict[str, object],
) -> ClassificationResult:
    """Run one deterministic schema-match, family, and propagation pipeline."""

    _validate_wiki_metadata(config, wiki_metadata)
    profiles = _build_profiles(
        facts,
        exclude_numeric_suffix=config.exclude_numeric_suffix,
    )
    if not profiles:
        raise ValueError("classification scope contains no in-scope physical objects")
    run_id = _single_run_id(facts)
    graph_run_id = _sha256_text(
        json.dumps(
            {
                "asset_ids": sorted(profiles),
                "config_hash": config.config_hash,
                "method": MATCH_METHOD_ID,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )[:24]
    signal_rows, limits_hit = _schema_match(profiles, config, graph_run_id)
    edges = _sparse_edges(signal_rows, profiles, config)
    partitions, families, memberships = _discover_families(
        profiles,
        edges,
        config,
        graph_run_id,
        run_id,
    )
    label_rows = _label_sources(profiles, config, wiki_metadata, run_id)
    candidates, results, propagation_stats = _propagate_labels(
        profiles,
        edges,
        label_rows,
        config,
        graph_run_id,
        run_id,
    )
    wiki_source_id = _wiki_source_id(wiki_metadata)
    wiki_sources = [
        {
            "source_id": wiki_source_id,
            "page_id": str(wiki_metadata["pageId"]),
            "title": str(wiki_metadata.get("title", "")),
            "version": wiki_metadata.get("version"),
            "cached_at": wiki_metadata.get("cachedAt"),
            "content_hash": str(wiki_metadata["contentHash"]),
            "source_status": "SUCCESS",
            "purpose": "CLASSIFICATION_SEED",
            "excluded_content": ["people", "partners", "staffing"],
        }
    ]
    packs = _build_evidence_packs(
        profiles,
        families,
        memberships,
        edges,
        label_rows,
        wiki_source_id,
        config,
    )
    llm_rows = run_llm_interpretation(packs, mode="disabled")
    return ClassificationResult(
        run_id=run_id,
        graph_run_id=graph_run_id,
        config_hash=config.config_hash,
        wiki_metadata=dict(wiki_metadata),
        schema_match_signals=signal_rows,
        similarity_edges=edges,
        community_partitions=partitions,
        family_candidates=families,
        family_memberships=memberships,
        label_source_outputs=label_rows,
        business_class_candidates=candidates,
        classification_results=results,
        wiki_sources=wiki_sources,
        evidence_packs=packs,
        llm_task_results=llm_rows,
        stats={
            "object_count": len(profiles),
            "excluded_numeric_suffix_count": sum(
                bool(row.get("in_panorama_scope"))
                and not bool(row.get("is_boundary"))
                and bool(_NUMERIC_SUFFIX.search(str(row.get("object_name", ""))))
                for row in facts.objects
            )
            if config.exclude_numeric_suffix
            else 0,
            "schema_match_signal_count": len(signal_rows),
            "edge_count": len(edges),
            "community_count": len({row["community_id"] for row in partitions}),
            "candidate_family_count": sum(row["status"] == "CANDIDATE" for row in families),
            "weak_family_count": sum(row["status"] == "WEAK" for row in families),
            "label_source_count": len(label_rows),
            "business_candidate_count": len(candidates),
            "unknown_count": sum(row["outcome"] == "UNKNOWN" for row in results),
            "competing_count": sum(row["outcome"] == "COMPETING" for row in results),
            "not_evaluable_count": sum(
                row["outcome"] == "NOT_EVALUABLE" for row in results
            ),
            "limits_hit": sorted(limits_hit),
            **propagation_stats,
        },
    )


def _build_profiles(
    facts: PhysicalFacts,
    *,
    exclude_numeric_suffix: bool = False,
) -> dict[str, _Profile]:
    columns_by_asset: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in facts.columns:
        columns_by_asset[str(row.get("asset_id", ""))].append(row)
    keys_by_asset: dict[str, set[str]] = defaultdict(set)
    for row in [*facts.constraints, *facts.indexes]:
        asset_id = str(row.get("asset_id", ""))
        for column_id in row.get("column_ids", []) or []:
            keys_by_asset[asset_id].update(_name_tokens(str(column_id).rsplit(":", 1)[-1]))
    neighbors: dict[str, set[str]] = defaultdict(set)
    for row in facts.dependencies:
        source = str(row.get("source_asset_id", ""))
        target = str(row.get("target_asset_id", ""))
        if source and target:
            neighbors[source].add(target)
            neighbors[target].add(source)
    profiles: dict[str, _Profile] = {}
    for row in facts.objects:
        if not row.get("in_panorama_scope") or row.get("is_boundary"):
            continue
        if exclude_numeric_suffix and _NUMERIC_SUFFIX.search(
            str(row.get("object_name", ""))
        ):
            continue
        asset_id = str(row["asset_id"])
        object_name = str(row.get("object_name", ""))
        schema_name = str(row.get("schema_name", ""))
        object_comment = str(row.get("object_comment") or "")
        column_tokens: set[str] = set()
        type_counts: Counter[str] = Counter()
        roots = {asset_id}
        for column in columns_by_asset.get(asset_id, []):
            column_tokens.update(_name_tokens(str(column.get("column_name", ""))))
            type_counts[_type_family(str(column.get("data_type", "")))] += 1
            if column.get("column_id"):
                roots.add(str(column["column_id"]))
        profiles[asset_id] = _Profile(
            asset_id=asset_id,
            schema_name=schema_name,
            object_name=object_name,
            object_type=str(row.get("object_type", "")),
            object_comment=object_comment,
            name_tokens=frozenset(
                _name_tokens(schema_name) | _name_tokens(object_name) | _char_ngrams(object_name)
            ),
            comment_tokens=frozenset(_text_tokens(object_comment)),
            column_tokens=frozenset(column_tokens),
            type_counts=tuple(sorted(type_counts.items())),
            key_tokens=frozenset(keys_by_asset.get(asset_id, set())),
            dependency_neighbors=frozenset(neighbors.get(asset_id, set())),
            root_source_refs=tuple(sorted(roots)),
        )
    return profiles


def _schema_match(
    profiles: dict[str, _Profile],
    config: ClassificationConfig,
    graph_run_id: str,
) -> tuple[list[dict[str, object]], set[str]]:
    name_index = _inverted_index(profiles, "name_tokens")
    column_index = _inverted_index(profiles, "column_tokens")
    candidate_pairs: dict[tuple[str, str], set[str]] = defaultdict(set)
    limits_hit: set[str] = set()
    window = max(config.top_k * 4, 8)
    for reason, index in (("SHARED_NAME_TOKEN", name_index), ("SHARED_COLUMN_TOKEN", column_index)):
        for token, assets in sorted(index.items()):
            if token in _COMMON_TOKENS or len(assets) < 2 or len(assets) > config.rare_token_max_frequency:
                continue
            ordered = sorted(assets)
            for left_index, left in enumerate(ordered):
                for right in ordered[left_index + 1 : left_index + 1 + window]:
                    pair = (left, right)
                    candidate_pairs[pair].add(reason)
                    if len(candidate_pairs) >= config.max_candidate_pairs:
                        limits_hit.add("max_candidate_pairs")
                        break
                if "max_candidate_pairs" in limits_hit:
                    break
            if "max_candidate_pairs" in limits_hit:
                break
        if "max_candidate_pairs" in limits_hit:
            break
    for profile in profiles.values():
        for neighbor in profile.dependency_neighbors:
            if neighbor in profiles and profile.asset_id != neighbor:
                pair = tuple(sorted((profile.asset_id, neighbor)))
                candidate_pairs[pair].add("DIRECT_DEPENDENCY")
    name_idf = _idf(name_index, len(profiles))
    column_idf = _idf(column_index, len(profiles))
    rows: list[dict[str, object]] = []
    for (left_id, right_id), reasons in sorted(candidate_pairs.items()):
        left = profiles[left_id]
        right = profiles[right_id]
        scores: dict[str, float | None] = {
            "physical_name": _weighted_jaccard(left.name_tokens, right.name_tokens, name_idf),
            "physical_comment": (
                _jaccard(left.comment_tokens, right.comment_tokens)
                if left.comment_tokens and right.comment_tokens
                else None
            ),
            "column_structure": _weighted_jaccard(
                left.column_tokens, right.column_tokens, column_idf
            ),
            "type_structure": _counter_similarity(left.type_counts, right.type_counts),
            "declared_key": (
                _jaccard(left.key_tokens, right.key_tokens)
                if left.key_tokens and right.key_tokens
                else None
            ),
            "declared_dependency": (
                1.0
                if right_id in left.dependency_neighbors or left_id in right.dependency_neighbors
                else 0.0
            ),
        }
        combined = _combined_score(scores, config.weights)
        support_count = sum(
            value is not None and value >= (0.5 if key == "declared_dependency" else 0.15)
            for key, value in scores.items()
        )
        cross_schema = left.schema_name != right.schema_name
        if combined < config.min_edge_score:
            continue
        if cross_schema and support_count < config.cross_schema_min_signals:
            continue
        availability = [key for key, value in scores.items() if value is not None]
        root_refs = sorted(set(left.root_source_refs) | set(right.root_source_refs))
        rows.append(
            {
                "left_asset_id": left_id,
                "right_asset_id": right_id,
                "method_id": MATCH_METHOD_ID,
                "method_version": METHOD_VERSION,
                "graph_run_id": graph_run_id,
                "combined_score": round(combined, 6),
                "support_signal_count": support_count,
                "availability_mask": availability,
                "blocking_reasons": sorted(reasons),
                "signal_scores": json.dumps(scores, sort_keys=True, separators=(",", ":")),
                "root_source_refs": root_refs,
                "interpretation": "method-local structural ranking signal; not business similarity probability",
            }
        )
    return rows, limits_hit


def _sparse_edges(
    rows: list[dict[str, object]],
    profiles: dict[str, _Profile],
    config: ClassificationConfig,
) -> list[dict[str, object]]:
    ranked: dict[str, list[tuple[float, str]]] = defaultdict(list)
    by_pair: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        left = str(row["left_asset_id"])
        right = str(row["right_asset_id"])
        score = float(row["combined_score"])
        ranked[left].append((score, right))
        ranked[right].append((score, left))
        by_pair[tuple(sorted((left, right)))] = row
    selected: dict[str, set[str]] = {}
    for asset_id in profiles:
        selected[asset_id] = {
            other
            for _score, other in sorted(
                ranked.get(asset_id, []), key=lambda item: (-item[0], item[1])
            )[: config.top_k]
        }
    edges: list[dict[str, object]] = []
    for pair, row in sorted(by_pair.items()):
        left, right = pair
        direct = "DIRECT_DEPENDENCY" in row["blocking_reasons"]
        if (right in selected[left] and left in selected[right]) or direct:
            edges.append({**row, "edge_selection": "DIRECT" if direct else "MUTUAL_TOP_K"})
    edges.sort(key=lambda row: (-float(row["combined_score"]), str(row["left_asset_id"]), str(row["right_asset_id"])))
    return edges[: config.max_edges]


def _discover_families(
    profiles: dict[str, _Profile],
    edges: list[dict[str, object]],
    config: ClassificationConfig,
    graph_run_id: str,
    run_id: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    try:
        import igraph as ig
        import leidenalg
    except ImportError as exc:
        raise RuntimeError("Leiden requires igraph==1.0.0 and leidenalg==0.11.0") from exc
    assets = sorted(profiles)
    index = {asset_id: position for position, asset_id in enumerate(assets)}
    graph = ig.Graph(n=len(assets), directed=False)
    graph.vs["name"] = assets
    graph.add_edges(
        [(index[str(row["left_asset_id"])], index[str(row["right_asset_id"])]) for row in edges]
    )
    weights = [float(row["combined_score"]) for row in edges]
    partition = leidenalg.find_partition(
        graph,
        leidenalg.RBConfigurationVertexPartition,
        weights=weights or None,
        resolution_parameter=config.leiden_resolution,
        seed=config.leiden_seed,
    )
    memberships = list(partition.membership)
    community_assets: dict[int, list[str]] = defaultdict(list)
    for asset_id, community in zip(assets, memberships, strict=True):
        community_assets[int(community)].append(asset_id)
    edge_by_community: dict[int, list[dict[str, object]]] = defaultdict(list)
    for row in edges:
        left = str(row["left_asset_id"])
        right = str(row["right_asset_id"])
        community = memberships[index[left]]
        if community == memberships[index[right]]:
            edge_by_community[int(community)].append(row)
    partitions: list[dict[str, object]] = []
    families: list[dict[str, object]] = []
    family_memberships: list[dict[str, object]] = []
    for community, members in sorted(community_assets.items()):
        community_id = f"{graph_run_id}:community:{community:05d}"
        internal = edge_by_community.get(community, [])
        multi_view_edges = sum(int(row["support_signal_count"]) >= 2 for row in internal)
        if len(members) < config.min_family_size:
            status = "SINGLETON"
        elif multi_view_edges >= config.min_multi_view_edges:
            status = "CANDIDATE"
        else:
            status = "WEAK"
        for asset_id in sorted(members):
            partitions.append(
                {
                    "asset_id": asset_id,
                    "community_id": community_id,
                    "partition_method": FAMILY_METHOD_ID,
                    "method_version": METHOD_VERSION,
                    "graph_run_id": graph_run_id,
                    "community_status": status,
                }
            )
        if status == "SINGLETON":
            continue
        family_id = f"{run_id}:FAMILY:{_sha256_text(community_id)[:16]}"
        families.append(
            {
                "family_candidate_id": family_id,
                "run_id": run_id,
                "scope_id": "titans-panorama-v1",
                "provisional_name": f"technical-family-{community:05d}",
                "status": status,
                "member_count": len(members),
                "internal_edge_count": len(internal),
                "multi_view_edge_count": multi_view_edges,
                "clustering_method": FAMILY_METHOD_ID,
                "method_version": METHOD_VERSION,
                "graph_run_id": graph_run_id,
                "limitations": ["Leiden community is not a business category"],
            }
        )
        degrees = Counter()
        for row in internal:
            degrees[str(row["left_asset_id"])] += 1
            degrees[str(row["right_asset_id"])] += 1
        max_degree = max(degrees.values(), default=0)
        for asset_id in sorted(members):
            degree = degrees[asset_id]
            role = "CORE" if max_degree and degree == max_degree else "EDGE"
            family_memberships.append(
                {
                    "family_candidate_id": family_id,
                    "asset_id": asset_id,
                    "membership_role": role,
                    "membership_score": round(degree / max(max_degree, 1), 6),
                    "membership_explanation": f"{degree} retained internal similarity edges",
                    "graph_run_id": graph_run_id,
                    "root_source_refs": list(profiles[asset_id].root_source_refs),
                }
            )
    return partitions, families, family_memberships


def _label_sources(
    profiles: dict[str, _Profile],
    config: ClassificationConfig,
    wiki_metadata: dict[str, object],
    run_id: str,
) -> list[dict[str, object]]:
    wiki_ref = _wiki_source_id(wiki_metadata)
    deduplicated: dict[tuple[str, str, str, str], dict[str, object]] = {}
    for profile in profiles.values():
        name_haystack = f"{profile.schema_name}_{profile.object_name}".upper()
        comment_haystack = profile.object_comment.upper()
        for dimension, labels in config.taxonomy.items():
            for label, rule in labels.items():
                terms = [str(value).upper() for value in rule.get("terms", []) or []]
                object_types = {str(value).upper() for value in rule.get("object_types", []) or []}
                if any(_term_matches(term, name_haystack) for term in terms):
                    _record_label(
                        deduplicated,
                        profile,
                        run_id,
                        dimension,
                        label,
                        "PHYSICAL_NAME",
                        "lf.wiki_term_on_physical_name.v1",
                        1.0,
                        [wiki_ref, profile.asset_id],
                    )
                if comment_haystack and any(term in comment_haystack for term in terms):
                    _record_label(
                        deduplicated,
                        profile,
                        run_id,
                        dimension,
                        label,
                        "PHYSICAL_COMMENT",
                        "lf.wiki_term_on_physical_comment.v1",
                        0.8,
                        [wiki_ref, profile.asset_id],
                    )
                if profile.object_type.upper() in object_types:
                    _record_label(
                        deduplicated,
                        profile,
                        run_id,
                        dimension,
                        label,
                        "DECLARED_STRUCTURE",
                        "lf.declared_object_type.v1",
                        1.0,
                        [profile.asset_id],
                    )
    return sorted(
        deduplicated.values(),
        key=lambda row: (
            str(row["asset_id"]),
            str(row["dimension"]),
            str(row["label"]),
            str(row["source_family"]),
        ),
    )


def _record_label(
    target: dict[tuple[str, str, str, str], dict[str, object]],
    profile: _Profile,
    run_id: str,
    dimension: str,
    label: str,
    source_family: str,
    method_id: str,
    strength: float,
    root_refs: list[str],
) -> None:
    key = (profile.asset_id, dimension, label, source_family)
    row = {
        "label_source_id": f"{run_id}:LABEL:{_sha256_text('|'.join(key))[:16]}",
        "asset_id": profile.asset_id,
        "dimension": dimension,
        "label": label,
        "action": "RESPOND",
        "source_family": source_family,
        "method_id": method_id,
        "method_version": METHOD_VERSION,
        "raw_method_score": strength,
        "root_source_refs": sorted(set(root_refs)),
        "independent_support_unit": source_family,
    }
    previous = target.get(key)
    if previous is None or float(previous["raw_method_score"]) < strength:
        target[key] = row


def _propagate_labels(
    profiles: dict[str, _Profile],
    edges: list[dict[str, object]],
    label_rows: list[dict[str, object]],
    config: ClassificationConfig,
    graph_run_id: str,
    run_id: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    assets = sorted(profiles)
    adjacency: dict[str, dict[str, float]] = defaultdict(dict)
    for row in edges:
        left = str(row["left_asset_id"])
        right = str(row["right_asset_id"])
        weight = float(row["combined_score"])
        adjacency[left][right] = weight
        adjacency[right][left] = weight
    seeds: dict[tuple[str, str, str], float] = {}
    source_ids: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for row in label_rows:
        key = (str(row["asset_id"]), str(row["dimension"]), str(row["label"]))
        seeds[key] = max(seeds.get(key, 0.0), float(row["raw_method_score"]))
        source_ids[key].append(str(row["label_source_id"]))
    candidates: list[dict[str, object]] = []
    results: list[dict[str, object]] = []
    convergence: dict[str, int] = {}
    convergence_status: dict[str, bool] = {}
    final_deltas: dict[str, float] = {}
    for dimension, labels in sorted(config.taxonomy.items()):
        score_by_label: dict[str, dict[str, float]] = {}
        for label in sorted(labels):
            initial = {asset_id: seeds.get((asset_id, dimension, label), 0.0) for asset_id in assets}
            scores = dict(initial)
            iterations = 0
            converged = False
            final_delta = 0.0
            for iteration in range(1, config.propagation_max_iterations + 1):
                updated: dict[str, float] = {}
                delta = 0.0
                for asset_id in assets:
                    neighbors = adjacency.get(asset_id, {})
                    total_weight = sum(neighbors.values())
                    propagated = (
                        sum(weight * scores[neighbor] for neighbor, weight in neighbors.items()) / total_weight
                        if total_weight
                        else 0.0
                    )
                    value = max(
                        initial[asset_id],
                        (1.0 - config.propagation_alpha) * initial[asset_id]
                        + config.propagation_alpha * propagated,
                    )
                    value = min(value, 1.0)
                    updated[asset_id] = value
                    delta = max(delta, abs(value - scores[asset_id]))
                scores = updated
                iterations = iteration
                final_delta = delta
                if delta <= config.propagation_tolerance:
                    converged = True
                    break
            score_by_label[label] = scores
            convergence_key = f"{dimension}:{label}"
            convergence[convergence_key] = iterations
            convergence_status[convergence_key] = converged
            final_deltas[convergence_key] = round(final_delta, 12)
        dimension_converged = all(
            convergence_status[f"{dimension}:{label}"] for label in labels
        )
        for asset_id in assets:
            ranked = sorted(
                ((scores[asset_id], label) for label, scores in score_by_label.items()),
                key=lambda item: (-item[0], item[1]),
            )
            eligible = [item for item in ranked if item[0] >= config.candidate_threshold][
                : config.max_candidates_per_dimension
            ]
            candidate_ids: list[str] = []
            for score, label in eligible:
                candidate_id = f"{run_id}:BUSINESS_CLASS:{_sha256_text(f'{asset_id}|{dimension}|{label}')[:16]}"
                direct_source_ids = sorted(set(source_ids.get((asset_id, dimension, label), [])))
                propagated_from = sorted(
                    neighbor
                    for neighbor in adjacency.get(asset_id, {})
                    if score_by_label[label].get(neighbor, 0.0) > 0
                )[:5]
                candidates.append(
                    {
                        "candidate_id": candidate_id,
                        "run_id": run_id,
                        "subject_id": asset_id,
                        "dimension": dimension,
                        "label": label,
                        "method_id": PROPAGATION_METHOD_ID,
                        "method_version": METHOD_VERSION,
                        "raw_method_score": round(score, 6),
                        "graph_run_id": graph_run_id,
                        "supporting_label_source_ids": direct_source_ids,
                        "propagated_from_asset_ids": propagated_from,
                        "limitations": [
                            "method-local score; not a calibrated probability",
                            "automatic candidate; not ACCEPTED",
                        ],
                    }
                )
                candidate_ids.append(candidate_id)
            if not dimension_converged:
                outcome = "NOT_EVALUABLE"
                reason = "label propagation reached the configured iteration limit"
                candidate_ids = []
            elif not eligible:
                outcome = "UNKNOWN"
                reason = "no label reached the configured candidate threshold"
            elif len(eligible) >= 2 and eligible[0][0] - eligible[1][0] < config.competition_margin:
                outcome = "COMPETING"
                reason = "top labels are not sufficiently separated"
            else:
                outcome = "SINGLE_CANDIDATE"
                reason = "one candidate is separated under the configured method"
                candidate_ids = candidate_ids[:1]
            results.append(
                {
                    "inference_result_id": f"{run_id}:BUSINESS_CLASS_RESULT:{_sha256_text(f'{asset_id}|{dimension}')[:16]}",
                    "run_id": run_id,
                    "subject_id": asset_id,
                    "task_type": f"BUSINESS_CLASSIFICATION:{dimension}",
                    "method_id": PROPAGATION_METHOD_ID,
                    "method_version": METHOD_VERSION,
                    "evaluation_eligibility": (
                        "EVALUABLE" if dimension_converged else "NOT_EVALUABLE"
                    ),
                    "outcome": outcome,
                    "candidate_ids": candidate_ids,
                    "reason": reason,
                    "graph_run_id": graph_run_id,
                    "next_verification": "review family, source labels, conflicts, and targeted Wiki evidence",
                }
            )
    return candidates, results, {
        "propagation_max_iterations_used": max(convergence.values(), default=0),
        "propagation_iterations": convergence,
        "propagation_converged": all(convergence_status.values()),
        "propagation_nonconverged_labels": sorted(
            key for key, converged in convergence_status.items() if not converged
        ),
        "propagation_final_deltas": final_deltas,
    }


def _build_evidence_packs(
    profiles: dict[str, _Profile],
    families: list[dict[str, object]],
    memberships: list[dict[str, object]],
    edges: list[dict[str, object]],
    label_rows: list[dict[str, object]],
    wiki_source_id: str,
    config: ClassificationConfig,
) -> list[dict[str, object]]:
    members_by_family: dict[str, list[str]] = defaultdict(list)
    for row in memberships:
        members_by_family[str(row["family_candidate_id"])].append(str(row["asset_id"]))
    labels_by_asset: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in label_rows:
        labels_by_asset[str(row["asset_id"])].append(row)
    packs: list[dict[str, object]] = []
    strong = [row for row in families if row["status"] == "CANDIDATE"][: config.llm_max_families]
    for family in strong:
        family_id = str(family["family_candidate_id"])
        members = sorted(members_by_family[family_id])
        representatives = members[:12]
        allowed = {wiki_source_id}
        for asset_id in representatives:
            allowed.update(profiles[asset_id].root_source_refs)
        relevant_edges = [
            row
            for row in edges
            if str(row["left_asset_id"]) in representatives
            and str(row["right_asset_id"]) in representatives
        ][:20]
        pack = {
            "task": "OBJECT_FAMILY_NAMING",
            "scope": {"scope_id": "titans-panorama-v1"},
            "subject_ids": [family_id],
            "family": family,
            "representative_objects": [
                {
                    "asset_id": asset_id,
                    "schema_name": profiles[asset_id].schema_name,
                    "object_name": profiles[asset_id].object_name,
                    "object_comment": profiles[asset_id].object_comment,
                    "column_tokens": sorted(profiles[asset_id].column_tokens)[:30],
                }
                for asset_id in representatives
            ],
            "structural_edges": relevant_edges,
            "weak_labels": [
                row
                for asset_id in representatives
                for row in labels_by_asset.get(asset_id, [])
            ],
            "wiki_evidence": [wiki_source_id],
            "counterevidence": [
                asset_id
                for asset_id in representatives
                if not labels_by_asset.get(asset_id)
            ],
            "known_gaps": ["no business rows inspected", "candidate family is not a business category"],
            "allowed_evidence_ids": sorted(allowed),
        }
        pack["pack_id"] = _sha256_text(_canonical_json(pack))
        while len(_canonical_json(pack)) > config.llm_max_pack_chars and len(pack["representative_objects"]) > 2:
            removed = pack["representative_objects"].pop()
            removed_id = str(removed["asset_id"])
            pack["structural_edges"] = [
                row
                for row in pack["structural_edges"]
                if removed_id not in (row["left_asset_id"], row["right_asset_id"])
            ]
            pack["weak_labels"] = [
                row for row in pack["weak_labels"] if row["asset_id"] != removed_id
            ]
            pack["pack_id"] = _sha256_text(_canonical_json({key: value for key, value in pack.items() if key != "pack_id"}))
        packs.append(pack)
    return packs


def validate_llm_response(
    evidence_pack: dict[str, object],
    response: dict[str, object],
) -> dict[str, object]:
    """Validate one model response against its bounded Evidence Pack."""

    action = str(response.get("model_action", ""))
    if action not in {"RESPOND", "ABSTAIN"}:
        raise ValueError("model_action must be RESPOND or ABSTAIN")
    allowed = set(evidence_pack.get("allowed_evidence_ids", []) or [])
    cited = set(response.get("supported_by", []) or []) | set(
        response.get("contradicted_by", []) or []
    )
    invalid = cited - allowed
    if invalid:
        raise ValueError(f"invalid Evidence references: {sorted(invalid)}")
    if action == "ABSTAIN":
        if not response.get("abstain_reason"):
            raise ValueError("ABSTAIN requires abstain_reason")
        if response.get("proposed_name"):
            raise ValueError("ABSTAIN must not propose a name")
    elif not response.get("proposed_name"):
        raise ValueError("RESPOND requires proposed_name")
    return dict(response)


def run_llm_interpretation(
    evidence_packs: list[dict[str, object]],
    *,
    mode: str = "disabled",
    provider: Callable[[dict[str, object]], dict[str, object]] | None = None,
    cache_dir: str | Path | None = None,
    max_retries: int = 1,
) -> list[dict[str, object]]:
    """Run a bounded injected provider or preserve the disabled state."""

    if mode not in {"disabled", "approved"}:
        raise ValueError("LLM mode must be disabled or approved")
    if mode == "approved" and provider is None:
        raise ValueError("approved LLM mode requires an injected approved provider")
    cache_root = Path(cache_dir) if cache_dir else None
    rows: list[dict[str, object]] = []
    for pack in evidence_packs:
        pack_id = str(pack["pack_id"])
        if mode == "disabled":
            rows.append(
                {
                    "llm_task_result_id": f"llm-disabled:{pack_id[:16]}",
                    "pack_id": pack_id,
                    "evaluation_eligibility": "NOT_EVALUABLE",
                    "model_action": None,
                    "candidate_ids": [],
                    "abstain_reason": "D-005 provider and data-egress approval not recorded",
                    "source_family": "LLM_INTERPRETATION",
                    "root_source_refs": list(pack.get("allowed_evidence_ids", [])),
                }
            )
            continue
        cache_path = cache_root / f"{pack_id}.json" if cache_root else None
        response: dict[str, object] | None = None
        if cache_path and cache_path.exists():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(cached, dict):
                response = validate_llm_response(pack, cached)
        error: str | None = None
        if response is None:
            for _attempt in range(max_retries + 1):
                try:
                    assert provider is not None
                    response = validate_llm_response(pack, provider(pack))
                    break
                except (ValueError, TypeError) as exc:
                    error = str(exc)
            if response is not None and cache_path:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(_pretty_json(response), encoding="utf-8")
        if response is None:
            rows.append(
                {
                    "llm_task_result_id": f"llm-failed:{pack_id[:16]}",
                    "pack_id": pack_id,
                    "evaluation_eligibility": "EVALUABLE",
                    "status": "FAILED",
                    "model_action": None,
                    "candidate_ids": [],
                    "error": error,
                    "source_family": "LLM_INTERPRETATION",
                    "root_source_refs": list(pack.get("allowed_evidence_ids", [])),
                }
            )
            continue
        rows.append(
            {
                "llm_task_result_id": f"llm-result:{pack_id[:16]}",
                "pack_id": pack_id,
                "evaluation_eligibility": "EVALUABLE",
                "status": "SUCCESS",
                "model_action": response["model_action"],
                "candidate_ids": [],
                "weak_label_proposals": response.get("candidate_labels", []),
                "proposed_name": response.get("proposed_name"),
                "abstain_reason": response.get("abstain_reason"),
                "supported_evidence_ids": response.get("supported_by", []),
                "contradicted_evidence_ids": response.get("contradicted_by", []),
                "source_family": "LLM_INTERPRETATION",
                "root_source_refs": list(pack.get("allowed_evidence_ids", [])),
                "independent_evidence_increment": 0,
            }
        )
    return rows


def import_llm_responses(
    classification_dir: str | Path,
    response_file: str | Path,
    *,
    model_id: str,
) -> dict[str, object]:
    """Validate and persist responses produced by an authorized current GPT session."""

    root = Path(classification_dir)
    pack_path = root / "panorama" / "llm" / "evidence_packs.jsonl"
    packs = [
        json.loads(line)
        for line in pack_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    pack_by_id = {str(pack["pack_id"]): pack for pack in packs}
    supplied: dict[str, dict[str, object]] = {}
    for line_number, line in enumerate(
        Path(response_file).read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict) or not isinstance(row.get("pack_id"), str):
            raise ValueError(f"LLM response line {line_number} must include pack_id")
        pack_id = str(row.pop("pack_id"))
        if pack_id not in pack_by_id:
            raise ValueError(f"LLM response references unknown pack_id: {pack_id}")
        if pack_id in supplied:
            raise ValueError(f"duplicate LLM response for pack_id: {pack_id}")
        supplied[pack_id] = row
    missing = sorted(set(pack_by_id) - set(supplied))
    if missing:
        raise ValueError(f"missing LLM responses for {len(missing)} evidence packs")

    cache_dir = root / "panorama" / "llm" / "cache" / model_id
    rows = run_llm_interpretation(
        packs,
        mode="approved",
        provider=lambda pack: supplied[str(pack["pack_id"])],
        cache_dir=cache_dir,
        max_retries=0,
    )
    prompt_hash = _sha256_text(LLM_PROMPT_ID)
    for row in rows:
        response = supplied[str(row["pack_id"])]
        row.update(
            {
                "model_id": model_id,
                "prompt_id": LLM_PROMPT_ID,
                "prompt_hash": prompt_hash,
                "response_hash": _sha256_text(_canonical_json(response)),
                "execution_mode": "CURRENT_GPT_SESSION_IMPORT",
            }
        )

    json_path = root / "panorama" / "llm" / "llm_task_results.json"
    parquet_path = root / "panorama" / "llm" / "llm_task_results.parquet"
    json_path.write_text(_pretty_json(rows), encoding="utf-8")
    import pyarrow as pa
    import pyarrow.parquet as pq

    pq.write_table(pa.Table.from_pylist(rows), parquet_path)
    review_path = root / "panorama" / "classification-review" / "llm.html"
    review_path.write_text(
        _llm_review_html(rows, pack_by_id, model_id),
        encoding="utf-8",
    )
    index_path = root / "panorama" / "classification-review" / "index.html"
    index_html = index_path.read_text(encoding="utf-8")
    index_html = index_html.replace(
        "外部 LLM 当前禁用。",
        "当前GPT候选解释已导入；<a href='llm.html'>查看GPT审阅结果</a>。",
    )
    index_path.write_text(index_html, encoding="utf-8")
    manifest_path = root / "classification-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("classification manifest must be an object")
    manifest["llm_mode"] = "current_gpt_session_import"
    manifest["llm"] = {
        "model_id": model_id,
        "prompt_id": LLM_PROMPT_ID,
        "prompt_hash": prompt_hash,
        "response_file_sha256": _sha256_bytes(Path(response_file).read_bytes()),
        "response_count": len(rows),
        "respond_count": sum(row.get("model_action") == "RESPOND" for row in rows),
        "abstain_count": sum(row.get("model_action") == "ABSTAIN" for row in rows),
        "independent_evidence_increment": 0,
    }
    manifest["known_gaps"] = [
        gap
        for gap in manifest.get("known_gaps", [])
        if gap
        not in {
            "external LLM is disabled until D-005 approval",
            "current GPT interpretations are weak proposals, not business acceptance",
        }
    ] + ["current GPT interpretations are weak proposals, not business acceptance"]
    for output in manifest.get("outputs", []):
        if output.get("logical_name") == "llm_task_results_json":
            output["content_sha256"] = _sha256_bytes(json_path.read_bytes())
            output["row_count"] = len(rows)
        elif output.get("logical_name") == "llm_task_results_parquet":
            output["content_sha256"] = _sha256_bytes(parquet_path.read_bytes())
            output["row_count"] = len(rows)
        elif output.get("logical_name") == "review_index":
            output["content_sha256"] = _sha256_bytes(index_path.read_bytes())
    manifest["outputs"] = [
        output
        for output in manifest.get("outputs", [])
        if output.get("logical_name") != "llm_review"
    ]
    manifest["outputs"].append(
        {
            "logical_name": "llm_review",
            "relative_path": review_path.relative_to(root).as_posix(),
            "content_sha256": _sha256_bytes(review_path.read_bytes()),
            "row_count": len(rows),
            "status": "SUCCESS",
        }
    )
    manifest_path.write_text(_pretty_json(manifest), encoding="utf-8")
    return dict(manifest["llm"])


def _llm_review_html(
    rows: list[dict[str, object]],
    pack_by_id: dict[str, dict[str, object]],
    model_id: str,
) -> str:
    body = []
    for row in rows:
        pack = pack_by_id[str(row["pack_id"])]
        family = pack.get("family", {})
        body.append(
            "<tr>"
            f"<td>{escape(str(family.get('provisional_name', '')))}</td>"
            f"<td>{escape(str(family.get('member_count', '')))}</td>"
            f"<td>{escape(str(row.get('model_action', '')))}</td>"
            f"<td>{escape(str(row.get('proposed_name') or ''))}</td>"
            f"<td>{escape(str(row.get('abstain_reason') or ''))}</td>"
            f"<td><code>{escape(', '.join(row.get('supported_evidence_ids', []) or []))}</code></td>"
            "</tr>"
        )
    return (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        "<title>TRADEFLOW GPT candidate-family review</title>"
        "<style>body{font-family:system-ui;margin:2rem;line-height:1.5}"
        "table{border-collapse:collapse;width:100%}th,td{border:1px solid #ddd;"
        "padding:.55rem;vertical-align:top}th{background:#f4f4f4}code{font-size:.8rem}"
        ".warning{padding:1rem;background:#fff4ce;border-left:4px solid #d79b00}</style>"
        "</head><body><h1>TRADEFLOW GPT 候选族审阅</h1>"
        f"<p>Model: <code>{escape(model_id)}</code></p>"
        "<p class='warning'>这些名称是弱监督候选，不是业务验收结论；ABSTAIN 表示现有证据不足。</p>"
        "<table><thead><tr><th>技术族</th><th>成员数</th><th>动作</th>"
        "<th>GPT 临时名称</th><th>弃权原因</th><th>引用证据</th></tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></body></html>"
    )


def write_classification_results(
    output_dir: str | Path,
    result: ClassificationResult,
    *,
    formats: tuple[str, ...] = ("json", "parquet"),
    source_panorama_root: str | Path | None = None,
) -> dict[str, Path]:
    """Write classification artifacts, a deterministic manifest, and review HTML."""

    root = Path(output_dir)
    rows_by_name = {
        "schema_match_signals": ("panorama/derived", result.schema_match_signals),
        "similarity_edges": ("panorama/derived", result.similarity_edges),
        "community_partitions": ("panorama/derived", result.community_partitions),
        "family_candidates": ("panorama/candidates", result.family_candidates),
        "family_memberships": ("panorama/candidates", result.family_memberships),
        "label_source_outputs": ("panorama/candidates", result.label_source_outputs),
        "business_class_candidates": ("panorama/candidates", result.business_class_candidates),
        "business_classification_results": ("panorama/candidates", result.classification_results),
        "wiki_sources": ("panorama/evidence", result.wiki_sources),
        "llm_task_results": ("panorama/llm", result.llm_task_results),
    }
    paths: dict[str, Path] = {}
    for logical_name, (subdir, rows) in rows_by_name.items():
        if "json" in formats:
            path = root / subdir / f"{logical_name}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_pretty_json(rows), encoding="utf-8")
            paths[f"{logical_name}_json"] = path
        if "parquet" in formats:
            import pyarrow as pa
            import pyarrow.parquet as pq

            path = root / subdir / f"{logical_name}.parquet"
            path.parent.mkdir(parents=True, exist_ok=True)
            pq.write_table(pa.Table.from_pylist(rows), path)
            paths[f"{logical_name}_parquet"] = path
    pack_path = root / "panorama" / "llm" / "evidence_packs.jsonl"
    pack_path.parent.mkdir(parents=True, exist_ok=True)
    pack_path.write_text(
        "".join(_canonical_json(pack) + "\n" for pack in result.evidence_packs),
        encoding="utf-8",
    )
    paths["evidence_packs"] = pack_path
    review_path = root / "panorama" / "classification-review" / "index.html"
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(
        _review_html(result, source_panorama_root),
        encoding="utf-8",
    )
    paths["review_index"] = review_path
    outputs = []
    for logical_name, path in sorted(paths.items()):
        outputs.append(
            {
                "logical_name": logical_name,
                "relative_path": path.relative_to(root).as_posix(),
                "content_sha256": _sha256_bytes(path.read_bytes()),
                "row_count": _row_count(logical_name, result),
                "status": "SUCCESS",
            }
        )
    manifest = {
        "run_id": result.run_id,
        "stage_id": "panorama-business-classification",
        "stage_status": "PARTIAL" if result.stats.get("limits_hit") else "SUCCESS",
        "graph_run_id": result.graph_run_id,
        "config_sha256": result.config_hash,
        "wiki_source": result.wiki_sources[0] if result.wiki_sources else None,
        "methods": [MATCH_METHOD_ID, FAMILY_METHOD_ID, PROPAGATION_METHOD_ID],
        "llm_mode": "disabled",
        "stats": result.stats,
        "outputs": outputs,
        "known_gaps": [
            "candidate classifications are not business accepted",
            "no business rows were queried",
            "external LLM is disabled until D-005 approval",
        ],
    }
    manifest_path = root / "classification-manifest.json"
    manifest_path.write_text(_pretty_json(manifest), encoding="utf-8")
    paths["manifest"] = manifest_path
    return paths


def _review_html(
    result: ClassificationResult,
    source_panorama_root: str | Path | None,
) -> str:
    candidate_by_id = {str(row["candidate_id"]): row for row in result.business_class_candidates}
    family_rows = "".join(
        f"<tr><td>{escape(str(row['provisional_name']))}</td><td>{escape(str(row['status']))}</td>"
        f"<td>{row['member_count']}</td><td>{row['multi_view_edge_count']}</td></tr>"
        for row in result.family_candidates[:200]
    )
    classification_rows = []
    for row in result.classification_results[:1000]:
        labels = [
            str(candidate_by_id[candidate_id]["label"])
            for candidate_id in row.get("candidate_ids", [])
            if candidate_id in candidate_by_id
        ]
        asset_id = str(row["subject_id"])
        link = escape(asset_id)
        if source_panorama_root:
            from .render import _slug

            target = (Path(source_panorama_root) / "objects" / f"{_slug(asset_id)}.html").resolve()
            link = f'<a href="{target.as_uri()}">{escape(asset_id)}</a>'
        classification_rows.append(
            f"<tr><td>{link}</td><td>{escape(str(row['task_type']).split(':', 1)[-1])}</td>"
            f"<td>{escape(str(row['outcome']))}</td><td>{escape(', '.join(labels))}</td>"
            f"<td>{escape(str(row['reason']))}</td></tr>"
        )
    stats = result.stats
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>TITANS 候选分类审阅</title>
<style>body{{font-family:Arial,"Microsoft YaHei",sans-serif;margin:24px;color:#243247}}table{{border-collapse:collapse;width:100%;margin:16px 0}}th,td{{border:1px solid #d8dee8;padding:7px;text-align:left;vertical-align:top}}th{{background:#eef3f8}}.warning{{background:#fff3cd;border:1px solid #e0b84f;padding:12px}}.stats{{display:flex;gap:12px;flex-wrap:wrap}}.stat{{background:#f4f7fa;padding:10px 14px;border-radius:6px}}</style></head>
<body><h1>TITANS 候选分类审阅</h1>
<div class="warning"><strong>尚未业务验收。</strong> Schema Matching 只表示结构相似；Leiden community 只表示运行级候选族；自动分类均为 Candidate/Competing/Unknown，不存在自动 Accepted。外部 LLM 当前禁用。</div>
<div class="stats"><div class="stat">对象 {stats.get('object_count', 0)}</div><div class="stat">边 {stats.get('edge_count', 0)}</div><div class="stat">候选族 {stats.get('candidate_family_count', 0)}</div><div class="stat">弱族 {stats.get('weak_family_count', 0)}</div><div class="stat">Unknown {stats.get('unknown_count', 0)}</div><div class="stat">Conflict/Competing {stats.get('competing_count', 0)}</div></div>
<h2>候选族</h2><table><thead><tr><th>临时名称</th><th>状态</th><th>成员</th><th>多视角边</th></tr></thead><tbody>{family_rows}</tbody></table>
<h2>分类结果（最多展示 1000 项）</h2><table><thead><tr><th>对象</th><th>维度</th><th>结果</th><th>候选</th><th>原因</th></tr></thead><tbody>{''.join(classification_rows)}</tbody></table>
<p>graph_run_id: {escape(result.graph_run_id)}；同一图用于 Leiden 与一次标签传播，但 candidate family 不增加标签票数。</p></body></html>"""


def _mapping(value: dict[str, object], key: str) -> dict[str, object]:
    item = value.get(key, {})
    if not isinstance(item, dict):
        raise ValueError(f"{key} must be a mapping")
    return item


def _positive_int(value: dict[str, object], key: str, default: int) -> int:
    result = int(value.get(key, default))
    if result <= 0:
        raise ValueError(f"{key} must be positive")
    return result


def _validate_wiki_metadata(
    config: ClassificationConfig,
    metadata: dict[str, object],
) -> None:
    if str(metadata.get("pageId", "")) != config.wiki_page_id:
        raise ValueError("Wiki page ID does not match classification config")
    if not metadata.get("contentHash") or metadata.get("version") is None or metadata.get("cachedAt") is None:
        raise ValueError("Wiki metadata must include contentHash, version, and cachedAt")


def _single_run_id(facts: PhysicalFacts) -> str:
    run_ids = sorted({str(row.get("run_id")) for row in facts.objects if row.get("run_id")})
    if len(run_ids) != 1:
        raise ValueError(f"classification requires exactly one physical run, got {run_ids}")
    return run_ids[0]


def _name_tokens(value: str) -> set[str]:
    return {token for token in _ASCII_TOKEN.findall(value.upper()) if token}


def _char_ngrams(value: str, size: int = 3) -> set[str]:
    normalized = re.sub(r"[^A-Z0-9]", "", value.upper())
    if len(normalized) < size:
        return set()
    return {f"NGRAM:{normalized[index:index + size]}" for index in range(len(normalized) - size + 1)}


def _text_tokens(value: str) -> set[str]:
    tokens = _name_tokens(value)
    for segment in _CHINESE_TEXT.findall(value):
        if len(segment) == 1:
            tokens.add(segment)
        else:
            tokens.update(f"ZH:{segment[index:index + 2]}" for index in range(len(segment) - 1))
    return tokens


def _type_family(value: str) -> str:
    upper = value.upper()
    if any(token in upper for token in ("CHAR", "CLOB", "TEXT")):
        return "TEXT"
    if any(token in upper for token in ("NUMBER", "DECIMAL", "FLOAT", "INT")):
        return "NUMBER"
    if any(token in upper for token in ("DATE", "TIME", "INTERVAL")):
        return "TEMPORAL"
    if any(token in upper for token in ("RAW", "BLOB", "BINARY")):
        return "BINARY"
    return upper or "UNKNOWN"


def _inverted_index(
    profiles: dict[str, _Profile],
    attribute: str,
) -> dict[str, list[str]]:
    index: dict[str, list[str]] = defaultdict(list)
    for asset_id, profile in profiles.items():
        for token in getattr(profile, attribute):
            index[token].append(asset_id)
    return index


def _idf(index: dict[str, list[str]], object_count: int) -> dict[str, float]:
    return {
        token: math.log((1 + object_count) / (1 + len(set(assets)))) + 1.0
        for token, assets in index.items()
    }


def _weighted_jaccard(
    left: Iterable[str],
    right: Iterable[str],
    weights: dict[str, float],
) -> float:
    left_set = set(left)
    right_set = set(right)
    union = left_set | right_set
    if not union:
        return 0.0
    numerator = sum(weights.get(token, 1.0) for token in left_set & right_set)
    denominator = sum(weights.get(token, 1.0) for token in union)
    return numerator / denominator if denominator else 0.0


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    union = left_set | right_set
    return len(left_set & right_set) / len(union) if union else 0.0


def _counter_similarity(
    left_items: tuple[tuple[str, int], ...],
    right_items: tuple[tuple[str, int], ...],
) -> float | None:
    left = dict(left_items)
    right = dict(right_items)
    if not left or not right:
        return None
    labels = set(left) | set(right)
    numerator = sum(min(left.get(label, 0), right.get(label, 0)) for label in labels)
    denominator = sum(max(left.get(label, 0), right.get(label, 0)) for label in labels)
    return numerator / denominator if denominator else 0.0


def _combined_score(
    scores: dict[str, float | None],
    weights: dict[str, float],
) -> float:
    available = [(key, value) for key, value in scores.items() if value is not None and key in weights]
    denominator = sum(weights[key] for key, _value in available)
    return (
        sum(weights[key] * float(value) for key, value in available) / denominator
        if denominator
        else 0.0
    )


def _term_matches(term: str, haystack: str) -> bool:
    if not term:
        return False
    if _CHINESE_TEXT.search(term):
        return term in haystack
    tokens = set(_ASCII_TOKEN.findall(haystack))
    return term in tokens or term in haystack.split("_")


def _wiki_source_id(metadata: dict[str, object]) -> str:
    return f"wiki:{metadata['pageId']}:{str(metadata['contentHash'])[:16]}"


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _pretty_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _row_count(logical_name: str, result: ClassificationResult) -> int | None:
    lookup = {
        "schema_match_signals_json": result.schema_match_signals,
        "schema_match_signals_parquet": result.schema_match_signals,
        "similarity_edges_json": result.similarity_edges,
        "similarity_edges_parquet": result.similarity_edges,
        "community_partitions_json": result.community_partitions,
        "community_partitions_parquet": result.community_partitions,
        "family_candidates_json": result.family_candidates,
        "family_candidates_parquet": result.family_candidates,
        "family_memberships_json": result.family_memberships,
        "family_memberships_parquet": result.family_memberships,
        "label_source_outputs_json": result.label_source_outputs,
        "label_source_outputs_parquet": result.label_source_outputs,
        "business_class_candidates_json": result.business_class_candidates,
        "business_class_candidates_parquet": result.business_class_candidates,
        "business_classification_results_json": result.classification_results,
        "business_classification_results_parquet": result.classification_results,
        "wiki_sources_json": result.wiki_sources,
        "wiki_sources_parquet": result.wiki_sources,
        "llm_task_results_json": result.llm_task_results,
        "llm_task_results_parquet": result.llm_task_results,
        "evidence_packs": result.evidence_packs,
    }
    rows = lookup.get(logical_name)
    return len(rows) if rows is not None else None
