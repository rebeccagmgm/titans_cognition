# -*- coding: utf-8 -*-
"""测试库（testdb）↔ 数综采集 覆盖率对账。

输入：
  - output/full-library-table-inventory-20260815/full-library-objects.csv  （测试库 12 schema 全量对象）
  - output/titans-collection-20260815/data/ods-source-mapping-final-v2.csv        （数综血缘 604 行）
  - output/titans-collection-20260815/data/titans_kafka_topics.json              （Kafka 4）
  - output/titans-collection-20260815/data/dpl_tables.json                       （dpl 59）

输出：output/titans-collection-20260815/stats/titans-coverage-report.html（自包含）
"""
import csv
import html
import json
import re
from collections import Counter

OUT = "output/titans-collection-20260815/data"
STATS_DIR = "output/titans-collection-20260815/stats"

# ---------- 1) 测试库 2629 对象 ----------
lib = list(csv.DictReader(open("output/full-library-table-inventory-20260815/full-library-objects.csv",
                              encoding="utf-8-sig")))
lib_by_schema = Counter(r["schema_name"] for r in lib)
lib_type = Counter((r["schema_name"], r["object_type"]) for r in lib)

# ---------- 2) 数综血缘源表（438）----------
def parse_dpl_src(name):
    m = re.match(r"tit_titans_([a-z0-9_]+?)_(.+)$", name, re.I)
    return (f"TITANS_{m.group(1).upper()}", m.group(2).upper()) if m else None


def parse_kafka_src(name):
    m = re.match(r"dpl_oracle_tit_titans_([a-z0-9_]+?)_(.+)$", name, re.I)
    return (f"TITANS_{m.group(1).upper()}", m.group(2).upper()) if m else None


odata_rows = list(csv.DictReader(open(f"{OUT}/ods-source-mapping-final-v2.csv", encoding="utf-8-sig")))
odata_src = set()
for r in odata_rows:
    if r.get("source_schema") and r.get("source_table"):
        odata_src.add((r["source_schema"].upper(), r["source_table"].upper()))

dpl_tables = json.load(open(f"{OUT}/dpl_tables.json", encoding="utf-8"))
dpl_src = set()
for t in dpl_tables:
    n = t.get("name", "")
    if n.startswith("tit_titans_") and parse_dpl_src(n):
        dpl_src.add(parse_dpl_src(n))

kafka_items = json.load(open(f"{OUT}/titans_kafka_topics.json", encoding="utf-8"))
kafka_src = set()
for it in kafka_items:
    n = it.get("name", "")
    if it.get("typeName") == "kafka_topic" and n.startswith("dpl_oracle_tit_") and parse_kafka_src(n):
        kafka_src.add(parse_kafka_src(n))

all_src = odata_src | dpl_src | kafka_src
src_by_schema = Counter(s[0] for s in all_src)

# ---------- 3) 对账表（只含确定性证据：测试库清单 + 数综血缘）----------
schemas = sorted(set(lib_by_schema) | set(src_by_schema))
rows_html = []
txt_lines = []
txt_lines.append("=" * 78)
txt_lines.append("测试库(testdb) vs 数综采集 对账（测试环境元数据，仅供参考）")
txt_lines.append("=" * 78)
txt_lines.append(f"{'schema':<20}{'测试库对象':>10}{'数综血缘源表':>12}  状态")
for s in schemas:
    lb = lib_by_schema.get(s, 0)
    src = src_by_schema.get(s, 0)
    if lb and src:
        status = "双向覆盖"
    elif lb and not src:
        status = "仅测试库(数综未采)"
    else:
        status = "仅数综(测试库清单外)"
    txt_lines.append(f"{s:<20}{lb:>10}{src:>12}  {status}")
    rows_html.append(f"<tr><td>{s}</td><td>{lb}</td><td>{src}</td><td>{status}</td></tr>")

