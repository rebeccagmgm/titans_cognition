# 整合字段语义导航提案

> 状态：RESEARCH / PROPOSED — 整合提案，不构成业务验收、正式本体或 Canonical 结论。
>
> 日期：2026-08-14
>
> 角色：语义导航整合设计师
>
> 输入报告：
> - `01-domain-skeleton.md` — OTC 衍生品领域导航骨架研究（自顶向下）
> - `02-field-corpus-analysis.md` / `02-field-shapes.json` — TRADEFLOW 字段语料与覆盖分析（自底向上验证）
> - `03-disambiguation-audit.md` / `03-gold-set.yaml` — 字段语义消歧与反例审计
>
> 约束：不修改实现代码、当前配置和正式输出。不提交 Git。YAML 骨架标记为 candidate/provisional，不冒充已发布业务本体。不以多数意见代替判断；逐项处理三份报告的冲突。顶层结构由业务稳定性决定，字段语料只负责验证与发现缺口。生命周期和业务区域正交。属性表达、字段属性、限定条件不得混入业务树。一个概念允许多个业务入口。不追求全部字段立即挂接。

---

## 1. 最终建议的导航层级与完整文本树

### 1.1 设计原则

导航采用**四层正交投影**，而非一棵单继承分类树：

1. **生命周期主线**（顶部横向条带）——回答"当前处于哪个业务阶段"。
2. **业务区域地图**（主导航）——回答"正在看哪类业务对象或能力"。
3. **概念详情投影**（中栏）——展示概念、属性表达和正交筛选。
4. **证据与治理队列**（右栏 + 独立面板）——展示物理实现、证据状态和复核原因。

生命周期与业务区域正交：一个概念可从多个阶段和多个区域进入，不强迫唯一归属。

### 1.2 生命周期主线（六阶段）

```
交易准备 → 交易达成 → 合同存续 → 估值风控 → 清算结算 → 运营治理
```

六阶段由 ISDA CDM 原始操作、FpML 核心过程和行业前中后台划分支撑，整体稳定（详见 01 报告第 2 节）。运营治理横切前五阶段。

### 1.3 业务区域地图（十个区域，含命名调整）

```
otc-derivatives-navigation
├─ 01 参与主体 (participants)
│   ├─ 客户
│   ├─ 交易对手
│   ├─ 机构 / 部门
│   └─ 交易员 / 联系人
├─ 02 产品与标的 (products-underlyings)
│   ├─ 产品类型 (TRS / IRS / Option)
│   ├─ 标的资产 (股票 / 指数 / ETF / 债券)
│   ├─ 品种
│   └─ 市场对象
├─ 03 询价、订单与交易 (inquiry-order-trade)
│   ├─ 询价 (RFQ)
│   ├─ 报价
│   ├─ 订单 / 委托
│   ├─ 成交 / 执行
│   └─ 交易记录
├─ 04 合约与经济条款 (contract-structure)          ← 原"合同与结构"改名
│   ├─ 合约
│   ├─ 合约腿 (leg)
│   ├─ 经济条款 (名义本金 / 行权价 / 到期日 / 付息频率)
│   ├─ 方案 / 组合
│   └─ 组合结构
├─ 05 合同生命周期 (lifecycle)                      ← 与 04 静态 vs 动态分离
│   ├─ 生效
│   ├─ 重置 / fixing
│   ├─ 行权
│   ├─ 修订
│   ├─ 平仓 / 减仓
│   ├─ 增仓
│   ├─ 转让 / 更替 (novation)
│   ├─ 到期
│   └─ 终止 / 提前终止
├─ 06 持仓与风险 (position-risk)
│   ├─ 持仓 / 头寸 (current / history)
│   ├─ 敞口
│   ├─ 对冲关系
│   └─ 限额 / 准入额度
├─ 07 估值、履约保障与现金流 (valuation-collateral-cashflow)
│   ├─ 估值 / 盯市结果
│   ├─ 价格 (全价 / 净价)
│   ├─ 保证金 (初始 / 变动 / 追保线 / 提取线)
│   ├─ 抵押品
│   ├─ 现金流 (计算侧)
│   ├─ 费用
│   ├─ 权利金
│   └─ 名义本金 (跨区域引用)
├─ 08 清算与结算 (clearing-settlement)               ← 原"市场执行、清算与结算"瘦身
│   ├─ 清算记录
│   ├─ 结算记录
│   ├─ 交割记录
│   ├─ 支付 / Transfer
│   └─ 保证金收付
├─ 09 参考数据与配置 (reference-configuration)
│   ├─ 市场参考数据 (行情 / 收市价)
│   ├─ 产品参数模板
│   ├─ 系统配置 / 规则参数
│   └─ 映射定义 / 数据字典
└─ 10 运营、报表与数据加工 (operations-reporting-data)
    ├─ 批处理任务 / 作业
    ├─ 报表 (持仓 / 交易 / 估值 / 监管)
    ├─ 对账记录
    ├─ 报送记录
    ├─ ETL / 数据加工
    └─ 运行状态 / 日志
```

### 1.4 属性轴（正交于业务树，独立投影）

```
attribute_axes (reusable-field-attributes)
├─ IDENTIFIER     标识
├─ ROLE           角色
├─ STATE          状态
├─ DIRECTION      方向
├─ MEASURE       计量
├─ CURRENCY       币种
├─ TIME           时间
├─ CONFIGURATION  配置
├─ AUDIT          审计
└─ OPEN           开放（语料发现驱动，状态 OPEN_CANDIDATE）
```

### 1.5 限定维度（正交于业务树，修饰属性表达）

```
qualifier_dimensions
├─ temporal_stage       INITIAL / CURRENT / END / BEFORE_ADJ / AFTER_ADJ
├─ direction            LONG / SHORT / BUY / SELL / PAY / RECEIVE
├─ currency_basis       ORIGINAL / LOCAL / UNDERLYING / SETTLEMENT
├─ party_role           CLIENT / INTERNAL / COUNTERPARTY / SOURCE / TARGET
├─ lifecycle_stage     ORDER / EXECUTION / POSITION / CLEARING / TERMINATION
├─ measure_state        DYNAMIC / FIXED / AVAILABLE / FROZEN / ACCUMULATED / ESTIMATED
└─ flow_side            SOURCE / TARGET  (仅数据流方向，不覆盖业务映射角色)
```

### 1.6 Reader 概念（导航入口锚点，当前 5 + 候选扩展 3）

当前已验证的 5 个 reader 概念保持不变：`reader:notional`、`reader:counterparty`、`reader:trade-order`、`reader:position`、`reader:margin`。

基于语料缺口（02 报告第 7 节），**建议研究但不立即发布**的候选 reader：

| 候选 reader | 理由 | 语料依据 | 状态 |
|---|---|---|---|
| `reader:price` | "价格"27 字段/24 表，净价/全价未区分 | 88 个估值概念碎片化 | PROVISIONAL |
| `reader:settlement` | 50 个现金流/结算概念无 reader | 分散在 50 张表 | PROVISIONAL |
| `reader:lifecycle-event` | 事件类型/日期无独立锚点 | 生命周期事件表存在 | PROVISIONAL |

这些候选在第二批填充时评估，不自动发布。

---

## 2. 每个导航节点的定义、边界、正例和反例

