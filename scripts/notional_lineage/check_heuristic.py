# -*- coding: utf-8 -*-
"""检查启发式绑定质量: 每条命中的绑定方式与证据"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

d = json.load(open(
    r"e:\02_area\股衍数据-数据cookbook\titans-cognition\output\notional-lineage-20260816\model-notional-lineage.json",
    encoding="utf-8"))

for r in d:
    if "error" in r:
        print(f"X {r['sql_file']}: {r['error'][:100]}")
        continue
    if not r.get("matched_columns"):
        continue
    print(f"\n◆ {r['target_table']} ({r['sql_file']})")
    for m in r["matched_columns"]:
        tag = "原生" if m.get("native") else ("计算" if m.get("computed") else "启发式")
        note = m.get("heuristic_note", "") or ""
        dr = f" | drill={m.get('drill_path', [])}" if m.get("drill_path") else ""
        print(f"  [{tag}] {m['output']} -> {m['terminal']}")
        if note:
            print(f"       证据: {note}")
        if m.get("proj_expr") and m["proj_expr"] != m["output"]:
            print(f"       投影: {m['proj_expr'][:100]}")