# 汇总数字
lib_total = len(lib)
src_total = len(all_src)
both_schema = set(lib_by_schema) & set(src_by_schema)
txt_lines.append("-" * 78)
txt_lines.append(f"测试库对象总数(12 schema): {lib_total}（TABLE {sum(1 for r in lib if r['object_type']=='TABLE')} + VIEW {sum(1 for r in lib if r['object_type']=='VIEW')}）")
txt_lines.append(f"数综血缘源表总数(13 schema): {src_total}（odata {len(odata_src)} / dpl {len(dpl_src)} / kafka {len(kafka_src)}，去重）")
txt_lines.append(f"schema 交集: {len(both_schema)} 个；测试库独有: {sorted(set(lib_by_schema)-set(src_by_schema))}；数综独有: {sorted(set(src_by_schema)-set(lib_by_schema))}")
covered = sum(lib_by_schema.get(s, 0) for s in both_schema)
txt_lines.append(f"按 schema 粗算: 交集 schema 的测试库对象合计 {covered}/{lib_total}（{covered/lib_total*100:.1f}%），"
                 f"但对象级交集需逐表对账")

# 对象级对账：测试库表名 vs 数综源表名（同 schema 同名）
obj_overlap = 0
obj_detail = []
lib_names = {(r["schema_name"], r["object_name"].upper()) for r in lib}
for s, t in all_src:
    if (s, t) in lib_names:
        obj_overlap += 1
    else:
        obj_detail.append((s, t))
txt_lines.append(f"对象级: 数综 {src_total} 个源表中，测试库同 schema 同名 {obj_overlap} 个；"
                 f"测试库清单中无同名 {len(obj_detail)} 个")
if obj_detail:
    txt_lines.append("  测试库无同名的数综源表（按 schema 计数）:")
    for s, c in Counter(s for s, t in obj_detail).most_common():
        txt_lines.append(f"    {s}: {c}")

# 33 个无同名对象的进一步细分：表名在测试库其他 schema 是否存在
own_name_else = []   # 表名在测试库存在（其他 schema）
no_object = []       # 测试库完全无此对象
lib_by_name = {}
for r in lib:
    lib_by_name.setdefault(r["object_name"].upper(), []).append((r["schema_name"], r["object_type"]))
for s, t in obj_detail:
    hits = lib_by_name.get(t, [])
    (own_name_else if hits else no_object).append((s, t, hits))
txt_lines.append(f"  其中: 表名在测试库其他 schema 存在 {len(own_name_else)} 个（schema 布局差异）；"
                 f"测试库完全无此对象 {len(no_object)} 个")
for s, t, hits in own_name_else:
    txt_lines.append(f"    {s}.{t} -> 测试库 {hits}")
for s, t, hits in no_object:
    txt_lines.append(f"    {s}.{t} -> 测试库无")

# 类型拆分：测试库 TABLE/VIEW
lib_tab = sum(1 for r in lib if r["object_type"] == "TABLE")
lib_view = sum(1 for r in lib if r["object_type"] == "VIEW")
view_covered = sum(1 for s, t in all_src if (s, t) in lib_names and lib_names and False)
# 数综源表里哪些在测试库是 VIEW（反查）
src_is_view = []
src_is_table = []
for s, t in all_src:
    for r in lib:
        if r["schema_name"] == s and r["object_name"].upper() == t:
            (src_is_view if r["object_type"] == "VIEW" else src_is_table).append((s, t))
            break
txt_lines.append(f"对象级细分: 数综源表中测试库为 TABLE 的 {len(src_is_table)} 个、VIEW 的 {len(src_is_view)} 个")

