"""Bounded V1B physical features for the TRADEFLOW deep sample.

This module deliberately stops before semantic inference.  Names and structure
are emitted as method-local signals, never as business facts.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re

import yaml

from .extract import PhysicalFacts


CASE_ID = "tradeflow"
SAMPLE_METHOD_ID = "sample.tradeflow.physical_stratified"
SAMPLE_METHOD_VERSION = "v1"
FEATURE_METHOD_ID = "feature.tradeflow.physical"
FEATURE_METHOD_VERSION = "v1"
SIMILARITY_METHOD_ID = "similarity.tradeflow.structure_jaccard"
SIMILARITY_METHOD_VERSION = "v1"

_TOKEN_PATTERN = re.compile(r"[A-Z0-9]+")
_STRATA = (
    "PK_COMPOSITE",
    "PK_SINGLE",
    "UK_ONLY",
    "NO_KEY_WITH_INDEX",
    "NO_DECLARED_KEY",
)


@dataclass
class TradeflowDerived:
    """Typed JSON-ready V1B physical observations."""

    sample_objects: list[dict[str, object]] = field(default_factory=list)
    column_features: list[dict[str, object]] = field(default_factory=list)
    object_features: list[dict[str, object]] = field(default_factory=list)
    structure_similarity: list[dict[str, object]] = field(default_factory=list)


def load_sample(path: str | Path) -> dict[str, object]:
    """Load and validate a bounded sample configuration."""

    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("sample YAML root must be a mapping")
    selected = payload.get("selected_objects")
    if not isinstance(selected, list) or not selected:
        raise ValueError("sample must contain a non-empty selected_objects list")
    for row in selected:
        if not isinstance(row, dict) or not isinstance(row.get("asset_id"), str):
            raise ValueError("each sample object must define an asset_id")
    return payload


def write_sample(path: str, sample: dict[str, object]) -> None:
    """Write a human-reviewable sample configuration."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(sample, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def select_tradeflow_sample(
    facts: PhysicalFacts,
    *,
    case_id: str = CASE_ID,
    max_objects: int = 8,
) -> dict[str, object]:
    """Select a small deterministic sample from physical facts only.

    One widest object is selected from each key/index stratum.  A pair with the
    same physical column fingerprint is added when available so that structural
    similarity can be tested against a negative business-meaning assumption.
    """

    if max_objects < len(_STRATA):
        raise ValueError("max_objects must allow one object per stratum")
    eligible = [
        row
        for row in facts.objects
        if row.get("schema_name") == "TITANS_TRADEFLOW"
        and not row.get("is_boundary")
        and row.get("extraction_status") == "SUCCESS"
    ]
    columns_by_asset = _group(facts.columns, "asset_id")
    constraints_by_asset = _group(facts.constraints, "asset_id")
    indexes_by_asset = _group(facts.indexes, "asset_id")
    records = []
    for row in eligible:
        asset = str(row["asset_id"])
        profile = _physical_profile(
            row,
            columns_by_asset.get(asset, []),
            constraints_by_asset.get(asset, []),
            indexes_by_asset.get(asset, []),
        )
        records.append(profile)

    chosen: dict[str, dict[str, object]] = {}
    for stratum in _STRATA:
        candidates = [row for row in records if row["stratum"] == stratum]
        if not candidates:
            raise ValueError(f"TRADEFLOW has no eligible object in stratum {stratum}")
        candidates.sort(
            key=lambda row: (-int(row["column_count"]), str(row["asset_id"]))
        )
        chosen[str(candidates[0]["asset_id"])] = {
            **candidates[0],
            "selection_reason": f"widest eligible object in {stratum}; physical facts only",
        }

    fingerprint_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in records:
        fingerprint_groups[str(row["structure_fingerprint"])].append(row)
    pairs = [
        sorted(group, key=lambda row: str(row["asset_id"]))
        for group in fingerprint_groups.values()
        if len(group) >= 2
    ]
    pairs.sort(
        key=lambda group: (
            -sum(int(row["column_count"]) for row in group[:2]),
            tuple(str(row["asset_id"]) for row in group[:2]),
        )
    )
    if pairs:
        pair = pairs[0][:2]
        for row in pair:
            asset = str(row["asset_id"])
            if asset not in chosen and len(chosen) < max_objects:
                chosen[asset] = {
                    **row,
                    "selection_reason": (
                        "same physical structure fingerprint as a sample peer; "
                        "contrast only, not a business-family claim"
                    ),
                }

    selected = [chosen[asset] for asset in sorted(chosen)]
    return {
        "version": "v1",
        "sample_id": f"{case_id}-v1b-physical-stratified",
        "case_id": case_id,
        "source_label": _source_label(selected),
        "schema": "TITANS_TRADEFLOW",
        "selection_method": {
            "method_id": SAMPLE_METHOD_ID,
            "method_version": SAMPLE_METHOD_VERSION,
            "input": "canonical panorama physical facts",
            "boundary": "one object per key/index stratum plus one structural contrast pair",
            "semantic_labels_enabled": False,
        },
        "selected_objects": [
            {
                "asset_id": row["asset_id"],
                "object_name": row["object_name"],
                "stratum": row["stratum"],
                "column_count": row["column_count"],
                "constraint_count": row["constraint_count"],
                "index_count": row["index_count"],
                "structure_fingerprint": row["structure_fingerprint"],
                "selection_reason": row["selection_reason"],
            }
            for row in selected
        ],
    }


