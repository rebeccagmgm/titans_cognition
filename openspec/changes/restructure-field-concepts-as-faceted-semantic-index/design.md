## Context

现有 V1 以字符 n-gram、TF-IDF、近邻召回和层次聚类生成固定三级候选树。真实 TRADEFLOW 运行形成 1,466 个节点；全树体检发现 47 组规范化重复、9 组规范化同名父子、216 个带括号装饰的标签，且 640 个三级节点中 491 个只有一个成员。问题并非聚类算法完全无效，而是聚类结果同时被当作数据形态分类、业务中心概念、限定层级和字段表达注册表。

V1 输出、当前 GPT 全树体检和 `add-llm-assisted-field-concept-review` 均已存在，且必须保持可重放。参见 `proposal.md`；行为边界见本 Change 的两份 capability spec。现行输入仍是测试库只读元数据，不读取列值；通用 LLM SDK 仍未获 D-005 授权。

## Goals / Non-Goals

**Goals:**

- 在不推翻文本相似候选召回能力的前提下，把“聚类即概念树”改为“候选召回 → 中心概念 → Facet/表达 → 字段绑定”。
- 用少量类型化文件表达多对多语义，避免为限定词组合生成无限层级。
- 让确定性代码完成可重放主线，LLM 只处理压缩后的疑难候选。
- 复用现有分页、Web Worker 和 Object Card 链接模式，支持更大范围时页面仍可用。

**Non-Goals:**

- 不维护正式业务本体、标准字段注册表或跨运行 Curated Concept 生命周期。
- 不在本 Change 建立跨 Schema 合并、向量检索、知识图数据库或在线审阅服务。
- 不用测试库列值校验同义关系、金额单位或实际业务用途。
- 不把既有表级分类或 Wiki 标题自动提升为字段基础概念。

## Decisions

### 1. 新建 V2 模块和输出，不在 V1 聚类器中继续打补丁

V2 读取同一 Physical Facts 和范围配置，并可读取 V1 作为比较基线，但从字段原始名称与注释重新构造语义表达。推荐流水线：

```text
Physical fields + fixed scope
  -> normalized source expressions
  -> decoration extraction
  -> head-concept candidates
  -> exact alias classes
  -> bounded approximate candidate recall
  -> facet/variant decomposition
  -> field bindings + conflicts/unknowns
  -> compact indexes + review projection
```

V1→V2 映射只作为比较 Projection，由共享 `column_id` 计算；不尝试把旧 1,466 个节点无损迁移成新真值。

**替代方案：** 直接修改 V1 `concepts.jsonl` 或应用 LLM Revision。拒绝，因为旧节点混合了多种语义身份，逐节点迁移会把历史错误固化到新契约中。

### 2. 采用四个类型化 JSONL 加 Manifest

```text
field-semantic-index-v2/
├─ base_concepts.jsonl
├─ concept_expressions.jsonl
├─ field_semantic_results.jsonl
├─ field_facets.jsonl
├─ manifest.json
├─ diagnostics/              # 可选，非Canonical
└─ review/                   # Projection
```

核心字段建议：

- `base_concepts`：`concept_id`、`canonical_key`、`label`、`value_kinds`、`support_status=SUPPORTED/PROVISIONAL`、`semantic_scope=DOMAIN/TECHNICAL/UNRESOLVED`、`method_id/version`、独立字段/对象/表达支持统计和 scope 依据。
- `concept_expressions`：`expression_id`、`concept_id`、`expression_kind=SOURCE_EXPRESSION/ALIAS/VARIANT`、`expression_status`、原始/规范化文本、语言、来源、装饰摘要。
- `field_semantic_results`：每个 `column_id` 一条任务结果，包含 `outcome=SINGLE_CANDIDATE/COMPETING/UNKNOWN`、零到多个嵌套候选绑定、方法局部分数、支持/冲突 Source Ref、解释和限制；绑定以 `relation_kind=EXPRESSES/RELATED_TO` 区分“字段表达该概念”和“字段仅与该概念相关”，Unknown 不引用伪造概念。
- `field_facets`：`binding_id`、`dimension`、`value`、原始片段、状态和 Source Ref。
- `manifest`：输入、配置、方法、数量、质量门、截断和 V1 基线；不读取表级业务主题分类。

