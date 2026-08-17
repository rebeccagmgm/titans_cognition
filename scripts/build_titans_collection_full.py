# -*- coding: utf-8 -*-
"""合并 TITANS 三条采集链路为一张全入口总表。

- odata_n_tit（604 行，来自 ods-source-mapping-final-v2.csv，sink=odata）
- dpl 库 tit_titans_*（59 行，来自 dpl_tables.json，sink=dpl）
- Kafka topic dpl_oracle_tit_*（4 行，来自 titans_kafka_topics.json，sink=kafka）

输出：titans-collection-full.csv；并打印源表级交并集统计。
"""
import csv
import json
import re
from collections import Counter

OUT_DIR = "output/titans-collection-20260815/data"


def parse_dpl_src(name: str):
    """tit_titans_dm_trd_otc_trade -> (TITANS_DM, TRD_OTC_TRADE)"""
    m = re.match(r"tit_titans_([a-z0-9_]+?)_(.+)$", name, re.I)
    return (f"TITANS_{m.group(1).upper()}", m.group(2).upper()) if m else None


def parse_kafka_src(name: str):
    """dpl_oracle_tit_titans_admin_adm_user_role -> (TITANS_ADMIN, ADM_USER_ROLE)"""
    m = re.match(r"dpl_oracle_tit_titans_([a-z0-9_]+?)_(.+)$", name, re.I)
    return (f"TITANS_{m.group(1).upper()}", m.group(2).upper()) if m else None


def main():
    # ---- 1) odata 604 行 ----
    odata_rows = list(csv.DictReader(open(f"{OUT_DIR}/ods-source-mapping-final-v2.csv", encoding="utf-8-sig")))
    print("odata 行数:", len(odata_rows))
    odata_src = set()
    for r in odata_rows:
        if r.get("source_schema") and r.get("source_table"):
            odata_src.add((r["source_schema"].upper(), r["source_table"].upper()))

    # ---- 2) dpl 59 行 ----
    dpl_tables = json.load(open(f"{OUT_DIR}/dpl_tables.json", encoding="utf-8"))
    dpl_by_name = {}
    for t in dpl_tables:
        dpl_by_name.setdefault(t.get("name"), []).append(t.get("qualifiedName", ""))
    dpl_rows = []
    dpl_src = set()
    for name, qns in sorted(dpl_by_name.items()):
        if not name.startswith("tit_titans_"):
            continue
        p = parse_dpl_src(name)
        if not p:
            continue
        dpl_src.add(p)
        envs = sorted({q.split("@")[-1] for q in qns})
        dpl_rows.append({
            "sink": "dpl",
            "target_table": name,
            "source_schema": p[0],
            "source_table": p[1],
            "match": "",  # 下面统一填
            "evidence": "LINEAGE-DIRECT",
            "note": "dpl 库表；环境: " + ",".join(envs),
        })
    print("dpl 行数:", len(dpl_rows))

    # ---- 3) kafka 4 行 ----
    kafka_items = json.load(open(f"{OUT_DIR}/titans_kafka_topics.json", encoding="utf-8"))
    kafka_rows = []
    kafka_src = set()
    for it in kafka_items:
        name = it.get("name", "")
        if it.get("typeName") != "kafka_topic" or not name.startswith("dpl_oracle_tit_"):
            continue
        p = parse_kafka_src(name)
        if not p:
            continue
        kafka_src.add(p)
        kafka_rows.append({
            "sink": "kafka",
            "target_table": name,
            "source_schema": p[0],
            "source_table": p[1],
            "match": "",
            "evidence": "LINEAGE-DIRECT",
            "note": "Kafka topic；源表下游反查确认",
        })
    print("kafka 行数:", len(kafka_rows))

    # ---- 4) 填 match（源表级交并集）----
    for rows, src_set in ((dpl_rows, dpl_src), (kafka_rows, kafka_src)):
        for r in rows:
            key = (r["source_schema"], r["source_table"])
            if key in odata_src:
                r["match"] = "OVERLAP"
            elif key in dpl_src:
                r["match"] = "OVERLAP"  # dpl/kafka 内部重叠也算
            else:
                r["match"] = "ONLY"

    # ---- 5) 输出合并 CSV ----
    out = f"{OUT_DIR}/titans-collection-full.csv"
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sink", "target_table", "source_schema", "source_table",
                    "match", "evidence", "note", "task_id", "task_name",
                    "upstream_all", "probe_status"])
        for r in odata_rows:
            w.writerow(["odata", r["ods_table"], r.get("source_schema", ""), r.get("source_table", ""),
                        r.get("match", ""), r.get("evidence", ""), r.get("note", ""),
                        r.get("task_id", ""), r.get("task_name", ""),
                        r.get("upstream_all", ""), r.get("probe_status", "")])
        for r in dpl_rows:
            w.writerow([r["sink"], r["target_table"], r["source_schema"], r["source_table"],
                        r["match"], r["evidence"], r["note"], "", "", "", ""])
        for r in kafka_rows:
            w.writerow([r["sink"], r["target_table"], r["source_schema"], r["source_table"],
                        r["match"], r["evidence"], r["note"], "", "", "", ""])
    print(f"已输出 {out}")

    # ---- 6) 源表级交并集统计 ----
    only_odata = odata_src - dpl_src - kafka_src
    only_dpl = dpl_src - odata_src - kafka_src
    only_kafka = kafka_src - odata_src - dpl_src
    od_dpl = (odata_src & dpl_src) - kafka_src
    od_kafka = (odata_src & kafka_src) - dpl_src
    dpl_kafka = (dpl_src & kafka_src) - odata_src
    tri = odata_src & dpl_src & kafka_src

    print("\n== 源表级分布（去重后）==")
    print(f"  仅 odata:        {len(only_odata)}")
    print(f"  仅 dpl:          {len(only_dpl)}")
    print(f"  仅 kafka:        {len(only_kafka)}")
    print(f"  odata+dpl:       {len(od_dpl)}")
    print(f"  odata+kafka:     {len(od_kafka)}")
    print(f"  dpl+kafka:       {len(dpl_kafka)}")
    print(f"  三链路:          {len(tri)}")
    print(f"  合计源表:        {len(odata_src | dpl_src | kafka_src)}")

    for label, s in (("仅 kafka", only_kafka), ("dpl+kafka", dpl_kafka), ("三链路", tri)):
        if s:
            print(f"  [{label}]:")
            for x in sorted(s):
                print("    ", x[0] + "." + x[1])


if __name__ == "__main__":
    main()