以下为十个业务区域 + 六个生命周期阶段的节点详情卡片。每张卡片包含：定义、边界（包含/排除/相邻）、正例、反例。

### 2.1 业务区域节点详情

#### 参与主体 (participants)

- **定义**：OTC 衍生品交易中涉及的法律实体和自然人，及其标识、分类和关系。
- **包含**：客户主数据、交易对手主数据、机构/部门、交易员/联系人、客户准入状态、交易对手分类。
- **排除**：买方/卖方/甲方/乙方等交易方向角色（→ ROLE 属性轴）；交易对手敞口金额（→ 估值区域）。
- **正例**：`TRD_ATP_ORDER_MAPPING.KEY_CTPTY_ID` — 交易对手主键，58 张表覆盖，跨表引用核心实体。
- **反例**：`CTPTY_SHORT_NAME`（交易对手短名）不是"空头持仓方向"的交易对手变体——"SHORT"是"简称"(abbreviated name)的英文，不是"空头"(short position)。

#### 产品与标的 (products-underlyings)

- **定义**：OTC 衍生品的产品类型定义和标的资产信息。
- **包含**：产品类型（TRS/IRS/Option）、标的资产（股票/指数/ETF/债券）、品种、产品分类。
- **排除**：合约具体经济条款（→ 合约与经济条款）；标的行情数据（→ 参考数据与配置）。
- **正例**：`REF_TRS_LEG.UNDERLYING_INS_ID` — 标的物主键，42 张表覆盖。
- **反例**：`OTC_OPTION_PARAMETER.EXCHANGE_TYPE` 注释为"互换类型"，但字段名为 EXCHANGE_TYPE——可能是"交易所类型"而非"互换类型"，同名异义。

#### 询价、订单与交易 (inquiry-order-trade)

- **定义**：从询价到成交执行的交易前链路及其记录。
- **包含**：询价记录、报价记录、订单/委托、成交/执行记录、交易状态、交易方向、交易日期/时间。
- **排除**：合约经济条款（→ 合约与经济条款）；交易后的清算和结算（→ 清算与结算）。
- **正例**：`REF_OTC_OPTION_DEAL_BAK.KEY_OTC_TRADE_ID` — OTC 交易主键，57 张表覆盖。
- **反例**：`NET_TOTAL_VALUE_TRADE` 可能是聚合计算结果而非交易本身，不应仅凭名称包含"TRADE"归入此区域。当前配置已将其排除（`excluded_expression_labels`）。

#### 合约与经济条款 (contract-structure)

- **定义**：合约的静态定义和结构化经济条款。
- **包含**：合约、合约腿（leg）、经济条款（名义本金、行权价、到期日、付息频率）、方案/组合结构、合约属性。
- **排除**：交易订单本身（→ 询价/订单/交易）；合约动态生命周期事件（→ 合同生命周期）。
- **正例**：`POS_FAST_TRS_LEG_CURRENT_POS.KEY_PLAN_ID` — 业务方案ID，19 张表覆盖。
- **反例**：`REF_OPTION_MARGIN_TRS_RELATION.TRS_KEY_OTC_TRADE_ID` 注释为"互换合约ID"，但这是期权与互换关联表中的外键，并非合约本身标识——关系表外键被误归类为合约标识。

#### 合同生命周期 (lifecycle)

- **定义**：合约法律形成后到期满/终止前的全部生命周期事件和状态变迁。
- **包含**：生命周期事件（重置、行权、修订、平仓、终止、更替）、事件类型、事件状态、事件日期/金额、重置记录、行权记录。
- **排除**：日终估值和盯市（→ 估值区域）；实际资金转移（→ 清算与结算）。
- **正例**：`TRD_OPTION_EVENT` / `TRD_TRS_EVENT` — 存续期事件表，含事件编号、合约编号、事件类型、事件日期、事件状态。
- **反例**：`REF_TRS.ACTUAL_SETTLE_RATE` — "结算汇率"是 RATE 属性轴 + 生命周期上下文限定，不是生命周期事件本身。仅因字段名含"结算"不能判定为事件。

#### 持仓与风险 (position-risk)

- **定义**：合约存续期间的持仓状态和风险度量。
- **包含**：当前持仓、历史持仓、持仓数量/方向、头寸、敞口、对冲关系、限额、准入额度。
- **排除**：估值金额（→ 估值区域）；持仓的清算交割（→ 清算与结算）。
- **正例**：`POS_TRS_LEG_CURRENT_POS.KEY_LEG_POSITION_ID` — 持仓ID，当前持仓表。
- **反例**：`POS_TRS_LEG_CURRENT_POS` vs `POS_TRS_LEG_HIS_POS` 不是两个独立业务概念——当前持仓 vs 历史持仓是同一概念的 STATE 限定（current vs history）。持仓数量是 QUANTITY 属性轴，不是独立概念。

#### 估值、履约保障与现金流 (valuation-collateral-cashflow)

- **定义**：合约的估值/盯市方法、履约保障（保证金/抵押品）管理和现金流计算。
- **包含**：估值/盯市结果、合约 PV/损益、保证金（初始/变动/追保线/提取线/预警线）、抵押品、现金流（计算侧）、费用、权利金、价格。
- **排除**：重置/fixing 事件本身（→ 合同生命周期）；实际资金转移（→ 清算与结算）。
- **正例**：`REF_OTC_CONTR_MARGIN_PARAM.INITIAL_MARGIN` — 保证金初始线(%)，保证金参数表。
- **反例**：`TRD_OTC_CONTR_INITIAL_AMT.INITIAL_AMT_CURRENCY` — "保证金扣除币种"是扣除属性，独立于保证金本体，是 CURRENCY 属性轴。"金额""费用""利息"本身是 MEASURE 属性轴词，不是业务区域概念。

#### 清算与结算 (clearing-settlement)

- **定义**：由交易、生命周期事件或估值结果触发的实际清算、交割和资金转移。
- **包含**：清算记录、结算记录、交割记录、支付/Transfer 记录、保证金收付、结算状态。
- **排除**：交易执行本身（→ 询价/订单/交易）；对账和报表（→ 运营/报表/数据加工）。
- **正例**：Transfer/结算记录表（含结算编号、交易编号、结算方向、结算金额、结算日期）。
- **反例**：`REF_FX_FORWARD_STRUCTURE.SETTLEMENT_METHOD` — "交割方式"是结算方式分类而非现金流实体。`CFG_EXCHANGE_RATE.CENTRAL_CLEARING_FEE_RATE` — "中央结算收费"是费率而非结算金额。

#### 参考数据与配置 (reference-configuration)

- **定义**：支撑 OTC 衍生品业务的市场参考数据、产品参数模板和系统配置。
- **包含**：市场参考数据（行情/收市价）、产品参数模板、系统配置/规则参数、映射定义、数据字典。
- **排除**：币种/时间等通用限定维度（→ 属性轴/限定维度）；交易/合约/持仓等业务对象（→ 各自区域）。
- **正例**：标的行情参考表（含标的代码、行情日期、收市价、数据来源）。
- **反例**："币种"不是参考数据区域概念，是 CURRENCY 属性轴。"参数"本身是 CONFIGURATION 属性轴词。

#### 运营、报表与数据加工 (operations-reporting-data)

