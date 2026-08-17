"""Build a full-library object inventory CSV from canonical Panorama facts.

Reads objects.json and columns.json under a facts directory and emits a
schema-grouped inventory of every in-scope object (table/view/mview/synonym)
with field counts and object comments, for offline human judgment.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--facts-dir",
        required=True,
        help="Panorama facts directory containing objects.json and columns.json",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output CSV path (UTF-8 with BOM for Excel)",
    )
    args = parser.parse_args()

    facts_dir = Path(args.facts_dir)
    objects = json.loads(
        (facts_dir / "objects.json").read_text(encoding="utf-8")
    )
    columns = json.loads(
        (facts_dir / "columns.json").read_text(encoding="utf-8")
    )
    field_count: dict[str, int] = {}
    for row in columns:
        asset_id = str(row.get("asset_id", ""))
        field_count[asset_id] = field_count.get(asset_id, 0) + 1

    rows: list[dict[str, object]] = []
    for obj in objects:
        if not obj.get("in_panorama_scope"):
            continue
        asset_id = str(obj["asset_id"])
        rows.append(
            {
                "schema_name": str(obj["schema_name"]),
                "object_name": str(obj["object_name"]),
                "object_type": str(obj["object_type"]),
                "field_count": field_count.get(asset_id, 0),
                "object_comment": str(obj.get("object_comment") or ""),
                "is_boundary": bool(obj.get("is_boundary", False)),
                "asset_id": asset_id,
            }
        )
    rows.sort(
        key=lambda row: (
            str(row["schema_name"]),
            str(row["object_type"]),
            str(row["object_name"]),
        )
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "schema_name",
                "object_name",
                "object_type",
                "field_count",
                "object_comment",
                "is_boundary",
                "asset_id",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    by_schema: dict[str, dict[str, int]] = {}
    for row in rows:
        schema = str(row["schema_name"])
        summary = by_schema.setdefault(schema, {"TABLE": 0, "VIEW": 0, "MATERIALIZED_VIEW": 0, "SYNONYM": 0})
        summary[str(row["object_type"])] += 1
    print(f"wrote {len(rows)} objects -> {output}")
    print(f"{'schema':<20}{'TABLE':>8}{'VIEW':>8}{'MVIEW':>8}{'SYNONYM':>10}{'total':>8}")
    total = {"TABLE": 0, "VIEW": 0, "MATERIALIZED_VIEW": 0, "SYNONYM": 0}
    for schema, summary in sorted(by_schema.items()):
        row_total = sum(summary.values())
        for key in total:
            total[key] += summary[key]
        print(
            f"{schema:<20}{summary['TABLE']:>8}{summary['VIEW']:>8}"
            f"{summary['MATERIALIZED_VIEW']:>8}{summary['SYNONYM']:>10}{row_total:>8}"
        )
    print(f"{'TOTAL':<20}{total['TABLE']:>8}{total['VIEW']:>8}"
          f"{total['MATERIALIZED_VIEW']:>8}{total['SYNONYM']:>10}{len(rows):>8}")


if __name__ == "__main__":
    main()
