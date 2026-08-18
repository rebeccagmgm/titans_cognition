// 决定性实验: 给 Schema 后, 三个漏源字段能否被解析 —— 用 npx tsx schema-experiment.ts 运行
// 目的: 验证 "缺 schema 导致漏源" 的结论 —— schema 喂入后 Ddct_Ptrn/Init_Marg_Prop/Base_Marg_Rate
//       是否进入 terminal（bound）而非 ambiguous
import { readFileSync } from "node:fs";
import { SqlSession, lineageAt, Schema } from "../../src/index.ts";
import { resolveColumnRef } from "../../src/sema/resolve.js";

const sql = readFileSync(
	"e:/02_area/股衍数据-数据cookbook/titans-cognition/.evidence-cache/tasksql-118141-20260814.txt",
	"utf-8",
);
const s = SqlSession.create(sql, "databricks");
const cell = s.doc.statements[1];
const text = cell.text;

// alias → 真实表名（来自 hops 文件 L44 来处的物理证据）
const aliasMap: Record<string, string> = {
	info: "PDATA_N.T98_OTC_DERI_COMP_SALE_INFO",
	det: "PDATA_N.T98_OTC_DERI_COMP_SALE_ADTNL_DET",
	cc: "PDATA_N.T99_DERI_COMP_TYPE_FND_COST_REF",
	s_sp: "PDATA_N.T99_DERI_COMP_SPRD_COEF_REF",
	c_sp: "PDATA_N.T99_DERI_CUTP_COMP_TYPE_SPRD_COEF_REF",
	s_ba: "PDATA_N.T99_DERI_COMP_BASE_COEF_REF",
	c_ba: "PDATA_N.T99_DERI_COMP_TYPE_BASE_COEF_REF",
	actl: "PDATA_N.T98_OTC_DERI_UNDRL_INCOME_RWD_SUM",
	m: "PDATA_N.T98_OTC_COMP_MNG_RELA_INFO",
};

// 从 SQL 提取所有 alias.column 限定引用 → 每表列集
const colSets: Record<string, Set<string>> = {};
const aliasRe = new RegExp(`\\b(${Object.keys(aliasMap).join("|")})\\.([A-Za-z_][A-Za-z0-9_]*)`, "gi");
for (const m of sql.matchAll(aliasRe)) {
	const alias = m[1].toLowerCase();
	(colSets[alias] ??= new Set()).add(m[2]);
}
// info 表替换为真实 DDL 全列（szdata table-ddl 实测, 2026-08-15）—— 含三个漏源字段:
//   init_marg_prop 初始保证金比例 / ddct_ptrn 抵扣模式 / base_marg_rate 基础保证金率
// 其余表仍用 SQL 限定引用列集（最小 schema; det/cc/m 全列待限流窗口后再补）
const infoRealCols = [
	"agt_id", "busi_type", "cutp_pty_id", "cutp_pty_shor_name", "cutp_pty_full_name",
	"sign_prd_name", "indt_cd", "corp_qual", "contr_type_cd", "contr_type_desc",
	"src_contr_type", "src_contr_type_desc", "src_sub_contr_type", "src_sub_contr_type_desc",
	"undrl_ins_id", "undrl_wd_cd", "undrl_name", "undrl_type", "undrl_type_desc", "src_undrl_type",
	"src_undrl_type_desc", "res_flag", "ipo_flag", "buy_sell_dir_cd", "cny_ex_rate",
	"init_nom_prin", "dyna_nom_prin", "absl_nom_prin", "strt_pric_date", "end_pric_date",
	"early_term_date", "earn_pymt_date", "term_days", "agt_stat_cd", "inr_seri_no",
	"otc_seri_no", "bndl_id", "rel_agt_id", "init_marg_prop", "init_marg_bal", "ddct_ptrn",
	"cms_rate", "fixed_rate", "fee_rate", "hedg_type_cd", "opt_fee", "opt_fee_paid_date",
	"ko_prtc_rate", "ko_yield", "net_coll", "coup_rate", "min_obs_date", "max_obs_date",
	"up_prtc_rate", "down_prtc_rate", "ki_barr_pct", "ko_barr_pct", "strk_pct", "down_strk_pct",
	"up_strk_pct", "data_src_cd", "task_name", "data_etl_date", "data_upt_date", "data_time",
	"book_bel_dept", "bgng_npv", "src_agt_stat_cd", "undrl_long_name", "qual_revw_flag",
	"ext_comp_no", "key_cutp_id", "undrl_curr", "intr_marg", "base_marg_rate", "marg_agt_id",
	"opt_fee_rate", "book_agt_id", "book_name", "cntr", "sler_cutp_pty_id", "futr_type",
	"agt_clas_cd", "cros_crrc_type_cd", "float_base_rate", "float_undrl_cd", "flot_intrt_ulmt",
	"comp_usag_cd", "sett_crrc_cd", "ex_rate_model", "busi_date", "grp_id",
];
colSets.info = new Set(infoRealCols);

