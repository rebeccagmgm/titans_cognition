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
insert overwrite table T98_OTC_DERI_COMP_SALE_INFO partition(busi_date = '2026-05-24', grp_id = '01')
select
trade.internal_trade_id as Agt_Id,
'OPTION' as Busi_Type,
rcm.outside_ctpty_code as Cutp_Pty_Id,
cp.abbreviation as Cutp_Pty_Shor_Name,
cp.corporate_name as Cutp_Pty_Full_Name,
cp.Signature_Name as Sign_Prd_Name,
cp.industry as Indt_Cd,
cp.aptitude as Corp_Qual,
if(
substring(ds.start_date, 1, 10) <= '2025-03-31'
,case when ds.contract_type = 'AUTOCALL' and ds.contract_sub_type not in ('SNOWBALL','SECURED') and coalesce(bc.ins_family,ins.ins_family) in ('EQUITY', 'GDR') then 'OPTION_AUTOCALL_STOCK'
when ds.contract_type = 'AUTOCALL' and ds.contract_sub_type not in ('SNOWBALL','SECURED') and coalesce(bc.ins_family,ins.ins_family) not in ('EQUITY', 'GDR') then 'OPTION_AUTOCALL_NONSTOCK'
when ds.contract_type = 'AUTOCALL' and ds.contract_sub_type in ('SNOWBALL','SECURED') then 'OPTION_SNOWBALL_SECURED'
when ds.contract_type = 'AIRBAG' and coalesce(bc.ins_family,ins.ins_family) in ('EQUITY', 'GDR') then 'OPTION_AIRBAG_STOCK'
when ds.contract_type = 'AIRBAG' and coalesce(bc.ins_family,ins.ins_family) not in ('EQUITY', 'GDR') then 'OPTION_AIRBAG_NONSTOCK'
when ds.contract_type in ('RISKY','AIRBAGX') and coalesce(bc.ins_family,ins.ins_family) = 'EQUITY' and deal.PRIVATE_PLACEMENT = 'Y' then 'OPTION_RISKY_AIRBAGX_PRI_STOCK'
when ds.contract_type in ('RISKY','AIRBAGX') and coalesce(deal.PRIVATE_PLACEMENT,'N') <> 'Y' then 'OPTION_RISKY_AIRBAGX_CIR_STOCK'
when rb.desk = 'OTCHK_QIS' and coalesce(bc.ins_family,ins.ins_family) = 'QIS' and deal.seller = '11613' then 'OPTION_N_CROSS_QTF_STRG_IDX'
when (ds.contract_type not in ('AUTOCALL','AIRBAG','RISKY','AIRBAGX') or ds.contract_type is null) and coalesce(bc.ins_family,ins.ins_family) in ('EQUITY', 'GDR') then 'OPTION_OTHER_STOCK'
when (ds.contract_type not in ('AUTOCALL','AIRBAG','RISKY','AIRBAGX') or ds.contract_type is null) and coalesce(bc.ins_family,ins.ins_family) not in ('EQUITY', 'GDR') then 'OPTION_OTHER_NONSTOCK'
end
,case when coalesce(bc.ins_family,ins.ins_family) in ('EQUITY', 'GDR')
and ds.contract_type not in ('RISKY','AIRBAGX','AIRBAGM','AIRBAGL','CUSTOMISED')
and not(ds.contract_type = 'AUTOCALL' and ds.contract_sub_type = 'SNOWBALL')
then 'OPTION_STOCK'
when coalesce(bc.ins_family,ins.ins_family) in ('INDEX', 'FUND')
and(ds.contract_type in ('ACCUMULATOR','DECCUMULATOR','AIRBAG') or (ds.contract_type = 'AUTOCALL' and ds.contract_sub_type <> 'SNOWBALL'))
then 'OPTION_IDX_ETF'
when rb.desk = 'OTCHK_QIS' and coalesce(bc.ins_family,ins.ins_family) = 'QIS' and deal.seller = '11613' then 'OPTION_N_CROSS_QTF_STRG_IDX'
when coalesce(bc.ins_family,ins.ins_family) = 'QIS' and ds.underlying_wind_code not in('GAMMA.WI', 'CHARM.WI') then 'OPTION_QTF_STRG_IDX_SPOT'
when coalesce(bc.ins_family,ins.ins_family) = 'QIS' and ds.underlying_wind_code in('GAMMA.WI', 'CHARM.WI') then 'OPTION_QTF_STRG_IDX_NONSPOT'
when ds.contract_type in ('RISKY','AIRBAGX') and coalesce(bc.ins_family,ins.ins_family) = 'EQUITY' and deal.PRIVATE_PLACEMENT = 'Y' then 'OPTION_RISKY_AIRBAGX_PRI_STOCK'
when ds.contract_type in ('RISKY','AIRBAGX') and coalesce(deal.PRIVATE_PLACEMENT,'N') <> 'Y' then 'OPTION_RISKY_AIRBAGX_CIR_STOCK'
else 'OPTION_OTHER_NONSTOCK'
end
) as Contr_Type_Cd,
if(
substring(ds.start_date, 1, 10) <= '2025-03-31'
,case when ds.contract_type = 'AUTOCALL' and ds.contract_sub_type not in ('SNOWBALL','SECURED') and coalesce(bc.ins_family,ins.ins_family) in ('EQUITY', 'GDR') then '自动赎回（除保本雪球和保本敲入型雪球）'
when ds.contract_type = 'AUTOCALL' and ds.contract_sub_type not in ('SNOWBALL','SECURED') and coalesce(bc.ins_family,ins.ins_family) not in ('EQUITY', 'GDR') then '自动赎回（除保本雪球和保本敲入型雪球）'
when ds.contract_type = 'AUTOCALL' and ds.contract_sub_type in ('SNOWBALL','SECURED') then '保本雪球和保本敲入型雪球'
when ds.contract_type = 'AIRBAG' and coalesce(bc.ins_family,ins.ins_family) in ('EQUITY', 'GDR') then '安全气囊'
when ds.contract_type = 'AIRBAG' and coalesce(bc.ins_family,ins.ins_family) not in ('EQUITY', 'GDR') then '安全气囊'
when ds.contract_type in ('RISKY','AIRBAGX') and coalesce(bc.ins_family,ins.ins_family) = 'EQUITY' and deal.PRIVATE_PLACEMENT = 'Y' then 'Risky和安全气囊X（限售股）'
when ds.contract_type in ('RISKY','AIRBAGX') and coalesce(deal.PRIVATE_PLACEMENT,'N') <> 'Y' then 'Risky和安全气囊X（流通股）'
when rb.desk = 'OTCHK_QIS' and coalesce(bc.ins_family,ins.ins_family) = 'QIS' and deal.seller = '11613' then '北上量化策略指数期权'
when (ds.contract_type not in ('AUTOCALL','AIRBAG','RISKY','AIRBAGX') or ds.contract_type is null) and coalesce(bc.ins_family,ins.ins_family) in ('EQUITY', 'GDR') then '其他期权（除Risky和安全气囊X）'
when (ds.contract_type not in ('AUTOCALL','AIRBAG','RISKY','AIRBAGX') or ds.contract_type is null) and coalesce(bc.ins_family,ins.ins_family) not in ('EQUITY', 'GDR') then '其他期权（除Risky和安全气囊X）'
end
,case when coalesce(bc.ins_family,ins.ins_family) in ('EQUITY', 'GDR')
and ds.contract_type not in ('RISKY','AIRBAGX','AIRBAGM','AIRBAGL','CUSTOMISED')
and not(ds.contract_type = 'AUTOCALL' and ds.contract_sub_type = 'SNOWBALL')
then '个股期权'
when coalesce(bc.ins_family,ins.ins_family) in ('INDEX', 'FUND')
and(ds.contract_type in ('ACCUMULATOR','DECCUMULATOR','AIRBAG') or (ds.contract_type = 'AUTOCALL' and ds.contract_sub_type <> 'SNOWBALL'))
then '指数/ETF期权'
when rb.desk = 'OTCHK_QIS' and coalesce(bc.ins_family,ins.ins_family) = 'QIS' and deal.seller = '11613' then '北上量化策略指数期权'
when coalesce(bc.ins_family,ins.ins_family) = 'QIS' and ds.underlying_wind_code not in('GAMMA.WI', 'CHARM.WI') then '量化策略指数期权（现货类）'
when coalesce(bc.ins_family,ins.ins_family) = 'QIS' and ds.underlying_wind_code in('GAMMA.WI', 'CHARM.WI') then '量化策略指数期权（非现货类）'
when ds.contract_type in ('RISKY','AIRBAGX') and coalesce(bc.ins_family,ins.ins_family) = 'EQUITY' and deal.PRIVATE_PLACEMENT = 'Y' then 'Risky和安全气囊X（限售股）'
when ds.contract_type in ('RISKY','AIRBAGX') and coalesce(deal.PRIVATE_PLACEMENT,'N') <> 'Y' then 'Risky和安全气囊X（流通股）'
else '其他期权'
end
) as Contr_Type_Desc,
ds.contract_type as Src_Contr_Type,
sct.dw_cd_val_desc as Src_Contr_Type_Desc,
ds.contract_sub_type as Src_Sub_Contr_Type,
ssct.dw_cd_val_desc as Src_Sub_Contr_Type_Desc,
ds.underlying_ins_id as Undrl_Ins_Id,
ds.underlying_wind_code as Undrl_Wd_Cd,
coalesce(bc.ins_sht_desc,ins.ins_sht_desc) as Undrl_Name,
case when coalesce(bc.ins_family,ins.ins_family) in ('EQUITY', 'GDR') and ds.underlying_currency not in ('HKD', 'USD') then 'OTH_STOCK'
when coalesce(bc.ins_family,ins.ins_family) in ('EQUITY', 'GDR') and ds.underlying_currency = 'HKD' then 'HK_STOCK'
when coalesce(bc.ins_family,ins.ins_family) in ('EQUITY', 'GDR') and ds.underlying_currency = 'USD' then 'US_STOCK'
when coalesce(bc.ins_family,ins.ins_family) not in ('EQUITY', 'GDR') then 'NON_STOCK'
else '-' end as Undrl_Type,
'' as Undrl_Type_Desc,
if(c.interotc_underlying_category = 'BONDS', 'BOND', coalesce(bc.ins_family,ins.ins_family)) as Src_Undrl_Type,
if(c.interotc_underlying_category = 'BONDS', '债券', sutd.dw_cd_val_desc) as Src_Undrl_Type_Desc,
if(deal.PRIVATE_PLACEMENT = 'Y', '1', '0') as Res_Flag,
'0' as IPO_Flag,
if(deal.SELLER in ('10161','10142'), '2', '1') as Buy_Sell_Dir_Cd,
case
when deal.COLLATERAL_NOTIONAL_CURRENCY = 'CNY' then 1
when deal.SETTLEMENT_CURRENCY = 'CNY' then ds.INIT_NOTL_EXCHANGE_RATE
else mid.MIDRATE
end as Cny_Ex_Rate,
(case
when deal.COLLATERAL_NOTIONAL_CURRENCY = 'CNY' then 1
when deal.SETTLEMENT_CURRENCY = 'CNY' then ds.INIT_NOTL_EXCHANGE_RATE
else mid.MIDRATE
end
) * deal.Initial_Notional as Init_Nom_Prin,
(case
when deal.COLLATERAL_NOTIONAL_CURRENCY = 'CNY' then 1
when deal.SETTLEMENT_CURRENCY = 'CNY' then ds.INIT_NOTL_EXCHANGE_RATE
else mid.MIDRATE
end
) * if('2026-05-24' between substring(ds.start_date, 1, 10) and substring(coalesce(deal.Early_Term_Date,ds.end_date), 1, 10), coalesce(deal.Notional,0), 0) as Dyna_Nom_Prin,
(case
when deal.COLLATERAL_NOTIONAL_CURRENCY = 'CNY' then 1
when deal.SETTLEMENT_CURRENCY = 'CNY' then ds.INIT_NOTL_EXCHANGE_RATE
else mid.MIDRATE
end
) * deal.Collateral_Notional as Absl_Nom_Prin,
substring(ds.start_date, 1, 10) as Strt_Pric_Date,
substring(ds.end_date, 1, 10) as End_Pric_Date,
substring(deal.Early_Term_Date, 1, 10) as Early_Term_Date,
substring(deal.Payment_Date, 1, 10) as Earn_Pymt_Date,
deal.Time_To_Maturity as Term_Days,
case when deal.Contr_Status in ('EFFECTIVE', 'EFFECTIVE_PENDING', 'TERMINATING', 'TERMINATING_PENDING') then '101'
when deal.Contr_Status = 'TERMINATED' then '226'
end as Agt_Stat_Cd,
trade.key_otc_trade_id as Inr_Seri_No,
trade.key_instrument_id as Otc_Seri_No,
deal.bundle_id as bndl_id,
rel.property_value as Rel_Agt_Id,
mrg.Initial_Margin as Init_Marg_Prop,
mrg.MARGIN_BALANCE_INIT as init_Marg_Bal,
mp.deduction_pattern as Ddct_Ptrn,
cp.commission_rate as cms_rate,
null as fixed_rate,
fee.fee_rate,
deal.hedge_type as Hedg_Type_Cd,
PREMIUM AS Opt_Fee,
substring(deal.premium_date, 1, 10) as Opt_Fee_Paid_Date,
ds.KNOCKOUT_EXTRA_PAR as KO_Prtc_rate,  --期权，上涨参与率
ds.REBATE_NOT_ABS as KO_Yield,  --敲出收益率，仅期权
ODS.NET_PNL as net_coll,  --期权，交易净收取
RODC.COUPON_RATE as Coup_Rate,
KO.Min_OBS_DATE,
KO.Max_OBS_DATE,
pr.Up_Prtc_rate,  --仅期权，向上参与率
pr.Down_Prtc_rate,  --仅期权，向下参与率
KI.DOWN_KI_BARRIER_PCT as KI_Barr_PCT,  --敲入障碍价
coalesce(KO.UP_KO_BARRIER_PCT,KO.DOWN_KO_BARRIER_PCT) as KO_Barr_PCT,  --敲出障碍价
STk.Strk_PCT,  --执行价
STk.DOWN_Strk_PCT,  --下跌保护执行价格
STk.UP_Strk_PCT,  --封顶价格
'TIT' AS Data_Src_Cd,
UPPER('PDATA_N.T98_OTC_DERI_COMP_SALE_INFO_TIT110') AS Task_Name,
'2026-05-24' AS Data_Etl_Date,
'2026-05-24' AS Data_Upt_Date,
'2026-05-25 03:26:09' AS Data_Time,
rb.department as Book_Bel_Dept,
calc.initial_npv as Bgng_Npv,
deal.Contr_Status as Src_Agt_Stat_Cd,
coalesce(bc.ins_lng_desc,ins.ins_lng_desc) as Undrl_Long_Name,
cp.client_qualify_review as Qual_Revw_Flag,
deal.contract_code as Ext_Comp_No,
deal.key_ctpty_id as Key_Cutp_Id,
coalesce(ds.underlying_currency,'') as Undrl_Curr,
null as Intr_Marg,
mrg.basic_margin_rate as Base_Marg_Rate,
mr.Marg_Agt_Id,  --拆货基合约
deal.premium_rate as Opt_Fee_Rate,            --期权费率
rb.key_book_id as Book_Agt_Id,
rb.Book_Name,
rb.Desk as Cntr,
IF(NVL(TRIM(deal.seller),'')='','',CONCAT('TIT060-',deal.seller)) as Sler_Cutp_Pty_Id,
coalesce(bc.future_type,fu.future_type) as Futr_Type,
trade.business_type as Agt_Clas_Cd,
ds.cross_currency_type as Cros_Crrc_Type_Cd,
'' as Float_Base_Rate,
'' as Float_Undrl_Cd,
'' as Flot_Intrt_Ulmt,
null as Comp_Usag_Cd,
deal.SETTLEMENT_CURRENCY as Sett_Crrc_Cd
from (
select * from odata_n_tit.d_trd_otc_trade
where busi_Date = '2026-05-24' and key_book_id not in ('10022', '10019')  --去掉测试book
) trade
inner join (
select * from odata_n_tit.d_ref_otc_option_deal where busi_Date = '2026-05-24'  --期权表
) deal
on deal.key_otc_trade_id = trade.key_otc_trade_id
inner join (
select * from odata_n_tit.d_ref_book
where busi_Date = '2026-05-24' and department in ('OTC','OTC_HK')  --限定OTC部及OTCHK的交易
) rb
ON rb.key_book_id = trade.key_book_id
left join (
select * from odata_n_tit.d_ref_option_deal_structure where busi_Date = '2026-05-24'
) ds
on deal.key_otc_trade_id = ds.key_otc_trade_id
left join odata_n_tit.d_ref_rmb_midrate mid -- 外汇中间价
on deal.collateral_notional_currency = mid.currency
and ds.start_date = mid.quote_date
left join (
select * from odata_n_tit.d_ref_ctpty_mapping where busi_Date = '2026-05-24'
) rcm
ON deal.key_ctpty_id = rcm.key_ctpty_id
left join (
select * from odata_n_tit.r_cfg_instrument_pool_props
where busi_Date = '2026-05-24' and KEY_POOL_ID = '10000'
) c
on c.key_instrument_id = ds.underlying_ins_id
left join (
select * from odata_n_tit.d_ref_instrument where busi_Date = '2026-05-24'
) ins
on ins.key_instrument_id = ds.underlying_ins_id
left join (
select * from odata_n_tit.d_ref_future_properties where busi_Date = '2026-05-24'
) fu
on fu.key_instrument_id = ds.underlying_ins_id
left join (
select
bc.key_instrument_id,
concat_ws(';',collect_list(ins.ins_sht_desc)) as ins_sht_desc,
concat_ws(';',collect_list(ins.ins_lng_desc)) as ins_lng_desc,
concat_ws(';',collect_set(ins.ins_family)) as ins_family,
concat_ws(';',collect_set(fu.future_type)) as future_type
from (
select * from odata_n_tit.d_ref_basket_constituent where busi_Date = '2026-05-24'
) bc
left join (
select * from odata_n_tit.d_ref_instrument where busi_Date = '2026-05-24'
) ins
on ins.key_instrument_id = bc.underlying_inst_id
left join (
select * from odata_n_tit.d_ref_future_properties where busi_Date = '2026-05-24'
) fu
on fu.key_instrument_id = bc.underlying_inst_id
group by bc.key_instrument_id
) bc
on bc.key_instrument_id = ds.underlying_ins_id
left join (
select * from odata_n_tit.d_trd_otc_contr_props
where busi_Date = '2026-05-24' and property_name = 'relatedOption'
) rel
on rel.key_otc_trade_id = trade.key_otc_trade_id
left join (
select * from odata_n_tit.d_ref_otc_contr_margin_param
where busi_Date = '2026-05-24'
) mrg
on mrg.key_otc_trade_id = trade.key_otc_trade_id
left join (
select option_key_otc_trade_id, concat_ws(';',collect_set(trs_key_otc_trade_id)) as Marg_Agt_Id
from (
select * from odata_n_tit.f_ref_option_margin_trs_relation
where busi_date = '2026-05-24' and status = 'Y'
) a
join (
select * from odata_n_tit.d_ref_trs
where busi_date = '2026-05-24' and trs_type = 'LONG_HOLD_SWAP'
) b
on a.trs_key_otc_trade_id = b.key_otc_trade_id
group by option_key_otc_trade_id
) mr
on mr.option_key_otc_trade_id = trade.key_otc_trade_id
left join (
select * from odata_n_tit.d_trd_bundle_info
where busi_Date = '2026-05-24'
) tbi
on tbi.bundle_id = deal.bundle_id
left join (
select * from odata_n_tit.d_margin_plan
where busi_Date = '2026-05-24'
) mp
on tbi.key_plan_id = mp.id
left join (
select *
from odata_n_tit.d_TRD_OPTION_DEAL_SETTLEMENT
WHERE busi_date = '2026-05-24'
) ODS
on trade.KEY_OTC_TRADE_ID = ODS.KEY_OTC_TRADE_ID
left join (
select *
from (
SELECT *, row_number() over(partition by KEY_INSTRUMENT_ID order by CALC_DATE) as rn
FROM odata_n_tit.d_trd_daily_accrual_fee
where busi_Date = '2026-05-24' and fee_type = 'ACCRUAL_PREMIUM_FEE'
) t
where rn = 1
) fee
on fee.key_instrument_id = trade.key_instrument_id
left join (
SELECT KEY_OTC_TRADE_ID, concat_ws(';',collect_set(cast(cast(COUPON_RATE as double) as string))) as COUPON_RATE
FROM odata_n_tit.d_REF_OPTION_DEAL_CR
where busi_date = '2026-05-24'
group by KEY_OTC_TRADE_ID
) RODC
on trade.KEY_OTC_TRADE_ID = RODC.KEY_OTC_TRADE_ID
LEFT JOIN (
SELECT
KEY_OTC_TRADE_ID,
MIN(substring(OBS_DATE,1,10)) as MIN_OBS_DATE,
Max(substring(OBS_DATE,1,10)) as Max_OBS_DATE,
concat_ws(';',collect_set(cast(cast(UP_KO_BARRIER_PCT as double) as string))) as UP_KO_BARRIER_PCT,
concat_ws(';',collect_set(cast(cast(DOWN_KO_BARRIER_PCT as double) as string))) as DOWN_KO_BARRIER_PCT
FROM odata_n_tit.d_REF_OP_DEAL_AUTOCALL_KODATE  --敲出
where busi_date = '2026-05-24'
GROUP BY KEY_OTC_TRADE_ID
) KO
ON trade.KEY_OTC_TRADE_ID = KO.KEY_OTC_TRADE_ID
LEFT JOIN (
SELECT
KEY_OTC_TRADE_ID,
concat_ws(';',collect_set(cast(cast(DOWN_KI_BARRIER_PCT as double) as string))) as DOWN_KI_BARRIER_PCT
FROM odata_n_tit.d_REF_OP_DEAL_AUTOCALL_KIDATE  --敲入
where busi_date = '2026-05-24'
GROUP BY KEY_OTC_TRADE_ID
) KI
ON trade.KEY_OTC_TRADE_ID = KI.KEY_OTC_TRADE_ID
left join (
select
KEY_OTC_TRADE_ID,
max(if(SEQ = '0', cast(STRIKE_PCT as double), 0)) as Strk_PCT,
max(if(SEQ = '1', cast(STRIKE_PCT as double), 0)) as DOWN_Strk_PCT,
max(if(SEQ = '2', cast(STRIKE_PCT as double), 0)) as UP_Strk_PCT
from odata_n_tit.d_REF_OPTION_DEAL_STRIKE
where busi_date = '2026-05-24'
group by KEY_OTC_TRADE_ID
) STk
on trade.KEY_OTC_TRADE_ID = STk.KEY_OTC_TRADE_ID
left join (
SELECT
KEY_OTC_TRADE_ID,
max(if(SEQ = '0', cast(participation_rate as double), 0)) as Up_Prtc_rate,
max(if(SEQ = '1', cast(participation_rate as double), 0)) as Down_Prtc_rate
FROM odata_n_tit.d_REF_OPTION_DEAL_PR
WHERE busi_date = '2026-05-24'
group by KEY_OTC_TRADE_ID
) pr
on trade.KEY_OTC_TRADE_ID = pr.KEY_OTC_TRADE_ID
left join (--关联经办人
select client_id,abbreviation,corporate_name,Signature_Name,industry,aptitude,commission_rate,client_qualify_review
from odata_n_ois.o_otc_derivative_counterparty
where busi_Date = '2026-05-24' and delete_flag = '0' and department != 'HK'
union all
select client_id,abbreviation,full_name as corporate_name, null as Signature_Name,null as industry,null as aptitude,null as commission_rate, null as client_qualify_review
from odata_n_ois.g_hk_counterparty
where busi_Date = '2026-05-24' and delete_flag = '0'
) cp
on rcm.outside_ctpty_code = cp.client_id
left join (
select *
from PDATA_N.REF_DW_CD_VAL
where dw_cd_id = 'CD382' and remark = 'TITANS场外衍生品合约类型'
) sct
on sct.dw_cd_val = ds.contract_type
left join (
select *
from PDATA_N.REF_DW_CD_VAL
where dw_cd_id = 'CD381'
) ssct
on ssct.dw_cd_val = ds.contract_sub_type
left join (
select *
from PDATA_N.REF_DW_CD_VAL
where dw_cd_id = 'CD128' and remark = 'TITANS场外衍生品标的类型'
) sutd
on sutd.dw_cd_val = coalesce(bc.ins_family,ins.ins_family)
left join (
select
key_instrument_id,
initial_npv,
key_book_id,
row_number() over(partition by key_instrument_id,key_book_id order by quote_date desc) as rk
from odata_n_tit.d_pos_eod_calc_metrics
where busi_date = '2026-05-24' and ins_family = 'OTC_OPTION_CONTRACT'
) calc
on trade.key_instrument_id = calc.key_instrument_id and trade.key_book_id = calc.key_book_id and calc.rk = 1
where Contr_Status in ('EFFECTIVE', 'EFFECTIVE_PENDING', 'TERMINATED', 'TERMINATING', 'TERMINATING_PENDING')
;