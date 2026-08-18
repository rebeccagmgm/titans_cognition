# -*- coding: utf-8 -*-
"""Prepare a sql-static-lineage Machine Facts profile from source-layer SQL evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


IDENTIFIER_RE = re.compile(r"^\s*(`[^`]+`|\"[^\"]+\"|\[[^\]]+\]|[A-Za-z_][A-Za-z0-9_$]*)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-manifest", required=True, type=Path)
    parser.add_argument("--source-table-facts", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--logical-source-id", default="gfhive-test-source-layer-20260817")
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def matching_close(text: str, opening: int) -> int | None:
    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(opening, len(text)):
        char = text[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in "'\"`":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def top_level_items(text: str) -> list[str]:
    items: list[str] = []
    start = 0
    depth = 0
    quote: str | None = None
    escaped = False
    for index, char in enumerate(text):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in "'\"`":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            items.append(text[start:index].strip())
            start = index + 1
    tail = text[start:].strip()
    if tail:
        items.append(tail)
    return items


def identifier(item: str) -> str | None:
    match = IDENTIFIER_RE.match(item)
    if not match:
        return None
    value = match.group(1)
    if value[:1] in "`\"[" and value[-1:] in "`\"]":
        value = value[1:-1]
    return value.strip()


def ddl_columns(ddl: str) -> list[dict[str, Any]]:
    normalized = ddl.strip()
    first_open = normalized.find("(")
    if first_open < 0:
        return []
    first_close = matching_close(normalized, first_open)
    if first_close is None:
        return []

    columns: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in top_level_items(normalized[first_open + 1:first_close]):
        name = identifier(item)
        if not name or name.upper() in {"CONSTRAINT", "PRIMARY", "UNIQUE", "KEY", "INDEX"}:
            continue
        key = name.lower()
        if key not in seen:
            columns.append({"name": name, "partition": False, "raw_definition": item})
            seen.add(key)

    partition_match = re.search(r"\bPARTITIONED\s+BY\s*\(", normalized, re.IGNORECASE)
    if partition_match:
        partition_open = normalized.find("(", partition_match.start())
        partition_close = matching_close(normalized, partition_open)
        if partition_close is not None:
            for item in top_level_items(normalized[partition_open + 1:partition_close]):
                name = identifier(item)
                if not name:
                    continue
                key = name.lower()
                if key in seen:
                    for column in columns:
                        if column["name"].lower() == key:
                            column["partition"] = True
                            break
                else:
                    columns.append({"name": name, "partition": True, "raw_definition": item})
                    seen.add(key)
    return columns


def columns_for(record: dict[str, Any]) -> list[dict[str, Any]]:
    direct = record.get("columns")
    if isinstance(direct, list):
        result: list[dict[str, Any]] = []
        for item in direct:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            result.append(
                {
                    "name": str(item["name"]),
                    "partition": bool(item.get("partition", False)),
                    "raw_definition": item.get("expression", item.get("raw_definition")),
                }
            )
        if result:
            return result
    ddl = ((record.get("ddl") or {}).get("ddl") if isinstance(record.get("ddl"), dict) else "")
    return ddl_columns(str(ddl)) if ddl else []


def schema_record(record: dict[str, Any]) -> dict[str, Any]:
    qualified_name = f"{record.get('db_name', '')}.{record.get('table_name', '')}".strip(".")
    status = str(record.get("schema_status") or "UNAVAILABLE")
    columns = columns_for(record)
    evidence_status = "SUCCESS" if columns and status != "UNAVAILABLE" else "UNRESOLVED"
    ddl_text = str((record.get("ddl") or {}).get("ddl") or "")
    return {
        "db": record.get("db_name"),
        "table": record.get("table_name"),
        "qualified_name": qualified_name,
        "required_for_star": False,
        "status": evidence_status,
        "source_status": status,
        "guid": record.get("guid"),
        "metadata_qualified_name": record.get("qualified_name"),
        "table_status": record.get("metadata_status"),
        "description": record.get("comment"),
        "ddl_sha256": sha256_bytes(ddl_text.encode("utf-8")) if ddl_text else None,
        "ddl": ddl_text or None,
        "columns": columns,
        "evidence_boundary": (
            "Source-layer table DDL/schema fact; does not establish upstream source-table metadata."
            if evidence_status == "SUCCESS"
            else "No usable source-layer table schema evidence was available."
        ),
    }


def task_output_tables(source_rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Build schedule-declared ODS outputs from table/task metadata.

    Source-layer task SQL is often exposed as the inner SELECT only.  The
    table facts retain the scheduler association, so that association is the
    authoritative input for the declared WRITE side of the task bundle.
    """

    outputs: dict[str, set[str]] = {}
    for record in source_rows:
        db_name = str(record.get("db_name") or "").strip()
        table_name = str(record.get("table_name") or "").strip()
        if not db_name or not table_name:
            continue
        qualified_name = f"{db_name}.{table_name}"
        task_ids = record.get("task_ids") or []
        if isinstance(task_ids, str):
            task_ids = [task_ids]
        if not isinstance(task_ids, list):
            continue
        for task_id in task_ids:
            normalized_task_id = str(task_id).strip()
            if normalized_task_id:
                outputs.setdefault(normalized_task_id, set()).add(qualified_name)
    return {task_id: sorted(names) for task_id, names in outputs.items()}


