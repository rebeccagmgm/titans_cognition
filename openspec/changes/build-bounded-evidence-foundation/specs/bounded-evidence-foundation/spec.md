## Purpose

本能力从固定 Wiki 分类种子和已落盘的 TITANS 物理元数据中，生成可重放、可解释且不会重复计算同源证据的候选对象族与候选业务分类，为业务全貌导航提供第一层语义入口。

## ADDED Requirements

### Requirement: 输入范围必须固定且可追溯

系统 SHALL 只读取指定 Panorama run 的 Canonical Physical Facts、批准的派生观察和 Wiki `175428801` 的固定只读快照。Wiki 输入 SHALL 记录页面 ID、版本或抓取时间、内容哈希和缓存定位；系统 SHALL NOT 为本能力遍历整个 Wiki 空间，也 SHALL NOT 将人员姓名、合作方或组织编制作为稳定分类标签。

#### Scenario: 使用固定 Wiki 页面启动运行

- **WHEN** 用户以一个已完成的 Panorama run 和 Wiki `175428801` 快照启动候选分类
- **THEN** 系统生成包含输入 Artifact 哈希、Wiki 内容哈希和方法版本的 Manifest，并且不请求未列入范围的 Wiki 页面

#### Scenario: Wiki 快照不可定位

- **WHEN** 页面版本、内容哈希或本地缓存定位无法记录
- **THEN** Wiki 标签源 SHALL 标记为 `NOT_EVALUABLE`，确定性结构阶段仍可运行，系统不得将未固定的页面内容混入正式结果

### Requirement: Schema Matching 只产生结构证据

系统 SHALL 从对象名称、对象注释、字段名称、字段类型、声明键和已有依赖分别计算可解释的相似信号及方法内排名。Schema Matching 输出 SHALL 作为 Derived Observation 表达“结构上像谁”，SHALL NOT 直接声明对象属于某个业务分类，也 SHALL NOT 将方法分数表达为正确概率。

#### Scenario: 两张表具有相似结构

- **WHEN** 两张表在名称、字段或键结构上形成候选匹配
- **THEN** 系统输出对象对、各信号原始分数、适用方法、输入来源和限制，而不直接输出已确认业务关系

#### Scenario: 只有一个弱信号相似

- **WHEN** 两张表只因通用字段名或单一名称词相似
- **THEN** 系统保留该信号为弱结构线索或从相似图中裁剪，不得将其升级为强候选族或业务分类

### Requirement: 相似图必须稀疏、有界且保留证据血缘

系统 SHALL 从 Schema Matching 结果构造有界的 schema similarity graph，并为图、边和派生结果记录共同的 `graph_run_id` 或等价来源标识。系统 SHALL 限制每个对象的候选邻居数并保留裁剪原因，避免全对象对结果无限膨胀。

#### Scenario: 构造对象相似图

- **WHEN** 一个对象存在多个相似候选
- **THEN** 系统只保留配置上限内满足互近邻或等价筛选条件的边，并在边上保留各独立结构信号分解

#### Scenario: 图输入能力缺失

- **WHEN** 某种字段、键或依赖能力不可用
- **THEN** 系统记录缺失信号及受影响对象，不得用零分伪装为已观测反证，也不得阻塞仍可评估的其他信号

### Requirement: Leiden community 只能形成候选族

系统 SHALL 在当前运行的 schema similarity graph 上执行社区发现，并将结果保存为运行级 `candidate_family`。Leiden community SHALL NOT 被视为 Business Category；单例、弱连接社区和不满足多视角支撑条件的社区 SHALL 保持 Unknown、单例或弱候选状态。

#### Scenario: 形成强连接社区

- **WHEN** 一个社区具有满足配置条件的内部连接和多视角结构支撑
- **THEN** 系统生成候选族、成员角色、成员级原因和图来源，但不自动赋予已确认业务分类

#### Scenario: 节点被算法分区但社区很弱

- **WHEN** Leiden 将节点分入某个社区但社区仅由弱边支撑或节点实际为单例
- **THEN** 系统不得以“算法已分区”为理由发布强候选族，并 SHALL 输出弱候选或 Unknown

### Requirement: 弱监督标签源必须可弃权且按来源族去重

