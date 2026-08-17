# -*- coding: utf-8 -*-
"""查看下游表清单分布。"""
import csv
from collections import Counter

rows = list(csv.DictReader(open("output/titans-collection-20260815/data/downstream-tables.csv", encoding="utf-8-sig")))
print("下游表总数:", len(rows))
print("类型分布:", dict(Counter(r["downstream_type"] for r in rows)))
print("前缀分布:", dict(Counter((r["downstream_name"] or "").split("_")[0] for r in rows).most_common(20)))
print("--- 前 30 张 ---")
for r in rows[:30]:
    print(f"{r['downstream_type']:20s} {r['downstream_name']}")
