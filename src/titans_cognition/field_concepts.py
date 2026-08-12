"""Lightweight, replayable field-concept discovery from physical metadata."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata

import yaml

from .extract import PhysicalFacts


METHOD_ID = "field_concepts.tfidf_hierarchy.v1"
METHOD_VERSION = "v1"

_NUMERIC_SUFFIX = re.compile(r"\d+$")
_ENGLISH_TOKEN = re.compile(r"[A-Z]+|\d+")
_SPACE = re.compile(r"\s+")
_PUNCTUATION = re.compile(r"[，,；;。.!！？?：:]|　")
_TRAILING_NOISE = re.compile(r"(?:字段|信息|数据)$")
_GENERIC_NAME_TOKENS = {
    "ID",
    "CODE",
    "TYPE",
    "STATUS",
    "FLAG",
    "VALUE",
    "AMOUNT",
    "NUMBER",
    "NAME",
    "DATA",
}
_QUALIFIER_TOKEN_LABELS = {
    "INITIAL": "初始",
    "CURRENT": "当前",
    "DYNAMIC": "动态",
    "BEFORE": "调整前",
    "AFTER": "调整后",
    "DELTA": "变动",
    "ABS": "绝对",
    "ABSOLUTE": "绝对",
    "LONG": "多头",
    "SHORT": "空头",
}


@dataclass(frozen=True)
class FieldConceptConfig:
    """Validated configuration for one bounded field-concept run."""

    source_text: str
    raw: dict[str, object]
    config_hash: str
    schemas: tuple[str, ...]
    object_types: tuple[str, ...]
    exclude_numeric_suffix: bool
    expected_object_count: int | None
    expected_excluded_count: int | None
    top_k: int
    max_candidates_per_field: int
    max_candidate_pairs: int
    max_feature_frequency: int
    min_similarity: float
    base_cluster_threshold: float
    qualified_cluster_threshold: float
    weights: dict[str, float]
    abbreviations: dict[str, str]
    broad_categories: dict[str, dict[str, object]]
    base_concepts: dict[str, dict[str, object]]

    def with_expected_object_count(self, count: int) -> "FieldConceptConfig":
        """Return a test-friendly copy with a different expected object count."""

        return replace(self, expected_object_count=count)


@dataclass
class FieldConceptResult:
    """Minimal canonical outputs plus run-local profiles and diagnostics."""

    run_id: str
    config_hash: str
    concepts: list[dict[str, object]] = field(default_factory=list)
    links: list[dict[str, object]] = field(default_factory=list)
    field_profiles: list[dict[str, object]] = field(default_factory=list)
    diagnostics: list[dict[str, object]] = field(default_factory=list)
    stats: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class _Profile:
    index: int
    field_id: str
    asset_id: str
    schema_name: str
    object_name: str
    object_comment: str
    field_name: str
    field_comment: str
    name_tokens: tuple[str, ...]
    normalized_comment: str
    data_type: str
    type_family: str
    broad_category: str
    base_concept: str
    display_label: str


def load_field_concept_config(path: str | Path) -> FieldConceptConfig:
    """Load a content-addressed YAML configuration."""

    source_text = Path(path).read_text(encoding="utf-8")
    value = yaml.safe_load(source_text)
    if not isinstance(value, dict):
        raise ValueError("field concept config must be a mapping")
    scope = _mapping(value, "scope")
    limits = _mapping(value, "limits")
    similarity = _mapping(value, "similarity")
    weights = _string_float_mapping(similarity.get("weights", {}), "similarity.weights")
    for required in ("name", "comment", "context", "type"):
        if required not in weights:
            raise ValueError(f"similarity.weights missing {required!r}")
    schemas = _string_tuple(scope.get("schemas"), "scope.schemas")
    object_types = _string_tuple(scope.get("object_types"), "scope.object_types")
    broad = _mapping(value, "broad_categories")
    bases = value.get("base_concepts", {})
    if not isinstance(bases, dict):
        raise ValueError("base_concepts must be a mapping")
    abbreviations = value.get("abbreviations", {})
    if not isinstance(abbreviations, dict):
        raise ValueError("abbreviations must be a mapping")
    if any(
        not isinstance(key, str) or not isinstance(item, str)
        for key, item in abbreviations.items()
    ):
        raise ValueError(
            "abbreviations keys and values must be strings; quote YAML words such as NO"
        )
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return FieldConceptConfig(
        source_text=source_text,
        raw=value,
        config_hash=_sha256_text(canonical),
        schemas=tuple(item.upper() for item in schemas),
        object_types=tuple(item.upper() for item in object_types),
        exclude_numeric_suffix=bool(scope.get("exclude_numeric_suffix", False)),
        expected_object_count=_optional_int(scope.get("expected_object_count")),
        expected_excluded_count=_optional_int(scope.get("expected_excluded_count")),
        top_k=_positive_int(limits, "top_k", 12),
        max_candidates_per_field=_positive_int(
            limits, "max_candidates_per_field", 500
        ),
        max_candidate_pairs=_positive_int(limits, "max_candidate_pairs", 250_000),
        max_feature_frequency=_positive_int(
            limits, "max_feature_frequency", 220
        ),
        min_similarity=float(similarity.get("min_similarity", 0.22)),
        base_cluster_threshold=float(
            similarity.get("base_cluster_threshold", 0.42)
        ),
        qualified_cluster_threshold=float(
            similarity.get("qualified_cluster_threshold", 0.66)
        ),
        weights=weights,
        abbreviations={str(key).upper(): str(item).upper() for key, item in abbreviations.items()},
        broad_categories={str(key): _rule_mapping(item, f"broad_categories.{key}") for key, item in broad.items()},
        base_concepts={str(key): _rule_mapping(item, f"base_concepts.{key}") for key, item in bases.items()},
    )


def run_field_concepts(
    facts: PhysicalFacts,
    config: FieldConceptConfig,
) -> FieldConceptResult:
    """Discover a bounded three-level field concept tree."""

    selected, excluded = _select_objects(facts, config)
    _validate_scope_counts(config, selected, excluded)
    selected_ids = {str(row["asset_id"]) for row in selected}
    object_by_id = {str(row["asset_id"]): row for row in selected}
    columns = [row for row in facts.columns if str(row.get("asset_id", "")) in selected_ids]
    columns.sort(key=lambda row: str(row.get("column_id", "")))
    if not columns:
        raise ValueError("field concept scope contains no columns")
    run_ids = {str(row.get("run_id", "")) for row in selected}
    if len(run_ids) != 1:
        raise ValueError(f"field concept scope requires one run_id, got {sorted(run_ids)}")

    profiles = [
        _build_profile(index, column, object_by_id[str(column["asset_id"])], config)
        for index, column in enumerate(columns)
    ]
    matrix = _vectorize(profiles, config)
    neighbors, candidate_pairs, candidate_limit_hit = _nearest_neighbors(matrix, config)
    concepts, primary_by_field = _build_concept_tree(
        profiles,
        neighbors,
        config,
    )
    links = _build_links(profiles, concepts, primary_by_field, neighbors, config)
    direct_member_counts = Counter(
        str(row["concept_id"]) for row in links if int(row.get("rank", 1)) == 1
    )
    concept_by_id = {str(row["concept_id"]): row for row in concepts}
    member_counts = Counter(direct_member_counts)
    for concept_id, count in direct_member_counts.items():
        parent_id = concept_by_id.get(concept_id, {}).get("parent_id")
        while parent_id:
            member_counts[str(parent_id)] += count
            parent_id = concept_by_id.get(str(parent_id), {}).get("parent_id")
    for concept in concepts:
        concept["member_count"] = member_counts.get(str(concept["concept_id"]), 0)
    concepts.sort(key=lambda row: (int(row["level"]), str(row["label"]), str(row["concept_id"])))
    links.sort(key=lambda row: (str(row["field_id"]), int(row["rank"]), str(row["concept_id"])))
    diagnostics = _diagnostic_rows(profiles, neighbors)
    assigned = {str(row["field_id"]) for row in links if int(row["rank"]) == 1}
    field_profiles = [_profile_row(profile) for profile in profiles]
    stats = {
        "object_count": len(selected),
        "excluded_object_count": len(excluded),
        "field_count": len(profiles),
        "assigned_field_count": len(assigned),
        "unassigned_field_count": len(profiles) - len(assigned),
        "concept_count": len(concepts),
        "link_count": len(links),
        "candidate_pair_count": candidate_pairs,
        "candidate_limit_hit": candidate_limit_hit,
        "llm_mode": "disabled",
    }
    return FieldConceptResult(
        run_id=next(iter(run_ids)),
        config_hash=config.config_hash,
        concepts=concepts,
        links=links,
        field_profiles=field_profiles,
        diagnostics=diagnostics,
        stats=stats,
    )


def write_field_concept_results(
    output_dir: str | Path,
    result: FieldConceptResult,
    *,
    write_diagnostics: bool = False,
    source_panorama_root: str | Path | None = None,
) -> dict[str, Path]:
    """Write the minimal canonical contract and a local review projection."""

    root = Path(output_dir) / "field-concepts"
    root.mkdir(parents=True, exist_ok=True)
    concepts_path = root / "concepts.jsonl"
    links_path = root / "field_concept_links.jsonl"
    concepts_path.write_text(_jsonl(result.concepts), encoding="utf-8")
    links_path.write_text(_jsonl(result.links), encoding="utf-8")
    review_path = root / "review" / "index.html"
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(
        _review_html(result, source_panorama_root=source_panorama_root),
        encoding="utf-8",
    )
    diagnostics_path = root / "diagnostics.jsonl"
    if write_diagnostics:
        diagnostics_path.write_text(_jsonl(result.diagnostics), encoding="utf-8")
    elif diagnostics_path.exists():
        diagnostics_path.unlink()
    outputs = [
        _output_entry("concepts", concepts_path, root, len(result.concepts)),
        _output_entry("field_concept_links", links_path, root, len(result.links)),
    ]
    manifest = {
        "run_id": result.run_id,
        "stage_id": "field-concept-index",
        "stage_status": "PARTIAL" if result.stats.get("candidate_limit_hit") else "SUCCESS",
        "config_sha256": result.config_hash,
        "method_id": METHOD_ID,
        "method_version": METHOD_VERSION,
        "llm_mode": "disabled",
        "stats": result.stats,
        "outputs": outputs,
        "known_gaps": [
            "concept hierarchy is candidate navigation, not a formal ontology",
            "no business rows were queried",
            "cross-schema generalization is not validated",
        ],
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(_pretty_json(manifest), encoding="utf-8")
    return {
        "concepts": concepts_path,
        "links": links_path,
        "manifest": manifest_path,
        "review_index": review_path,
    }


def _select_objects(
    facts: PhysicalFacts,
    config: FieldConceptConfig,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    in_scope = []
    excluded = []
    for row in facts.objects:
        schema = str(row.get("schema_name", "")).upper()
        object_type = str(row.get("object_type", "")).upper()
        if schema not in config.schemas or object_type not in config.object_types:
            continue
        if not bool(row.get("in_panorama_scope", True)) or bool(row.get("is_boundary", False)):
            continue
        if config.exclude_numeric_suffix and _NUMERIC_SUFFIX.search(str(row.get("object_name", ""))):
            excluded.append(row)
        else:
            in_scope.append(row)
    in_scope.sort(key=lambda row: str(row.get("asset_id", "")))
    excluded.sort(key=lambda row: str(row.get("asset_id", "")))
    return in_scope, excluded


def _validate_scope_counts(
    config: FieldConceptConfig,
    selected: list[dict[str, object]],
    excluded: list[dict[str, object]],
) -> None:
    if config.expected_object_count is not None and len(selected) != config.expected_object_count:
        raise ValueError(
            f"expected {config.expected_object_count} objects, got {len(selected)}"
        )
    if config.expected_excluded_count is not None and len(excluded) != config.expected_excluded_count:
        raise ValueError(
            f"expected {config.expected_excluded_count} excluded objects, got {len(excluded)}"
        )


def _build_profile(
    index: int,
    column: dict[str, object],
    object_row: dict[str, object],
    config: FieldConceptConfig,
) -> _Profile:
    field_name = str(column.get("column_name", ""))
    comment = str(column.get("column_comment") or "")
    name_tokens = _name_tokens(field_name, config.abbreviations)
    normalized_comment = _normalize_comment(comment)
    type_family = _type_family(str(column.get("data_type", "")))
    name_signal = " ".join(name_tokens)
    signal_text = name_signal + " " + normalized_comment
    broad_category = _broad_category(
        name_signal,
        normalized_comment,
        type_family,
        config,
    )
    base_concept = _base_concept(signal_text, broad_category, config)
    display_label = _display_label(normalized_comment, name_tokens)
    return _Profile(
        index=index,
        field_id=str(column["column_id"]),
        asset_id=str(column["asset_id"]),
        schema_name=str(object_row.get("schema_name", "")),
        object_name=str(object_row.get("object_name", "")),
        object_comment=str(object_row.get("object_comment") or ""),
        field_name=field_name,
        field_comment=comment,
        name_tokens=name_tokens,
        normalized_comment=normalized_comment,
        data_type=str(column.get("data_type", "")),
        type_family=type_family,
        broad_category=broad_category,
        base_concept=base_concept,
        display_label=display_label,
    )


def _vectorize(profiles: list[_Profile], config: FieldConceptConfig):
    dimension = 4096
    document_counts: list[dict[int, float]] = []
    document_frequency: Counter[int] = Counter()
    for profile in profiles:
        counts: dict[int, float] = defaultdict(float)
        sources = [
            (
                "NAME",
                " ".join(profile.name_tokens),
                config.weights["name"],
                (2, 3),
            ),
            (
                "COMMENT",
                profile.normalized_comment,
                config.weights["comment"],
                (2, 3),
            ),
            (
                "CONTEXT",
                f"{profile.object_name} {profile.object_comment}",
                config.weights["context"],
                (2, 2),
            ),
            (
                "TYPE",
                profile.type_family,
                config.weights["type"],
                (2, 3),
            ),
        ]
        for prefix, text, weight, ngram_range in sources:
            if not text or weight <= 0:
                continue
            features = _text_features(prefix, text, ngram_range)
            for feature, count in Counter(features).items():
                bucket = _feature_bucket(feature, dimension)
                counts[bucket] += float(count) * float(weight)
        document_counts.append(dict(counts))
        document_frequency.update(counts)
    if not any(document_counts):
        raise ValueError("field concept vectorization produced no features")
    vectors: list[dict[int, float]] = []
    total = len(profiles)
    for counts in document_counts:
        weighted: dict[int, float] = {}
        for bucket, count in counts.items():
            frequency = document_frequency[bucket]
            if frequency > config.max_feature_frequency:
                continue
            inverse_document_frequency = math.log((1 + total) / (1 + frequency)) + 1.0
            weighted[bucket] = (
                math.log1p(count) * inverse_document_frequency
            )
        norm = math.sqrt(sum(value * value for value in weighted.values())) or 1.0
        vectors.append({bucket: value / norm for bucket, value in weighted.items()})
    return vectors


def _nearest_neighbors(vectors, config: FieldConceptConfig):
    count = len(vectors)
    neighbor_count = min(config.top_k, max(0, count - 1))
    neighbors: dict[int, list[tuple[int, float]]] = defaultdict(list)
    unique_pairs: set[tuple[int, int]] = set()
    candidate_limit_hit = False
    if neighbor_count == 0:
        return neighbors, 0, False
    postings: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for index, vector in enumerate(vectors):
        for feature, weight in vector.items():
            postings[feature].append((index, weight))
    for left, vector in enumerate(vectors):
        scores: dict[int, float] = defaultdict(float)
        for feature, left_weight in vector.items():
            for right, right_weight in postings[feature]:
                if right != left:
                    scores[right] += left_weight * right_weight
        if len(scores) > config.max_candidates_per_field:
            scored = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[
                : config.max_candidates_per_field
            ]
        else:
            scored = scores.items()
        rows = [
            (int(right), round(float(score), 6))
            for right, score in scored
            if float(score) >= config.min_similarity
        ]
        rows.sort(key=lambda item: (-item[1], item[0]))
        neighbors[left] = rows[:neighbor_count]
        for right, _ in neighbors[left]:
            unique_pairs.add((min(left, right), max(left, right)))
            if len(unique_pairs) >= config.max_candidate_pairs:
                candidate_limit_hit = True
                break
        if candidate_limit_hit:
            break
    if candidate_limit_hit:
        allowed = unique_pairs
        for left in list(neighbors):
            neighbors[left] = [
                (right, score)
                for right, score in neighbors[left]
                if (min(left, right), max(left, right)) in allowed
            ]
    return neighbors, len(unique_pairs), candidate_limit_hit


def _build_concept_tree(
    profiles: list[_Profile],
    neighbors: dict[int, list[tuple[int, float]]],
    config: FieldConceptConfig,
) -> tuple[list[dict[str, object]], dict[str, tuple[str, float, str]]]:
    concepts: dict[str, dict[str, object]] = {}
    primary: dict[str, tuple[str, float, str]] = {}

    def ensure(label: str, level: int, parent_id: str | None) -> str:
        concept_id = _concept_id(label, level, parent_id)
        concepts.setdefault(
            concept_id,
            {
                "concept_id": concept_id,
                "label": label,
                "level": level,
                "parent_id": parent_id,
                "status": "CANDIDATE",
                "method_id": METHOD_ID,
                "method_version": METHOD_VERSION,
                "member_count": 0,
            },
        )
        return concept_id

    unanchored_by_broad: dict[str, list[int]] = defaultdict(list)
    for profile in profiles:
        broad = profile.broad_category or "其他"
        broad_id = ensure(broad, 1, None)
        if profile.base_concept:
            base_id = ensure(profile.base_concept, 2, broad_id)
            base_rule = config.base_concepts.get(profile.base_concept, {})
            qualified = _qualified_label(
                profile,
                profile.base_concept,
                tuple(str(term) for term in base_rule.get("terms", [])),
            )
            if qualified:
                concept_id = ensure(qualified, 3, base_id)
                primary[profile.field_id] = (concept_id, 1.0, "TAXONOMY_QUALIFIED")
            else:
                primary[profile.field_id] = (base_id, 0.95, "TAXONOMY_BASE")
        else:
            unanchored_by_broad[broad].append(profile.index)

    for broad, indices in sorted(unanchored_by_broad.items()):
        broad_id = ensure(broad, 1, None)
        clusters = _cluster_indices(indices, neighbors, config.base_cluster_threshold)
        for cluster_indices in clusters:
            if len(cluster_indices) < 2:
                # A surface label with no supporting neighbor is not a concept.
                # Keep the physical field available as unassigned instead.
                continue
            members = [profiles[index] for index in cluster_indices]
            base_label = _cluster_label(members)
            if not base_label:
                continue
            base_id = ensure(base_label, 2, broad_id)
            qualified_clusters = _cluster_indices(
                cluster_indices,
                neighbors,
                config.qualified_cluster_threshold,
            )
            multiple_labels = len({member.display_label for member in members if member.display_label}) > 1
            for qualified_indices in qualified_clusters:
                qualified_members = [profiles[index] for index in qualified_indices]
                qualified_label = _cluster_label(qualified_members)
                use_qualified = (
                    multiple_labels
                    and bool(qualified_label)
                    and qualified_label != base_label
                )
                concept_id = (
                    ensure(qualified_label, 3, base_id) if use_qualified else base_id
                )
                method = "TFIDF_HIERARCHY"
                score = 0.8
                for member in qualified_members:
                    primary[member.field_id] = (concept_id, score, method)
    return list(concepts.values()), primary


def _cluster_indices(
    indices: list[int],
    neighbors: dict[int, list[tuple[int, float]]],
    threshold: float,
) -> list[list[int]]:
    if not indices:
        return []
    if len(indices) == 1:
        return [list(indices)]
    allowed = set(indices)
    scores: dict[tuple[int, int], float] = {}
    for left in indices:
        for right, score in neighbors.get(left, []):
            if right in allowed:
                key = (min(left, right), max(left, right))
                scores[key] = max(scores.get(key, 0.0), score)
    edges = sorted(
        (
            (score, left, right)
            for (left, right), score in scores.items()
            if score >= threshold
        ),
        key=lambda item: (-item[0], item[1], item[2]),
    )
    clusters: dict[int, set[int]] = {index: {index} for index in indices}
    owner = {index: index for index in indices}
    for _, left, right in edges:
        left_owner = owner[left]
        right_owner = owner[right]
        if left_owner == right_owner:
            continue
        left_members = clusters[left_owner]
        right_members = clusters[right_owner]
        if any(
            scores.get((min(a, b), max(a, b)), 0.0) < threshold
            for a in left_members
            for b in right_members
        ):
            continue
        keep = min(left_owner, right_owner)
        remove = max(left_owner, right_owner)
        merged = clusters[keep] | clusters[remove]
        clusters[keep] = merged
        del clusters[remove]
        for member in merged:
            owner[member] = keep
    return [sorted(clusters[key]) for key in sorted(clusters)]


def _build_links(
    profiles: list[_Profile],
    concepts: list[dict[str, object]],
    primary: dict[str, tuple[str, float, str]],
    neighbors: dict[int, list[tuple[int, float]]],
    config: FieldConceptConfig,
) -> list[dict[str, object]]:
    links = []
    primary_concept = {field_id: row[0] for field_id, row in primary.items()}
    for profile in profiles:
        assignment = primary.get(profile.field_id)
        if not assignment:
            continue
        concept_id, score, method = assignment
        links.append(
            _link_row(profile, concept_id, score, method, "CANDIDATE", 1)
        )
        alternatives: dict[str, float] = {}
        for neighbor_index, similarity in neighbors.get(profile.index, []):
            if similarity < config.qualified_cluster_threshold:
                continue
            neighbor = profiles[neighbor_index]
            neighbor_concept = primary_concept.get(neighbor.field_id)
            if not neighbor_concept or neighbor_concept == concept_id:
                continue
            if neighbor.broad_category != profile.broad_category:
                continue
            alternatives[neighbor_concept] = max(
                alternatives.get(neighbor_concept, 0.0), similarity
            )
        if alternatives:
            alternate_id, alternate_score = sorted(
                alternatives.items(), key=lambda item: (-item[1], item[0])
            )[0]
            links.append(
                _link_row(
                    profile,
                    alternate_id,
                    alternate_score,
                    "TFIDF_NEIGHBOR",
                    "AMBIGUOUS",
                    2,
                )
            )
    known = {str(row["concept_id"]) for row in concepts}
    if any(str(row["concept_id"]) not in known for row in links):
        raise ValueError("field concept link references an unknown concept")
    return links


def _link_row(
    profile: _Profile,
    concept_id: str,
    score: float,
    method: str,
    status: str,
    rank: int,
) -> dict[str, object]:
    return {
        "field_id": profile.field_id,
        "asset_id": profile.asset_id,
        "schema_name": profile.schema_name,
        "object_name": profile.object_name,
        "field_name": profile.field_name,
        "field_comment": profile.field_comment or None,
        "data_type": profile.data_type,
        "type_family": profile.type_family,
        "concept_id": concept_id,
        "rank": rank,
        "status": status,
        "method": method,
        "method_score": round(float(score), 6),
        "method_id": METHOD_ID,
        "method_version": METHOD_VERSION,
    }


def _diagnostic_rows(
    profiles: list[_Profile],
    neighbors: dict[int, list[tuple[int, float]]],
) -> list[dict[str, object]]:
    rows = []
    for left, values in sorted(neighbors.items()):
        for rank, (right, score) in enumerate(values, 1):
            rows.append(
                {
                    "field_id": profiles[left].field_id,
                    "neighbor_field_id": profiles[right].field_id,
                    "rank": rank,
                    "cosine_similarity": score,
                    "method_id": METHOD_ID,
                }
            )
    return rows


def _profile_row(profile: _Profile) -> dict[str, object]:
    return {
        "field_id": profile.field_id,
        "asset_id": profile.asset_id,
        "field_name": profile.field_name,
        "field_comment": profile.field_comment or None,
        "data_type": profile.data_type,
        "comment_available": bool(profile.field_comment),
        "name_tokens": list(profile.name_tokens),
        "normalized_comment": profile.normalized_comment,
        "type_family": profile.type_family,
        "broad_category": profile.broad_category,
        "base_concept": profile.base_concept or None,
        "status": "SUCCESS",
    }


def _name_tokens(value: str, abbreviations: dict[str, str]) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", value).upper()
    tokens = _ENGLISH_TOKEN.findall(normalized.replace("_", " "))
    return tuple(abbreviations.get(token, token) for token in tokens)


def _text_features(
    prefix: str,
    value: str,
    ngram_range: tuple[int, int],
) -> list[str]:
    normalized = unicodedata.normalize("NFKC", value).upper()
    compact = " ".join(normalized.split())
    features = [f"{prefix}:FULL:{compact}"]
    features.extend(f"{prefix}:TOKEN:{token}" for token in compact.split())
    joined = compact.replace(" ", "_")
    for width in range(ngram_range[0], ngram_range[1] + 1):
        features.extend(
            f"{prefix}:CHAR:{joined[index:index + width]}"
            for index in range(max(0, len(joined) - width + 1))
        )
    return features


def _feature_bucket(value: str, dimension: int) -> int:
    digest = hashlib.blake2b(value.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % dimension


def _normalize_comment(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = text.replace("（", "(").replace("）", ")")
    text = _PUNCTUATION.sub(" ", text)
    text = _SPACE.sub(" ", text).strip()
    text = _TRAILING_NOISE.sub("", text).strip()
    return text


def _type_family(value: str) -> str:
    upper = value.upper()
    if any(token in upper for token in ("NUMBER", "DECIMAL", "NUMERIC", "FLOAT", "DOUBLE", "INT")):
        return "NUMBER"
    if any(token in upper for token in ("DATE", "TIMESTAMP", "TIME")):
        return "DATE_TIME"
    if any(token in upper for token in ("CHAR", "VARCHAR", "CLOB", "TEXT")):
        return "TEXT"
    if any(token in upper for token in ("BLOB", "RAW", "BINARY")):
        return "BINARY"
    return upper or "UNKNOWN"


def _broad_category(
    name_signal: str,
    comment_signal: str,
    type_family: str,
    config: FieldConceptConfig,
) -> str:
    # A qualifier in the comment (for example, "settlement currency") must not
    # override what the physical field name says the value actually is.
    name_upper = name_signal.upper()
    for label, rule in config.broad_categories.items():
        if any(
            _term_matches(name_upper, str(term))
            for term in rule.get("terms", [])
        ):
            return label
    comment_upper = comment_signal.upper()
    for label, rule in config.broad_categories.items():
        if any(
            _term_matches(comment_upper, str(term))
            for term in rule.get("terms", [])
        ):
            return label
    for label, rule in config.broad_categories.items():
        families = {str(item).upper() for item in rule.get("type_families", [])}
        if type_family in families:
            return label
    return "其他"


def _base_concept(
    signal_text: str,
    broad_category: str,
    config: FieldConceptConfig,
) -> str:
    upper = signal_text.upper()
    for label, rule in config.base_concepts.items():
        required_broad = str(rule.get("broad_category", ""))
        if required_broad and required_broad != broad_category:
            continue
        if any(_term_matches(upper, str(term)) for term in rule.get("terms", [])):
            return label
    return ""


def _term_matches(signal_upper: str, term: str) -> bool:
    normalized = unicodedata.normalize("NFKC", term).upper().strip()
    if not normalized:
        return False
    if re.search(r"[\u4e00-\u9fff]", normalized):
        return normalized in signal_upper
    term_tokens = _ENGLISH_TOKEN.findall(normalized.replace("_", " "))
    signal_tokens = set(_ENGLISH_TOKEN.findall(signal_upper.replace("_", " ")))
    return bool(term_tokens) and all(token in signal_tokens for token in term_tokens)


def _display_label(comment: str, name_tokens: tuple[str, ...]) -> str:
    if comment:
        return comment[:80]
    meaningful = [token for token in name_tokens if token not in _GENERIC_NAME_TOKENS]
    if not meaningful:
        meaningful = list(name_tokens)
    return " ".join(meaningful[:8]).title()


def _qualified_label(
    profile: _Profile,
    base_label: str,
    base_terms: tuple[str, ...],
) -> str:
    if profile.normalized_comment:
        label = profile.normalized_comment[:80]
        if label in {base_label, f"{base_label}金额"}:
            return ""
        if base_label in label or any(
            _term_matches(label, term)
            for term in base_terms
            if re.search(r"[\u4e00-\u9fff]", term)
        ):
            return label
    qualifiers = []
    for token in profile.name_tokens:
        label = _QUALIFIER_TOKEN_LABELS.get(token)
        if label and label not in qualifiers:
            qualifiers.append(label)
    return "".join(qualifiers) + base_label if qualifiers else ""


def _cluster_label(profiles: list[_Profile]) -> str:
    labels = [profile.display_label for profile in profiles if profile.display_label]
    if not labels:
        return ""
    counts = Counter(labels)
    return sorted(counts, key=lambda item: (-counts[item], len(item), item))[0]


def _concept_id(label: str, level: int, parent_id: str | None) -> str:
    value = json.dumps(
        {"label": label, "level": level, "parent_id": parent_id},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"concept-{_sha256_text(value)[:16]}"


def _review_html(
    result: FieldConceptResult,
    *,
    source_panorama_root: str | Path | None = None,
) -> str:
    object_urls: dict[str, str] = {}
    if source_panorama_root:
        from .render import _slug

        object_root = Path(source_panorama_root) / "objects"
        for asset_id in {str(row.get("asset_id") or "") for row in result.links}:
            target = (object_root / f"{_slug(asset_id)}.html").resolve()
            if target.exists():
                object_urls[asset_id] = target.as_uri()
    asset_ids = sorted({str(row.get("asset_id") or "") for row in result.links})
    asset_indexes = {asset_id: index for index, asset_id in enumerate(asset_ids)}
    object_url_list = [object_urls.get(asset_id, "") for asset_id in asset_ids]
    concepts = [
        {
            "id": str(row["concept_id"]),
            "label": str(row["label"]),
            "level": int(row["level"]),
            "parent": str(row["parent_id"]) if row.get("parent_id") else None,
            "members": int(row.get("member_count", 0)),
        }
        for row in result.concepts
    ]
    links = [
        {
            "concept": str(row["concept_id"]),
            "table": str(row.get("object_name") or ""),
            "field": str(row.get("field_name") or ""),
            "comment": str(row.get("field_comment") or ""),
            "type": str(row.get("data_type") or ""),
            "family": str(row.get("type_family") or ""),
            "status": str(row.get("status") or ""),
            "rank": int(row.get("rank", 1)),
            "score": round(float(row.get("method_score", 0.0)), 6),
            "object": asset_indexes[str(row.get("asset_id") or "")],
        }
        for row in result.links
    ]
    stats = result.stats
    replacements = {
        "__CONCEPT_DATA__": _json_for_script(concepts),
        "__LINK_DATA__": _json_for_script(links),
        "__OBJECT_URL_DATA__": _json_for_script(object_url_list),
        "__OBJECT_COUNT__": str(stats["object_count"]),
        "__FIELD_COUNT__": str(stats["field_count"]),
        "__CONCEPT_COUNT__": str(stats["concept_count"]),
        "__UNASSIGNED_COUNT__": str(stats["unassigned_field_count"]),
        "__PAIR_COUNT__": str(stats["candidate_pair_count"]),
    }
    page = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>字段概念候选审阅</title>
<style>
:root{color-scheme:light;font-family:Arial,"Microsoft YaHei",sans-serif;color:#243247;background:#f6f8fb}*{box-sizing:border-box}body{margin:0}.shell{max-width:1440px;margin:auto;padding:20px}.warning{padding:12px;background:#fff3cd;border:1px solid #e0b84f;border-radius:8px}.stats,.roots{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}.stat,.root-button,.concept-button{border:1px solid #d7deea;background:#fff;border-radius:8px;padding:9px 12px}.root-button,.concept-button,.page-button{cursor:pointer}.root-button:hover,.concept-button:hover{border-color:#4777c7;background:#f2f6ff}.layout{display:grid;grid-template-columns:minmax(280px,0.8fr) minmax(520px,1.8fr);gap:16px}.panel{background:#fff;border:1px solid #d7deea;border-radius:10px;padding:16px;min-width:0}.search{width:100%;padding:11px;border:1px solid #98a2b3;border-radius:7px;font-size:15px}.muted{color:#667085;font-size:13px}.breadcrumb{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:12px}.breadcrumb button{border:0;background:none;color:#265eae;cursor:pointer;padding:2px}.concept-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:8px}.concept-button{text-align:left}.concept-button strong{display:block}.field-card{border-top:1px solid #e4e8ef;padding:10px 0}.field-name{font-family:Consolas,monospace;font-weight:700}.table-link{color:#265eae;font-weight:600;text-decoration:none}.table-link:hover{text-decoration:underline}.field-meta{display:flex;gap:8px;flex-wrap:wrap;margin-top:5px}.badge{font-size:12px;background:#eef3f8;border-radius:12px;padding:2px 7px}.pager{display:flex;gap:8px;align-items:center;margin-top:12px}.page-button{padding:6px 10px;border:1px solid #c7d0dd;background:#fff;border-radius:6px}.page-button:disabled{opacity:.45;cursor:default}.empty{padding:18px;color:#667085;text-align:center}.loading{padding:12px;color:#4777c7}@media(max-width:850px){.layout{grid-template-columns:1fr}.shell{padding:12px}}
</style></head><body><main class="shell">
<h1>字段概念候选审阅</h1>
<div class="warning"><strong>候选导航，不是正式本体。</strong> 未读取列值，未调用外部 LLM；页面按需加载，字段与概念数量增长时不会全量渲染。</div>
<div class="stats"><div class="stat">表 __OBJECT_COUNT__</div><div class="stat">字段 __FIELD_COUNT__</div><div class="stat">概念 __CONCEPT_COUNT__</div><div class="stat">未分配 __UNASSIGNED_COUNT__</div><div class="stat">候选对 __PAIR_COUNT__</div></div>
<section class="panel"><h2>导航分面</h2><div id="root-list" class="roots"></div></section>
<div class="layout">
  <section class="panel"><h2>概念浏览</h2><div id="breadcrumb" class="breadcrumb muted">请选择导航分面</div><div id="child-list" class="concept-list"></div><div id="child-pager" class="pager"></div></section>
  <section class="panel"><h2>字段反查概念路径</h2><input id="field-search" class="search" placeholder="输入字段名、中文注释或表名"><div id="search-status" class="muted"></div><div id="search-results"></div><div id="search-pager" class="pager"></div><hr><h2 id="field-title">概念字段（包含后代）</h2><div id="field-results" class="empty">请选择概念</div><div id="field-pager" class="pager"></div></section>
</div>
</main>
<script id="concept-data" type="application/json">__CONCEPT_DATA__</script>
<script id="link-data" type="application/json">__LINK_DATA__</script>
<script id="object-url-data" type="application/json">__OBJECT_URL_DATA__</script>
<script>
const FIELD_PAGE_SIZE=50,CONCEPT_PAGE_SIZE=60,SEARCH_PAGE_SIZE=50;
const concepts=JSON.parse(document.getElementById('concept-data').textContent);
document.getElementById('concept-data').remove();
const objectUrls=JSON.parse(document.getElementById('object-url-data').textContent);
document.getElementById('object-url-data').remove();
const byId=new Map(concepts.map(item=>[item.id,item]));
const children=new Map();
for(const item of concepts){const key=item.parent||'';if(!children.has(key))children.set(key,[]);children.get(key).push(item)}
for(const items of children.values())items.sort((a,b)=>a.label.localeCompare(b.label,'zh-CN'));
const ancestorIds={};for(const item of concepts){const ids=[];let current=item;while(current){ids.push(current.id);current=current.parent?byId.get(current.parent):null}ancestorIds[item.id]=ids}
const workerSource=`let links=[],byScope=new Map();
self.onmessage=e=>{const m=e.data;if(m.type==='init'){links=JSON.parse(m.raw);for(const row of links){row.search=(row.table+' '+row.field+' '+row.comment+' '+row.type).toLowerCase();for(const concept of (m.ancestors[row.concept]||[row.concept])){if(!byScope.has(concept))byScope.set(concept,[]);byScope.get(concept).push(row)}}self.postMessage({type:'ready'});return}if(m.type==='concept'){const all=byScope.get(m.concept)||[];const start=m.page*m.size;self.postMessage({type:'concept',request:m.request,total:all.length,rows:all.slice(start,start+m.size).map(row=>({...row,direct:row.concept===m.concept}))});return}if(m.type==='search'){const q=m.query.toLowerCase();const found=[];for(const row of links){if(row.search.includes(q))found.push(row)}const start=m.page*m.size;self.postMessage({type:'search',request:m.request,total:found.length,rows:found.slice(start,start+m.size)})}}`;
const workerUrl=URL.createObjectURL(new Blob([workerSource],{type:'text/javascript'}));const worker=new Worker(workerUrl);URL.revokeObjectURL(workerUrl);
let rawLinks=document.getElementById('link-data').textContent;document.getElementById('link-data').remove();worker.postMessage({type:'init',raw:rawLinks,ancestors:ancestorIds});rawLinks=null;
let selectedId=null,childPage=0,fieldPage=0,searchPage=0,requestSeq=0,latestField=0,latestSearch=0,searchTimer=null;
const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const pathFor=id=>{const path=[];let item=byId.get(id);while(item){path.unshift(item);item=item.parent?byId.get(item.parent):null}return path};
const pager=(target,page,total,size,kind)=>{const pages=Math.max(1,Math.ceil(total/size));target.innerHTML=total>size?`<button class="page-button" data-page="${kind}" data-delta="-1" ${page===0?'disabled':''}>上一页</button><span class="muted">${page+1} / ${pages} · ${total} 条</span><button class="page-button" data-page="${kind}" data-delta="1" ${page+1>=pages?'disabled':''}>下一页</button>`:''};
const rootList=document.getElementById('root-list');
rootList.innerHTML=(children.get('')||[]).map(item=>`<button class="root-button" data-concept="${esc(item.id)}"><strong>${esc(item.label)}</strong><br><span class="muted">${item.members} 个后代字段</span></button>`).join('');
function selectConcept(id){selectedId=id;childPage=0;fieldPage=0;renderConcept();requestFields()}
function renderConcept(){const item=byId.get(selectedId);if(!item)return;document.getElementById('breadcrumb').innerHTML=pathFor(selectedId).map((part,index,array)=>`<button data-concept="${esc(part.id)}">${esc(part.label)}</button>${index<array.length-1?'<span>›</span>':''}`).join('');const all=children.get(selectedId)||[];const start=childPage*CONCEPT_PAGE_SIZE;document.getElementById('child-list').innerHTML=all.length?all.slice(start,start+CONCEPT_PAGE_SIZE).map(child=>`<button class="concept-button" data-concept="${esc(child.id)}"><strong>${esc(child.label)}</strong><span class="muted">L${child.level} · ${child.members} 个后代字段</span></button>`).join(''):'<div class="empty">没有下级概念</div>';pager(document.getElementById('child-pager'),childPage,all.length,CONCEPT_PAGE_SIZE,'child');document.getElementById('field-title').textContent=`${item.label} · 全部后代字段`}
function requestFields(){if(!selectedId)return;const request=++requestSeq;latestField=request;document.getElementById('field-results').innerHTML='<div class="loading">正在读取字段…</div>';worker.postMessage({type:'concept',concept:selectedId,page:fieldPage,size:FIELD_PAGE_SIZE,request})}
function fieldCards(rows,withPath){return rows.length?rows.map(row=>{const url=objectUrls[row.object]||'';const table=url?`<a class="table-link" href="${esc(url)}" target="_blank" rel="noopener">${esc(row.table)}</a>`:`<span class="muted">${esc(row.table)}</span>`;return `<article class="field-card"><div><span class="field-name">${esc(row.field)}</span> · ${table}</div><div>${esc(row.comment||'—')}</div><div class="field-meta">${withPath?`<button class="page-button" data-concept="${esc(row.concept)}">${esc(pathFor(row.concept).map(item=>item.label).join(' › '))}</button>`:''}${row.direct===undefined?'':`<span class="badge">${row.direct?'直属':'后代'}</span>`}<span class="badge">类型 ${esc(row.type||row.family||'未知')}</span><span class="badge">候选 ${row.rank}</span><span class="badge">${Number(row.score).toFixed(3)}</span><span class="badge">${esc(row.status)}</span></div></article>`}).join(''):'<div class="empty">没有字段</div>'}
function requestSearch(){const query=document.getElementById('field-search').value.trim();if(!query){document.getElementById('search-status').textContent='';document.getElementById('search-results').innerHTML='';document.getElementById('search-pager').innerHTML='';return}const request=++requestSeq;latestSearch=request;document.getElementById('search-status').textContent='正在搜索…';worker.postMessage({type:'search',query,page:searchPage,size:SEARCH_PAGE_SIZE,request})}
worker.onmessage=e=>{const m=e.data;if(m.type==='ready')return;if(m.type==='concept'&&m.request===latestField){document.getElementById('field-results').innerHTML=fieldCards(m.rows,true);pager(document.getElementById('field-pager'),fieldPage,m.total,FIELD_PAGE_SIZE,'field')}if(m.type==='search'&&m.request===latestSearch){document.getElementById('search-status').textContent=`找到 ${m.total} 条，当前仅渲染本页`;document.getElementById('search-results').innerHTML=fieldCards(m.rows,true);pager(document.getElementById('search-pager'),searchPage,m.total,SEARCH_PAGE_SIZE,'search')}};
document.addEventListener('click',event=>{const concept=event.target.closest('[data-concept]');if(concept){selectConcept(concept.dataset.concept);return}const page=event.target.closest('[data-page]');if(!page||page.disabled)return;const delta=Number(page.dataset.delta);if(page.dataset.page==='child'){childPage+=delta;renderConcept()}else if(page.dataset.page==='field'){fieldPage+=delta;requestFields()}else{searchPage+=delta;requestSearch()}});
document.getElementById('field-search').addEventListener('input',()=>{searchPage=0;clearTimeout(searchTimer);searchTimer=setTimeout(requestSearch,180)});
</script></body></html>"""
    for placeholder, value in replacements.items():
        page = page.replace(placeholder, value)
    return page


