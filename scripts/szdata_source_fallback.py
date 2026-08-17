"""Resolve ODS tables whose direct lineage carries no TITANS source.

Two-step resolution:

1. TRANSITIVE: follow self-layer upstream (odata_n_tit.*) up to a table
   that already has a probed TITANS source, and inherit it.
2. TASK_SQL: for the remaining tables with a production task id, pull the
   task SQL via `opencli szdata task-sql` and extract TITANS_* tables
   referenced in FROM/JOIN clauses.

Output CSV columns:
    ods_table, source_schema, source_table, method, from_tables,
    upstream_chain, task_id

Usage:
    python scripts/szdata_source_fallback.py \
        --probe output/titans-collection-20260815/data/ods-source-mapping.csv \
        --output output/titans-collection-20260815/data/ods-source-fallback.csv \
        --sleep-ms 200
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import time
from pathlib import Path

_TITANS_RE = re.compile(
    r"(?:from|join)\s+(?P<schema>(?:TITANS|titans)_\w+)\.(?P<table>\w+)",
    re.IGNORECASE,
)


def _task_sql(task_id: str) -> str:
    result = subprocess.run(
        ["opencli", "szdata", "task-sql", "--task-id", str(task_id), "--full", "true", "-f", "json"],
        capture_output=True,
        shell=True,
    )
    if result.returncode != 0:
        return ""
    try:
        payload = json.loads(result.stdout.decode("utf-8"))
    except json.JSONDecodeError:
        return ""
    # task-sql returns a summary; the SQL body is cached locally by the adapter
    if isinstance(payload, list) and payload:
        for item in payload:
            cache = item.get("sqlCachePath") or item.get("sql_cache_path")
            if cache and Path(cache).exists():
                return Path(cache).read_text(encoding="utf-8", errors="replace")
        return json.dumps(payload, ensure_ascii=False)
    return str(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", required=True, help="ods-source-mapping.csv from szdata_ods_source_probe.py")
    parser.add_argument("--output", required=True, help="fallback CSV output path")
    parser.add_argument("--sleep-ms", type=int, default=200)
    args = parser.parse_args()

    with open(args.probe, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    # base map: ods_table -> (schema, table) from direct probes
    base = {
        str(r["ods_table"]): (str(r["source_schema"]), str(r["source_table"]))
        for r in rows
        if r.get("source_schema")
    }

    # iterative: previously resolved fallback rows join the base map
    prev = Path(args.output)
    resolved_ods: set[str] = set()
    if prev.exists():
        with prev.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("source_schema"):
                    base[str(row["ods_table"])] = (str(row["source_schema"]), str(row["source_table"]))
                    resolved_ods.add(str(row["ods_table"]))

    results: list[dict[str, str]] = []
    need_sql: list[dict[str, str]] = []
    for row in rows:
        if row.get("source_schema") or row["ods_table"] in resolved_ods:
            continue
        ods = row["ods_table"]
        chain = [p for p in (row.get("upstream_all") or "").split("|") if p]
        found: tuple[str, str] | None = None
        for entry in chain:
            # entry may be qualified (odata_n_tit.d_ref_trs_p) or bare
            bare = entry.split(".", 1)[-1] if "." in entry else entry
            if bare in base:
                found = base[bare]
                break
        if found:
            results.append(
                {
                    "ods_table": ods,
                    "source_schema": found[0],
                    "source_table": found[1],
                    "method": "TRANSITIVE",
                    "from_tables": "",
                    "upstream_chain": "|".join(chain),
                    "task_id": row.get("task_id", ""),
                }
            )
        elif row.get("task_id"):
            need_sql.append(row)

    for index, row in enumerate(need_sql, 1):
        sql_text = _task_sql(row["task_id"])
        hits = [
            f"{m.group('schema').upper()}.{m.group('table').upper()}"
            for m in _TITANS_RE.finditer(sql_text)
        ]
        unique = sorted(set(hits))
        ods = row["ods_table"]
        if unique:
            first = unique[0].split(".", 1)
            results.append(
                {
                    "ods_table": ods,
                    "source_schema": first[0],
                    "source_table": first[1],
                    "method": "TASK_SQL",
                    "from_tables": ";".join(unique),
                    "upstream_chain": "|".join(p for p in (row.get("upstream_all") or "").split("|") if p),
                    "task_id": row.get("task_id", ""),
                }
            )
        else:
            results.append(
                {
                    "ods_table": ods,
                    "source_schema": "",
                    "source_table": "",
                    "method": "STILL_UNKNOWN",
                    "from_tables": "",
                    "upstream_chain": "|".join(p for p in (row.get("upstream_all") or "").split("|") if p),
                    "task_id": row.get("task_id", ""),
                }
            )
        if index % 10 == 0 or index == len(need_sql):
            print(f"task-sql progress {index}/{len(need_sql)}: {ods} -> {results[-1]['method']}")
        if index < len(need_sql):
            time.sleep(args.sleep_ms / 1000)

    fieldnames = ["ods_table", "source_schema", "source_table", "method", "from_tables", "upstream_chain", "task_id"]
    # merge: keep previously resolved rows, override rows re-probed this round
    final_map: dict[str, dict[str, str]] = {}
    if prev.exists():
        with prev.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                final_map[str(row["ods_table"])] = {k: row.get(k, "") for k in fieldnames}
    for out in results:
        final_map[out["ods_table"]] = out
    with open(args.output, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for out in final_map.values():
            writer.writerow({k: out.get(k, "") for k in fieldnames})

    counts: dict[str, int] = {}
    for out in results:
        counts[out["method"]] = counts.get(out["method"], 0) + 1
    print(f"fallback resolved: {counts}")
    print(f"done -> {args.output}")


if __name__ == "__main__":
    main()
