"""Merge naming-based mapping with lineage-probed source to produce the final
ODS -> TITANS source table comparison.

Inputs:
- --probe     ods-source-mapping.csv (lineage evidence, from szdata_ods_source_probe.py)
- --mapping   collected-mapped.csv   (naming inference, from analyze_szdata_collection.py)
- --unmapped  collected-unmapped.csv (naming misses, from analyze_szdata_collection.py)
- --fallback  ods-source-fallback.csv (optional; transitive/task-sql resolution
              from szdata_source_fallback.py)

Output (same directory as --probe unless --output given):
- ods-source-mapping-final.csv
    ods_table, task_id, source_schema, source_table (lineage), mapping_schema,
    mapping_table (naming), match (CONFIRM / CORRECTED / NEW / EXTERNAL / UNKNOWN),
    note
- ods-source-mapping-summary.txt

Match semantics:
- CONFIRM   lineage and naming agree on schema+table
- CORRECTED lineage gives a different schema or table than naming
- NEW       naming had no mapping but lineage found a TITANS_* source
- EXTERNAL  lineage source is not TITANS_* (external / cross-layer table)
- FALLBACK  no direct lineage; resolved via ODS-internal transit (TRANSITIVE)
            or production task SQL (TASK_SQL)
- NAMING    no lineage evidence at all; naming inference only
- UNKNOWN   probe failed or no upstream recorded

Evidence column: LINEAGE-DIRECT / LINEAGE-TRANSITIVE / TASK-SQL /
NAMING-INFERRED / NONE

Usage:
    python scripts/analyze_ods_source_mapping.py \
        --probe output/titans-collection-20260815/data/ods-source-mapping.csv \
        --mapping output/titans-collection-20260815/data/collection-analysis/collected-mapped.csv \
        --unmapped output/titans-collection-20260815/data/collection-analysis/collected-unmapped.csv \
        [--fallback output/titans-collection-20260815/data/ods-source-fallback.csv]
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", required=True)
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--unmapped", required=True)
    parser.add_argument("--fallback", default="")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    probe_dir = Path(args.probe).parent
    mapping_rows = _read_csv(Path(args.mapping))
    unmapped_rows = _read_csv(Path(args.unmapped))

    # naming map: ods_table -> list of (schema, table)
    by_name: dict[str, list[tuple[str, str]]] = {}
    for row in mapping_rows:
        by_name.setdefault(row["ods_table"], []).append((row["titans_schema"], row["titans_object"]))

    # fallback map: ods_table -> (schema, table, method)
    fb_path = Path(args.fallback) if args.fallback else None
    fb_rows = _read_csv(fb_path) if fb_path else []
    by_fallback = {
        str(row["ods_table"]): (str(row["source_schema"]), str(row["source_table"]), str(row["method"]))
        for row in fb_rows
        if row.get("source_schema")
    }

    final_rows: list[dict[str, str]] = []
    stats = {
        "CONFIRM": 0,
        "CORRECTED": 0,
        "NEW": 0,
        "EXTERNAL": 0,
        "FALLBACK": 0,
        "NAMING": 0,
        "UNKNOWN": 0,
    }
    for row in _read_csv(Path(args.probe)):
        ods = row["ods_table"]
        src_schema = row.get("source_schema", "")
        src_table = row.get("source_table", "")
        candidates = by_name.get(ods, [])
        if row.get("probe_status") != "SUCCESS":
            # metadata detail missing: fall back to naming candidates when present
            if candidates and "NOT-FOUND" in row.get("probe_status", ""):
                first = candidates[0]
                out = {
                    **row,
                    "source_schema": first[0],
                    "source_table": first[1],
                    "mapping_schema": ";".join(c[0] for c in candidates),
                    "mapping_table": ";".join(c[1] for c in candidates),
                    "match": "NAMING",
                    "evidence": "NAMING-INFERRED",
                    "note": "metadata detail missing in SZData; naming inference only",
                }
            else:
                out = {**row, "mapping_schema": "", "mapping_table": "", "match": "UNKNOWN", "evidence": "NONE", "note": row.get("probe_status", "")}
        elif not src_schema:
            fb = by_fallback.get(ods)
            if fb and fb[0]:
                out = {
                    **row,
                    "source_schema": fb[0],
                    "source_table": fb[1],
                    "mapping_schema": ";".join(c[0] for c in candidates),
                    "mapping_table": ";".join(c[1] for c in candidates),
                    "match": "FALLBACK",
                    "evidence": {"TRANSITIVE": "LINEAGE-TRANSITIVE", "TASK_SQL": "TASK-SQL"}.get(fb[2], "FALLBACK-" + fb[2]),
                    "note": "resolved via " + fb[2],
                }
            elif candidates:
                first = candidates[0]
                out = {
                    **row,
                    "source_schema": first[0],
                    "source_table": first[1],
                    "mapping_schema": ";".join(c[0] for c in candidates),
                    "mapping_table": ";".join(c[1] for c in candidates),
                    "match": "NAMING",
                    "evidence": "NAMING-INFERRED",
                    "note": "no lineage/task evidence; naming inference only",
                }
            else:
                out = {
                    **row,
                    "mapping_schema": "",
                    "mapping_table": "",
                    "match": "UNKNOWN",
                    "evidence": "NONE",
                    "note": "no TITANS upstream, no naming candidate" if not candidates else "no TITANS upstream in lineage",
                }
        elif (src_schema, src_table) in candidates:
            out = {**row, "mapping_schema": src_schema, "mapping_table": src_table, "match": "CONFIRM", "evidence": "LINEAGE-DIRECT", "note": ""}
        elif candidates:
            out = {
                **row,
                "mapping_schema": ";".join(c[0] for c in candidates),
                "mapping_table": ";".join(c[1] for c in candidates),
                "match": "CORRECTED",
                "evidence": "LINEAGE-DIRECT",
                "note": "naming differs from lineage source",
            }
        else:
            out = {
                **row,
                "mapping_schema": "",
                "mapping_table": "",
                "match": "NEW",
                "evidence": "LINEAGE-DIRECT",
                "note": "naming missed, lineage found source",
            }
        stats[out["match"]] = stats.get(out["match"], 0) + 1
        final_rows.append(out)

    # naming-only rows that the probe never returned (defensive; should not happen)
    probed = {r["ods_table"] for r in _read_csv(Path(args.probe))}
    for ods, candidates in by_name.items():
        if ods not in probed:
            final_rows.append(
                {
                    "ods_table": ods,
                    "task_id": "",
                    "task_name": "",
                    "source_schema": "",
                    "source_table": "",
                    "upstream_all": "",
                    "upstream_type": "",
                    "probe_status": "MISSING",
                    "mapping_schema": ";".join(c[0] for c in candidates),
                    "mapping_table": ";".join(c[1] for c in candidates),
                    "match": "UNKNOWN",
                    "note": "not probed",
                }
            )
            stats["UNKNOWN"] += 1

    output = Path(args.output) if args.output else probe_dir / "ods-source-mapping-final.csv"
    fieldnames = [
        "ods_table",
        "task_id",
        "task_name",
        "source_schema",
        "source_table",
        "mapping_schema",
        "mapping_table",
        "match",
        "evidence",
        "upstream_all",
        "upstream_type",
        "probe_status",
        "note",
    ]
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for out in final_rows:
            writer.writerow({k: out.get(k, "") for k in fieldnames})

    summary = probe_dir / "ods-source-mapping-summary.txt"
    lines = [
        "ODS -> TITANS source mapping summary (lineage evidence)",
        f"probe rows: {len(_read_csv(Path(args.probe)))}",
    ]
    lines += [f"{key}: {value}" for key, value in stats.items()]
    if fb_rows:
        lines.append(f"fallback rows used: {len(by_fallback)}")
    n_corrected = sum(1 for r in final_rows if r["match"] == "CORRECTED")
    n_new = sum(1 for r in final_rows if r["match"] == "NEW")
    n_naming = sum(1 for r in final_rows if r["match"] == "NAMING")
    if n_corrected:
        lines.append("\nCORRECTED rows (naming != lineage):")
        lines += [
            f"  {r['ods_table']}: naming={r['mapping_schema']}.{r['mapping_table']} -> lineage={r['source_schema']}.{r['source_table']}"
            for r in final_rows
            if r["match"] == "CORRECTED"
        ]
    if n_new:
        lines.append("\nNEW rows (lineage-only):")
        lines += [
            f"  {r['ods_table']}: {r['source_schema']}.{r['source_table']}"
            for r in final_rows
            if r["match"] == "NEW"
        ]
    if n_naming:
        lines.append("\nNAMING rows (no lineage evidence):")
        lines += [
            f"  {r['ods_table']}: {r['source_schema']}.{r['source_table']}"
            for r in final_rows
            if r["match"] == "NAMING"
        ]
    summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"done -> {output}")


if __name__ == "__main__":
    main()