def main() -> int:
    args = parse_args()
    task_manifest = args.task_manifest.resolve()
    source_facts = args.source_table_facts.resolve()
    output_dir = args.output_dir.resolve()
    project_root = Path.cwd().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    task_rows = read_jsonl(task_manifest)
    source_rows = read_jsonl(source_facts)
    outputs_by_task = task_output_tables(source_rows)
    valid_tasks: list[dict[str, Any]] = []
    for row in task_rows:
        task_id = str(row.get("task_id") or "")
        sql_path = Path(str(row.get("normalized_path") or "")).resolve()
        if not task_id.isdigit() or not sql_path.exists() or sql_path.stat().st_size == 0:
            raise SystemExit(f"invalid task SQL evidence: {task_id}")
        try:
            relative_sql = sql_path.relative_to(project_root).as_posix()
        except ValueError as error:
            raise SystemExit(f"task SQL must be inside project: {sql_path}") from error
        task_profile: dict[str, Any] = {"task_id": task_id, "sql_snapshot": relative_sql}
        declared_outputs = outputs_by_task.get(task_id, [])
        if declared_outputs:
            task_profile["writes"] = declared_outputs
        valid_tasks.append(task_profile)
    task_ids = [row["task_id"] for row in valid_tasks]
    if len(task_ids) != len(set(task_ids)):
        raise SystemExit("duplicate task_id in task manifest")

    schema_records = [schema_record(row) for row in source_rows]
    schema_evidence = {
        "schema_version": "source-layer-machine-facts-schema-evidence-v1",
        "case_id": output_dir.name,
        "source": "CANONICAL_SOURCE_LAYER_TABLE_FACTS",
        "collection_mode": "DDL_OR_TASK_SQL_PROJECTION",
        "required_table_count": len(schema_records),
        "required_star_table_count": 0,
        "success_count": sum(row["status"] == "SUCCESS" for row in schema_records),
        "unresolved_count": sum(row["status"] != "SUCCESS" for row in schema_records),
        "evidence_boundary": "Table facts describe source-layer ODS table schemas; upstream TITANS schema is not inferred from them.",
        "records": schema_records,
    }
    profile = {
        "schema_version": "machine-facts-source-layer-profile-v1",
        "dialect": "databricks",
        "logical_source_id": args.logical_source_id,
        "schema_evidence": (output_dir / "schema-evidence.json").relative_to(project_root).as_posix(),
        "tasks": valid_tasks,
    }
    summary = {
        "task_count": len(valid_tasks),
        "schema_record_count": len(schema_records),
        "schema_success_count": schema_evidence["success_count"],
        "schema_unresolved_count": schema_evidence["unresolved_count"],
        "declared_write_task_count": sum(1 for row in valid_tasks if row.get("writes")),
        "declared_write_count": sum(len(row.get("writes", [])) for row in valid_tasks),
        "profile": str(output_dir / "machine-facts-profile.json"),
        "schema_evidence": str(output_dir / "schema-evidence.json"),
    }
    (output_dir / "machine-facts-profile.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "schema-evidence.json").write_text(json.dumps(schema_evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "preparation-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
