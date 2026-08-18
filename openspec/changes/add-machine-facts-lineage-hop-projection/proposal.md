## Why

Machine Facts 当前只保存物理 Base Origin 到字段表达式的来源摘要，没有投影 `sql-static-lineage` 已实现的逐跳 `LineageHop` DAG。这使 Query Consumer 无法直接解释字段经过的 CTE、子查询、计算、改名、Star 展开和 Setop 分支，只能重新猜测或重跑分析。

## What Changes

- 在每个 Task Machine Facts Bundle 中增加版本化的 `lineage-hop-roots.jsonl`、`lineage-hop-nodes.jsonl` 和 `lineage-hop-edges.jsonl`。
- 直接投影原生 `LineageHop`：保留计算 Hop、物理 Terminal、DAG 共享、Setop 分支以及 Hop 级 `rename/expand` via trail，不由 Relation Facts 重构近似路径。
- 保留现有 `column-lineage-edges.jsonl` 的 Base-Origin 摘要语义，并通过守恒 Gate 验证可评测 Root 的 Hop Terminal 与现有物理来源一致。
- 显式保留 `FULL_HOP`、`FLAT_ORIGIN_ONLY`、`UNKNOWN_COVERAGE` 和 `NOT_EVALUABLE` 覆盖状态；不为最终 Star Expansion、Scalar/EXISTS 内部路径或不支持结构伪造 Hop。
- 更新 Machine Facts TypeScript Contract、JSON Schema、Manifest 计数/Gate、端点与 DAG Validator、OpenSpec 和回归 Fixture；方法版本变化后重建旧 Bundle。
- 该路径只表达 `VALUE_LINEAGE`；Filter、Join、Group By 对行集的影响仍由 Relation/Expression Facts 表达，不将 Hop 冒充为完整业务因果图。

## Capabilities

### New Capabilities

- `machine-facts-lineage-hop-projection`: 定义任务内原生逐跳字段传播事实、覆盖/降级状态、稳定身份、守恒验证和 Bundle 发布契约。

### Modified Capabilities

<!-- None. The reusable SQL Machine Facts change is complete but not yet archived into main specs. -->

## Impact

- 影响 `sql-static-lineage/scripts/plans/plan-adapter.ts`、Plan/Machine Facts contracts、Machine Facts writer/validator、JSON Schema、测试和 SQL 分析文档。
- 新增 Task Bundle 文件和 Manifest 记录，但不改变现有 Base-Origin 边和 Output Binding 的方向与语义。
- 不引入新数据库、外部调用、业务数据行、LLM 或调度执行。
