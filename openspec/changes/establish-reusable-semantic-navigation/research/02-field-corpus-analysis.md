# TRADEFLOW 字段语料与覆盖分析

> **分析师角色**：字段语料与覆盖分析师。本报告不负责设计顶层业务本体，只为业务骨架架构师提供事实依据。
>
> **数据来源**：`output/stage3-tradeflow-context-semantic-map-v1-20260812/context-enriched-field-semantic-map/`
>
> **分析日期**：2026-08-14
>
> **边界声明**：以下所有统计基于全量记录读取，非抽样推断。所有候选概念均为 CANDIDATE 状态，不构成已确认事实。报告不修改任何现有代码、配置或正式输出。

---

## 1. 全量概念、属性表达、字段实例和表覆盖统计

### 1.1 语料总量

| 统计项 | 数值 | 数据来源 |
|--------|------|----------|
| 业务概念 (business_concepts) | 1,375 | business_concepts.jsonl |
| 属性表达 (attribute_expressions) | 1,559 | attribute_expressions.jsonl |
| 数据语义候选 (data_semantic_candidates) | 1,559 | diagnostics/data_semantic_candidates.jsonl |
| 语义观察 (semantic_observations) | 5,347 | semantic_observations.jsonl |
| 语义假设 (semantic_hypotheses) | 2,243 | semantic_hypotheses.jsonl |
| 语义关系 (semantic_relations) | 8,740 | semantic_relations.jsonl |
| 业务上下文 (business_contexts) | 4 | business_contexts.jsonl |
| 限定词 (qualifiers) | 32 | qualifiers.jsonl |
| 语义映射候选 (semantic_mapping_candidates) | 4,075 | diagnostics/semantic_mapping_candidates.jsonl |
| 语义规范化候选 (semantic_normalization_candidates) | 1,602 | diagnostics/semantic_normalization_candidates.jsonl |
| 语义复核队列 (semantic_review_queue) | 859 | diagnostics/semantic_review_queue.jsonl |

### 1.2 字段实例与表覆盖

| 统计项 | 数值 | 说明 |
|--------|------|------|
| 候选中唯一字段引用数 | 4,294 | data_semantic_candidates 的 field_refs 去重 |
| 观察中唯一字段引用数 | 5,342 | semantic_observations 的 column_id 去重 |
| 物理字段实例总数 | 4,294 | physical_instances 总计数 |
| 候选覆盖的表数 | 233 | physical_instances 中的 object_name 去重 |
| TRADEFLOW 总表/视图数 | 477 | Stage 0 objects.json |
| TRADEFLOW 总字段数 | 13,611 | Stage 0 columns.json |
| Manifest 声明源字段数 | 5,512 | manifest.json stats.source_field_count |

**覆盖率说明**：候选语料覆盖 233/477 = 48.9% 的 TRADEFLOW 表，覆盖 4,294/13,611 = 31.5% 的物理字段。覆盖率不代表语义正确性，仅反映确定性语料归拢范围。

### 1.3 业务上下文

| 上下文 ID | 类型 | 标签 | 来源提示 |
|-----------|------|------|----------|
| business-context-9a2c7597... | PRODUCT | IRS | KEY_LEG_ID (REF_IRS_CASH_FLOW) |
| business-context-3550b2c6... | PRODUCT | OPTION | SELLER (OTC_OPTION_PARAMETER) |
| business-context-9f26b6d1... | PRODUCT | TRS | CLEAN_PRICE (TRS_UNWIND_INSTRUCTION) |
| business-context-de9cd971... | UNKNOWN | 上下文未确认 | CAPPITECH_UTI (TRD_OTC_CONTR_REPORT) |

**发现**：仅 3 个产品上下文（IRS、OPTION、TRS）被确定性识别，1 个为"上下文未确认"。这说明语料覆盖偏重 TRS/期权类业务，IRS 利率互换仅通过现金流表进入，外汇远期等产品类型缺乏独立上下文锚定。

### 1.4 限定词维度

| 维度 | 候选值 |
|------|--------|
| aggregation_state | ACCUMULATED |
| attribute_kind | IDENTIFIER |
| availability_state | AVAILABLE, FROZEN |
| cashflow_direction | PAY, RECEIVE |
| currency_basis | LOCAL_CURRENCY, ORIGINAL_CURRENCY, SETTLEMENT_CURRENCY, UNDERLYING_CURRENCY |
| estimation_status | ESTIMATED |
| flow_side | SOURCE, TARGET |
| lifecycle_stage | CLEARING, EXECUTION, ORDER, POSITION, TERMINATION |
| measure_basis | ABSOLUTE |
| party_role | CLIENT, INTERNAL |
| position_side | LONG, SHORT |
| temporal_stage | AFTER_ADJUSTMENT, BEFORE_ADJUSTMENT, CURRENT, END, INITIAL |
| trade_side | BUY, SELL |
| variability | DYNAMIC, FIXED |

**发现**：14 个限定词维度覆盖了方向、时态、币种基准、生命周期阶段等核心属性轴。但 `party_role` 仅含 CLIENT 和 INTERNAL，缺少 SELLER/BUYER 等 OTC 交易角色——这些角色在物理字段中以独立概念出现（如"卖方名称"），未进入限定词系统。

### 1.5 属性表达分布

| 统计项 | 数值 |
|--------|------|
| 有 qualifier_signature 的表达 | 495 / 1,559 (31.8%) |
| 无 qualifier_signature 的表达 | 1,064 / 1,559 (68.2%) |
| 有父级表达 (display_parent) | 159 |
| 有 contextual_qualifiers | 7 |
| 有冲突 (conflicts) | 0 |
| 有不确定性 (uncertainties) | 0 |