- **定义**：横切全生命周期的后运营、报表、报送、对账和数据治理活动。
- **包含**：批处理任务/作业、报表、对账记录、报送记录、ETL/数据加工任务、运行状态/日志。
- **排除**：具体业务事件语义（→ 对应业务区域）；审计字段 created_by/updated_time（→ AUDIT 属性轴）。
- **正例**：日终批处理报表表（含报表编号、报表类型、运行日期、运行状态、数据来源）。
- **反例**：`CREATED_DATETIME`（222 实例）— 纯审计字段，不是业务区域概念。`TRS_FAST_MAPPING_DAY_TASK.POSITION_SYNC_TOTAL` — "持仓待同步总数"是任务计数字段，不是持仓本体属性。

### 2.2 生命周期阶段节点详情（摘要，详见 01 报告第 2.2 节）

| 阶段 | 定义 | 核心对象 | 关键事件 | 相邻边界 |
|---|---|---|---|---|
| 交易准备 | 交易法律/合规可发生前的全部准备 | 客户、交易对手、产品、标的、限额 | 准入审批 | → 交易达成：可执行交易意向形成 |
| 交易达成 | 询价到执行、簿记、确认 | 询价、报价、订单、交易、合约 | 询价、报价、成交、确认、合约形成 | → 合同存续：合约形成 |
| 合同存续 | 合约形成后到期满/终止前 | 合约、合约腿、名义本金、持仓 | 重置、行权、修订、平仓、终止、更替 | → 估值风控：重置产生估值输入 |
| 估值风控 | 持续计量、风险度量、履约保障 | 估值、保证金、抵押品、价格 | 盯市（日终）、追保 | → 清算结算：估值产生待结算金额 |
| 清算结算 | 实际资金和证券交割 | 清算记录、结算记录、Transfer | 清算、交割、结算、支付 | → 运营治理：对账和报表 |
| 运营治理 | 横切全生命周期的后运营 | 报表、对账、报送、ETL | 批处理、对账、报送 | 横切前五阶段 |

---

## 3. 生命周期入口与业务区域的多入口矩阵

生命周期主线（行）与业务区域（列）的交叉表示一个业务区域在哪些阶段有活跃入口。✓ = 核心入口，◇ = 跨阶段引用，空白 = 无活跃入口。

| 业务区域 \ 生命周期 | 交易准备 | 交易达成 | 合同存续 | 估值风控 | 清算结算 | 运营治理 |
|---|---|---|---|---|---|---|
| 参与主体 | ✓ 准入/限额 | ◇ 引用 | ◇ 引用 | ◇ 对手方敞口 | | ◇ 报表 |
| 产品与标的 | ✓ 产品准入 | ✓ 选择 | ✓ 条款 | ◇ 定价 | | ◇ 报表 |
| 询价/订单/交易 | | ✓ 核心 | ◇ 被事件修改 | | ◇ 产生结算义务 | ◇ 报表 |
| 合约与经济条款 | | ✓ 合约形成 | ✓ 条款引用 | ◇ 估值基准 | ◇ 现金流计算 | ◇ 报表 |
| 合同生命周期 | | ◇ 合约形成 | ✓ 核心 | ◇ 重置→估值 | ◇ 事件→结算 | ◇ 报表 |
| 持仓与风险 | | | ✓ 持仓身份 | ✓ 风险度量 | ◇ 交割量 | ◇ 报表 |
| 估值/履约/现金流 | ◇ 限额参数 | | ◇ 名义本金 | ✓ 核心 | ◇ 保证金收付 | ◇ 报表 |
| 清算与结算 | | | ◇ 事件触发 | ◇ 估值触发 | ✓ 核心 | ◇ 对账 |
| 参考数据与配置 | ✓ 参数设置 | | | ◇ 估值输入 | | ✓ 维护 |
| 运营/报表/数据加工 | | | | | | ✓ 核心 |

**多入口概念示例**：

| 概念 | 入口 1 | 入口 2 | 入口 3 | 说明 |
|---|---|---|---|---|
| 名义本金 | 合同存续 (CORE_OBJECT) | 估值风控 (CROSS_STAGE) | 合约与经济条款 (静态定义) | 基准金额跨阶段 |
| 持仓 | 合同存续 (CORE_OBJECT) | 估值风控 (CROSS_STAGE) | — | 状态快照 vs 风险度量 |
| 保证金 | 估值风控 (CORE_OBJECT) | 清算与结算 (收付侧) | 参考数据 (参数侧) | 计算侧 vs 执行侧 vs 配置侧 |
| 交易对手 | 交易准备 (CORE_OBJECT) | 交易达成 (引用) | 估值风控 (敞口) | 主体跨阶段 |
| 合约 | 交易达成 (形成) | 合同存续 (生命周期) | 估值风控 (盯市) | 合约形成是交易达成终点 |

---

## 4. 字段属性与限定维度注册表

### 4.1 属性轴注册表

| 属性轴 | 定义 | CDM 对照 | 典型修饰 | 语料验证（02 报告） |
|---|---|---|---|---|
| IDENTIFIER | 标识：用于引用和区分业务对象 | TradeIdentifier, Identifier | 交易编号、合约编号、持仓编号、事件编号 | KEY_CTPTY_ID(58表), KEY_OTC_TRADE_ID(57表), KEY_PLAN_ID(39表) 验证 |
| ROLE | 角色：字段在交易/合约中承担的参与方角色 | PartyRole | 买方、卖方、甲方、乙方、源侧、目标侧 | party_role 限定词仅含 CLIENT/INTERNAL，缺少 SELLER/BUYER（见 4.3 缺口） |
| STATE | 状态：业务对象或交易的状态 | State, ClosedStateEnum | 当前、历史、已终止、已到期、已行权 | lifecycle_stage 限定词验证（POSITION/EXECUTION等） |
| DIRECTION | 方向：交易方向或持仓方向 | 隐含在 quantity direction | 多头、空头、买入、卖出、支付、收取 | position_side(LONG/SHORT), trade_side(BUY/SELL) 验证 |
| MEASURE | 计量：金额、数量、比率等度量值 | Price, Quantity, PriceQuantity | 金额、数量、比率、价格、余额、市值 | 605 个概念被判定为 field_attribute，验证此轴需求 |
| CURRENCY | 币种：度量值的计价货币 | Currency | 原币、本币、标的币种、结算币种 | currency_basis 限定词验证（4 值） |
| TIME | 时间：业务时点 | date, dateTime, TimeZone | 交易日期、成交时间、到期日、重置日 | temporal_stage 限定词验证（5 值） |
| CONFIGURATION | 配置：分类、模式、参数、规则 | 隐含在 product/contract attributes | 类型、类别、模式、参数、规则 | "业务类型"(36表)、"互换类型"(17表) 候选 |
| AUDIT | 审计：数据创建/更新/来源追踪 | EventTimestamp, WorkflowStepApproval | 创建人、创建时间、更新人、更新时间、数据来源 | CREATED_DATETIME(222), UPDATED_DATETIME(213) 验证 |
| OPEN | 开放：语料发现的新属性形态 | 不对应，CDM 不预设封闭枚举 | 由语料发现驱动 | 状态 OPEN_CANDIDATE |

### 4.2 限定维度注册表

