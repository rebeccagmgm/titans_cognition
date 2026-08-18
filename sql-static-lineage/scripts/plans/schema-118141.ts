// 118141 真实表结构 Schema —— 来源: szdata table-ddl 实测 (pdata_n 库, 2026-08-15)
//   info = T98_OTC_DERI_COMP_SALE_INFO 92列 / det = T98_OTC_DERI_COMP_SALE_ADTNL_DET 23列 (21普通+2分区)
//   m    = T98_OTC_COMP_MNG_RELA_INFO 60列 (59普通+1分区)
//   其余表 (s_sp/c_sp/s_ba/c_ba/cc/actl) 在 SQL 中是显式列子查询, 无需 schema
import { Schema } from "../../src/index.ts";

const cols = (names: string[]) => Object.fromEntries(names.map((c) => [c, "string"]));

export const schema118141Mapping = {
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
};

export const schema118141 = new Schema(schema118141Mapping);
