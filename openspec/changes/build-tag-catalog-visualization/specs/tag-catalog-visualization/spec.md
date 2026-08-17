## Purpose

为固定的 SZData 标签快照提供可复现的多级目录阅读入口，使用户能够从标签目录定位标签维度，并查看与该维度直接关联的源字段和计算 SQL，同时不把快照缺失或本地生成内容误认为平台事实。

## ADDED Requirements

### Requirement: Generate a snapshot-bound tag catalog projection

系统 SHALL 接受一个包含标签详情、目录数据、快照 manifest 和维度 SQL 文件的固定快照输入，校验输入可读性和记录一致性，并生成独立的、以快照标识绑定的静态目录投影。

#### Scenario: Valid tag snapshot

- **WHEN** 快照 manifest、标签详情 JSONL 和目录数据均可读取，且标签维度 ID 唯一、声明数量一致
- **THEN** 系统 SHALL 生成标签目录页面和投影 manifest，并记录输入路径、输入哈希、快照标识、标签维度数量和生成页面路径

#### Scenario: Invalid tag snapshot

- **WHEN** 输入缺失、JSONL 不可解析、标签维度 ID 重复或 manifest 数量不一致
- **THEN** 系统 SHALL 在发布前失败，并且不得留下看似完整的部分页面

### Requirement: Build a real multi-level catalog tree

标签目录页面 SHALL 将每条标签记录的目录路径拆分为多级目录节点，标签维度作为叶子节点；没有目录路径的记录 SHALL 进入明确的未归类分支。目录节点计数 SHALL 反映其当前可见叶子集合。

#### Scenario: Nested catalog path

- **WHEN** 标签记录包含多段目录路径
- **THEN** 页面 SHALL 按路径顺序建立父子目录节点，并在末端展示对应标签维度，而不是把完整路径显示成一个节点

#### Scenario: Missing catalog path

- **WHEN** 标签记录没有目录路径或目录路径不可用
- **THEN** 页面 SHALL 将该标签放入“未归类/源数据无目录”分支，并在详情中保留该缺口状态

### Requirement: Show source-backed tag details and SQL evidence

标签详情 SHALL 展示快照中已有的标签名称、ID、类别、实时类型、状态、更新方式、来源/结果表、描述和证据状态；存在维度 SQL 文件时 SHALL 展示 SQL 内容或可定位链接，并同时展示文件路径、长度、SHA-256 和 SQL 证据状态。

#### Scenario: Found dimension SQL

- **WHEN** 标签详情的 SQL 证据状态为 `FOUND` 且对应文件可读取
- **THEN** 用户 SHALL 能查看该维度 SQL，并能核对其文件标识和哈希

#### Scenario: Locally generated dimension SQL

- **WHEN** SQL 证据状态为 `GENERATED_LOCAL`
- **THEN** 页面 SHALL 明确标注该 SQL 为本地生成内容，不得将其展示为平台原始调度 SQL

#### Scenario: SQL unavailable

- **WHEN** 快照没有对应 SQL 文件或 SQL 字段未采集
- **THEN** 页面 SHALL 显示“未采集/不可用”等明确状态，不得根据标签名称、来源表或其他字段补写 SQL

### Requirement: Preserve evidence boundaries and exclude task execution semantics

本能力 SHALL 只展示标签快照及其维度 SQL 证据，不得查询或执行业务数据，不得把调度任务 SQL、调度日志或任务关系推断为标签维度定义。

#### Scenario: Task SQL is absent

- **WHEN** 快照仅包含维度 SQL，而没有调度任务 SQL
- **THEN** 页面 SHALL 将调度任务 SQL 标记为未纳入/未采集，不得用维度 SQL 冒充调度任务 SQL

#### Scenario: Read-only projection

- **WHEN** 生成或打开标签目录页面
- **THEN** 系统 SHALL 只读取快照文件并生成本地投影，不得写入 SZData、源系统或数据库

### Requirement: Support bounded search and visible-subset counts

页面 SHALL 支持按标签名称、标签 ID、目录路径、状态和描述进行文本筛选；筛选后 SHALL 隐藏空目录、更新可见标签计数，并独立保留快照总量供比较。

#### Scenario: Filtered tag catalog

- **WHEN** 用户输入匹配条件
- **THEN** 页面 SHALL 只展示匹配标签及其祖先目录，目录计数和当前结果数 SHALL 按可见集合重算，快照总量 SHALL 继续单独显示

#### Scenario: Select a tag dimension

- **WHEN** 用户点击可见标签维度
- **THEN** 详情面板 SHALL 展示该记录的源字段、证据状态和 SQL 入口，并在清除筛选后保持数据关联
