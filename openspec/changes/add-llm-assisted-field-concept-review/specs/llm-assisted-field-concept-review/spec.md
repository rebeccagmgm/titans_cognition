## Purpose

本能力在不改变确定性字段概念基线的前提下，对算法识别出的少量疑难概念簇进行有界、可重放的 LLM 语义审阅，并产出可追溯、可拒绝、可与原结果逐项比较的修订候选。

## ADDED Requirements

### Requirement: 疑难簇必须由确定性条件选择

系统 SHALL 根据运行配置中显式、可重放的簇级指标选择待审阅对象，指标 SHALL 至少覆盖语义混杂、成员离群、命名证据不足和候选关系冲突。系统 SHALL NOT 依赖字段名白名单、概念名特例或人工逐项点选来形成默认审阅集合。

#### Scenario: 普通簇不进入模型审阅

- **WHEN** 一个概念簇未触发任何已配置的疑难条件
- **THEN** 系统 SHALL 保留其确定性结果且 SHALL NOT 为其生成 LLM 审阅 Pack

#### Scenario: 相同输入重复选择

- **WHEN** 相同的基线运行、选择配置和程序版本被再次执行
- **THEN** 系统 SHALL 产生相同的待审阅簇集合及选择原因

### Requirement: 审阅 Pack 必须最小化且可追溯

系统 SHALL 为每个待审阅簇生成独立、内容寻址的审阅 Pack。Pack SHALL 仅包含完成该簇判断所需的稳定 Evidence ID、代表字段、中文或英文注释、非权威类型提示、当前概念路径、成员统计、反例和已知缺口；每项内容 SHALL 可追溯到输入运行。Pack MUST NOT 包含业务数据行、凭据、连接信息、完整 DDL 或未获批准的 Wiki 正文。

#### Scenario: Pack 内容变化

- **WHEN** Pack 中任一规范化证据、Prompt 版本或输出契约发生变化
- **THEN** 系统 SHALL 生成不同的内容哈希且 SHALL NOT 复用旧响应

#### Scenario: 中文注释缺失

- **WHEN** 某字段没有中文注释但仍有名称或其他结构证据
- **THEN** 系统 SHALL 将缺失事实写入 Pack 并继续允许审阅，而 SHALL NOT 因注释缺失将字段判为不可用

### Requirement: 模型响应必须是有界候选判断

模型响应 SHALL 使用强类型契约，并且每个判断 SHALL 仅能采用 `KEEP`、`RENAME`、`SPLIT`、`PARENT_CHILD`、`FACET` 或 `ABSTAIN`。除 `ABSTAIN` 外，每个判断 SHALL 引用 Pack 内的 Evidence ID、说明反证并给出受影响的现有概念或字段集合；模型不得引入 Pack 之外的事实。

#### Scenario: 模型无法可靠判断

- **WHEN** Pack 证据不足以支持唯一修订
- **THEN** 响应 SHALL 使用 `ABSTAIN` 或明确保留冲突，且系统 SHALL NOT 猜测缺失结论

#### Scenario: 响应引用未知证据

- **WHEN** 响应引用不在当前 Pack 白名单中的 Evidence ID
- **THEN** 系统 SHALL 将该响应标记为无效且 SHALL NOT 形成修订候选

### Requirement: 层级与限定维度必须分开表达

系统 SHALL 允许修订候选形成由证据决定的可变深度父子路径，而 SHALL NOT 强制所有概念使用固定二级层级。币种、方向、阶段、口径等与基础概念正交的限定维度 SHALL 优先表达为 Facet；仅当证据支持“是一种”语义时才 SHALL 提议父子关系。

#### Scenario: 初始名义本金候选

- **WHEN** 证据同时支持“名义本金”基础概念和“初始”阶段限定
- **THEN** 模型 MAY 提议父子关系或阶段 Facet，但 SHALL 明确其关系类型和证据，不得只靠字段类型作出结论

### Requirement: LLM 结果不得覆盖确定性基线

系统 SHALL 将所有有效模型响应、规范化修订候选和校验结果写入独立数据集。系统 MUST NOT 原地修改 `concepts.jsonl`、`field_concept_links.jsonl`、Physical Facts、人工审阅决定或其运行 Manifest。

#### Scenario: 模型建议拆分概念簇

- **WHEN** 一个有效响应提出 `SPLIT`
- **THEN** 系统 SHALL 展示拆分后的候选成员与原簇差异，但原簇及字段链接 SHALL 保持不变

### Requirement: 首条执行路径必须支持离线导出和导入

系统 SHALL 支持将待审阅 Pack 导出供当前 GPT 会话处理，并将返回的结构化响应离线导入、校验和投影。Provider SDK SHALL 默认禁用，且只有在 D-005 对 Provider、账号、保留策略和本 Change 外发范围另行批准后才 MAY 启用。

#### Scenario: 未批准 SDK 外发

- **WHEN** 没有满足 D-005 的 SDK 授权配置
- **THEN** 确定性选择和 Pack 导出 SHALL 可运行，SDK 调用 SHALL 报告 `NOT_EVALUABLE` 或保持禁用，而 SHALL NOT 阻塞现有 V1 结果

### Requirement: 审阅运行必须可重放并隔离失败

每次运行 SHALL 记录输入运行标识、Pack 哈希、Prompt 版本、响应哈希、模型标识、可得的 Token 用量、契约校验状态和程序版本。缓存 SHALL 以规范化 Pack、Prompt 和输出契约的联合内容哈希为键。单个 Pack 的缺失、失败、无效响应或 `ABSTAIN` SHALL 被保留并 SHALL NOT 使其他 Pack 或确定性基线失败。

#### Scenario: 重复导入相同响应

- **WHEN** 相同 Pack、Prompt、契约和响应被再次导入
- **THEN** 系统 SHALL 产生相同的规范化候选和重放标识

### Requirement: 对比视图必须保留证据边界

审阅投影 SHALL 对每个疑难簇并排显示确定性基线、LLM 修订候选、选择原因、支持证据、反证、校验状态和人工决定入口，并 SHALL 提供概念到字段再到表及 Object Card 的导航。LLM 候选 SHALL 始终以候选状态展示。

#### Scenario: 查看一个重命名候选

- **WHEN** 用户打开一个有效的 `RENAME` 候选
- **THEN** 页面 SHALL 同时显示原名称、候选名称、引用证据和受影响字段，并 SHALL NOT 将候选名称冒充已接受名称
