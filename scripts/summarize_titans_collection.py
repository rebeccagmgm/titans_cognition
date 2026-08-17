# -*- coding: utf-8 -*-
"""TITANS 采集链路统计 + 自包含 HTML 可视化报告。

输入：titans-collection-full.csv（667 行）+ dpl_tables.json + titans_kafka_topics.json
输出：
  - output/titans-collection-20260815/stats/titans-collection-stats.txt   （文本统计）
  - output/titans-collection-20260815/stats/titans-collection-report.html（自包含报告）
"""
import csv
import html
import json
import re
from collections import Counter

OUT_DIR = "output/titans-collection-20260815/data"
STATS_DIR = "output/titans-collection-20260815/stats"

# ---------- 读取 ----------
# odata 侧直接从 final-v2 读（含 task_id），dpl/kafka 从各自 json 构造，不依赖合并表
odata_rows = list(csv.DictReader(open(f"{OUT_DIR}/ods-source-mapping-final-v2.csv", encoding="utf-8-sig")))
for r in odata_rows:
    r["target_table"] = r["ods_table"]

dpl_tables = json.load(open(f"{OUT_DIR}/dpl_tables.json", encoding="utf-8"))

def parse_dpl_src(name):
    m = re.match(r"tit_titans_([a-z0-9_]+?)_(.+)$", name, re.I)
    return (f"TITANS_{m.group(1).upper()}", m.group(2).upper()) if m else None


def parse_kafka_src(name):
    m = re.match(r"dpl_oracle_tit_titans_([a-z0-9_]+?)_(.+)$", name, re.I)
    return (f"TITANS_{m.group(1).upper()}", m.group(2).upper()) if m else None


dpl_rows = []
kafka_rows = []
for t in dpl_tables:
    n = t.get("name", "")
    if n.startswith("tit_titans_") and parse_dpl_src(n):
        p = parse_dpl_src(n)
        if not any(x["target_table"] == n for x in dpl_rows):
            dpl_rows.append({"sink": "dpl", "target_table": n,
                             "source_schema": p[0], "source_table": p[1]})
kafka_items = json.load(open(f"{OUT_DIR}/titans_kafka_topics.json", encoding="utf-8"))
for it in kafka_items:
    n = it.get("name", "")
    if it.get("typeName") == "kafka_topic" and n.startswith("dpl_oracle_tit_") and parse_kafka_src(n):
        p = parse_kafka_src(n)
        kafka_rows.append({"sink": "kafka", "target_table": n,
                           "source_schema": p[0], "source_table": p[1]})


dpl_names = sorted({t.get("name") for t in dpl_tables if t.get("name", "").startswith("tit_titans_")})
dpl_src = {parse_dpl_src(n) for n in dpl_names}
dpl_src = {s for s in dpl_src if s}
kafka_src = {parse_kafka_src(r["target_table"]) for r in kafka_rows}
kafka_src = {s for s in kafka_src if s}

odata_src = set()
for r in odata_rows:
    if r.get("source_schema") and r.get("source_table"):
        odata_src.add((r["source_schema"].upper(), r["source_table"].upper()))

# ---------- 统计 ----------
stats = {}

# 1) 总量
stats["总量"] = {
    "odata_表": len(odata_rows),
    "dpl_表": len(dpl_rows),
    "kafka_topic": len(kafka_rows),
    "去重源表": len(odata_src | dpl_src | kafka_src),
    "采集任务(odata侧)": len({r.get("task_id") for r in odata_rows if r.get("task_id")}),
}

# 2) 链路组合（源表级）
def combo(s):
    o, d, k = s in odata_src, s in dpl_src, s in kafka_src
    return ("仅odata" if o and not d and not k else
            "仅dpl" if d and not o and not k else
            "仅kafka" if k and not o and not d else
            "odata+dpl" if o and d and not k else
            "odata+kafka" if o and k and not d else
            "dpl+kafka" if d and k and not o else "三链路")
stats["链路组合"] = Counter(combo(s) for s in (odata_src | dpl_src | kafka_src))

# 3) match / evidence（odata 604）
stats["match分布"] = Counter(r.get("match", "") for r in odata_rows)
stats["evidence分布"] = Counter(r.get("evidence", "") for r in odata_rows)

# 4) 源 schema → 各链路表数
schema_stats = {}
for s in sorted(odata_src | dpl_src | kafka_src, key=lambda x: x[0]):
    sch = s[0]
    e = schema_stats.setdefault(sch, {"odata": 0, "dpl": 0, "kafka": 0, "源表": 0})
    e["源表"] += 1
    if s in odata_src:
        e["odata"] += 1
    if s in dpl_src:
        e["dpl"] += 1
    if s in kafka_src:
        e["kafka"] += 1
