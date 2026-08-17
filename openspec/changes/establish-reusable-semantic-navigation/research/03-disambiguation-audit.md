# 字段语义消歧与反例审计报告

## 元数据

- **审计标识**: 03-disambiguation-audit
- **审计角色**: 字段语义消歧和反例审计师
- **源运行**: stage3-tradeflow-context-semantic-map-v1-20260812
- **导航运行**: stage5-tradeflow-semantic-navigation-v1-20260813
- **审计日期**: 2026-08-14
- **前置分析**: 02-field-shapes.json（字段语料与覆盖分析）

## 审计方法

本审计以 Stage 3 上下文语义结果和 Stage 5 导航投影为对象，逐条检查以下数据源：

- `business_concepts.jsonl`（1375 条业务概念）
- `attribute_expressions.jsonl`（1559 条属性表达）
- `qualifiers.jsonl`（32 条限定条件）
- `semantic_observations.jsonl`（5347 条语义观测，含原始 raw_facets）
- `diagnostics/data_semantic_candidates.jsonl`（1559 条数据语义候选）
- `diagnostics/semantic_review_queue.jsonl`（859 条审查队列项）

核心交叉验证路径：物理列名（column_name）→ 中文注释（column_comment）→ raw_facets → qualifier_signature → 属性表达标签。当物理列名中的英文 token 与中文注释的业务含义冲突时，判定为误归类。

## 误归类清单

### 严重度 1（CRITICAL）：短名/简称误判为空头 SHORT

**影响范围**：18 个物理字段实例，涉及 3 个属性表达，12 张表。

**根因**：`field-semantics-v2.yaml` 的 facet 配置 `direction.SHORT: [空头, SHORT]` 中包含英文 token `SHORT`。物理列名 `CTPTY_SHORT_NAME`、`SHORT_NAME` 中的 `SHORT` 被提取为 `direction: SHORT` 限定，再经 `qualifier_axes.mappings.direction.SHORT → position_side` 映射为 `position_side: SHORT`（空头）。但此处的 `SHORT` 是"短名"（abbreviated name）的英文缩写，不是"空头持仓"（short position）。

**受影响属性表达**：

| 属性表达标签 | 业务概念 | qualifier_signature | field_count | 表数 |
|---|---|---|---|---|
| 交易对手短名（空头） | 交易对手短名 | position_side: SHORT | 12 | 12 |
| 交易对手简称（空头） | 交易对手简称 | position_side: SHORT | 5 | 5 |
| 客户短名（空头） | 短名 | party_role: CLIENT, position_side: SHORT | 1 | 1 |

**物理证据**（代表性实例）：

| 表名 | 列名 | 中文注释 | raw_facets（提取结果） | 正确解释 |
|---|---|---|---|---|
| TRD_LS_DEAL | CTPTY_SHORT_NAME | 交易对手短名 | direction: SHORT（来自列名） | 交易对手的简称属性，非空头 |
| TRD_OPTION_MANUAL_TRADE_DEAL | CTPTY_SHORT_NAME | 交易对手简称 | direction: SHORT（来自列名） | 交易对手的简称属性，非空头 |
| TRD_CLN_TRADE_DEAL | CTPTY_SHORT_NAME | 客户短名 | direction: SHORT, party_role: CLIENT | 客户的简称属性，非空头 |
| TRD_PRE_TRADE_VALIDATION_LOG | SHORT_NAME | 交易对手简称 | direction: SHORT（来自列名） | 交易对手的简称属性，非空头 |

**无冲突证据**：`CTPTY_NAME`（列名不含 SHORT）和 `CTPTY_SHTNAME`（缩写形式）的同类字段 `raw_facets` 为空，说明系统识别了它们不包含方向限定——但 `CTPTY_SHORT_NAME` 因包含完整 `SHORT` token 被误判。

### 严重度 1（CRITICAL）：长名误判为多头 LONG

**影响范围**：1 个物理字段实例。