| 限定维度轴 | 当前值 | 示例 | 语料验证 | 备注 |
|---|---|---|---|---|
| temporal_stage | INITIAL/CURRENT/END/BEFORE_ADJ/AFTER_ADJ | 初始名义本金、当前名义本金 | ✓ 5 值全部验证 | 稳定 |
| direction (position_side) | LONG/SHORT | 多头/空头动态名义本金 | ✓ 但有 SHORT/LONG token 歧义（见 4.3） | 需消歧规则 |
| direction (trade_side) | BUY/SELL | 买入/卖出成交 | ✓ | 稳定 |
| direction (cashflow) | PAY/RECEIVE | 保证金支付/收取 | ✓ | 稳定 |
| currency_basis | ORIGINAL/LOCAL/UNDERLYING/SETTLEMENT | 原币/本币/标的币种/结算币种金额 | ✓ 4 值全部验证 | 稳定 |
| party_role | CLIENT/INTERNAL/COUNTERPARTY/SOURCE/TARGET | 客户/内部/交易对手 | ⚠ 仅 CLIENT/INTERNAL 验证，缺少 SELLER/BUYER | 缺口 |
| lifecycle_stage | ORDER/EXECUTION/POSITION/CLEARING/TERMINATION | 委托/成交/持仓/清算/终止阶段 | ✓ 5 值验证 | 稳定 |
| measure_state | DYNAMIC/FIXED/AVAILABLE/FROZEN/ACCUMULATED/ESTIMATED | 动态/冻结/累计金额 | ✓ 6 值验证 | 稳定 |
| flow_side | SOURCE/TARGET | 源侧/目标侧数据流 | ⚠ 与 party_role 混淆（见 4.3） | 需分离规则 |
| variability | DYNAMIC/FIXED | 动态/固定名义本金 | ✓ | 与 measure_state 部分重叠 |
| aggregation_state | ACCUMULATED | 累计已提取现金流 | ✓ | 稳定 |
| availability_state | AVAILABLE/FROZEN | 可用/冻结保证金 | ✓ | 稳定 |
| estimation_status | ESTIMATED | 估算金额 | ✓ | 稳定 |
| attribute_kind | IDENTIFIER | 标识属性 | ✓ | 稳定 |

### 4.3 属性轴与限定维度的已知缺陷（来自 03 审计报告）

| 缺陷 ID | 严重度 | 描述 | 影响范围 | 最小修复原则（不实现） |
|---|---|---|---|---|
| DEFECT-SHORT-LONG | CRITICAL | 英文 token SHORT/LONG 在列名中歧义爆炸：短名→空头、长名→多头 | 18 字段误判 position_side:SHORT，1 字段误判 LONG | direction facet 的英文 pattern 仅在中文注释含"空头"/"多头"时匹配 |
| DEFECT-SOURCE-TARGET | MODERATE | SOURCE/TARGET 双语义混淆：数据流方向 vs 业务映射角色 | 15 个属性表达被附加 flow_side 限定 | party_role 的 SOURCE/TARGET 与 flow_side 分离为独立维度 |
| DEFECT-GENERIC-WORD | MODERATE | 泛化词（状态/类型/金额/币种/日期/简称/缩写）被提升为 DOMAIN 业务概念 | 7 个概念层次混淆 | field_families/broad_categories 词在投影中标记为 ATTRIBUTE scope |
| DEFECT-NAME-COMMENT-CONFLICT | LOW | 列名 token 与中文注释方向冲突时优先级错误 | 1 字段（SHORT_DYNAMIC_NOTIONAL_ORG） | 列名与注释冲突时注释优先；标记 CONFLICT 而非自动消解 |
| DEFECT-ORDER-TRADE-MERGE | LOW | 订单与交易在导航层合并 | reader:trade-order source_labels | 导航层合并可接受，概念层应保持分离 |

这些缺陷是 03 审计报告的产出，本提案**记录但不修复**（约束：不修改实现代码和当前配置）。它们将作为后续修订批次的输入。

---

## 5. 概念、属性表达、物理字段之间的关系模型

### 5.1 四层关系模型

```
┌─────────────────────────────────────────────────────────┐
│ Layer 1: 业务导航入口 (Navigation Entry)                │
│  生命周期阶段 × 业务区域 = 多入口矩阵                     │
│  e.g. [合同存续, 合约与经济条款] → 名义本金              │
├─────────────────────────────────────────────────────────┤
│ Layer 2: 业务概念 (Business Concept)                     │
│  稳定的业务实体或度量，有唯一身份                         │
│  e.g. 名义本金 (business-concept-xxx)                    │
│  └─ 属性表达 (Attribute Expression)                      │
│      概念在物理字段中的具体观察形式                       │
│      e.g. "初始名义本金" = 名义本金 + temporal_stage:INITIAL │
│      e.g. "多头动态名义本金(标的币种)" = 名义本金         │
│           + position_side:LONG + measure_state:DYNAMIC   │
│           + currency_basis:UNDERLYING                    │
├─────────────────────────────────────────────────────────┤
│ Layer 3: 字段属性轴 + 限定维度 (Attribute Axes + Qualifiers)│
│  正交于业务树的可复用修饰轴                               │
│  IDENTIFIER / ROLE / STATE / DIRECTION / MEASURE /        │
│  CURRENCY / TIME / CONFIGURATION / AUDIT / OPEN           │
│  + temporal_stage / direction / currency_basis / ...      │
├─────────────────────────────────────────────────────────┤
│ Layer 4: 物理实现 (Physical Implementation)              │
│  Schema / Table / Column + 证据                           │
│  e.g. TRADEFLOW / REF_FAST_TRS / NOTIONAL_BASE           │
│  证据: column_name=NOTIONAL_BASE, column_comment=初始名义本金│
└─────────────────────────────────────────────────────────┘
```

### 5.2 关系规则

1. **概念 → 属性表达**：一对多。一个概念可有多个属性表达（如名义本金→初始/动态/多头动态/空头动态）。
2. **属性表达 → 物理字段**：一对多。一个属性表达可由多个物理字段实例支撑（如"交易对手"→60 张表的 KEY_CTPTY_ID + CTPTY_SHORT_NAME + ...）。
3. **概念 → 导航入口**：多对多。一个概念可从多个生命周期阶段 × 业务区域进入（多入口）。
4. **属性轴 → 概念**：多对多。一个属性轴可跨概念复用（如 IDENTIFIER 轴修饰交易/合约/持仓/事件编号）。
5. **限定维度 → 属性表达**：一对多。一个限定维度轴的值修饰属性表达（如 temporal_stage:INITIAL 修饰"初始名义本金"）。

### 5.3 分层禁止规则

- **禁止**：将属性表达提升为独立业务概念（如"动态名义本金"不是独立概念，是名义本金 + measure_state:DYNAMIC）。
- **禁止**：将字段属性轴词提升为业务概念（如"金额""状态""币种"不是业务对象）。
- **禁止**：将限定维度值提升为业务概念（如"初始""多头"不是独立概念）。
- **禁止**：将物理列名 token 直接作为业务语义（如列名 SHORT 不等于"空头"，需注释佐证）。
- **禁止**：将关系表外键误归类为被引用实体的标识（如 REF_OPTION_MARGIN_TRS_RELATION.TRS_KEY_OTC_TRADE_ID 是关系外键，不是合约标识）。

