# -*- coding: utf-8 -*-
"""查看下游探测抽样结果。"""
import csv
from collections import Counter

rows = list(csv.DictReader(open("output/titans-collection-20260815/data/downstream-odata.csv", encoding="utf-8-sig")))
down = [r for r in rows if r["downstream_name"]]
print("行数:", len(rows), "有下游:", len(down))
print("前缀分布:", dict(Counter(r["downstream_prefix"] or "(无)" for r in down)))
print("类型分布:", dict(Counter(r["downstream_type"] for r in down)))
print("--- 下游明细 ---")
for r in down[:40]:
    print(f"{r['upstream_table']:28s} -> {r['downstream_type']:18s} {r['downstream_name']}")
