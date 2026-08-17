CREATE TABLE IF NOT EXISTS T05_OTC_COMP_RGST_SAC_EVT(
Evt_Id                     STRING COMMENT '事件编号'
,Otc_Comp_Agt_Id            STRING COMMENT '场外合约协议编号'
,Otc_Comp_Agt_Modifr        STRING COMMENT '场外合约协议修饰符'
,Actl_Sett_Date             STRING COMMENT '实际结算日期'
,Sac_Rgst_Cd                STRING COMMENT '证协报备编号'
,Rgst_Date                  STRING COMMENT '报备日期'
,New_Rgst_Due_Date          STRING COMMENT '新增报备日期'
,Trmt_Rgst_Due_Date         STRING COMMENT '终止报备日期'
,New_Rgst_Due_Date_Dbl      STRING COMMENT '新增报备日期_双印版'
,Rgst_Stat_Cd               STRING COMMENT '报备状态代码'
,Attach_Rgst_Stat_Cd        STRING COMMENT '附件报备状态代码'
,Data_Src_Cd                STRING COMMENT '数据来源代码'
,Task_Name                  STRING COMMENT '任务名'
,Data_Etl_Date              STRING COMMENT '数据加载日期'
,Data_Upt_Date              STRING COMMENT '数据更新日期'
,Data_Time                  STRING COMMENT '数据时间'
,Real_Src_Tbl               STRING COMMENT '真实源表'
,Renw_Flag                  STRING COMMENT '展期标志'
,Rgst_Maty_Date             STRING COMMENT '报备到期日期'
)COMMENT '场外合约报备中国证协事件'
PARTITIONED BY (SRC_TBL  STRING COMMENT'源表')
STORED AS ORC;
INSERT OVERWRITE TABLE T05_OTC_COMP_RGST_SAC_EVT PARTITION(SRC_TBL='ODATA_N_TIT.D_TRD_OTC_CONTR_REPORT')
SELECT
CONCAT('TIT184-',A.KEY_OTC_TRADE_ID)
AS  Evt_Id                  --事件编号
,A.KEY_OTC_TRADE_ID                      AS  Otc_Comp_Agt_Id         --场外合约协议编号
,CASE WHEN B.KEY_OTC_TRADE_ID IS NOT NULL THEN '20206'
WHEN C.KEY_OTC_TRADE_ID IS NOT NULL THEN '20207'
ELSE '' END                      AS  Otc_Comp_Agt_Modifr     --场外合约协议修饰符
,SUBSTR(ACTUAL_SETTLEMENT_DATE,1,10)   AS  Actl_Sett_Date          --实际结算日期
,INTEROTC_CODE                         AS  Sac_Rgst_Cd             --证协报备编号
,SUBSTR(REPORT_DATE,1,10)              AS  Rgst_Date               --报备日期
,SUBSTR(NEW_REPORT_DEADLINE,1,10)      AS  New_Rgst_Due_Date       --新增报备日期
,SUBSTR(TERMINATE_REPORT_DEALLINE,1,10)AS  Trmt_Rgst_Due_Date      --终止报备日期
,SUBSTR(NEW_DOUBLE_DEADLINE,1,10)      AS  New_Rgst_Due_Date_Dbl   --新增报备日期_双印版
,REPORT_STATUS                         AS  Rgst_Stat_Cd            --报备状态代码
,FILE_REPORT_STATUS                    AS  Attach_Rgst_Stat_Cd     --附件报备状态代码
,'TIT'                 AS  Data_Src_Cd             --数据来源代码
,'PDATA_N.T05_OTC_COMP_RGST_SAC_EVT_TIT184_KXC'                    AS  Task_Name               --任务名
,'2026-05-18'                AS  Data_Etl_Date           --数据加载日期
,'2026-05-19'              AS  Data_Upt_Date           --数据更新日期
,'2026-05-19 02:18:06'                  AS  Data_Time               --数据时间
,'ODATA_N_TIT.D_TRD_OTC_CONTR_REPORT'                   AS  Real_Src_Tbl            --真实源表
,CASE WHEN HAS_ROLLOVERED ='Y'  THEN '1'
WHEN HAS_ROLLOVERED ='N'  THEN '0'
ELSE HAS_ROLLOVERED  END         AS  Renw_Flag              --展期标志
,SUBSTR(REPORT_END_DATE,1,10)          AS  Rgst_Maty_Date         --报备到期日期
FROM   (SELECT *  FROM ODATA_N_TIT.D_TRD_OTC_CONTR_REPORT WHERE  BUSI_DATE='2026-05-18' )A
LEFT JOIN (SELECT KEY_OTC_TRADE_ID FROM ODATA_N_TIT.D_REF_TRS  WHERE BUSI_DATE ='2026-05-18'  )B
ON A.KEY_OTC_TRADE_ID=B.KEY_OTC_TRADE_ID
LEFT JOIN (SELECT KEY_OTC_TRADE_ID FROM ODATA_N_TIT.D_REF_OTC_OPTION_DEAL  WHERE BUSI_DATE ='2026-05-18'  )C
ON A.KEY_OTC_TRADE_ID=C.KEY_OTC_TRADE_ID
;