## Purpose

将 `sql-static-lineage` 已证明的逐跳值传播 DAG 保存为可验证、可重建、可供 Query Consumer 稳定消费的任务级 Machine Facts，同时诚实保留无法逐跳展开的覆盖缺口。

## ADDED Requirements

### Requirement: Task Bundle 保存规范化 Hop DAG
对于包含可分析字段表达式的任务，系统 SHALL 在当前 Task Bundle 中输出 `lineage-hop-roots.jsonl`、`lineage-hop-nodes.jsonl` 和 `lineage-hop-edges.jsonl`。Root SHALL 区分请求的字段表达式与原生 Hop Head；Node SHALL 表达原生 Hop 及其 Hop 级 via trail；Edge SHALL 仅表达物理字段或生产者 Hop 到消费者 Hop 的值传播。

#### Scenario: 外层透传被原生 Hop 折叠
- **WHEN** 一个最终字段表达式经过 CTE 或子查询透传并被原生 lineage walk 折叠到内层生产者
- **THEN** Root 记录保留 `root_expression_id` 和不同的 `head_hop_id`，不伪造外层 Hop Node

#### Scenario: DAG 包含物理 Terminal 和中间计算
- **WHEN** 字段路径经过一个或多个计算表达式到达物理字段
- **THEN** 系统以 `HOP_TO_HOP` 和 `PHYSICAL_FIELD_TO_HOP` 边保留生产者到消费者的有向路径

### Requirement: Hop 投影保持原生语义
系统 MUST 直接消费原生 `LineageHop`，不得由 Relation Facts 重建近似 Hop。`via` SHALL 按原生顺序保存在 Hop Node 上；物理表 SHALL 作为 Terminal 而非 Hop；Setop SHALL 通过分支 Hop 表达而不伪造 Setop Hop Node。

#### Scenario: Rename 与 Star Descent
- **WHEN** 原生 Hop 带有保序的 `rename` 或 `expand` via trail
- **THEN** Node 原样保留每个 via step 的顺序、类型和对应 Relation，不将 via 虚假分配到某条边

#### Scenario: UNION 产生多分支
- **WHEN** 原生 Hop 对 UNION、EXCEPT 或 INTERSECT 生成多个生产者分支
- **THEN** 系统保留每个分支 Hop 及可获得的分支 Relation/Ordinal，不新建无原生对应的 Setop Hop

#### Scenario: 同一 Hop 同时读取 Terminal 和下游 Hop
- **WHEN** 一个表达式同时读取直接物理字段与派生字段
- **THEN** Node 可同时具有物理 Terminal 和 Downstream Hop，两类边都必须保留

### Requirement: Hop 身份和端点确定性
持久化 `hop_id`、`edge_id` 和所有 Relation/Expression/Field 端点 SHALL 使用 Task/Statement 内全局化的确定性身份，不得依赖内存对象身份、原文文本或遍历顺序。Scope 无法映射到 Relation 时 MUST 停止发布该 Root 的 Hop 节点与边。

#### Scenario: 两个 Root 共享一个生产者
- **WHEN** 两个 Root 的原生 walk 到达同一 Scope/Projection/Span 中的生产者
- **THEN** 确定性 ID 将其折叠为同一 Hop Node，并保留各 Root 的独立 Root Binding

#### Scenario: Scope 端点不可映射
- **WHEN** 原生 Hop Scope 无法解析到当前 Task/Statement 的 Relation ID
- **THEN** Root 标记为 `NOT_EVALUABLE`并写入类型化原因，不使用降级 ID 或发布悬空端点

### Requirement: 覆盖与降级状态不得过度声明
每个 Root SHALL 保留 `coverage_state`（`FULL_HOP`、`FLAT_ORIGIN_ONLY`、`UNKNOWN_COVERAGE`、`NOT_EVALUABLE`）与 `projection_status`（`PROJECTED`、`PARTIAL_NATIVE`、`NOT_EVALUABLE`）。只有当原生 Hop 能力完整、所有 Scope 可映射、无 unresolved/candidate，且物理 Terminal 守恒时才能标记 `PROJECTED`。

#### Scenario: Scalar 或 EXISTS 子查询被压平
- **WHEN** 表达式包含当前原生实现只转换为物理 Origins 的 Scalar/EXISTS 子查询
- **THEN** Root 为 `FLAT_ORIGIN_ONLY/PARTIAL_NATIVE`，保留已知 Origins 但不声称子查询内部 Hop 完整

#### Scenario: 最终 Star Expansion 没有逐字段原生锚点
- **WHEN** Field Expression 是 Adapter 从最终 Star Projection 合成的字段记录
- **THEN** Root 为 `NOT_EVALUABLE`、`head_hop_id=null` 并保留 `NATIVE_STAR_COLUMN_ANCHOR_UNAVAILABLE`，不伪造逐字段 Hop

#### Scenario: 未建模表达式或来源路径
- **WHEN** Root 包含明确不在原生 Hop 覆盖内的 Expr 或 Source 特性
- **THEN** Root 为 `UNKNOWN_COVERAGE`，不得因为没有现成 Unknown 记录而升级为 `PROJECTED`

### Requirement: Hop Terminal 与 Base Origin 守恒
系统 SHALL 保留现有 `column-lineage-edges.jsonl` 的物理来源摘要语义。对 `FULL_HOP` 且可评测的 Root，从 Hop DAG 可达的物理 Terminal 集合 MUST 与该 Root 的现有物理输入集合相等；其他状态 SHALL 显式降级而非虚假通过守恒 Gate。

#### Scenario: 可评测 Root 来源一致
- **WHEN** Root 满足 `FULL_HOP`、无 unresolved/candidate 且所有端点有效
- **THEN** Validator 验证 Hop 可达物理字段与 Base-Origin 摘要完全相等，否则 Bundle 校验失败

#### Scenario: Root 只有部分原生覆盖
- **WHEN** Root 为 `FLAT_ORIGIN_ONLY`、`UNKNOWN_COVERAGE` 或存在 unresolved/candidate
- **THEN** Manifest 将该 Root 计入部分/不可评测计数，不将物理集合相等解释为完整 Hop 证明

### Requirement: Hop 事实仅表达任务内值传播
Hop 数据集 SHALL 声明 `flow_kind=VALUE_LINEAGE`，不得把 Filter、Join、Group By 对行存在、行选择、多重性或 Grain 的影响伪装成 Hop 字段传播。

#### Scenario: Consumer 解释完整加工因果
- **WHEN** Query Consumer 需要解释同时包含值传播和行集控制的 SQL
- **THEN** Consumer 必须组合 Hop Facts 与 Relation/Expression Facts，不得仅依据 Hop DAG 声称完整业务因果或 Grain

### Requirement: Bundle 契约、验证和重建同步升级
新数据集 SHALL 进入版本化 TypeScript Contract、JSON Schema、必需输出清单、Manifest 计数/Gate 和发布前 Validator。旧 Bundle MUST 在新方法版本下重建，系统不得把缺少 Hop 文件的旧 Bundle 宣称为新契约成功产物。

#### Scenario: 新 Bundle 端点、DAG 或计数无效
- **WHEN** Hop 文件存在悬空端点、环、非确定性重复、Schema 错误、计数/哈希不一致或守恒失败
- **THEN** 发布前 Validator 拒绝该 Bundle 并返回可定位的失败原因

#### Scenario: 方法版本变更后读取旧 Bundle
- **WHEN** 当前 Writer 遇到未包含 Hop 必需输出的旧 Bundle
- **THEN** 系统根据现有可恢复发布规则将其重建/替换，而不复用为新版本 Bundle
