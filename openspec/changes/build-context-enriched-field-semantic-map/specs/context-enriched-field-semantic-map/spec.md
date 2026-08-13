## Purpose

本能力将固定 Wiki Tree 快照中的候选业务语义与既有字段语义结果进行有界、可追溯的对齐，形成可从业务导航树进入属性表达矩阵，并下钻到上下文、限定、物理字段、表与证据的字段语义地图。

## ADDED Requirements

### Requirement: 语义发现必须区分事实、假设、决定和发布结果

系统 SHALL 分别保存不可变 `SemanticObservation`、机器 `SemanticHypothesis`、版本化 `ReviewDecision` 与 `PublishedProjection`。Observation SHALL 保留字段名、注释、表、类型、既有绑定与 Facet 来源；Hypothesis SHALL 保存候选概念、属性表达、限定、关系、证据、反证与方法；ReviewDecision SHALL 独立记录处置且不得成为业务证据；PublishedProjection SHALL 只消费满足发布门槛的假设或已接受决定。

#### Scenario: 候选尚未达到发布门槛

- **WHEN** 一个字段只有名称相似、裸子串、Wiki目录或单一不一致注释支持其基础概念或属性表达
- **THEN** 系统 SHALL 将其保留为 `INSUFFICIENT_EVIDENCE` 或 `CONFLICT` Hypothesis，并 SHALL NOT 将其作为无冲突 `AttributeExpression` 或语义关系发布到主地图

#### Scenario: 稳定限定表达达到发布门槛

- **WHEN** 观察表达与基础概念精确一致、属于语言级标识符等价，或其全部残差可由同一来源的版本化限定轴证据解释且无反证
- **THEN** 系统 SHALL 允许其进入 Published Projection，并保留全部 Observation、方法和发布理由

### Requirement: 上下文增强模型必须区分五类核心对象

系统 SHALL 分别表示 `BusinessConcept`、`BusinessContext`、`AttributeExpression`、`Qualifier` 和 `TechnicalAsset`。业务对象、业务主体、业务事件和业务度量 SHALL 作为 `BusinessConcept` 的候选语义类型；Table、Column 和 SQL SHALL 作为 `TechnicalAsset` 或 Evidence，且任何候选对象 SHALL NOT 覆盖物理事实。

#### Scenario: 名义本金相关字段被组织

- **WHEN** 系统处理表达名义本金、动态名义本金和多头动态名义本金的字段
- **THEN** 系统 SHALL 将名义本金表示为 `BusinessConcept`，将真实观察到的稳定组合表示为 `AttributeExpression`，将表和字段保留为 `TechnicalAsset`

### Requirement: 属性表达必须是可复用且有证据的稳定节点

每个 `AttributeExpression` SHALL 通过 `EXPRESSION_OF` 指向一个基础 `BusinessConcept`，并 SHALL 只在字段名、字段注释、Wiki 标题/正文、SQL或跨物理实例复现等实际证据支持时物化。系统 SHALL NOT 生成未观察到的 Qualifier 笛卡尔组合，也 SHALL NOT 因表达可分解为 Qualifier 而拒绝保存稳定表达。

#### Scenario: 多头动态名义本金真实出现

- **WHEN** 一个或多个物理字段实际表达“多头动态名义本金”
- **THEN** 系统 SHALL 生成候选 `AttributeExpression`“多头动态名义本金”，以 `EXPRESSION_OF` 关联名义本金，并以 `QUALIFIED_BY` 记录状态=动态和方向=多头

#### Scenario: 组合未在证据中出现

- **WHEN** 系统已观察到“初始名义本金”和“多头动态名义本金”，但未观察到“初始多头名义本金”
- **THEN** 系统 SHALL NOT 仅根据可组合 Qualifier 生成“初始多头名义本金”节点

### Requirement: 属性表达默认跨上下文复用

系统 SHALL 使用多对多 `APPEARS_IN` 将同一 `AttributeExpression` 关联到零个、一个或多个 `BusinessContext`。产品、对象或汇总范围未知时 SHALL 保留通用或未知上下文，而 SHALL NOT 强迫归入 TRS、期权或其他产品。只有存在定义、粒度、计算口径或用途差异证据时，系统才 SHALL 产生按上下文拆分表达的候选，并保留未拆分基线与差异依据。

#### Scenario: 初始名义本金跨多个上下文复用

- **WHEN** 相同语义的“初始名义本金”同时出现在 TRS、期权和未区分产品的交易汇总表
- **THEN** 系统 SHALL 默认保留一个“初始名义本金”属性表达，并分别关联多个上下文或未知上下文

#### Scenario: 上下文中的口径存在差异

- **WHEN** Wiki正文、SQL、表粒度或人工评审证明两个上下文中的同名表达具有不同业务定义或计算口径
- **THEN** 系统 SHALL 保留拆分候选、差异证据和冲突状态，而 SHALL NOT 静默合并或自动确认为两个正式属性

### Requirement: 系统必须使用六类核心语义关系