**字段数分布**：1 字段=971, 2-5 字段=478, 6-20 字段=93, 20+ 字段=17

**对象数分布**：1 对象=1,008, 2-5 对象=444, 6-20 对象=90, 20+ 对象=17

**发现**：68.2% 的属性表达仅覆盖单个字段和单个对象，说明大量概念是从单一表单一字段中发现，跨表复现率低。20+ 字段的 17 个高覆盖表达是骨架挂接的核心候选。

### 1.6 语义复核队列

| 复核类型 | 数量 | 原因 |
|----------|------|------|
| QUALIFIED_VARIANT | 498 | RECURRENT_CORE_WITH_UNTYPED_MODIFIER |
| SAME_PHYSICAL_NAME_DIFFERENT_COMMENT | 361 | （同名异注释） |

**发现**：859 条复核队列中，498 条是"重复核心词+未分类修饰词"（如 Price → CleanPrice），361 条是"同一物理字段名出现不同注释"。后者是同名异义风险的主要来源。

---

## 2. 按预设骨架统计

以下统计将 1,375 个业务概念逐一与 `reusable-semantic-navigation.yaml` 中的预设导航骨架（5 个 reader 概念、6 个生命周期阶段、10 个业务区域、9 个属性轴）进行匹配。

| 骨架支持类别 | 概念数 | 占比 | 说明 |
|-------------|--------|------|------|
| 明确可挂接 (direct_attach) | 57 | 4.1% | 标签直接匹配骨架 reader 概念源标签或业务区域/阶段术语 |
| 多入口候选 (multi_entry) | 0 | 0% | 本轮无概念同时匹配多个 reader 概念 |
| 属性表达 (attribute_expr) | 377 | 27.4% | 概念的属性表达携带 qualifier_signature，属于修饰维度而非独立业务节点 |
| 字段属性 (field_attribute) | 605 | 44.0% | 覆盖范围小（≤1 字段、≤1 对象），更像字段级属性而非业务概念 |
| 限定条件 (qualifier_cond) | 0 | 0% | 概念标签与限定词值无直接匹配 |
| 技术/审计字段 (tech_audit) | 1 | 0.1% | 标签匹配审计模式（如 created/updated 等） |
| 证据不足 (insufficient) | 2 | 0.1% | 无字段实例且无属性表达 |
| 真正无法解释 (unexplained) | 333 | 24.2% | 不匹配任何骨架术语，且非属性表达、非技术字段 |
| **合计** | **1,375** | **100%** | |

### 2.1 明确可挂接的 57 个概念

这 57 个概念可直接挂接到预设骨架的 reader 概念或业务区域/阶段。

**挂接到 reader:notional（名义本金）**：
- 名义本金（55 字段，19 表）→ contract-lifecycle / valuation-collateral-cashflow

**挂接到 reader:counterparty（交易对手）**：
- 交易对手（60 字段，60 表）、交易对手主键（6 字段）、交易对手名称缩写（1 字段）、交易对手备注（4 字段）、交易对手所属部门（2 字段）、交易对手短名（15 字段）、交易对手简称（8 字段）、交易对手缩写（13 字段）、交易对手长名（1 字段）、原交易对手类型（1 字段）、原始交易对手（1 字段）、源侧交易对手（1 字段）、目标交易对手（1 字段）、背靠背交易对手（1 字段）、背靠背交易对手缩写（1 字段）

**挂接到 reader:trade-order（交易/订单）**：
- 交易（12 字段）、交易内部编号（6 字段）、交易台订单编号（2 字段）、交易日期（41 字段）、交易时间（1 字段）、交易状态（2 字段）、内部订单编号（1 字段）、用户子订单（2 字段）、用户订单（2 字段）、系统内部订单（1 字段）、系统算法订单编号（1 字段）、订单业务主键（1 字段）、订单唯一（1 字段）、订单日期（1 字段）、订单时间（1 字段）、订单编号（4 字段）

**挂接到 reader:position（持仓）**：
- 持仓（4 字段）、持仓数量（4 字段）、持仓日期（3 字段）、持仓来源（3 字段）、持仓类型（2 字段）

**挂接到 reader:margin（保证金）**：
- 保证金（8 字段）、保证金余额（1 字段）、保证金初始线（4 字段）、保证金提取线（4 字段）、保证金提取维持线（4 字段）、保证金方向（4 字段）、保证金比例（1 字段）、保证金追保线（4 字段）、保证金追保维持线（4 字段）、保证金金额（2 字段）、保证金预警线（3 字段）、基础保证金率（10 字段）

**挂接到业务区域（无 reader 匹配）**：
- 交易员（6 字段，participants）、交易所（13 字段，reference-configuration）、支付（2 字段，execution-clearing-settlement）、结算（1 字段，execution-clearing-settlement）、Price（1 字段，valuation-collateral-cashflow）

### 2.2 关键缺口说明

**multi_entry = 0** 说明本轮匹配逻辑未发现同一概念同时匹配多个 reader 概念。但"交易日期"既匹配 reader:trade-order 又出现在 contract-lifecycle 和 clearing-settlement 的术语集中——这属于"同一概念在多个阶段出现"，而非"匹配多个 reader 概念"，因此未计入 multi_entry。实际多入口风险集中在"名义本金"（同时是 contract-lifecycle 的 core object 和 valuation-risk 的 cross-stage term）和"持仓"（同样跨阶段）。

