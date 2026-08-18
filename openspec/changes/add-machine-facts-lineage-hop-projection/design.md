## Context

见 `proposal.md` 的动机。当前 Machine Facts 已将 Project/Aggregate Field Expression、物理 Base Origin、Relation Topology 和 Output Binding 拆分为独立数据集。`src/lineage/hops.ts` 另有基于同一 binder 的内存 `LineageHop` DAG：Hop 引用原 IR/Scope/Projection，物理表是 Terminal，纯改名和 Star Descent 被折叠到 Hop 级 `via`，Setop 在分支处 fan-out 而没有 Setop Hop。

持久化必须在 Scope/Projection 对象仍存在时完成本地映射，并在 Writer 中转换为 Task/Statement 全局 ID。任何无法证明的映射、覆盖或守恒都必须降级，不得为了形成连续图而伪造节点。

## Goals / Non-Goals

**Goals:**

- 为每个已有 Project/Aggregate Field Expression 保存可查询的原生值传播 DAG。
- 保持原生 Hop、Terminal、via、Setop 分支与 DAG 共享语义。
- 使 Hop Terminal 与已有 Base-Origin 摘要可互相校验。
- 在不支持/不完整结构上保留可机读的降级状态。

**Non-Goals:**

- 不重写原生 LineageHop 算法，不由 Relation Facts 推测 Hop。
- 不将 Filter/Join/Group By 行集控制、Window 输入角色、Grain 或 Cardinality 写入 Hop 契约。
- 不为最终 Star Expansion 新建原生逐字段锚点；该能力是后续独立改动。
- 不把任务内 Hop 直接写成跨 Task 边或业务语义关系。

## Decisions

### 1. Hop 是 Task Bundle 内的确定性派生事实

新增文件位于 `registry/tasks/<task>/bundle/`，与当前 SQL/Schema/Parser/Adapter 版本共同发布。跨 Task 组合仍由 Consumer Projection 从 Task Bundle 读取，不将跨 Task 路径写回单 Task Canonical Bundle。

替代方案是每次查询重跑 SQL Parser，但这会使 Task Asset 不自包含，并引入 Parser/Schema 版本漂移。

### 2. 使用 Root、Node、Edge 三份规范化 JSONL

- `lineage-hop-roots.jsonl`：一行对应一个 requested Field Expression，保存 Root Expression 与 Native Head 的区别、Coverage/Projection Status 和降级原因。
- `lineage-hop-nodes.jsonl`：一行对应一个去重原生 Hop，保存 Scope Relation、可选 Expression 引用、Expr 种类/文本/Span、Terminal State、Downstream 标记和有序 `via`。
- `lineage-hop-edges.jsonl`：只存 `PHYSICAL_FIELD_TO_HOP` 与 `HOP_TO_HOP`，按生产者→消费者方向持久化。

三份文件是必需的：折叠后 requested Root 可能不是 Head；Node 承载不能正确分配给单边的 via；Edge 为 Consumer 提供不重复嵌套子树的图查询。

### 3. Adapter 产生 Local Hop Projection，Writer 全局化

Plan Adapter 在 `Scope`、`Projection` 和 Relation 映射仍存在时：

1. 为所有 Project/Aggregate 表达式建立 `Projection -> local expression locator`。
2. 为所有 Scope 保留 `Scope -> local relation id`。
3. 对可评测 Projection 调用 `lineageOf()`，递归序列化原生 DAG 为 local Root/Node/Edge。
4. 如何 Scope 映射失败，整个 Root 降级，不发布孤立 Node/Edge。

Writer 仅负责将所有 Local Relation/Expression/Field 端点转为当前 Task/Statement 全局 ID，并写入版本化契约。将原生对象延迟到 Writer 中重新查找的方案被拒绝，因为序列化 Plan 已经丢失对象身份。

### 4. ID 使用结构身份，不使用对象、文本或遍历序号

Local Hop Key 由 `local_relation_id + projection role/ordinal + source span + expr kind` 构成；Writer 在前面加入 Task/Statement 全局前缀。如 Hop 不能映射到 Relation，不使用 Span-only fallback，Root 直接 `NOT_EVALUABLE`。