系统 SHALL 支持 `BROADER/NARROWER`、`EXPRESSION_OF`、`APPEARS_IN`、`QUALIFIED_BY`、`RELATED_TO` 和 `IMPLEMENTED_BY`。每条关系 SHALL 校验允许的 Subject/Object 类型。导航位置 SHALL 保存为 Projection 配置或候选导航边，且 SHALL NOT 自动成为 `BROADER/NARROWER`。

#### Scenario: 关系类型不得混用

- **WHEN** 名义本金在导航中显示于“业务度量 > 金额”，并出现于 TRS 合约上下文
- **THEN** 系统 SHALL 分别保存导航位置和 `APPEARS_IN` 候选，且 SHALL NOT 仅因页面路径生成已确认的上下位关系

#### Scenario: 邻近字段被发现

- **WHEN** 系统发现“名义本金币种”或“名义本金重置日期”
- **THEN** 系统 SHALL 将其保留为独立概念并使用 `RELATED_TO` 候选关联名义本金，除非更具体的关系已获得足够证据和明确契约

### Requirement: 限定维度必须开放且可解释

Qualifier 维度和值 SHALL 由版本化通用规则和语料证据产生，不得固定为名义本金当前观察到的时点、状态、方向和币种口径。未知限定 SHALL 保留为候选或 Unknown；系统 SHALL NOT 因增加新维度而改变既有 AttributeExpression 的物理事实引用。

上游 Facet 到发布 Qualifier 的轴映射 SHALL 存在于版本化配置中。代码 SHALL NOT 通过新增业务词特例临时决定轴归属；同一发布轴内的值必须语义互斥，不同轴必须可组合。

#### Scenario: 其他概念出现新限定维度

- **WHEN** 一个非名义本金概念稳定出现频率、主体角色或计算口径限定
- **THEN** 系统 SHALL 能保存对应维度和值，而无需增加该概念的定点算法分支

#### Scenario: 说明性上下文不制造重复属性表达

- **WHEN** 两个同名、同物理字段表达只有一个因说明性注释或表场景带出生命周期限定，且该限定未在属性表达或字段名中词法化出现
- **THEN** 系统 SHALL 保留一个 AttributeExpression，将该生命周期信息记录为上下文提示而非表达身份；若限定直接出现在属性表达或字段名中，则 SHALL 继续保留为 `QUALIFIED_BY`

### Requirement: Wiki Tree 必须先产生语义候选再参与映射

系统 SHALL 从固定 Wiki Tree 快照的 `pageId`、标题和祖先路径生成有来源的 Wiki Semantic Candidate，并 SHALL 区分产品/域、对象、主体、事件、过程、属性、规则、文档场景和 Unknown 候选。Wiki 目录父子关系 SHALL 仅作路径与导航证据，不得直接发布为业务上下位关系；目录结论需要正文时 SHALL 记录待读页面而非伪造结论。

业务导航 SHALL 使用版本化 Case 配置区分实体、实体属性、度量/日期语义头和通用字段属性类型。普通关键词仅在表达中出现 SHALL NOT 自动把概念提升为该实体、事件或度量；同一词同时出现在主体和对象词表时 SHALL 由明确优先级或复核决定。无法稳定分类的概念 SHALL 显示为“待归类”，不得通过扩大子串匹配伪造覆盖率。

#### Scenario: 实体与实体属性分层导航

- **WHEN** `交易对手`、`交易对手短名` 和 `交易对手佣金费率` 同时存在
- **THEN** 系统 SHALL 分别导航到“业务主体”、“业务主体 > 交易对手属性”和“业务度量 > 比率”，且 SHALL NOT 因包含“交易”或“交易对手”而同时进入业务对象

#### Scenario: 第二 Schema 通过配置复用导航算法

- **WHEN** 第二 Schema 提供自己的实体词、属性模式、显示模板和限定轴配置
- **THEN** 系统 SHALL 在不修改核心导航代码的前提下生成本 Schema 的导航，并将不能解释的概念保留为待归类

#### Scenario: TRS验收目录被处理

- **WHEN** 路径包含“系统测试 > 业务验收 > TRS验收指引 > TRS动态名义本金列表验收指引”
- **THEN** 系统 SHALL 可产生 TRS、动态名义本金和验收场景候选并引用完整路径，但 SHALL NOT 断言“业务验收”是 TRS 或名义本金的业务父概念

### Requirement: 数据与Wiki候选映射必须有界且可重放

系统 SHALL 从既有 V2 结果派生 Data Semantic Candidate，并以数据候选驱动有界的 Wiki 候选召回和映射。映射 SHALL 保存输入快照哈希、召回信号、支持证据、反证、方法和截断信息；系统 MUST NOT 对全部 Wiki 节点与全部字段执行无界笛卡尔匹配。

#### Scenario: 动态名义本金召回Wiki上下文

- **WHEN** V2 存在动态名义本金表达和 TRS 表上下文提示
- **THEN** 系统 SHALL 有界召回相关 Wiki 标题与路径并生成映射候选，且相同输入、配置和版本 SHALL 得到相同候选顺序与内容哈希

### Requirement: 候选治理必须作用于对象和关系断言

