# -*- coding: utf-8 -*-
"""名义本金表达 -> 数综贴源层(odata_n_tit) 映射。

将 stage6 名义本金涉及的 34 张 TITANS_TRADEFLOW 表与
ods-source-mapping-final-v2.csv 匹配，判定每张表是否进入贴源、
贴源表名(task_sql 中实际写入的 odata_n_tit 表)、映射证据类别。

输出:
  - table-ods-mapping.csv       表级映射
  - notional-fields-with-ods.csv 字段级合并(含贴源信息)
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output" / "notional-lineage-20260816"
COLLECT = ROOT / "output/titans-collection-20260815/data"

fields = json.loads((OUT / "notional-fields.json").read_text(encoding="utf-8"))
fields = [f for f in fields if f["stage"] == "stage6"]

# 读贴源映射
rows = []
with (COLLECT / "ods-source-mapping-final-v2.csv").open(encoding="utf-8-sig", newline="") as fh:
    for r in csv.DictReader(fh):
        rows.append(r)

# 索引: 表名(精确, 忽略大小写) -> [mapping rows]
# 说明: 数综采集源表注册在生产镜像 schema(TITANS_DM), 测试库同名表在
# TITANS_TRADEFLOW, 故按表名匹配忽略 schema, 另记录 schema 差异。
by_src: dict[str, list[dict]] = {}
for r in rows:
    schema = r["source_schema"]
    table = r["source_table"]
    if not schema or not table:
        continue
    for s, t in zip(schema.split(";"), table.split(";")):
        s, t = s.strip(), t.strip()
        if t:
            by_src.setdefault(t.upper(), []).append(r)

# 表级映射
tables = sorted({(f["schema"], f["table"]) for f in fields})
table_map = []
for schema, table in tables:
    hit = by_src.get(table.upper(), [])
    if hit:
        # 取证据最强的映射
        hit = sorted(hit, key=lambda r: {"CONFIRM": 0, "FALLBACK": 1, "NAMING": 2}.get(r["match"], 3))
        r = hit[0]
        reg_schema = r["source_schema"]
        same_schema = schema.upper() in reg_schema.upper()
        table_map.append(
            {
                "src_schema": schema,
                "src_table": table,
                "ods_table": r["ods_table"],
                "task_id": r["task_id"],
                "task_name": r["task_name"],
                "match": r["match"],
                "evidence": r["evidence"],
                "reg_schema": reg_schema,
                "schema_note": "" if same_schema else f"测试库{schema}->数综注册{reg_schema}",
                "mapping_count": len(hit),
                "probe_status": r["probe_status"],
            }
        )
    else:
        table_map.append(
            {
                "src_schema": schema,
                "src_table": table,
                "ods_table": "",
                "task_id": "",
                "task_name": "",
                "match": "NOT_FOUND",
                "evidence": "",
                "reg_schema": "",
                "schema_note": "",
                "mapping_count": 0,
                "probe_status": "",
            }
        )

with (OUT / "table-ods-mapping.csv").open("w", encoding="utf-8-sig", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(table_map[0].keys()))
    w.writeheader()
    w.writerows(table_map)

# 字段级合并
ods_by_table = {f"{r['src_schema']}.{r['src_table']}": r for r in table_map}
merged = []
for f in fields:
    key = f"{f['schema']}.{f['table']}"
    r = ods_by_table.get(key, {})
    merged.append(
        {
            **f,
            "ods_table": r.get("ods_table", ""),
            "ods_task_id": r.get("task_id", ""),
            "mapping_match": r.get("match", ""),
            "mapping_evidence": r.get("evidence", ""),
        }
    )
with (OUT / "notional-fields-with-ods.csv").open("w", encoding="utf-8-sig", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(merged[0].keys()))
    w.writeheader()
    w.writerows(merged)
with (OUT / "notional-fields-with-ods.json").open("w", encoding="utf-8") as fh:
    json.dump(merged, fh, ensure_ascii=False, indent=2)

# 摘要
in_ods = [t for t in table_map if t["match"] != "NOT_FOUND"]
not_in = [t for t in table_map if t["match"] == "NOT_FOUND"]
print(f"表级: 共 {len(table_map)} 张, 进入贴源 {len(in_ods)} 张, 未进贴源 {len(not_in)} 张")
print("\n== 进入贴源的表 ==")
for t in in_ods:
    print(f"  {t['src_table']} -> {t['ods_table']} [{t['match']}/{t['evidence']}] task={t['task_id']}")
print("\n== 未进贴源的表 ==")
for t in not_in:
    print(f"  {t['src_table']}")
print(f"\n[已保存] {OUT}")