`concept_id` 保持运行级；`canonical_key` 用规范中心表达和必要消歧键确定性生成，便于同一输入重放与 V1/V2 比较，但不承诺跨 Schema 或跨版本成为正式稳定实体。

**替代方案：** 把 Facet 和 Alias 嵌入一个大 `concepts.jsonl`。拒绝，因为字段到多个 Facet/竞争概念是天然多对多，嵌套结构会增加重复并使增量查询困难。

### 3. 中心词优先，修饰词不参与唯一父类选择

规范化分三层输出而不是生成一条被覆盖的清洗文本：

1. `source_expression`：完整保留字段名和注释。
2. `semantic_core_tokens`：候选中心概念。
3. `qualifier/decorator tokens`：Facet 和非语义装饰。

中心词候选综合字段名 Token、中文短语、跨字段复现、注释中心位置和低权重表上下文。前缀“当日、期初、调整前”等不得盖过后部中心词；字段类型只影响 `value_kind` 和冲突提示。

当多个中心词得分接近或英文缩写无法解析时，保留 `COMPETING/UNKNOWN`，不依赖 `其他` 桶完成覆盖。

包含一个已知中心表达并不自动意味着字段本身表达该概念。剥离 Facet 和装饰后仍有独立中心语义时，已知中心只形成 `RELATED_TO` 导航绑定；例如“名义本金重置时间”不得与“动态名义本金”同样计入名义本金的直接成员。查询可同时返回直接与相关字段，但支持门、成员计数和 `SINGLE_CANDIDATE/COMPETING` 只以 `EXPRESSES` 绑定计算。

中心语义不得等同于表达的最后一个数据形态词。V2 使用三层身份：

1. `field_family`：日期、时间、金额、数量、比率、代码、名称等宽泛字段形态，仅用于跨表召回和入口分组，不声明业务等义。
2. `semantic_core`：能够独立回答“这个字段是什么”的最小稳定复合业务短语，例如支付日期、交易日期、终止日期、敲入日期、名义本金、交易对手。
3. `facet`：移除后不改变上述核心身份的正交限定，例如实际/预计、首次/最近、初始/动态、调整前/后、原币/本币。

复合概念边界按“中文注释词尾形态优先、受控双语/缩写组合兜底、对比替换检验”产生。中文注释存在时，只有注释自身以日期/金额等形态词结尾才进入该字段族，英文列名不得覆盖不匹配的中文语义；无中文注释时，可用受控双语映射将紧邻的动作/事件词与形态词组合为候选 `semantic_core`。这是一条高精度、可解释的首版规则，不宣称已实现无词典的语料驱动发现。只有在移除某片段后剩余短语仍保持同一业务身份时，该片段才可成为 Facet。无法稳定判断时保留完整表达为 PROVISIONAL、COMPETING 或 UNKNOWN，不得退化成宽泛形态词。

**替代方案：** 训练通用中文句法或依赖外部 Embedding。首版拒绝，因为字段注释短、格式不规则且包含大量英文缩写；本地可解释规则与语料统计更容易验证失败边界。

### 4. Facet 使用开放维度契约和受控规则，不使用概念特例

配置提供通用维度及语言模式，例如：

- `temporal_stage`：初始、期初、期末、当前、调整前、调整后。
- `direction`：多头、空头、买入、卖出、支付、收取。
- `currency_basis`：原币、本币、标的币种、结算币种和显式币种代码。
- `party_role`：客户、我方、对手方、源侧、目标侧。
- `lifecycle_stage`：委托、成交、持仓、清算、终止。
- `measure_state`：动态、固定、可用、冻结、累计、预估。
- `unit/format/sequence`：单位、格式和数字槽位；默认仅为候选。

维度集合是配置化开放枚举；未知修饰词保存为 `UNRESOLVED_QUALIFIER`，而不是丢弃或自动升级概念。语料中高频出现但未进入受控维度的修饰片段只生成 Facet 候选，不自动更新配置。规则针对语言模式和维度，不针对某个业务概念。

Facet 词表不是无条件拆词表。`PAY/EXECUTION/TERMINATION/CLEARING` 等词只有在不构成稳定复合概念身份时才可作为 direction/lifecycle Facet；“支付日期、交易日期、终止日期、清算日期”中的动作/事件词属于 semantic core。Facet 提取必须通过“移除后核心身份保持不变”的校验，否则保留在核心短语中。

