"""Static V1A Panorama and physical Object Card projection."""

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
from html import escape
import os
from pathlib import Path
import re
from typing import Any

from .derive import DerivedObservations
from .extract import PhysicalFacts
from .scope import ScopeConfig


def render_panorama(
    scope: ScopeConfig,
    facts: PhysicalFacts,
    derived: DerivedObservations,
    output_dir: str | Path,
    *,
    scope_config_sha256: str | None = None,
    code_version: str = "working-tree",
) -> dict[str, Any]:
    """Render a local, read-only Panorama projection from canonical facts."""

    root = Path(output_dir)
    panorama_root = root / "panorama"
    schema_root = panorama_root / "schemas"
    object_root = panorama_root / "objects"
    schema_root.mkdir(parents=True, exist_ok=True)
    object_root.mkdir(parents=True, exist_ok=True)

    profiles = {
        str(row["asset_id"]): row for row in derived.object_inventory_profiles
    }
    objects_by_schema: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in facts.objects:
        objects_by_schema[str(row.get("schema_name", "")).upper()].append(row)

    object_paths: dict[str, Path] = {}
    for row in facts.objects:
        asset = str(row["asset_id"])
        object_path = object_root / f"{_slug(asset)}.html"
        object_path.write_text(
            _object_card_html(
                row,
                facts,
                profiles.get(asset, {}),
                object_path,
            ),
            encoding="utf-8",
        )
        object_paths[asset] = object_path

    schema_paths: dict[str, Path] = {}
    schema_summaries = {
        str(row["schema_name"]): row for row in derived.schema_summary
    }
    for schema_name in sorted(objects_by_schema):
        schema_path = schema_root / f"{_slug(schema_name)}.html"
        schema_path.write_text(
            _schema_html(
                schema_name,
                objects_by_schema[schema_name],
                schema_summaries.get(schema_name, {}),
                profiles,
                object_paths,
                schema_path,
            ),
            encoding="utf-8",
        )
        schema_paths[schema_name] = schema_path

    index_path = panorama_root / "index.html"
    index_path.write_text(
        _index_html(scope, facts, derived, schema_paths, index_path),
        encoding="utf-8",
    )

    manifest = _build_manifest(
        scope,
        facts,
        root,
        [index_path, *schema_paths.values(), *object_paths.values()],
        scope_config_sha256=scope_config_sha256,
        code_version=code_version,
    )
    manifest_path = root / "manifest.json"
    manifest_path.write_text(
        _json_text(manifest),
        encoding="utf-8",
    )
    return {
        "index": index_path,
        "schema_pages": list(schema_paths.values()),
        "object_cards": list(object_paths.values()),
        "manifest": manifest_path,
    }


def _index_html(
    scope: ScopeConfig,
    facts: PhysicalFacts,
    derived: DerivedObservations,
    schema_paths: dict[str, Path],
    current_path: Path,
) -> str:
    run_id = _run_id(facts)
    in_scope = [row for row in facts.objects if row.get("in_panorama_scope")]
    boundary_count = sum(bool(row.get("is_boundary")) for row in facts.objects)
    definition_failures = sum(
        str(row.get("extraction_status", "")).upper() != "SUCCESS"
        for row in facts.object_definitions
    )
    rows = []
    summaries = {str(row["schema_name"]): row for row in derived.schema_summary}
    for schema_name, path in sorted(schema_paths.items()):
        summary = summaries.get(schema_name, {})
        rows.append(
            "<tr>"
            f"<td><a href='{escape(_relative(current_path, path))}'>{escape(schema_name)}</a></td>"
            f"<td>{summary.get('object_count', 0)}</td>"
            f"<td>{summary.get('column_count', 0)}</td>"
            f"<td>{summary.get('definition_failure_count', 0)}</td>"
            "</tr>"
        )
    return _page(
        "TITANS Panorama",
        f"""
        <h1>TITANS Panorama</h1>
        <p class="notice">测试库元数据认知候选，不代表生产业务事实；本页不读取业务数据行。</p>
        <dl class="summary">
          <dt>Scope</dt><dd>{escape(scope.scope_id)}</dd>
          <dt>Run</dt><dd>{escape(run_id)}</dd>
          <dt>In-scope objects</dt><dd>{len(in_scope)}</dd>
          <dt>Boundary objects</dt><dd>{boundary_count}</dd>
          <dt>Columns</dt><dd>{len(facts.columns)}</dd>
          <dt>Definition failures</dt><dd>{definition_failures}</dd>
          <dt>Schema summaries</dt><dd>{len(derived.schema_summary)}</dd>
        </dl>
        <h2>Schemas</h2>
        <table><thead><tr><th>Schema</th><th>Objects</th><th>Columns</th><th>Definition gaps</th></tr></thead>
        <tbody>{''.join(rows)}</tbody></table>
        <p class="muted">Identity、Grain、Object Family 和业务语义尚未在 V1A 启用。</p>
        """,
    )