stats["schema"] = schema_stats

# 5) ODS 业务域前缀（首 token）
def first_token(name):
    m = re.match(r"^([a-z]+)", name or "")
    return m.group(1) if m else "?"
stats["业务域前缀"] = Counter(first_token(r["target_table"]) for r in odata_rows)

# 6) ODS 后缀变体（入湖/刷新逻辑）
def suffix_class(name):
    n = (name or "").lower()
    if n.endswith("_h15risk") or "_h15" in n:
        return "_H15RISK(15分钟)"
    if n.endswith("_pb"):
        return "_PB(增量+盘后)"
    if n.endswith("_p"):
        return "_P(增量)"
    if n.endswith("_s"):
        return "_S(快照)"
    if n.endswith("_tmp"):
        return "_TMP(临时)"
    if n.endswith("_all"):
        return "_ALL(全量)"
    if n.endswith("_bak"):
        return "_BAK(备份)"
    if n.endswith("_his"):
        return "_HIS(历史)"
    return "无后缀(全量/普通)"
stats["后缀变体"] = Counter(suffix_class(r["target_table"]) for r in odata_rows)

# 7) 任务 TOP
task_cnt = Counter()
for r in odata_rows:
    tid = r.get("task_id")
    if tid:
        task_cnt[tid] += 1
stats["任务TOP"] = task_cnt.most_common(10)
task_name_map = {r.get("task_id"): r.get("task_name", "") for r in odata_rows if r.get("task_id")}

# 8) UNKNOWN 清单
stats["UNKNOWN"] = [r for r in odata_rows if r.get("match") == "UNKNOWN"]

# 9) 16 schema 的 ODS 表数（含 NAMING 兜底标注）
src_by_schema = Counter(r.get("source_schema", "").upper() or "UNKNOWN" for r in odata_rows)
stats["odata_schema分布"] = src_by_schema

# ---------- 输出文本 ----------
lines = []
lines.append("=" * 60)
lines.append("TITANS 采集链路统计（测试环境元数据，仅供参考）")
lines.append("=" * 60)
lines.append(f"ODS 表(Hive): {stats['总量']['odata_表']} | dpl 表(TiDB/StarRocks): {stats['总量']['dpl_表']}"
             f" | Kafka topic: {stats['总量']['kafka_topic']} | 去重源表: {stats['总量']['去重源表']}"
             f" | odata 侧采集任务: {stats['总量']['采集任务(odata侧)']}")
lines.append("\n[链路组合-源表级]")
for k, v in stats["链路组合"].most_common():
    lines.append(f"  {k:12s} {v:4d}")
lines.append("\n[match-odata 604]")
for k, v in stats["match分布"].most_common():
    lines.append(f"  {k:12s} {v:4d}")
lines.append("\n[schema × 链路]")
lines.append("  {:22s} {:>5s} {:>5s} {:>6s} {:>6s}".format("schema", "源表", "odata", "dpl", "kafka"))
for sch, e in stats["schema"].items():
    lines.append("  {:22s} {:>5d} {:>5d} {:>6d} {:>6d}".format(
        sch, e["源表"], e["odata"], e["dpl"], e["kafka"]))
lines.append("\n[ODS 业务域前缀]")
for k, v in stats["业务域前缀"].most_common():
    lines.append(f"  {k:6s} {v:4d}")
lines.append("\n[ODS 后缀变体(入湖逻辑)]")
for k, v in stats["后缀变体"].most_common():
    lines.append(f"  {k:24s} {v:4d}")
lines.append("\n[采集任务 TOP10]")
for k, v in stats["任务TOP"]:
    lines.append(f"  task {k:>8s} {v:3d} 张  {task_name_map.get(k, '')}")
lines.append("\n[UNKNOWN 5]")
for r in stats["UNKNOWN"]:
    lines.append(f"  {r['target_table']} | {r.get('note','')}")
text = "\n".join(lines)
print(text)
with open(f"{STATS_DIR}/titans-collection-stats.txt", "w", encoding="utf-8") as f:
    f.write(text)

