# -*- coding: utf-8 -*-
"""生成《名义本金加工路径全景报告》Markdown
输入: model-notional-lineage.json + model-sql-hits.json + notional-fields-with-ods.json
输出: output/notional-lineage-20260816/notional-lineage-report.md
"""
import io
import json
import sys
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT = r"e:\02_area\股衍数据-数据cookbook\titans-cognition\output\notional-lineage-20260816"

lin = json.load(open(f"{OUT}\\model-notional-lineage.json", encoding="utf-8"))
hits = json.load(open(f"{OUT}\\model-sql-hits.json", encoding="utf-8"))
fwo = json.load(open(f"{OUT}\\notional-fields-with-ods.json", encoding="utf-8"))

# ---- 贴源字段清单汇总 ----
ods_fields = defaultdict(list)
for x in fwo:
    t = (x.get("ods_table") or "").lower()
    if t:
        ods_fields[t].append(x.get("column_name", ""))
ods_fields = {k: sorted(set(v)) for k, v in ods_fields.items()}

# ---- 分类命中列 ----
def classify(m):
    """返回 (加工方式, 证据等级)"""
    if m.get("native"):
        if m.get("computed"):
            return "计算", "原生"
        if m.get("proj_expr") and m["proj_expr"] != m["output"]:
            return "改名", "原生"
        return "透传", "原生"
    if m.get("computed"):
        note = m.get("heuristic_note", "") or ""
        evi = "启发式"
        if "多" in note or m.get("candidate_tables"):
            evi = "候选标注"
        elif "唯一贴源表" in note:
            evi = "唯一表同名"
        elif "命中贴源表" in note:
            evi = "输出列名强匹配"
        return "计算", evi
    note = m.get("heuristic_note", "") or ""
    if "多" in note or m.get("candidate_tables"):
        return "未知", "候选标注"
    if "投影列名" in note:
        return "改名(启发式)", "投影列名强匹配"
    if "列名命中贴源表" in note:
        return "透传(启发式)", "输出列名强匹配"
    if "唯一贴源表" in note:
        return "透传(启发式)", "唯一表同名"
    return "未知", "其他"

task_rows = []          # (目标表, sql_file, task_id, ods_refs, 列明细)
mode_counter = Counter()
evi_counter = Counter()
for r in lin:
    if not r.get("matched_columns"):
        continue
    det = []
    for m in r["matched_columns"]:
        mode, evi = classify(m)
        mode_counter[mode] += 1
        evi_counter[evi] += 1
        det.append((m["output"], mode, evi, m.get("terminal", ""), m.get("proj_expr", "")))
    task_rows.append((r["target_table"], r["sql_file"], r["task_id"], r.get("ods_refs", ""), det))

skips = [r for r in lin if r.get("skip")]
skip_rows = [(r["target_table"], r["sql_file"], r.get("ods_refs", "")) for r in skips]

# 贴源表使用统计
ods_usage = Counter()
for r in lin:
    for t in (r.get("ods_refs") or "").split(";"):
        if t.strip():
            ods_usage[t.strip().lower()] += 1

# ---- 渲染 ----
W = []
W.append("# 名义本金加工路径全景报告（TITANS 测试库）\n")
W.append("> 生成: 2026-08-16 | 数据源: TITANS 测试库只读元数据 + 365 个加工 SQL（downstream-tasks-sql）\n")
W.append("## 1. 链路总览\n")
W.append("```\n")
W.append("名义本金表达(63表达/118字段/34表)\n")
W.append("        │ 按表名映射(允许 titans_dm 注册差异)\n")
W.append("        ▼\n")
W.append("贴源层 odata_n_tit.d_* (8张表确认进入)\n")
W.append("        │ 365 个加工 SQL 扫描: 33 个任务引用贴源表\n")
W.append("        ▼\n")
W.append("加工层: 17 个任务含名义本金字段加工(76列) + 16 个任务仅引用(无名义本金字段)\n")
W.append("```\n")
W.append("**统计口径**: 33 个引用贴源表的任务中, 17 个任务的目标表含有名义本金字段并完成字段级血缘解析(76 列, 0 未解), 16 个任务仅引用贴源表做关联键/分区筛选/协议关系维护, 不含名义本金加工。\n")

W.append("## 2. 贴源层进入情况（8 张表）\n")
W.append("| 贴源表 | 名义本金字段(进入) | 被引用任务数 |\n|---|---|---|\n")
for t in sorted(ods_fields):
    n = ods_usage.get(t, 0)
    W.append(f"| {t} | {len(ods_fields[t])} | {n} |\n")
W.append(f"\n合计: 8 张贴源表, {sum(len(v) for v in ods_fields.values())} 个名义本金字段进入贴源层。\n")

W.append("## 3. 加工任务明细（17 任务 / 76 列）\n")
for tbl, sf, tid, ods_refs, det in sorted(task_rows):
    W.append(f"### {tbl}\n")
    W.append(f"- SQL: `{sf}` | 任务: {tid} | 贴源引用: {ods_refs}\n")
    W.append("| 目标列 | 加工方式 | 证据 | 最终来源 | 投影表达式 |\n|---|---|---|---|---|\n")
    for out, mode, evi, term, proj in det:
        term_short = term if len(term) <= 90 else term[:90] + "…"
        proj_short = proj.replace("\n", " ") if len(proj) <= 70 else proj[:70].replace("\n", " ") + "…"
        W.append(f"| {out} | {mode} | {evi} | `{term_short}` | `{proj_short}` |\n")
    W.append("\n")