Edge ID 由全局 From Endpoint Kind/ID、To Hop ID、Edge Kind 以及存在时的 Branch Relation/Ordinal 规范化生成。不使用遍历序号。

### 5. via 保存在 Node，Setop 不造 Hop

原生 API 会将一个 Hop 跟随过的 `rename/expand` Scope 合并成 Hop 级有序 trail，无法证明每个 step 只属于某条 Downstream Edge。因此 via 只存在 Node 上。

Setop 分支保留多个 HOP_TO_HOP 边，并在可映射时附 Branch Relation/Ordinal；不建立原生 API 中不存在的 Setop Node。

### 6. Coverage 是确定性 Feature Gate

`nativeHopCoverageOf()` 在发布 Root 前按 IR/Source 特性决定：

- `NOT_EVALUABLE`：Adapter 合成的最终 Star Expansion Root，或 Scope/Relation 映射缺失。
- `UNKNOWN_COVERAGE`：`Expr.kind=other` 或明确未被原生 Hop 建模的 Lateral/Pivot/TVF/Pipe 过渡。
- `FLAT_ORIGIN_ONLY`：Scalar/EXISTS 子查询；当前 API 使用 `originsOfSubquery` 获取 Terminal，不提供子查询内部 Hop。
- `FULL_HOP`：仅包含已支持 Expr 种类与 CTE/FROM-subquery/Setop 过渡。

`PROJECTED` 还要求：无 native unresolved Terminal，无 candidate/unresolved input，所有端点有效，并且 Hop Terminal 与 Base-Origin 摘要守恒。合法的“物理 Terminal + Downstream Hop”可以是 `PROJECTED`；只有 unresolved/candidate/coverage gap 降级。

### 7. 现有 Base-Origin Edge 是兼容摘要

`column-lineage-edges.jsonl` 保持现有 Physical Field -> Field Expression 语义、文件名与边方向。它不改名为 Hop，也不代替 Hop DAG。对满足 `FULL_HOP` 的 Root，Validator 对比两边的物理字段集合；对降级 Root 仅校验已发布端点，不声称覆盖完整。

### 8. Hop 不替代行集控制事实

所有 Hop Root 声明 `flow_kind=VALUE_LINEAGE`。Query Consumer 解释指标或 Grain 时必须另外读取 Relation/Expression Facts 中的 Filter、Join、Group By、Window 和行集控制证据。

## Risks / Trade-offs

- [每个 Field Expression 调用 lineage walk 增加时间和 Bundle 体积] → 对 Node/Edge 使用确定性 ID 去重，Manifest 记录计数；用代表 Fixture 与现有六任务回放观察增量。
- [原生 Hop 覆盖不等于所有 SQL 结构完整] → 使用确定性 Coverage Gate，任何未建模特性不能因为没有 Unknown 而自动升级。
- [Hop 与 Base-Origin 出现两份相似信息] → 用明确语义分工和 Origin Conservation Gate：一份是摘要，一份是路径，不允许静默漂移。
- [Contract 升级使旧 Bundle 不能被新 Validator 复用] → 提升 Writer/Adapter/Schema 版本，通过现有 Staging/Recovery 机制重建，不就地修补旧产物。
- [分支信息无法对所有原生 Hop 精确映射] → Branch Relation/Ordinal 仅在原生 Scope/Plan 能证明时发布，不影响 Hop 边本身。

## Migration Plan

1. 增加失败 Fixture 和版本化 Contract/Schema。
2. 在 Plan Adapter 实现 Local Hop Projection 与 Coverage Gate。
3. 在 Machine Facts Writer 全局化并发布三份 JSONL，扩展 Manifest/Validator。
4. 跑通单任务 Fixture、现有 Machine Facts 回归、Typecheck 和 OpenSpec 严格校验。
5. 在已忽略的生成目录重建旧 Bundle，验证首次 `REPLACED`、二次 `REUSED` 且索引字节一致。

回滚时恢复 Writer/Adapter/Schema 版本及必需文件列表，然后从保留的 SQL/Schema Snapshot 重建旧版 Bundle；不在原位删减新 Bundle 的部分文件伪造旧版产物。