with open(f"{STATS_DIR}/titans-coverage-stats.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(txt_lines))
print("\n".join(txt_lines))

# ---------- HTML ----------
html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>测试库 vs 数综采集 覆盖率对账</title>
<style>
  body {{ font-family: "Microsoft YaHei", sans-serif; background: #f5f7fa; margin: 0; color: #333; }}
  .wrap {{ max-width: 1000px; margin: 0 auto; padding: 24px; }}
  h1 {{ font-size: 22px; }}
  h2 {{ font-size: 17px; border-left: 4px solid #2f6fed; padding-left: 10px; margin-top: 30px; }}
  table {{ background: #fff; border-collapse: collapse; width: 100%; font-size: 13px; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  th {{ background: #2f6fed; color: #fff; padding: 8px 12px; text-align: left; }}
  td {{ padding: 7px 12px; border-bottom: 1px solid #eef1f5; }}
  .cards {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 16px 0; }}
  .card {{ background: #fff; border-radius: 8px; padding: 14px 20px; flex: 1; min-width: 150px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  .card .num {{ font-size: 26px; font-weight: 700; color: #2f6fed; }}
  .card .lbl {{ font-size: 13px; color: #888; margin-top: 4px; }}
  .note {{ background: #fff8e6; border: 1px solid #f0d488; border-radius: 8px; padding: 12px 16px; font-size: 13px; margin-top: 14px; }}
  .warn {{ background: #fdecea; border: 1px solid #f0b4ad; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>测试库 vs 数综采集：覆盖率对账</h1>
  <p style="color:#888;font-size:13px;">测试库 = 本地 Oracle testdb 12 schema 全量对象（2026-08-15 拉取）· 数综 = szdata 血缘确认源表（2026-08-15）· 测试环境，仅供参考</p>

  <div class="cards">
    <div class="card"><div class="num">{lib_total}</div><div class="lbl">测试库对象（12 schema，TABLE {lib_tab} + VIEW {lib_view}）</div></div>
    <div class="card"><div class="num">{src_total}</div><div class="lbl">数综血缘源表（13 schema，去重）</div></div>
    <div class="card"><div class="num">{obj_overlap}</div><div class="lbl">同 schema 同名的对象级交集</div></div>
    <div class="card"><div class="num">{len(src_by_schema) - len(both_schema)}</div><div class="lbl">数综独有 schema（测试库清单外）</div></div>
  </div>

  <h2>Schema 级对账</h2>
  { "<table><thead><tr><th>schema</th><th>测试库对象</th><th>数综血缘源表</th><th>状态</th></tr></thead><tbody>" + "".join(rows_html) + "</tbody></table>" }

  <div class="note">
  <b>读法</b>：<br>
  ① 「双向覆盖」的 8 个 schema 是 TITANS 主体系（DM/TRADEFLOW/REFDATA/MARGIN/OTCCLEARING/MARKETDATA/ADMIN/WORKFLOW）；<br>
  ② 「仅测试库」4 个 schema（ETL/TRADING/RISK/QUERY）：测试库有对象，但数综血缘里没有出现——大概率未采集或未登记；<br>
  ③ 「仅数综」5 个 schema（BOOKING/OPERATION/SERVICE/STATICDATA/STOCKBANK）：数综采集的源库与本地测试库不是同一套（数综采的是另一环境/镜像）。
  </div>

  <div class="note warn">
  <b>注意</b>：对象级同名交集 {obj_overlap} 只是"同 schema 同名"粗对，未做大小写/视图语义级核对；<br>
  数综源表中测试库无同名的 {len(all_src) - obj_overlap} 个里：<b>{len(own_name_else)} 个表名在测试库 TITANS_DM 存在</b>（如 REF_PORTFOLIO、TRD_DEAL、PRICING_BUCKET_METRIC、REF_COUNTERPARTY——数综侧在 STATICDATA/BOOKING/SERVICE/REFDATA，测试库全堆在 DM，schema 布局不同）；<b>{len(no_object)} 个测试库完全无此对象</b>（如 BK_BOOK、OPE_*、TRD_BOOK_MAPPING*、GPU_MA_EOD_*、EQ_EQUITY_SOURCE）。<br>
  结论倾向：数综采集的源是另一套环境（生产镜像），不是本地测试库；测试库与数综源库是两套不同布局的库。
  </div>
</div>
</body>
</html>"""

with open(f"{STATS_DIR}/titans-coverage-report.html", "w", encoding="utf-8") as f:
    f.write(html_doc)
print(f"\n覆盖率报告已生成: {STATS_DIR}/titans-coverage-report.html")
