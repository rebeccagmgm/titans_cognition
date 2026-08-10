"""Independent baseline reconciliation and Gate A decision support."""

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from .extract import PhysicalFacts
from .scope import ScopeConfig


def panorama_delivery_ready(render_dir: str | Path) -> bool:
    """Return whether the minimum V1A static delivery artifacts exist."""

    root = Path(render_dir)
    manifest = root / "manifest.json"
    index = root / "panorama" / "index.html"
    schemas = root / "panorama" / "schemas"
    objects = root / "panorama" / "objects"
    return (
        manifest.is_file()
        and index.is_file()
        and schemas.is_dir()
        and any(schemas.glob("*.html"))
        and objects.is_dir()
        and any(objects.glob("*.html"))
    )


def reconcile_facts(
    scope: ScopeConfig,
    facts: PhysicalFacts,
    baseline: Mapping[str, Any],
    *,
    delivery_ready: bool = False,
) -> dict[str, object]:
    """Compare canonical facts with an independently produced metadata baseline.

    The function deliberately separates physical-data reconciliation from the Gate A
    delivery decision. Matching counts do not imply that a usable Panorama map or
    Object Card exists.
    """

    in_scope_objects = [
        row
        for row in facts.objects
        if bool(row.get("in_panorama_scope"))
        and not bool(row.get("is_boundary"))
        and scope.accepts_object(
            str(row.get("schema_name", "")),
            str(row.get("object_type", "")),
        )
    ]
    asset_ids = {str(row["asset_id"]) for row in in_scope_objects}
    actual_object_counts = Counter(
        (
            str(row.get("schema_name", "")).upper(),
            _canonical_type(str(row.get("object_type", ""))),
        )
        for row in in_scope_objects
    )
    actual_column_counts = _column_counts_by_schema(facts, asset_ids)
    expected_object_counts, expected_object_keys = _expected_object_counts(
        baseline.get("objects", [])
    )
    expected_column_counts = _expected_column_counts(baseline.get("columns", []))

    checks: list[dict[str, object]] = []
    reconciliation_blockers: list[str] = []
    gate_blockers: list[str] = []
    warnings: list[str] = []

    object_count_match = actual_object_counts == expected_object_counts
    checks.append(
        {
            "check_id": "OBJECT_COUNT_RECONCILIATION",
            "status": "PASS" if object_count_match else "FAILED",
            "expected": _counter_rows(expected_object_counts),
            "actual": _counter_rows(actual_object_counts),
        }
    )
    if not object_count_match:
        reconciliation_blockers.append("OBJECT_COUNT_MISMATCH")

    column_count_match = actual_column_counts == expected_column_counts
    checks.append(
        {
            "check_id": "COLUMN_COUNT_RECONCILIATION",
            "status": "PASS" if column_count_match else "FAILED",
            "expected": dict(sorted(expected_column_counts.items())),
            "actual": dict(sorted(actual_column_counts.items())),
        }
    )
    if not column_count_match:
        reconciliation_blockers.append("COLUMN_COUNT_MISMATCH")

    if expected_object_keys:
        actual_object_keys = {
            (
                str(row.get("schema_name", "")).upper(),
                _canonical_type(str(row.get("object_type", ""))),
                str(row.get("object_name", "")).upper(),
            )
            for row in in_scope_objects
        }
        missing = sorted(expected_object_keys - actual_object_keys)
        unexpected = sorted(actual_object_keys - expected_object_keys)
        coverage_status = "PASS" if not missing and not unexpected else "FAILED"
        checks.append(
            {
                "check_id": "OBJECT_KEY_COVERAGE",
                "status": coverage_status,
                "missing_count": len(missing),
                "unexpected_count": len(unexpected),
            }
        )
        if missing or unexpected:
            reconciliation_blockers.append("OBJECT_KEY_COVERAGE_MISMATCH")
    else:
        checks.append(
            {
                "check_id": "OBJECT_KEY_COVERAGE",
                "status": "NOT_EVALUATED",
                "reason": "independent baseline has counts but no object names",
            }
        )
        gate_blockers.append("INDEPENDENT_OBJECT_NAME_BASELINE_MISSING")

    boundary_invalid = [
        row
        for row in facts.objects
        if bool(row.get("is_boundary"))
        and (
            bool(row.get("in_panorama_scope"))
            or not row.get("boundary_for_case_ids")
        )
    ]
    checks.append(
        {
            "check_id": "BOUNDARY_SCOPE_INTEGRITY",
            "status": "PASS" if not boundary_invalid else "FAILED",
            "invalid_count": len(boundary_invalid),
        }
    )
    if boundary_invalid:
        reconciliation_blockers.append("BOUNDARY_SCOPE_INVALID")

    definition_failure_count = sum(
        str(row.get("extraction_status", "")).upper() != "SUCCESS"
        for row in facts.object_definitions
    )
    failure_targets = {
        str(row.get("target_id")) for row in facts.failures if row.get("target_id")
    }
    missing_failure_rows = [
        row
        for row in facts.object_definitions
        if str(row.get("extraction_status", "")).upper() != "SUCCESS"
        and str(row.get("asset_id")) not in failure_targets
    ]
    checks.append(
        {
            "check_id": "FAILURE_RECORD_COVERAGE",
            "status": "PASS" if not missing_failure_rows else "FAILED",
            "missing_count": len(missing_failure_rows),
        }
    )
    if missing_failure_rows:
        reconciliation_blockers.append("FAILURE_RECORD_COVERAGE_MISMATCH")
    if definition_failure_count:
        warnings.append("DEFINITION_EXTRACTION_DEGRADED")

    data_failed = bool(reconciliation_blockers)
    data_reconciliation_status = "FAILED" if data_failed else "PASS"
    if not delivery_ready:
        gate_blockers.append("PANORAMA_DELIVERY_NOT_IMPLEMENTED")
    all_blockers = reconciliation_blockers + gate_blockers
    gate_a_status = "BLOCKED" if all_blockers else (
        "DEGRADED" if warnings else "PASS"
    )
    return {
        "scope_id": scope.scope_id,
        "data_reconciliation_status": data_reconciliation_status,
        "gate_a_status": gate_a_status,
        "definition_failure_count": definition_failure_count,
        "checks": checks,
        "blockers": sorted(set(all_blockers)),
        "warnings": sorted(set(warnings)),
    }


