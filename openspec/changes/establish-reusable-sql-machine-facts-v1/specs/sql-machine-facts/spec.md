## Purpose

提供确定性、文件优先的任务级 SQL 溯源与逻辑计划事实仓库，使下游分析能够复用这些事实，同时避免把案例专属连接或机器推断提升为已经确认的业务真值。

## ADDED Requirements

### Requirement: 任务级当前事实包
系统 SHALL 将每个任务唯一的一份当前 SQL 事实保存到 `machine-facts/registry/tasks/<task_id>/bundle/`。事实包 SHALL 只描述一个任务和一份精确 SQL 快照，其仓库身份 SHALL 仅为 `task_id`；`sql_sha256` 是当前输入指纹而不是第二层身份，不得增加 Analysis ID 或 Run ID。

#### Scenario: 两个任务使用相同 SQL
- **WHEN** 两个不同任务引用字节完全相同的 SQL 且分析上下文相同
- **THEN** 系统分别保存两个任务级分析包，但允许它们引用同一个内容寻址 SQL 快照

#### Scenario: 相同上下文重放已有事实包
- **WHEN** Task、SQL、Schema、方法版本和配置均未变化且输出内容一致
- **THEN** 系统校验后返回 `REUSED`，无需重写事实包

#### Scenario: 同一任务的 SQL 发生变化
- **WHEN** 已有任务使用新的 SQL 字节重新分析并通过全部校验
- **THEN** 系统在同一 `task_id` 目录替换该任务当前 Bundle，Manifest 记录新的 `sql_sha256`，旧 Bundle 不再作为版本保留

#### Scenario: 生成上下文变化
- **WHEN** Schema Bundle、Parser、Adapter、Contract、方言或分析配置发生变化
- **THEN** 系统在同级临时目录生成并完整校验新事实包，再通过可恢复发布流程替换当前事实包，不保存 Fact Diff 或历史 Edition

#### Scenario: 相同上下文产生不同输出
- **WHEN** Task、SQL、Schema、方法版本和配置完全相同但 Canonical Output 不同
- **THEN** 系统以 `NON_DETERMINISTIC_OUTPUT` 失败，并保持当前事实包不变

### Requirement: 当前分析状态与失败保留
系统 SHALL 在 `machine-facts/registry/tasks/<task_id>/analysis-status.json` 保存该任务唯一的当前分析状态。状态 SHALL 包含当前请求的 SQL、Schema、方法和配置指纹，以及 `ANALYZING`、`SUCCESS` 或 `FAILED` 状态；失败时 SHALL 保存类型化失败结果且不得把旧成功 Bundle 继续声明为当前成功分析。

#### Scenario: 开始重建当前任务
- **WHEN** 系统接受一个任务的新分析请求
- **THEN** 系统先将任务状态写为 `ANALYZING` 并记录请求输入指纹，再开始生成 Staging Bundle

#### Scenario: 新分析成功
- **WHEN** Staging Bundle 完整生成、通过校验并完成可恢复发布
- **THEN** 系统将状态写为 `SUCCESS`，记录当前 Manifest Hash，且发现索引只引用该 Bundle

#### Scenario: 新分析失败
- **WHEN** Parser、Adapter、Schema Binding、校验或发布恢复失败
- **THEN** 系统将状态写为 `FAILED` 并保留当前失败类别、Reason Code、输入指纹和可定位诊断；旧 Bundle 可以为恢复目的保留，但 MUST NOT 进入当前成功索引

#### Scenario: 发现中断的发布
- **WHEN** 启动时发现 `ANALYZING` 状态、Staging/Recovery 目录或状态与 Bundle Manifest 不一致
- **THEN** 系统执行确定性恢复或返回 `RECOVERY_REQUIRED`，不得猜测某个目录为当前成功结果

### Requirement: 内容寻址输入快照
系统 SHALL 将精确 UTF-8 SQL 字节保存到 `machine-facts/snapshots/sql/<sql_sha256>.sql`，将规范化 Schema Bundle 保存到 `machine-facts/snapshots/schema/<schema_bundle_sha256>.json`。快照名称 SHALL 使用对实际存储字节计算的完整小写 SHA-256。

#### Scenario: 首次发现 SQL 快照
- **WHEN** 配置任务指向一份可读 SQL Artifact
- **THEN** 系统写入或复用文件名 Hash 与实际内容 Hash 一致的 SQL 快照

