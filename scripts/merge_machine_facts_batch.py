# -*- coding: utf-8 -*-
"""Safely merge a validated Machine Facts batch into a canonical root.

Overlapping task IDs are retained from the canonical root after their SQL
hashes are checked. Only new task IDs are copied. Content-addressed snapshots
are copied only when absent or byte-identical, and the canonical index is
replaced atomically after all preflight checks pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--incoming", required=True, type=Path)
    parser.add_argument("--canonical", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument(
        "--replace-overlap",
        action="store_true",
        help="replace canonical bundles for overlapping task IDs after preflight validation",
    )
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_jsonl(rows: list[dict[str, Any]]) -> str:
    ordered = sorted(rows, key=lambda row: str(row.get("task_id", "")))
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in ordered)


def copy_if_needed(source: Path, target: Path) -> str:
    if target.exists():
        if sha256_file(source) != sha256_file(target):
            raise RuntimeError(f"content-addressed artifact collision: {target}")
        return "EXISTING_IDENTICAL"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return "COPIED"


def validate_incoming_task(incoming: Path, row: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    task_id = str(row.get("task_id") or "")
    if row.get("status") != "SUCCESS":
        raise RuntimeError(f"incoming task is not SUCCESS: {task_id}")
    bundle = incoming / str(row.get("bundle_path") or "")
    manifest_path = bundle / "manifest.json"
    status_path = bundle.parent / "analysis-status.json"
    if not manifest_path.exists() or not status_path.exists():
        raise RuntimeError(f"missing bundle/status: {task_id}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    status = json.loads(status_path.read_text(encoding="utf-8"))
    if manifest.get("task_id") != task_id or status.get("task_id") != task_id:
        raise RuntimeError(f"task identity mismatch: {task_id}")
    if status.get("state") != "SUCCESS" or status.get("current_manifest_sha256") != row.get("manifest_sha256"):
        raise RuntimeError(f"status/index mismatch: {task_id}")
    for key in ("sql_snapshot", "schema_snapshot"):
        relative = str(manifest.get("inputs", {}).get(key) or "")
        artifact = incoming / relative
        if not artifact.exists() or artifact.stat().st_size == 0:
            raise RuntimeError(f"missing {key} for task {task_id}: {relative}")
    return bundle.parent, manifest


def main() -> int:
    args = parse_args()
    incoming = args.incoming.resolve()
    canonical = args.canonical.resolve()
    report_path = args.report.resolve()
    incoming_index_path = incoming / "indexes/task-fact-index.jsonl"
    canonical_index_path = canonical / "indexes/task-fact-index.jsonl"
    incoming_rows = read_jsonl(incoming_index_path)
    canonical_rows = read_jsonl(canonical_index_path)
    incoming_by_id = {str(row["task_id"]): row for row in incoming_rows}
    canonical_by_id = {str(row["task_id"]): row for row in canonical_rows}
    if len(incoming_by_id) != len(incoming_rows):
        raise RuntimeError("incoming index contains duplicate task IDs")
    if len(canonical_by_id) != len(canonical_rows):
        raise RuntimeError("canonical index contains duplicate task IDs")

    overlap = sorted(set(incoming_by_id) & set(canonical_by_id), key=int)
    sql_conflicts = [
        task_id
        for task_id in overlap
        if incoming_by_id[task_id].get("sql_sha256") != canonical_by_id[task_id].get("sql_sha256")
    ]
    if sql_conflicts:
        raise RuntimeError(f"SQL hash conflicts for task IDs: {','.join(sql_conflicts)}")
    new_ids = sorted(set(incoming_by_id) - set(canonical_by_id), key=int)
    replace_ids = overlap if args.replace_overlap else []
    validated_ids = sorted(set(new_ids) | set(replace_ids), key=int)

    validated: dict[str, tuple[Path, dict[str, Any]]] = {}
    for task_id in validated_ids:
        validated[task_id] = validate_incoming_task(incoming, incoming_by_id[task_id])
        target_task = canonical / "registry/tasks" / task_id
        if task_id in new_ids and target_task.exists():
            raise RuntimeError(f"task directory exists but is absent from canonical index: {task_id}")
        if task_id in replace_ids and not target_task.exists():
            raise RuntimeError(f"overlap task directory is missing from canonical root: {task_id}")

    artifacts: list[tuple[Path, Path]] = []
    for task_id, (task_root, manifest) in validated.items():
        for key in ("sql_snapshot", "schema_snapshot"):
            relative = Path(str(manifest["inputs"][key]).replace("/", os.sep))
            artifacts.append((incoming / relative, canonical / relative))

    for source, target in artifacts:
        if target.exists() and sha256_file(source) != sha256_file(target):
            raise RuntimeError(f"artifact collision: {target}")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    before_index = report_path.parent / "canonical-index-before-merge.jsonl"
    shutil.copy2(canonical_index_path, before_index)
    task_backup: Path | None = None
    if replace_ids:
        task_backup = report_path.parent / f"canonical-task-backup-before-merge-{os.getpid()}"
        if task_backup.exists():
            raise RuntimeError(f"task backup already exists: {task_backup}")
        task_backup.mkdir(parents=True)
        for task_id in replace_ids:
            shutil.copytree(canonical / "registry/tasks" / task_id, task_backup / task_id)

    copied_artifacts = 0
    identical_artifacts = 0
    for source, target in artifacts:
        result = copy_if_needed(source, target)
        if result == "COPIED":
            copied_artifacts += 1
        else:
            identical_artifacts += 1

    for task_id, (task_root, _) in validated.items():
        target_task = canonical / "registry/tasks" / task_id
        if task_id in replace_ids:
            shutil.rmtree(target_task)
        shutil.copytree(task_root, target_task)

    final_by_id = dict(canonical_by_id)
    for task_id in validated_ids:
        final_by_id[task_id] = incoming_by_id[task_id]
    final_rows = list(final_by_id.values())
    temporary_index = canonical_index_path.with_name(f"{canonical_index_path.name}.merge-{os.getpid()}.tmp")
    temporary_index.write_text(canonical_jsonl(final_rows), encoding="utf-8")
    os.replace(temporary_index, canonical_index_path)

    report = {
        "incoming_task_count": len(incoming_rows),
        "canonical_task_count_before": len(canonical_rows),
        "overlap_count": len(overlap),
        "overlap_sql_conflicts": len(sql_conflicts),
        "new_task_count": len(new_ids),
        "replaced_task_count": len(replace_ids),
        "canonical_task_count_after": len(final_rows),
        "copied_snapshot_count": copied_artifacts,
        "identical_snapshot_count": identical_artifacts,
        "canonical_index_backup": str(before_index),
        "canonical_task_backup": str(task_backup) if task_backup else None,
        "canonical_index": str(canonical_index_path),
        "incoming_root": str(incoming),
        "logical_source_ids": sorted({str(row.get("logical_source_id")) for row in final_rows}),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
