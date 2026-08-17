CREATE TABLE if not exists T98_OTC_DERI_COMP_SALE_INFO(
Agt_Id string comment '合约编号',
Busi_Type string comment '业务类型',
Cutp_Pty_Id string comment '交易对手客户编号',
Cutp_Pty_Shor_Name string comment '交易对手当事人简称',
Cutp_Pty_Full_Name string comment '交易对手当事人名称',
Sign_Prd_Name string comment '代签产品名称',
Indt_Cd string comment '行业代码',
Corp_Qual string comment '企业资质',
Contr_Type_Cd string comment '合约类型代码',
Contr_Type_Desc string comment '合约类型描述',
Src_Contr_Type string comment '源合约类型',
Src_Contr_Type_Desc string comment '源合约类型描述',
Src_Sub_Contr_Type string comment '源合约子类型',
Src_Sub_Contr_Type_Desc string comment '源合约子类型描述',
Undrl_Ins_Id string comment '标的ID',
Undrl_Wd_Cd string comment '标的万得代码',
Undrl_Name string comment '标的名称',
Undrl_Type string comment '标的类型',
Undrl_Type_Desc string comment '标的类型描述',
Src_Undrl_Type string comment '源标的类型',
Src_Undrl_Type_Desc string comment '源标的类型描述',
Res_Flag string comment '限售标志',
IPO_Flag string comment 'IPO标志',
Buy_Sell_Dir_Cd string comment '买卖方向代码',
Cny_Ex_Rate string comment '人民币汇率',
Init_Nom_Prin string comment '初始名义本金',
Dyna_Nom_Prin string comment '动态名义本金',
Absl_Nom_Prin string comment '绝对名义本金',
Strt_Pric_Date string comment '期初定价日',
End_Pric_Date string comment '期末定价日',
Early_Term_Date string comment '提前终止日',
Earn_Pymt_Date string comment '收益兑付日',
Term_Days string comment '期限天数',
Agt_Stat_Cd string comment '协议状态代码',
Inr_Seri_No string comment '内部流水号',
Otc_Seri_No string comment '场外合约流水号',
bndl_id string comment '组合编号',
Rel_Agt_Id string comment '关联合约编号',
Init_Marg_Prop string comment '初始保证金比例',
init_Marg_Bal string comment '初始保证金',
Ddct_Ptrn string comment '抵扣模式',
cms_rate string comment '佣金费率',
fixed_rate string comment '固定腿利率',
fee_rate string comment '实际费率',
Hedg_Type_Cd string comment '对冲类型代码',
Opt_Fee string comment '期权费',
Opt_Fee_Paid_Date string comment '期权费支付日期',
KO_Prtc_rate string comment '敲出参与率',
KO_Yield string comment '敲出收益率',
net_coll string comment '交易净收取',
Coup_Rate string comment '票息',
Min_OBS_DATE string comment '最小观察日',
Max_OBS_DATE string comment '最大观察日',
Up_Prtc_rate string comment '向上参与率',
Down_Prtc_rate string comment '向下参与率',
KI_Barr_PCT string comment '敲入障碍价',
KO_Barr_PCT string comment '敲出障碍价',
Strk_PCT string comment '执行价',
DOWN_Strk_PCT string comment '下跌保护执行价格',
UP_Strk_PCT string comment '封顶价格',
Data_Src_Cd string comment '数据来源代码',
Task_Name string comment '任务名',
Data_Etl_Date string comment '数据加载日期',
Data_Upt_Date string comment '数据更新日期',
Data_Time string comment '数据时间',
Book_Bel_Dept string comment '账簿所属部门',
Bgng_Npv string comment '期初NPV',
Src_Agt_Stat_Cd string comment '源合约状态',
Undrl_Long_Name string comment '标的长名称',
Qual_Revw_Flag string comment '客户资质复核标志',
Ext_Comp_No string comment '外部合约编号',
Key_Cutp_Id string comment 'Titans客户编号',
Undrl_Curr string comment '标的币种',
Intr_Marg string comment '利差',
Base_Marg_Rate string comment '基础保证金率',
Marg_Agt_Id string comment '保证金合约编号',
Opt_Fee_Rate string comment '期权费率',
Book_Agt_Id string comment '账簿协议编号',
Book_Name string comment '账簿名称',
Cntr string comment '柜台',
Sler_Cutp_Pty_Id string comment '销售方交易对手当事人编号',
Futr_Type string comment '期货类型',
Agt_Clas_Cd string comment '协议分类代码',
Cros_Crrc_Type_Cd string comment '跨币种类型代码',
Float_Base_Rate string comment '浮动基础利率',
Float_Undrl_Cd string comment '浮动腿标的代码',
Flot_Intrt_Ulmt string comment '浮动利率上限',
Comp_Usag_Cd string comment '合约用途代码',
Sett_Crrc_Cd string comment '结算币种代码'
)
COMMENT 'T98_场外衍生品合约销售收入基本信息表'
PARTITIONED BY (
Busi_Date string comment '业务日期',
Grp_Id string comment '并行分组标识'
)
STORED AS ORC
;
insert overwrite table T98_OTC_DERI_COMP_SALE_INFO partition(busi_date = '2026-05-23', grp_id = '04')
select
trade.internal_trade_id as Agt_Id,
'TRS' as Busi_Type,
rcm.outside_ctpty_code as Cutp_Pty_Id,
cp.abbreviation as Cutp_Pty_Shor_Name,
cp.corporate_name as Cutp_Pty_Full_Name,
cp.Signature_Name as Sign_Prd_Name,
cp.industry as Indt_Cd,
cp.aptitude as Corp_Qual,
rt.trs_type as Contr_Type_Cd,
sct.dw_cd_val_desc as Contr_Type_Desc,
rt.trs_type as Src_Contr_Type,
sct.dw_cd_val_desc as Src_Contr_Type_Desc,
'' as Src_Sub_Contr_Type,
'' as Src_Sub_Contr_Type_Desc,
dy.Undrl_Ins_Id,
dy.Undrl_Wd_Cd,
dy.Undrl_Name,
dy.Undrl_Type,
dy.Undrl_Type_Desc,
dy.Src_Undrl_Type,
dy.Src_Undrl_Type_Desc,
'0' as Res_Flag,
'0' as IPO_Flag,
if(rt.seller in ('10161','10142'), '1', '2') as Buy_Sell_Dir_Cd,
'1' as Cny_Ex_Rate,
dy.Init_Nom_Prin,
coalesce(np.Dyna_Nom_Prin,'0') as Dyna_Nom_Prin,
'0.0' as Absl_Nom_Prin,
substring(rt.START_DATE, 1, 10) as Strt_Pric_Date,
substring(rt.End_Date, 1, 10) as End_Pric_Date,
substring(tocr.Actual_Settlement_Date, 1, 10) as Early_Term_Date,
'' as Earn_Pymt_Date,
rt.Time_To_Maturity as Term_Days,
case when rt.contr_status in ('EFFECTIVE', 'EFFECTIVE_PENDING', 'TERMINATING', 'TERMINATING_PENDING') then '101'
when rt.contr_status = 'TERMINATED' then '226'
end as Agt_Stat_Cd,
trade.key_otc_trade_id as Inr_Seri_No,
trade.key_instrument_id as Otc_Seri_No,
rt.bundle_id as bndl_id,
rel.property_value as Rel_Agt_Id,
mrg.Initial_Margin as Init_Marg_Prop,
mrg.MARGIN_BALANCE_INIT as init_Marg_Bal,
mp.deduction_pattern as Ddct_Ptrn,
cp.commission_rate as cms_rate,
null as fixed_rate,
null as fee_rate,
null as Hedg_Type_Cd,
null AS Opt_Fee,
null as Opt_Fee_Paid_Date,
null as KO_Prtc_rate,
null as KO_Yield,
null as net_coll,
null as Coup_Rate,
null as Min_OBS_DATE,
null as Max_OBS_DATE,
null as Up_Prtc_rate,
null as Down_Prtc_rate,
null as KI_Barr_PCT,
null as KO_Barr_PCT,
null as Strk_PCT,
null as DOWN_Strk_PCT,
null as UP_Strk_PCT,
'TIT' AS Data_Src_Cd,
UPPER('PDATA_N.T98_OTC_DERI_COMP_SALE_INFO_TIT293') AS Task_Name,
'2026-05-23' AS Data_Etl_Date,
'2026-05-23' AS Data_Upt_Date,
'2026-05-24 02:24:10' AS Data_Time,
rb.department as Book_Bel_Dept,
null as Bgng_Npv,
rt.contr_status as Src_Agt_Stat_Cd,
dy.Undrl_Long_Name,
cp.client_qualify_review as Qual_Revw_Flag,
rt.contract_code as Ext_Comp_No,
rt.key_ctpty_id as Key_Cutp_Id,
coalesce(dy.Undrl_Curr,'') as Undrl_Curr,
null as Intr_Marg,
mrg.basic_margin_rate as Base_Marg_Rate,
mrg.margin_internal_trade_id as Marg_Agt_Id,
null as Opt_Fee_Rate,
rb.key_book_id as Book_Agt_Id,
rb.Book_Name,
rb.Desk as Cntr,
IF(NVL(TRIM(rt.seller),'')='','',CONCAT('TIT060-',rt.seller)) as Sler_Cutp_Pty_Id,
dy.future_type as Futr_Type,
trade.business_type as Agt_Clas_Cd,
rt.cross_currency_type as Cros_Crrc_Type_Cd,
'' as Float_Base_Rate,
'' as Float_Undrl_Cd,
'' as Flot_Intrt_Ulmt,
null as Comp_Usag_Cd,
rt.SETTLEMENT_CURRENCY as Sett_Crrc_Cd
from (
select * from odata_n_tit.d_trd_otc_trade
where busi_Date = '2026-05-23' and key_book_id NOT IN ('10022', '10019')  --去掉测试book
) trade
inner join (
select * from odata_n_tit.d_ref_book
where busi_Date = '2026-05-23' and department in ('OTC','OTC_HK')  --限定OTC部及OTCHK的交易
) rb
ON rb.key_book_id = trade.key_book_id
inner join (
select * from odata_n_tit.d_ref_fast_trs
where busi_Date = '2026-05-23' and trs_type = 'N_CROSS_DMA_SWAP'
) rt
ON rt.key_otc_trade_id = trade.key_otc_trade_id
left join (
select * from odata_n_tit.d_trd_otc_contr_report where busi_Date = '2026-05-23'
) TOCR
ON TOCR.KEY_OTC_TRADE_ID = rt.KEY_OTC_TRADE_ID
left join (
select * from odata_n_tit.d_ref_ctpty_mapping where busi_Date = '2026-05-23'
) rcm
ON rt.key_ctpty_id = rcm.key_ctpty_id
left join (
select key_instrument_id, sum(dynamic_notional) as Dyna_Nom_Prin
from odata_n_tit.d_pos_fast_trs_leg_his_pos
where busi_date = '2026-05-23' and position_type = 'EOD_POSITION' and substring(src_busi_date,1,10) = '2026-05-23'
group by key_instrument_id
) np
on np.key_instrument_id = trade.key_instrument_id
left join (
select
dy.key_instrument_id,
concat_ws(';',collect_list(dy.underlying_ins_id)) as Undrl_Ins_Id,
concat_ws(';',collect_list(dy.wind_code)) as Undrl_Wd_Cd,
concat_ws(';',collect_list(dy.ins_sht_desc)) as Undrl_Name,
concat_ws(';',collect_list(d.ins_lng_desc)) as Undrl_Long_Name,
concat_ws(',',collect_set(case when dy.ins_family in ('EQUITY', 'GDR', 'BASKET') and d.currency not in ('HKD', 'USD') then 'OTH_STOCK'
when dy.ins_family in ('EQUITY', 'GDR', 'BASKET') and d.currency = 'HKD' then 'HK_STOCK'
when dy.ins_family in ('EQUITY', 'GDR', 'BASKET') and d.currency = 'USD' then 'US_STOCK'
when dy.ins_family not in ('EQUITY', 'GDR', 'BASKET') then 'NON_STOCK'
else '-' end)) as Undrl_Type,
'' as Undrl_Type_Desc,
concat_ws(',',collect_set(dy.ins_family)) as Src_Undrl_Type,
concat_ws(',',collect_set(sutd.dw_cd_val_desc)) as Src_Undrl_Type_Desc,
concat_ws(',',collect_set(coalesce(dy.currency,''))) as Undrl_Curr,
concat_ws(',',collect_set(f.future_type)) as future_type,
sum(dynamic_notional) as Init_Nom_Prin
from (
SELECT *,row_number() over(partition by key_instrument_id, wind_code order by src_busi_date) as rk
FROM odata_n_tit.d_pos_fast_trs_leg_his_pos
where busi_Date = '2026-05-23' and position_type = 'EOD_POSITION'
) dy
left join (
select * from odata_n_tit.d_ref_instrument where busi_Date = '2026-05-23'
) d
on d.wind_code = dy.wind_code
left join (
select * from odata_n_tit.d_ref_future_properties where busi_Date = '2026-05-23'
) f
on f.key_instrument_id = d.key_instrument_id
left join (
select *
from PDATA_N.REF_DW_CD_VAL
where dw_cd_id = 'CD128' and remark = 'TITANS场外衍生品标的类型'
) sutd
on sutd.dw_cd_val = d.ins_family
where dy.rk = 1
group by dy.key_instrument_id
) dy
ON dy.key_instrument_id = trade.key_instrument_id
left join (
select * from odata_n_tit.d_trd_otc_contr_props
where busi_Date = '2026-05-23' and property_name = 'relatedOption'
) rel
on rel.key_otc_trade_id = trade.key_otc_trade_id
left join (
select * from odata_n_tit.d_ref_otc_contr_margin_param
where busi_Date = '2026-05-23'
) mrg
on mrg.key_otc_trade_id = trade.key_otc_trade_id
left join (
select * from odata_n_tit.d_trd_bundle_info
where busi_Date = '2026-05-23'
) tbi
on tbi.bundle_id = rt.bundle_id
left join (
select * from odata_n_tit.d_margin_plan
where busi_Date = '2026-05-23'
) mp
on tbi.key_plan_id = mp.id
left join (--关联客户信息
select client_id,abbreviation,corporate_name,Signature_Name,industry,aptitude,commission_rate,client_qualify_review
from odata_n_ois.o_otc_derivative_counterparty
where busi_Date = '2026-05-23' and delete_flag = '0' and department != 'HK'
union all
select client_id,abbreviation,full_name as corporate_name, null as Signature_Name,null as industry,null as aptitude,null as commission_rate, null as client_qualify_review
from odata_n_ois.g_hk_counterparty
where busi_Date = '2026-05-23' and delete_flag = '0'
) cp
on rcm.outside_ctpty_code = cp.client_id
left join (
select *
from PDATA_N.REF_DW_CD_VAL
where dw_cd_id = 'CD382' and remark = 'TITANS场外衍生品合约类型'
) sct
on sct.dw_cd_val = rt.trs_type
where Contr_Status in ('EFFECTIVE', 'EFFECTIVE_PENDING', 'TERMINATED', 'TERMINATING', 'TERMINATING_PENDING')
;