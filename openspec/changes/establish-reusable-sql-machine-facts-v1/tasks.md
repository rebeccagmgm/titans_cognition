## 1. 契约与测试基础

- [x] 1.1 为 Analysis Status、Manifest、Source Artifact、Schema Reference、Statement、Dataset I/O、Relation Node/Edge、Field Expression Node、Column Lineage Edge、Unknown Outcome 和 Task Fact Index 定义版本化 TypeScript 记录契约与 JSON Schema。
- [x] 1.2 增加脱敏 SQL/Schema Fixture，覆盖多语句 SQL、嵌套算子、物理输入字段血缘、Schema 展开星号、声明写入与解析写入、部分解析和未解析绑定。
- [x] 1.3 先增加失败测试，覆盖 Canonical JSON、SQL 精确字节哈希、Schema Bundle 规范化、`task_id` 唯一当前身份、安全任务路径段、必填 `logical_source_id`，以及易变字段和案例专属字段的排除。
- [x] 1.4 先增加失败测试，覆盖必需文件、JSON Schema、哈希/数量、Status/Manifest 一致性、Span 回读、Relation/Expression/Lineage 引用完整性、Outcome Class 分层和 V1 禁止记录类型。

## 2. 确定性仓库基础能力

- [x] 2.1 实现 Identity Document、Schema Snapshot、JSON Document 和确定性排序 JSONL 的规范化序列化及 SHA-256 工具。
- [x] 2.2 实现安全仓库路径构造，以及 SQL/Schema 内容寻址快照的写入或校验复用行为。
- [x] 2.3 实现任务级 `analysis-status.json` 的 `ANALYZING`、`SUCCESS`、`FAILED` 状态转换、输入指纹、Manifest Hash 和类型化失败结果；非成功状态不得进入当前索引。
- [x] 2.4 实现同级 Staging/Recovery 目录和单写者可恢复发布，在 Windows 下支持 `CREATED`、相同上下文且内容一致时 `REUSED`、输入或方法变化时 `REPLACED`、相同上下文但内容冲突时 `NON_DETERMINISTIC_OUTPUT`，以及中断后的确定性恢复或 `RECOVERY_REQUIRED`。

## 3. 任务事实包提取

- [x] 3.1 实现通用分析输入加载器和现有指标 Profile 的窄适配器，只消费 `logical_source_id`、方言、Schema Evidence、Task ID、SQL Path、声明写入和会影响行为的选项。
- [x] 3.2 复用 sql-static-lineage 阶段 1 与 Plan Adapter，输出任务内的 Statement、Relation Node、Relation Edge 和 Field Expression 数据集，并保留完整 Span 与表达式原文。
- [x] 3.3 输出 Dataset I/O，分别保留 `SQL_PLAN`、SQL 解析写入和 `PROFILE_DECLARED` 来源，不合并确定性不同的记录。
- [x] 3.4 输出任务内“物理输入字段到表达式”血缘；只有可证实绑定时才输出“表达式到物理输出字段”血缘，不得以 `focus_outputs` 代替证据。
- [x] 3.5 将 Parser Diagnostic、Plan Unknown、缺失 Schema、未解析物理字段、不适用输出和失败规范化为明确的 `UNKNOWN`、`NOT_EVALUABLE`、`NOT_APPLICABLE` 或 `FAILURE` 记录。
- [x] 3.6 为每个任务事实包写入 Source Record、Schema Reference、确定性 Manifest、输出数量/哈希、Gate 和强制 V1 边界声明；Dataset/Physical Field Identity 必须包含 `logical_source_id`。

## 4. 校验与发现

- [x] 4.1 发布前按全部 JSON Schema 和语义完整性规则校验事实包，错误必须精确定位到文件和标识符。
- [x] 4.2 仅从 `SUCCESS` 且 Status/Manifest Hash 一致的当前 Bundle 确定性重建 `task-fact-index.jsonl`，每个 Task 至多一条，排除失败、恢复中和无效 Bundle 并报告原因。
- [x] 4.3 增加 SQL 变化后同 Task 覆盖、损坏文件、缺失端点、快照哈希不符、不同逻辑数据源同名对象隔离、相同上下文非确定性冲突、发布中断恢复、失败状态排除、索引重建和双目录确定性重放测试，并使全部新增单元测试和 Fixture 测试通过。

## 5. 真实案例迁移与非回归

- [x] 5.1 增加命令，将当前六任务指标 Profile 处理到已忽略的 `machine-facts/` 根目录，且不修改现有案例图产物。
- [x] 5.2 执行六任务迁移并校验所有任务事实包；确认每个 `task_id` 只有一份当前 Bundle，没有 Analysis ID、指标角色/路径或跨任务边；随后重放，确认六个 Bundle 均被复用且重建索引字节一致。
- [x] 5.3 从现有本地证据选择一个不属于六任务指标 Profile 的独立分析输入，通过同一 Generic Contract 生成、校验和重放 Bundle；不得为通过验证引入新的外部采集或案例专属 Writer 分支。
- [x] 5.4 重跑现有 sql-static-lineage Golden、指标加工图和最小因果路径校验；若有回归，只修实现，不削弱原断言。
- [x] 5.5 更新 `.gitignore` 和 SQL 分析文档，说明生成目录、一 Task 一份当前 Bundle、失败状态、可恢复替换、Schema Binding 和逻辑数据源身份，以及 V1 不定义阶段 3、跨任务、Derived Package、Projection、Capability Negotiation 或查询层的边界。
- [x] 5.6 复核最终 Diff，检查是否误改既有脏文件、泄露原始 SQL/Schema、将案例事实写入 Canonical Output、出现未版本化行为变化或缺少测试；记录最终 OpenSpec 严格校验和测试结果。

最终校验记录：`openspec validate establish-reusable-sql-machine-facts-v1 --strict --json` 通过；sql-static-lineage 全量回归 173 个测试文件通过（4022 passed、5 skipped）；Machine Facts 定向测试 27 passed，Machine Facts/Plan Adapter 相关回归 44 passed。TypeScript 全局检查仍有仓库既存的导入配置、Plan Adapter 及并行查询脚本错误，未将其误报为本任务通过。