# ---------- 输出 HTML ----------
def bar(title, counter, max_val=None, unit="张", color="#2f6fed"):
    """CSS 条形图 HTML 片段"""
    total = sum(counter.values())
    mx = max_val or max(counter.values())
    items = []
    for k, v in counter.most_common():
        pct = v / total * 100
        w = v / mx * 100
        items.append(f"""
        <div class="bar-row">
          <div class="bar-label">{html.escape(str(k))}</div>
          <div class="bar-track"><div class="bar-fill" style="width:{w:.1f}%;background:{color}"></div></div>
          <div class="bar-val">{v} <span class="bar-pct">({pct:.1f}%)</span></div>
        </div>""")
    return f'<h3>{html.escape(title)}</h3><div class="bars">{ "".join(items) }</div>'

def table(headers, rows_html, cls=""):
    h = "".join(f"<th>{html.escape(str(x))}</th>" for x in headers)
    return f'<table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{"".join(rows_html)}</tbody></table>'

# schema 矩阵表
schema_rows = []
for sch, e in sorted(stats["schema"].items()):
    combos = []
    if e["odata"] and e["dpl"]:
        combos.append("odata+dpl")
    elif e["odata"]:
        combos.append("odata")
    if e["kafka"]:
        combos.append("kafka")
    schema_rows.append(
        f"<tr><td>{sch}</td><td>{e['源表']}</td><td>{e['odata']}</td><td>{e['dpl']}</td>"
        f"<td>{e['kafka']}</td><td>{'、'.join(combos) or '-'}</td></tr>")

match_rows = "".join(
    f"<tr><td>{k}</td><td>{v}</td><td>{v/604*100:.1f}%</td></tr>"
    for k, v in stats["match分布"].most_common())
task_rows = "".join(
    f"<tr><td>{k}</td><td>{html.escape(task_name_map.get(k, ''))}</td><td>{v}</td></tr>" for k, v in stats["任务TOP"])
unknown_rows = "".join(
    f"<tr><td>{html.escape(r['target_table'])}</td><td>{html.escape(r.get('note') or '')}</td></tr>"
    for r in stats["UNKNOWN"])

task_html = table(["task_id", "任务名", "采集表数"], task_rows) if task_rows else "<p>无任务数据</p>"
combo_colors = {"仅odata": "#4e79a7", "仅dpl": "#e15759", "仅kafka": "#59a14f",
                "odata+dpl": "#b07aa1", "odata+kafka": "#76b7b2", "dpl+kafka": "#f28e2b",
                "三链路": "#ff9da7"}
combo_html = []
mx = max(stats["链路组合"].values())
total_src = stats["总量"]["去重源表"]
for k, v in stats["链路组合"].most_common():
    combo_html.append(f"""
    <div class="bar-row">
      <div class="bar-label">{k}</div>
      <div class="bar-track"><div class="bar-fill" style="width:{v/mx*100:.1f}%;background:{combo_colors.get(k,'#999')}"></div></div>
      <div class="bar-val">{v} <span class="bar-pct">({v/total_src*100:.1f}%)</span></div>
    </div>""")

suffix_note = {
    "_P(增量)": "每日增量追加",
    "_PB(增量+盘后)": "增量 + 盘后批量",
    "_H15RISK(15分钟)": "15 分钟高频刷新（风险）",
    "_S(快照)": "快照",
    "_TMP(临时)": "临时表",
    "_ALL(全量)": "全量",
    "_BAK(备份)": "备份",
    "_HIS(历史)": "历史归档",
    "无后缀(全量/普通)": "常规全量/普通表",
}