def _schema_html(
    schema_name: str,
    objects: list[dict[str, object]],
    summary: dict[str, object],
    profiles: dict[str, dict[str, object]],
    object_paths: dict[str, Path],
    current_path: Path,
) -> str:
    rows = []
    for row in sorted(objects, key=lambda value: str(value.get("asset_id", ""))):
        asset = str(row["asset_id"])
        profile = profiles.get(asset, {})
        object_path = object_paths[asset]
        boundary = "BOUNDARY" if row.get("is_boundary") else "IN_SCOPE"
        rows.append(
            "<tr>"
            f"<td><a href='{escape(_relative(current_path, object_path))}'>{escape(str(row.get('object_name', '')))}</a></td>"
            f"<td>{escape(str(row.get('object_type', '')))}</td>"
            f"<td>{escape(boundary)}</td>"
            f"<td>{profile.get('column_count', 0)}</td>"
            f"<td>{escape(str(row.get('extraction_status', '')))}</td>"
            "</tr>"
        )
    return _page(
        f"Schema {schema_name}",
        f"""
        <p><a href='../index.html'>← Panorama</a></p>
        <h1>Schema {escape(schema_name)}</h1>
        <p class="notice">物理元数据页面；不代表业务模块或正式业务定义。</p>
        <dl class="summary">
          <dt>Objects</dt><dd>{summary.get('object_count', 0)}</dd>
          <dt>Columns</dt><dd>{summary.get('column_count', 0)}</dd>
          <dt>Constraints</dt><dd>{summary.get('constraint_count', 0)}</dd>
          <dt>Indexes</dt><dd>{summary.get('index_count', 0)}</dd>
          <dt>Dependencies</dt><dd>{summary.get('dependency_out_count', 0)}</dd>
        </dl>
        <table><thead><tr><th>Object</th><th>Type</th><th>Scope</th><th>Columns</th><th>Status</th></tr></thead>
        <tbody>{''.join(rows)}</tbody></table>
        """,
    )


def _object_card_html(
    object_row: dict[str, object],
    facts: PhysicalFacts,
    profile: dict[str, object],
    current_path: Path,
) -> str:
    asset = str(object_row["asset_id"])
    columns = [row for row in facts.columns if row.get("asset_id") == asset]
    constraints = [row for row in facts.constraints if row.get("asset_id") == asset]
    indexes = [row for row in facts.indexes if row.get("asset_id") == asset]
    definitions = [
        row for row in facts.object_definitions if row.get("asset_id") == asset
    ]
    dependencies = [
        row for row in facts.dependencies if row.get("source_asset_id") == asset
    ]
    column_rows = "".join(
        "<tr>"
        f"<td>{escape(str(row.get('column_name', '')))}</td>"
        f"<td>{escape(str(row.get('data_type', '')))}</td>"
        f"<td>{escape(str(row.get('nullable_declared', '')))}</td>"
        f"<td>{escape(str(row.get('column_comment') or ''))}</td>"
        "</tr>"
        for row in sorted(columns, key=lambda value: int(value.get("ordinal_position", 0)))
    )
    definition_rows = "".join(
        "<tr>"
        f"<td>{escape(str(row.get('definition_type', '')))}</td>"
        f"<td>{escape(str(row.get('extraction_status', '')))}</td>"
        f"<td>{escape(str(row.get('error_category') or ''))}</td>"
        "</tr>"
        for row in definitions
    )
    dependency_rows = "".join(
        "<tr>"
        f"<td>{escape(str(row.get('target_asset_id', '')))}</td>"
        f"<td>{escape(str(row.get('dependency_type', '')))}</td>"
        f"<td>{escape(str(row.get('target_is_boundary', False)))}</td>"
        "</tr>"
        for row in dependencies
    )
    return _page(
        f"Object {object_row.get('object_name', '')}",
        f"""
        <p><a href='../schemas/{escape(_slug(str(object_row.get('schema_name', ''))))}.html'>← Schema</a></p>
        <h1>{escape(str(object_row.get('object_name', '')))}</h1>
        <p class="notice">物理 Object Card。数据来自测试库元数据，不读取业务数据行，不作业务语义结论。</p>
        <dl class="summary">
          <dt>Asset ID</dt><dd>{escape(asset)}</dd>
          <dt>Schema / Type</dt><dd>{escape(str(object_row.get('schema_name', '')))} / {escape(str(object_row.get('object_type', '')))}</dd>
          <dt>Scope</dt><dd>{'BOUNDARY' if object_row.get('is_boundary') else 'IN_SCOPE'}</dd>
          <dt>Extraction status</dt><dd>{escape(str(object_row.get('extraction_status', '')))}</dd>
          <dt>Comment</dt><dd>{escape(str(object_row.get('object_comment') or ''))}</dd>
        </dl>
        <h2>Columns ({len(columns)})</h2>
        <table><thead><tr><th>Name</th><th>Type</th><th>Nullable</th><th>Comment</th></tr></thead><tbody>{column_rows}</tbody></table>
        <h2>Definitions ({len(definitions)})</h2>
        <table><thead><tr><th>Type</th><th>Status</th><th>Error category</th></tr></thead><tbody>{definition_rows}</tbody></table>
        <h2>Constraints / Indexes</h2>
        <p>Constraints: {len(constraints)}; indexes: {len(indexes)}.</p>
        <h2>Dependencies ({len(dependencies)})</h2>
        <table><thead><tr><th>Target</th><th>Type</th><th>Boundary</th></tr></thead><tbody>{dependency_rows}</tbody></table>
        """,
    )