---

## 3. 高频但不应成为业务节点的字段形态

以下字段在多张表中高频出现，但它们是技术审计或通用标识字段，不应仅因词频高而被提升为顶层业务分类节点。

| 字段名 | 实例数 | 覆盖表数 | 不应成为业务节点的原因 |
|--------|--------|----------|----------------------|
| UPDATED_DATETIME | 222 | 222 | 纯审计字段，无业务语义 |
| CREATED_DATETIME | 213 | 213 | 纯审计字段，无业务语义 |
| UPDATED_BY | 189 | 189 | 审计操作人，非业务参与主体 |
| CREATED_BY | 185 | 185 | 审计操作人，非业务参与主体 |
| ID | 44 | 44 | 通用技术主键，无独立业务含义 |
| CURRENCY | 39 | 39 | 参考属性，适合作为属性轴而非业务节点 |
| QUANTITY | 34 | 34 | 通用计量字段，语义依赖表上下文 |
| WIND_CODE | 31 | 31 | 外部标识引用，非业务核心概念 |
| REMARK | 19 | 19 | 通用备注字段，无独立语义 |

**反例说明**：以下高频字段虽词频高，但确实承载业务语义，不应被归入"非业务"类别：

| 字段名 | 实例数 | 应归入的业务域 | 理由 |
|--------|--------|---------------|------|
| KEY_CTPTY_ID | 58 | 交易对手 | 交易对手主键，跨表引用核心实体 |
| KEY_OTC_TRADE_ID | 57 | 交易/合约 | OTC 交易主键，跨表引用核心实体 |
| TRADE_DATE | 50 | 交易/订单 | 交易达成日期，已挂接 reader:trade-order |
| UNDERLYING_INS_ID | 42 | 产品/标的 | 标的物主键，跨表引用 |
| KEY_PLAN_ID | 39 | 合同/合约腿 | 业务方案主键，跨表引用 |
| BUSINESS_TYPE | 30 | 产品/标的 | 业务类型分类字段 |
| TRANSACTION_TYPE | 26 | 交易/订单 | 交易品种分类字段 |
| TRADE_AMOUNT | 25 | 交易/订单 | 交易金额计量 |

---

## 4. 可能缺失的稳定业务概念（候选）

以下概念在语料中有可观的字段覆盖和表分布，但未匹配预设骨架任何术语。它们是 **候选**，不构成已确认事实，需要业务骨架架构师判断是否纳入。

### 候选 1：业务类型 (BUSINESS_TYPE)

| 项 | 值 |
|----|-----|
| 字段数 | 36 |
| 覆盖表数 | 35 |
| 属性类型 | NUMBER, TEXT |

**字段正例**：
- `FX_EXPOSURE.FE_BUSI_TYPE` // 业务类型
- `OTC_OPTION_PARAMETER.BUSINESS_TYPE` // 业务类型
- `REF_TRS_INTERNAL_TRADE.BUSINESS_TYPE` // 业务类型

**反例/歧义**：
- `REF_LARGE_NOTIONAL_LIMIT.RULE_TRD_TYPE` 注释为"业务类型"，但字段名为 RULE_TRD_TYPE，可能涉及大额交易限额规则而非通用业务类型。
- `TRD_PRE_TRADE_VALIDATION_LOG.INS_FAMILY` 注释为"合约类型"而非"业务类型"，但被归入此概念簇——存在跨概念边界。

**上下文证据**：35 张表跨 FX敞口、期权参数、TRS内部交易、大额限额等子系统，说明"业务类型"是跨产品的稳定分类维度。但其值域可能因产品而异，不宜直接作为统一分类节点。

### 候选 2：交易品种 (TRANSACTION_TYPE)

| 项 | 值 |
|----|-----|
| 字段数 | 24 |
| 覆盖表数 | 24 |
| 属性类型 | TEXT |

**字段正例**：
- `TRD_ALLMARKET_ORDER_DEAL.TRANSACTION_TYPE` // 交易品种
- `TRD_FT_TODAY_ORIGINAL_DEAL.TRANSACTION_TYPE` // 交易品种

**反例/歧义**：字段名统一为 TRANSACTION_TYPE，但覆盖全市场订单、港股通、借贷等多条业务线，"品种"语义可能不等价于跨业务线的统一分类。

**上下文证据**：24 张表全部属于交易达成区域，注释一致性高。可能是 trade-agreement 阶段下的稳定子概念。

### 候选 3：互换类型 (TRS_TYPE)

| 项 | 值 |
|----|-----|
| 字段数 | 17 |
| 覆盖表数 | 17 |
| 属性类型 | TEXT |

**字段正例**：
- `CFG_TRS_TEMPLATE.TRS_TYPE` // 互换类型
- `POS_FAST_TRS_LEG_CURRENT_POS.TRS_TYPE` // 互换类型

**反例/歧义**：
- `OTC_OPTION_PARAMETER.EXCHANGE_TYPE` 注释为"互换类型"，但字段名为 EXCHANGE_TYPE，可能实际含义是"交易所类型"而非"互换类型"——这是同名异义的反例。

**上下文证据**：主要出现在 TRS 相关的配置、持仓和交易表中。如果纳入骨架，应限定在 contract-structure 区域下的 TRS 子分类。

### 候选 4：利差 (SPREAD)

| 项 | 值 |
|----|-----|
| 字段数 | 14 |
| 覆盖表数 | 14 |
| 属性类型 | NUMBER, RATIO |