html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>TITANS 采集链路全景统计</title>
<style>
  body {{ font-family: "Microsoft YaHei", "PingFang SC", sans-serif; margin: 0; background: #f5f7fa; color: #333; }}
  .wrap {{ max-width: 1080px; margin: 0 auto; padding: 24px; }}
  h1 {{ font-size: 24px; }}
  h2 {{ font-size: 18px; border-left: 4px solid #2f6fed; padding-left: 10px; margin-top: 36px; }}
  h3 {{ font-size: 15px; color: #555; margin-bottom: 8px; }}
  .cards {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 16px 0; }}
  .card {{ background: #fff; border-radius: 8px; padding: 14px 20px; flex: 1; min-width: 130px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  .card .num {{ font-size: 28px; font-weight: 700; color: #2f6fed; }}
  .card .lbl {{ font-size: 13px; color: #888; margin-top: 4px; }}
  .bars {{ background: #fff; border-radius: 8px; padding: 16px 20px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  .bar-row {{ display: flex; align-items: center; margin: 7px 0; }}
  .bar-label {{ width: 150px; font-size: 13px; text-align: right; padding-right: 10px; flex-shrink: 0; }}
  .bar-track {{ flex: 1; background: #eef1f5; border-radius: 4px; height: 22px; }}
  .bar-fill {{ height: 22px; border-radius: 4px; min-width: 2px; }}
  .bar-val {{ width: 110px; font-size: 13px; padding-left: 10px; }}
  .bar-pct {{ color: #aaa; font-size: 12px; }}
  table {{ background: #fff; border-collapse: collapse; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.08); width: 100%; font-size: 13px; }}
  th {{ background: #2f6fed; color: #fff; padding: 8px 12px; text-align: left; }}
  td {{ padding: 7px 12px; border-bottom: 1px solid #eef1f5; }}
  tr:hover td {{ background: #f7faff; }}
  .note {{ background: #fff8e6; border: 1px solid #f0d488; border-radius: 8px; padding: 12px 16px; font-size: 13px; color: #6b5d1f; margin-top: 16px; }}
  .section {{ margin-top: 8px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>TITANS 采集链路全景统计</h1>
  <p style="color:#888;font-size:13px;">基于数综元数据血缘（测试环境） · 生成日期 2026-08-15 · 数据值仅供参考，表结构与链路可信</p>

  <div class="cards">
    <div class="card"><div class="num">{stats['总量']['odata_表']}</div><div class="lbl">ODS 表（odata_n_tit / Hive 入湖）</div></div>
    <div class="card"><div class="num">{stats['总量']['dpl_表']}</div><div class="lbl">dpl 贴源表（TiDB/StarRocks）</div></div>
    <div class="card"><div class="num">{stats['总量']['kafka_topic']}</div><div class="lbl">Kafka 实时 topic</div></div>
    <div class="card"><div class="num">{stats['总量']['去重源表']}</div><div class="lbl">去重后 TITANS 源表（Oracle）</div></div>
    <div class="card"><div class="num">{stats['总量']['采集任务(odata侧)']}</div><div class="lbl">odata 侧采集任务数</div></div>
  </div>

  <h2>一、入湖逻辑：一张源表会被哪些链路采集</h2>
  <div class="bars">{''.join(combo_html)}</div>
  <div class="note">「仅 odata」占绝对多数：TITANS 主体数据只入 Hive ODS 一条湖。
  「odata+dpl」48 张为双链路并存；「仅 dpl」8 张只进 TiDB/StarRocks 贴源层（odata_n_tit 中没有）；
  TITANS_ADMIN 用户权限 4 张走实时（Kafka），其中 3 张三链路齐全、ADM_USER 无 dpl 批采。</div>

  <h2>二、13 个源 schema × 3 条链路</h2>
  {table(["schema", "源表数", "odata", "dpl", "kafka", "链路组合"], schema_rows)}

  <h2>三、ODS 表证据质量（604 张）</h2>
  {table(["match 类别", "张数", "占比"], [f"<tr><td>{k}</td><td>{v}</td><td>{v/604*100:.1f}%</td></tr>" for k, v in stats['match分布'].most_common()])}
  <div class="note">CONFIRM=血缘+命名一致；CORRECTED=血缘纠正命名；NEW=血缘发现命名没猜到；FALLBACK=沿 ODS 内部链路追溯/任务 SQL 补全；NAMING=仅命名推断；UNKNOWN=无证据。</div>

  <h2>四、ODS 业务域分布（表名前缀）</h2>
  {bar("ODS 表业务域前缀", stats['业务域前缀'])}

  <h2>五、入湖形态（表名后缀 = 刷新逻辑）</h2>
  {bar("ODS 后缀变体", stats['后缀变体'])}
  <div class="note">{ "；".join(f"{k} = {v}" for k, v in suffix_note.items() if k in stats['后缀变体']) }</div>

  <h2>六、采集任务 TOP10（odata 侧）</h2>
  {task_html}

  <h2>七、UNKNOWN 5 张（无血缘证据）</h2>
  {table(["ODS 表", "备注"], unknown_rows)}

  <div class="note">
  <b>说明</b>：odata_n_ois（166 张）为 GF_OTC 柜台采集层，非 TITANS；odata_n 裸库仅 2 张表。
  本报告基于 szdata 元数据血缘，全部结论为测试环境证据；8 张「仅 dpl」源表与 5 张 UNKNOWN 的源库侧确认需回公司。</div>
</div>
</body>
</html>"""

with open(f"{STATS_DIR}/titans-collection-report.html", "w", encoding="utf-8") as f:
    f.write(html_doc)
print(f"\n报告已生成: {STATS_DIR}/titans-collection-report.html")
