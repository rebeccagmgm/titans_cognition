// 118141 真实 Schema 全量血缘正式生成 —— 用 npx tsx sql-static-lineage-118141-full.ts 运行
// Schema 来源: szdata table-ddl 实测（pdata_n 库, 2026-08-15）
//   info = T98_OTC_DERI_COMP_SALE_INFO 92列 / det = T98_OTC_DERI_COMP_SALE_ADTNL_DET 23列 (21普通+2分区)
//   m    = T98_OTC_COMP_MNG_RELA_INFO 60列 (59普通+1分区)
//   其余表（s_sp/c_sp/s_ba/c_ba/cc/actl）在 SQL 中是显式列子查询, 无需 schema
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { SqlSession, lineage, Schema } from "../../src/index.ts";

const sql = readFileSync(
	"e:/02_area/股衍数据-数据cookbook/titans-cognition/.evidence-cache/tasksql-118141-20260814.txt",
	"utf-8",
);

const cols = (names: string[]) => Object.fromEntries(names.map((c) => [c, "string"]));
const schema = new Schema({
	"PDATA_N.T98_OTC_DERI_COMP_SALE_INFO": cols([
		"agt_id","busi_type","cutp_pty_id","cutp_pty_shor_name","cutp_pty_full_name","sign_prd_name",
		"indt_cd","corp_qual","contr_type_cd","contr_type_desc","src_contr_type","src_contr_type_desc",
		"src_sub_contr_type","src_sub_contr_type_desc","undrl_ins_id","undrl_wd_cd","undrl_name",
		"undrl_type","undrl_type_desc","src_undrl_type","src_undrl_type_desc","res_flag","ipo_flag",
		"buy_sell_dir_cd","cny_ex_rate","init_nom_prin","dyna_nom_prin","absl_nom_prin","strt_pric_date",
		"end_pric_date","early_term_date","earn_pymt_date","term_days","agt_stat_cd","inr_seri_no",
		"otc_seri_no","bndl_id","rel_agt_id","init_marg_prop","init_marg_bal","ddct_ptrn","cms_rate",
		"fixed_rate","fee_rate","hedg_type_cd","opt_fee","opt_fee_paid_date","ko_prtc_rate","ko_yield",
		"net_coll","coup_rate","min_obs_date","max_obs_date","up_prtc_rate","down_prtc_rate","ki_barr_pct",
		"ko_barr_pct","strk_pct","down_strk_pct","up_strk_pct","data_src_cd","task_name","data_etl_date",
		"data_upt_date","data_time","book_bel_dept","bgng_npv","src_agt_stat_cd","undrl_long_name",
		"qual_revw_flag","ext_comp_no","key_cutp_id","undrl_curr","intr_marg","base_marg_rate",
		"marg_agt_id","opt_fee_rate","book_agt_id","book_name","cntr","sler_cutp_pty_id","futr_type",
		"agt_clas_cd","cros_crrc_type_cd","float_base_rate","float_undrl_cd","flot_intrt_ulmt",
		"comp_usag_cd","sett_crrc_cd","ex_rate_model","busi_date","grp_id",
	]),
	"PDATA_N.T98_OTC_DERI_COMP_SALE_ADTNL_DET": cols([
		"agt_id","busi_type","cutp_pty_id","undrl_ins_id","undrl_wd_cd","undrl_name","strt_pric_date",
		"end_pric_date","init_nom_prin","dyna_nom_prin","fee_rate","inta","fnd_cost","trd_cms",
		"trd_cms_cost","marg_prop","data_src_cd","task_name","data_etl_date","data_upt_date","data_time",
		"busi_date","grp_id",
	]),
	"PDATA_N.T98_OTC_COMP_MNG_RELA_INFO": cols([
		"agt_id","pty_id","inr_org_id_1","inr_org_name_1","div_org_id_1","div_org_name_1",
		"cust_mngr_user_id_1","cust_mngr_name_1","cust_mngr_emp_id_1","allo_prop_1","inr_org_id_2",
		"inr_org_name_2","div_org_id_2","div_org_name_2","cust_mngr_user_id_2","cust_mngr_name_2",
		"cust_mngr_emp_id_2","allo_prop_2","inr_org_id_3","inr_org_name_3","div_org_id_3","div_org_name_3",
		"cust_mngr_user_id_3","cust_mngr_name_3","cust_mngr_emp_id_3","allo_prop_3","main_oper_user_id",
		"main_oper_name","main_oper_emp_id","intro_oper_user_id","intro_oper_name","intro_oper_emp_id",
		"data_src_cd","task_name","data_etl_date","data_upt_date","data_time","inr_main_oper_user_id",
		"inr_main_oper_name","inr_main_oper_emp_id","inr_intro_oper_user_id","inr_intro_oper_name",
		"inr_intro_oper_emp_id","tit_oper_user_id","tit_oper_name","tit_oper_emp_id","tit_oper_inr_org_id",
		"tit_oper_inr_org_name","tit_cust_mngr_user_id","tit_cust_mngr_name","tit_cust_mngr_emp_id",
		"tit_cust_mngr_inr_org_id","tit_cust_mngr_inr_org_name","cust_mngr_emp_stat_cd_1",
		"cust_mngr_emp_stat_desc_1","cust_mngr_emp_stat_cd_2","cust_mngr_emp_stat_desc_2",
		"cust_mngr_emp_stat_cd_3","cust_mngr_emp_stat_desc_3","busi_date",
	]),
});