### 5.4 以名义本金为例的完整投影

```
名义本金 (Business Concept)
│  导航入口: [合同存续, 合约与经济条款] CORE_OBJECT
│            [估值风控, 估值/履约/现金流] CROSS_STAGE
│
├─ 初始名义本金 (Attribute Expression)
│  限定: temporal_stage=INITIAL
│  物理字段: REF_IRS.NOTIONAL_BASE // 初始名义本金
│
├─ 动态名义本金 (Attribute Expression)
│  限定: measure_state=DYNAMIC
│  物理字段: REG_RECON_DETAIL_VALUATION.DYNAMIC_NOTIONAL_BASE
│
├─ 多头动态名义本金(标的币种) (Attribute Expression)
│  限定: position_side=LONG + measure_state=DYNAMIC + currency_basis=UNDERLYING
│  物理字段: REF_FAST_TRS.LONG_DYNAMIC_NOTIONAL // 多头动态名义本金(标的币种)
│
├─ 空头动态名义本金(结算币种) (Attribute Expression)
│  限定: position_side=SHORT + measure_state=DYNAMIC + currency_basis=SETTLEMENT
│  物理字段: REF_FAST_TRS.SHORT_DYNAMIC_NOTIONAL // 空头动态名义本金(结算币种)
│
├─ 字段属性轴:
│  IDENTIFIER (合约编号引用) | MEASURE (金额) | CURRENCY (币种) | TIME (时点)
│
└─ 物理实现:
   TRADEFLOW / REF_FAST_TRS / 19 张表 / 55 个字段实例
   证据状态: CANDIDATE (部分字段注释缺失)
```

---

## 6. 当前 1375 个概念候选的覆盖分布

### 6.1 骨架支持分类总览（来自 02 报告第 2 节）

| 骨架支持类别 | 概念数 | 占比 | 说明 |
|---|---|---|---|
| 明确可挂接 (direct_attach) | 57 | 4.1% | 标签直接匹配 reader 概念或业务区域/阶段术语 |
| 多入口候选 (multi_entry) | 0 | 0% | 本轮匹配逻辑未发现同一概念匹配多个 reader |
| 属性表达 (attribute_expr) | 377 | 27.4% | 携带 qualifier_signature，属于修饰维度 |
| 字段属性 (field_attribute) | 605 | 44.0% | 覆盖面小（≤1 字段、≤1 对象），更像字段级属性 |
| 限定条件 (qualifier_cond) | 0 | 0% | 无直接匹配 |
| 技术/审计字段 (tech_audit) | 1 | 0.1% | 匹配审计模式 |
| 证据不足 (insufficient) | 2 | 0.1% | 无字段实例且无属性表达 |
| 真正无法解释 (unexplained) | 333 | 24.2% | 不匹配任何骨架术语 |
| **合计** | **1,375** | **100%** | |

### 6.2 覆盖分布的关键判断

**重要约束**：范围外 ≠ 未知。以下分布说明覆盖范围，不得把"unexplained"等同于"业务概念不存在"或"方法失败"。

1. **direct_attach (57)**：可直接挂接到 reader 概念或业务区域。这是第一批填充的核心。
2. **attribute_expr (377)**：这些不是独立业务概念，而是已有概念的限定变体。应归入对应概念下的属性表达层，不新增导航节点。
3. **field_attribute (605)**：覆盖面小（≤1 字段、≤1 对象），更像字段级属性。其中 775 个（跨 unexplained + field_attribute）更可能是属性而非概念。这些不应成为导航节点。
4. **unexplained (333)**：不匹配任何骨架术语。其中：
   - 48 个（≥5 字段、≥5 对象）可能是真业务概念候选（见 02 报告第 6.2 节）。
   - 117 个（3-5 字段）处于模糊地带。
   - 其余更可能是属性或噪声。
5. **multi_entry (0)**：本轮匹配逻辑的限制——它检测"同一概念匹配多个 reader 概念"，而非"同一概念在多个阶段出现"。实际多入口（如名义本金、持仓）由配置种子的 lifecycle_entries 显式定义。

### 6.3 按业务区域的覆盖分布（来自 02 报告第 5 节）

| 业务区域 | 概念数 | 覆盖表数 | 关键发现 |
|---|---|---|---|
| 参与主体 | 24 (18 交易对手 + 6 客户) | 69 + 3 | KEY_CTPTY_ID(58表)最稳定；客户独立节点证据不足 |
| 产品与标的 | 49 | 85 | 碎片化严重；UNDERLYING_INS_ID(42表)和 TRANSACTION_TYPE(24表)最稳定 |
| 询价/订单/交易 | 114 | 126 | 16 个挂接 reader:trade-order；大量是具体表的主键 |
| 合约与经济条款 | 86 | 130 | 最大领域；KEY_PLAN_ID 有 3 个变体注释 |
| 持仓与风险 | 13 | 15 | 5 个挂接 reader:position；覆盖面窄 |
| 名义本金 | 7 | 22 | 挂接 reader:notional；55 字段有部分 null 注释 |
| 估值/风险 | 88 | 74 | 仅 2 个挂接；"价格"(27字段)最核心但净价/全价未区分 |
| 保证金/抵押品 | 29 | 19 | 14 个挂接 reader:margin；抵押品无独立概念 |
| 现金流/交割/结算 | 50 | 50 | 无 reader 匹配；缺少统一聚合节点 |

### 6.4 48 个可能是真业务概念的候选（摘要）

以下概念覆盖面广（≥5 字段、≥5 对象）、注释一致、无 qualifier_signature，可能是骨架未覆盖的真业务概念。**这些是候选，不自动发布**。

| 概念标签 | 字段数 | 对象数 | 候选归属 |
|---|---|---|---|
| 业务类型 | 36 | 35 | products-underlyings 或 reference-configuration |
| 交易品种 | 24 | 24 | inquiry-order-trade |
| 业务日期 | 23 | 23 | operations-reporting-data 或 TIME 轴 |
| 互换类型 | 17 | 17 | contract-structure |
| 业务标志 | 14 | 14 | inquiry-order-trade |
| 利差 | 14 | 14 | contract-structure（合约腿经济条款） |
| 交易金额 | 13 | 13 | inquiry-order-trade（MEASURE 属性） |
| 委托数量 | 13 | 13 | inquiry-order-trade（MEASURE 属性） |
| 交易全价 | 12 | 12 | valuation-collateral-cashflow |
| 交易净价 | 12 | 12 | valuation-collateral-cashflow |
| 固定利率 | 12 | 12 | contract-structure（经济条款） |
| 券息 | 11 | 11 | contract-structure（经济条款） |
| 合约乘数 | 10 | 10 | contract-structure |
| 成交日期 | 10 | 10 | inquiry-order-trade（TIME 属性） |
| 平仓数量 | 6 | 6 | lifecycle（终止计量） |
| 强平线 | 6 | 6 | position-risk（风控阈值） |
| 兑付日 | 6 | 6 | clearing-settlement（时间参数） |
| 兑付日延期 | 7 | 7 | clearing-settlement（时间修饰） |
| 利率类型 | 8 | 8 | contract-structure（参数分类） |
| 对冲交易账号 | 6 | 6 | position-risk（对冲标识） |

