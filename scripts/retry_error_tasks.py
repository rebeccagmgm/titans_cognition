# -*- coding: utf-8 -*-
"""清理 tasks CSV 中的 ERROR 行，供 fetch_downstream_sql.py tasks 重跑。

用法: python scripts/retry_error_tasks.py   # 先删 ERROR 行
      python scripts/fetch_downstream_sql.py tasks   # 重查（断点续跑）
      python scripts/fetch_downstream_sql.py sql      # 补拉新增任务的 SQL
"""
import csv

CSV = "output/titans-collection-20260815/data/downstream-tables-tasks.csv"

rows = list(csv.DictReader(open(CSV, encoding="utf-8-sig")))
err = [r for r in rows if r["probe_status"] in ("ERROR", "PARSE_ERR")]
keep = [r for r in rows if r["probe_status"] not in ("ERROR", "PARSE_ERR")]
with open(CSV, "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    for r in keep:
        w.writerow(r)
print(f"删除 ERROR 行 {len(err)} 条，保留 {len(keep)} 条 -> 重跑 tasks 阶段即可")
