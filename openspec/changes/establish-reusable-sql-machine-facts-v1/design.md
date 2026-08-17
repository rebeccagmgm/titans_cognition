## Context

当前 sqllens 纵向切片已经能够保留精确 SQL、Statement Span、Relation Node、Field Expression、物理输入解析、Parser Diagnostic 和显式 Plan Unknown。指标加工图又在同一个案例产物中组合了六个任务、Profile 声明写入、指标角色、跨任务边和最小因果路径。为什么必须把可复用层从案例 Projection 中分离，见 `proposal.md`。

实现位于现有嵌套 `sqllens/` 工作区中，只消费本地 SQL 和 Schema Evidence。现有产物及工作区已有修改必须保持不变。生成的原始 SQL、Schema Snapshot 和 Machine Facts 不进入 Git；只有契约、代码、脱敏 Fixture 和测试进入版本控制。

## Goals / Non-Goals

**目标：**

- 为每个配置任务提取一个可独立校验的阶段 1/2 Bundle。
- 以 `task_id` 唯一定位一份当前事实包，并保证相同生成上下文下的 Canonical Content 可确定性重放。
- 保留物理表和字段引用，供后续组合，但不以表作为存储根。
- 保留完整证据、部分状态、失败和方法来源。
- 通过任务级当前状态和可恢复发布，保证失败或中断不会被旧成功结果伪装成当前成功分析。
- 使用当前指标案例的全部六个任务验证通用 Writer，同时不把指标语义带入事实层。
- 使用至少一个独立于该指标 Profile 的本地输入验证 Writer 不依赖案例专属结构。

**非目标：**

- Canonical Cross-Task Edge、指标路径、影响分析答案或查询 UI。
- 定义或生成通用 Derived Package、Projection、Capability Negotiation、阶段 3 Grain/Cardinality 或 Cross-Task Lineage。
- 长期 Registry Service、Execution History Store、Catalog 或 Ontology。
- 重构 sqllens 的 `src/` 库内部实现；第一版仍是 Analysis Layer Adapter。

## Decisions

### 1. 以 Task 为目录展开轴，Table 是被引用事实

仓库目录如下：

```text
machine-facts/
├─ snapshots/
│  ├─ sql/<sql_sha256>.sql
│  └─ schema/<schema_bundle_sha256>.json
├─ registry/
│  └─ tasks/<task_id>/
│     ├─ analysis-status.json
│     └─ bundle/
│        ├─ manifest.json
│        ├─ source-artifact.json
│        ├─ schema-refs.jsonl
│        ├─ statements.jsonl
│        ├─ dataset-io.jsonl
│        ├─ relation-nodes.jsonl
│        ├─ relation-edges.jsonl
│        ├─ field-expression-nodes.jsonl
│        ├─ column-lineage-edges.jsonl
│        └─ unknowns.jsonl
└─ indexes/
   └─ task-fact-index.jsonl
```

Task 拥有 SQL 和分析上下文；一张表可能被多个任务读取或写入，因此不能安全地拥有加工事实。Bundle 中仍保留规范化 Dataset 和 Field Identity，后续查询层可以按表聚合，也可以通过物理字段组合任务包。

备选方案一是以 Physical Table 组织。否决原因是多输出 Statement、共享表和多写入任务会造成重复或歧义合并。备选方案二是以 Run ID 组织。否决原因是执行或采集事件具有易变性，会重复保存稳定分析事实。

### 2. 只有 Snapshot 内容寻址，当前事实包使用 Task 身份

SQL Snapshot Identity 是精确存储字节的 SHA-256。Schema Evidence 被投影成规范文档，按固定 Key 和 Record 顺序序列化，再对 Canonical UTF-8 字节计算 Hash。Schema 文档保留每条来源记录的 Dataset Name、Status、Column、分区字段、`required_for_star`、DDL Hash 和 Evidence Provenance；Capture Path 与 Timestamp 不进入 Canonical Content。Task Bundle 的 `schema-refs.jsonl` 提供这些字段的查询友好投影，物理字段名列表保持兼容。