**根因**：与 SHORT 同理。物理列名 `CTPTY_LONG_NAME` 中的 `LONG` token 被 `direction.LONG: [多头, LONG]` 匹配，映射为 `position_side: LONG`（多头）。

**物理证据**：

| 表名 | 列名 | 中文注释 | raw_facets | 正确解释 |
|---|---|---|---|---|
| TRD_TRS_ORDER | CTPTY_LONG_NAME | 交易对手长名 | direction: LONG（来自列名） | 交易对手的全称属性，非多头 |

### 严重度 2（MODERATE）：SOURCE/TARGET 数据流向与业务主体混淆

**影响范围**：15 个属性表达含 `flow_side: SOURCE` 或 `flow_side: TARGET`。

**根因**：`field-semantics-v2.yaml` 的 `party_role` facet 同时包含 `SOURCE: [源侧, 来源方, SOURCE]` 和 `TARGET: [目标侧, TARGET]`。`qualifier_axes` 映射将 `party_role: SOURCE → flow_side`，`party_role: TARGET → flow_side`。这导致两种不同语义被压入同一维度：

1. **数据流向**：源侧/目标侧——描述数据迁移或映射的方向（正确归属 flow_side）
2. **业务主体关系**：目标交易对手——描述交易对手在业务映射中的角色（不应归属 flow_side）

**关键反例**：

| 属性表达标签 | 物理列名 | 中文注释 | 当前限定 | 问题 |
|---|---|---|---|---|
| 目标交易对手 | TARGET_CTPTY_ID | 目标交易对手 | flow_side: TARGET | "目标"是业务映射关系，非数据流方向 |
| 目标交易对手ID | TARGET_CTPTY_ID | 目标交易对手ID | flow_side: TARGET, attribute_kind: IDENTIFIER | 同上 |
| 源侧交易对手 | SOURCE_CTPTY_ID | 源侧交易对手ID | flow_side: SOURCE | "源侧"是数据流方向，但被附加到交易对手实体上 |

**注意**：`"事件来源类型（源侧）"`、`"估值汇率来源（源侧）"`等表达中的"来源"指业务来源而非数据流方向，也被误标为 `flow_side: SOURCE`。

### 严重度 2（MODERATE）：简称/缩写被提升为独立业务概念

**影响范围**：7 个业务概念。

以下概念在 `business_concepts.jsonl` 中以 `DOMAIN` scope 存在为独立业务概念，但它们实际上是字段属性表达（"名称"这一基础概念的限定变体），不是独立业务实体：

| 业务概念标签 | support_status | 正确层次 |
|---|---|---|
| 简称 | SUPPORTED | 字段属性（名称的限定） |
| 缩写 | PROVISIONAL | 字段属性 |
| 名称缩写 | PROVISIONAL | 字段属性 |
| 短名 | PROVISIONAL | 字段属性 |
| 交易对手短名 | SUPPORTED | 交易对手概念的属性表达 |
| 交易对手简称 | SUPPORTED | 交易对手概念的属性表达 |
| 交易对手长名 | PROVISIONAL | 交易对手概念的属性表达 |

**层次混淆**：这些概念被 Stage 5 导航配置（`reusable-semantic-navigation.yaml`）统一收录到 `reader:counterparty` 的 `source_labels` 中，与"交易对手"本体并列。虽然导航层的合并处理可以接受，但概念层将"简称"等同于"交易对手"是层次混淆。

### 严重度 2（MODERATE）：状态/类型/金额/币种/日期被提升为业务概念

**影响范围**：7 个业务概念。

| 业务概念 | support_status | 正确层次 |
|---|---|---|
| 状态 | SUPPORTED | 字段属性分类 |
| 状态信息 | PROVISIONAL | 字段属性 |
| 类型 | SUPPORTED | 字段属性分类 |
| 金额 | SUPPORTED | 字段族（field_family） |
| 金额乘数 | SUPPORTED | 字段属性 |
| 币种 | SUPPORTED | 字段属性分类 |
| 日期 | SUPPORTED | 字段族（field_family） |