def _build_manifest(
    scope: ScopeConfig,
    facts: PhysicalFacts,
    root: Path,
    outputs: list[Path],
    *,
    scope_config_sha256: str | None,
    code_version: str,
) -> dict[str, object]:
    now = datetime.now(timezone.utc).isoformat()
    run_id = _run_id(facts)
    output_rows = []
    for path in outputs:
        output_rows.append(
            {
                "artifact_id": f"{run_id}:{_slug(str(path.relative_to(root)))}",
                "logical_name": path.stem,
                "relative_path": path.relative_to(root).as_posix(),
                "schema_version": "v1",
                "row_count": None,
                "content_sha256": _sha256(path),
                "producer_stage": "panorama-render",
                "status": "SUCCESS",
            }
        )
    input_paths = [
        root / "panorama" / "facts" / name
        for name in (
            "objects.json",
            "columns.json",
            "constraints.json",
            "indexes.json",
            "object_definitions.json",
            "dependencies.json",
        )
    ]
    return {
        "run_id": run_id,
        "stage_id": "panorama-render",
        "scope_ids": [scope.scope_id],
        "source_label": scope.source_label,
        "started_at": now,
        "completed_at": now,
        "visibility_boundary": "current-account-accessible-metadata",
        "source_capture": {
            "consistency_mode": "BEST_EFFORT_METADATA_CAPTURE",
            "source_scn": None,
            "query_bundle_sha256": None,
        },
        "scope_config_sha256": scope_config_sha256,
        "code_version": code_version,
        "rules_version": "v1a-physical-render-v1",
        "schema_version": "v1",
        "prompt_versions": {},
        "model_configs": {},
        "inputs": [
            {
                "artifact_id": f"{run_id}:{path.stem}",
                "logical_name": path.stem,
                "relative_path": path.relative_to(root).as_posix(),
                "schema_version": "v1",
                "content_sha256": _sha256(path),
            }
            for path in input_paths
            if path.exists()
        ],
        "outputs": output_rows,
        "known_gaps": [
            "V1A projection is physical metadata only",
            "Identity, Grain, Object Family, Wiki, and LLM are not enabled",
        ],
    }


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#17202a}}table{{border-collapse:collapse;width:100%;margin:1rem 0}}th,td{{border:1px solid #d8dee4;padding:.45rem;text-align:left;vertical-align:top}}th{{background:#f3f6f8}}.notice{{background:#fff7d6;border-left:4px solid #d9a441;padding:.75rem}}.muted{{color:#5b6570}}.summary{{display:grid;grid-template-columns:13rem 1fr;gap:.35rem 1rem}}dt{{font-weight:600}}dd{{margin:0;word-break:break-word}}a{{color:#0969da}}</style></head>
<body>{body}</body></html>
"""


def _run_id(facts: PhysicalFacts) -> str:
    for row in facts.objects:
        if row.get("run_id"):
            return str(row["run_id"])
    return "unknown-run"


def _slug(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    return f"{clean[:120]}-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:10]}"


def _relative(current: Path, target: Path) -> str:
    return Path(os.path.relpath(target, current.parent)).as_posix()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_text(value: object) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
