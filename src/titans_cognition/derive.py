"""Deterministic V1A structural observations derived from canonical facts."""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import hashlib
import re

from .extract import PhysicalFacts


@dataclass
class DerivedObservations:
    """Structural projections that do not claim business identity or grain."""

    schema_summary: list[dict[str, object]] = field(default_factory=list)
    object_inventory_profiles: list[dict[str, object]] = field(default_factory=list)
    dependency_summary: list[dict[str, object]] = field(default_factory=list)
    extraction_failures: list[dict[str, object]] = field(default_factory=list)


_TOKEN_PATTERN = re.compile(r"[A-Z0-9]+")


def derive_observations(facts: PhysicalFacts) -> DerivedObservations:
    """Build deterministic structural summaries from one canonical fact run."""

    objects_by_asset = {
        str(row["asset_id"]): row for row in facts.objects if row.get("asset_id")
    }
    columns_by_asset: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in facts.columns:
        asset = row.get("asset_id")
        if asset:
            columns_by_asset[str(asset)].append(row)

    constraints_by_asset = _group_by_asset(facts.constraints)
    indexes_by_asset = _group_by_asset(facts.indexes)
    definitions_by_asset = _group_by_asset(facts.object_definitions)
    dependencies_by_asset = _group_by_asset(facts.dependencies, "source_asset_id")
    failures_by_asset = _group_by_asset(facts.failures, "target_id")

    profiles = [
        _object_profile(
            row,
            columns_by_asset.get(str(row["asset_id"]), []),
            constraints_by_asset.get(str(row["asset_id"]), []),
            indexes_by_asset.get(str(row["asset_id"]), []),
            definitions_by_asset.get(str(row["asset_id"]), []),
            dependencies_by_asset.get(str(row["asset_id"]), []),
            failures_by_asset.get(str(row["asset_id"]), []),
        )
        for row in sorted(
            facts.objects,
            key=lambda value: str(value.get("asset_id", "")),
        )
    ]

    return DerivedObservations(
        schema_summary=_schema_summaries(profiles),
        object_inventory_profiles=profiles,
        dependency_summary=_dependency_summaries(
            facts.dependencies,
            objects_by_asset,
        ),
        extraction_failures=list(facts.failures),
    )


def _group_by_asset(
    rows: list[dict[str, object]],
    key: str = "asset_id",
) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        asset = row.get(key)
        if asset:
            grouped[str(asset)].append(row)
    return grouped


def _object_profile(
    object_row: dict[str, object],
    columns: list[dict[str, object]],
    constraints: list[dict[str, object]],
    indexes: list[dict[str, object]],
    definitions: list[dict[str, object]],
    dependencies: list[dict[str, object]],
    failures: list[dict[str, object]],
) -> dict[str, object]:
    asset = str(object_row["asset_id"])
    column_signature = "|".join(
        f"{row.get('column_name', '')}:{row.get('data_type', '')}:"
        f"{row.get('nullable_declared', '')}"
        for row in sorted(
            columns,
            key=lambda value: int(value.get("ordinal_position", 0)),
        )
    )
    definition_success_count = sum(
        str(row.get("extraction_status", "")).upper() == "SUCCESS"
        for row in definitions
    )
    boundary_dependency_count = sum(
        bool(row.get("target_is_boundary")) for row in dependencies
    )
    object_name = str(object_row.get("object_name", ""))
    return {
        "run_id": object_row.get("run_id"),
        "asset_id": asset,
        "source_label": object_row.get("source_label"),
        "schema_name": object_row.get("schema_name"),
        "object_name": object_name,
        "object_type": object_row.get("object_type"),
        "column_count": len(columns),
        "comment_present": bool(object_row.get("object_comment")),
        "commented_column_count": sum(
            bool(row.get("column_comment")) for row in columns
        ),
        "constraint_count": len(constraints),
        "index_count": len(indexes),
        "dependency_out_count": len(dependencies),
        "dependency_boundary_count": boundary_dependency_count,
        "definition_count": len(definitions),
        "definition_success_count": definition_success_count,
        "definition_failure_count": len(definitions) - definition_success_count,
        "extraction_failure_count": len(failures),
        "extraction_status": object_row.get("extraction_status"),
        "name_tokens": _TOKEN_PATTERN.findall(object_name.upper()),
        "structure_fingerprint": hashlib.sha256(
            column_signature.encode("utf-8")
        ).hexdigest()[:16],
    }


def _schema_summaries(
    profiles: list[dict[str, object]],
) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for profile in profiles:
        grouped[str(profile["schema_name"])].append(profile)

    summaries: list[dict[str, object]] = []
    for schema_name, rows in sorted(grouped.items()):
        type_counts = Counter(str(row["object_type"]) for row in rows)
        summaries.append(
            {
                "schema_name": schema_name,
                "object_count": len(rows),
                "table_count": type_counts.get("TABLE", 0),
                "view_count": type_counts.get("VIEW", 0),
                "materialized_view_count": type_counts.get(
                    "MATERIALIZED_VIEW", 0
                ),
                "synonym_count": type_counts.get("SYNONYM", 0),
                "column_count": sum(int(row["column_count"]) for row in rows),
                "commented_object_count": sum(
                    bool(row["comment_present"]) for row in rows
                ),
                "constraint_count": sum(
                    int(row["constraint_count"]) for row in rows
                ),
                "index_count": sum(int(row["index_count"]) for row in rows),
                "definition_count": sum(
                    int(row["definition_count"]) for row in rows
                ),
                "definition_success_count": sum(
                    int(row["definition_success_count"]) for row in rows
                ),
                "definition_failure_count": sum(
                    int(row["definition_failure_count"]) for row in rows
                ),
                "dependency_out_count": sum(
                    int(row["dependency_out_count"]) for row in rows
                ),
                "dependency_boundary_count": sum(
                    int(row["dependency_boundary_count"]) for row in rows
                ),
                "extraction_failure_count": sum(
                    int(row["extraction_failure_count"]) for row in rows
                ),
            }
        )
    return summaries


def _dependency_summaries(
    dependencies: list[dict[str, object]],
    objects_by_asset: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for dependency in dependencies:
        source = str(dependency.get("source_asset_id", ""))
        target = str(dependency.get("target_asset_id", ""))
        source_schema = _asset_schema(source)
        target_schema = _asset_schema(target)
        if source_schema and target_schema:
            grouped[(source_schema, target_schema)].append(dependency)

    summaries: list[dict[str, object]] = []
    for (source_schema, target_schema), rows in sorted(grouped.items()):
        source_assets = Counter(str(row["source_asset_id"]) for row in rows)
        target_assets = {str(row["target_asset_id"]) for row in rows}
        summaries.append(
            {
                "source_schema_name": source_schema,
                "target_schema_name": target_schema,
                "dependency_count": len(rows),
                "source_object_count": len(source_assets),
                "target_object_count": len(target_assets),
                "boundary_dependency_count": sum(
                    bool(row.get("target_is_boundary")) for row in rows
                ),
                "top_source_asset_ids": [
                    asset
                    for asset, _count in sorted(
                        source_assets.items(),
                        key=lambda item: (-item[1], item[0]),
                    )[:10]
                    if asset in objects_by_asset
                ],
            }
        )
    return summaries


def _asset_schema(asset: str) -> str | None:
    parts = asset.split(":", 3)
    return parts[1] if len(parts) == 4 and parts[1] else None
