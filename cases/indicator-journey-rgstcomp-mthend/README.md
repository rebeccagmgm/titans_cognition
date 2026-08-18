# 指标旅程小项目：grp1_CompScal_OtcDeriRgstComp_MthEnd

> 广发证券_合约规模_场外衍生品报备合约_当月月末_无备注信息（ind2024070561739587 / 任务 162610）

## 目标

用「先逆向、再正向」的方式彻底搞清楚该指标的完整逻辑，产出四件套：**端到端链路图 / 口径拐点表 / 名义本金指标族 / 影响清单**。

## 项目结构

```
cases/indicator-journey-rgstcomp-mthend/
├── indicator-card.yaml        # 指标卡片（快照基线、parsedCaliber 六要素）
├── scope.yaml                 # 案例范围（链路任务清单 + 证据路径）
├── journey-hops.yaml          # 7 跳链路（每跳任务/SQL变换/口径变化/证据）
└── caliber-inflections.yaml   # 口径拐点表 IF-01~IF-09 + openQuestions

sql-static-lineage/scripts/analysis/journey-rgstcomp-mthend.ts          # 列级血缘解析脚本（可复跑）
sql-static-lineage/output/118141/journey-rgstcomp-mthend-lineage.txt  # sql-static-lineage 解析输出

output/indicator-journey-rgstcomp-mthend/
├── indicator-table-lineage.json  # 指标表血缘（上游4表 + 下游1表）
└── journey-report.md             # ★ 主报告（四件套汇总）

scripts/extract-otc-family.py     # 指标族筛选脚本（快照 → 14 核心族）
```

## 复跑方式

```bash
# 1. 血缘解析（需要 sql-static-lineage 依赖）
npx tsx sql-static-lineage/scripts/analysis/journey-rgstcomp-mthend.ts

# 2. 指标族筛选（需要本地字典快照 20260812-refresh）
python scripts/extract-otc-family.py
```

## 结论速览

- **逻辑**：T98 快照（期权/互换/KS/极速互换四分组，动态名义本金，01/02 显式折算人民币）LEFT JOIN T05 剔除 `SKIP_REPORT` 无需报备合约 → `SUM(dyna_nom_prin)` → 组合 8888 广发证券，按 busi_mon 分区写指标表
- **最大风险点**：IF-03 分组 03/04 币种未显式折算（KS/极速互换若含外币合约则混币种）
- **下游**：唯一直接下游 `adm_sum_corp_oper_anlz_mth_otc`；同族 14 个指标共享 T98/T05 上游