（完整 48 个候选见 02 报告第 6.2 节）

---

## 7. 第一批、第二批、后续批次的填充顺序

### 7.1 填充原则

1. **先验证后扩展**：先用已有 reader 概念和业务区域验证骨架，再扩展新节点。
2. **先高覆盖后低覆盖**：优先处理字段覆盖广、表分布宽的稳定概念。
3. **先核心后边缘**：先填充业务主线概念，再处理跨区域和模糊地带。
4. **不追求全部挂接**：范围外概念保留为 OPEN_CANDIDATE 或 UNKNOWN，不强行归类。

### 7.2 第一批：核心概念验证（57 个 direct_attach + reader 种子）

**目标**：验证 5 个 reader 概念和骨架结构是否能正确承载已有概念。

| 批次项 | 内容 | 概念数 | 依据 |
|---|---|---|---|
| reader:notional | 名义本金及其 7 个属性表达变体 | 7 | 55 字段/19 表，挂接 reader:notional |
| reader:counterparty | 交易对手及 18 个子概念 | 18 | KEY_CTPTY_ID 58 表覆盖 |
| reader:trade-order | 交易/订单及 16 个子概念 | 16 | KEY_OTC_TRADE_ID 57 表覆盖 |
| reader:position | 持仓及 5 个子概念 | 5 | POS_ 表族 |
| reader:margin | 保证金及 14 个子概念 | 14 | REF_OTC_CONTR_MARGIN_PARAM 等 |
| 业务区域直接匹配 | 交易员、交易所、支付、结算、Price | 5 | 02 报告第 2.1 节 |
| 小计 | | ~57+ | direct_attach 类别 |

**验收标准**：每个概念能从正确的生命周期入口和业务区域进入；属性表达正确归类到概念下；物理字段证据可追溯。

### 7.3 第二批：属性表达归拢 + 候选 reader 评估

**目标**：将 377 个 attribute_expr 归入对应概念；评估 3 个候选 reader。

| 批次项 | 内容 | 数量 | 依据 |
|---|---|---|---|
| 属性表达归拢 | 377 个带 qualifier_signature 的表达归入对应概念 | 377 | 02 报告 attribute_expr 类别 |
| 候选 reader:price 评估 | "价格"(27字段)、"交易全价"(12表)、"交易净价"(12表) | ~3 | 02 报告第 7.1 节缺口 |
| 候选 reader:settlement 评估 | 50 个现金流/结算概念 | ~50 | 无 reader 匹配 |
| 候选 reader:lifecycle-event 评估 | 事件类型/事件日期 | ~2 | 生命周期事件表 |
| 48 个真概念候选评估 | 业务类型、交易品种、利差等 | 48 | 02 报告第 6.2 节 |

**验收标准**：候选 reader 经过正例/反例/歧义例验证后才发布；48 个候选逐一裁定 ACCEPT/DEFER/REJECT。

### 7.4 第三批：字段属性归拢 + 模糊地带裁定

**目标**：将 605 个 field_attribute 归入 AUDIT/MEASURE/TIME 等属性轴；裁定 117 个模糊地带概念。

| 批次项 | 内容 | 数量 | 依据 |
|---|---|---|---|
| 审计字段归拢 | CREATED_DATETIME(222)等 → AUDIT 轴 | ~537 | 02 报告第 6.3 节 |
| 字段属性归拢 | 605 个 field_attribute 归入属性轴 | 605 | 02 报告 field_attribute 类别 |
| 模糊地带裁定 | 事件类型、交易费率、佣金模式等 | 117 | 02 报告第 6.4 节 |

### 7.5 后续批次：剩余 unexplained + 跨 Schema 验证

**目标**：处理剩余 333 个 unexplained 中的低覆盖概念；在第二 Schema 上验证骨架复用性。

| 批次项 | 内容 | 数量 | 依据 |
|---|---|---|---|
| 低覆盖 unexplained | ≤2 字段的待归类概念 | ~168 | 333 - 48 - 117 |
| 跨 Schema 验证 | 在 OTCCLEARING 或 TRADING 上验证骨架 | — | 01 报告第 9.5 节，D-010 待决 |
| 03 审计缺陷修复 | SHORT/LONG 消歧等 4 项最小修复 | — | 03 报告最小修复原则 |

---

## 8. 明确列出不会自动挂接的内容

以下内容在本提案中**不会自动挂接到导航树**，保留为候选、Unknown 或 OPEN_CANDIDATE：

### 8.1 概念层不会自动挂接

1. **48 个"可能真业务概念"候选**（02 报告第 6.2 节）——需业务骨架架构师逐一裁定。
2. **117 个模糊地带概念**（02 报告第 6.4 节）——3-5 字段覆盖，不足以确认。
3. **333 个 unexplained 概念中除 48 个候选外的剩余**——更可能是属性或噪声。
4. **7 个泛化词概念**（状态/类型/金额/币种/日期/简称/缩写）——03 审计判定为层次混淆，应降级为 ATTRIBUTE scope，不进入业务树。
5. **7 个简称/缩写类概念**（简称/缩写/名称缩写/短名/交易对手短名/交易对手简称/交易对手长名）——03 审计判定为交易对手的属性表达，不是独立实体。
6. **"客户"作为独立业务节点**——02 报告第 5.2 节：仅 6 概念/3 表，证据不足，当前作为 reader:counterparty 的子属性。
7. **"抵押品"作为独立实体**——02 报告第 5.9 节：语料中无独立"抵押品"概念，逻辑通过保证金参数隐式表达。

### 8.2 属性/限定层不会自动挂接

8. **新属性轴**——语料发现的 OPEN 候选不自动成为正式属性轴，需验证。
9. **新限定维度值**——flow_side 的 SOURCE/TARGET 在消歧修复前不自动用于业务映射角色。
10. **SHORT/LONG 英文 token 作为方向限定**——03 审计：在中文注释不含"空头"/"多头"时不提取。

### 8.3 关系/证据层不会自动挂接

11. **Wiki 目录结构**——不能单独形成业务层级或字段属性（设计决策第 4 项）。
12. **关系表外键**——不能误归类为被引用实体的标识（如 TRS_KEY_OTC_TRADE_ID 不是合约标识）。
13. **字段名拼接概念**——如 "KeyTrsManualTrsDeal" 是字段名拼接而非业务注释，属于自动归类噪声。
14. **英文原样注释**——如 "PRICE"、"CLOSE_STOCK_COMMISSION" 注释缺失，不自动判断业务语义。

### 8.4 跨 Schema 不会自动推广

15. **TRADEFLOW 验证的深规则**——不自动推广到其他 Panorama Schema（AGENTS.md 硬边界）。
16. **第二 Schema 骨架调整**——依赖 D-010 待决事项，不在本提案决定。

---

## 9. 对前三份报告每项重大分歧的 ACCEPT/REJECT/DEFER 裁定

### 9.1 01 领域骨架报告的差异建议（第 7 节）