Task SQL Facts 的唯一仓库身份是：

```text
task_id
```

`sql_sha256`、`schema_bundle_sha256`、Dialect、Parser/Adapter/Contract Version 和 `analysis_config_sha256` 全部记录在 Manifest 中，用于说明本次事实如何生成、判断是否需要重建，以及检测相同上下文下的非确定性；它们不形成额外目录身份。一个 Task 的 SQL 变化后，成功结果直接替换同一 Task 的当前 Bundle。

备选方案一是使用 `task_id + sql_sha256` 作为目录身份。否决原因是 SQL 变化后会留下多个目录，而脱离 Profile 扫描时无法判断哪个代表当前任务。备选方案二是使用 Analysis ID、Source Path、Capture Timestamp 或 Run ID。否决原因是这些值描述生成过程而不是当前任务身份。SQL Hash 仍按精确字节计算，因为注释、Literal 和 Source Span 都属于证据。

### 3. 当前状态驱动可恢复发布

本地 V1 是单写者工具，不声称 Windows 对已有非空目录提供整体原子替换。每次分析采用可恢复状态机：

1. 校验输入后，将 `analysis-status.json` 写为 `ANALYZING`，记录本次 SQL、Schema、方法和配置指纹；
2. 在同级 Staging Directory 生成 Bundle，并完成 Schema、Hash、引用、Span 和边界校验；
3. 上下文相同且内容相同则删除 Staging、写回 `SUCCESS` 并返回 `REUSED`；相同上下文但内容不同则写为 `FAILED/NON_DETERMINISTIC_OUTPUT`，不替换旧 Bundle；
4. 新内容需要发布时，将现有 Bundle 移入唯一 Recovery Directory，再把 Staging 移为 `bundle/`；任一步失败都按状态和目录 Hash 确定性恢复；
5. 新 Bundle 再校验成功后，将状态写为 `SUCCESS` 并记录 Manifest Hash，随后删除 Recovery Directory；无法恢复时写为 `FAILED/RECOVERY_REQUIRED`。

旧 Bundle 可以在失败恢复期间物理保留，但只要状态不是 `SUCCESS` 或状态中的 Manifest Hash 不匹配，它就不是当前成功事实，也不得进入发现索引。V1 不生成 Fact Diff、不保存版本目录、不建设 History/Edition。Manifest 不包含易变时间戳；状态文件是当前操作状态，不是运行历史。

### 4. 通用输入契约比指标 Profile 更窄

Writer 接收的分析输入只包含：

- `logical_source_id`、Dialect 和 Schema Evidence Reference；
- `task_id`、SQL Snapshot Path 和可选 Declared Output Dataset 列表；
- 会影响输出的显式分析选项。

Adapter 可以读取现有指标加工 Profile，但只消费上述通用字段。`case_id`、`indicator_id`、Task `role`、`focus_outputs` 和 `minimal_causal_paths` 不得进入 Canonical Task Bundle 或 `analysis_config_sha256`。Task ID 在当前仓库内必须唯一并校验为安全 Path Segment；`logical_source_id` 必须稳定且进入 Dataset/Physical Field Identity。Input Path 只作为路径解析，绝不拼接进 Shell Command。

Declared Write 是有用的任务上下文，但 Provenance 固定为 `PROFILE_DECLARED`。Parser 可以独立输出 SQL-Derived Write Fact。两类记录确定性不同，因此不得合并。

### 5. 分离拓扑、表达式语义和 I/O 数据集

现有综合 `edges.jsonl` 被拆开，因为不同 Edge Kind 的契约不同：