**字段正例**：
- `REF_FAST_TRS_LEG.SPREAD` // 利差
- `REF_IRS_LEG.SPREAD` // 利差(%)

**反例/歧义**：RATIO 和 NUMBER 混合，说明不同表的利差计量单位不统一（百分比 vs 基点），不宜直接合并为同一节点。

**上下文证据**：集中在合约腿参考表，是合约经济条款的组成部分。适合作为 contract-lifecycle 下的属性而非独立节点。

### 候选 5：券息 (INTEREST_RATE)

| 项 | 值 |
|----|-----|
| 字段数 | 11 |
| 覆盖表数 | 11 |
| 属性类型 | RATIO |

**字段正例**：
- `REF_FAST_TRS_LEG.INTEREST_RATE` // 券息
- `TRD_LEND_STOCK_ORDER_DEAL.INTEREST_RATE` // 券息

**反例/歧义**：字段名 INTEREST_RATE 在通用金融语境中是"利率"，但注释统一为"券息"。TRS 和借贷股票场景下的"券息"含义可能不等价。

### 候选 6：固定利率 (FIXED_INTEREST_RATE)

| 项 | 值 |
|----|-----|
| 字段数 | 12 |
| 覆盖表数 | 12 |
| 属性类型 | RATIO |

**字段正例**：
- `REF_FAST_TRS_LEG.FIXED_INTEREST_RATE` // 固定利率
- `REF_IRS_LEG.FIXED_RATE` // 固定利率(%)，固定腿

**反例/歧义**：字段名有 FIXED_INTEREST_RATE 和 FIXED_RATE 两种，注释一致但精度可能不同。

### 候选 7：创建时间/创建人 (审计字段)

| 项 | 值 |
|----|-----|
| 字段数 | 207 / 185 |
| 覆盖表数 | 204 / 185 |
| 属性类型 | DATE_TIME / TEXT |

**说明**：这两个概念虽然高频且稳定，但明确属于技术审计字段，应归入 attribute_axis: AUDIT 而非任何业务节点。

### 候选 8：合约乘数 (CONTRACT_MULTIPLIER)

| 项 | 值 |
|----|-----|
| 字段数 | 10 |
| 覆盖表数 | 10 |
| 属性类型 | NUMBER |

**字段正例**：
- `POS_TRS_LEG_CURRENT_POS.CONTRACT_MULTIPLIER` // 合约乘数
- `TRD_ATP_DEAL.CONTRACT_MULTIPLIER` // 合约乘数

**上下文证据**：跨持仓和交易表出现，是合约经济条款的计量属性。适合作为 contract-structure 下的属性。

### 候选 9：交易金额 (TRADE_AMOUNT)

| 项 | 值 |
|----|-----|
| 字段数 | 13 |
| 覆盖表数 | 13 |
| 属性类型 | NUMBER |

**字段正例**：
- `TRD_ATP_DEAL.TRADE_AMOUNT` // 交易金额
- `TRD_GFTG_TRS_DEAL.TRADE_AMOUNT` // 交易金额

**上下文证据**：跨多类交易表出现，是 trade-agreement 阶段的核心计量属性。可挂接为 reader:trade-order 下的 MEASURE 属性。

### 候选 10：委托数量 (QUANTITY / ORDER_QTY)

| 项 | 值 |
|----|-----|
| 字段数 | 13 |
| 覆盖表数 | 13 |
| 属性类型 | NUMBER |

**字段正例**：
- `TRD_ATP_ORDER_INFO.ENTRUST_QTY` // 委托数量
- `TRD_FAST_TRS_OMS_ORDER.ORDER_QTY` // 委托数量

**反例/歧义**：字段名有 QUANTITY、ORDER_QTY、ENTRUST_QTY 三种，注释统一为"委托数量"但语义可能包含成交数量和申报数量两种。

> **完整候选清单**：JSON 文件 `02-field-shapes.json` 的 `missing_business_concept_candidates` 字段包含全部 161 个候选（按字段数降序排列），每个均标注 `note: "CANDIDATE only - not confirmed"`。`unclassified_analysis.all_entries` 字段包含全部 940 个待归类条目及其属性/概念判断。

---

## 5. 领域专项分析

### 5.1 交易对手

| 项 | 值 |
|----|-----|
| 概念数 | 18 |
| 覆盖表数 | 69 |

**正例**：
- `TRD_ATP_ORDER_MAPPING.KEY_CTPTY_ID` // 交易对手 — 主键引用，60 张表覆盖
- `TRD_ALLMARKET_ORDER_DEAL.CTPTY_SHT_NAME` // 交易对手简称 — 名称属性
- `TRD_B2B_CONTRACT_CONFIG.B2B_KEY_CTPTY_ID` // 背靠背交易对手 — 背靠背场景

**反例/歧义**：
- `REF_TRS.ACTUAL_CTPTY` 注释为"交易对手备注"，但字段名 ACTUAL_CTPTY 暗示"实际交易对手"——注释可能不够精确。
- `TRD_FICC_TRADING_BOND_ORI_DEAL.COUNTERPARTY` 注释为"交易对手短名"，但字段名为 COUNTERPARTY（通用交易对手），注释可能是对字段语义的窄化。

**证据边界**：18 个概念中 15 个挂接 reader:counterparty。交易对手主键 KEY_CTPTY_ID 在 58 张表中出现，是最稳定的标识字段。"交易对手佣金费率"（2 字段）不属于交易对手本体，而属于费率属性。

