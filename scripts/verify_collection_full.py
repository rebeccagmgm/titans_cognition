# -*- coding: utf-8 -*-
"""验证合并表 + 确认 odata+kafka 交叉源表。"""
import csv
import json
import re

OUT_DIR = "output/titans-collection-20260815/data"

rows = list(csv.DictReader(open(f"{OUT_DIR}/titans-collection-full.csv", encoding="utf-8-sig")))
print("合并表总行数:", len(rows))
from collections import Counter
print("sink 分布:", dict(Counter(r['sink'] for r in rows)))

# 源表级再算一遍 odata+kafka
kafka_items = json.load(open(f"{OUT_DIR}/titans_kafka_topics.json", encoding="utf-8"))
kafka_src = set()
for it in kafka_items:
    if it.get("typeName") != "kafka_topic":
        continue
    m = re.match(r"dpl_oracle_tit_titans_([a-z0-9_]+?)_(.+)$", it.get("name", ""), re.I)
    if m:
        kafka_src.add((f"TITANS_{m.group(1).upper()}", m.group(2).upper()))
print("\nKafka 源表:", sorted(kafka_src))

odata_src = set()
for r in rows:
    if r['sink'] == 'odata' and r['source_schema'] and r['source_table']:
        odata_src.add((r['source_schema'].upper(), r['source_table'].upper()))
print("odata+kafka（无 dpl）:", sorted(odata_src & kafka_src))
print("仅 kafka:", sorted(kafka_src - odata_src))

# odata 侧 ADM_USER 对应的 ODS 表
print("\nodata 侧 ADM_USER 相关行:")
for r in rows:
    if r['sink'] == 'odata' and r['source_table'].upper() in ('ADM_USER', 'ADM_USER_ROLE', 'ADM_EMPLOYEE', 'ADM_ROLE'):
        print(f"  {r['target_table']} <- {r['source_schema']}.{r['source_table']} | {r['match']} | {r['evidence']}")
