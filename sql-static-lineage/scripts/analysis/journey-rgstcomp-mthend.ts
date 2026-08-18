// 指标旅程：grp1_CompScal_OtcDeriRgstComp_MthEnd 列级血缘解析
// 运行：npx tsx sql-static-lineage/scripts/analysis/journey-rgstcomp-mthend.ts
// 覆盖：162610（指标加工SQL）全量血缘 + index_val 逐跳；86840/86841（T98 采集）Dyna_Nom_Prin 逐跳
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { SqlSession, lineage, lineageAt, Schema } from "../../src/index.ts";
import { partSpanOf } from "../../src/ir/part-span.js";

const EV = "e:/02_area/股衍数据-数据cookbook/titans-cognition/.evidence-cache/";
const sql162610 = readFileSync(EV + "tasksql-162610-20260816122434.txt", "utf-8");
const sql86840 = readFileSync(EV + "tasksql-86840-20260816122735.txt", "utf-8");
const sql86841 = readFileSync(EV + "tasksql-86841-20260816122832.txt", "utf-8");

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
	"PDATA_N.T05_OTC_COMP_RGST_SAC_EVT": cols([
		"evt_id","otc_comp_agt_id","otc_comp_agt_modifr","actl_sett_date","sac_rgst_cd","rgst_date",
		"new_rgst_due_date","trmt_rgst_due_date","new_rgst_due_date_dbl","rgst_stat_cd",
		"attach_rgst_stat_cd","data_src_cd","task_name","data_etl_date","data_upt_date","data_time",
		"real_src_tbl","renw_flag","rgst_maty_date","src_tbl",
	]),
	"dm_index_n.tag_def": cols(["tag_partition_id", "dim_num", "dim_val", "tag_id", "status", "calc_ind"]),
	"dm_index_n.grp_def": cols(["grp_id", "grp_val", "grp_type_code", "status"]),
	"odata_n_tit.d_trd_otc_trade": cols(["key_otc_trade_id", "internal_trade_id", "key_book_id", "busi_date"]),
	"odata_n_tit.d_ref_otc_option_deal": cols(["key_otc_trade_id", "notional", "key_ctpty_id", "collateral_notional_currency", "settlement_currency", "busi_date"]),
	"odata_n_tit.d_ref_trs": cols(["key_otc_trade_id", "currency", "base_currency", "settlement_currency", "base_init_exchange_rate", "settle_init_exchange_rate", "start_date", "end_date", "trs_type", "busi_date"]),
	"odata_n_tit.d_ks_trade_comfirm_info": cols(["key_trade_comfirm_id", "counterparty_id", "notional", "dynamic_notional", "trs_type", "seller", "busi_date"]),
	"odata_n_tit.d_ks_trs_eod_postion": cols(["key_otc_trade_id", "nom_prin", "busi_date"]),
	"odata_n_tit.d_ref_fast_trs": cols(["key_otc_trade_id", "long_dynamic_notional", "dynamic_notional", "busi_date"]),
	"odata_n_tit.d_pos_fast_trs_leg_his_pos": cols(["key_otc_trade_id", "dyna_nom_prin", "busi_date"]),
	"odata_n_tit.d_ref_book": cols(["key_book_id", "department", "busi_date"]),
	"odata_n_tit.d_ref_ctpty_mapping": cols(["key_ctpty_id", "outside_ctpty_code", "busi_date"]),
	"odata_n_tit.d_ref_option_deal_structure": cols(["key_otc_trade_id", "start_date", "end_date", "contract_type", "contract_sub_type", "underlying_ins_id", "busi_date"]),
	"odata_n_tit.d_ref_rmb_midrate": cols(["currency", "quote_date", "midrate"]),
	"odata_n_tit.d_trd_otc_contr_report": cols(["key_otc_trade_id", "report_status", "interotc_code", "report_date", "busi_date"]),
	"odata_n_tit.d_ref_instrument": cols(["key_instrument_id", "ins_family", "ins_sht_desc", "ins_lng_desc", "busi_date"]),
});

function scopeLabel(scope: any): string {
	const outs = Array.isArray(scope.outputs) ? scope.outputs.slice(0, 2).join(",") : "unknown";
	return `${scope.body.kind}[${outs}]`;
}
function exprText(expr: any, text: string): string {
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
function printHop(hop: any, text: string, depth: number, out: string[]): void {
	const pad = "  ".repeat(depth);
	const term =
		hop.terminal === "unresolved"
			? "unresolved(诚实死路)"
			: hop.terminal?.map((o: any) => `${o.table.join(".")}.${o.column}`).join(", ") ?? "-";
	out.push(`${pad}● 层: ${scopeLabel(hop.scope)} | 下游${hop.downstream.length}跳`);
	out.push(`${pad}  加工: ${exprText(hop.expr, text)}`);
	out.push(`${pad}  IR : ${exprSummary(hop.expr)}`);
	out.push(`${pad}  来处: ${term}`);
	for (const d of hop.downstream) printHop(d, text, depth + 1, out);
}

const out: string[] = [];
const log = (x: string) => out.push(x);

// ========== 1. 指标加工 SQL（162610）全量血缘 ==========
{
	const s = SqlSession.create(sql162610, "databricks");
	const cell = s.doc.statements[1];
	const text = cell.text;
	const lin = lineage(cell.scopes, schema);
	log("=== 162610 指标加工SQL 列级血缘（dm_index_n.index_grp1_CompScal_OtcDeriRgstComp_MthEnd）===");
	log(`SQL 语句数: ${s.doc.statements.length} | 血缘输出列数: ${lin.all.length}`);
	for (const c of lin.all) {
		const srcs = c.origins.map((o) => `${o.table.join(".")}.${o.column}`);
		log(`${c.output} <- ${srcs.length ? srcs.join(", ") : "(无基表来源)"}`);
	}
	log("\n=== index_val（指标值）逐跳血缘 ===");
	const idx = text.indexOf("index_val");
	const hop = lineageAt(cell.scopes, idx, schema);
	printHop(hop, text, 0, out);
	log("\n=== index_val 来源统计 ===");
	const target = lin.all.find((c) => c.output === "index_val");
	if (target) {
		const byCol: Record<string, number> = {};
		for (const o of target.origins) byCol[`${o.table.join(".")}.${o.column}`] = (byCol[`${o.table.join(".")}.${o.column}`] ?? 0) + 1;
		for (const [k, v] of Object.entries(byCol)) log(`${k} ×${v}`);
	}
}

// ========== 2. T98 采集 SQL（86840 期权 / 86841 互换）Dyna_Nom_Prin 逐跳 ==========
for (const [taskId, sql, label] of [
	["86840", sql86840, "期权分组(grp_id=01)"],
	["86841", sql86841, "互换分组(grp_id=02)"],
] as const) {
	const s = SqlSession.create(sql, "databricks");
	const cell = s.doc.statements[1];
	const text = cell.text;
	out.push("");
	out.push(`=== 任务 ${taskId} T98 采集（${label}）Dyna_Nom_Prin 逐跳血缘 ===`);
	const idx = text.indexOf("Dyna_Nom_Prin");
	if (idx < 0) { out.push("未找到 Dyna_Nom_Prin"); continue; }
	const hop = lineageAt(cell.scopes, idx, schema);
	printHop(hop, text, 0, out);
}

const report = out.join("\n");
mkdirSync("output/118141", { recursive: true });
writeFileSync("output/118141/journey-rgstcomp-mthend-lineage.txt", report, "utf8");
console.log(report);
console.log("\n\n[已保存] output/118141/journey-rgstcomp-mthend-lineage.txt");
