## Why

现有 SZData 标签快照已经包含标签维度、目录路径和本地维度 SQL，但当前目录树把完整路径当作单个节点，难以按业务目录浏览；SQL 也缺少与标签详情绑定的读者入口。现在需要把这批只读快照整理成可复现的标签资产目录，同时明确 SQL 的来源和证据边界。

## What Changes

- 新增一个以已落盘标签快照为输入的标签目录树投影。
- 将 `catalogPath` 拆分为真正的多级目录节点，标签维度作为叶子节点；无目录的记录进入显式的未归类分支。
- 提供标签维度详情面板，展示名称、类型、状态、实时/离线属性、来源/结果表、描述和证据状态。
- 在详情中展示标签维度计算 SQL，并保留 SQL 文件路径、SHA-256、长度和 `FOUND` / `GENERATED_LOCAL` / 未采集等状态。
- 支持按标签名称、ID、目录、状态和描述检索，并按当前可见集合更新目录计数。
- 保留快照总量、输入文件和哈希信息，生成独立、可重复的静态阅读产物。
- 不纳入调度任务 SQL、任务日志、业务数据行查询或 SQL 执行；调度任务 SQL 作为后续独立范围。

## Capabilities

### New Capabilities

- `tag-catalog-visualization`: 从固定标签快照生成多级标签目录、标签详情和证据边界明确的维度 SQL 展示。

### Modified Capabilities

- None.

## Impact

- 新增标签快照投影/渲染入口及其验证测试，具体实现位置在后续 design 中确定。
- 消费 `dimension-details.jsonl`、`catalog-tree.json`、`detail-manifest.json` 和 `dimension-sql/` 等只读快照产物。
- 生成独立的标签目录阅读页面和投影 manifest，不修改源快照，不接入数据库，不引入外部模型调用。
- 当前指标目录展示 Change 保持不变；标签 Change 与 `.opencli` 快照目录之间通过显式输入路径和来源哈希关联。