def _json_for_script(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace(
        "<", "\\u003c"
    ).replace(">", "\\u003e").replace("&", "\\u0026")


def _output_entry(logical_name: str, path: Path, root: Path, row_count: int) -> dict[str, object]:
    return {
        "logical_name": logical_name,
        "relative_path": path.relative_to(root).as_posix(),
        "content_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "row_count": row_count,
        "status": "SUCCESS",
    }


def _jsonl(rows: list[dict[str, object]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def _pretty_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _mapping(value: dict[str, object], key: str) -> dict[str, object]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise ValueError(f"{key} must be a mapping")
    return item


def _rule_mapping(value: object, key: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a mapping")
    for list_key in ("terms", "type_families"):
        item = value.get(list_key, [])
        if not isinstance(item, list):
            raise ValueError(f"{key}.{list_key} must be a list")
    return dict(value)


def _string_float_mapping(value: object, key: str) -> dict[str, float]:
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a mapping")
    result = {str(name): float(number) for name, number in value.items()}
    if any(number < 0 or not math.isfinite(number) for number in result.values()):
        raise ValueError(f"{key} values must be finite and non-negative")
    return result


def _string_tuple(value: object, key: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{key} must be a non-empty list")
    return tuple(str(item) for item in value)


def _positive_int(value: dict[str, object], key: str, default: int) -> int:
    result = int(value.get(key, default))
    if result <= 0:
        raise ValueError(f"{key} must be positive")
    return result


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    result = int(value)
    if result < 0:
        raise ValueError("expected counts must be non-negative")
    return result