#### Scenario: 快照文件名与内容不一致
- **WHEN** 内容寻址路径上已有快照，但其字节与路径 Hash 不一致
- **THEN** 系统校验失败且不得发布分析包

#### Scenario: Schema Evidence 不完整
- **WHEN** 一个或多个被引用 Dataset 的 Schema Evidence 缺失、失败或字段为空
- **THEN** Canonical Schema Bundle 保留这些状态，并将受影响的解析或 Star Expansion 记录为显式未解析结果

### Requirement: 生成来源与覆盖规则
系统 SHALL 在 Manifest 中记录 `schema_bundle_sha256`、方言、Parser 名称与版本、Plan Adapter 名称与版本、Contract Version 和 `analysis_config_sha256`。这些字段用于复现、判断是否需要重建和检测非确定性，但 MUST NOT 形成第二层事实身份。时间戳、进程标识、输出路径和源采集路径等易变值 MUST NOT 进入 Canonical Output。

#### Scenario: 重放相同分析上下文
- **WHEN** 同一任务使用相同 SQL 字节、Canonical Schema Evidence、方言、配置和方法版本重新分析
- **THEN** 系统生成内容等价的输出并复用当前事实包

#### Scenario: 分析方法发生变化
- **WHEN** Parser、Adapter、Contract、方言、Schema Bundle 或分析配置发生变化
- **THEN** 系统将变化后的来源信息写入新 Manifest，并在校验成功后通过可恢复发布流程替换当前事实包

#### Scenario: 不要求事实历史
- **WHEN** 当前事实包被新生成结果替换
- **THEN** 系统不生成 Fact Diff、不保存旧 Bundle，也不建设 History 或 Edition 目录

### Requirement: 完整 Manifest 与源记录
每个已发布分析包 SHALL 包含 `manifest.json`、`source-artifact.json` 和 `schema-refs.jsonl`。Manifest SHALL 标识任务、精确输入快照、Schema 和方法版本、输出契约、记录数、内容 Hash、校验 Gate 和范围边界。`schema-refs.jsonl` SHALL 保留表级 Evidence Provenance、DDL Hash、`required_for_star` 和分区字段投影，同时保持物理字段名列表。`source-artifact.json` SHALL 引用 SQL 快照而不是复制 SQL 原文。

#### Scenario: 分析包发布成功
- **WHEN** 所有必需数据集均已写入并通过校验
- **THEN** Manifest 报告 `SUCCESS`，为每个必需输出记录 Schema Version、Row Count 和 SHA-256，并且全部强制完整性 Gate 通过

#### Scenario: Parser 无法创建文档
- **WHEN** SQL Parser 在分析 Statement 之前失败
- **THEN** 当前 `analysis-status.json` 保留 Source Reference 和 Failure Outcome，任务状态为 `FAILED`，系统不得声称阶段 1 或阶段 2 完整覆盖

### Requirement: 逻辑数据源与物理标识边界
系统 SHALL 要求分析输入声明仓库内稳定的 `logical_source_id`。Dataset 和 Physical Field Identity SHALL 至少包含该逻辑数据源及可获得的 Catalog、Schema、Dataset 和 Field 组成部分；不得仅凭同名 Schema/Table 将不同数据源或环境合并。

#### Scenario: 两个数据源存在同名表
- **WHEN** 两个不同 `logical_source_id` 都包含相同 Schema、Dataset 和 Field 名称
- **THEN** 系统生成不同的 Dataset/Physical Field Identity，且任何跨源组合留给后续 Consumer

#### Scenario: 逻辑数据源缺失
- **WHEN** 分析输入没有提供合法的 `logical_source_id`
- **THEN** 输入校验失败且不得生成或替换当前 Bundle

### Requirement: Statement 事实保留 SQL 证据
每个分析包 SHALL 包含 `statements.jsonl`，按源顺序保留所有已解析 Statement，以及稳定任务内标识、Statement Type、精确 Source Span、Statement 原文、Parse Status 和 Diagnostic。Statement ID SHALL 在任务包内唯一，所有 Span SHALL 能对引用的 SQL 快照进行回读。

#### Scenario: SQL 同时包含 DDL 和 DML
- **WHEN** 任务 SQL 快照包含多个不同类型的 Statement
- **THEN** 系统按顺序为每个已解析 Statement 输出一条事实，不得丢弃非查询语句

#### Scenario: Statement 只完成部分解析
- **WHEN** Statement 存在 Syntax Diagnostic 但仍能产生部分表示
- **THEN** Statement 以 `PARTIAL` 状态保留，并链接对应 Diagnostic Outcome