W.append("## 4. 仅引用贴源表的任务（16 个, 无名义本金字段）\n")
W.append("| 目标表 | SQL | 贴源引用 |\n|---|---|---|\n")
for tbl, sf, ods_refs in sorted(skip_rows):
    W.append(f"| {tbl} | `{sf}` | {ods_refs} |\n")
W.append("\n> 说明: 这些任务引用了贴源表, 但 SQL 正文不含名义本金关键词(notional_keyword_count=0), 引用用途为关联键/分区筛选/协议关系维护等。\n")

W.append("## 5. 加工方式分类\n")
W.append("| 加工方式 | 列数 | 说明 |\n|---|---|---|\n")
mode_desc = {
    "透传": "同名直接透传",
    "改名": "源列 AS 目标列(改名映射)",
    "计算": "CASE WHEN / NVL 等表达式计算",
    "透传(启发式)": "启发式绑定的同名透传",
    "改名(启发式)": "启发式绑定, 投影为源列改名",
    "未知": "多表歧义候选",
}
for k, v in mode_counter.most_common():
    W.append(f"| {k} | {v} | {mode_desc.get(k, '')} |\n")

W.append("\n## 6. 证据等级\n")
W.append("| 证据等级 | 列数 | 含义 |\n|---|---|---|\n")
evi_desc = {
    "原生": "sql-static-lineage 语法解析 + 血缘绑定",
    "投影列名强匹配": "投影源列名命中贴源表字段清单(启发式)",
    "输出列名强匹配": "输出列名命中贴源表字段清单(启发式)",
    "唯一表同名": "任务仅引用一张贴源表, 按同名列绑定(启发式)",
    "候选标注": "多贴源表均有同名列, 无法唯一确定(如实标注)",
    "其他": "计算表达式引用无法绑定",
}
for k, v in evi_counter.most_common():
    W.append(f"| {k} | {v} | {evi_desc.get(k, '')} |\n")
W.append("\n> 启发式绑定全部为 LLM 无关的确定性规则: ①投影/输出列名在贴源表字段清单(01 阶段提取)中的唯一命中; ②任务 SQL 仅引用一张贴源表时的同名列绑定; ③多表同名列如实标注为候选, 不做猜测。\n")

W.append("## 7. 关键发现与局限\n")
W.append("1. **透传/改名是主流**: 76 列中绝大多数为贴源字段的透传或改名映射(如 `NOTIONAL AS Nom_Prin`), 计算型集中在 `Dyna_Nom_Prin`(CASE WHEN 多分支, 引用 Init_Nom_Prin、d_pos_trs_leg_his_pos.Init_Price×Quantity、d_ks_trade_comfirm_info.dynamic_notional、d_pos_fast_trs_leg_his_pos.dynamic_notional)与 `Larg_Nom_Prin_Appr_Stat_Cd`(NVL 校验状态)。\n")
W.append("2. **清单外源表**: t03_otc_opt_comp_sub_trd_info 原生解析出 `D_REF_INS_OPTION_INFO`(NOTIONAL/NOTIONAL_CURRENCY/INIT_NOTL_EXCHANGE_RATE 等), t98_otc_deri_comp_sale_adtnl_det 计算表达式引用 `D_KS_TRADE_COMFIRM_INFO.dynamic_notional`——两张表均不在前序 34 表/8 贴源映射清单内, 提示 p1/p2 阶段按表名匹配存在覆盖缺口, 建议补充核查。\n")
W.append("3. **sql-static-lineage(databricks 方言)解析边界**: ①内层 FROM 无别名+投影引用未定义前缀的子查询解析错乱; ②`WITH ... INSERT OVERWRITE` 前导 CTE 语句 lineage 只输出 CTE 列; ③两层以上无别名嵌套 lineage 截断。以上均通过文本投影提取+贴源列清单启发式回退覆盖, 并在本报告中如实标注证据等级。\n")
W.append("4. **唯一未定列**: t03_otc_comp_perf_marg_ref.Lcrrc_Dyna_Nom_Prin(`DYNAMIC_NOTIONAL`)在 d_ref_otc_option_deal 与 d_ref_trs 两表字段清单均有同名, 文本无法区分, 标注为候选。\n")

W.append("## 8. 产物清单\n")
W.append("- `model-sql-hits.json`: 33 个引用贴源表任务的清单(ods_refs 每任务贴源引用)\n")
W.append("- `model-notional-lineage.json`: 17 任务 76 列字段级血缘(原生/启发式/候选逐条标注)\n")
W.append("- `notional-fields-with-ods.json`: 118 条名义本金字段记录(01 阶段全量, 含贴源映射)\n")

with open(f"{OUT}\\notional-lineage-report.md", "w", encoding="utf-8") as f:
    f.write("".join(W))
print(f"报告已生成: {OUT}\\notional-lineage-report.md")
print(f"加工方式: {dict(mode_counter)}")
print(f"证据等级: {dict(evi_counter)}")