### 5.2 客户

| 项 | 值 |
|----|-----|
| 概念数 | 6 |
| 覆盖表数 | 3 |

**正例**：
- `OTC_DERIVATIVE_COUNTERPARTY.CLIENT_ID` // 客户编号
- `OTC_OPTION_PARAMETER.IS_2TRADER_CLIENT` // 是否二级交易商客户

**反例/歧义**：
- 客户概念仅出现在 `OTC_DERIVATIVE_COUNTERPARTY` 和 `REF_OTCPRODUCT` 两张表中，覆盖面极窄。客户编号 CLIENT_ID 在 OTC 衍生品交易对手表和产品参考表中出现，但这两张表的"客户"视角可能不同——前者是交易对手的客户属性，后者可能是产品销售关联的客户。

**证据边界**：6 个概念全部为单字段单表覆盖，无 reader 匹配（reader:counterparty 的 source_labels 中不包含"客户"）。客户作为独立业务节点的证据不足，当前更适合作为 reader:counterparty 的子属性。

### 5.3 产品/标的

| 项 | 值 |
|----|-----|
| 概念数 | 49 |
| 覆盖表数 | 85 |

**正例**：
- `REF_OTCPRODUCT.PRODUCT_CODE` // 产品代码 — 参考表主键
- `TRD_ALLMARKET_ORDER_DEAL.TRANSACTION_TYPE` // 交易品种 — 跨 24 表
- `REF_TRS_LEG.UNDERLYING_INS_ID` // 标的物主键（通过 UNDERLYING_INS_ID 42 表覆盖推断）

**反例/歧义**：
- `TRS_UNWIND_INSTRUCTION.CLOSE_STOCK_COMMISSION` 注释为 "CLOSE_STOCK_COMMISSION"（英文原样），被归入产品/标的域，但实际是清算佣金费用——注释缺失导致的误归类。
- `TRS_UNWIND_INSTRUCTION.KEY_INSTRUMENT_ID` 注释为 "KEY_INSTRUMENT_ID"，被作为独立概念 "KeyInstrument"——这是字段名本身而非业务注释。

**证据边界**：产品/标的覆盖面广但概念碎片化严重。49 个概念中大部分为单表单字段。最稳定的是 `UNDERLYING_INS_ID`（42 表）和 `TRANSACTION_TYPE`（24 表），但后者更接近交易属性而非产品标识。

### 5.4 询价/报价/订单/交易

| 项 | 值 |
|----|-----|
| 概念数 | 114 |
| 覆盖表数 | 126 |

**正例**：
- `REF_OTC_OPTION_DEAL_BAK.KEY_OTC_TRADE_ID` // OTC 交易主键 — 57 表覆盖
- `TRD_TRS_MERGED_TRADE_DEAL.KEY_TRS_MERGED_TRADE_DEAL_ID` // 合并交易主键
- `TRD_ALLMARKET_ORDER_SPLIT_DEAL.KEY_STOCK_ORDER_ID` // 一级订单主键

**反例/歧义**：
- `TRD_TRS_MANUAL_TRADE_DEAL.KEY_TRS_MANUAL_TRS_DEAL_ID` 注释为 "ID"，被归入 "KeyTrsManualTrsDeal"——这是字段名拼接而非业务注释，属于自动归类的噪声。
- `REF_MAIN_CONTRACT.TERMINATE_PRICE` 注释为"期末交易价"，但"交易价"实际是合约终止时的定价，不是交易达成时的价格——语义在合同终止而非交易达成。

**证据边界**：114 个概念中 16 个挂接 reader:trade-order。大量概念是具体表的交易主键（如 KEY_TRS_MANUAL_TRS_DEAL_ID），属于技术标识而非通用业务概念。交易全价/交易净价（各 12 表）是稳定的计量属性但未挂接骨架。

### 5.5 合同/合约腿/经济条款

| 项 | 值 |
|----|-----|
| 概念数 | 86 |
| 覆盖表数 | 130 |

**正例**：
- `REF_IRS_CASH_FLOW.KEY_LEG_ID` // IRS Leg ID — 物理桥连接 TRS 调查图
- `POS_FAST_TRS_LEG_CURRENT_POS.KEY_PLAN_ID` // 业务方案ID — 19 表覆盖
- `TRD_TRS_MERGED_TRADE_DEAL.KEY_OTC_TRADE_ID` // 互换合约编号

**反例/歧义**：
- `REF_OPTION_MARGIN_TRS_RELATION.TRS_KEY_OTC_TRADE_ID` 注释为"互换合约ID"，但这是期权与互换的关联表中的外键，并非合约本身的标识——关系表外键被误归类为合约标识。
- `TRD_OTC_CONTR_MAIN_SUB_MAPPING.MAIN_OTC_TRADE_ID` 注释为"主合约ID"，但这是主子合约映射表中的主键引用——需区分"合约标识"和"主子合约关系"。

**证据边界**：86 个概念覆盖 130 张表，是最大的领域。但概念高度碎片化：业务方案（KEY_PLAN_ID）有 3 个变体（业务方案ID、业务方案主键、业务方案编号），说明同一实体在不同表中有不同的注释表达。合约腿 KEY_LEG_ID 仅 3 表覆盖，但物理桥连接了 IRS/TRS 调查图。

### 5.6 持仓/头寸

| 项 | 值 |
|----|-----|
| 概念数 | 13 |
| 覆盖表数 | 15 |

