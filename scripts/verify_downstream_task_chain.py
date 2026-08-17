# -*- coding: utf-8 -*-
"""验证链路：下游表 guid -> table-detail 拿 horaeTasks。"""
import json
import subprocess


def run(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, shell=True)
    return r.stdout.decode("utf-8", errors="replace")


# 1) 从 d_trd_otc_trade 的血缘里拿 dtl_trd_jour_income_day 的 guid
out = run(["opencli", "szdata", "table-lineage", "--guid", "015482a7-341a-4c58-b53f-f0b43f9178e9", "-f", "json"])
nodes = json.loads(out)
target = None
for n in nodes:
    if n.get("name") == "dtl_trd_jour_income_day":
        target = n
        break
print("下游节点:", json.dumps(target, ensure_ascii=False) if target else "未找到")

if target:
    # 2) table-detail 拿 horaeTasks
    out2 = run(["opencli", "szdata", "table-detail", "--guid", target["id"], "-f", "json"])
    try:
        detail = json.loads(out2)
        if isinstance(detail, list):
            detail = detail[0] if detail else {}
        print("表名:", detail.get("name"))
        print("库:", detail.get("dbName"))
        print("horaeTasks:", json.dumps(detail.get("horaeTasks"), ensure_ascii=False)[:500])
        print("sourceTables:", json.dumps(detail.get("sourceTables"), ensure_ascii=False)[:300])
        print("modelTables:", json.dumps(detail.get("modelTables"), ensure_ascii=False)[:300])
    except Exception as e:
        print("table-detail 解析失败:", e)
        print("原始输出前500字:", out2[:500])