def derive_tradeflow_features(
    facts: PhysicalFacts,
    sample: dict[str, object],
) -> TradeflowDerived:
    """Derive bounded, deterministic physical features for sample assets."""

    selected_rows = sample["selected_objects"]
    assert isinstance(selected_rows, list)
    selected_ids = {str(row["asset_id"]) for row in selected_rows}
    objects = {
        str(row["asset_id"]): row
        for row in facts.objects
        if str(row.get("asset_id")) in selected_ids
    }
    if set(objects) != selected_ids:
        missing = sorted(selected_ids - set(objects))
        raise ValueError(f"sample assets missing from physical facts: {missing}")

    columns_by_asset = _group(facts.columns, "asset_id")
    constraints_by_asset = _group(facts.constraints, "asset_id")
    indexes_by_asset = _group(facts.indexes, "asset_id")
    dependencies = [
        row
        for row in facts.dependencies
        if row.get("source_asset_id") in selected_ids
        or row.get("target_asset_id") in selected_ids
    ]

    column_features: list[dict[str, object]] = []
    object_features: list[dict[str, object]] = []
    for asset in sorted(selected_ids):
        object_row = objects[asset]
        columns = sorted(
            columns_by_asset.get(asset, []),
            key=lambda row: int(row.get("ordinal_position", 0)),
        )
        constraints = constraints_by_asset.get(asset, [])
        indexes = indexes_by_asset.get(asset, [])
        key_sets = _key_sets(constraints)
        indexed = {
            column_id
            for index in indexes
            for column_id in index.get("column_ids", [])
        }
        for column in columns:
            column_id = str(column["column_id"])
            column_features.append(
                {
                    "run_id": object_row.get("run_id"),
                    "case_id": sample.get("case_id", CASE_ID),
                    "asset_id": asset,
                    "column_id": column_id,
                    "column_name": column.get("column_name"),
                    "name_tokens": _tokens(str(column.get("column_name", ""))),
                    "data_type_family": _data_type_family(str(column.get("data_type", ""))),
                    "nullable_declared": column.get("nullable_declared"),
                    "default_present": bool(column.get("default_expression")),
                    "column_comment_present": bool(column.get("column_comment")),
                    "in_primary_key": column_id in key_sets["PRIMARY_KEY"],
                    "in_unique_key": column_id in key_sets["UNIQUE_KEY"],
                    "in_foreign_key": column_id in key_sets["FOREIGN_KEY"],
                    "in_index": column_id in indexed,
                    "method_id": FEATURE_METHOD_ID,
                    "method_version": FEATURE_METHOD_VERSION,
                    "status": "SUCCESS",
                }
            )
        profile = _physical_profile(object_row, columns, constraints, indexes)
        object_features.append(
            {
                "run_id": object_row.get("run_id"),
                "case_id": sample.get("case_id", CASE_ID),
                "asset_id": asset,
                "object_name": object_row.get("object_name"),
                "object_type": object_row.get("object_type"),
                "column_count": len(columns),
                "constraint_count": len(constraints),
                "primary_key_count": len(key_sets["PRIMARY_KEY_CONSTRAINTS"]),
                "unique_key_count": len(key_sets["UNIQUE_KEY_CONSTRAINTS"]),
                "foreign_key_count": len(key_sets["FOREIGN_KEY_CONSTRAINTS"]),
                "index_count": len(indexes),
                "dependency_out_count": sum(
                    row.get("source_asset_id") == asset for row in dependencies
                ),
                "comment_present": bool(object_row.get("object_comment")),
                "definition_present": any(
                    row.get("asset_id") == asset
                    and row.get("extraction_status") == "SUCCESS"
                    for row in facts.object_definitions
                ),
                "name_tokens": _tokens(str(object_row.get("object_name", ""))),
                "sample_stratum": next(
                    row.get("stratum")
                    for row in selected_rows
                    if row.get("asset_id") == asset
                ),
                "structure_fingerprint": profile["structure_fingerprint"],
                "method_id": FEATURE_METHOD_ID,
                "method_version": FEATURE_METHOD_VERSION,
                "status": "SUCCESS",
            }
        )

    return TradeflowDerived(
        sample_objects=list(selected_rows),
        column_features=column_features,
        object_features=object_features,
        structure_similarity=_similarity_rows(
            selected_ids,
            objects,
            columns_by_asset,
            constraints_by_asset,
            dependencies,
        ),
    )