| ID | 差异 | 裁定 | 理由 |
|---|---|---|---|
| L1 | "合约"从 trade-agreement cross_stage 移至 core_object | **ACCEPT** | CDM ContractFormation 是交易达成终点事件，合约在此阶段形成。保留多入口引用。 |
| L2 | contract-lifecycle business_event 增加"行权" | **ACCEPT** | CDM Exercise 是 9 个原始操作之一，当前配置遗漏。语料有 TRD_OPTION_EVENT 支撑。 |
| L3 | contract-lifecycle business_event 增加"更替"(novation) | **ACCEPT** | CDM PartyChange 对应 Novation，是重要生命周期事件。 |
| L4 | valuation-risk cross_stage "结算"改为"现金流" | **ACCEPT** | "结算"是清算结算阶段的 business_event，不应作为估值风控的跨环节概念。估值的产出是"现金流计算"。 |
| L5 | clearing-settlement business_event 增加"支付" | **ACCEPT** | CDM Transfer 原始操作对应支付/资金转移。 |
| A1 | valuation-collateral-cashflow 移除"金额""费用""利息" | **ACCEPT** | 这些是 MEASURE 属性轴词，不是业务区域概念。02 报告第 6.3 节验证。 |
| A2 | reference-configuration 移除"币种" | **ACCEPT** | 币种是 CURRENCY 属性轴。 |
| A3 | operations-reporting-data 移除"created""updated" | **ACCEPT** | 这些是 AUDIT 属性轴词。02 报告验证 CREATED_DATETIME(222实例)。 |
| A4 | position-risk 移除"限额" | **DEFER** | "限额"在业务上确实是风控概念，但 02 报告显示"强平线"(6表)等参数存在。"限额"更适合作为 CONFIGURATION 属性轴或 risk 的属性表达。需第二批验证后决定。 |
| A5 | contract-structure 增加"经济条款" | **ACCEPT** | 当前词表遗漏核心概念。02 报告第 5.5 节验证（利差/固定利率/券息等经济条款概念存在）。 |
| N1 | "合同与结构"改名为"合约与经济条款" | **ACCEPT** | 明确区分静态定义（合约条款）与动态事件（生命周期）。 |
| N2 | "市场执行、清算与结算"移除"市场执行" | **ACCEPT** | 执行是交易达成终点，属于"询价/订单/交易"。CDM Execution 属于 trade instantiation。 |
| N3 | execution-clearing-settlement ID 改为 clearing-settlement | **ACCEPT** | 与 N2 一致。 |
| B1 | 增加 lifecycle_vs_valuation 边界规则 | **ACCEPT** | 重置(reset)是事件触发，估值(valuation)是计量结果。CDM 将 Reset 和 Transfer 分开。 |
| B2 | 增加 cashflow_boundary 边界规则 | **ACCEPT** | 现金流计算(valuation)与现金流执行(settlement)需区分。 |
| B3 | 增加 event_vs_measure 边界规则 | **ACCEPT** | 仅因字段名含"重置""结算""平仓"不能判定为事件。03 审计验证此风险。 |

### 9.2 02 字段语料报告的缺口建议（第 7 节）

| ID | 缺口/建议 | 裁定 | 理由 |
|---|---|---|---|
| GAP-1 | 增加 reader:settlement 或 reader:cashflow | **DEFER** | 50 个概念无 reader 匹配是真实缺口，但当前概念碎片化严重（分散在 50 张不同产品线表）。第二批先评估聚合可能性，不立即发布 reader。 |
| GAP-2 | 将"价格"明确为 reader 概念 | **DEFER** | "价格"27 字段/24 表是最稳定概念，但净价/全价未区分，且存在 CleanPrice vs FullPrice 歧义。第二批先区分语义变体再决定。 |
| GAP-3 | 抵押品可能不需要独立节点 | **ACCEPT** | 语料中无独立"抵押品"概念，逻辑通过保证金参数隐式表达。保留"抵押品"在业务区域词中作为概念候选，但不设独立 reader。 |
| GAP-4 | 客户作为 reader:counterparty 子属性 | **ACCEPT** | 仅 6 概念/3 表，证据不足。当前保留为客户概念候选但不设独立 reader。 |
| GAP-5 | 事件作为 lifecycle 阶段子概念 | **ACCEPT** | 事件类型/日期无需独立 reader，归入合同生命周期区域。 |
| GAP-6 | 净价 vs 全价歧义 | **DEFER** | CLEAN_PRICE(29表)和 FULL_PRICE(12表)确实分属不同语义。第二批在评估 reader:price 时一并处理。 |
| GAP-7 | 结算汇率 vs 交割汇率歧义 | **DEFER** | 外汇远期中"结算"与"交割"可能不等价。需第二批验证 REF_FX_FORWARD 表族后决定。 |
| GAP-8 | 持仓数量 vs 委托数量同名歧义 | **ACCEPT** | QUANTITY 同时出现在持仓表和订单表，同名字段在不同表中表达不同语义。归入对应概念的属性表达，不合并。 |
| GAP-9 | 产品上下文偏差（仅 IRS/OPTION/TRS） | **ACCEPT** | 语料偏重 TRS/期权。外汇远期、借贷股票等产品线缺少上下文锚定。这是语料偏差，不修改骨架——骨架是开放的。 |
| GAP-10 | 48 个真概念候选纳入骨架 | **DEFER** | 需逐一裁定。其中部分（如"业务类型"36表）可能是 CONFIGURATION 属性轴而非业务概念。第二批处理。 |

### 9.3 03 消歧审计报告的最小修复原则

| ID | 修复原则 | 裁定 | 理由 |
|---|---|---|---|
| FIX-1 | SHORT/LONG 英文 token 消歧 | **ACCEPT** | 03 审计排名第一的语义错误。18 字段误判。修复方向：direction facet 英文 pattern 仅在注释含"空头"/"多头"时匹配。不实现，记录为后续修订输入。 |
| FIX-2 | SOURCE/TARGET 双语义分离 | **ACCEPT** | 排名第二。party_role 的 SOURCE/TARGET 与 flow_side 应分离。不实现。 |
| FIX-3 | 泛化词概念降级 | **ACCEPT** | 排名第三。field_families/broad_categories 词标记为 ATTRIBUTE scope。不实现。 |
| FIX-4 | 列名/注释冲突优先级 | **ACCEPT** | 排名第四。注释优先于列名 token。冲突标记 CONFLICT 而非自动消解。不实现。 |

**所有 FIX 项均 ACCEPT 其方向，但 DEFER 其实现**——本提案约束为不修改实现代码和当前配置。这些修复原则将作为后续 OpenSpec change 或配置修订的输入。

### 9.4 跨报告冲突裁定

| 冲突 | 01 报告立场 | 02 报告立场 | 03 报告立场 | 裁定 | 理由 |
|---|---|---|---|---|---|
| "限额"归属 | position-risk business_area_terms 移除"限额"(A4) | "强平线"(6表)存在 | — | **DEFER** | 01 建议移除，但 02 显示有语料支撑。需验证"限额"是 CONFIGURATION 属性还是 risk 概念。 |
| 订单与交易分离 | 导航层可合并 | — | 概念层应分离(LOW) | **ACCEPT 03** | 导航层合并 reader:trade-order 可接受（用户视角），但概念层保持"订单"和"交易"分离。不影响导航结构。 |
| "结算"在估值风控 | cross_stage 改"现金流"(L4) | — | — | **ACCEPT 01** | "结算"是清算结算的 business_event，不应出现在估值风控的 cross_stage。 |
| 抵押品独立性 | 区域词保留"抵押品" | 语料无独立概念(GAP-3) | — | **ACCEPT 02** | 语料验证优先：无独立实体则不设 reader，但区域词保留为候选。 |
| SHORT/LONG token | — | — | CRITICAL 缺陷(FIX-1) | **ACCEPT 03** | 审计发现的高严重度缺陷，修复方向明确。不实现但记录。 |

