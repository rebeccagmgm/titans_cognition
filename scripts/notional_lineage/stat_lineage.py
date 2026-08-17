# -*- coding: utf-8 -*-
"""统计 model-notional-lineage.json 的命中与 unresolved 分布"""
import json
from collections import Counter

d = json.load(open(
    r"e:\02_area\股衍数据-数据cookbook\titans-cognition\output\notional-lineage-20260816\model-notional-lineage.json",
    encoding="utf-8"))

errs = [r for r in d if "error" in r]
print(f"记录数: {len(d)}  报错记录: {len(errs)}")
for r in errs:
    print(f"  ERR {r.get('sql_file')} | {str(r.get('error'))[:150]}")

tasks = [r for r in d if "matched_columns" in r]
print(f"命中任务: {len(tasks)}")
col_total = 0
un_total = 0
for r in tasks:
    cols = r["matched_columns"]
    col_total += len(cols)
    unresolved = [m for m in cols
                  if not m.get("hops") or not m["hops"][0].get("terminal")
                  or m["hops"][0]["terminal"] == "unresolved"]
    un_total += len(unresolved)
    flag = "  <== unresolved" if unresolved else ""
    print(f"  {r['target_table']} ({r['sql_file']}) hit={len(cols)} unresolved={len(unresolved)}{flag}")
    for m in unresolved:
        term = m["hops"][0]["terminal"] if m.get("hops") and m["hops"][0].get("terminal") else "(无hop)"
        exprs = m["hops"][0]["expr"] if m.get("hops") else "(无hop)"
        print(f"      ? {m['output']} | origins={','.join(m['origins'][:4])} | term={term} | expr={str(exprs)[:80]}")

print(f"\n合计: {col_total} 列命中, unresolved {un_total} 列")

# 哪些输出列名重复出现（可能对应多行/多次出现的列名锚定问题）
out_counter = Counter()
for r in tasks:
    for m in r["matched_columns"]:
        out_counter[m["output"].upper()] += 1
print("\n高频输出列名:")
for name, cnt in out_counter.most_common(15):
    print(f"  {name}: {cnt}")
