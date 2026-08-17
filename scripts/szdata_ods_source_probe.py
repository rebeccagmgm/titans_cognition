"""Probe each SZData ODS table for its production task and upstream source.

Calls `opencli szdata table --view summary` per table (byte-safe subprocess)
and extracts:

- production task id/name (tasks)
- upstream source tables (lineage.upstream), preferring TITANS_* sources

Output CSV columns:
    ods_table, task_id, task_name, source_schema, source_table,
    upstream_all, upstream_type, probe_status

Supports resume: rows already present in the output CSV are skipped, so a
long run can be restarted after a network or rate-limit interruption.

Usage:
    python scripts/szdata_ods_source_probe.py \
        --ods-tables output/titans-collection-20260815/data/odata_n_tit_tables.json \
        --db odata_n_tit \
        --output output/titans-collection-20260815/data/ods-source-mapping.csv \
        --sleep-ms 300
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import time
from pathlib import Path


def _probe_table(db: str, table: str) -> dict[str, object]:
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
    if result.returncode != 0:
        return {"probe_status": "ERROR", "error": result.stderr.decode("utf-8", errors="replace")[-200:]}
    payload = json.loads(result.stdout.decode("utf-8"))
    if not payload:
        return {"probe_status": "EMPTY"}
    item = payload[0]
    tasks = item.get("tasks") or []
    upstream = item.get("lineage", {}).get("upstream") or []
    return {
        "task_id": tasks[0].get("taskId", "") if tasks else "",
        "task_name": tasks[0].get("taskName", "") if tasks else "",
        "upstream_all": [str(u.get("table", "")) for u in upstream],
        "upstream_types": [str(u.get("typeName", "")) for u in upstream],
        "probe_status": "SUCCESS",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ods-tables", required=True, help="ODS inventory JSON from szdata_table_inventory.py")
    parser.add_argument("--db", required=True, help="SZData database, e.g. odata_n_tit")
    parser.add_argument("--output", required=True, help="Output CSV path (resume-supported)")
    parser.add_argument("--sleep-ms", type=int, default=300, help="Delay between probes")
    parser.add_argument("--limit", type=int, default=0, help="0=all, else max tables to probe")
    args = parser.parse_args()

    ods = json.loads(Path(args.ods_tables).read_text(encoding="utf-8"))
    names = [str(row["name"]) for row in ods]
    if args.limit:
        names = names[: args.limit]

    output = Path(args.output)
    done: set[str] = set()
    if output.exists():
        with output.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                done.add(str(row["ods_table"]))
    pending = [name for name in names if name not in done]
    print(f"total={len(names)} done={len(done)} pending={len(pending)}")

    with output.open("a" if output.exists() else "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "ods_table",
                "task_id",
                "task_name",
                "source_schema",
                "source_table",
                "upstream_all",
                "upstream_type",
                "probe_status",
            ],
        )
        if not output.exists() or output.stat().st_size == 0:
            writer.writeheader()
        for index, name in enumerate(pending, 1):
            info = _probe_table(args.db, name)
            upstream = info.get("upstream_all") or []
            source_schema = ""
            source_table = ""
            for entry in upstream:
                if entry.upper().startswith("TITANS_"):
                    parts = entry.split(".", 1)
                    source_schema = parts[0]
                    source_table = parts[1] if len(parts) > 1 else ""
                    break
            writer.writerow(
                {
                    "ods_table": name,
                    "task_id": info.get("task_id", ""),
                    "task_name": info.get("task_name", ""),
                    "source_schema": source_schema,
                    "source_table": source_table,
                    "upstream_all": "|".join(upstream),
                    "upstream_type": "|".join(info.get("upstream_types") or []),
                    "probe_status": info.get("probe_status", "UNKNOWN"),
                }
            )
            if index % 25 == 0 or index == len(pending):
                print(f"progress {index}/{len(pending)}: {name} -> {source_schema}.{source_table}")
            if index < len(pending):
                time.sleep(args.sleep_ms / 1000)
    print(f"done -> {output}")


if __name__ == "__main__":
    main()