这些泛化词被 `field-semantics-v2.yaml` 的 `field_families` 和 `broad_categories` 定义为字段族或分类，但 context_semantics 的投影仍将它们发布为 `DOMAIN` scope 的业务概念。读者可能误以为"状态"是一个业务对象。

### 严重度 3（LOW）：订单与交易在导航层合并

**影响范围**：Stage 5 导航配置 `reader:trade-order` 的 `source_labels` 同时包含"交易"和"订单*"系列概念。

**分析**：导航配置将 `交易`、`交易ID`、`交易内部编号`、`交易状态`、`交易日期`、`交易时间` 与 `订单编号`、`交易台订单编号`、`内部订单编号` 等合并到同一个 reader concept "交易/订单"下。虽然这两个对象在业务上确实关联紧密，但：
- "交易"对应 `trade-agreement` 生命周期阶段（成交阶段）
- "订单"对应 `trade-agreement` 的前置（委托阶段）
- 二者不应在概念层被合并为单一业务对象

当前的 `excluded_expression_labels: [NET_TOTAL_VALUE_TRADE]` 排除了一个误归类的字段，说明系统已意识到部分问题，但未系统性解决。

### 严重度 3（LOW）：REF_LS_TRS 列名/注释方向冲突

**影响范围**：1 个物理字段实例。

| 表名 | 列名 | 中文注释 | raw_facets | 问题 |
|---|---|---|---|---|
| REF_LS_TRS | SHORT_DYNAMIC_NOTIONAL_ORG | 多头动态名义本金（结算币种） | direction: SHORT（列名）+ direction: LONG（注释"多头"） | 列名说 SHORT，注释说多头 |

系统同时提取了两个冲突的 direction facet（SHORT 和 LONG），但最终归属到"空头动态名义本金（结算币种）"表达。注释中的"多头"应优先于列名中的 `SHORT` token，因为注释是业务人员书写的语义声明。

### 正确分类确认

以下表达虽然包含 SHORT/LONG 限定，但经物理证据验证为**正确分类**：

| 属性表达 | 物理列名 | 中文注释 | 判定 |
|---|---|---|---|
| 空头动态名义本金（结算币种） | SHORT_DYNAMIC_NOTIONAL | 空头动态名义本金（结算币种） | CORRECT — 注释明确"空头" |
| 空头动态名义本金（标的币种） | SHORT_DYNAMIC_NOTIONAL_ORG | 空头动态名义本金（标的币种） | CORRECT — 注释明确"空头" |
| 多头动态名义本金（标的币种） | LONG_DYNAMIC_NOTIONAL | 多头动态名义本金（标的币种） | CORRECT — 注释明确"多头" |
| 卖空数量（空头） | — | 卖空数量 | CORRECT — "卖空"即空头卖出 |
| 平空数量（空头） | — | 平空数量 | CORRECT — "平空"即平仓空头 |
| 计息起止（多头） | INTEREST_INTERVAL_L | 计息起止（多头） | CORRECT — 注释明确"多头" |
| 计息起止（空头） | INTEREST_INTERVAL_S | 计息起止（空头） | CORRECT — 注释明确"空头" |
| 空头内在价值系数 | SHORT_INNER_VALUE_RATIO | 空头内在价值系数 | CORRECT — 注释明确"空头" |
| 多头内在价值系数 | LONG_INNER_VALUE_RATIO | 多头内在价值系数 | CORRECT — 注释明确"多头" |

## 当前最严重的语义错误（按影响排序）

### 排名 1：英文 token SHORT/LONG 在物理列名中的歧义爆炸