**替代方案：** 允许任意修饰词直接成为树节点。拒绝，因为多个正交维度组合会指数膨胀，且无法进行组合筛选。

### 5. 相似度和聚类降级为候选召回，不再直接定义基础概念

保留字符 n-gram、TF-IDF、Token 和低权重上下文，用于：

- 召回可能的 Alias/Variant；
- 发现中英文或缩写近似；
- 给出竞争基础概念候选；
- 发现离群和冲突。

高精度规范化等价可进入 deterministic alias class；近似相似只生成有界候选边。层次聚类如继续使用，只能形成 run-scoped candidate family，随后必须经过中心词/Facet分解，不能把 dendrogram 层级直接发布为业务 `is-a`。

**替代方案：** 完全删除成熟相似算法，只用词典规则。拒绝，因为异名同义和缩写召回仍需要统计相似；问题在其职责越界，不在算法本身存在。

### 6. Alias、Variant、Source Expression 和噪声分层

判定顺序从高精度到低精度：

1. Unicode、大小写、空白、连接符等规范化等价 → `ALIAS`。
2. 已配置双语/缩写映射且其他信号不冲突 → `expression_kind=ALIAS`、`expression_status=CANDIDATE`。
3. 共享中心概念且可拆出 Facet → `VARIANT`。
4. 仅文本相似但中心概念不稳 → 竞争绑定。
5. 疑似错字、截断、拼接、序号槽位 → quarantine/待核查表达。

所有阶段保留原始表达。自动修正只产生候选规范文本，不覆盖 Physical Fact 注释。

同属 `field_family` 不构成 Alias 或 Variant。“起息日期、交易日期、终止日期、敲入日期”可以共同出现在“日期类字段”调查入口，但彼此仍是独立 semantic core；除非有额外证据，不得因为尾词、类型或相似度相同而归入同一 Alias/Variant 集合。

基础概念发布再分两级：满足配置化独立复现门的标记为 `SUPPORTED` 并进入默认导航；可解析但证据单薄的标记为 `PROVISIONAL`，仍可搜索和反查字段。默认支持门要求至少两个独立物理字段，并由跨对象复现或多个不同 Facet/表达提供第二视角；门槛可配置但必须进入 Manifest，不能因验收概念名称改变。

支持强度不能代替概念用途。另设 `semantic_scope`：通用创建/更新/删除、同步、来源追踪、技术配置等模式可形成 `TECHNICAL` 候选；业务属性候选为 `DOMAIN`；无法稳定判断时为 `UNRESOLVED`。三者全部保留，审阅页分区展示，避免高频技术字段因复现充分而淹没业务调查入口。scope 规则仍须通用、版本化并接受变形测试，不能按表或概念定点指定。

### 7. 质量门以结构不变量和调查效用为主

硬门包括：

- 规范化同名父子关系为 0；V2 本身不发布固定父子树。
- 已识别的数据字典、枚举和格式装饰不得成为独立基础概念。
- 每个绑定引用有效 `column_id`，每个 Concept/Facet/Expression 引用可解析。
- `UNKNOWN/COMPETING/CONFLICT` 不得被转换为兜底 Concept。
- `EXPRESSES` 与 `RELATED_TO` 必须分开计数；一个宽泛中心词不得仅因出现在长注释中吞并日期、比率、收益或状态字段。
- 相同输入、配置和版本的内容哈希与规范结果一致。
- 不存在范围、表名、字段名或验收概念的算法特例。
- 用合成词替换验收样本的中心词后，中心词/Facet/状态结构保持同构，防止通用配置演化成概念特例。
- 对高频形态族执行“复合概念保真”审计：日期、金额、代码、名称等不得吞并具有稳定动作、事件、对象或口径身份的复合概念。
- 业务审阅卡必须使用中文说明“字段族、基础概念、别名、限定条件、相关字段”，机器枚举默认折叠；若用户必须理解 `EXPRESSES`、`lifecycle_stage=...` 才能完成判断，则业务可读性 Gate 失败。