系统 SHALL 将固定 Wiki 种子、Schema 上下文、高精度名称规则和获批的 LLM 解释作为独立、可定位、可弃权的标签源。每个标签 SHALL 记录 `label_source_id`、`source_family`、支持对象和原始依据；同一根派生来源的多个结果 SHALL NOT 被计作多份独立支持。系统 SHALL NOT 实现 `LF_CLUSTER_NEIGHBOR` 或其他把相似图邻域再次包装成独立弱监督投票的标签函数。

#### Scenario: 聚类和传播复用同一张图

- **WHEN** candidate family 和后续标签传播都源于同一个 `graph_run_id`
- **THEN** candidate family 只作为传播单元或上下文，不额外增加标签票数，系统能够审计该分类只使用了一份图结构证据

#### Scenario: 多个规则来自同一名称证据

- **WHEN** 多个名称规则由同一组对象名 Token 派生并支持相同标签
- **THEN** 系统按同一 `source_family` 汇总其支持，不得把规则数量当成相互独立的证据数量

### Requirement: 标签传播必须单次、有界并允许拒绝分类

系统 SHALL 仅在候选族和明确种子准备完成后执行一次有界 Label Propagation 阶段。传播 SHALL 配置最大迭代数、收敛条件和跨 Schema 边界，分别输出候选标签、竞争标签、Unknown 或 Not Evaluable；自动结果 SHALL NOT 使用 `ACCEPTED`，该状态仅属于人工 Review Decision。

#### Scenario: 种子通过强图关系支持对象

- **WHEN** 一个对象或候选族通过满足传播条件的边连接到一致的业务标签种子
- **THEN** 系统生成带传播路径、来源标签和方法内分数的 `candidate_business_class`

#### Scenario: 候选标签接近或互相冲突

- **WHEN** 第一与第二标签缺少足够区分，或独立标签源存在实质冲突
- **THEN** 系统输出 Competing/Conflict 或 Unknown，并说明缺少的区分证据，不得强制选择覆盖率更高的标签

#### Scenario: 传播达到运行上限

- **WHEN** 传播未在配置的最大迭代数内收敛
- **THEN** 系统停止该阶段、保留部分运行记录并将受影响结果标记为失败或不可评估，不得自动开启第二轮自我修正

### Requirement: LLM 只能解释有界候选族

系统 SHALL 只向 LLM 提供候选族代表对象、结构信号摘要、Wiki 分类种子、反证和允许引用的 Evidence ID。LLM SHALL 只能提出候选名称、业务能力、异常成员和 Abstain；不得补写 Physical Fact、改变图结构、自动接受分类或触发外部工具。

#### Scenario: LLM 输出有合法证据引用

- **WHEN** 获批模型返回通过 Schema 和 Evidence ID 白名单校验的候选解释
- **THEN** 系统将其保存为一个弱监督标签源和独立 LLM Task Result，同时保留模型、Prompt、Evidence Pack 和响应哈希

#### Scenario: Provider 或数据外发未获批准

- **WHEN** LLM Provider、账号或允许外发的元数据范围尚未明确批准
- **THEN** 外部模型调用 SHALL 保持禁用，LLM任务 SHALL 标记为 `NOT_EVALUABLE`，确定性结构和无 LLM 候选结果仍可重建

### Requirement: 结果必须可重放并服务双向导航

系统 SHALL 落盘固定分类词表、对象特征、相似边、候选族、标签源、传播结果、Conflict/Unknown 和阶段 Manifest。静态地图可以从这些 Canonical/Derived 结果生成“业务分类到表”和“表到候选分类”的双向入口，但 SHALL 明确候选、冲突和未知状态。

#### Scenario: 使用相同输入重跑

- **WHEN** 输入 Artifact、Wiki 快照、配置、代码和模型缓存均未变化
- **THEN** 确定性结果 SHALL 内容等价，LLM结果 SHALL 复用经过校验的内容寻址缓存，Manifest 能定位所有输入和输出

#### Scenario: 用户从业务分类进入对象

- **WHEN** 地图展示一个候选业务分类及其对象成员
- **THEN** 用户能够进入任一对象并返回分类入口，同时查看结构来源、弱监督标签、Conflict/Unknown 和“尚未业务验收”的边界说明