console.log("=== 构造的 Schema 列集（info=真实DDL全列, 其他=SQL限定引用）===");
for (const [alias, cols] of Object.entries(colSets))
	console.log(`${aliasMap[alias]}: ${cols.size} 列 (${[...cols].slice(0, 8).join(", ")}...)`);

const schemaObj: Record<string, Record<string, string>> = {};
for (const [alias, cols] of Object.entries(colSets))
	schemaObj[aliasMap[alias]] = Object.fromEntries([...cols].map((c) => [c, "string"]));
const schema = new Schema(schemaObj);

// 1) resolveColumnRef: 三个字段在 case 所在 scope 的解析状态（带 schema）
console.log("\n=== 1. resolveColumnRef（带 schema）===");
const idx = text.indexOf("Curr_Prvs_Sales_Income");
const outerHop = lineageAt(cell.scopes, idx, schema);
const caseHops: any[] = [];
(function collect(h: any): void {
	if (!h) return;
	if (h.expr?.kind === "case") caseHops.push(h);
	for (const d of h.downstream ?? []) collect(d);
})(outerHop);
const inner = caseHops.sort((a, b) => (b.expr.whens?.length ?? 0) - (a.expr.whens?.length ?? 0))[0];
for (const name of ["Ddct_Ptrn", "Init_Marg_Prop", "Base_Marg_Rate"]) {
	const r = resolveColumnRef(inner.scope, { parts: [name], clause: undefined }, schema as any);
	if (r.kind === "bound")
		console.log(`✅ ${name} → bound: ${r.source.source?.relation?.parts?.join(".") ?? "?"}.${r.column}`);
	else if (r.kind === "ambiguous")
		console.log(`⚠️  ${name} → ambiguous: ${r.candidates?.map((x: any) => x.source?.relation?.parts?.join(".") ?? x.kind).join(", ") ?? "?"}`);
	else console.log(`❌ ${name} → ${r.kind}`);
}

// 2) lineageAt: terminal 是否包含三个字段
console.log("\n=== 2. lineageAt terminal（带 schema，内层 13 分支 case）===");
const termTexts = (inner.terminal ?? [])
	.map((o: any) => `${o.table.join(".")}.${o.column}`)
	.sort();
console.log(`terminal 列数: ${termTexts.length}`);
for (const name of ["Ddct_Ptrn", "Init_Marg_Prop", "Base_Marg_Rate"])
	console.log(`${termTexts.some((t: string) => t.endsWith("." + name)) ? "✅" : "❌"} ${name} ${termTexts.some((t: string) => t.endsWith("." + name)) ? "已进入 terminal" : "仍未进入"}`);
console.log(`\nterminal 全量（${termTexts.length}）:`);
for (const t of termTexts) console.log("  " + t);
