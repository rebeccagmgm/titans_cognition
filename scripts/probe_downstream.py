# -*- coding: utf-8 -*-
"""探测贴源层下一层：odata_n_tit / dpl 表的直接下游消费方。

调用 opencli szdata table-lineage --guid <guid> -f json，提取 direction=DOWNSTREAM 节点，
汇总下游表清单（名称/类型），支持断点续跑与 --limit 抽样。

Usage:
    python scripts/probe_downstream.py \
        --tables output/titans-collection-20260815/data/odata_n_tit_tables.json \
        --output output/titans-collection-20260815/data/downstream-odata.csv \
        --limit 5
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import time
from pathlib import Path


def fetch_lineage(guid: str) -> list[dict]:
    r = subprocess.run(
        ["opencli", "szdata", "table-lineage", "--guid", guid, "-f", "json"],
        capture_output=True, shell=True,
    )
    if r.returncode != 0:
        return []
    try:
        return json.loads(r.stdout.decode("utf-8"))
    except Exception:
        return []


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tables", required=True, help="输入清单 JSON（含 name/guid）")
    parser.add_argument("--output", required=True, help="输出 CSV（断点续跑）")
    parser.add_argument("--limit", type=int, default=0, help="0=全部，否则只跑前 N 张")
    parser.add_argument("--sleep-ms", type=int, default=500, help="相邻调用间隔")
    parser.add_argument("--name-prefix", default="", help="只探测名字以此前缀开头的表（如 tit_titans_）")
    args = parser.parse_args()

    tables = json.loads(Path(args.tables).read_text(encoding="utf-8"))
    # 去重（同名多环境只留第一个 guid）
    seen: dict[str, str] = {}
    for t in tables:
        name = str(t.get("name", ""))
        if args.name_prefix and not name.startswith(args.name_prefix):
            continue
        if name and name not in seen and t.get("guid"):
            seen[name] = str(t["guid"])
    names = list(seen.keys())
    if args.limit:
        names = names[: args.limit]
    print(f"total={len(seen)} limit={args.limit} run={len(names)}")

    output = Path(args.output)
    done: set[str] = set()
    if output.exists():
        with output.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                done.add(str(row["upstream_table"]))
    pending = [n for n in names if n not in done]
    print(f"done={len(done)} pending={len(pending)}")

    with output.open("a" if output.exists() else "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "upstream_table", "guid", "downstream_name", "downstream_type",
                "downstream_guid", "downstream_prefix", "probe_status",
            ],
        )
        if not output.exists() or output.stat().st_size == 0:
            writer.writeheader()
        for i, name in enumerate(pending, 1):
            guid = seen[name]
            nodes = fetch_lineage(guid)
            down = [n for n in nodes if n.get("direction") == "DOWNSTREAM"]
            status = "SUCCESS" if nodes else "EMPTY"
            if not down:
                writer.writerow({"upstream_table": name, "guid": guid,
                                 "downstream_name": "", "downstream_type": "",
                                 "downstream_guid": "", "downstream_prefix": "", "probe_status": status})
            else:
                for n in down:
                    dname = str(n.get("name", ""))
                    writer.writerow({
                        "upstream_table": name, "guid": guid,
                        "downstream_name": dname,
                        "downstream_type": str(n.get("typeName", "")),
                        "downstream_guid": str(n.get("id", "")),
                        "downstream_prefix": dname.split("_")[0] if dname else "",
                        "probe_status": status,
                    })
            if i % 20 == 0 or i == len(pending):
                print(f"progress {i}/{len(pending)}: {name} -> downstream {len(down)}", flush=True)
            if i < len(pending):
                time.sleep(args.sleep_ms / 1000)
    print(f"done -> {output}")


if __name__ == "__main__":
    main()
