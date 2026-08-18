r"""Batch-read SZData metadata required to expand SELECT * safely.

The script is deliberately read-only.  It reads a sql-static-lineage target manifest,
resolves table names to databases, reuses GUIDs from existing lineage extracts,
and caches table metadata plus DDL as append-only JSONL records.

Example (PowerShell)::

    .venv\Scripts\python.exe scripts\szdata_star_metadata_batch.py `
      --targets output\downstream-machine-facts-20260817\star-metadata-targets.json `
      --cache output\downstream-machine-facts-20260817\szdata-schema-cache.jsonl `
      --task-map output\titans-collection-20260815\data\downstream-tables-tasks.csv `
      --odata-lineage output\titans-collection-20260815\data\downstream-odata.csv `
      --guid-overrides cases\downstream-machine-facts\szdata-guid-overrides.json `
      --retry-errors --retry-empty

The cache is append-only; the latest record for a cache key is authoritative.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import shutil
import subprocess
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

LOGGER = logging.getLogger("szdata_star_metadata_batch")
TABLE_FIELDS = (
    "guid",
    "qualifiedName",
    "status",
    "description",
    "typeName",
    "tableType",
    "dbType",
    "dbName",
    "tableName",
)
TABLE_DETAIL_FIELDS = ("structure", "partition", "tasks", "lineage", "business", "relations")
DDL_FIELDS = ("guid", "qualifiedName", "dbName", "tableName", "type", "partition", "ddl")


@dataclass(frozen=True)
class Target:
    cache_key: str
    table_ref: str
    db: str
    table: str
    db_resolution: str
    task_ids: tuple[str, ...]
    source_records: tuple[dict[str, Any], ...]


def _first_row(payload: Any) -> dict[str, Any] | None:
    """Unwrap the JSON shapes returned by opencli/MCP.

    SZData commonly returns ``[row]``.  Some adapters wrap that list in a
    ``result`` field, so both forms are accepted.
    """

    if isinstance(payload, list):
        return payload[0] if payload and isinstance(payload[0], dict) else None
    if not isinstance(payload, dict):
        return None
    result = payload.get("result")
    if isinstance(result, list):
        return result[0] if result and isinstance(result[0], dict) else None
    if isinstance(result, dict):
        return result
    return payload


def parse_table_response(payload: Any) -> dict[str, Any] | None:
    """Parse ``szdata table --view full`` including the nested table object."""

    row = _first_row(payload)
    if not row:
        return None
    table = row.get("table") if isinstance(row.get("table"), dict) else row
    if isinstance(row.get("data"), dict) and not table.get("guid"):
        data = row["data"]
        table = data.get("table", data) if isinstance(data, dict) else table
    result = {field: table[field] for field in TABLE_FIELDS if field in table}
    result.update({field: row[field] for field in TABLE_DETAIL_FIELDS if field in row})
    return result or None


def parse_ddl_response(payload: Any) -> dict[str, Any] | None:
    """Parse ``szdata table-ddl`` including its outer JSON array."""

    row = _first_row(payload)
    if not row:
        return None
    return {field: row[field] for field in DDL_FIELDS if field in row} or None


def is_rate_limited(message: str | None) -> bool:
    text = message or ""
    return "threshold=5" in text or "dimension=USER" in text or "全局限流" in text


def _safe_identifier(value: str) -> bool:
    return bool(value) and all(char.isalnum() or char in "._$" for char in value)


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _load_latest_cache(path: Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return latest
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                LOGGER.warning("Ignoring malformed cache line %s:%d", path, line_number)
                continue
            key = record.get("cache_key")
            if key:
                latest[key] = record
    return latest


def _load_task_databases(path: Path | None) -> dict[str, set[str]]:
    task_databases: dict[str, set[str]] = defaultdict(set)
    if path is None or not path.exists():
        return task_databases
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            task_id = (row.get("horae_task_id") or "").strip()
            database = (row.get("db_name") or "").strip()
            if task_id and database:
                task_databases[task_id].add(database)
    return task_databases


def _load_guid_indexes(
    task_map_path: Path | None, odata_lineage_path: Path | None
) -> tuple[dict[str, str], dict[str, set[str]]]:
    qualified: dict[str, str] = {}
    simple: dict[str, set[str]] = defaultdict(set)
    if task_map_path and task_map_path.exists():
        with task_map_path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                database = (row.get("db_name") or "").strip().lower()
                table = (row.get("downstream_name") or "").strip().lower()
                guid = (row.get("downstream_guid") or "").strip()
                if database and table and guid:
                    qualified[f"{database}.{table}"] = guid
    if odata_lineage_path and odata_lineage_path.exists():
        with odata_lineage_path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                table = (row.get("upstream_table") or "").strip().lower()
                guid = (row.get("guid") or "").strip()
                if table and guid:
                    simple[table].add(guid)
    return qualified, simple


def load_guid_overrides(path: Path | None) -> dict[str, str]:
    """Load explicit logical-name to physical-GUID decisions.

    Values may be a GUID string or an object containing a ``guid`` field.  The
    latter lets the config retain a human-readable reason without changing the
    runtime contract.
    """

    if path is None or not path.exists():
        return {}
    payload = _read_json(path)
    raw_overrides = payload.get("overrides", payload) if isinstance(payload, dict) else {}
    result: dict[str, str] = {}
    for key, value in raw_overrides.items():
        if isinstance(value, str) and value:
            result[key.lower()] = value
        elif isinstance(value, dict) and isinstance(value.get("guid"), str) and value["guid"]:
            result[key.lower()] = value["guid"]
    return result


def load_targets(path: Path, task_map_path: Path | None = None) -> list[Target]:
    payload = _read_json(path)
    raw_records = payload.get("unique_table_refs") or payload.get("records") or []
    task_databases = _load_task_databases(task_map_path)
    grouped: dict[str, dict[str, Any]] = {}
    for raw in raw_records:
        table_ref = (raw.get("table_ref") or "").strip()
        if not table_ref:
            continue
        task_id = str(raw.get("task_id") or "")
        parts = table_ref.split(".")
        if raw.get("qualified") and len(parts) >= 2:
            database = ".".join(parts[:-1])
            table = parts[-1]
            resolution = "SQL_QUALIFIED"
        else:
            table = table_ref
            candidates = task_databases.get(task_id, set())
            database = next(iter(candidates)) if len(candidates) == 1 else ""
            resolution = "TASK_DB_UNIQUE" if database else "UNRESOLVED"
        key = f"{database.lower()}.{table.lower()}" if database else f"?.{table.lower()}"
        group = grouped.setdefault(
            key,
            {
                "cache_key": key,
                "table_ref": table_ref,
                "db": database,
                "table": table,
                "db_resolution": resolution,
                "task_ids": set(),
                "source_records": [],
            },
        )
        if task_id:
            group["task_ids"].add(task_id)
        group["source_records"].append(
            {
                field: raw.get(field)
                for field in (
                    "task_id",
                    "sql_file",
                    "statement_index",
                    "dialect",
                    "table_ref",
                    "qualified",
                )
            }
        )
    return [
        Target(
            cache_key=group["cache_key"],
            table_ref=group["table_ref"],
            db=group["db"],
            table=group["table"],
            db_resolution=group["db_resolution"],
            task_ids=tuple(sorted(group["task_ids"])),
            source_records=tuple(group["source_records"]),
        )
        for group in sorted(grouped.values(), key=lambda item: item["cache_key"])
    ]


def _opencli_command() -> str:
    configured = os.environ.get("OPENCLI_COMMAND")
    if configured:
        return configured
    for candidate in ("opencli.cmd", "opencli", "opencli.ps1"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise FileNotFoundError("opencli command not found; set OPENCLI_COMMAND explicitly")


class SzDataClient:
    def __init__(self, command: str, timeout: float, retries: int, retry_delay: float) -> None:
        self.command = command
        self.timeout = timeout
        self.retries = retries
        self.retry_delay = retry_delay

    def query(self, args: list[str]) -> tuple[Any | None, str | None]:
        for attempt in range(self.retries + 1):
            try:
                completed = subprocess.run(
                    [self.command, "szdata", *args, "-f", "json"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                if attempt < self.retries:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                return None, "CLI_TIMEOUT"
            except OSError as error:
                return None, f"EXEC_ERROR:{type(error).__name__}"
            output = (completed.stdout or "").strip()
            if completed.returncode == 0 and output:
                try:
                    payload = json.loads(output)
                except json.JSONDecodeError as error:
                    return None, f"JSON_ERROR:{type(error).__name__}"
                if isinstance(payload, dict) and payload.get("ok") is False:
                    return None, "CLI_RESPONSE_NOT_OK"
                return payload, None
            message = (completed.stderr or completed.stdout or "").strip()
            if is_rate_limited(message) and attempt < self.retries:
                time.sleep(self.retry_delay * (attempt + 1))
                continue
            return None, f"CLI_EXIT:{completed.returncode}:{message[-500:]}"
        return None, "RETRY_EXHAUSTED"


def _table_record(client: SzDataClient, target: Target) -> tuple[str, dict[str, Any] | None, str | None]:
    if not _safe_identifier(target.db) or not _safe_identifier(target.table):
        return target.cache_key, None, "UNSAFE_OR_UNRESOLVED_IDENTIFIER"
    payload, error = client.query(["table", "--db", target.db, "--table", target.table, "--view", "full"])
    return target.cache_key, parse_table_response(payload) if error is None else None, error


def _ddl_record(
    client: SzDataClient, target: Target, guid: str
) -> tuple[str, dict[str, Any] | None, str | None]:
    payload, error = client.query(["table-ddl", "--guid", guid])
    return target.cache_key, parse_ddl_response(payload) if error is None else None, error


def _map_parallel(items: Iterable[Any], workers: int, function: Any) -> dict[str, tuple[Any, ...]]:
    values = list(items)
    if not values:
        return {}
    results: dict[str, tuple[Any, ...]] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [executor.submit(function, item) for item in values]
        for future in as_completed(futures):
            result = future.result()
            results[result[0]] = result[1:]
    return results


def _needs_retry(record: dict[str, Any], retry_errors: bool, retry_empty: bool) -> bool:
    if record.get("ddl_status") == "SUCCESS":
        return False
    if record.get("table_status") == "ERROR" or record.get("ddl_status") == "ERROR":
        return retry_errors
    return retry_empty


def collect(
    targets: list[Target],
    cache_path: Path,
    task_map_path: Path | None,
    odata_lineage_path: Path | None,
    guid_overrides_path: Path | None,
    workers: int,
    timeout: float,
    retries: int,
    retry_delay: float,
    retry_errors: bool,
    retry_empty: bool,
) -> dict[str, Any]:
    latest = _load_latest_cache(cache_path)
    qualified_guids, simple_guids = _load_guid_indexes(task_map_path, odata_lineage_path)
    guid_overrides = load_guid_overrides(guid_overrides_path)
    selected: list[Target] = []
    for target in targets:
        previous = latest.get(target.cache_key)
        if target.cache_key.lower() in guid_overrides and (
            not previous or previous.get("ddl_status") != "SUCCESS"
        ):
            selected.append(target)
            continue
        if previous and not _needs_retry(previous, retry_errors, retry_empty):
            continue
        selected.append(target)

    client = SzDataClient(_opencli_command(), timeout, retries, retry_delay)
    table_results: dict[str, tuple[dict[str, Any] | None, str | None]] = {}
    ddl_results: dict[str, tuple[dict[str, Any] | None, str | None]] = {}
    guid_by_key: dict[str, str] = {}
    mode_by_key: dict[str, str] = {}
    table_work: list[Target] = []

    for target in selected:
        previous = latest.get(target.cache_key, {})
        previous_info = previous.get("table_info") or {}
        guid = guid_overrides.get(target.cache_key.lower()) or previous_info.get("guid")
        if guid_overrides.get(target.cache_key.lower()):
            mode_by_key[target.cache_key] = "CONFIGURED_GUID_OVERRIDE"
        if not guid and target.db:
            guid = qualified_guids.get(f"{target.db.lower()}.{target.table.lower()}")
            if guid:
                mode_by_key[target.cache_key] = "LOCAL_QUALIFIED_GUID"
        if not guid and target.db.lower() == "odata_n_tit":
            candidates = simple_guids.get(target.table.lower(), set())
            if len(candidates) == 1:
                guid = next(iter(candidates))
                mode_by_key[target.cache_key] = "LOCAL_ODS_GUID"
        if guid:
            guid_by_key[target.cache_key] = guid
            table_results[target.cache_key] = (
                previous_info
                or {
                    "guid": guid,
                    "qualifiedName": f"{target.db}.{target.table}",
                    "dbName": target.db,
                    "tableName": target.table,
                },
                None,
            )
        else:
            table_work.append(target)
            mode_by_key.setdefault(target.cache_key, "SZDATA_TABLE")

    LOGGER.info("table lookups=%d, workers=%d", len(table_work), workers)
    table_results.update(_map_parallel(table_work, workers, lambda item: _table_record(client, item)))
    for key, (info, error) in table_results.items():
        if info and info.get("guid"):
            guid_by_key[key] = info["guid"]

    ddl_work = [target for target in selected if target.cache_key in guid_by_key]
    LOGGER.info("DDL lookups=%d, workers=%d", len(ddl_work), workers)
    ddl_results.update(
        _map_parallel(
            ddl_work,
            workers,
            lambda item: _ddl_record(client, item, guid_by_key[item.cache_key]),
        )
    )

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("a", encoding="utf-8") as handle:
        for target in selected:
            table_info, table_error = table_results.get(target.cache_key, (None, "NO_TABLE_RESULT"))
            ddl_info, ddl_error = ddl_results.get(target.cache_key, (None, None))
            record: dict[str, Any] = {
                "cache_key": target.cache_key,
                "table_ref": target.table_ref,
                "db": target.db,
                "table": target.table,
                "db_resolution": target.db_resolution,
                "task_ids": list(target.task_ids),
                "source_records": list(target.source_records),
                "lookup_mode": mode_by_key.get(target.cache_key, "SZDATA_TABLE"),
                "table_status": "SUCCESS" if table_info else "ERROR" if table_error else "EMPTY",
                "ddl_status": "SUCCESS" if ddl_info and ddl_info.get("ddl") else "NO_GUID",
            }
            if table_info:
                record["table_info"] = table_info
            if table_error:
                record["table_error"] = table_error
            if ddl_info:
                record["ddl"] = ddl_info
                if not ddl_info.get("ddl"):
                    record["ddl_status"] = "NO_DDL"
            elif target.cache_key in guid_by_key:
                record["ddl_status"] = "ERROR" if ddl_error else "EMPTY"
            if ddl_error:
                record["ddl_error"] = ddl_error
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            latest[target.cache_key] = record

    table_status = Counter(record.get("table_status") for record in latest.values())
    ddl_status = Counter(record.get("ddl_status") for record in latest.values())
    summary = {
        "target_groups": len(targets),
        "selected_for_processing": len(selected),
        "latest_records": len(latest),
        "table_status": dict(sorted(table_status.items())),
        "ddl_status": dict(sorted(ddl_status.items())),
        "records_with_ddl": sum(record.get("ddl_status") == "SUCCESS" for record in latest.values()),
        "records_with_errors": sum(
            record.get("table_status") == "ERROR" or record.get("ddl_status") == "ERROR"
            for record in latest.values()
        ),
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", type=Path, required=True, help="sql-static-lineage star-metadata-targets.json")
    parser.add_argument("--cache", type=Path, required=True, help="append-only metadata cache JSONL")
    parser.add_argument("--summary", type=Path, help="summary JSON; defaults beside --cache")
    parser.add_argument("--task-map", type=Path, help="downstream-tables-tasks.csv")
    parser.add_argument("--odata-lineage", type=Path, help="downstream-odata.csv")
    parser.add_argument("--guid-overrides", type=Path, help="explicit logical-name to physical-GUID decisions")
    parser.add_argument("--workers", type=int, default=1, help="SZData concurrency; default 1 for rate-limit safety")
    parser.add_argument("--timeout", type=float, default=80.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--retry-delay", type=float, default=2.0)
    parser.add_argument("--retry-errors", action="store_true")
    parser.add_argument("--retry-empty", action="store_true")
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s %(message)s")
    if args.workers < 1:
        parser.error("--workers must be >= 1")
    targets = load_targets(args.targets, args.task_map)
    summary = collect(
        targets=targets,
        cache_path=args.cache,
        task_map_path=args.task_map,
        odata_lineage_path=args.odata_lineage,
        guid_overrides_path=args.guid_overrides,
        workers=args.workers,
        timeout=args.timeout,
        retries=args.retries,
        retry_delay=args.retry_delay,
        retry_errors=args.retry_errors,
        retry_empty=args.retry_empty,
    )
    summary_path = args.summary or args.cache.with_name("szdata-schema-cache-summary.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