- **错误类**：英文物理字段名冒充业务属性表达
- **影响**：18 个字段被误判为 `position_side: SHORT`（空头），1 个字段被误判为 `position_side: LONG`（多头）。读者在语义导航页面上看到"交易对手短名（空头）"，会误以为这是空头持仓相关的交易对手属性。
- **根因路径**：`field-semantics-v2.yaml` facets → `direction: SHORT/LONG` → `qualifier_axes` → `position_side`
- **最小修复原则**：在 facet 提取阶段，当 `SHORT`/`LONG` token 出现在物理列名中但中文注释不包含"空头"/"多头"时，不提取该 facet；或将 `SHORT`/`LONG` 从 `direction` facet 的英文 pattern 中移除，仅保留中文 pattern `[空头]` / `[多头]`。

### 排名 2：SOURCE/TARGET 的 flow_side 与 party_role 语义混淆

- **错误类**：数据流向与业务主体角色混淆
- **影响**：15 个属性表达被附加 `flow_side` 限定，其中至少 3 个（目标交易对手、事件来源类型、估值汇率来源）属于业务语义而非数据流方向。
- **根因路径**：`party_role: SOURCE/TARGET` → `qualifier_axes` → `flow_side`
- **最小修复原则**：区分 `party_role` 中的数据流角色（源侧/目标侧）与业务映射角色（目标交易对手）。对于"目标交易对手"等业务关系，不应提取 `flow_side` 限定，而应保留为 `party_role` 或标记为 `RELATED_TO` 关系。

### 排名 3：泛化词被提升为 DOMAIN scope 业务概念

- **错误类**：字段属性/字段族混入业务对象树
- **影响**："状态"、"类型"、"金额"、"币种"、"日期"、"简称"、"缩写"等泛化词被发布为 DOMAIN scope 业务概念，读者可能误以为它们是独立业务实体。
- **根因路径**：`field-semantics-v2.py` 的概念提升逻辑未将 `field_families` 和 `broad_categories` 级别的概念降级为 `ATTRIBUTE` scope。
- **最小修复原则**：在 context_semantics 投影时，将 `field_families` 和 `broad_categories` 中已定义的泛化词（状态、类型、金额、币种、日期、简称、缩写）的 `semantic_scope` 从 `DOMAIN` 降级为 `ATTRIBUTE`，或从导航投影中排除。

### 排名 4：列名/注释方向冲突时优先级错误

- **错误类**：物理实现冒充业务属性表达
- **影响**：`SHORT_DYNAMIC_NOTIONAL_ORG` 列名含 `SHORT` 但注释为"多头"，系统同时提取两个冲突 facet 后归属到空头表达。
- **根因路径**：facet 提取不区分列名来源与注释来源的优先级
- **最小修复原则**：当列名 token 与注释中文词义冲突时，注释优先；或为冲突情况标记 `CONFLICT` 状态而非自动归属。

## 最小修复原则汇总（不实现）

1. **SHORT/LONG 英文 token 消歧**：facet 配置中 `direction.SHORT` 和 `direction.LONG` 的英文 pattern 仅在中文注释不含"空头"/"多头"时不应匹配，或在提取后由兼容性检查器拒绝。
2. **SOURCE/TARGET 双语义分离**：`party_role` 中的 `SOURCE`/`TARGET` 与 `flow_side` 应分离为两个独立维度，或在 `qualifier_axes` 映射中不再将 `party_role: SOURCE/TARGET` 映射到 `flow_side`。
3. **泛化词概念降级**：`field_families` 和 `broad_categories` 定义的词在 context 投影中应标记为 `ATTRIBUTE` 或 `TECHNICAL` scope，不进入业务概念树。
4. **列名/注释冲突优先级**：当物理列名英文 token 与中文注释词义冲突时，注释优先；冲突标记为 `CONFLICT` 而非自动消解。

## 边界声明

- 本审计为工程层面的只读审查，不修改任何实现代码或配置。
- 审计结论不等于业务验收，不设置 `business_acceptance=ACCEPTED`。
- Gold Set 中的状态标记为审计师独立判定，需用户确认后才能升级为正式 Gold Set。
- 本审计仅覆盖 TRADEFLOW 一个 Schema，不适用于其他 Schema。