**正例**：
- `POS_TRS_LEG_CURRENT_POS.KEY_LEG_POSITION_ID` // 持仓ID
- `POS_TRS_SOUTH_CLIENT.QUANTITY` // 持仓数量

**反例/歧义**：
- `TRS_FAST_MAPPING_DAY_TASK.POSITION_SYNC_TOTAL` 注释为"持仓待同步总数"——这是任务计数字段，不是持仓本体属性。
- `FX_EXPOSURE.KEY_FE_ID` 注释为"外汇敞口ID"——敞口与持仓在风控语境中有关联，但物理上是不同实体。

**证据边界**：13 个概念中 5 个挂接 reader:position。持仓覆盖面窄（15 表），集中在 POS_ 和 TRD_EXT_FAST_TRS_POS 表族。持仓数量在不同表中字段名不同（QUANTITY, POS_QUANTITY_SRC, POS_QUANTITY_TGT），说明存在源/目标侧的持仓镜像。

### 5.7 名义本金

| 项 | 值 |
|----|-----|
| 概念数 | 7 |
| 覆盖表数 | 22 |

**正例**：
- `REF_OTC_OPTION_DEAL_BAK.NOTIONAL` // 名义本金
- `REG_RECON_DETAIL_VALUATION.DYNAMIC_NOTIONAL_BASE` // 动态名义本金基准
- `REF_IRS.NOTIONAL_BASE` // 初始名义本金

**反例/歧义**：
- `OTC_OPTION_PARAMETER.NAME_OF_PRINCIPAL_CN` 注释为"名义本金大写"——这是名义本金的中文大写表示，属于展示属性而非计量属性。
- `REF_IRS.CURRENCY` 注释为"名义本金币种"——这是币种属性，不应独立于名义本金概念，但当前被归为独立概念。

**证据边界**：名义本金核心概念 55 字段覆盖 19 表，挂接 reader:notional。但 55 字段中有多个 null 注释（如 COLLATERAL_NOTIONAL, DYNAMIC_NOTIONAL_BASE），说明部分字段注释缺失，仅靠字段名推断语义。名义本金重置（NOTIONAL_RESET_AMOUNT）是合约存续期的关键事件属性。

### 5.8 估值/风险

| 项 | 值 |
|----|-----|
| 概念数 | 88 |
| 覆盖表数 | 74 |

**正例**：
- `TRD_B2B_DEAL.PRICE` // 价格 — 27 字段覆盖
- `REG_RECON_DETAIL_EVENT.PRICE` // 事件价格
- `OTC_OPTION_PARAMETER.DOWN_PROTECT_PRICE` // 下跌保护执行价格

**反例/歧义**：
- `TRS_UNWIND_INSTRUCTION.PRICE` 注释为 "PRICE"（英文原样），被归为独立概念 "Price"——注释缺失导致无法判断是全价还是净价。
- `OTC_OPTION_PARAMETER.PRICE_FREQ` 注释为"价格计算频率"——这是计算参数而非估值结果。

**证据边界**：88 个概念中仅 2 个挂接到 valuation-collateral-cashflow 区域。"价格"是最核心概念（27 字段 24 表），但存在 CleanPrice（净价）和 FullPrice（全价）两种语义变体未在骨架中区分。估值类概念严重碎片化，缺少"市值"和"估值结果"等稳定聚合节点。

### 5.9 保证金/抵押品

| 项 | 值 |
|----|-----|
| 概念数 | 29 |
| 覆盖表数 | 19 |

**正例**：
- `REF_OTC_CONTR_MARGIN_PARAM.INITIAL_MARGIN` // 保证金初始线(%)
- `REF_CONTR_DAILY_MARGIN_PARAM.MARGIN_CALL` // 保证金追保线
- `REF_CONTR_DAILY_MARGIN_PARAM.WITHDRAW` // 保证金提取线

**反例/歧义**：
- `TRD_OTC_CONTR_INITIAL_AMT.INITIAL_AMT_PRIORITY` 注释为"保证金扣除优先级"——这是扣除逻辑参数，非保证金金额。
- `TRD_OTC_CONTR_INITIAL_AMT.INITIAL_AMT_CURRENCY` 注释为"保证金扣除币种"——同样是扣除属性，独立于保证金本体。

**证据边界**：29 个概念中 14 个挂接 reader:margin。保证金参数集中在 REF_OTC_CONTR_MARGIN_PARAM、REF_CONTR_DAILY_MARGIN_PARAM 和 TRD_COLLATERAL_PARAM 三张配置表中，参数高度一致。"抵押品"（collateral）在骨架术语中出现，但语料中未发现独立的"抵押品"概念——抵押品逻辑通过保证金参数隐式表达，缺少独立的抵押品实体表。

### 5.10 现金流/交割/结算

| 项 | 值 |
|----|-----|
| 概念数 | 50 |
| 覆盖表数 | 50 |

**正例**：
- `REF_IRS_CASH_FLOW.CUM_EXTRACTED_CF` // 累计已提取现金流
- `REF_TRS.ACTUAL_SETTLE_RATE` // 实际结算汇率
- `TRD_OTC_CONTR_REPORT.ACTUAL_SETTLEMENT_DATE` // 实际结算日

**反例/歧义**：
- `CFG_EXCHANGE_RATE.CENTRAL_CLEARING_FEE_RATE` 注释为"中央结算收费"——这是费率而非结算金额，被归入现金流域但实际属于费用参数。
- `REF_FX_FORWARD_STRUCTURE.SETTLEMENT_METHOD` 注释为"交割方式"——这是结算方式分类而非现金流实体。

