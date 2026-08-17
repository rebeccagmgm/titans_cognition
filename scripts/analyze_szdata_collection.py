"""Cross-reference TITANS full-library objects against SZData ODS layer tables.

Maps `odata_n_tit` (TITANS ODS collection layer) table names back to the
canonical TITANS object inventory and writes:

- collected-mapped.csv   : ODS tables that map to a TITANS object
- collected-unmapped.csv : ODS tables with no TITANS match (review manually)
- collection-summary.txt : per-schema counts and mapping statistics

Name normalization: strip known prefixes (d_, n_, otc_o_), strip known
suffixes (_p, _pb, _his variants are kept), uppercase, then match.

Usage:
    python scripts/analyze_szdata_collection.py \
        --titans-inventory output/full-library-table-inventory-20260815/full-library-objects.csv \
        --ods-tables output/titans-collection-20260815/data/odata_n_tit_tables.json \
        --output output/titans-collection-20260815/data/collection-analysis
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

_MULTI_PREFIXES = ("TIT_", "OTC_O_", "EMAIL_", "XB_", "D_", "V_", "N_", "A_", "B_", "F_", "G_", "K_", "M_", "O_", "P_", "R_", "T_", "W_", "E_", "L_")
_SUFFIXES = ("_P", "_PB", "_S", "_H15RISK", "_TMP", "_ALL", "_BAK", "_HIS")


def _normalize_ods_name(name: str) -> tuple[str, str | None]:
    upper = name.upper()
    matched_prefix = None
    for prefix in _MULTI_PREFIXES:
        if upper.startswith(prefix):
            upper = upper[len(prefix):]
            matched_prefix = prefix.rstrip("_")
            break
    for suffix in _SUFFIXES:
        if upper.endswith(suffix):
            upper = upper[: -len(suffix)]
            break
    return upper, matched_prefix


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--titans-inventory", required=True)
    parser.add_argument("--ods-tables", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    titans = []
    with Path(args.titans_inventory).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            row["_key"] = str(row["object_name"]).upper()
            row["_schema_key"] = f"{row['schema_name']}.{row['object_name']}".upper()
            titans.append(row)
    by_name: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in titans:
        by_name[str(row["_key"])].append(row)

    ods = json.loads(Path(args.ods_tables).read_text(encoding="utf-8"))

    mapped: list[dict[str, object]] = []
    unmapped: list[dict[str, object]] = []
    for row in ods:
        ods_name = str(row["name"])
        normalized, prefix = _normalize_ods_name(ods_name)
        candidates = by_name.get(normalized, [])
        if not candidates:
            unmapped.append(
                {
                    "ods_table": ods_name,
                    "normalized": normalized,
                    "comment": row.get("comment", ""),
                    "qualifiedName": row.get("qualifiedName", ""),
                }
            )
            continue
        for cand in candidates:
            mapped.append(
                {
                    "ods_table": ods_name,
                    "match_type": "EXACT" if prefix is None else f"PREFIX:{prefix}",
                    "titans_schema": cand["schema_name"],
                    "titans_object": cand["object_name"],
                    "object_type": cand["object_type"],
                    "field_count": cand["field_count"],
                    "ods_comment": row.get("comment", ""),
                    "titans_comment": cand["object_comment"],
                    "guid": row.get("guid", ""),
                }
            )

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    mapped_path = output / "collected-mapped.csv"
    with mapped_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "ods_table",
                "match_type",
                "titans_schema",
                "titans_object",
                "object_type",
                "field_count",
                "ods_comment",
                "titans_comment",
                "guid",
            ],
        )
        writer.writeheader()
        writer.writerows(mapped)
    unmapped_path = output / "collected-unmapped.csv"
    with unmapped_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["ods_table", "normalized", "comment", "qualifiedName"],
        )
        writer.writeheader()
        writer.writerows(unmapped)

    mapped_schemas = Counter(row["titans_schema"] for row in mapped)
    summary_path = output / "collection-summary.txt"
    with summary_path.open("w", encoding="utf-8") as handle:
        handle.write(
            f"ODS tables total       : {len(ods)}\n"
            f"Mapped to TITANS       : {len(mapped)} ({len({r['ods_table'] for r in mapped})} unique ODS tables)\n"
            f"Unmapped               : {len(unmapped)}\n"
            f"Mapped TITANS objects  : {len({r['titans_schema'] + '.' + r['titans_object'] for r in mapped})}\n\n"
        )
        handle.write("By TITANS schema (mapped):\n")
        for schema, count in mapped_schemas.most_common():
            handle.write(f"  {schema:<24}{count:>6}\n")
        handle.write("\nUnmapped ODS tables:\n")
        for row in sorted(unmapped, key=lambda r: str(r["ods_table"])):
            handle.write(f"  {row['ods_table']:<60}-> {row['normalized']}\n")
    print(mapped_path.read_text(encoding="utf-8-sig").splitlines()[0])
    print(f"mapped={len(mapped)} unmapped={len(unmapped)}")
    print(mapped_schemas.most_common())


if __name__ == "__main__":
    main()