---

## 10. 页面如何呈现这套结构

### 10.1 三栏布局（保持但不强迫所有关系树形化）

```
┌──────────────────────────────────────────────────────────────────┐
│  生命周期主线: [交易准备] [交易达成] [合同存续✓] [估值风控] [清算结算] [运营治理] │
│  当前阶段: 合同存续                                                 │
├────────────────┬───────────────────────┬──────────────────────────┤
│  左栏: 阶段地图  │  中栏: 概念索引         │  右栏: 表达详情与证据      │
│                │                       │                          │
│  核心对象:      │  概念列表(当前阶段):    │  选中: 多头动态名义本金     │
│  · 合约         │  · 名义本金 (55字段)    │  (标的币种)                │
│  · 合约腿      │  · 持仓 (4字段)        │                          │
│  · 名义本金     │  · 重置记录            │  限定维度:                │
│                │  · 行权记录            │  · position_side: LONG    │
│  业务事件:      │                       │  · measure_state: DYNAMIC │
│  · 重置/fixing  │  [概念详情投影]         │  · currency_basis: UNDERLYING│
│  · 行权        │  名义本金               │                          │
│  · 修订        │  ├─ 初始名义本金        │  物理实现:                │
│  · 平仓        │  ├─ 动态名义本金        │  · TRADEFLOW/REF_FAST_TRS │
│  · 终止        │  ├─ 多头动态名义本金 ✓  │    /LONG_DYNAMIC_NOTIONAL│
│  · 更替        │  ├─ 空头动态名义本金    │                          │
│                │  └─ ...               │  证据:                    │
│  跨环节关联:    │                       │  · column_name:           │
│  · 估值(→风控)  │  正交筛选:              │    LONG_DYNAMIC_NOTIONAL  │
│  · 现金流(→结算)│  [IDENTIFIER][MEASURE] │  · column_comment:       │
│  · 持仓(→风控)  │  [CURRENCY][TIME]      │    多头动态名义本金(标的币种)│
│                │  [STATE][DIRECTION]    │  · evidence_status: CANDIDATE│
│  [配置种子标记]  │                       │                          │
│  CONFIGURATION_ │                       │  [候选/发布切换]            │
│  SEED           │                       │  [原因筛选]               │
│                │                       │                          │
├────────────────┴───────────────────────┴──────────────────────────┤
│  治理队列(独立面板，不在业务树内):                                    │
│  · 618 条证据不足假设  · 66 条冲突  · 361 条同名异注释  · 1326 条未发布源概念 │
│  按原因拆分: 未识别概念 / 未识别属性 / 未识别限定 / 角色待确认 / 关系待确认 / │
│              证据不足 / 证据冲突                                       │
└──────────────────────────────────────────────────────────────────┘
```

### 10.2 呈现规则

1. **生命周期主线**在页面顶部横向展示为可点击的阶段条带。点击切换阶段后，左栏更新为该阶段的核心对象、业务事件和跨环节关联。
2. **业务区域**不作为独立页面层级，而是作为中栏概念索引的分组维度。用户可通过筛选器切换业务区域视图。
3. **三栏保持**但右栏不强迫所有关系树形化：
   - 右栏展示选中的属性表达及其限定维度、物理实现和证据。
   - 概念之间的关系（如名义本金→持仓引用）以"跨环节关联"链接形式呈现，不画为父子树。
   - 治理队列独立于业务树，按原因分组，不在三栏内折叠。
4. **候选/发布切换**：页面同时提供候选层和发布层视图。候选层显示全量观察表达和 Unknown/Conflict；发布层只显示满足发布条件的候选。
5. **配置种子标记**：生命周期入口在页面中标记为 `CONFIGURATION_SEED`（非证据），不冒充物理事实。
6. **Unknown 可见**：无物理证据的区域/概念显示"当前无物理证据"或候选状态，不生成虚构成员。
7. **证据边界可见**：每个候选显示 evidence_status（CANDIDATE/CONFIRMED/AMBIGUOUS/UNKNOWN/CONFLICT）。

### 10.3 页面与数据的关系

- 页面消费**真实运行 Projection**（当前 TRADEFLOW 输入），不使用示意案例冒充运行结果。
- 页面是可替换的 Projection，不回写 Physical Facts、原始注释或 Canonical 结果。
- 相同输入重跑时，确定性导航结果内容等价，Manifest 能定位全部差异。

---

## 附录 A：YAML 骨架文件说明

配套文件 `04-navigation-skeleton.yaml` 是本提案的候选骨架配置。它：

- 标记为 `status: candidate/provisional`，不冒充已发布业务本体。
- 包含整合后的生命周期阶段、业务区域、属性轴、限定维度、边界规则和多入口映射。
- 应用了 01 报告所有 ACCEPT 的差异（L1-L5, A1-A5, N1-N3, B1-B3）。
- 记录了 03 报告的已知缺陷作为 `known_defects`，不修复但标注。
- 列出了候选 reader（price/settlement/lifecycle-event）为 PROVISIONAL 状态。

## 附录 B：证据来源与边界声明

本提案的证据来源与 01 报告第 8 节一致：

| 来源类型 | 来源 | 用途 | 边界 |
|---|---|---|---|
| 外部权威 | ISDA CDM, FpML | 生命周期事件模型、原始操作、状态机 | 行业逻辑模型，不等于物理存储 |
| 内部 Wiki | 有界只读检索（pageId 见 01 报告第 8.2 节） | 弱上下文和实现关联 | 不等于业务定义或数据库声明事实 |
| 项目物理证据 | OTC 交易—合约—持仓草稿、Panorama facts | 交易主记录、合约属性、事件表、持仓表 | 测试库元数据，不代表生产业务事实 |
| 字段语义运行结果 | output/stage2/stage3/stage4 | 1,375 概念、1,559 属性表达 | 候选/投影，非 Canonical 结论 |
| 替代评审 | surrogate-review-v2 / reader-projection-review-v3 | ACCEPT_WITH_UNKNOWNS / ACCEPT | 工程评审，不等于业务验收 |

本提案的外部调研未提交或上传任何内部字段名、表名、注释和 Wiki 内容。

## 附录 C：与现有评审的衔接

| 评审文件 | 处置 | 本提案关系 |
|---|---|---|
| surrogate-review-v2.md | ACCEPT_WITH_UNKNOWNS | 本提案在评审基础上整合三份研究报告，不改变评审处置 |
| reader-projection-review-v3.md | ACCEPT (工程/读者) | 本提案保留三栏布局和治理队列独立面板，与 V3 评审一致 |
| navigation-proposal-v2.md | REVIEW_REQUIRED | 本提案是 V2 提案的后续整合，回答 V2 提出的 4 个判断问题 |
| tasks.md 7.5 | 未完成 | 本提案产出后仍需用户明确 ACCEPT 才能替换现有页面入口 |

**本提案不设置 `business_acceptance=ACCEPTED`，不授权规模化，不替换现有字段语义地图入口。**
