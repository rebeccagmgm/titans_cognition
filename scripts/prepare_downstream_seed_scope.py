# -*- coding: utf-8 -*-
"""整理已有平台下游清单为可审计的继续下钻种子表。

本脚本只读取仓库已有 CSV 和 Task Machine Facts，不调用 szdata，不新增血缘关系。
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "output" / "titans-collection-20260815" / "data"
OUT = ROOT / "output" / "downstream-dive-20260818"
FACT_TASKS = ROOT / "machine-facts" / "registry" / "tasks"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def unique_join(values: list[str]) -> str:
    return "|".join(sorted({value for value in values if value}))


def build_fact_write_index() -> tuple[dict[str, set[str]], dict[str, set[str]], int, int]:
    assets_by_tail: dict[str, set[str]] = defaultdict(set)
    tasks_by_tail: dict[str, set[str]] = defaultdict(set)
    task_count = 0
    io_count = 0
    for task_dir in sorted(FACT_TASKS.iterdir()):
        if not task_dir.is_dir():
            continue
        io_path = task_dir / "bundle" / "dataset-io.jsonl"
        if not io_path.exists():
            continue
        task_count += 1
        for line in io_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            io_count += 1
            if str(record.get("direction", "")).upper() != "WRITE":
                continue
            asset = str(record.get("physical_dataset") or "").strip()
            if not asset:
                continue
            tail = asset.rsplit(".", 1)[-1].lower()
            assets_by_tail[tail].add(asset)
            task_id = str(record.get("task_id") or task_dir.name)
            tasks_by_tail[tail].add(task_id)
    return assets_by_tail, tasks_by_tail, task_count, io_count


def main() -> None:
    odata = read_csv(DATA / "downstream-odata.csv")
    dpl = read_csv(DATA / "downstream-dpl.csv")
    task_rows = read_csv(DATA / "downstream-tables-tasks.csv")

    relation_index: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {
            "sources": set(),
            "upstream_tables": set(),
            "upstream_guids": set(),
            "downstream_types": set(),
        }
    )
    relation_counts: Counter[str] = Counter()
    for source, rows in (("odata", odata), ("dpl", dpl)):
        for row in rows:
            guid = row.get("downstream_guid", "").strip()
            if not guid:
                continue
            if not row.get("downstream_name", "").strip():
                continue
            info = relation_index[guid]
            info["sources"].add(source)
            info["upstream_tables"].add(row.get("upstream_table", "").strip())
            info["upstream_guids"].add(row.get("guid", "").strip())
            info["downstream_types"].add(row.get("downstream_type", "").strip())
            relation_counts[guid] += 1

    assets_by_tail, tasks_by_tail, fact_task_count, fact_io_count = build_fact_write_index()
    output_rows: list[dict[str, str]] = []
    for row in task_rows:
        guid = row.get("downstream_guid", "").strip()
        name = row.get("downstream_name", "").strip()
        db_name = row.get("db_name", "").strip()
        db_lower = db_name.lower()
        info = relation_index.get(guid, {})
        sources = info.get("sources", set())
        if db_lower == "dm_otc_n":
            scope_status = "ALREADY_DM_OTC_N_SEED"
        elif db_lower.startswith("dm_"):
            scope_status = "DM_OTHER_SEED"
        elif not db_name or db_name == "-":
            scope_status = "DB_UNKNOWN"
        else:
            scope_status = "NON_DM_SEED_CONTINUE"

        tail = name.lower()
        matched_assets = assets_by_tail.get(tail, set())
        platform_files = ["downstream-tables-tasks.csv"]
        if "odata" in sources:
            platform_files.insert(0, "downstream-odata.csv")
        if "dpl" in sources:
            platform_files.insert(0, "downstream-dpl.csv")
        platform_evidence = "|".join(platform_files)
        output_rows.append(
            {
                "seed_guid": guid,
                "seed_table_name": name,
                "seed_db_name": db_name,
                "seed_task_ids": row.get("horae_task_id", "").strip(),
                "seed_task_labels": row.get("horae_task_label", "").strip().replace("\n", " "),
                "platform_sources": unique_join(list(sources)),
                "platform_upstream_tables": unique_join(list(info.get("upstream_tables", set()))),
                "platform_upstream_guids": unique_join(list(info.get("upstream_guids", set()))),
                "platform_relation_count": str(relation_counts.get(guid, 0)),
                "downstream_type": unique_join(list(info.get("downstream_types", set()))),
                "table_detail_status": row.get("probe_status", "").strip(),
                "fact_write_match": "MATCHED" if matched_assets else "NOT_FOUND",
                "fact_write_assets": unique_join(list(matched_assets)),
                "fact_write_task_ids": unique_join(list(tasks_by_tail.get(tail, set()))),
                "scope_status": scope_status,
                "platform_evidence": platform_evidence,
                "fact_evidence": "machine-facts/registry/tasks/*/bundle/dataset-io.jsonl",
            }
        )

    output_rows.sort(key=lambda item: (item["scope_status"], item["seed_db_name"].lower(), item["seed_table_name"].lower(), item["seed_guid"]))
    OUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUT / "seed-scope.csv"
    fieldnames = list(output_rows[0].keys()) if output_rows else []
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    scope_counts = Counter(row["scope_status"] for row in output_rows)
    source_counts = Counter(row["platform_sources"] or "UNMATCHED" for row in output_rows)
    fact_counts = Counter(row["fact_write_match"] for row in output_rows)
    manifest = {
        "schema_version": "downstream-seed-scope-v1",
        "generated_by": "scripts/prepare_downstream_seed_scope.py",
        "szdata_called": False,
        "inputs": {
            "downstream_odata_rows": len(odata),
            "downstream_dpl_rows": len(dpl),
            "downstream_tables_tasks_rows": len(task_rows),
            "fact_task_directories": fact_task_count,
            "fact_dataset_io_rows": fact_io_count,
        },
        "outputs": {
            "seed_row_count": len(output_rows),
            "scope_status_counts": dict(scope_counts),
            "platform_source_counts": dict(source_counts),
            "fact_write_match_counts": dict(fact_counts),
        },
        "boundary": {
            "seed_identity": "downstream_guid",
            "dm_target": "dm_otc_n",
            "previous_11_seed_run_is_authoritative": False,
            "task_fact_is_auxiliary_validation": True,
        },
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
