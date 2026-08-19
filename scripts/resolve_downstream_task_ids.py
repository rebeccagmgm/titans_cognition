"""Resolve downstream table assets to Horae task IDs through SZData.

The resolver is deliberately serial and resumable:

* one ``task-inspect --table`` call at a time;
* 15 seconds between normal calls by default;
* explicit rate-limit classification and a bounded backoff;
* successful and confirmed no-task rows are skipped on later runs;
* every result is checkpointed to CSV after each query.

It only performs read-only SZData metadata queries.  It does not generate or
merge Machine Facts.

Example:

    python scripts/resolve_downstream_task_ids.py \
        --input output/szdata-recursive-downstream-20260818-sharded/table-details/part-00001.csv \
        --output output/downstream-dive-20260818/part-00001-task-map.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


OUTPUT_FIELDS = (
    "guid",
    "db_name",
    "qualified_name",
    "query_table",
    "status",
    "task_ids",
    "task_count",
    "attempts",
    "checked_at_utc",
    "evidence_level",
    "error_class",
)
RESOLVED_STATUSES = {"SUCCESS", "NO_TASKS"}
NON_RETRYABLE_INPUT_STATUSES = {"INPUT_INVALID"}


@dataclass(frozen=True)
class QueryResult:
    status: str
    task_ids: tuple[str, ...] = ()
    task_count: int | None = None
    evidence_level: str = ""
    error_class: str = ""


def normalize_query_table(qualified_name: str) -> str:
    """Remove the physical data-source suffix from ``db.table@source``."""

    return qualified_name.strip().split("@", 1)[0].strip()


def _decode(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _is_rate_limit(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in (
            "限流",
            "rate limit",
            "rate_limit",
            "too many requests",
            "429",
            "dimension=user",
            "threshold=",
        )
    )


def _error_class(text: str) -> str:
    lowered = text.lower()
    if _is_rate_limit(text):
        return "RATE_LIMIT"
    if any(marker in lowered for marker in ("auth_required", "鉴权", "登录", "session")):
        return "AUTH_REQUIRED"
    if "timeout" in lowered or "超时" in text:
        return "TIMEOUT"
    return "COMMAND_ERROR"


def _unique_task_ids(records: Iterable[dict[str, Any]]) -> tuple[str, ...]:
    values: list[str] = []
    seen: set[str] = set()
    for record in records:
        task_id = str(record.get("taskId") or record.get("task_id") or "").strip()
        if task_id and task_id not in seen:
            seen.add(task_id)
            values.append(task_id)
    return tuple(values)


def classify_response(returncode: int, stdout: str, stderr: str) -> QueryResult:
    """Classify one OpenCLI response without collapsing failures into no-match."""

    if returncode != 0:
        error_class = _error_class(stdout + "\n" + stderr)
        status = "RATE_LIMITED" if error_class == "RATE_LIMIT" else error_class
        return QueryResult(status=status, error_class=error_class)

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return QueryResult(status="PARSE_ERROR", error_class="JSON_PARSE")

    if isinstance(payload, list):
        item = payload[0] if payload else {}
    elif isinstance(payload, dict):
        item = payload
    else:
        item = {}
    if not isinstance(item, dict):
        return QueryResult(status="PARSE_ERROR", error_class="JSON_SHAPE")

    profile = item.get("tableProfile") or {}
    profile_tasks = profile.get("tasks") if isinstance(profile, dict) else []
    task_records = item.get("tasks") or []
    if not isinstance(profile_tasks, list):
        profile_tasks = []
    if not isinstance(task_records, list):
        task_records = []
    task_ids = _unique_task_ids([*profile_tasks, *task_records])

    errors = [
        error
        for record in task_records
        if isinstance(record, dict)
        for error in (record.get("errors") or [])
        if error
    ]
    top_status = str(item.get("status") or "").upper()
    evidence_level = str(item.get("evidenceLevel") or "")
    raw_count = item.get("taskCount")
    task_count = raw_count if isinstance(raw_count, int) else len(task_ids)

    if top_status == "PARTIAL" or errors:
        return QueryResult(
            status="PARTIAL",
            task_ids=task_ids,
            task_count=task_count,
            evidence_level=evidence_level,
            error_class="TASK_PARTIAL",
        )
    if task_ids:
        return QueryResult(
            status="SUCCESS",
            task_ids=task_ids,
            task_count=task_count,
            evidence_level=evidence_level,
        )
    return QueryResult(
        status="NO_TASKS",
        task_count=task_count,
        evidence_level=evidence_level,
    )


def query_table(table: str, timeout_seconds: int) -> QueryResult:
    command = build_task_inspect_command(table)
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            shell=False,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return QueryResult(status="TIMEOUT", error_class="TIMEOUT")
    except OSError:
        return QueryResult(status="COMMAND_ERROR", error_class="OPENCLI_UNAVAILABLE")

    return classify_response(
        completed.returncode,
        _decode(completed.stdout),
        _decode(completed.stderr),
    )


def _input_files(path: Path, max_input_files: int | None = None) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        files = sorted(path.glob("part-*.csv"))
        if max_input_files is not None:
            if max_input_files <= 0:
                raise ValueError("max_input_files must be positive")
            files = files[:max_input_files]
        return files
    raise FileNotFoundError(path)


def load_input_rows(
    path: Path, max_input_files: int | None = None
) -> list[dict[str, str]]:
    rows_by_guid: dict[str, dict[str, str]] = {}
    for file_path in _input_files(path, max_input_files):
        with file_path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                guid = str(row.get("guid") or "").strip()
                if not guid:
                    continue
                rows_by_guid.setdefault(guid, {key: str(value or "") for key, value in row.items()})
    return list(rows_by_guid.values())


def load_existing(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {
            str(row.get("guid") or "").strip(): row
            for row in csv.DictReader(handle)
            if str(row.get("guid") or "").strip()
        }


def _atomic_write(path: Path, rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with temp_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        last_error: PermissionError | None = None
        for attempt in range(5):
            try:
                os.replace(temp_path, path)
                last_error = None
                break
            except PermissionError as error:
                last_error = error
                if attempt == 4:
                    raise
                time.sleep(0.2 * (attempt + 1))
        if last_error is not None:
            raise last_error
    finally:
        temp_path.unlink(missing_ok=True)


def _record(
    source: dict[str, str],
    result: QueryResult,
    attempts: int,
) -> dict[str, str]:
    qualified_name = str(source.get("qualified_name") or "").strip()
    query_table = normalize_query_table(qualified_name)
    return {
        "guid": str(source.get("guid") or "").strip(),
        "db_name": str(source.get("db_name") or "").strip(),
        "qualified_name": qualified_name,
        "query_table": query_table,
        "status": result.status,
        "task_ids": "|".join(result.task_ids),
        "task_count": "" if result.task_count is None else str(result.task_count),
        "attempts": str(attempts),
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "evidence_level": result.evidence_level,
        "error_class": result.error_class,
    }


def _pending_record(source: dict[str, str]) -> dict[str, str]:
    return _record(source, QueryResult(status="PENDING"), 0)


def _checkpoint_rows(
    sources: Iterable[dict[str, str]], results: dict[str, dict[str, str]]
) -> Iterable[dict[str, str]]:
    for source in sources:
        guid = str(source.get("guid") or "").strip()
        yield results.get(guid, _pending_record(source))


def _opencli_executable() -> str:
    """Resolve the Windows command shim that Python can execute directly."""

    if os.name == "nt":
        return shutil.which("opencli.cmd") or shutil.which("opencli") or "opencli.cmd"
    return shutil.which("opencli") or "opencli"


def build_task_inspect_command(table: str) -> list[str]:
    return [
        _opencli_executable(),
        "szdata",
        "task-inspect",
        "--table",
        table,
        "--include",
        "detail",
        "--concurrency",
        "1",
        "-f",
        "json",
        "--trace",
        "retain-on-failure",
    ]


def run(
    *,
    input_path: Path,
    output_path: Path,
    interval_seconds: float = 15.0,
    timeout_seconds: int = 90,
    rate_limit_backoff_seconds: float = 120.0,
    rate_limit_retries: int = 1,
    max_input_files: int | None = None,
) -> int:
    sources = load_input_rows(input_path, max_input_files)
    existing = load_existing(output_path)
    results = dict(existing)
    for source in sources:
        guid = str(source.get("guid") or "").strip()
        query_table_name = normalize_query_table(str(source.get("qualified_name") or ""))
        if not query_table_name and results.get(guid, {}).get("status") != "INPUT_INVALID":
            results[guid] = _record(
                source,
                QueryResult(
                    status="INPUT_INVALID",
                    error_class="MISSING_QUALIFIED_NAME",
                ),
                int(results.get(guid, {}).get("attempts") or 0),
            )
    pending = [
        source
        for source in sources
        if results.get(str(source.get("guid") or "").strip(), {}).get("status")
        not in RESOLVED_STATUSES | NON_RETRYABLE_INPUT_STATUSES
    ]

    print(f"input objects: {len(sources)}", flush=True)
    print(f"pending objects: {len(pending)}", flush=True)
    if not pending:
        _atomic_write(output_path, _checkpoint_rows(sources, results))
        return 1 if any(
            results[source["guid"]].get("status") not in RESOLVED_STATUSES
            for source in sources
        ) else 0

    for index, source in enumerate(pending, 1):
        guid = str(source.get("guid") or "").strip()
        prior_attempts = int(results.get(guid, {}).get("attempts") or 0)
        rate_limit_attempt = 0
        while True:
            query_table_name = normalize_query_table(str(source.get("qualified_name") or ""))
            if not query_table_name:
                result = QueryResult(
                    status="INPUT_INVALID",
                    error_class="MISSING_QUALIFIED_NAME",
                )
            else:
                result = query_table(query_table_name, timeout_seconds)
            attempts = prior_attempts + 1
            results[guid] = _record(source, result, attempts)
            _atomic_write(output_path, _checkpoint_rows(sources, results))
            print(
                f"[{index}/{len(pending)}] {query_table_name} -> {result.status}",
                flush=True,
            )

            if result.status != "RATE_LIMITED":
                break
            if rate_limit_attempt >= rate_limit_retries:
                print(
                    "rate limit persisted; checkpoint saved, stopping for a later resume",
                    flush=True,
                )
                return 2
            rate_limit_attempt += 1
            backoff = rate_limit_backoff_seconds * (2 ** (rate_limit_attempt - 1))
            print(
                f"rate limit detected; backing off {backoff:g}s before retry",
                flush=True,
            )
            time.sleep(backoff)

        if index < len(pending):
            time.sleep(interval_seconds)

    unresolved = [
        row
        for row in (results[source["guid"]] for source in sources)
        if row.get("status") not in RESOLVED_STATUSES
    ]
    return 1 if unresolved else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, dest="input_path")
    parser.add_argument("--output", required=True, type=Path, dest="output_path")
    parser.add_argument("--interval-seconds", type=float, default=15.0)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--rate-limit-backoff-seconds", type=float, default=120.0)
    parser.add_argument("--rate-limit-retries", type=int, default=1)
    parser.add_argument(
        "--max-input-files",
        type=int,
        default=None,
        help="When --input is a directory, process only the first N sorted part-*.csv files.",
    )
    args = parser.parse_args()
    return run(
        input_path=args.input_path,
        output_path=args.output_path,
        interval_seconds=args.interval_seconds,
        timeout_seconds=args.timeout_seconds,
        rate_limit_backoff_seconds=args.rate_limit_backoff_seconds,
        rate_limit_retries=args.rate_limit_retries,
        max_input_files=args.max_input_files,
    )


if __name__ == "__main__":
    raise SystemExit(main())
