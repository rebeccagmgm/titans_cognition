# -*- coding: utf-8 -*-
"""探测 TITANS 源表在 odata_n_tit 之外的采集链路（dpl 库 / Kafka topic）。

背景：odata_n_tit 全量溯源后发现 TITANS 源表还有两条不经 odata_n_tit 的下游：
  1. dpl 库的 tit_titans_* 表（gf_rdbms_table，TiDB/StarRocks）
  2. Kafka topic dpl_oracle_tit_*（kafka_topic）
本脚本用 table-search 按前缀统计这两条链路的规模与 schema 分布。
"""
import csv
import json
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict

OUT_DIR = "output/titans-collection-20260815/data"
OUT_CSV = f"{OUT_DIR}/titans-extra-sinks.csv"


def search_all(keyword: str, type_code: str = "003000", max_pages: int = 60) -> list:
    """分页拉全 keyword 命中。返回 items 列表。"""
    items = []
    for page in range(1, max_pages + 1):
        r = subprocess.run(
            ["opencli", "szdata", "table-search", "--keyword", keyword,
             "--type", type_code, "--size", "100", "--page", str(page), "-f", "json"],
            capture_output=True, shell=True,
        )
        if r.returncode != 0:
            err = r.stderr.decode("utf-8", errors="replace")[:120]
            print(f"  [{keyword}] page {page} ERR: {err}", flush=True)
            break
        try:
            data = json.loads(r.stdout.decode("utf-8"))
        except Exception as e:
            print(f"  [{keyword}] page {page} parse ERR: {e}", flush=True)
            break
        if not data:
            break
        items.extend(data)
        if len(data) < 100:
            break
        time.sleep(0.4)
    return items


def parse_schema(name: str) -> str:
    """tit_titans_dm_trd_otc_trade -> TITANS_DM；dpl_oracle_tit_titans_admin_adm_user -> TITANS_ADMIN。"""
    m = re.match(r"(?:tit_)?(?:dpl_oracle_tit_)?titans_([a-z0-9_]+?)_.*", name, re.IGNORECASE)
    if m:
        return f"TITANS_{m.group(1).upper()}"
    m2 = re.match(r"dpl_oracle_tit_titans_([a-z0-9_]+?)_.*", name, re.IGNORECASE)
    if m2:
        return f"TITANS_{m2.group(1).upper()}"
    return ""


def main():
    print("=== 1/2 dpl 库 tit_titans_* 表 ===", flush=True)
    dpl_items = search_all("tit_titans_", "003000")
    print(f"  dpl 表命中 {len(dpl_items)} 条", flush=True)

    print("=== 2/2 Kafka topic dpl_oracle_tit_* ===", flush=True)
    kafka_items = search_all("dpl_oracle_tit_", "003000")
    print(f"  kafka 命中 {len(kafka_items)} 条", flush=True)

    # 去重（同表多环境 qn）
    def dedup(items):
        seen = set()
        out = []
        for it in items:
            key = (it.get("name"), it.get("typeName"))
            if key in seen:
                continue
            seen.add(key)
            out.append(it)
        return out

    dpl_items = dedup(dpl_items)
    kafka_items = dedup(kafka_items)

    # schema 分布
    dpl_schemas = Counter(parse_schema(x.get("name", "")) or "?" for x in dpl_items)
    kafka_schemas = Counter(parse_schema(x.get("name", "")) or "?" for x in kafka_items)

    print("\n=== dpl 库（tit_titans_*）schema 分布 ===", flush=True)
    for s, c in dpl_schemas.most_common():
        print(f"  {c:5d}  {s}", flush=True)
    print("\n=== Kafka topic（dpl_oracle_tit_*）schema 分布 ===", flush=True)
    for s, c in kafka_schemas.most_common():
        print(f"  {c:5d}  {s}", flush=True)

    # 落 CSV
    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sink", "name", "type", "qualifiedName", "schema"])
        for it in dpl_items:
            w.writerow(["dpl", it.get("name"), it.get("typeName"),
                        it.get("qualifiedName", ""), parse_schema(it.get("name", ""))])
        for it in kafka_items:
            w.writerow(["kafka", it.get("name"), it.get("typeName"),
                        it.get("qualifiedName", ""), parse_schema(it.get("name", ""))])
    print(f"\n已保存 {OUT_CSV}（dpl {len(dpl_items)} + kafka {len(kafka_items)}）", flush=True)


if __name__ == "__main__":
    sys.exit(main())
