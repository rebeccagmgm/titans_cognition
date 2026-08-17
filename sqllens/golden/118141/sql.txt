CREATE TABLE IF NOT EXISTS  DM_OTC_N.OTC_SALE_DAILY_RPT( 
	 Agt_Id String COMMENT '合约编号' , Busi_Type String COMMENT '业务类型' , Cutp_Pty_Id String COMMENT '交易对手客户编号' , Cutp_Pty_Shor_Name String COMMENT '交易对手当事人简称' , Cutp_Pty_Full_Name String COMMENT '交易对手当事人名称' , Sign_Prd_Name String COMMENT '代签产品名称' , Contr_Type_Cd String COMMENT '合约类型代码' , Contr_Type_Desc String COMMENT '合约类型描述' , Src_Contr_Type String COMMENT '源合约类型' , Src_Contr_Type_Desc String COMMENT '源合约类型描述' , Src_Sub_Contr_Type String COMMENT '源合约子类型' , Src_Sub_Contr_Type_Desc String COMMENT '源合约子类型描述' , Undrl_Ins_Id String COMMENT '标的ID' , Undrl_Wd_Cd String COMMENT '标的' , Undrl_Name String COMMENT '标的名称' , Undrl_Type String COMMENT '标的类型' , Src_Undrl_Type String COMMENT '源标的类型' , Annu_Sprd String COMMENT '年化价差' , Absl_Sprd String COMMENT '绝对价差' , Annu_Base String COMMENT '年化销售费系数' , Absl_Base String COMMENT '绝对销售费系数' , Init_Nom_Prin String COMMENT '初始名义本金' , Init_Nom_Prin_Main String COMMENT '主经办人初始名义本金' , Init_Nom_Prin_Intro String COMMENT '引入经办人初始名义本金' , Dyna_Nom_Prin String COMMENT '动态名义本金' , Dyna_Nom_Prin_Main String COMMENT '主经办人动态名义本金' , Dyna_Nom_Prin_Intro String COMMENT '引入经办人动态名义本金' , Accum_Dyna_Nom_Prin String COMMENT '累计动态名义本金' , Absl_Nom_Prin String COMMENT '绝对名义本金' , Absl_Nom_Prin_Main String COMMENT '主经办人绝对名义本金' , Absl_Nom_Prin_Intro String COMMENT '引入经办人绝对名义本金' , Accum_Absl_Nom_Prin String COMMENT '累计绝对名义本金' , Curr_Prvs_Sales_Income String COMMENT '当日计提销售收入' , Curr_Prvs_Sales_Income_1 String COMMENT '当日计提销售收入_1' , Curr_Prvs_Sales_Income_2 String COMMENT '当日计提销售收入_2' , Curr_Prvs_Sales_Income_3 String COMMENT '当日计提销售收入_3' , Strt_Pric_Date String COMMENT '期初定价日' , End_Pric_Date String COMMENT '期末定价日' , Accrued_Strt_Date String COMMENT '计提初始日' , Accrued_End_Date String COMMENT '计提结束日' , Earn_Pymt_Date String COMMENT '收益兑付日' , Actl_Days String COMMENT '实际天数' , Is_Preterm_Flag String COMMENT '是否提前终止标识' , Early_Term_Date String COMMENT '提前终止日' , Agt_Stat_Cd String COMMENT '协议状态代码' , Main_Oper_User_Id String COMMENT '主经办人ID' , Main_Oper_Name String COMMENT '主经办人姓名' , Main_Oper_Emp_Id String COMMENT '主经办人ERP编号' , Intro_Oper_User_Id String COMMENT '引入经办人ID' , Intro_Oper_Name String COMMENT '引入经办人姓名' , Intro_Oper_Emp_Id String COMMENT '引入经办人ERP编号' , Intro_Inr_Org_Id_1 String COMMENT '引入部门ID_1' , Intro_Inr_Org_Name_1 String COMMENT '引入部门名称_1' , Div_Org_Id_1 String COMMENT '所属分公司ID_1' , Div_Org_Name_1 String COMMENT '所属分公司名称_1' , Cust_Mngr_User_Id_1 String COMMENT '客户经理ID_1' , Cust_Mngr_Name_1 String COMMENT '客户经理姓名_1' , Cust_Mngr_Emp_Id_1 String COMMENT '客户经理ERP编号_1' , Allo_Prop_1 String COMMENT '分配比例_1' , Intro_Inr_Org_Id_2 String COMMENT '引入部门ID_2' , Intro_Inr_Org_Name_2 String COMMENT '引入部门名称_2' , Div_Org_Id_2 String COMMENT '所属分公司ID_2' , Div_Org_Name_2 String COMMENT '所属分公司名称_2' , Cust_Mngr_User_Id_2 String COMMENT '客户经理ID_2' , Cust_Mngr_Name_2 String COMMENT '客户经理姓名_2' , Cust_Mngr_Emp_Id_2 String COMMENT '客户经理ERP编号_2' , Allo_Prop_2 String COMMENT '分配比例_2' , Intro_Inr_Org_Id_3 String COMMENT '引入部门ID_3' , Intro_Inr_Org_Name_3 String COMMENT '引入部门名称_3' , Div_Org_Id_3 String COMMENT '所属分公司ID_3' , Div_Org_Name_3 String COMMENT '所属分公司名称_3' , Cust_Mngr_User_Id_3 String COMMENT '客户经理ID_3' , Cust_Mngr_Name_3 String COMMENT '客户经理姓名_3' , Cust_Mngr_Emp_Id_3 String COMMENT '客户经理ERP编号_3' , Allo_Prop_3 String COMMENT '分配比例_3' , Accrued_Date String COMMENT '计提日期' , Data_Time String COMMENT '数据时间' , Accum_prvs_sales_income String COMMENT '累计计提销售收入' , Accum_prvs_sales_income_1 String COMMENT '累计计提销售收入_1' , Accum_prvs_sales_income_2 String COMMENT '累计计提销售收入_2' , Accum_prvs_sales_income_3 String COMMENT '累计计提销售收入_3' , Adtnl_Rwd String COMMENT '额外奖励' , fee_rate String COMMENT '成交费率' , Fin_Rati String COMMENT '融资比例' , Intr_Marg string COMMENT '利差' , Res_Flag string COMMENT '限售标志' , Opt_Fee_Rate string COMMENT '期权费率' , Ex_Rate_Model string COMMENT '汇率模式' , Cust_Mngr_Is_Actv_1 string COMMENT '客户经理是否在职_1' , Cust_Mngr_Is_Actv_2 string COMMENT '客户经理是否在职_2' , Cust_Mngr_Is_Actv_3 string COMMENT '客户经理是否在职_3' ) COMMENT '场外衍生品合约交叉销售收入日报' PARTITIONED BY ( busi_date String COMMENT '业务日期' ) STORED AS ORC;

