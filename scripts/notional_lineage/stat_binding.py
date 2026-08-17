# -*- coding: utf-8 -*-
"""统计 78 列的绑定方式分布 + 汇总关键信息供报告使用"""
import io
import json
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

D = json.load(open(
    r"e:\02_area\股衍数据-数据cookbook\titans-cognition\output\notional-lineage-20260816\model-notional-lineage.json",
    encoding="utf-8"))

total = 0
dist = Counter()
per_task = []
for r in D:
    if not r.get("matched_columns"):
        continue
    n = len(r["matched_columns"])
    total += n
    tags = []
    for m in r["matched_columns"]:
        note = m.get("heuristic_note", "") or ""
        if m.get("native"):
            tag = "原生"
        elif "投影列名" in note:
            tag = "启发式·投影列名强匹配"
        elif "列名命中贴源表" in note:
            tag = "启发式·输出列名强匹配"
        elif "唯一贴源表" in note:
            tag = "启发式·唯一表同名"
        elif "多" in note or "候选" in str(m.get("candidate_tables", "")):
            tag = "候选标注(多表歧义)"
        else:
            tag = "启发式·其他"
        dist[tag] += 1
        tags.append(tag)
    per_task.append((r["target_table"], n, Counter(tags)))

print(f"总计 {total} 列, 绑定方式分布:")
for tag, c in dist.most_common():
    print(f"  {tag}: {c}")
print()
print("各任务:")
for t, n, tc in sorted(per_task):
    parts = ", ".join(f"{k}{v}" for k, v in tc.most_common())
    print(f"  {t}: {n}列 [{parts}]")