比较指标报告但不设武断通过比例：基础概念数、单成员基础概念数、Alias/Variant数、Facet覆盖、Conflict/Unknown、V1→V2合并/拆分分布。五类代表样本需要逐项展示“理解发生了什么变化”，而不是只报告聚类内部指标。

### 8. Review Projection 使用预构建轻量索引和有界 DOM

完整 HTML 不是第一交付。Canonical 结果完成后先生成 CLI/Markdown/JSON 轻量报告，验证结构硬门和五类调查能否仅靠结果文件完成概念—字段—表查询。只有该语义形态 Gate 通过，才实现下述页面索引和交互；失败时保留运行和报告，不为页面继续投入。

生成阶段构建紧凑的只读 Projection 索引：

- concept → bindings；
- facet dimension/value → bindings；
- column/table → bindings；
- normalized expression → concept candidates。
- semantic scope → concepts/bindings。

页面首屏只加载概念/Facet摘要，详情通过分片 JSON 或 Worker 按需读取；任何列表分页。默认业务视图先展示字段族、稳定基础概念、业务化限定条件和具体字段，工程枚举置于可展开技术详情。Object Card 链接复用现有 URI 规则。本 Change 不把表级业务主题接入审阅页；稳定物理 ID 仅为未来独立组合 Projection 保留连接点。

**替代方案：** 在浏览器内加载并渲染完整图。拒绝，因为当前单 Schema 页面已经出现卡顿，扩大后 DOM 和主线程扫描都会线性恶化。

### 9. LLM 只审阅压缩后的冲突，不进入生成闭环

现有全量树体检可作为设计证据，现有逐簇 LLM Review 作为历史旁路保留。V2 若未来接 LLM，只发送确定性输出的最小 Conflict/Unknown Pack，返回 Alias/Variant/Facet/Concept 修订候选；不得触发第二轮无界传播或自动写回。

当前实现阶段无需 Provider，现有 D-005 当前会话授权也不自动转化为 SDK 授权。

## Risks / Trade-offs

- [中心词规则仍可能误判短注释] → 保留竞争候选与 Unknown，并以五类不同错误模式的样本和反例驱动通用测试。
- [Facet 词表逐渐膨胀成隐性本体] → 只允许通用维度与语言模式；新增项记录来源和覆盖统计，概念特有规则禁止进入主配置。
- [高频技术字段满足支持门后淹没业务候选] → 将支持强度与 DOMAIN/TECHNICAL/UNRESOLVED 分区解耦，全部可检索但默认导航分别展示。
- [四个 JSONL 比 V1 两个文件复杂] → 这是多对多语义的最小规范化集合；页面和导出提供合并 Projection，用户不必直接理解文件结构。
- [V1 与 V2 数量无法直接比较] → 比较以共享字段、表达和调查任务为单位，不把节点数下降本身当成准确性提高。
- [没有列值仍无法解决真实同名异义] → 显式 Conflict/Unknown，测试库结构和类型不作为最终业务真值。
- [配置驱动被误解为跨 Schema 可用] → Manifest 和页面固定显示验证范围；另一个 Schema 必须新授权和独立验证。
- [同时接入表级业务分类导致范围与误差来源混杂] → 当前 Change 完全解耦，只保留物理 ID 连接点，待 V2 本身验证后另行组合。

## Migration Plan

1. 冻结并记录当前 V1、全树体检和 LLM Review 的输入/输出位置与哈希。
2. 定义 V2 类型、Schema 校验器和最小合成 fixture，先覆盖中心词、Facet、Alias、Conflict 和 Unknown。
3. 实现 V2 确定性流水线与质量门，不改 V1 命令和输出。
4. 在固定 TRADEFLOW 233 表输入上生成独立 V2，并形成按 `column_id` 对齐的 V1/V2 轻量比较及五类调查报告。
5. 执行语义形态与业务可读性 Gate；若结构硬门、复合概念保真或结果级双向查询未通过，保留失败结果并停止完整页面建设。
6. Gate 通过后生成有界审阅页面并验证交互性能；若最终可见改善仍不足，恢复 V1 页面入口。
7. 只有本 Change 验收通过时，才将 V2 设为当前字段调查入口，且仍不扩大 Schema。

回滚时停止使用 V2 输出并恢复 V1 页面入口；Physical Facts、V1、LLM Review 和其他 Panorama 结果不需要恢复操作。
