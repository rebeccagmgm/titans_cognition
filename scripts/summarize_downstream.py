# -*- coding: utf-8 -*-
"""下一层消费关系汇总统计（文本 + HTML 报告）。

输入:
  downstream-odata.csv / downstream-dpl.csv  贴源表 -> 下游
  downstream-tables.csv                       去重下游表
  downstream-tables-tasks.csv                 下游表 -> 任务
  downstream-tasks-sql/                       任务 SQL 文件

输出:
  stats/downstream-summary.txt
  stats/downstream-report.html
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

DATA = Path("output/titans-collection-20260815/data")
STATS = Path("output/titans-collection-20260815/stats")

# ---------- 1) 贴源表 -> 下游 ----------
rel_rows: list[dict] = []
for f in ["downstream-odata.csv", "downstream-dpl.csv"]:
    p = DATA / f
    if not p.exists():
        continue
    for r in csv.DictReader(p.open(encoding="utf-8-sig")):
        rel_rows.append(r)

upstream_with_down = {r["upstream_table"] for r in rel_rows if r["downstream_name"]}
upstream_total = {r["upstream_table"] for r in rel_rows}
n_up = len(upstream_total)
n_up_down = len(upstream_with_down)

# 上游表 -> 下游表 关系计数
rel_pairs = [(r["upstream_table"], r["downstream_name"]) for r in rel_rows if r["downstream_name"]]
n_pairs = len(set(rel_pairs))

# ---------- 2) 下游表 ----------
tbl_rows = list(csv.DictReader((DATA / "downstream-tables.csv").open(encoding="utf-8-sig")))
n_tbl = len(tbl_rows)
tbl_type = Counter(r["downstream_type"] for r in tbl_rows)
tbl_prefix = Counter((r["downstream_name"] or "").split("_")[0] for r in tbl_rows)

# ---------- 3) 下游表 -> 任务 ----------
tsk_rows = list(csv.DictReader((DATA / "downstream-tables-tasks.csv").open(encoding="utf-8-sig")))
n_with_task = sum(1 for r in tsk_rows if r["horae_task_id"])
n_no_task = sum(1 for r in tsk_rows if not r["horae_task_id"])
db_dist = Counter(r["db_name"] for r in tsk_rows if r["db_name"])
task_ids = sorted({r["horae_task_id"] for r in tsk_rows if r["horae_task_id"]})
n_task = len(task_ids)

# ---------- 4) SQL 落盘 ----------
sql_files = list((DATA / "downstream-tasks-sql").glob("tasksql-*.txt"))
sql_tasks = {f.stem.split("-")[1] for f in sql_files}
n_sql = len(sql_files)
sql_size = sum(f.stat().st_size for f in sql_files)
sql_dup_tasks = n_task - len(sql_tasks)

lines: list[str] = []
lines.append("=" * 72)
lines.append("贴源层下一层消费关系汇总（测试环境元数据，仅供参考）")
lines.append("=" * 72)
lines.append("")
lines.append(f"贴源表探测: {n_up} 张（odata 604 + dpl 59）")
lines.append(f"  有下游消费方: {n_up_down} 张（{n_up_down / n_up * 100:.1f}%）")
lines.append(f"  贴源表->下游表关系对: {n_pairs}")
lines.append("")
lines.append(f"去重下游表: {n_tbl} 张")
lines.append(f"  类型: {dict(tbl_type)}")
lines.append(f"  前缀 Top12: {dict(tbl_prefix.most_common(12))}")
lines.append("")
lines.append(f"下游表->Horae任务: 有任务 {n_with_task} / 无任务 {n_no_task}")
lines.append(f"  去重任务数: {n_task}")
lines.append(f"  任务所属库 Top12: {dict(db_dist.most_common(12))}")
lines.append("")
lines.append(f"SQL 落盘: {n_sql} 个文件（{sql_size / 1024:.0f} KB），覆盖任务 {len(sql_tasks)}/{n_task}")
if sql_dup_tasks:
    lines.append(f"  缺 SQL 任务: {sql_dup_tasks} 个 -> {sorted(set(task_ids) - sql_tasks)}")
lines.append("")
lines.append("下游表类型分布:")
for t, c in tbl_type.most_common():
    lines.append(f"  {t:20s} {c}")
lines.append("")
lines.append("下游表库分布（任务侧）:")
for d, c in db_dist.most_common():
    lines.append(f"  {d:16s} {c}")
lines.append("")
lines.append("上游表按前缀分布（是否有下游）:")
up_prefix = Counter(r["upstream_table"].split("_")[0] if r["upstream_table"] else "" for r in rel_rows)
for p, c in up_prefix.most_common(12):
    lines.append(f"  {p:10s} {c}")

STATS.mkdir(parents=True, exist_ok=True)
txt = "\n".join(lines) + "\n"
(STATS / "downstream-summary.txt").write_text(txt, encoding="utf-8")
print(txt)

# ---------- HTML 报告 ----------
def esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

rows_html = []
for r in sorted(rel_rows, key=lambda x: (x["upstream_table"], x["downstream_name"])):
    if not r["downstream_name"]:
        continue
    rows_html.append(
        f"<tr><td>{esc(r['upstream_table'])}</td><td>{esc(r['downstream_type'])}</td>"
        f"<td>{esc(r['downstream_name'])}</td></tr>"
    )

task_html = []
for r in sorted(tsk_rows, key=lambda x: (x["db_name"], x["downstream_name"])):
    task_html.append(
        f"<tr><td>{esc(r['downstream_name'])}</td><td>{esc(r['db_name'])}</td>"
        f"<td>{esc(r['horae_task_id']) or '-'}</td>"
        f"<td>{esc(r['horae_task_label'][:60])}</td>"
        f"<td>{esc(r['probe_status'])}</td></tr>"
    )

html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<title>贴源层下一层消费关系</title>
<style>
body{{font-family:'Segoe UI',Microsoft YaHei,sans-serif;margin:24px;background:#f7f8fa;color:#222}}
h1{{font-size:22px}} h2{{font-size:17px;margin-top:28px;border-left:4px solid #2b6cb0;padding-left:8px}}
.card{{background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:14px 18px;margin:10px 0}}
table{{border-collapse:collapse;width:100%;font-size:13px;background:#fff}}
th,td{{border:1px solid #e2e8f0;padding:5px 8px;text-align:left;white-space:nowrap}}
th{{background:#2b6cb0;color:#fff;position:sticky;top:0}}
tr:nth-child(even){{background:#f7fafc}}
.note{{color:#718096;font-size:12px;margin-top:6px}}
.big{{font-size:26px;font-weight:600;color:#2b6cb0}}
</style></head><body>
<h1>贴源层下一层消费关系</h1>
<p class="note">依据：数综 szdata 元数据血缘（table-lineage DOWNSTREAM）与 Horae 任务登记（table-detail horaeTasks）。
测试环境元数据，仅供参考。生成时间：2026-08-16。</p>

<div class="card"><span class="big">{n_up}</span> 张贴源表探测 &nbsp;|&nbsp;
<span class="big">{n_up_down}</span> 张有下游 &nbsp;|&nbsp;
<span class="big">{n_tbl}</span> 张去重下游表 &nbsp;|&nbsp;
<span class="big">{n_task}</span> 个 Horae 任务 &nbsp;|&nbsp;
<span class="big">{n_sql}</span> 个 SQL 文件（{sql_size/1024:.0f} KB）</div>

<h2>1. 下游表类型分布</h2>
<div class="card">
<table><tr><th>类型</th><th>数量</th></tr>"""
for t, c in tbl_type.most_common():
    html += f"<tr><td>{esc(t)}</td><td>{c}</td></tr>"
