# Golden Case 001 —— 任务 118141 全量表编码 SQL

**固定日期**: 2026-08-15
**用途**: Logical Plan Facts adapter 的回归基准 (SQL → sql-static-lineage → plan-facts-118141.json)
**来源**: `.evidence-cache/tasksql-118141-20260814.txt` (Horae 调度任务 SQL, TITANS_TRADEFLOW 基线)
**方言**: databricks (Spark), 含 minijinja 模板参数 `${yyyy-MM-dd}`
**契约**: v1.1 (meta.contract_version=1.1.0, adapter=0.2.0, parser=sql-static-lineage 1.8.0)

## 文件

- `sql.txt` —— SQL 原文副本 (独立于 evidence-cache, 防缓存被清后丢失)
- `plan-facts.json` —— adapter 基准输出 (`{ plan, grain_inference }`)
- schema 来源: szdata table-ddl 实测 (pdata_n 库: info 92列 / det 23列(21普通+2分区) /
  m 60列(59普通+1分区)), 其余 6 表为显式列子查询无需 schema —— `scripts/plans/schema-118141.ts`

## 重跑命令

```bash
cd sql-static-lineage
npx tsx scripts/plans/plan-118141.ts          # 重新生成 output/118141/plan-facts-118141.json
npx tsx scripts/verification/verify-golden.ts # 结构回归；忽略易变 generated_at
# 除 generated_at 外，任何节点级差异都需说明
```

## 固定断言 (adapter 回归点)

1. **结构**: 47 个关系节点, 4 层嵌套 (root → casttable → x → t), 9 张物理表
2. **JOIN 链 (t 层)**: `join.1`(inner, det) + `join.2..7`(left, s_sp/c_sp/s_ba/c_ba/cc/m),
   左深链: left 逐级引用前节点, right 引用各子查询的 project 根
3. **lateral 行扩展**: 4 个 expand 节点 (s_sp/c_sp/c_ba/cc 的 `y`), 挂接在
   各自链尾之后 (不是 join), 产生列非空
4. **聚合 (actl)**: `aggregate` 节点 GROUP BY `Contr_Id`, measures = `sum(Dev_Dept_Rwd)`
   + `max(Sett_End_Date)`
5. **star 展开**: 3 处 star 全部展开 —— `info.project` 92 列 / `m.project` 60 列
   (schema 列清单), `x.project` 76 列 (`T.*` → 子查询输出列传播); 无 star 残留
   unknown, unknowns=3 (c_sp/c_ba/cc 的 `busi_date` lateral 盲区)
6. **condition_columns 精确性** (每个 join 只列自己的 ON 列):
   - `join.1`: `agt_id`(info) / `agt_id`(det) —— 2 列
   - `join.2`: CONTRACT_CODE/Agt_Id/busi_date/busi_date —— 4 列 (s_sp/info/s_sp/det)
   - `x.join.1`: Agt_Id/Contr_Id/Qtr_End_Date/End_Pric_Date —— 4 列 (t/actl/actl/t)
7. **machine truth 不截断**: 所有 `*_expr` / `expr_text` 字段为完整原文 (无 …);
   截断预期仅出现在 `*_display` / `display_text` (≤ 20 字符, 全量 20 条)
8. **条件列物理解析** (给 schema 后): 57/60 列追到基表:
   - `join.1`: `info.agt_id → T98_OTC_DERI_COMP_SALE_INFO.agt_id`、
     `det.agt_id → T98_OTC_DERI_COMP_SALE_ADTNL_DET.agt_id`
   - `join.2`: `s_sp.CONTRACT_CODE → T99_DERI_COMP_SPRD_COEF_REF.Inr_Comp_No`
     (穿透子查询别名到基表列)
   - `x.join.1`: `actl.Contr_Id → T98_OTC_DERI_UNDRL_INCOME_RWD_SUM.Contr_Id`、
     `actl.Qtr_End_Date → ...Sett_End_Date`、`t.End_Pric_Date → [Early_Term_Date,
     End_Pric_Date]` (多源数组, coalesce 双分支)
   - 3 列未解析 (c_sp/c_ba/cc 的 `busi_date`, sql-static-lineage followColumn 对 lateral
     子查询别名列盲区) → physical=null + unknowns 条目
9. **grain 传播** (aggregate 的 key 沿 plan 传播):
   - `actl.aggregate`: grain=["Contr_Id"], cardinality=non-increasing, confidence=high
   - `x.join.1` (t LEFT JOIN actl): **requires=[]** —— 右表 grain key [Contr_Id]
     由上游 GROUP BY 传播, 连接条件覆盖 → non-increasing/high, 无需外部元数据
   - 其余 join (右表无传播 grain, 如 det/m/s_ba): requires 精确到右表列
     (如 `join.1` → det.agt_id; `join.2` → s_sp.CONTRACT_CODE/busi_date)
   - 每个 read: requires = 该表 PK/UK 元数据
10. **expand fanout 模型** (不再用 non-decreasing):
    `cardinality=unknown` + `cardinality_effect=fanout` + `per_input_rows=0..N`
    + `grain_effect=expanded` (explode/posexplode 空集合/NULL 不产生行)

## 已知边界 (v1.1 不覆盖)

- read 节点 `columns` 恒为 null —— 需 qualify 展开 (v2)
- 条件列物理解析对 lateral 子查询别名列 (c_sp/c_ba/cc 的 busi_date) 为 null ——
  sql-static-lineage followColumn 盲区, unknowns 已显式记录
- span 为文档坐标 (cell.span.start 已平移, 可回到 SQL 原文验证;
  物理解析锚定在 cell 坐标 (nodeAt 裸数值比较) —— 见 plan-adapter.ts 注释)