| 数据集 | 职责 |
| --- | --- |
| `statements.jsonl` | 有序 SQL Statement 证据和 Diagnostic |
| `dataset-io.jsonl` | 带 Provenance 的任务/Statement 读写 |
| `relation-nodes.jsonl` | 阶段 2 Operator Fact |
| `relation-edges.jsonl` | 仅任务内 Operator Topology |
| `field-expression-nodes.jsonl` | Relation Node 产生或使用的表达式 |
| `column-lineage-edges.jsonl` | 物理输入到表达式，以及已验证的表达式到物理输出边 |
| `unknowns.jsonl` | 类型化未解析、不可评测、不适用和失败结果 |

ID 由 Task、Statement Ordinal、Relation Local ID、Expression Role 和 Ordinal 确定性生成，并在 Bundle 内有效。Dataset 和 Physical Field ID 使用 `logical_source_id + 可获得的 Catalog/Schema/Dataset/Field` 规范化标识，防止不同数据源或环境的同名对象被自动合并；存在原始拼写时将其作为证据保留。所有表达式保留完整 Machine Text，事实层不包含展示截断。

### 6. 保守处理输出字段绑定

V1 的 Schema Binding 指使用当前 `schema_bundle_sha256` 将 SQL 中的表别名、未限定字段、子查询字段和 Star Projection 解析为物理 Dataset/Field。它属于阶段 1 的当前事实输出，直接保存在 Task Core Bundle，并通过 `schema-refs.jsonl` 和 Manifest 记录来源；Schema Bundle 变化时重建并通过可恢复发布替换当前 Bundle，不另建 Binding History。

输入物理字段来自使用 Canonical Schema Bundle 的 sqllens Lineage/Name Resolution。只有 SQL Statement 与 Target 能形成无歧义的位置/名称绑定时，才输出 Field-Expression-to-Output-Field Edge。`focus_outputs` 和 Profile 声明的 Target Table 本身不足以构成该证据。

这样既允许后续通过共享 Physical Field Identity 组合跨任务关系，又不会把组合关系写成 Canonical Fact。缺少可靠 Output Binding 时，任务内溯源和 Relation Analysis 仍可复用，并且缺口保持显式。

### 7. Unknown 是数据集，不是混合状态

为兼容现有原型，文件名继续使用 `unknowns.jsonl`，但每条记录必须有明确 `outcome_class`：`UNKNOWN`、`NOT_EVALUABLE`、`NOT_APPLICABLE` 或 `FAILURE`。Parser Diagnostic、Plan Adapter Unknown、未解析物理字段、缺少 Schema 和未经验证的 Output Binding 使用稳定 Reason Code 与 Locator。字段表达式另存 `input_dependency_status` 和 `unresolved_input_columns`；混合物理与未解析依赖使用 `PARTIAL`，`NO_PHYSICAL_INPUT` 和 `DERIVED_OUTPUT` 不再被 Writer 误归为字段绑定 Unknown。

Manifest 按 Outcome Class 和 Gate 分别统计。成功 Bundle 可以包含真正的未解析或不适用记录；成功表示分析完成并诚实保留限制，不表示所有引用均已解析。

### 8. 发布前执行契约驱动校验

JSON Schema 定义每类 Document/Record 的形状。Semantic Validator 还要检查：

- Snapshot 和 Bundle File 的完整 Hash/Path 一致性；
- Task 目录身份、当前状态、输入指纹和 Manifest 一致；
- 必需文件及声明 Row Count；
- 安全 Identifier 和 Relative Path；
- Statement 顺序与 Source Span 回读；
- Relation Edge Endpoint，以及要求范围内的 Ownership Reference 无环；
- Field Expression Ownership 和 Lineage Endpoint 存在；
- Provenance Enum 与 Boundary Declaration；
- 不存在被禁止的阶段 3、Cross-Task 和 Indicator-Specific Record Kind。

确定性测试在两个隔离临时根目录中生成结果并比较 Canonical File Hash。Golden Test 使用小型脱敏 SQL/Schema Fixture。当前六任务案例使用已有本地 Evidence 做 Integration Verification，其生成结果保持忽略状态。

### 9. 案例产物只作为验证输入