**证据边界**：50 个概念无 reader 匹配（骨架中未定义 reader:settlement 或 reader:cashflow）。现金流/结算概念分散在 REF_IRS_CASH_FLOW、REF_TRS、TRD_OTC_CONTR_REPORT 等不同产品线表中。缺少统一的"现金流"或"结算事件"聚合节点是骨架的主要缺口。

---

## 6. "待归类"分析：属性 vs. 真业务概念

在 1,375 个业务概念中，940 个（68.4%）落在 unexplained（333）、field_attribute（605）和 insufficient（2）类别中。以下分析这些"待归类"概念中哪些更可能是属性，哪些可能是真业务概念。

### 6.1 更可能是属性的概念

以下概念覆盖面小（≤2 字段、≤2 对象），无 qualifier_signature，语义上更接近字段级属性而非独立业务节点。在 940 个待归类概念中，775 个属于此类。以下为代表性示例：

| 概念标签 | 字段数 | 对象数 | 判断为属性的理由 |
|----------|--------|--------|-----------------|
| UnitCost | 2 | 2 | 单位成本，是计量属性 |
| 下单时间 | 2 | 2 | 时间属性，属于 reader:trade-order 的 TIME 轴 |
| 事件价格 | 2 | 2 | 价格属性，属于事件计量而非独立概念 |
| 事件前数量 | 2 | 2 | 计量属性，是持仓数量的时态变体 |
| 事件后数量 | 2 | 2 | 同上 |
| 交易对手佣金费率 | 2 | 2 | 费率属性，属于交易对手的修饰维度 |
| 交易录入时间 | 2 | 2 | 时间属性 |
| 债券全价 | 2 | 2 | 价格属性，属于估值计量的修饰变体 |
| 债券开仓净价 | 2 | 2 | 同上 |
| 兑付日假期 | 2 | 2 | 日期属性，是兑付日的修饰 |
| 公司行为类型 | 2 | 2 | 类型分类属性 |

**判断逻辑**：这些概念在物理上仅出现 1-2 次字段实例，语义是某个更核心概念的修饰或变体。例如"事件前数量"和"事件后数量"是"持仓数量"的 temporal_stage 修饰（BEFORE_ADJUSTMENT / AFTER_ADJUSTMENT），不应独立为业务节点。

### 6.2 可能是真业务概念

以下概念覆盖面较广（≥5 字段、≥5 对象），无 qualifier_signature，在物理字段中有一致的注释，可能是骨架未覆盖的真业务概念。在 940 个待归类概念中，48 个属于此类。以下为全部 48 个候选：

| 概念标签 | 字段数 | 对象数 | 可能是业务概念的理由 | 候选归属 |
|----------|--------|--------|---------------------|----------|
| 业务类型 | 36 | 35 | 跨产品线高频出现，是稳定分类维度 | products-underlyings 或 reference-configuration |
| 交易品种 | 24 | 24 | 跨全市场订单表一致出现 | inquiry-order-trade |
| 业务日期 | 23 | 23 | 跨多子系统作为时间锚点 | operations-reporting-data 或 TIME 轴 |
| 互换类型 | 17 | 17 | TRS 子系统核心分类 | contract-structure |
| 业务标志 | 14 | 14 | 交易方向标志，跨交易表一致 | inquiry-order-trade |
| 利差 | 14 | 14 | 合约腿经济条款核心参数 | contract-lifecycle |
| 交易金额 | 13 | 13 | 交易计量核心 | inquiry-order-trade |
| 委托数量 | 13 | 13 | 订单计量核心 | inquiry-order-trade |
| 交易全价 | 12 | 12 | 价格计量核心 | valuation-collateral-cashflow |
| 交易净价 | 12 | 12 | 价格计量核心 | valuation-collateral-cashflow |
| 固定利率 | 12 | 12 | 合约经济条款核心 | contract-lifecycle |
| 券息 | 11 | 11 | 借券/TRS 核心参数 | contract-lifecycle |
| 合约乘数 | 10 | 10 | 合约计量参数 | contract-structure |
| 成交日期 | 10 | 10 | 交易达成时间 | inquiry-order-trade |
| 平仓数量 | 6 | 6 | 合约终止计量 | lifecycle |
| 强平线 | 6 | 6 | 风控阈值参数 | position-risk |
| 兑付日 | 6 | 6 | 结算时间参数 | clearing-settlement |
| 兑付日延期 | 7 | 7 | 结算时间修饰 | clearing-settlement |
| 利率类型 | 8 | 8 | 合约参数分类 | contract-lifecycle |
| 对冲交易账号 | 6 | 6 | 对冲执行标识 | position-risk |

**重要声明**：以上"可能"仅为候选方向，不得自动发布为业务概念。需要业务骨架架构师结合业务语义判断是否纳入。

### 6.3 应归入审计/技术轴的概念

以下概念高频但明确属于审计字段，应归入 attribute_axis: AUDIT：

| 概念标签 | 字段数 | 对象数 | 归入理由 |
|----------|--------|--------|----------|
| 创建时间 | 207 | 204 | CREATED_DATETIME 的别名 |
| 修改时间 | 71 | 71 | UPDATED_DATETIME 的别名 |
| 创建人 | 185 | 185 | CREATED_BY 的别名 |
| 修改人 | 69 | 69 | UPDATED_BY 的别名 |
| 创建日 | 5 | 5 | CREATED_DATETIME 的窄化 |

这些概念合计 537 字段实例，占 unexplained 类别的主要部分。它们不应成为业务节点，但应纳入 AUDIT 属性轴作为稳定维度。