html += "</table></div>"

html += f"""<h2>2. 下游表前缀分布（Top 12）</h2>
<div class="card"><table><tr><th>前缀</th><th>数量</th></tr>"""
for p, c in tbl_prefix.most_common(12):
    html += f"<tr><td>{esc(p)}</td><td>{c}</td></tr>"
html += "</table></div>"

html += f"""<h2>3. 任务所属库分布（Top 12）</h2>
<div class="card"><table><tr><th>库</th><th>任务数</th></tr>"""
for d, c in db_dist.most_common(12):
    html += f"<tr><td>{esc(d)}</td><td>{c}</td></tr>"
html += "</table></div>"

html += f"""<h2>4. 贴源表 -> 下游表明细（{len(rows_html)} 对）</h2>
<div class="card"><div style="max-height:420px;overflow:auto">
<table><tr><th>贴源表</th><th>下游类型</th><th>下游表</th></tr>"""
html += "".join(rows_html)
html += "</table></div></div>"

html += f"""<h2>5. 下游表 -> Horae 任务明细（{len(task_html)} 行）</h2>
<div class="card"><div style="max-height:420px;overflow:auto">
<table><tr><th>下游表</th><th>库</th><th>任务 ID</th><th>任务</th><th>状态</th></tr>"""
html += "".join(task_html)
html += "</table></div></div>"

html += """</body></html>"""
(STATS / "downstream-report.html").write_text(html, encoding="utf-8")
print(f"\n报告: {STATS / 'downstream-report.html'}")