现有指标加工图不做原地改写。Generic Writer 使用相同的六份 SQL Snapshot 和 Schema Evidence 重新处理，生成六个独立的当前 Bundle。验证按任务检查 Statement、Operator 和 Expression 的合理覆盖，但不机械复制旧综合 Edge，因为那会把案例专属语义带入新事实层。

六任务案例只能证明指标专属字段没有污染 Core，不能单独证明 Writer 可复用。第一版还必须选择至少一个不属于该指标 Profile、已有本地 SQL/Schema Evidence 的独立分析输入，通过相同通用输入契约生成 Bundle。只有六个指标任务和独立输入全部校验通过、第二次重放全部复用、重建索引字节一致，并且既有指标加工图和最小因果路径校验保持通过时才算工程实现完成。

### 10. Core Bundle 是隔离的 Derived Observation 底座

本 Change 只定义 sqllens 阶段 1/2 的任务级当前 Core Bundle。它不修改 Panorama Physical Facts，不生成 Cognitive Candidate、Review Decision 或读者 Projection，也不自动替代现有 `derived/view_lineage` 契约。后续若有 Grain、跨任务血缘、指标或影响分析等真实 Consumer，必须通过独立 Change 明确其输入 Manifest 引用、类型化输出、认识论层级和验收条件；在此之前不预设通用 Package、Projection 或 Capability 协议。

## Risks / Trade-offs

- [Schema Canonicalization 错把易变采集信息当成分析输入] → 定义并测试显式 Schema Snapshot Projection，不直接对原始 Evidence File 计算 Hash。
- [相同生成上下文产生不同输出] → 对 Manifest 中的 SQL、Schema、方法和配置来源做精确比较；只有上下文变化才允许可恢复替换，相同上下文差异按 `NON_DETERMINISTIC_OUTPUT` 失败。
- [Task-First Storage 降低按表浏览的直接性] → 保留规范化 Dataset/Field Identity 与可重建索引；Table Projection 只作为后续派生 Consumer。
- [不同数据源的同名对象被错误合并] → 强制输入 `logical_source_id`，并将其纳入 Dataset/Physical Field Identity。
- [Profile 声明写入看起来与 Parsed Write 同样可靠] → 强制分开记录和 Provenance，不在去重时升级声明。
- [现有 Adapter 输出案例专属 Entity 或 Edge] → 建立窄 Writer Contract，并增加 Forbidden Field/Edge 回归测试。
- [原始 SQL 或 Schema Snapshot 被提交到 Git] → 扩展 Ignore 规则并检查 Tracked File；只提交脱敏 Fixture。
- [Windows 发布中断留下目录缺口或旧结果] → 使用单写者、状态先行、Staging/Recovery 唯一目录和启动恢复；任何状态/Hash 不一致均排除出成功索引。
- [单一指标案例让案例结构伪装成通用契约] → 增加独立于该 Profile 的本地分析输入；V1 不声明跨 Schema 或业务语义泛化。
- [Core Bundle 被误当成项目 Canonical Physical Fact] → Manifest 和文档明确其 Derived Observation 边界，正式接入留给后续 Consumer Change。

## Migration Plan

1. 先增加版本化契约和脱敏 Fixture，再实现 Generic Writer。
2. 实现 Canonical Serialization、Hash、Path Validation、任务状态和可恢复 Create/Reuse/Replace Primitive。
3. 实现 Schema Snapshot Projection，以及从现有 sqllens 阶段 1/2 结果生成 Task Bundle。
4. 实现 Bundle/Status/Index Validator，再增加确定性、失败保留、恢复和损坏测试。
5. 将六任务指标 Profile 及一个独立本地分析输入处理到已忽略的 `machine-facts/`，校验每个 Bundle，重建索引并重放验证复用。
6. 重跑既有 sqllens Golden、Indicator Processing Graph 和 Minimal Causal Path 校验，证明没有回归。

回滚只需移除本 Change 新增的实现、契约、测试和生成的 `machine-facts/` 目录。现有案例产物和分析脚本不做原地迁移，因此无需回滚。