### Requirement: Dataset I/O 区分观察与声明
每个分析包 SHALL 包含 `dataset-io.jsonl`。每条记录 SHALL 标识方向（`READ` 或 `WRITE`）、规范化 Dataset Identity、已知时的 Statement、Provenance 和 Resolution Status。SQL Plan 观察与外部声明的任务上下文 MUST 保持区分；声明写入 MUST NOT 表示为 Parser 已确认。

#### Scenario: 逻辑计划观察到输入表
- **WHEN** Read Relation 解析到物理 Dataset
- **THEN** 系统输出一条 Provenance 为 `SQL_PLAN` 的 `READ` 记录，并引用对应 Statement 和 Relation Node

#### Scenario: 输出表只来自任务 Profile
- **WHEN** 分析输入声明了任务输出，但 SQL Output Binding 未被可靠提取
- **THEN** 系统输出 Provenance 为 `PROFILE_DECLARED` 的 `WRITE` 记录，且不得输出 Parser 已确认的输出字段血缘

#### Scenario: SQL 可靠提取输出表
- **WHEN** 已解析 Statement 能无歧义识别 Write Target
- **THEN** 系统输出带 SQL 解析来源的 `WRITE` 记录；独立的 Profile 声明作为佐证上下文保留，不得覆盖该记录

### Requirement: 任务内逻辑计划图
每个分析包 SHALL 包含 `relation-nodes.jsonl` 和 `relation-edges.jsonl`，表示各 Statement 的阶段 2 Logical Plan。Relation Node SHALL 使用 `READ`、`PROJECT`、`FILTER`、`JOIN`、`AGGREGATE`、`EXPAND`、`SETOP` 和 `OTHER` 类型；Relation Edge SHALL 只连接同一任务包内的节点，并保留 Source Span 和算子专属事实，不得截断机器事实。

#### Scenario: 嵌套查询包含 Join 和 Aggregate
- **WHEN** 相关算子位于顶层 Query Scope 以下
- **THEN** 系统输出嵌套 Relation Node 及其拓扑，不得只检查 Root Scope

#### Scenario: 算子无法建模
- **WHEN** 已解析 SQL 包含契约未支持的 Relation Body 或 Operator
- **THEN** 系统保留 `OTHER` Node 或带源证据的显式未解析结果，不得静默丢弃

### Requirement: 字段表达式与任务内字段溯源
每个分析包 SHALL 包含 `field-expression-nodes.jsonl` 和 `column-lineage-edges.jsonl`。Field Expression Node SHALL 保留所属 Statement 与 Relation、Role、Ordinal、Output Name Status、完整表达式文本、存在时的 Source Span 和已解析输入字段。任务内 Lineage Edge SHALL 只表达本任务分析可获得的证据：物理输入字段到字段表达式，或在输出绑定无歧义时字段表达式到物理输出字段。

#### Scenario: 表达式读取到已解析物理字段
- **WHEN** Schema 辅助血缘为表达式解析到一个或多个物理输入字段
- **THEN** 系统为每个物理字段输出一条指向该 Field Expression Node 的溯源边，并记录 Method 和 Resolution Provenance

#### Scenario: 输出绑定不可靠
- **WHEN** 表达式存在 Output Name，但其物理 Write Target 只来自 Focus 配置，或无法按位置和结构完成映射
- **THEN** 系统不得输出 Expression-to-Physical-Output Edge；当该缺口影响完整性时必须显式记录

#### Scenario: Schema 展开 Star Projection
- **WHEN** Star Projection 能通过 Canonical Schema Bundle 展开
- **THEN** 系统输出带 Schema Expansion Provenance 的展开字段表达式，且这些字段不再残留 Unresolved Star

### Requirement: 失败与不确定性是一等记录
每个分析包 SHALL 包含 `unknowns.jsonl`，记录阶段 1 或阶段 2 遇到的未解析、部分、失败、不可评测和不适用结果。每条记录 SHALL 标识 Outcome Class、Reason Code、可读原因、受影响 Subject、可用时的 Source Locator，以及缺失能力或证据。`UNKNOWN`、`NOT_EVALUABLE`、`NOT_APPLICABLE` 和 `FAILURE` MUST 保持区分。

每个字段表达式记录 SHALL 同时标识 `input_dependency_status`：`PHYSICAL`、`DERIVED_OUTPUT`、`PARTIAL`、`UNRESOLVED` 或 `NO_PHYSICAL_INPUT`，并保留 `unresolved_input_columns`。混合物理输入与未解析输入时 MUST 使用 `PARTIAL`，不得降级为完全物理。`input_fields` 为空本身不得被解释为字段绑定失败；运行时表达式、字面量和合法派生输出必须保留其实际状态。