SELECT  CAST( Agt_Id AS String ) Agt_Id ,
	 CAST( Busi_Type AS String ) Busi_Type ,
	 CAST( Cutp_Pty_Id AS String ) Cutp_Pty_Id ,
	 CAST( Cutp_Pty_Shor_Name AS String ) Cutp_Pty_Shor_Name ,
	 CAST( Cutp_Pty_Full_Name AS String ) Cutp_Pty_Full_Name ,
	 CAST( Sign_Prd_Name AS String ) Sign_Prd_Name ,
	 CAST( Contr_Type_Cd AS String ) Contr_Type_Cd ,
	 CAST( Contr_Type_Desc AS String ) Contr_Type_Desc ,
	 CAST( Src_Contr_Type AS String ) Src_Contr_Type ,
	 CAST( Src_Contr_Type_Desc AS String ) Src_Contr_Type_Desc ,
	 CAST( Src_Sub_Contr_Type AS String ) Src_Sub_Contr_Type ,
	 CAST( Src_Sub_Contr_Type_Desc AS String ) Src_Sub_Contr_Type_Desc ,
	 CAST( Undrl_Ins_Id AS String ) Undrl_Ins_Id ,
	 CAST( Undrl_Wd_Cd AS String ) Undrl_Wd_Cd ,
	 CAST( Undrl_Name AS String ) Undrl_Name ,
	 CAST( Undrl_Type AS String ) Undrl_Type ,
	 CAST( Src_Undrl_Type AS String ) Src_Undrl_Type ,
	 CAST( Annu_Sprd AS String ) Annu_Sprd ,
	 CAST( Absl_Sprd AS String ) Absl_Sprd ,
	 CAST( Annu_Base AS String ) Annu_Base ,
	 CAST( Absl_Base AS String ) Absl_Base ,
	 CAST( Init_Nom_Prin AS String ) Init_Nom_Prin ,
	 CAST( Init_Nom_Prin_Main AS String ) Init_Nom_Prin_Main ,
	 CAST( Init_Nom_Prin_Intro AS String ) Init_Nom_Prin_Intro ,
	 CAST( Dyna_Nom_Prin AS String ) Dyna_Nom_Prin ,
	 CAST( Dyna_Nom_Prin_Main AS String ) Dyna_Nom_Prin_Main ,
	 CAST( Dyna_Nom_Prin_Intro AS String ) Dyna_Nom_Prin_Intro ,
	 CAST( Accum_Dyna_Nom_Prin AS String ) Accum_Dyna_Nom_Prin ,
	 CAST( Absl_Nom_Prin AS String ) Absl_Nom_Prin ,
	 CAST( Absl_Nom_Prin_Main AS String ) Absl_Nom_Prin_Main ,
	 CAST( Absl_Nom_Prin_Intro AS String ) Absl_Nom_Prin_Intro ,
	 CAST( Accum_Absl_Nom_Prin AS String ) Accum_Absl_Nom_Prin ,
	 CAST( Curr_Prvs_Sales_Income AS String ) Curr_Prvs_Sales_Income ,
	 CAST( Curr_Prvs_Sales_Income_1 AS String ) Curr_Prvs_Sales_Income_1 ,
	 CAST( Curr_Prvs_Sales_Income_2 AS String ) Curr_Prvs_Sales_Income_2 ,
	 CAST( Curr_Prvs_Sales_Income_3 AS String ) Curr_Prvs_Sales_Income_3 ,
	 CAST( Strt_Pric_Date AS String ) Strt_Pric_Date ,
	 CAST( End_Pric_Date AS String ) End_Pric_Date ,
	 CAST( Accrued_Strt_Date AS String ) Accrued_Strt_Date ,
	 CAST( Accrued_End_Date AS String ) Accrued_End_Date ,
	 CAST( Earn_Pymt_Date AS String ) Earn_Pymt_Date ,
	 CAST( Actl_Days AS String ) Actl_Days ,
	 CAST( Is_Preterm_Flag AS String ) Is_Preterm_Flag ,
	 CAST( Early_Term_Date AS String ) Early_Term_Date ,
	 CAST( Agt_Stat_Cd AS String ) Agt_Stat_Cd ,
	 CAST( Main_Oper_User_Id AS String ) Main_Oper_User_Id ,
	 CAST( Main_Oper_Name AS String ) Main_Oper_Name ,
	 CAST( Main_Oper_Emp_Id AS String ) Main_Oper_Emp_Id ,
	 CAST( Intro_Oper_User_Id AS String ) Intro_Oper_User_Id ,
	 CAST( Intro_Oper_Name AS String ) Intro_Oper_Name ,
	 CAST( Intro_Oper_Emp_Id AS String ) Intro_Oper_Emp_Id ,
	 CAST( Intro_Inr_Org_Id_1 AS String ) Intro_Inr_Org_Id_1 ,
	 CAST( Intro_Inr_Org_Name_1 AS String ) Intro_Inr_Org_Name_1 ,
	 CAST( Div_Org_Id_1 AS String ) Div_Org_Id_1 ,
	 CAST( Div_Org_Name_1 AS String ) Div_Org_Name_1 ,
	 CAST( Cust_Mngr_User_Id_1 AS String ) Cust_Mngr_User_Id_1 ,
	 CAST( Cust_Mngr_Name_1 AS String ) Cust_Mngr_Name_1 ,
	 CAST( Cust_Mngr_Emp_Id_1 AS String ) Cust_Mngr_Emp_Id_1 ,
	 CAST( Allo_Prop_1 AS String ) Allo_Prop_1 ,
	 CAST( Intro_Inr_Org_Id_2 AS String ) Intro_Inr_Org_Id_2 ,
	 CAST( Intro_Inr_Org_Name_2 AS String ) Intro_Inr_Org_Name_2 ,
	 CAST( Div_Org_Id_2 AS String ) Div_Org_Id_2 ,
	 CAST( Div_Org_Name_2 AS String ) Div_Org_Name_2 ,
	 CAST( Cust_Mngr_User_Id_2 AS String ) Cust_Mngr_User_Id_2 ,
	 CAST( Cust_Mngr_Name_2 AS String ) Cust_Mngr_Name_2 ,
	 CAST( Cust_Mngr_Emp_Id_2 AS String ) Cust_Mngr_Emp_Id_2 ,
	 CAST( Allo_Prop_2 AS String ) Allo_Prop_2 ,
	 CAST( Intro_Inr_Org_Id_3 AS String ) Intro_Inr_Org_Id_3 ,
	 CAST( Intro_Inr_Org_Name_3 AS String ) Intro_Inr_Org_Name_3 ,
	 CAST( Div_Org_Id_3 AS String ) Div_Org_Id_3 ,
	 CAST( Div_Org_Name_3 AS String ) Div_Org_Name_3 ,
	 CAST( Cust_Mngr_User_Id_3 AS String ) Cust_Mngr_User_Id_3 ,
	 CAST( Cust_Mngr_Name_3 AS String ) Cust_Mngr_Name_3 ,
	 CAST( Cust_Mngr_Emp_Id_3 AS String ) Cust_Mngr_Emp_Id_3 ,
	 CAST( Allo_Prop_3 AS String ) Allo_Prop_3 ,
	 CAST( Accrued_Date AS String ) Accrued_Date ,
	 CAST( Data_Time AS String ) Data_Time ,
	 CAST( Accum_prvs_sales_income AS String ) Accum_prvs_sales_income ,
	 CAST( Accum_prvs_sales_income_1 AS String ) Accum_prvs_sales_income_1 ,
	 CAST( Accum_prvs_sales_income_2 AS String ) Accum_prvs_sales_income_2 ,
	 CAST( Accum_prvs_sales_income_3 AS String ) Accum_prvs_sales_income_3 ,
	 CAST( Adtnl_Rwd AS String ) Adtnl_Rwd ,
	 CAST( fee_rate AS String ) fee_rate ,
	 CAST( Fin_Rati AS String ) Fin_Rati ,
	Intr_Marg,
	Res_Flag,
	Opt_Fee_Rate,
	Ex_Rate_Model,
	Cust_Mngr_Is_Actv_1,
	Cust_Mngr_Is_Actv_2,
	Cust_Mngr_Is_Actv_3,
	 CAST( busi_date AS String ) busi_date  FROM (
	 select
    Agt_Id,
    Busi_Type,
    Cutp_Pty_Id,
    Cutp_Pty_Shor_Name,
    Cutp_Pty_Full_Name,
    Sign_Prd_Name,
    Contr_Type_Cd,
    Contr_Type_Desc,
    Src_Contr_Type,
    Src_Contr_Type_Desc,
    Src_Sub_Contr_Type,
    Src_Sub_Contr_Type_Desc,
    Undrl_Ins_Id,
    Undrl_Wd_Cd,
    Undrl_Name,
    Undrl_Type,
    Src_Undrl_Type,
    Annu_Sprd,
    Absl_Sprd,
    Annu_Base,
    Absl_Base,
    Init_Nom_Prin,
    IF(Intro_Oper_User_Id IS NULL or Intro_Oper_User_Id = '', Init_Nom_Prin * 1, Init_Nom_Prin * 0.4) AS Init_Nom_Prin_Main,  --还需要判断是否存在主经办人或引入经办人？看下数据是null还是''还是0？
    IF(Intro_Oper_User_Id IS NULL or Intro_Oper_User_Id = '', Init_Nom_Prin * 0, Init_Nom_Prin * 0.6) AS Init_Nom_Prin_Intro,
    Dyna_Nom_Prin,
    IF(Intro_Oper_User_Id IS NULL or Intro_Oper_User_Id = '', Dyna_Nom_Prin * 1, Dyna_Nom_Prin * 0.4) AS Dyna_Nom_Prin_Main,
    IF(Intro_Oper_User_Id IS NULL or Intro_Oper_User_Id = '', Dyna_Nom_Prin * 0, Dyna_Nom_Prin * 0.6) AS Dyna_Nom_Prin_Intro,
    Accum_Dyna_Nom_Prin,
    Absl_Nom_Prin,
    IF(Intro_Oper_User_Id IS NULL or Intro_Oper_User_Id = '', Absl_Nom_Prin * 1, Absl_Nom_Prin * 0.4) AS Absl_Nom_Prin_Main,
    IF(Intro_Oper_User_Id IS NULL or Intro_Oper_User_Id = '', Absl_Nom_Prin * 0, Absl_Nom_Prin * 0.6) AS Absl_Nom_Prin_Intro,
    Accum_Absl_Nom_Prin,
    Curr_Prvs_Sales_Income_n as Curr_Prvs_Sales_Income,
    Curr_Prvs_Sales_Income_n * Allo_Prop_1 AS Curr_Prvs_Sales_Income_1,
    Curr_Prvs_Sales_Income_n * Allo_Prop_2 AS Curr_Prvs_Sales_Income_2,
    Curr_Prvs_Sales_Income_n * Allo_Prop_3 AS Curr_Prvs_Sales_Income_3,
    Strt_Pric_Date,
    End_Pric_Date,
    Strt_Pric_Date as Accrued_Strt_Date,
    Accrued_End_Date,
    Earn_Pymt_Date,
    datediff(if(Accrued_Date > End_Pric_Date, End_Pric_Date, Accrued_Date), Strt_Pric_Date) + 1 AS Actl_Days,  --实际天数应该要包含头尾的？包括日均动态、绝对名义本金也是按照包含头尾的？
    IF(Early_Term_Date IS NULL OR Early_Term_Date = '', '0', '1') AS Is_Preterm_Flag,
    Early_Term_Date,
    Agt_Stat_Cd,
    Main_Oper_User_Id,
    Main_Oper_Name,
    Main_Oper_Emp_Id,
    Intro_Oper_User_Id,
    Intro_Oper_Name,
    Intro_Oper_Emp_Id,
    Intro_Inr_Org_Id_1,
    Intro_Inr_Org_Name_1,
    Div_Org_Id_1,
    Div_Org_Name_1,
    Cust_Mngr_User_Id_1,
    Cust_Mngr_Name_1,
    Cust_Mngr_Emp_Id_1,
    Allo_Prop_1,
    Intro_Inr_Org_Id_2,
    Intro_Inr_Org_Name_2,
    Div_Org_Id_2,
    Div_Org_Name_2,
    Cust_Mngr_User_Id_2,
    Cust_Mngr_Name_2,
    Cust_Mngr_Emp_Id_2,
    Allo_Prop_2,
    Intro_Inr_Org_Id_3,
    Intro_Inr_Org_Name_3,
    Div_Org_Id_3,
    Div_Org_Name_3,
    Cust_Mngr_User_Id_3,
    Cust_Mngr_Name_3,
    Cust_Mngr_Emp_Id_3,
    Allo_Prop_3,
    Accrued_Date,
    from_unixtime(unix_timestamp(),'yyyy-MM-dd HH:mm:ss') AS Data_Time,
    default.gfgreatest(sum(coalesce(Curr_Prvs_Sales_Income_n, 0)) over(partition by agt_id,Contr_Type_Cd order by accrued_date),0) as Accum_prvs_sales_income,
    default.gfgreatest(sum(coalesce(Curr_Prvs_Sales_Income_n * Allo_Prop_1, 0)) over(partition by agt_id,Contr_Type_Cd order by accrued_date),0) as Accum_prvs_sales_income_1,
    default.gfgreatest(sum(coalesce(Curr_Prvs_Sales_Income_n * Allo_Prop_2, 0)) over(partition by agt_id,Contr_Type_Cd order by accrued_date),0) as Accum_prvs_sales_income_2,
    default.gfgreatest(sum(coalesce(Curr_Prvs_Sales_Income_n * Allo_Prop_3, 0)) over(partition by agt_id,Contr_Type_Cd order by accrued_date),0) as Accum_prvs_sales_income_3,
    Adtnl_Rwd,
    if(Src_Contr_Type in ('AIRBAGX','AIRBAGM','AIRBAGL'), fee_rate, null) as fee_rate,
    if(Src_Contr_Type in ('AIRBAGX','AIRBAGM','AIRBAGL'), Fin_Rati, null) as Fin_Rati,
    Intr_Marg,
    Res_Flag,
    Opt_Fee_Rate,
    Ex_Rate_Model,
    Cust_Mngr_Is_Actv_1,  -- 客户经理是否在职_1
    Cust_Mngr_Is_Actv_2,  -- 客户经理是否在职_2
    Cust_Mngr_Is_Actv_3,  -- 客户经理是否在职_3
    '${yyyy-MM-dd}' as busi_date
from (
    select T.*,
        case
            --金仕达分摊150万的系统费用
            when Contr_Type_Cd = 'TRS_KINGSTAR_SWAP' then Curr_Prvs_Sales_Income - Curr_Prvs_Sales_Income/sum(Curr_Prvs_Sales_Income) over(partition by Contr_Type_Cd, Accrued_Date) * 1500000 / 365 * 0.5
            -- 个股期权、指数/ETF期权考虑保底，保底系数0.1%
            -- 累计实发+当季应发 < 保底应发，取保底应发-累计实发
            when Contr_Type_Cd in('OPTION_STOCK', 'OPTION_IDX_ETF')
                and End_Pric_Date = Accrued_Date
                and coalesce(sum(Curr_Prvs_Sales_Income) over(partition by Agt_Id order by Accrued_Date),0) < Init_Nom_Prin * 0.001
                    then Init_Nom_Prin * 0.001 - coalesce(actl.Dev_Dept_Rwd, 0) - sum(if(Accrued_Date > coalesce(actl.Qtr_End_Date,'2025-03-31'), Curr_Prvs_Sales_Income,0)) over(partition by Agt_Id) + Curr_Prvs_Sales_Income
            else Curr_Prvs_Sales_Income
            end as Curr_Prvs_Sales_Income_n
    from (
        select
            info.Agt_Id,
            info.Busi_Type,
            info.Cutp_Pty_Id,
            info.Cutp_Pty_Shor_Name,
            info.Cutp_Pty_Full_Name,
            info.Sign_Prd_Name,
            info.Contr_Type_Cd,
            info.Contr_Type_Desc,
            info.Src_Contr_Type,
            info.Src_Contr_Type_Desc,
            info.Src_Sub_Contr_Type,
            info.Src_Sub_Contr_Type_Desc,
            '' as Undrl_Ins_Id,
            info.Undrl_Wd_Cd,
            info.Undrl_Name,
            info.Undrl_Type,
            info.Src_Undrl_Type,
            IF(coalesce(s_sp.Spread_Calculation, c_sp.Spread_Calculation) = 'ANNUALIZED', coalesce(s_sp.Annualized_Spread, c_sp.Annualized_Spread), '') AS Annu_Sprd,
            IF(coalesce(s_sp.Spread_Calculation, c_sp.Spread_Calculation) = 'ABSOLUTE', coalesce(s_sp.Absolute_Spread, c_sp.Absolute_Spread), '') AS Absl_Sprd,
            IF(coalesce(s_ba.BASE_CALCULATION, c_ba.BASE_CALCULATION) = 'ANNUALIZED', coalesce(s_ba.BASE_AWARD_RATE, c_ba.BASE_AWARD_RATE), '') AS Annu_Base,
            IF(coalesce(s_ba.BASE_CALCULATION, c_ba.BASE_CALCULATION) = 'ABSOLUTE', coalesce(s_ba.BASE_AWARD_RATE, c_ba.BASE_AWARD_RATE), '') AS Absl_Base,
            info.Init_Nom_Prin,
            coalesce(det.Dyna_Nom_Prin, 0) as Dyna_Nom_Prin,
            sum(if(det.busi_date BETWEEN info.Strt_Pric_Date AND coalesce(info.Early_Term_Date, info.End_Pric_Date), coalesce(det.Dyna_Nom_Prin, 0),0)) over(partition by info.agt_id,info.Contr_Type_Cd order by det.busi_date) as Accum_Dyna_Nom_Prin,
            if(info.grp_id = '01', det.Dyna_Nom_Prin, 0) as Absl_Nom_Prin,
            sum(if(det.busi_date BETWEEN info.Strt_Pric_Date AND coalesce(info.Early_Term_Date, info.End_Pric_Date), coalesce(det.Dyna_Nom_Prin, 0),0)) over(partition by info.agt_id,info.Contr_Type_Cd order by det.busi_date) as Accum_Absl_Nom_Prin,
            case when info.Src_Contr_Type in ('AIRBAGX','AIRBAGM','AIRBAGL') and Ddct_Ptrn = 'DEDUCTION' then 0  --抵扣则为0
                 when info.Src_Contr_Type in ('AIRBAGX','AIRBAGM','AIRBAGL') and coalesce(Ddct_Ptrn,'') != 'DEDUCTION' and coalesce(info.Marg_Agt_Id,'') = '' then det.Dyna_Nom_Prin * (1 - Init_Marg_Prop) * (det.fee_rate/1.06 - cc.capital_cost) / 365 * 0.3
                 when info.Src_Contr_Type in ('AIRBAGX','AIRBAGM','AIRBAGL') and coalesce(Ddct_Ptrn,'') != 'DEDUCTION' and coalesce(info.Marg_Agt_Id,'') != '' then det.Dyna_Nom_Prin * (1 - Base_Marg_Rate) * (det.fee_rate*(1 - Init_Marg_Prop)/(1 - Base_Marg_Rate)/1.06 - cc.capital_cost) /365 *0.3
                 when info.Src_Contr_Type = 'LONG_HOLD_SWAP' and coalesce(info.Marg_Agt_Id,'') != '' then 0
                 when info.Contr_Type_Cd = 'TRS_KINGSTAR_SWAP' then (det.Inta * 0.94 + det.Trd_Cms - det.Trd_Cms_Cost - det.Fnd_Cost * cc.capital_cost/365) * 0.5
                 when info.Busi_Type = 'OPTION' and coalesce(s_sp.Spread_Calculation, c_sp.Spread_Calculation, 'ABSOLUTE') = 'ANNUALIZED' and coalesce(s_ba.BASE_CALCULATION, c_ba.BASE_CALCULATION) = 'ANNUALIZED'
                        then IF(det.busi_date BETWEEN info.Strt_Pric_Date AND coalesce(info.Early_Term_Date, info.End_Pric_Date), det.Dyna_Nom_Prin * coalesce(s_sp.Annualized_Spread, c_sp.Annualized_Spread, 0) / 365 + det.Dyna_Nom_Prin * coalesce(s_ba.BASE_AWARD_RATE, c_ba.BASE_AWARD_RATE, 0) / 365, 0)
                 when info.Busi_Type = 'OPTION' and coalesce(s_sp.Spread_Calculation, c_sp.Spread_Calculation, 'ABSOLUTE') = 'ANNUALIZED' and coalesce(s_ba.BASE_CALCULATION, c_ba.BASE_CALCULATION) = 'ABSOLUTE'
                        then IF(det.busi_date BETWEEN info.Strt_Pric_Date AND coalesce(info.Early_Term_Date, info.End_Pric_Date), det.Dyna_Nom_Prin * coalesce(s_sp.Annualized_Spread, c_sp.Annualized_Spread, 0) / 365, 0) + IF(det.busi_date = info.Strt_Pric_Date, info.Init_Nom_Prin * coalesce(s_ba.BASE_AWARD_RATE, c_ba.BASE_AWARD_RATE, 0), 0)
                 when info.Busi_Type = 'OPTION' and coalesce(s_sp.Spread_Calculation, c_sp.Spread_Calculation, 'ABSOLUTE') = 'ABSOLUTE' and coalesce(s_ba.BASE_CALCULATION, c_ba.BASE_CALCULATION) = 'ANNUALIZED'
                        then IF(det.busi_date = info.Strt_Pric_Date, info.Init_Nom_Prin * coalesce(s_sp.Absolute_Spread, c_sp.Absolute_Spread, 0), 0) + IF(det.busi_date BETWEEN info.Strt_Pric_Date AND coalesce(info.Early_Term_Date, info.End_Pric_Date), det.Dyna_Nom_Prin * coalesce(s_ba.BASE_AWARD_RATE, c_ba.BASE_AWARD_RATE, 0) / 365, 0)
                 when info.Busi_Type = 'OPTION' and coalesce(s_sp.Spread_Calculation, c_sp.Spread_Calculation, 'ABSOLUTE') = 'ABSOLUTE' and coalesce(s_ba.BASE_CALCULATION, c_ba.BASE_CALCULATION) = 'ABSOLUTE'
                        then IF(det.busi_date = info.Strt_Pric_Date, info.Init_Nom_Prin * coalesce(s_sp.Absolute_Spread, c_sp.Absolute_Spread, 0), 0) + IF(det.busi_date = info.Strt_Pric_Date, info.Init_Nom_Prin * coalesce(s_ba.BASE_AWARD_RATE, c_ba.BASE_AWARD_RATE, 0), 0)
                 when info.Busi_Type = 'TRS' and coalesce(s_sp.Spread_Calculation, c_sp.Spread_Calculation, 'ABSOLUTE') = 'ANNUALIZED' and coalesce(s_ba.BASE_CALCULATION, c_ba.BASE_CALCULATION) = 'ANNUALIZED'
                        then IF(det.busi_date BETWEEN info.Strt_Pric_Date AND coalesce(info.Early_Term_Date, info.End_Pric_Date), det.Dyna_Nom_Prin * coalesce(s_sp.Annualized_Spread, c_sp.Annualized_Spread, 0) / 365 + det.Dyna_Nom_Prin * coalesce(s_ba.BASE_AWARD_RATE, c_ba.BASE_AWARD_RATE, 0) / 365, 0)
                 when info.Busi_Type = 'TRS' and coalesce(s_sp.Spread_Calculation, c_sp.Spread_Calculation, 'ABSOLUTE') = 'ANNUALIZED' and coalesce(s_ba.BASE_CALCULATION, c_ba.BASE_CALCULATION) = 'ABSOLUTE'
                        then IF(det.busi_date BETWEEN info.Strt_Pric_Date AND coalesce(info.Early_Term_Date, info.End_Pric_Date), det.Dyna_Nom_Prin * coalesce(s_sp.Annualized_Spread, c_sp.Annualized_Spread, 0) / 365, 0) + IF(det.busi_date = info.Strt_Pric_Date, info.Init_Nom_Prin * coalesce(s_ba.BASE_AWARD_RATE, c_ba.BASE_AWARD_RATE, 0), 0)
                 when info.Busi_Type = 'TRS' and coalesce(s_sp.Spread_Calculation, c_sp.Spread_Calculation, 'ABSOLUTE') = 'ABSOLUTE' and coalesce(s_ba.BASE_CALCULATION, c_ba.BASE_CALCULATION) = 'ANNUALIZED'
                        then IF(det.busi_date = info.Strt_Pric_Date, info.Init_Nom_Prin * coalesce(s_sp.Absolute_Spread, c_sp.Absolute_Spread, 0), 0) + IF(det.busi_date BETWEEN info.Strt_Pric_Date AND coalesce(info.Early_Term_Date, info.End_Pric_Date), det.Dyna_Nom_Prin * coalesce(s_ba.BASE_AWARD_RATE, c_ba.BASE_AWARD_RATE, 0) / 365, 0)
                 when info.Busi_Type = 'TRS' and coalesce(s_sp.Spread_Calculation, c_sp.Spread_Calculation, 'ABSOLUTE') = 'ABSOLUTE' and coalesce(s_ba.BASE_CALCULATION, c_ba.BASE_CALCULATION) = 'ABSOLUTE'
                        then IF(det.busi_date = info.Strt_Pric_Date, info.Init_Nom_Prin * coalesce(s_sp.Absolute_Spread, c_sp.Absolute_Spread, 0), 0) + IF(det.busi_date = info.Strt_Pric_Date, info.Init_Nom_Prin * coalesce(s_ba.BASE_AWARD_RATE, c_ba.BASE_AWARD_RATE, 0), 0)
                 END AS Curr_Prvs_Sales_Income,
            info.Strt_Pric_Date,
            coalesce(info.Early_Term_Date, info.End_Pric_Date) as End_Pric_Date,
            info.Strt_Pric_Date as Accrued_Strt_Date,
            coalesce(info.Early_Term_Date, info.End_Pric_Date) as Accrued_End_Date,
            info.Early_Term_Date,
            info.Earn_Pymt_Date,
            info.Agt_Stat_Cd,
            m.Main_Oper_User_Id,
            m.Main_Oper_Name,
            m.Main_Oper_Emp_Id,
            m.Intro_Oper_User_Id,
            m.Intro_Oper_Name,
            m.Intro_Oper_Emp_Id,
            m.Inr_Org_Id_1 as Intro_Inr_Org_Id_1,
            m.Inr_Org_Name_1 as Intro_Inr_Org_Name_1,
            m.Div_Org_Id_1,
            m.Div_Org_Name_1,
            m.Cust_Mngr_User_Id_1,
            m.Cust_Mngr_Name_1,
            m.Cust_Mngr_Emp_Id_1,
            m.Allo_Prop_1,
            m.Inr_Org_Id_2 as Intro_Inr_Org_Id_2,
            m.Inr_Org_Name_2 as Intro_Inr_Org_Name_2,
            m.Div_Org_Id_2,
            m.Div_Org_Name_2,
            m.Cust_Mngr_User_Id_2,
            m.Cust_Mngr_Name_2,
            m.Cust_Mngr_Emp_Id_2,
            m.Allo_Prop_2,
            m.Inr_Org_Id_3 as Intro_Inr_Org_Id_3,
            m.Inr_Org_Name_3 as Intro_Inr_Org_Name_3,
            m.Div_Org_Id_3,
            m.Div_Org_Name_3,
            m.Cust_Mngr_User_Id_3,
            m.Cust_Mngr_Name_3,
            m.Cust_Mngr_Emp_Id_3,
            m.Allo_Prop_3,
            det.busi_date as Accrued_Date,
            coalesce(Additional_Reward,0) as Adtnl_Rwd,
            det.fee_rate,
            1 - info.Init_Marg_Prop as Fin_Rati,
            info.Intr_Marg,
            info.Res_Flag,
            info.Opt_Fee_Rate,
            if(info.Ex_Rate_Model in ('SHENZHEN_HONGKONG_STOCK_CONNECT','SHANGHAI_HONGKONG_STOCK_CONNECT'),info.Ex_Rate_Model,null) as Ex_Rate_Model,
            if(nvl(m.Cust_Mngr_Emp_Stat_Desc_1, '') = '', m.Cust_Mngr_Emp_Stat_Desc_1, if(m.Cust_Mngr_Emp_Stat_Desc_1 = '在职', '是', '否')) as Cust_Mngr_Is_Actv_1,  -- 客户经理是否在职_1
            if(nvl(m.Cust_Mngr_Emp_Stat_Desc_2, '') = '', m.Cust_Mngr_Emp_Stat_Desc_2, if(m.Cust_Mngr_Emp_Stat_Desc_2 = '在职', '是', '否')) as Cust_Mngr_Is_Actv_2,  -- 客户经理是否在职_2
            if(nvl(m.Cust_Mngr_Emp_Stat_Desc_3, '') = '', m.Cust_Mngr_Emp_Stat_Desc_3, if(m.Cust_Mngr_Emp_Stat_Desc_3 = '在职', '是', '否')) as Cust_Mngr_Is_Actv_3   -- 客户经理是否在职_3
        from (
            select * from PDATA_N.T98_OTC_DERI_COMP_SALE_INFO
            where busi_date = '${yyyy-MM-dd}' and Src_Contr_Type != 'FEE_SWAP'  --销售收入不计算“费用互换”
                and grp_id != '04' and Book_Bel_Dept != 'OTC_HK'  --极速合约暂不计算，香港合约单独计算
            ) info
        inner join PDATA_N.T98_OTC_DERI_COMP_SALE_ADTNL_DET det
        on info.agt_id = det.agt_id
        left join (
            select
                Contract_Code,
                Spread_Calculation,
                Annualized_Spread,
                Absolute_Spread,
                date_add(strt_date, pos) as busi_date
            from (
                select
                    Inr_Comp_No as Contract_Code,
                    if(Sprd_Calc_Type = '', null, Sprd_Calc_Type) as Spread_Calculation,
                    Annu_Sprd_Coef as Annualized_Spread,
                    Absl_Sprd_Coef as Absolute_Spread,
                    Vld_Date as strt_date,
                    date_sub(lead(Vld_Date, 1, date_add('${yyyy-MM-dd}', 1)) over(partition by Inr_Comp_No order by Vld_Date), 1) as end_Date
                from PDATA_N.T99_DERI_COMP_SPRD_COEF_REF
                where src_tbl = 'ODATA_N_OIS.O_CONTRACT_SPREAD_RATE' and Del_Flag = '0' and coalesce(Coef_Type, '') != 'INR' and Agt_Id != ''
                ) x
            lateral view posexplode(split(space(datediff(end_date, strt_date)), ' ')) y as pos, val
            ) s_sp
        on s_sp.CONTRACT_CODE = info.Agt_Id and s_sp.busi_date = det.busi_date
        left join (
            select
                CLIENT_ID,
                CONTRACT_TYPE,
                CONTRACT_TYPE_NAME,
                Spread_Calculation,
                Annualized_Spread,
                Absolute_Spread,
                date_add(strt_date, pos) as busi_date
            from (
                select
                    Pty_Id as CLIENT_ID,
                    Src_Comp_Type_Cd as CONTRACT_TYPE,
                    Src_Comp_Type_Desc as CONTRACT_TYPE_NAME,
                    if(Calc_Type = '', null, Calc_Type) as Spread_Calculation,
                    Annu_Sprd_Coef as Annualized_Spread,
                    Absl_Sprd_Coef as Absolute_Spread,
                    if(Bgng_Prcg_Date_Llmt = '1900-01-01','2019-01-01',Bgng_Prcg_Date_Llmt) as strt_date,
                    if(Bgng_Prcg_Date_Ulmt = '2999-12-31','${yyyy-MM-dd}',Bgng_Prcg_Date_Ulmt) as end_Date
                from PDATA_N.T99_DERI_CUTP_COMP_TYPE_SPRD_COEF_REF
                where src_tbl = 'ODATA_N_OIS.O_CTPTY_CROSS_SELL_COEFFICIENT' and Del_Flag = '0'
                ) x
            lateral view posexplode(split(space(datediff(end_date, strt_date)), ' ')) y as pos, val
            ) c_sp
        on c_sp.CLIENT_ID = info.Cutp_Pty_Id and c_sp.CONTRACT_TYPE = info.Contr_Type_Cd and c_sp.busi_date = info.Strt_Pric_Date
        left join (
            select
                Inr_Comp_No as Contract_Code,
                Calc_Type as BASE_CALCULATION,
                Base_Yield as BASE_AWARD_RATE,
                if(Adtnl_Rwd = '', 0, Adtnl_Rwd) as additional_reward,
                Adtnl_Rwd_Flag as have_additional_reward
            from PDATA_N.T99_DERI_COMP_BASE_COEF_REF
            where src_tbl = 'ODATA_N_OIS.O_CONTRACT_BASE_RATE' and Del_Flag = '0' and Agt_Id != ''
            ) s_ba
        on s_ba.CONTRACT_CODE = info.Agt_Id
        left join (
            select
                CONTRACT_TYPE,
                CONTRACT_TYPE_NAME,
                BASE_CALCULATION,
                BASE_AWARD_RATE,
                date_add(strt_date, pos) as busi_date
            from (
                select
                    Src_Comp_Type_Cd as CONTRACT_TYPE,
                    Src_Comp_Type_Desc as CONTRACT_TYPE_NAME,
                    Calc_Type as BASE_CALCULATION,
                    Base_Yield as BASE_AWARD_RATE,
                    if(Bgng_Prcg_Date_Llmt = '1900-01-01','2019-01-01',Bgng_Prcg_Date_Llmt) as strt_date,
                    if(Bgng_Prcg_Date_Ulmt = '2999-12-31','${yyyy-MM-dd}',Bgng_Prcg_Date_Ulmt) as end_Date
                from PDATA_N.T99_DERI_COMP_TYPE_BASE_COEF_REF
                where src_tbl = 'ODATA_N_OIS.O_BUS_TYPE_BASE_RATE' and Del_Flag = '0' and Src_Dept_No = 'OTC'
                ) x
            lateral view posexplode(split(space(datediff(end_date, strt_date)), ' ')) y as pos, val
            ) c_ba
        on c_ba.CONTRACT_TYPE = info.Contr_Type_Cd and c_ba.busi_date = info.Strt_Pric_Date        
        left join (
            select
                CONTRACT_TYPE,
                CAPITAL_COST,
                date_add(strt_date, pos) as busi_date
            from (
                select
                    Src_Comp_Type_Cd as CONTRACT_TYPE,
                    Fnd_Cost as CAPITAL_COST,
                    if(Intr_Strt_Date = '1900-01-01','2019-01-01',Intr_Strt_Date) as strt_date,
                    if(Intr_End_Date = '2999-12-31','${yyyy-MM-dd}',Intr_End_Date) as end_Date
                from PDATA_N.T99_DERI_COMP_TYPE_FND_COST_REF
                where src_tbl = 'ODATA_N_OIS.G_BUS_TYPE_CAPITAL_COST' and Del_Flag = '0' and Src_Dept_No = 'OTC'
                ) x
            lateral view posexplode(split(space(datediff(end_date, strt_date)), ' ')) y as pos, val
            ) cc
        on cc.CONTRACT_TYPE = info.Contr_Type_Cd and cc.busi_date = info.Strt_Pric_Date
        left join (
            select * from PDATA_N.T98_OTC_COMP_MNG_RELA_INFO
            where busi_Date = '${yyyy-MM-dd}'
            ) m
        on m.Agt_Id = info.Agt_Id
        where coalesce(if(m.Inr_Org_Id_1 = '', '8846', m.Inr_Org_Id_1), '8846') != '8846' or coalesce(if(m.Inr_Org_Id_2 = '', '8846', m.Inr_Org_Id_2), '8846') != '8846' or coalesce(if(m.Inr_Org_Id_3 = '', '8846', m.Inr_Org_Id_3), '8846') != '8846'
            or info.agt_id in ('OPT-OTC20220163','OPT-OTC20220128','OPT-OTC20220148','OPT-OTC20220162','OPT-OTC20220153','OPT-OTC20220089-1','OPT-OTC20220155','OPT-OTC20220126','OPT-OTC20220147','OPT-OTC20220129')
        ) T
    left join(
        -- 累计实发收入
        select
            Contr_Id,
            sum(Dev_Dept_Rwd) as Dev_Dept_Rwd,
            max(Sett_End_Date) as Qtr_End_Date
        from PDATA_N.T98_OTC_DERI_UNDRL_INCOME_RWD_SUM
        where busi_date = '${yyyy-MM-dd}' and src_tbl = 'ODATA_N_OIS.G_CROSS_INCOME_REWARD'
            and Sett_Time >= '202502' and Sett_Time < concat('${yyyy}0', quarter('${yyyy-MM-dd}'))
        group by Contr_Id
        ) actl
    on t.Agt_Id = actl.Contr_Id and actl.Qtr_End_Date < t.End_Pric_Date
    ) X 
	) castTable