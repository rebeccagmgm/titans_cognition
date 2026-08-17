CREATE TABLE IF NOT EXISTS dm_index_n.index_grp1_CompScal_OtcDeriRgstComp_MthEnd( grp_id STRING COMMENT '组合ID',  index_val STRING COMMENT '指标值' , data_time STRING COMMENT '数据时间', modify_operator STRING COMMENT '修改人', modify_time STRING COMMENT '修改时间', status STRING COMMENT '状态 1：可用 0：已失效', index_id STRING COMMENT '指标代码' ) COMMENT '广发证券_合约规模_场外衍生品报备合约_当月月末' PARTITIONED BY ( busi_mon STRING COMMENT '业务月份', tag_id STRING COMMENT '标签ID' ) STORED AS ORC;
SELECT grp.grp_id AS grp_id, index.index_val, from_unixtime(unix_timestamp(),'yyyy-MM-dd HH:mm:ss'), 'wxgaoh' modify_operator, '2999-12-31 00:00:00' modify_time, '1' status, 'ind2024070561739587' index_id, index.busi_mon busi_mon, tag_id FROM (select
    '8888' as grp_val,
    'COMPANY' as grp_type_code,
    sum(a.dyna_nom_prin) as index_val,
    'tag999999999' as tag_id,
    '${yyyyMM}' as busi_mon
from (
    select * from PDATA_N.T98_OTC_DERI_COMP_SALE_INFO
    where busi_Date = '${yyyy-MM-dd}'
    ) a
left join (
    select * from PDATA_N.T05_OTC_COMP_RGST_SAC_EVT
    where src_tbl in ('ODATA_N_TIT.D_TRD_OTC_CONTR_REPORT','ODATA_N_TIT.D_KS_TRADE_COMFIRM_INFO') and Rgst_Stat_Cd = 'SKIP_REPORT'
    ) c
on a.Inr_Seri_No = c.Otc_Comp_Agt_Id
where c.Otc_Comp_Agt_Id is null
union all
select
    '8888' as grp_val,
    'COMPANY' as grp_type_code,
    sum(a.dyna_nom_prin) as index_val,
    t.tag_id,
    '${yyyyMM}' as busi_mon
from (
    select * from PDATA_N.T98_OTC_DERI_COMP_SALE_INFO
    where busi_Date = '${yyyy-MM-dd}'
    ) a
left join (
    select * from PDATA_N.T05_OTC_COMP_RGST_SAC_EVT
    where src_tbl in ('ODATA_N_TIT.D_TRD_OTC_CONTR_REPORT','ODATA_N_TIT.D_KS_TRADE_COMFIRM_INFO') and Rgst_Stat_Cd = 'SKIP_REPORT'
    ) c
on a.Inr_Seri_No = c.Otc_Comp_Agt_Id
left join (
    select * from dm_index_n.tag_def
    where tag_partition_id = 'tagdim101742'
    ) t
on t.dim_val = a.busi_type
where c.Otc_Comp_Agt_Id is null
group by t.tag_id
	) index JOIN (SELECT * FROM dm_index_n.grp_def WHERE status='1' AND grp_type_code IN ('COMPANY')) grp ON index.grp_type_code = (CASE WHEN grp.grp_type_code IN ('INDV_CUST','CORP_CUST') THEN 'CLIENT' ELSE grp.grp_type_code END) AND index.grp_val = grp.grp_val