每个机器发现的对象和关系断言 SHALL 独立保存状态、Evidence、Counterevidence、Method、内部 `method_score` 和 Review Decision。`method_score` SHALL 仅用于方法内排序，不得解释为概率；人工决定 SHALL NOT 被记作新的业务证据。

#### Scenario: 页面展示映射候选

- **WHEN** 一个上下文映射尚未经过人工确认但拥有数据库与 Wiki 路径支持
- **THEN** 页面 SHALL 显示“有证据候选”及可定位依据，而 SHALL NOT 显示“82%正确”或把它提升为 Canonical 关系

### Requirement: 页面必须以双树三栏方式交付概念族全貌

审阅 Projection SHALL 提供全局搜索、左侧业务语义导航树、中间属性表达矩阵和右侧表达详情。属性表达矩阵 SHALL 只展示真实物化表达，以当前实际出现的开放限定维度作为列，并支持同维度多选、跨维度组合筛选；每个筛选值 SHALL 显示在其他当前条件下可命中的表达数量。系统 SHALL NOT 为展示而把可交叉限定强制解释为唯一父子层级。右侧 SHALL 显示基础概念、限定、候选业务上下文、按物理字段名聚合的实现、具体表字段链接、相关概念和证据状态。内部关系枚举、ID和方法分数 SHALL 默认隐藏于技术详情。

#### Scenario: 用户搜索名义本金

- **WHEN** 用户从全局搜索打开名义本金
- **THEN** 页面 SHALL 在中栏以矩阵展示名义本金、初始名义本金、动态名义本金及其真实复合表达、限定差异和实现数量，并允许选择任一表达查看上下文、字段、表和证据

#### Scenario: 同一字段名出现在多张表

- **WHEN** `DYNAMIC_NOTIONAL` 出现在多张表
- **THEN** 右栏 SHALL 先显示一个物理表达及其表数，再分页展开各 `Schema.Table.Column` 和 Panorama 详情链接

### Requirement: 首轮必须用真实概念闭环验证且不得规模化

首轮 SHALL 固定 TRADEFLOW 233 表 V2 结果和指定 Wiki Tree 快照，以名义本金检验全部对象、关系、跨上下文复用、邻近概念、Unknown、物理映射和三栏页面，并以至少一个不同语义形态概念验证通用性。首轮结果 SHALL NOT 被解释为完整 Wiki 语义层、全 Panorama 适用、正式本体或业务验收通过。

#### Scenario: 名义本金闭环通过

- **WHEN** 名义本金能够从导航树进入属性表达矩阵并下钻到上下文、字段、表和证据
- **THEN** 项目 SHALL 报告该案例的读者可用性结果，同时继续分别报告总体业务验收和规模化授权

### Requirement: 语义清洗必须跨 Schema 可重放且不得依赖业务特例枚举

系统 SHALL 从完整输入概念语料的重复核心表达、前后修饰片段、物理字段名、中文注释、类型、既有 Facet 和表分布产生语义族、别名、限定变体、相关属性和冲突候选。固定确定性规则 SHALL 仅承担语言级规范化，不得列举某个业务概念、产品或当前截图样例。每个归拢候选 SHALL 保留来源概念、原始标签、方法和语料证据。

#### Scenario: 新 Schema 出现未知业务词

- **WHEN** 新 Schema 中多个概念共享一个此前未配置的稳定核心，但具有不同前后修饰表达
- **THEN** 系统 SHALL 能从语料复现发现该候选语义族和开放修饰词，而无需增加该业务词的专用代码分支

#### Scenario: 相同物理字段名的注释不完全一致

- **WHEN** 相同规范化物理字段名在不同表中存在两个或以上非空中文注释
- **THEN** 系统 SHALL 生成有界复核项，并允许模型或人工处置为别名、限定变体、相关属性、冲突或延期；系统 SHALL NOT 自动覆盖注释或把复核决定记作业务证据

#### Scenario: 未复核语料修饰词不得进入最终限定

- **WHEN** 语料复现仅发现一个候选稳定核心及前后修饰片段，但尚无模型或人工复核决定
- **THEN** 系统 SHALL 将候选族和修饰片段保留在诊断与复核队列，且 SHALL NOT 将修饰片段发布为最终 `Qualifier` 或改变 `AttributeExpression` 身份

#### Scenario: 物理字段或中文表达支持多个冲突概念

- **WHEN** 同一物理字段被直接绑定到多个基础概念，或中文字段表达与其基础概念不存在可解释的包含或标识符等价关系
- **THEN** 系统 SHALL 保留全部来源事实并显式发布冲突与反证，且 SHALL NOT 将相关 `EXPRESSION_OF` 断言展示为无冲突候选

#### Scenario: 不同语义轴不得挤入同一限定维度

- **WHEN** 上游 Facet 将源侧/目标侧与客户/交易对手/内部角色共同放入主体角色，或将动态/固定、可用/冻结、预估/累计共同放入状态
- **THEN** 系统 SHALL 在只读 Projection 中拆分为可解释的正交限定轴，同时保留原始 Facet 作为来源证据