def _group(rows: list[dict[str, object]], key: str) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        value = row.get(key)
        if value is not None:
            grouped[str(value)].append(row)
    return grouped


def _key_sets(constraints: list[dict[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {
        "PRIMARY_KEY": set(),
        "UNIQUE_KEY": set(),
        "FOREIGN_KEY": set(),
        "PRIMARY_KEY_CONSTRAINTS": [],
        "UNIQUE_KEY_CONSTRAINTS": [],
        "FOREIGN_KEY_CONSTRAINTS": [],
    }
    for row in constraints:
        kind = str(row.get("constraint_type", "")).upper()
        if kind not in ("PRIMARY_KEY", "UNIQUE_KEY", "FOREIGN_KEY"):
            continue
        if str(row.get("extraction_status", "SUCCESS")).upper() != "SUCCESS":
            continue
        result[kind].update(row.get("column_ids", []))
        result[f"{kind}_CONSTRAINTS"].append(row)
    return result


def _physical_profile(
    object_row: dict[str, object],
    columns: list[dict[str, object]],
    constraints: list[dict[str, object]],
    indexes: list[dict[str, object]],
) -> dict[str, object]:
    key_sets = _key_sets(constraints)
    pk_constraints = key_sets["PRIMARY_KEY_CONSTRAINTS"]
    uk_constraints = key_sets["UNIQUE_KEY_CONSTRAINTS"]
    if pk_constraints:
        max_pk_width = max(len(row.get("column_ids", [])) for row in pk_constraints)
        stratum = "PK_COMPOSITE" if max_pk_width > 1 else "PK_SINGLE"
    elif uk_constraints:
        stratum = "UK_ONLY"
    elif indexes:
        stratum = "NO_KEY_WITH_INDEX"
    else:
        stratum = "NO_DECLARED_KEY"
    signature = "|".join(
        f"{row.get('column_name', '')}:{row.get('data_type', '')}:"
        f"{row.get('nullable_declared', '')}"
        for row in sorted(columns, key=lambda value: int(value.get("ordinal_position", 0)))
    )
    return {
        "asset_id": object_row["asset_id"],
        "object_name": object_row.get("object_name"),
        "stratum": stratum,
        "column_count": len(columns),
        "constraint_count": len(constraints),
        "index_count": len(indexes),
        "structure_fingerprint": hashlib.sha256(signature.encode("utf-8")).hexdigest()[:16],
    }


def _similarity_rows(
    selected_ids: set[str],
    objects: dict[str, dict[str, object]],
    columns_by_asset: dict[str, list[dict[str, object]]],
    constraints_by_asset: dict[str, list[dict[str, object]]],
    dependencies: list[dict[str, object]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    assets = sorted(selected_ids)
    neighborhoods: dict[str, set[str]] = defaultdict(set)
    for dependency in dependencies:
        source = str(dependency["source_asset_id"])
        target = str(dependency["target_asset_id"])
        neighborhoods[source].add(target)
        neighborhoods[target].add(source)
    for index, left in enumerate(assets):
        for right in assets[index + 1 :]:
            left_names = {_normalize_feature_name(row.get("column_name")) for row in columns_by_asset[left]}
            right_names = {_normalize_feature_name(row.get("column_name")) for row in columns_by_asset[right]}
            left_keys = set().union(*(_key_sets(constraints_by_asset[left])[kind] for kind in ("PRIMARY_KEY", "UNIQUE_KEY", "FOREIGN_KEY")))
            right_keys = set().union(*(_key_sets(constraints_by_asset[right])[kind] for kind in ("PRIMARY_KEY", "UNIQUE_KEY", "FOREIGN_KEY")))
            name_score = _jaccard(
                set(_tokens(str(objects[left].get("object_name", "")))),
                set(_tokens(str(objects[right].get("object_name", "")))),
            )
            column_score = _jaccard(left_names, right_names)
            key_score = _jaccard(
                {_normalize_feature_name(value.rsplit(":", 1)[-1]) for value in left_keys},
                {_normalize_feature_name(value.rsplit(":", 1)[-1]) for value in right_keys},
            )
            neighborhood_score = _jaccard(neighborhoods[left], neighborhoods[right])
            combined = round(
                0.25 * name_score + 0.5 * column_score + 0.2 * key_score + 0.05 * neighborhood_score,
                6,
            )
            rows.append(
                {
                    "left_asset_id": left,
                    "right_asset_id": right,
                    "method_id": SIMILARITY_METHOD_ID,
                    "method_version": SIMILARITY_METHOD_VERSION,
                    "name_score": round(name_score, 6),
                    "column_score": round(column_score, 6),
                    "key_score": round(key_score, 6),
                    "relation_neighborhood_score": round(neighborhood_score, 6),
                    "combined_score": combined,
                    "feature_breakdown": json.dumps(
                        {
                            "name_tokens": "jaccard",
                            "column_names": "jaccard",
                            "key_column_names": "jaccard",
                            "relation_neighbors": "jaccard",
                            "interpretation": "method-local ranking signal; not business similarity probability",
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                }
            )
    return rows


def _tokens(value: str) -> list[str]:
    return _TOKEN_PATTERN.findall(value.upper())


def _normalize_feature_name(value: object) -> str:
    return str(value or "").upper().strip()


def _source_label(rows: list[dict[str, object]]) -> str:
    return str(rows[0]["asset_id"]).split(":", 1)[0] if rows else "testdb"


def _jaccard(left: set[object], right: set[object]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _data_type_family(data_type: str) -> str:
    value = data_type.upper()
    if any(token in value for token in ("CHAR", "CLOB", "VARCHAR")):
        return "CHARACTER"
    if any(token in value for token in ("NUMBER", "DECIMAL", "FLOAT", "BINARY_FLOAT")):
        return "NUMERIC"
    if any(token in value for token in ("DATE", "TIMESTAMP", "INTERVAL")):
        return "TEMPORAL"
    if any(token in value for token in ("RAW", "BLOB", "LONG RAW")):
        return "BINARY_LOB"
    return "OTHER"
