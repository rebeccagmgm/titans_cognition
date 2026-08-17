"""Retry failed ODS probes and record the actual error reason.

Batch probes may fail with "Table not found in metadata MCP" either because
the entity truly has no metadata detail, or because of transient
rate-limit/timeout issues. This script re-probes every ERROR row from
ods-source-mapping.csv, records the stderr message, and distinguishes:

- RETRY-OK        re-probe succeeded (has upstream/tasks)
- NOT-FOUND       metadata MCP explicitly says table not found
- OTHER-ERROR     transient/other failure (message recorded)

Output CSV columns:
    ods_table, task_id, upstream_all, outcome, error_msg

Usage:
    python scripts/szdata_retry_ods_probe.py \
        --probe output/titans-collection-20260815/data/ods-source-mapping.csv \
        --output output/titans-collection-20260815/data/ods-retry.csv \
        --sleep-ms 400
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import time
from pathlib import Path


def _probe(db: str, table: str) -> tuple[str, str, str]:
    result = subprocess.run(
        [
            "opencli",
            "szdata",
            "table",
            "--db",
            db,
            "--table",
            table,
            "--view",
            "summary",
            "-f",
            "json",
        ],
        capture_output=True,
        shell=True,
    )
    err = result.stderr.decode("utf-8", errors="replace").strip()
    if result.returncode != 0:
        return "NOT-FOUND" if "not found" in err.lower() else "OTHER-ERROR", "", err[-300:]
    try:
        payload = json.loads(result.stdout.decode("utf-8"))
    except json.JSONDecodeError:
        return "OTHER-ERROR", "", "json decode failed: " + result.stdout.decode("utf-8", errors="replace")[:200]
    if not payload:
        return "OTHER-ERROR", "", "empty payload"
    item = payload[0]
    tasks = item.get("tasks") or []
    upstream = item.get("lineage", {}).get("upstream") or []
    return (
        "RETRY-OK",
        (tasks[0].get("taskId", "") if tasks else ""),
        "|".join(str(u.get("table", "")) for u in upstream),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--db", default="odata_n_tit")
    parser.add_argument("--sleep-ms", type=int, default=400)
    args = parser.parse_args()

    with open(args.probe, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    targets = [r["ods_table"] for r in rows if r.get("probe_status") == "ERROR"]
    print(f"retry targets: {len(targets)}")

    output = Path(args.output)
    done: set[str] = set()
    if output.exists():
        with output.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                done.add(str(row["ods_table"]))
    pending = [t for t in targets if t not in done]
    print(f"pending: {len(pending)}")

    with output.open("a" if output.exists() else "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ods_table", "task_id", "upstream_all", "outcome", "error_msg"])
        if not output.exists() or output.stat().st_size == 0:
            writer.writeheader()
        for index, table in enumerate(pending, 1):
            outcome, task_id, extra = _probe(args.db, table)
            writer.writerow(
                {
                    "ods_table": table,
                    "task_id": task_id,
                    "upstream_all": extra if outcome == "RETRY-OK" else "",
                    "outcome": outcome,
                    "error_msg": "" if outcome == "RETRY-OK" else extra,
                }
            )
            if index % 25 == 0 or index == len(pending):
                print(f"progress {index}/{len(pending)}: {table} -> {outcome}")
            if index < len(pending):
                time.sleep(args.sleep_ms / 1000)
    print(f"done -> {output}")


if __name__ == "__main__":
    main()
