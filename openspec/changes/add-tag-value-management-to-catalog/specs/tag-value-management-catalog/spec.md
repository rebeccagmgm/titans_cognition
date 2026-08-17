## Purpose

为 SZData 标签快照提供同时面向标签管理和标签维度管理的阅读入口，使读者能够区分 `tagId` 与 `tagDimId`，并沿真实关联在两个对象之间定位证据。

## ADDED Requirements

### Requirement: Consume distinct tag-value and tag-dimension datasets

系统 SHALL 将标签管理记录和标签维度记录作为两个不同的数据对象读取，分别保留 `tagId/tagName` 与 `tagDimId/tagDimName`，不得根据维度记录、SQL 或名称推造另一类对象。

#### Scenario: Complete all-scope snapshot
- **WHEN** 输入快照包含标签值、标签维度和关联记录
- **THEN** 页面 SHALL 分别统计和展示标签管理对象、标签维度对象及其关联证据

#### Scenario: Dimension-only snapshot
- **WHEN** 输入快照仅包含标签维度记录
- **THEN** 页面 SHALL 继续展示维度目录，并明确标注标签管理数据未采集，不得显示伪造的标签行

### Requirement: Provide one object-aware catalog tree

页面 SHALL 使用同一棵“类型 → 目录 → 标签维度 → 标签”阅读树；维度节点与标签叶子 SHALL 有轻量但明确的视觉区分。标签详情 SHALL 展示平台返回的标签名称、标签 ID、状态、目录和生成条件，标签维度详情 SHALL 展示维度字段及其 SQL 证据。底层对象和主键不得合并。

#### Scenario: Select a tag value
- **WHEN** 用户选择一个标签叶子
- **THEN** 页面 SHALL 显示该标签的 `tagId`、关联状态和所属维度，并保持目录树展开状态

#### Scenario: Select a tag dimension
- **WHEN** 用户选择一个标签维度节点
- **THEN** 页面 SHALL 显示该维度的 `tagDimId`、目录、打标调度 ID、系统标签调度 ID、源/结果字段、证据状态和格式化 SQL；没有任务时显示“未配置”，不在详情中重复列出关联标签

#### Scenario: Detail response omits list task assignments
- **WHEN** 维度详情响应返回空任务数组，但标签维度管理列表返回一个或多个打标或系统标签任务 ID
- **THEN** 快照和投影 SHALL 使用管理列表中的非空任务证据并按任务 ID 去重；详情空数组不得覆盖列表证据，只有两处均无任务时才显示“未配置”

#### Scenario: Resume after the list page was persisted
- **WHEN** 续跑跳过已完成的维度列表分页并继续抓取维度详情
- **THEN** 采集 SHALL 从已落盘的 `tag-dimensions.jsonl` 恢复列表记录后再合并详情，不得因内存映射重建为空而丢失任务 ID

#### Scenario: Projection displays task IDs without workflow records
- **WHEN** 页面从维度管理列表展示任务 ID 且 `workflowRecordsFetched=0`
- **THEN** 投影 manifest SHALL 记录 `tag-dimensions.jsonl` 的路径与 SHA-256，并将任务证据标为 `ID_ONLY`；页面 SHALL 明示这些 ID 不证明任务详情、执行结果或授权

#### Scenario: Tag relates to multiple dimensions
- **WHEN** 一个标签关联多个维度
- **THEN** 页面 SHALL 在每个有证据的维度下提供该标签入口，但根级标签总数 SHALL 按 `tagId` 去重，重复入口不得被解释为多个标签对象

### Requirement: Preserve holding versus combination type

系统 SHALL 将平台返回的 `tagType/tagClas` 作为独立于目录的“持仓/组合”类型保留，并在标签管理和标签维度管理的目录树中作为首层分类；代码 `1/2` SHALL 分别显示为“持仓/组合”。

#### Scenario: Dimension has no catalog but has a type
- **WHEN** 标签维度的源目录为空且 `tagClas=1` 或 `tagClas=2`
- **THEN** 页面 SHALL 先将其归入“类型：持仓”或“类型：组合”，再在该类型下展示“未分类（源快照）”，不得把类型缺失与目录缺失混为一谈

#### Scenario: Missing-catalog dimension also has related tags
- **WHEN** 无目录维度同时存在关联标签
- **THEN** 页面 SHALL 在同一个“未分类（源快照）”分支按 `tagDimId` 合并维度及其标签，每个维度只出现一次；没有关联标签的无目录维度仍保留并显示零标签

#### Scenario: Read a snapshot created before the mapper correction
- **WHEN** 快照保留 `tagClassCode/tagTypeCode`，但名称字段仍是数字文本或旧翻译
- **THEN** 投影 SHALL 使用代码恢复“持仓/组合”显示，同时保留快照证据边界，不修改原快照文件

### Requirement: Preserve relation and evidence boundaries

系统 SHALL 只使用快照中实际返回的标签-维度关联建立导航；缺失、部分成功、超时或命令失败的关联 SHALL 保留其状态，且不得解释为无关联。页面 SHALL 显示快照范围和输入文件状态。

#### Scenario: Partial relation evidence
- **WHEN** 标签记录存在但某个维度关联查询失败或没有完整证据
- **THEN** 页面 SHALL 展示该关联的失败或部分状态，并保留对象本身，不得删除标签或降级为“没有维度”

#### Scenario: Invalid or incomplete input
- **WHEN** 标签值文件缺失、JSONL 不可解析、对象 ID 重复或快照声明范围与文件内容不一致
- **THEN** 生成 SHALL 失败且不得替换已有有效投影

### Requirement: Keep the projection read-only and snapshot-bound

投影 SHALL 只读取固定快照文件，不查询业务数据、不执行标签 SQL、不修改 SZData 或源快照；页面 SHALL 显示来源快照标识和生成结果的证据边界。

#### Scenario: Reader opens generated projection
- **WHEN** 用户打开生成页面
- **THEN** 页面 SHALL 能区分平台返回字段、本地投影字段和未采集字段，并保留现有维度 SQL 的格式化与语法高亮展示

### Requirement: Prove snapshot completeness across source result windows and resumes

全量快照 SHALL 在源端结果超过单次查询窗口时使用页面真实支持且经总数守恒验证的筛选分片。`COMPLETE` SHALL 仅在每类对象的累计唯一抓取数等于源端期望数、关系专属维度详情已纳入恢复集合、manifest 计数与落盘文件一致且未发现漂移时输出。

#### Scenario: Tag values exceed the source result window
- **WHEN** 标签值总数超过单个查询分片可返回的最大记录数
- **THEN** 采集 SHALL 递归拆分互斥筛选，并在每一层验证子分片总数之和等于父分片总数；无法证明守恒时 SHALL 输出 `PARTIAL`

#### Scenario: Resume after detail enrichment timeout
- **WHEN** 标签值、关系和部分维度详情已落盘后任务超时并续跑
- **THEN** 采集 SHALL 从关系文件恢复关联维度 ID，按唯一 ID 补齐详情，并以累计文件计数写入 manifest，不得把本轮新增数当作总数

#### Scenario: Fetched count is lower than expected
- **WHEN** 任一已请求范围的累计唯一记录数小于源端期望数
- **THEN** manifest SHALL 标记 `PARTIAL` 和 `INCOMPLETE_FETCH`，不得标记 `COMPLETE`