const s = SqlSession.create(sql, "databricks");
const cell = s.doc.statements[1]; // SELECT 语句
const text = cell.text;

const out: string[] = [];
const log = (x: string) => out.push(x);

// ========== 1. 全量血缘（92 输出列）==========
// 无来源列按表达式类型细分 provenance 分类（字面量 vs runtime/system-derived vs 其他）
const RUNTIME_FNS = new Set([
	"unix_timestamp", "from_unixtime", "current_timestamp", "now",
	"current_date", "current_datetime", "current_user", "uuid", "rand", "random",
]);
function classifyNoSource(output: string): string {
	const i = text.indexOf(output);
	if (i < 0) return "无来源";
	const e = lineageAt(cell.scopes, i, schema)?.expr;
	if (!e) return "无来源";
	if (e.kind === "literal") return "字面量";
	if (e.kind === "function" && RUNTIME_FNS.has(String(e.name ?? "").toLowerCase()))
		return "runtime/system-derived";
	if (e.kind === "function") return `函数(${e.name})无基表输入`;
	return `${e.kind} 无基表输入`;
}

const lin = lineage(cell.scopes, schema);
log(`SQL 长度: ${sql.length} | 语句数: 2 (ddl + query) | 方言: databricks`);
log(`血缘输出列数: ${lin.all.length}\n`);
log("=== 92 列全量血缘（输出列 <- 基表来源）===");
const noSourceCls: Record<string, number> = {};
for (const c of lin.all) {
	const srcs = c.origins.map((o) => `${o.table.join(".")}.${o.column}`);
	if (srcs.length === 0) {
		const cls = classifyNoSource(c.output);
		noSourceCls[cls] = (noSourceCls[cls] ?? 0) + 1;
		log(`${c.output} <- (无基表来源: ${cls})`);
	} else {
		log(`${c.output} <- ${srcs.join(", ")}`);
	}
}
const clsSummary = Object.entries(noSourceCls)
	.map(([k, v]) => `${k}×${v}`)
	.join(" / ") || "无";
log(`\n无基表来源的列: ${Object.values(noSourceCls).reduce((a, b) => a + b, 0)}（${clsSummary}）`);

// ========== 2. 漏源检查: 三个历史漏源字段 ==========
log("\n=== 漏源回归检查（此前无 schema 时静默丢失的字段）===");
for (const name of ["Ddct_Ptrn", "Init_Marg_Prop", "Base_Marg_Rate"]) {
	const hit = lin.all.some((c) => c.origins.some((o) => o.column === name));
	log(`${hit ? "✅" : "❌"} ${name} ${hit ? "已出现在血缘来源中" : "仍未出现"}`);
}

// ========== 3. 逐跳 + 加工逻辑（Curr_Prvs_Sales_Income 全链）==========
import { lineageAt } from "../../src/index.ts";
import { partSpanOf } from "../../src/ir/part-span.js";

function scopeLabel(scope: any): string {
	const outs = Array.isArray(scope.outputs) ? scope.outputs.slice(0, 2).join(",") : "unknown";
	return `${scope.body.kind}[${outs}]`;
}
function exprText(expr: any): string {
	const sp = partSpanOf(expr.cst);
	if (!sp) return "(无span)";
	return text.slice(sp.start, sp.end).replace(/\s+/g, " ").trim();
}
function exprSummary(expr: any): string {
	switch (expr.kind) {
		case "case": return `case[${expr.whens.length}个when分支]`;
		case "function": return `function ${expr.name}${expr.window ? " [OVER窗口]" : ""}[${expr.args?.length ?? "?"}参]`;
		case "binary": return `binary ${expr.op}`;
		case "column": return `column ${(expr.parts ?? []).join(".")}`;
		case "literal": return `literal '${expr.text}'`;
		default: return expr.kind;
	}
}
function printHop(hop: any, depth: number): void {
	const pad = "  ".repeat(depth);
	const term =
		hop.terminal === "unresolved"
			? "unresolved(诚实死路)"
			: hop.terminal?.map((o: any) => `${o.table.join(".")}.${o.column}`).join(", ") ?? "-";
	log(`${pad}● 层: ${scopeLabel(hop.scope)} | 下游${hop.downstream.length}跳`);
	log(`${pad}  加工: ${exprText(hop.expr)}`);
	log(`${pad}  IR : ${exprSummary(hop.expr)}`);
	log(`${pad}  来处: ${term}`);
	for (const d of hop.downstream) printHop(d, depth + 1);
}

log("\n=== 逐跳血缘: Curr_Prvs_Sales_Income（真实 schema 版）===");
const idx = text.indexOf("Curr_Prvs_Sales_Income");
const hop = lineageAt(cell.scopes, idx, schema);
printHop(hop, 0);

mkdirSync("output/118141", { recursive: true });
writeFileSync("output/118141/sql-static-lineage-118141-full-output.txt", out.join("\n"), "utf8");
console.log(out.join("\n"));
console.log("\n\n[已保存] sql-static-lineage-118141-full-output.txt");