#### Scenario: 物理字段绑定失败
- **WHEN** 已解析 Column Reference 因 Schema Evidence 或 Analyzer 能力不足而无法绑定
- **THEN** 系统保留表达式并输出类型化未解析结果，不得虚构物理字段

#### Scenario: 非查询语句没有查询输出
- **WHEN** DDL Statement 合理地没有 Projected Output Column
- **THEN** 系统记录 `NOT_APPLICABLE`，不得把该缺失当成分析失败或语义 Unknown

#### Scenario: 无物理输入的合法表达式
- **WHEN** 表达式是字面量、运行时函数或已知派生输出，且没有可直接绑定的物理字段
- **THEN** 系统保留字段表达式及其 `input_dependency_status`，不得仅因 `input_fields` 为空追加物理字段绑定 Unknown

### Requirement: 可重建发现索引
系统 SHALL 仅根据任务 `analysis-status.json` 和已校验的当前 Bundle Manifest 生成 `machine-facts/indexes/task-fact-index.jsonl`。索引 SHALL 为每个 `SUCCESS` 且状态所引 Manifest Hash 与 Bundle 一致的任务保留至多一条确定性记录，并且无需读取案例 Profile 即可重建。

#### Scenario: 索引被删除
- **WHEN** 已校验 Bundle 仍存在但发现索引缺失
- **THEN** 重建索引生成内容等价且排序确定的记录

#### Scenario: 遇到无效 Bundle
- **WHEN** 重建索引时发现任务状态非 `SUCCESS`，或 Bundle 未通过 Manifest、Hash、Schema、状态引用或完整性校验
- **THEN** 系统将其排除在成功索引之外并报告校验失败

### Requirement: 校验与重放 Gate
系统 SHALL 在报告 Bundle 成功前校验 JSON Contract、必需文件、Content Hash、Snapshot Hash、Identifier/Path Safety、Referential Integrity、Statement Span 回读、Relation Topology、Expression Ownership、Lineage Endpoint、输出数量和确定性重放。

#### Scenario: 引用节点不存在
- **WHEN** Relation Edge 或 Lineage Edge 引用了不存在的 Node
- **THEN** 校验返回受影响文件和标识符并失败，Bundle 不得报告成功

#### Scenario: 迁移当前指标案例
- **WHEN** 使用当前 SQL 和 Schema 快照处理 `indicator-journey-rgstcomp-mthend` 中配置的六个任务
- **THEN** 每个任务分别生成一份已校验的当前 Bundle，且 Canonical Machine Facts 中不得出现 Indicator ID、Task Role、Focus Output、Minimal Causal Path 或 Cross-Task Edge

#### Scenario: 同一案例重放两次
- **WHEN** 输入和方法版本未变且当前指标案例被处理两次
- **THEN** 第二次处理复用全部六个 Bundle，并生成内容等价的发现索引

#### Scenario: 独立工作流验证
- **WHEN** Generic Writer 使用一个不属于六任务指标 Profile 的本地 SQL/Schema 分析输入
- **THEN** 系统通过同一输入契约生成并校验当前 Bundle，且无需指标 Profile、案例专属 Entity 或跨任务逻辑

### Requirement: V1 范围与安全边界
V1 Machine Facts 能力 SHALL 只执行本地、确定性的阶段 1 和阶段 2 分析，并实现任务当前身份、状态、可恢复发布、类型化事实与校验。它 MUST NOT 查询业务数据行、执行 SQL 或调度、调用外部模型、增加远程服务、创建图数据库依赖，或定义/生成通用 Derived Package、Projection、Capability Negotiation、Grain/Cardinality、跨任务字段拼接、ProductionUnit、指标专属解释或查询层。

#### Scenario: Consumer 请求跨任务血缘
- **WHEN** 下游 Consumer 需要连接上游任务输出字段与下游任务输入字段
- **THEN** 本 V1 Writer 拒绝生成该结果；Consumer 必须通过后续独立 Change 定义输入引用、类型化输出和验收边界

#### Scenario: Consumer 请求 Grain Fact
- **WHEN** 下游 Consumer 调用 Grain Analysis
- **THEN** 本 V1 Writer 返回范围外错误，Grain 和 Cardinality 不得出现在本 V1 Bundle 中
