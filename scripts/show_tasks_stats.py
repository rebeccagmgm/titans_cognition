# -*- coding: utf-8 -*-
"""统计 tasks 阶段结果：任务覆盖 / 状态分布 / 无任务表。"""
import csv
from collections import Counter

rows = list(csv.DictReader(open("output/titans-collection-20260815/data/downstream-tables-tasks.csv", encoding="utf-8-sig")))
print("下游表:", len(rows))
print("状态分布:", dict(Counter(r["probe_status"] for r in rows)))
print("有任务表:", sum(1 for r in rows if r["horae_task_id"]))
print("去重任务数:", len({r["horae_task_id"] for r in rows if r["horae_task_id"]}))
print("库分布:", dict(Counter(r["db_name"] for r in rows if r["db_name"]).most_common(15)))
print("--- ERROR 明细 ---")
for r in rows:
    if r["probe_status"] in ("ERROR", "PARSE_ERR"):
        print(f"{r['downstream_name']} | {r['db_name']} | {r['horae_task_label'][:80]}")
print("--- 无任务表(前 40) ---")
for r in rows:
    if r["probe_status"] == "NO_TASK":
        print(f"{(r['downstream_name'] or '').split('_')[0]:18s} {r['downstream_name']} | {r['db_name']}")
