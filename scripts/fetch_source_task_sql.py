# -*- coding: utf-8 -*-
"""Collect SQL for the source-layer task set with cache reuse and bounded retries.

The source mapping contains one row per ODS table, so the collection unit here
is a unique numeric ``task_id``. Existing task-sql snapshots are reused first;
only tasks without a non-empty snapshot are sent to SZData. The final output
has one normalized ``<task_id>.sql`` file per task plus a JSONL manifest with
source, status, size, and SHA-256 evidence.

Usage::

    python scripts/fetch_source_task_sql.py \
      --source-map output/titans-collection-20260815/data/ods-source-mapping-final-v2.csv \
      --output-dir output/source-layer-task-sql-20260817 \
      --workers 3 --retry-count 1
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


TASK_SQL_RE = re.compile(r"^tasksql-(?P<task_id>\d+)-.*\.txt$", re.IGNORECASE)
RATE_RE = re.compile(r"429|rate.?limit|too many|限流|频繁", re.IGNORECASE)
AUTH_RE = re.compile(r"401|403|unauthori[sz]ed|forbidden|permission|权限", re.IGNORECASE)
NOT_FOUND_RE = re.compile(r"not found|不存在|找不到", re.IGNORECASE)


@dataclass(frozen=True)
class Candidate:
    path: Path
    kind: str
    priority: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-map", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--retry-count", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_task_rows(source_map: Path) -> dict[str, list[str]]:
    by_task: dict[str, list[str]] = {}
    with source_map.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            task_id = str(row.get("task_id") or "").strip()
            if not task_id.isdigit():
                continue
            table = str(row.get("ods_table") or "").strip()
            by_task.setdefault(task_id, [])
            if table and table not in by_task[task_id]:
                by_task[task_id].append(table)
    return dict(sorted(by_task.items(), key=lambda item: int(item[0])))


def files_in(directory: Path, pattern: str) -> Iterable[Path]:
    if not directory.exists():
        return []
    return (path for path in directory.glob(pattern) if path.is_file())


def candidates_for(task_id: str, project_root: Path, output_dir: Path) -> list[Candidate]:
    roots = [
        (output_dir / "raw", "RUN_RAW", 300),
        (
            project_root / "machine-facts/registry/source-layer/special-7/task-sql-files",
            "SPECIAL_EVIDENCE",
            250,
        ),
        (project_root / ".evidence-cache", "EVIDENCE_CACHE", 200),
        (
            project_root / "output/titans-collection-20260815/data/downstream-tasks-sql",
            "DOWNSTREAM_SQL",
            100,
        ),
    ]
    found: list[Candidate] = []
    for directory, kind, priority in roots:
        if kind == "SPECIAL_EVIDENCE":
            paths = files_in(directory, f"{task_id}.query.sql")
        else:
            paths = files_in(directory, f"tasksql-{task_id}-*.txt")
        for path in paths:
            try:
                if path.stat().st_size > 0:
                    found.append(Candidate(path=path, kind=kind, priority=priority))
            except OSError:
                continue
    return found


def choose_candidate(candidates: list[Candidate]) -> Candidate | None:
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item.priority, item.path.stat().st_mtime))


def classify_failure(returncode: int, output: str, new_files: list[Path]) -> str:
    if returncode == 0 and new_files:
        return "FETCHED"
    if RATE_RE.search(output):
        return "RATE_LIMIT"
    if AUTH_RE.search(output):
        return "AUTH_OR_PERMISSION"
    if NOT_FOUND_RE.search(output):
        return "NOT_FOUND"
    if returncode == 0:
        return "EMPTY_RESPONSE"
    return "ERROR"


def fetch_one(task_id: str, raw_dir: Path, timeout_seconds: int) -> dict[str, object]:
    before = {path.resolve() for path in files_in(raw_dir, f"tasksql-{task_id}-*.txt")}
    command = [
        "opencli",
        "szdata",
        "task-sql",
        "--task-id",
        task_id,
        "--save-to",
        str(raw_dir),
        "--full",
        "true",
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=True,
            timeout=timeout_seconds,
            check=False,
        )
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        returncode = int(result.returncode)
    except subprocess.TimeoutExpired:
        return {"task_id": task_id, "status": "TIMEOUT", "returncode": None}
    except OSError:
        return {"task_id": task_id, "status": "LAUNCH_ERROR", "returncode": None}

    after = [path for path in files_in(raw_dir, f"tasksql-{task_id}-*.txt") if path.resolve() not in before]
    status = classify_failure(returncode, output, after)
    return {
        "task_id": task_id,
        "status": status,
        "returncode": returncode,
        "raw_path": str(max(after, key=lambda item: item.stat().st_mtime)) if after else "",
    }


def fetch_batch(task_ids: list[str], raw_dir: Path, workers: int, timeout_seconds: int) -> list[dict[str, object]]:
    if not task_ids:
        return []
    results: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(fetch_one, task_id, raw_dir, timeout_seconds): task_id
            for task_id in task_ids
        }
        for index, future in enumerate(as_completed(futures), 1):
            task_id = futures[future]
            try:
                result = future.result()
            except Exception:
                result = {"task_id": task_id, "status": "WORKER_ERROR", "returncode": None}
            results.append(result)
            if index % 20 == 0 or index == len(task_ids):
                print(f"fetch progress {index}/{len(task_ids)}", flush=True)
    return results


def retryable(status: str) -> bool:
    return status in {"RATE_LIMIT", "ERROR", "EMPTY_RESPONSE", "TIMEOUT", "LAUNCH_ERROR", "WORKER_ERROR"}


def main() -> int:
    args = parse_args()
    if args.workers < 1 or args.retry_count < 0:
        raise SystemExit("--workers must be >= 1 and --retry-count must be >= 0")

    project_root = Path.cwd().resolve()
    source_map = args.source_map.resolve()
    output_dir = args.output_dir.resolve()
    raw_dir = output_dir / "raw"
    sql_dir = output_dir / "sql"
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    sql_dir.mkdir(parents=True, exist_ok=True)

    by_task = read_task_rows(source_map)
    task_ids = list(by_task)
    selected: dict[str, Candidate] = {}
    missing: list[str] = []
    for task_id in task_ids:
        candidate = choose_candidate(candidates_for(task_id, project_root, output_dir))
        if candidate is None:
            missing.append(task_id)
        else:
            selected[task_id] = candidate

    print(f"source tasks: {len(task_ids)}; reusable SQL: {len(selected)}; missing: {len(missing)}")

    fetch_results: dict[str, dict[str, object]] = {}
    pending = missing
    for attempt in range(args.retry_count + 1):
        if not pending:
            break
        workers = args.workers if attempt == 0 else 1
        if attempt:
            time.sleep(1.0)
        batch = fetch_batch(pending, raw_dir, workers, args.timeout_seconds)
        for result in batch:
            fetch_results[str(result["task_id"])] = result
        succeeded = [
            str(result["task_id"])
            for result in batch
            if result.get("status") == "FETCHED" and result.get("raw_path")
        ]
        for task_id in succeeded:
            candidate = choose_candidate(candidates_for(task_id, project_root, output_dir))
            if candidate is not None:
                selected[task_id] = candidate
        pending = [
            task_id
            for task_id in pending
            if task_id not in selected
            and retryable(str(fetch_results.get(task_id, {}).get("status", "ERROR")))
        ]
        print(
            f"attempt {attempt + 1}: fetched={len(succeeded)}; retryable_remaining={len(pending)}",
            flush=True,
        )

    manifest_rows: list[dict[str, object]] = []
    for task_id in task_ids:
        candidate = selected.get(task_id)
        fetch_result = fetch_results.get(task_id, {})
        status = str(fetch_result.get("status") or "") if task_id in fetch_results else ""
        if candidate is not None:
            normalized = sql_dir / f"{task_id}.sql"
            shutil.copyfile(candidate.path, normalized)
            normalized_hash = sha256_file(normalized)
            if candidate.kind == "RUN_RAW":
                status = "FETCHED" if status in {"", "FETCHED"} else status
            elif not status:
                status = f"REUSED_{candidate.kind}"
            manifest_rows.append(
                {
                    "task_id": task_id,
                    "source_tables": ";".join(by_task[task_id]),
                    "source_table_count": len(by_task[task_id]),
                    "status": status,
                    "source_kind": candidate.kind,
                    "source_path": str(candidate.path),
                    "normalized_path": str(normalized),
                    "bytes": normalized.stat().st_size,
                    "sha256": normalized_hash,
                    "collected_at": utc_now(),
                }
            )
        else:
            manifest_rows.append(
                {
                    "task_id": task_id,
                    "source_tables": ";".join(by_task[task_id]),
                    "source_table_count": len(by_task[task_id]),
                    "status": status or "MISSING",
                    "source_kind": "",
                    "source_path": "",
                    "normalized_path": "",
                    "bytes": 0,
                    "sha256": "",
                    "collected_at": utc_now(),
                }
            )

    manifest_path = output_dir / "source-task-sql-manifest.jsonl"
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        for row in manifest_rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    counts: dict[str, int] = {}
    for row in manifest_rows:
        key = str(row["status"])
        counts[key] = counts.get(key, 0) + 1
    summary = {
        "source_map": str(source_map),
        "source_task_count": len(task_ids),
        "manifest": str(manifest_path),
        "sql_dir": str(sql_dir),
        "status_counts": dict(sorted(counts.items())),
        "generated_at": utc_now(),
    }
    summary_path = output_dir / "source-task-sql-summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if counts.get("MISSING", 0) == 0 and not any(
        key in counts for key in {"RATE_LIMIT", "ERROR", "EMPTY_RESPONSE", "TIMEOUT", "LAUNCH_ERROR", "WORKER_ERROR"}
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