### 6.4 模糊地带

以下概念覆盖面中等（3-5 字段），难以明确判断是属性还是概念。在 940 个待归类概念中，117 个属于此类。以下为代表性示例：

| 概念标签 | 字段数 | 对象数 | 模糊原因 |
|----------|--------|--------|----------|
| 事件类型 | 5 | 5 | 跨事件表出现，但可能是事件分类属性而非独立实体 |
| 交易费率 | 5 | 5 | 跨表费率，但可能是交易佣金的修饰 |
| 佣金模式 | 5 | 5 | TRS 佣金分类，但仅在 TRS 子系统内稳定 |
| 参与率 | 5 | 5 | 期权/TRS 经济参数，可能是合约属性 |
| 印花税 | 4 | 4 | 跨交易表费用，但仅 4 表不足以确认 |
| 分红比例 | 4 | 4 | 公司行为参数，可能属于 lifecycle 事件属性 |
| 卖方名称 | 4 | 4 | 仅在对账表中出现，可能是 reader:counterparty 的角色变体 |
| 到期收益率 | 3 | 3 | 估值指标，但覆盖面不足以确认为独立节点 |

这些概念需要业务骨架架构师结合业务流程进一步判断。

---

## 7. 骨架覆盖缺口汇总

### 7.1 明确缺口

| 缺口 | 证据 | 建议方向（非决定） |
|------|------|-------------------|
| 现金流/结算缺少 reader 概念 | 50 个概念无 reader 匹配，分散在 50 张表 | 考虑增加 reader:settlement 或 reader:cashflow |
| 估值缺少稳定聚合节点 | 88 个概念严重碎片化，仅"价格"有 27 字段覆盖 | 考虑将"价格"明确为 reader 概念 |
| 抵押品缺少独立实体 | "抵押品"在骨架术语中出现但语料中无独立概念 | 抵押品逻辑隐式在保证金参数中，可能不需要独立节点 |
| 客户作为独立节点证据不足 | 仅 6 个概念覆盖 3 张表 | 客户可能更适合作为 reader:counterparty 的子属性 |
| 事件/生命周期缺少独立 reader | "事件类型"（5 表）、"事件日期"（6 表）无 reader 匹配 | 事件可能是 lifecycle 阶段下的子概念 |

### 7.2 歧义风险

| 歧义 | 涉及字段 | 风险说明 |
|------|----------|----------|
| 净价 vs. 全价 | CLEAN_PRICE（29 表）、FULL_PRICE（12 表） | 两者分属不同概念但语义高度相关，骨架未区分 |
| 交易方向 vs. 买卖方向 | TRADE_DIRECTION（14 表，注释"业务标志"） | 注释为"业务标志"而非"交易方向"，可能含多义 |
| 结算汇率 vs. 交割汇率 | SETTLE_RATE, STRIKE_FX_RATE | 外汇远期中"结算"与"交割"可能不等价 |
| 持仓数量 vs. 委托数量 | QUANTITY 同时出现在持仓表和订单表 | 同名字段在不同表中可能表达不同语义 |

### 7.3 产品上下文偏差

当前 4 个业务上下文仅识别了 IRS、OPTION、TRS 三种产品和 1 个 UNKNOWN。语料中大量字段涉及外汇远期（REF_FX_FORWARD）、借贷股票（TRD_LEND_STOCK）、全市场订单（TRD_ALLMARKET）等产品线，但这些产品未被识别为独立上下文。这导致跨产品比较时缺少产品维度锚定。

---

## 附录：数据来源与方法说明

### A.1 读取的全量文件

| 文件 | 行数 | 读取方式 |
|------|------|----------|
| business_concepts.jsonl | 1,375 | 全量 JSONL |
| attribute_expressions.jsonl | 1,559 | 全量 JSONL |
| diagnostics/data_semantic_candidates.jsonl | 1,559 | 全量 JSONL |
| diagnostics/semantic_review_queue.jsonl | 859 | 全量 JSONL |
| semantic_observations.jsonl | 5,347 | 全量 JSONL |
| semantic_hypotheses.jsonl | 2,243 | 全量 JSONL |
| semantic_relations.jsonl | 8,740 | 全量 JSONL |
| business_contexts.jsonl | 4 | 全量 JSONL |
| qualifiers.jsonl | 32 | 全量 JSONL |
| diagnostics/semantic_mapping_candidates.jsonl | 4,075 | 全量 JSONL |
| diagnostics/semantic_normalization_candidates.jsonl | 1,602 | 全量 JSONL |
| Stage 0 columns.json | 68,458 | 全量 JSON（筛选 TRADEFLOW 13,611 条） |
| Stage 0 objects.json | - | 全量 JSON（筛选 TRADEFLOW 477 表/视图） |

### A.2 证据分类原则

本报告严格区分以下三类证据：
1. **字段名**：数据库声明的列名（如 `KEY_CTPTY_ID`），属于物理事实。
2. **字段注释**：数据库声明的列注释（如"交易对手主键"），属于物理事实但可能不精确。
3. **表上下文**：字段所在表名和表类型，属于物理事实的结构上下文。

不因字段词频高就建议其成为顶层业务分类。高频字段需区分"高频因为审计需要"和"高频因为业务核心"。

### A.3 结构化数据

完整结构化统计和候选数据保存于同目录下的 `02-field-shapes.json`。该文件中的所有候选均标注为 CANDIDATE 状态，不构成已确认事实。
