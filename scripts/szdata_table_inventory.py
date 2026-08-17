"""Fetch a SZData (数综) table inventory page by page through opencli.

Runs `opencli szdata table-search` via subprocess (byte-safe, avoids
PowerShell 5.1 console-code-page corruption) and merges all pages into
one JSON file plus a compact CSV.

Usage:
    python scripts/szdata_table_inventory.py --db odata_n_tit \
        --output output/titans-collection-20260815/data/tables.json

The script keeps raw records (guid/name/comment/typeName/qualifiedName/
dbName/dataSource) so later lineage checks can reuse the GUIDs.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import time
from pathlib import Path


def _fetch_page(db: str, type_code: str, size: int, page: int) -> list[dict[str, object]]:
    result = subprocess.run(
        [
            "opencli",
            "szdata",
            "table-search",
            "--db",
            db,
            "--type",
            type_code,
            "--size",
            str(size),
            "--page",
            str(page),
            "-f",
            "json",
        ],
        capture_output=True,
        shell=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"opencli table-search failed (page {page}): "
            f"{result.stderr.decode('utf-8', errors='replace')[-500:]}"
        )
    return json.loads(result.stdout.decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="SZData database name, e.g. odata_n_tit")
    parser.add_argument("--type", default="003000", help="Metadata type code; 003000=表")
    parser.add_argument("--size", type=int, default=100, help="Rows per page")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--max-pages", type=int, default=200, help="Safety cap on pages")
    parser.add_argument("--sleep-ms", type=int, default=400, help="Delay between pages")
    args = parser.parse_args()

    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    page = 1
    while page <= args.max_pages:
        batch = _fetch_page(args.db, args.type, args.size, page)
        fresh = [row for row in batch if str(row.get("guid")) not in seen]
        rows.extend(fresh)
        seen.update(str(row.get("guid")) for row in fresh)
        print(f"page {page}: {len(batch)} rows (fresh {len(fresh)}, total {len(rows)})")
        if len(batch) < args.size or not fresh:
            break
        page += 1
        time.sleep(args.sleep_ms / 1000)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    csv_path = output.with_suffix(".csv")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "guid",
                "name",
                "comment",
                "typeName",
                "qualifiedName",
                "dbName",
                "dataSource",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "guid": row.get("guid", ""),
                    "name": row.get("name", ""),
                    "comment": row.get("comment", ""),
                    "typeName": row.get("typeName", ""),
                    "qualifiedName": row.get("qualifiedName", ""),
                    "dbName": row.get("dbName", ""),
                    "dataSource": row.get("dataSource", ""),
                }
            )
    print(f"wrote {len(rows)} rows -> {output}")
    print(f"wrote csv -> {csv_path}")


if __name__ == "__main__":
    main()