def _expected_object_counts(
    rows: Any,
) -> tuple[Counter[tuple[str, str]], set[tuple[str, str, str]]]:
    counts: Counter[tuple[str, str]] = Counter()
    keys: set[tuple[str, str, str]] = set()
    if not isinstance(rows, list):
        raise ValueError("baseline.objects must be a list")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("baseline object rows must be mappings")
        schema = str(row.get("schema_name", "")).upper()
        object_type = _canonical_type(str(row.get("object_type", "")))
        if not schema or not object_type:
            raise ValueError("baseline object rows need schema_name and object_type")
        if row.get("object_name"):
            keys.add((schema, object_type, str(row["object_name"]).upper()))
            counts[(schema, object_type)] += 1
        else:
            counts[(schema, object_type)] += int(row.get("object_count", 0))
    return counts, keys


def _expected_column_counts(rows: Any) -> dict[str, int]:
    if not isinstance(rows, list):
        raise ValueError("baseline.columns must be a list")
    counts: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict) or not row.get("schema_name"):
            raise ValueError("baseline column rows need schema_name")
        counts[str(row["schema_name"]).upper()] = int(row.get("column_count", 0))
    return dict(sorted(counts.items()))


def _column_counts_by_schema(
    facts: PhysicalFacts,
    asset_ids: set[str],
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    schema_by_asset = {
        str(row["asset_id"]): str(row.get("schema_name", "")).upper()
        for row in facts.objects
        if row.get("asset_id") in asset_ids
    }
    for row in facts.columns:
        asset = str(row.get("asset_id", ""))
        if asset in schema_by_asset:
            counts[schema_by_asset[asset]] += 1
    return dict(sorted(counts.items()))


def _counter_rows(counter: Counter[tuple[str, str]]) -> list[dict[str, object]]:
    return [
        {
            "schema_name": schema,
            "object_type": object_type,
            "object_count": count,
        }
        for (schema, object_type), count in sorted(counter.items())
    ]


def _canonical_type(value: str) -> str:
    return value.strip().upper().replace(" ", "_")
