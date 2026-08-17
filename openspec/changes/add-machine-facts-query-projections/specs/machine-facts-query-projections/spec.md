## Purpose

为下游分析提供一个基于已校验 Machine Facts 的派生投影入口，使现有结构化路径验证可以复用任务 Bundle，同时不把案例路径结论伪装成基础事实。

## ADDED Requirements

### Requirement: Bundle 投影输入

投影器 SHALL 只读取已发布的 Task Bundle、对应 Profile 和 Bundle Manifest，不得重新解析 SQL 或查询业务数据行。投影器 SHALL 保留任务、关系、字段表达式、物理输入和结构化条件事实的证据引用。

#### Scenario: 从任务 Bundle 装配路径

- **WHEN** Profile 声明了最小因果路径且所引用任务 Bundle 均通过校验
- **THEN** 投影器生成可供路径装配器消费的 GraphInputs，并保留上游 Artifact/Manifest 引用

#### Scenario: Bundle 缺失或无效

- **WHEN** Profile 引用的任务 Bundle 缺失、Manifest Hash 不匹配或未通过校验
- **THEN** 投影失败或输出带 Gap 的 `PARTIAL` 结果，不得将缺失证据标记为 `COMPLETE`

#### Scenario: Profile SQL 与 Bundle 不一致

- **WHEN** Profile 中任务的 SQL Snapshot SHA-256 与当前 Bundle Manifest 的 `inputs.sql_sha256` 不一致
- **THEN** 投影必须拒绝消费该 Bundle，并报告 SQL Snapshot Hash 不一致

### Requirement: 派生路径投影

投影器 SHALL 支持 `VALUE_FLOW` 和 `ROWSET_CONTROL` 两类最小路径，并 SHALL 将路径状态、步骤、结构化边、证据引用和 Gap 写入独立 Projection 文件。路径投影不得修改 Canonical Task Bundle。

#### Scenario: 完整值流路径

- **WHEN** 生产字段、任务数据集流、下游读取、表达式馈入和目标聚合写入边均可由事实与 Profile 连接
- **THEN** 路径状态为 `COMPLETE`，并输出值流步骤和证据边

#### Scenario: 行集控制路径

- **WHEN** 控制字段、结构化过滤条件、LEFT JOIN、IS NULL 条件和受控聚合均有证据
- **THEN** 输出 `ROWSET_CONTROL` 路径，并明确该路径改变行集而非直接传递数值

### Requirement: 投影身份与边界

每个 Projection SHALL 记录 Projection 类型、Case/Profile Hash、上游 Task Manifest Hash、结果 Hash、状态和未声明能力边界。Projection 的 `PASS` MUST NOT 表示业务口径正确、完整指标链路或全部任务覆盖。

#### Scenario: 上游事实变化

- **WHEN** 任一上游 Task Manifest Hash 或 Profile Hash 发生变化
- **THEN** 投影结果身份发生变化并重新生成，不得复用旧 Projection

#### Scenario: 仅配置路径通过

- **WHEN** 所有 Profile 声明路径均为 `COMPLETE`
- **THEN** Projection 可以报告 `PASS`，但必须保留未声明的完整性、业务正确性和全任务覆盖边界
