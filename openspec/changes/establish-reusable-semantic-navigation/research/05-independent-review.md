# Independent Review of Integrated Semantic Navigation

## 1. Disposition

**REWORK**

决定性理由：

1. `03-gold-set.yaml` 不能直接解析；人工按条核验的 27 个案例中，当前投影仍明确暴露短名/长名方向误判、SOURCE/TARGET 混义、泛化词升格和订单/交易合并等失败。
2. 五层语义没有严格隔离：Stage 5 将“交易对手短名（空头）”“交易对手长名（多头）”“原交易对手类型（源侧）”显示为 `SUPPORTED`，已知误判仍进入 Reader 表达层。
3. 1375 的分类算术可对账，但“57 个核心对象”“48 个真概念”“5 个 validated Reader 概念”均把候选、属性表达或字段属性混成业务概念，语义口径不成立。
4. 生命周期和业务区域不是完全正交：估值风控、清算结算和运营治理是跨合同存续的活动或支撑面；业务区域又重复设置“合同生命周期”，31 个矩阵入口均无独立 Evidence ID。
5. 第二 Schema 尚未选择或验证；TRADEFLOW 词法、配置和运行候选不能标为跨 Schema 已验证规则。

## 2. Scope and Evidence Read

### 实际读取

- 项目约束：`README.md`、`CONTEXT.md`、`AGENTS.md`、`docs/spec/README.md`、`docs/spec/12-open-decisions.md`、`docs/current-status-baseline.md`。
- Change 全包：`.openspec.yaml`、`proposal.md`、`design.md`、`tasks.md`、`inputs/frozen-inputs.yaml`、两份 delta spec，以及 `review/` 下三份既有评审。
- 研究输入：`01-domain-skeleton.md`、`02-field-corpus-analysis.md`、`02-field-shapes.json`、`03-disambiguation-audit.md`、`03-gold-set.yaml`、`04-integrated-navigation-proposal.md`、`04-navigation-skeleton.yaml`。
- 当前配置：`cases/tradeflow/reusable-semantic-navigation.yaml`。
- Stage 3：Manifest、1375 条 `business_concepts`、1559 条 `attribute_expressions`、1559 条 `data_semantic_candidates`、859 条 `semantic_review_queue`，以及页面 `index.html`、`catalog.js` 和相关概念分片。
- Stage 5：Manifest、`index.html`、`projection.js`、5 个 Reader concept 分片。
- 补充工程证据：固定 Harness 报告。其含义仅为输入哈希与固定检查点通过，且明确记录 `INDEPENDENT_REVIEW_NOT_ATTACHED`；不参与本报告的语义处置。

### 读取边界

- `03-gold-set.yaml` 第 65 行含未加引号的冒号文本，PyYAML 报 `mapping values are not allowed here`。为完成逐条审阅，仅在内存中把 `forbidden_misinterpretations` 的自由文本当作字符串解析；未修改源文件。
- 页面通过 HTML/JavaScript 与真实数据分片静态核验；未进行浏览器交互式可用性测试，因此键盘、响应式布局和实际点击旅程不在本次结论内。
- 未查询业务数据行，未访问外部站点，未把内部元数据外发。CDM/FpML 只按提案中的引用方式检查其证据边界，未重新验证外部模型的每个类型与枚举。
- Wiki 页面正文未重新读取；提案中的 Wiki pageId 和路径只能视为既有弱上下文，不能独立确认业务层级或矩阵入口。

## 3. Top-Level Skeleton Review

### 3.1 六个生命周期阶段

| 阶段 | 处置 | 决定性理由 |
|---|---|---|
| 交易准备 | ACCEPT | 作为交易前准入、主协议、限额和产品可交易性准备的导航阶段合理；不得因当前字段缺少准入证据而虚构成员。 |
| 交易达成 | ACCEPT | 询价、报价、订单、执行、确认形成可理解链路；但订单和成交交易必须保持不同对象身份。 |
| 合同存续 | REWORK | 被写成从形成到终止的包围阶段，同时估值、保证金、现金流和结算又在存续期间反复发生；它不能与后三者形成简单串行阶段。 |
| 估值风控 | REWORK | 估值、风险度量、限额、抵押品和保证金管理是多个持续活动，不是合同存续之后的单一阶段；应作为并行活动面或可重复业务过程。 |
| 清算结算 | REWORK | 清算、支付、交割可由成交或任一生命周期事件多次触发，不是单一末端阶段；清算、结算义务、转移指令和结算结果需分开。 |
| 运营治理 | REWORK | 报表、对账、报送、批处理、审计和数据治理横切全部阶段，不属于与前五项同类型的生命周期阶段。 |

结论：六项可保留为“导航泳道候选”，不能宣称为严格顺序的生命周期。至少应将“运营治理”移为横切支撑面，并明确合同存续与估值/结算是可重叠、可重复关系。

### 3.2 十个一级业务区域

| 业务区域 | 处置 | 决定性理由 |
|---|---|---|
| 参与主体 | REWORK | 客户、交易对手、交易员、部门和联系人不是同一种主体层级；当前又把客户当作交易对手子属性，需先明确法律实体、业务关系和人员角色。 |
| 产品与标的 | ACCEPT | 产品定义和标的资产是稳定且可区分的 OTC 业务对象；应保持产品、产品实例、标的和行情数据边界。 |
| 询价、订单与交易 | REWORK | 可作为导航区域，但不能把询价、报价、订单、执行和交易合并为一个 Reader 概念；当前 `reader:trade-order` 已违反此边界。 |
| 合约与经济条款 | REWORK | “合同/主协议”“交易合约”“合约腿”“经济条款”层级未定义；实际投影又把名义本金挂到估值/保证金/现金流区域，区域职责不一致。 |
| 合同生命周期 | REWORK | 与顶层 `contract-lifecycle` 阶段重复同一维度，破坏生命周期 × 业务区域正交性；应表达生命周期事件对象/过程，而不是重复一条阶段轴。 |
| 持仓与风险 | REWORK | 持仓/头寸是状态对象，敞口是风险度量，对冲是关系/行为，限额是控制；当前区域过度聚合。 |
| 估值、履约保障与现金流 | REWORK | 估值结果、保证金、抵押品和现金流是不同对象/过程；现金流计算与实际支付边界虽在文档中声明，区域和实际挂接仍重叠。 |
| 清算与结算 | REWORK | 区域本身合理，但 `04` 使用 `clearing-settlement`，Stage 5 仍显示 `execution-clearing-settlement`，标识和语义版本漂移；无当前 Reader 概念验证。 |
| 参考数据与配置 | REWORK | 市场参考数据是业务输入，产品模板是业务配置，系统规则/映射是技术实现；三者不应作为同质业务对象放在一层。 |
| 运营、报表与数据加工 | REWORK | 运营活动、读者报表、监管报送、ETL 和审计日志混合业务与技术职责；应拆成运营/报告消费与技术加工/审计投影。 |

### 3.3 导航粒度

- “生命周期 → 业务区域 → 核心对象/业务事件 → 稳定业务概念”是可用上限，但当前区域本身已经把多个对象、过程和技术支撑面压在一起。
- `状态/类型/金额/币种/日期/简称/缩写` 不应成为业务树节点；Stage 3 仍把这些词保留为 `DOMAIN` candidate，说明分层禁令尚未落实到事实投影。
- 多入口必须引用同一 concept identity。当前 Stage 5 对 5 个 Reader identity 做到了分片复用，但入口本身全部是配置种子，不能据此确认业务归属。

## 4. Core Concept Review

### 4.1 要求概念逐项审阅

“允许属性”指可以在详情/矩阵表达的类型；“限定”指条件维度，不表示已被当前规则正确识别。

| 概念 | 定义与排除边界 | 生命周期 / 区域入口 | 允许属性与限定 | 真实正例 / 误导反例 | 证据状态 | 第一批 |
|---|---|---|---|---|---|---|
| 客户 | 与机构建立服务/交易关系的一方；不等于任意交易对手，也不是名称属性 | 交易准备 / 参与主体 | 标识、名称、分类、准入；主体角色 | `客户短名` / `CTPTY_SHORT_NAME` 不能证明客户=交易对手 | 仅少量候选且被并入 counterparty | DEFER |
| 交易对手 | 某交易或合同关系的对方主体；排除简称、部门和数据源/目标侧 | 交易准备、交易达成 / 参与主体 | 标识、名称、角色、关系状态 | `KEY_CTPTY_ID` / `CTPTY_SHORT_NAME` 的 SHORT 不是空头 | 有大量字段，但已知严重误判仍为 SUPPORTED | REWORK_REQUIRED |
| 产品 | 可交易衍生品类型/方案定义；排除具体合约实例和标的 | 交易准备、交易达成 / 产品与标的 | 类型、参数、适用市场 | 产品类型字段 / “类型”本身不是产品 | 无 Reader 定义，当前词表证据 | DEFER |
| 标的 | 决定衍生价值的资产、指数或篮子；排除产品和行情值 | 交易达成、合同存续 / 产品与标的 | 代码、名称、类型、币种 | 标的代码候选 / `目标` 不等于标的 | 无 Reader 定义，候选碎片化 | DEFER |
| 询价 | 向潜在交易方请求可成交条件的事件/记录；排除报价和订单 | 交易达成 / 询价订单交易 | 标识、发起方、时间、状态 | 当前语料无稳定 Reader 实例 / “询价类型”只是属性 | 未形成可复算 Reader | DEFER |
| 报价 | 对询价或市场请求给出的价格/条款提议；排除成交交易 | 交易达成 / 询价订单交易 | 价格、数量、有效期、方向 | 报价类型候选 / PRICE 不能单独证明报价 | 未形成可复算 Reader | DEFER |
| 订单 | 下达或接收的交易意图/委托；排除成交结果 | 交易达成 / 询价订单交易 | 标识、时间、数量、状态、主体角色 | `KEY_STOCK_ORDER_ID` / 不等于 `KEY_OTC_TRADE_ID` | 被 `reader:trade-order` 合并 | REWORK_REQUIRED |
| 交易 | 已达成或记录的成交事实；排除未成交订单和法律主协议 | 交易达成 / 询价订单交易 | 标识、成交时间、价格、数量、状态 | `KEY_OTC_TRADE_ID` / “订单业务主键”不是交易主键 | 被订单表达污染 | REWORK_REQUIRED |
| 合约 | 交易形成的权利义务记录；排除主协议、模板和订单 | 交易达成、合同存续 / 合约经济条款 | 标识、版本、状态、有效期 | `CONTRACT_ID` / 合约模板编号不是合约实例 | 无独立 Reader 边界 | DEFER |
| 合约腿 | 合约中独立计价/支付的组成部分；排除字段后缀 LEG | 合同存续 / 合约经济条款 | 标识、顺序、条款、付款方向 | `KEY_LEG_ID` / 任意含 LEG 的字段不自动成腿 | 只有字段词与结构候选 | DEFER |
| 经济条款 | 合约权利义务的结构化条件集合；不是单一业务对象 | 交易达成、合同存续 / 合约经济条款 | 金额、利率、期限、币种、日历 | 利差、固定利率、券息 / “类型”不是条款对象 | 当前被拆成多个候选 | DEFER |
| 持仓 | 某主体在时点上的合约/资产余额状态；排除订单和风险敞口 | 合同存续、估值风控 / 持仓风险 | 标识、数量、日期、类型、来源 | `KEY_LEG_POSITION_ID` / `POSITION_SOURCE` 的 source 未必是业务来源 | 16 字段/10 表，但来源误限定 | REWORK_REQUIRED |
| 头寸 | 具有方向和数量的暴露单位；与持仓可能相关但不默认同义 | 合同存续、估值风控 / 持仓风险 | 方向、数量、币种、时点 | 多头/空头数量 / “长名”“短名”不是头寸方向 | 提案未给持仓/头寸判别准则 | DEFER |
| 名义本金 | 计算现金流/收益的合约基准金额；排除市值、保证金和结算额 | 合同存续 / 合约经济条款；估值仅为引用 | 金额、币种口径、时点、方向、变化方式 | `NOTIONAL_BASE`、`INITIAL_NOTIONAL` / `COLLATERAL_NOTIONAL` 名称不自动等于抵押品 | 55 字段/19 表，仍有币种与列名冲突 | REWORK_REQUIRED |
| 估值 | 对合约/持仓在时点上的价值计算或结果；排除价格输入和结算额 | 估值风控 / 估值 | 标识、日期、方法、金额、币种 | `VALUATION_DATE` / 同步计数不是估值结果 | 只有零散属性，未定义对象粒度 | DEFER |
| 风险敞口 | 在口径和时点下的潜在损失/敏感暴露；排除持仓数量和市值泛词 | 估值风控 / 持仓风险 | 数量、金额、币种、风险类型 | `EXPOSURE_VALUE`、`EXPOSURE_QUANTITY` / 表名含 exposure 不足以确认 | 两个明确字段，边界仍不足 | DEFER |
| 保证金 | 为履约保障计算、要求或持有的金额/余额；排除阈值、比例和抵押品资产 | 估值风控；收付进入清算结算 / 履约保障 | 金额、余额、比例、阈值、收付方向、时点 | `MARGIN_BALANCE_INIT`、`INITIAL_AMT` / `MARGIN_DIRECTION` 未自动等于持仓方向 | 49 字段/17 表，方向和对象/阈值混合 | REWORK_REQUIRED |
| 抵押品 | 为担保义务而质押/转移的资产；不等于保证金参数或名义本金 | 估值风控、清算结算 / 履约保障 | 资产标识、数量、价值、折扣率、状态 | `MARGIN_COLLATERAL_TYPE` 只是类型提示 / `COLLATERAL_NOTIONAL` 不是资产实例 | 无独立实体证据 | DEFER |
| 现金流 | 按合约条款计算的应收应付金额及日期；排除已执行支付和结算状态 | 合同存续、估值风控、清算结算 / 现金流 | 金额、日期、币种、收付方向、状态 | `IRS_CASH_FLOW_ID`、计息现金流 / “现金”泛词不是现金流 | 50 个碎片候选，无 Reader | DEFER |
| 交割 | 履行证券/资产或资金转移义务的事件；排除计算出的现金流 | 清算结算 / 清算结算 | 方式、日期、数量、状态、参与方 | 交割方式/汇率候选 / 结算字段不自动证明已交割 | 未形成事件粒度 | DEFER |
| 清算 | 确定义务、净额和参与方的过程/结果；排除最终资产转移 | 清算结算 / 清算结算 | 机构、净额、日期、状态 | 清算机构/清算金额候选 / 同步状态不是清算本身 | 无 Reader，区域标识漂移 | DEFER |
| 结算结果 | 义务完成、失败或待处理的结果；排除结算方式、币种和日期属性 | 清算结算 / 清算结算 | 状态、金额、日期、失败原因 | `SETTLEMENT_GENERATED` 仅是状态提示 / “结算状态”不是独立结果对象 | 无稳定身份和粒度 | DEFER |

### 4.2 五个现有 Reader 概念重新判定

| Reader | 判定 | 理由 |
|---|---|---|
| 名义本金 | REWORK_REQUIRED | 基础概念可用，但定义仍是占位式“当前字段支持的候选”；挂接区域与“经济条款”不一致，并存在币种冲突和列名/注释冲突。 |
| 交易对手 | REWORK_REQUIRED | 页面把 12 个“短名（空头）”、5 个“简称（空头）”、1 个“长名（多头）”作为 SUPPORTED/PROVISIONAL 表达，直接失败。 |
| 交易 / 订单 | REJECT | 这是两个不同业务对象。导航区域可以并列展示，但不能用单一 Reader identity 和统一定义承载二者。 |
| 持仓 | REWORK_REQUIRED | 正例有限；“持仓来源（源侧）”把业务来源和数据侧混合，且与头寸的边界没有定义。 |
| 保证金 | REWORK_REQUIRED | 保证金本体、金额、余额、阈值、比例和方向混在一个表达集合；`保证金方向`仍未稳定落到 cashflow_direction。 |

本审阅不使用 `validated`。当前配置里的五个 `status: validated` 均应降为待复核状态。

## 5. Layer-Separation Review

### 5.1 五层判断

| 层 | 应承担的职责 | 当前结果 | 判定 |
|---|---|---|---|
| 业务概念 | 稳定对象、事件或可定义业务事实 | 1375 个 candidate 中包含 `状态/类型/金额/简称` 等泛化词 | FAIL |
| 属性表达 | 某概念在真实字段中的具体表达 | Stage 5 能显示表达矩阵，但错误方向已固化进表达 label | FAIL |
| 字段属性 | 标识、计量、时间、审计等跨概念形态 | 轴存在，但 CONFIGURATION、STATE、DIRECTION 过宽 | REWORK |
| 限定条件 | 时点、方向、币种、角色等上下文条件 | 14 维存在重叠；部分限定由英文 token 错误推断 | FAIL |
| 物理实现 | 表、字段名、注释、Evidence 和来源 | 页面可下钻并保留来源；但物理英文 token 仍影响业务表达 | REWORK |

### 5.2 真实字段逐项核验（24 项）

| # | 物理字段 / 注释 | 应属层次 | 审阅结果 |
|---:|---|---|---|
| 1 | `REF_IRS.NOTIONAL_BASE` / 初始名义本金 | 名义本金属性表达 + INITIAL | 正例；不应独立成“初始”概念。 |
| 2 | `REF_OTC_OPTION_DEAL.INITIAL_NOTIONAL` / 初始名义本金 | 名义本金属性表达 + INITIAL | 正例。 |
| 3 | `KEY_CTPTY_ID` / 交易对手ID | 交易对手的 IDENTIFIER | 正例；ID 不成为对象。 |
| 4 | `MARGIN_BALANCE_INIT` / 初始保证金 | 保证金属性表达 + INITIAL | 正例。 |
| 5 | `INITIAL_AMT` / 初始保证金 | 保证金属性表达 + INITIAL | 正例；物理名不能作为 Reader label。 |
| 6 | `MARGIN_DIRECTION` / 保证金支付方向 | 保证金表达 + cashflow_direction | 当前部分表达没有方向限定，FAIL。 |
| 7 | `EVENT_STATUS` / 事件状态 | 生命周期事件的 STATE | 状态不是顶层概念。 |
| 8 | `SETTLEMENT_GENERATED` / 债券结算状态 | 结算/交割流程状态 | 不能据“结算”认定结算结果对象。 |
| 9 | `BUSINESS_TYPE` / 业务类型 | 分类/配置属性候选 | 不能列入“真业务概念”即发布。 |
| 10 | `SOURCE_TYPE` / 事件来源类型 | 业务来源属性 | Stage 3 显示“事件来源类型（源侧）”，把来源误作 flow_side，FAIL。 |
| 11 | `VALUATION_RATE_SOURCE_ID` / 估值汇率来源 | 估值汇率来源/标识属性 | 显示“（源侧）”属于数据侧误判，FAIL。 |
| 12 | `TARGET_CTPTY_ID` / 目标交易对手 | 交易对手 + 映射角色待定 | Stage 5 标为 flow_side TARGET，FAIL。 |
| 13 | `CTPTY_SHORT_NAME` / 交易对手短名 | 交易对手名称属性 | 显示“（空头）”，CRITICAL FAIL。 |
| 14 | `CTPTY_LONG_NAME` / 交易对手长名 | 交易对手全称属性 | 显示“（多头）”，CRITICAL FAIL。 |
| 15 | `SOURCE_CTPTY` / 原交易对手类型 | 交易对手关系/类型属性待判 | 显示“（源侧）”，不能由 SOURCE token 决定。 |
| 16 | `KEY_STOCK_ORDER_ID` / 订单业务主键 | 订单 IDENTIFIER | 不得并为交易标识。 |
| 17 | `KEY_OTC_TRADE_ID` / 交易ID | 交易 IDENTIFIER | 与订单 ID 分离。 |
| 18 | `CONTRACT_ID` / 合约编号 | 合约 IDENTIFIER | 编号不是合约本体。 |
| 19 | `KEY_LEG_ID` / 腿ID | 合约腿 IDENTIFIER | 需要合约腿上下文；LEG token 单独不足。 |
| 20 | `EXPOSURE_VALUE` / 敞口市值 | 风险敞口 MEASURE | 正例，但不足以证明整个表/区域。 |
| 21 | `CREATED_BY` / 创建人 | AUDIT | 不得污染业务树；语料中 185 个实例。 |
| 22 | `UPDATED_DATETIME` / 更新时间 | AUDIT/TIME | 不得成为业务概念；语料中 213 个实例。 |
| 23 | `PUSH_BATCH_NO` / 推送批次号 | 技术批次 IDENTIFIER/AUDIT | 不得成为业务对象。 |
| 24 | `ID` / 主键（UUID 字符串） | 技术标识 | UUID 是物理类型提示，不是业务对象。 |

精确的 `SOURCE_SYSTEM`、`UPDATED_AT`、`EXT_FIELD_1` 和“结算现金流”标签未在当前 1559 个候选表达中观察到；其缺失应记为 `NOT_OBSERVED_IN_CURRENT_PROJECTION`，不能凭示例名称推断归类成功。

## 6. Attribute and Qualifier Review

### 6.1 十个属性轴

| 属性轴 | 处置 | 理由 |
|---|---|---|
| IDENTIFIER | KEEP | 可跨交易、合约、持仓复用；必须绑定所属业务对象。 |
| ROLE | RENAME | 改为 `PARTY_ROLE`，只承载主体在关系中的角色；排除 SOURCE/TARGET 数据侧和买卖/多空方向。 |
| STATE | RENAME | 改为 `BUSINESS_OBJECT_STATE`，状态值必须带对象命名空间，避免所有状态共用一个枚举。 |
| DIRECTION | REJECT | 它把交易方向、持仓方向和收付方向聚成过宽轴；保留三个独立限定维度即可。 |
| MEASURE | KEEP | 金额、数量、比率等形态可复用，但价格/余额/市值仍需概念上下文。 |
| CURRENCY | KEEP | 作为度量币种属性合理；币种角色由 qualifier 表达。 |
| TIME | KEEP | 日期/时间形态可复用；具体业务时点由 qualifier 或属性表达确定。 |
| CONFIGURATION | REJECT | 类型、类别、模式、参数、规则并非同一种字段属性；该大桶会继续制造伪概念。 |
| AUDIT | KEEP | 创建、更新、来源追踪可明确隔离技术审计字段。 |
| OPEN | DEFER | 它是治理状态/扩展槽，不是与标识、计量同类型的正式属性轴。 |

当前正式配置只有 9 个轴，不含 `OPEN`；提案 YAML 有 10 个。报告中的“10 个轴”与运行配置并非同一版本。

### 6.2 十四个限定维度

| 限定维度 | 处置 | 理由 |
|---|---|---|
| temporal_stage | RENAME | 改为 `observation_time_role`；INITIAL/CURRENT/END/调整前后是观察口径，不是业务生命周期阶段。 |
| position_side | KEEP | 多头/空头独立维度合理；必须由中文注释或明确上下文确认，禁用裸 SHORT/LONG 名称投票。 |
| trade_side | KEEP | BUY/SELL 表达交易行为方向，不等于主体角色或持仓方向。 |
| cashflow_direction | KEEP | PAY/RECEIVE 表达收付方向；保证金方向需落入此维。 |
| currency_basis | KEEP | 原币/本币/标的币种/结算币种边界合理，但列名与注释冲突必须保留 Conflict。 |
| party_role | RENAME | 改为 `party_relationship_role`，补齐 counterparty 等关系角色；CLIENT/INTERNAL 不能覆盖买卖方和数据侧。 |
| lifecycle_stage | REJECT | ORDER/EXECUTION/POSITION/CLEARING/TERMINATION 混合对象、事件和阶段，并与顶层生命周期重复。 |
| measure_state | REJECT | DYNAMIC/FIXED/AVAILABLE/FROZEN/ACCUMULATED/ESTIMATED 已被四个更窄维度拆分，保留会重复编码。 |
| flow_side | TRADEFLOW_ONLY | 只适用于映射/加工数据侧；不能作为一般 OTC 主体限定。 |
| variability | KEEP | DYNAMIC/FIXED 是稳定的变化方式维度。 |
| aggregation_state | KEEP | ACCUMULATED 是累计口径；未来值扩展前保持开放。 |
| availability_state | RENAME | 改为 `availability_condition`，避免与业务对象状态混淆。 |
| estimation_status | KEEP | ESTIMATED 是计量结果的估算条件。 |
| attribute_kind | MERGE | IDENTIFIER 应并入字段属性轴，不应再作为 qualifier 重复表达。 |

## 7. Multi-Entry Matrix Review

`04-navigation-skeleton.yaml` 有 31 个非空入口。每项只有自然语言 reason，没有独立 Evidence ID；Stage 5 对实际展示的 7 个入口也明确标注 `CONFIGURATION_SEED｜非证据`。因此以下全部只能保留为配置种子，不能视为已确认导航。

| # | 业务区域 × 生命周期 | 提案角色/理由摘要 | 独立证据 | 结论 |
|---:|---|---|---|---|
| 1 | 参与主体 × 交易准备 | CORE / 准入限额 | 无 | CONFIGURATION_SEED |
| 2 | 参与主体 × 交易达成 | CROSS / 交易引用 | 无 | CONFIGURATION_SEED |
| 3 | 参与主体 × 合同存续 | CROSS / 引用 | 无 | DEFER；理由空泛 |
| 4 | 参与主体 × 估值风控 | CROSS / 对手方敞口 | 无 | CONFIGURATION_SEED |
| 5 | 产品标的 × 交易准备 | CORE / 产品准入 | 无 | CONFIGURATION_SEED |
| 6 | 产品标的 × 交易达成 | CORE / 产品选择 | 无 | CONFIGURATION_SEED |
| 7 | 产品标的 × 合同存续 | CROSS / 条款定义 | 无 | REWORK；产品、标的、条款对象混合 |
| 8 | 产品标的 × 估值风控 | CROSS / 定价 | 无 | CONFIGURATION_SEED |
| 9 | 询价订单交易 × 交易达成 | CORE / 交易达成 | 无 | CONFIGURATION_SEED；需拆对象 |
| 10 | 询价订单交易 × 合同存续 | CROSS / 被事件修改 | 无 | REWORK；被修改的是交易状态/合约，不是整个区域 |
| 11 | 询价订单交易 × 清算结算 | CROSS / 产生义务 | 无 | CONFIGURATION_SEED |
| 12 | 合约条款 × 交易达成 | CORE / 合约形成 | 无 | CONFIGURATION_SEED |
| 13 | 合约条款 × 合同存续 | CORE / 条款引用 | 无 | CONFIGURATION_SEED |
| 14 | 合约条款 × 估值风控 | CROSS / 估值基准 | 无 | CONFIGURATION_SEED |
| 15 | 生命周期区域 × 合同存续 | CORE / 生命周期事件 | 无 | REWORK；与阶段轴自指重复 |
| 16 | 生命周期区域 × 估值风控 | CROSS / 重置输入 | 无 | CONFIGURATION_SEED |
| 17 | 生命周期区域 × 清算结算 | CROSS / 事件触发 | 无 | CONFIGURATION_SEED |
| 18 | 持仓风险 × 合同存续 | CORE / 持仓身份属性 | 无 | CONFIGURATION_SEED |
| 19 | 持仓风险 × 估值风控 | CORE / 风险估值口径 | 无 | REWORK；持仓与风险对象未拆 |
| 20 | 持仓风险 × 清算结算 | CROSS / 交割量 | 无 | CONFIGURATION_SEED |
| 21 | 估值履保现金流 × 交易准备 | CROSS / 限额参数 | 无 | REWORK；限额不代表整个区域 |
| 22 | 估值履保现金流 × 合同存续 | CROSS / 名义本金 | 无 | REWORK；名义本金首先是经济条款 |
| 23 | 估值履保现金流 × 估值风控 | CORE / 估值保证金现金流 | 无 | REWORK；三个对象/过程合并 |
| 24 | 估值履保现金流 × 清算结算 | CROSS / 保证金收付 | 无 | CONFIGURATION_SEED |
| 25 | 清算结算 × 合同存续 | CROSS / 事件触发 | 无 | CONFIGURATION_SEED |
| 26 | 清算结算 × 估值风控 | CROSS / 估值触发 | 无 | REWORK；估值不总是直接触发结算 |
| 27 | 清算结算 × 清算结算 | CORE / 实际交割 | 无 | REWORK；自指入口且清算≠交割 |
| 28 | 参考配置 × 交易准备 | CORE / 参数设置 | 无 | CONFIGURATION_SEED |
| 29 | 参考配置 × 估值风控 | CROSS / 估值输入 | 无 | CONFIGURATION_SEED |
| 30 | 参考配置 × 运营治理 | CORE / 参考数据维护 | 无 | CONFIGURATION_SEED |
| 31 | 运营报表数据 × 运营治理 | CORE / 批处理报表对账报送 | 无 | REWORK；技术加工与业务运营混合 |

## 8. Count Reconciliation

| 口径 | 提案值 | 复算/来源 | 结论 |
|---|---:|---:|---|
| business concept candidates | 1375 | `business_concepts.jsonl` 1375 行 | VERIFIED AS CANDIDATE COUNT |
| direct_attach | 57 | 57 个唯一 concept ID | VERIFIED COUNT；不是 57 个核心对象 |
| attribute_expr classification | 377 | 377 个唯一 concept ID | VERIFIED COUNT |
| field_attribute classification | 605 | 605 个唯一 concept ID | VERIFIED COUNT |
| qualifier_cond classification | 0 | 0 | VERIFIED；与另有 14 维/32 qualifier 不同口径 |
| tech_audit classification | 1 | 1 (`Operator`) | VERIFIED COUNT；明显低估审计字段 |
| insufficient | 2 | 2 | VERIFIED COUNT |
| unexplained | 333 | 333 | VERIFIED COUNT |
| 分类合计 | 1375 | 57+377+605+0+1+2+333=1375 | ARITHMETIC PASS ONLY |
| “48 个真概念候选” | 48 | `likely_concepts` 48 项 | VERIFIED COUNT；SEMANTIC FAIL，含创建/修改时间、日期、币种、类型等属性 |
| “57 个第一批核心对象” | 57 | 等同 direct_attach | SEMANTIC FAIL；其中含 Price、日期、状态、短名、简称、保证金线、部门等 |
| 第一批五组括号数 | 60 | 7+18+16+5+14=60 | UNVERIFIED；未说明 3 个重复/差异如何消除 |
| Reader concepts（提案） | 8 | YAML 5 validated + 3 provisional | VERIFIED CONFIG COUNT；不是 8 个已验证概念 |
| Reader concepts（Stage 5） | 5 | 5 个 Reader 分片 | VERIFIED PROJECTION COUNT |
| Stage 5 expressions | 95 | Manifest | VERIFIED PROJECTION COUNT |
| Stage 5 attached/unattached | 5 Reader / 1326 source concepts | Manifest | 不可相加为 1375；5 是聚合 Reader identity，1326 是未发布 source concept |
| Stage 3 attribute expressions | 1559 | JSONL 1559 行 | VERIFIED |
| candidate field instances | 4294 | 1559 candidates 去重 field refs | VERIFIED |
| source fields in manifest | 5512 | Stage 3 Manifest | VERIFIED；与 4294 不是同一覆盖口径 |
| TRADEFLOW total columns | 13611 | 02-field-shapes | VERIFIED FROM FROZEN ANALYSIS；不等于已进入候选字段 |
| candidate-covered tables / total tables | 233 / 477 | 02-field-shapes | VERIFIED；不能声称全表语义承载已验证 |
| 第二批子集 | 48 + 117 | unexplained 的 likely/ambiguous 子集 | VERIFIED IF DISJOINT；数据结构显示分别列出 |
| unexplained 剩余 | 168 | 333-48-117 | ARITHMETIC PASS |

结论：1375 的分桶算术自洽，但概念、source concept、Reader concept、attribute expression、field instance、physical column 和 table 的口径在提案叙述中多次互换。算术通过不能证明分类正确。

“范围外”不应称为 Unknown。Stage 5 的 `NAVIGATION_CANDIDATE_NOT_PUBLISHED=1326` 已单独呈现，这是正确方向；但它还没有进一步区分“范围外、非首批、属性层、证据不足、真正未知”。

## 9. Gold Set Results

源文件共有 27 项，但当前 YAML 不能直接解析。以下结果基于逐条文本与当前 Stage 3/5 投影对照；任何明确失败阻止 ACCEPT。

| ID | 结果 | 决定性证据 |
|---|---|---|
| A01 | FAIL | `CTPTY_SHORT_NAME` 仍显示“交易对手短名（空头）”。 |
| A02 | FAIL | 仍显示“交易对手简称（空头）”。 |
| A03 | FAIL | 仍显示“客户短名（空头）”。 |
| A04 | FAIL | `SHORT_NAME` 仍显示“交易对手简称（空头）”。 |
| A05 | PASS | `CTPTY_SHTNAME` 显示“交易对手短名”，未附方向。 |
| B01 | FAIL | `CTPTY_LONG_NAME` 仍显示“交易对手长名（多头）”。 |
| C01 | PASS | 空头动态名义本金保留 position_side SHORT。 |
| C02 | NOT_EVALUABLE | Gold 写“标的币种”，当前同表实例/投影显示“结算币种”，冻结输入与 Gold 描述不一致。 |
| C03 | FAIL | SHORT 字段的 expected_base_concept 却写成“多头内在价值系数”，Gold 自身方向矛盾。 |
| C04 | FAIL | Stage 3 有“计息起止（空头）”，但 Stage 5 `reader:position` 未包含该表达，无法完成允许入口。 |
| D01 | FAIL | “目标交易对手”仍被标为 flow_side TARGET。 |
| D02 | PASS | Stage 5 “源侧交易对手ID”只显示 identifier，未再显示 flow_side；标签仍需业务映射语境解释。 |
| E01 | FAIL | `状态` 仍存在于 Stage 3 DOMAIN candidate。 |
| E02 | FAIL | `类型` 仍存在于 Stage 3 DOMAIN candidate。 |
| E03 | FAIL | `金额` 仍存在于 Stage 3 DOMAIN candidate。 |
| E04 | FAIL | `简称` 仍存在于 Stage 3 DOMAIN candidate。 |
| F01 | NOT_EVALUABLE | 指定表/列组合未在当前 candidate 实例中定位；冲突队列存在相关名义本金冲突，但不能替代该条复核。 |
| G01 | NOT_EVALUABLE | “卖方”未进入五个 Reader 分片；不能仅凭 trade_side 规则宣告通过。 |
| G02 | NOT_EVALUABLE | “买入数量”未进入五个 Reader 分片；需订单/交易对象上下文。 |
| H01 | FAIL | Stage 5 继续使用单一 `reader:trade-order` identity。 |
| I01 | PASS | `CTPTY_NAME` 未附 SHORT 限定。 |
| I02 | PASS | `COUNTERPARTY` 显示为交易对手短名，未生成独立业务对象。 |
| J01 | FAIL | “事件来源类型”显示“（源侧）”。 |
| J02 | FAIL | “估值汇率来源”显示“（源侧）”。 |
| K01 | PASS | 初始名义本金在 Stage 5 作为名义本金表达 + INITIAL。 |
| L01 | FAIL | Stage 3 仍保留“背靠背交易对手缩写”独立 DOMAIN source concept；Stage 5 只是 Reader 聚合，并未纠正 Canonical candidate。 |
| M01 | FAIL | “保证金方向”作为 SUPPORTED 表达却无 cashflow_direction；只有“保证金支付方向”被限定为 PAY。 |

汇总：`PASS=6`、`FAIL=17`、`NOT_EVALUABLE=4`。Gold Set 结果为 **FAIL**。

## 10. Positive, Ambiguous and Counterexample Cases

| 类型 | 案例 | 期望 | 当前判断 |
|---|---|---|---|
| 正例 | 初始名义本金 | 名义本金 + INITIAL → 物理字段 | PASS |
| 正例 | 交易对手ID | 交易对手 + IDENTIFIER → `KEY_CTPTY_ID` | PASS |
| 正例 | 初始保证金 | 保证金 + INITIAL → 5 个字段实例 | PASS |
| 正例 | 结算现金流 | 现金流 → 收付/结算执行 → 物理字段 | NOT_EVALUABLE；无 Reader，只有碎片候选 |
| 歧义 | 方向 | 必须区分 position/trade/cashflow | FAIL；泛化 DIRECTION 轴仍存在 |
| 歧义 | 状态 | 绑定具体对象状态空间 | FAIL；仍是 DOMAIN candidate |
| 歧义 | 类型 | 绑定对象或配置语境 | FAIL；48 候选中仍含多种“类型” |
| 歧义 | 来源 | 区分业务来源、主体角色、数据侧 | FAIL；事件/汇率来源被标源侧 |
| 歧义 | 目标 | 区分目标主体、标的、数据目标 | FAIL；目标交易对手被标数据侧 |
| 歧义 | 当前值 | 保留具体对象、时点和口径 | NOT_OBSERVED；不得凭泛词自动归类 |
| 误导 | 交易对手短名 | 名称属性，不是空头 | FAIL |
| 误导 | 交易对手长名 | 全称属性，不是多头 | FAIL |
| 误导 | 原交易对手类型 | 关系/类型待判，不是数据源侧 | FAIL |
| 误导 | 订单业务主键 | 订单标识，不是交易对象 | FAIL；仍在合并 Reader 下 |
| 误导 | 结算状态 | 状态属性，不是结算结果对象 | PARTIAL；未升顶层，但对象边界未定义 |
| 误导 | 市场成交配置 | 配置/市场/成交需上下文拆分 | NOT_OBSERVED；字符串规则不得推断 |
| 误导 | 合约模板编号 | 模板标识，不是合约实例 | NOT_OBSERVED；规则应明确禁止升格 |
| 技术 | `ID` / UUID 注释 | 技术标识 | PASS AS BOUNDARY；不得发布业务对象 |
| 技术 | `CREATED_BY` | AUDIT | PASS AS BOUNDARY；当前仍需从 1375 概念树剥离 |
| 技术 | `UPDATED_DATETIME` | AUDIT/TIME | PASS AS BOUNDARY |
| 技术 | `PUSH_BATCH_NO` | 技术批次标识 | PASS AS BOUNDARY |
| 技术 | `SOURCE_SYSTEM` | 数据血缘/审计 | NOT_OBSERVED |
| 技术 | `EXT_FIELD_1` | 技术扩展槽 | NOT_OBSERVED |

## 11. Cross-Schema Boundary

### 可作为跨 Schema 候选的稳定部分

- 业务对象与属性/限定/物理实现分层的原则。
- 询价、订单、交易、合约、生命周期事件、持仓、估值、风险、现金流、清算/结算等开放业务概念集合。
- IDENTIFIER、MEASURE、CURRENCY、TIME、AUDIT 等宽属性形态。
- 候选、证据、反证、Conflict、Unknown、Review Decision 和 Projection 分离。

### TRADEFLOW 专属或当前配置专属

- 中文注释与英文物理 token 的 SHORT/LONG、SOURCE/TARGET 规则。
- `tradeflow-v1` qualifier 值、当前 5 个 Reader source label 清单、业务区域词种子。
- `flow_side`、映射表语境、当前字段覆盖统计和 233/477 表覆盖范围。
- 名义本金、保证金和持仓的当前表达集合及其表分布。

### 当前运行候选

- 1375 source concept、1559 attribute expression、95 个 Stage 5 Reader 表达和 31 个矩阵入口。
- 当前配置种子、Wiki 弱上下文、SUPPORTED/PROVISIONAL 状态都不是跨 Schema 事实。

`docs/spec/12-open-decisions.md` 的 D-010 明确“第二 Schema 验证对象”仍是 V1 后决定事项，并阻塞把方法宣传为全 TITANS 通用。任务 7.2 的勾选不能覆盖这个当前事实；未见第二 Schema 的 case pack、运行 Manifest、反例结果或独立审阅。因此结论是：**跨 Schema 有效性 NOT_EVALUATED，禁止 GLOBAL_VALIDATED。**

## 12. Reader-Page Review

### 做到的部分

- Stage 5 使用真实 Stage 3 输入，Manifest 保存来源哈希；未回写 Canonical/Physical Facts。
- 页面将生命周期入口显式显示为 `CONFIGURATION_SEED｜非证据`，这是正确证据边界。
- 三栏结构可从 Reader 概念进入表达矩阵，再下钻物理字段、表、Assertion、Evidence 和方法。
- 治理队列独立显示 66 Conflict、618 Insufficient Evidence、1326 未发布 source concept、498 未类型化 modifier、361 同名异注释。
- 同一 Reader concept 可被多个阶段引用，而不是复制分片数据。

### 阻止业务使用的缺陷

1. 左栏虽显示配置种子，但六阶段仍被视觉表达为单一生命周期主线，未揭示估值、结算和运营治理的并行/横切关系。
2. 页面只覆盖 5 个 Reader、95 个表达；清算结算和运营治理阶段为空，1326 个 source concept 未挂接，不能证明“承载当前全量字段语义”。
3. 交易对手页把已知错误表达显示为 `SUPPORTED`，一般读者会把错误限定当成可信事实；治理队列没有阻止错误表达进入正文。
4. `交易 / 订单` 的单一 identity 和占位式定义掩盖两个业务对象的边界。
5. 保证金、持仓页面仍混合对象、属性和来源/方向；名义本金的区域挂接与合约经济条款不一致。
6. 治理队列按原因分组是进步，但 `NAVIGATION_CANDIDATE_NOT_PUBLISHED` 尚未进一步拆成范围外、非首批、属性层、证据不足和真正未知。
7. Stage 3 页面存在字符编码/呈现风险的静态迹象，且业务树仍含大量泛化 candidate；本次未做浏览器交互验证，不能宣告可用性通过。

页面模型判定：**REWORK**。信息架构方向可保留，但当前内容不能作为稳定业务导航入口。

## 13. Required Rework

### 决定性缺陷与最小修订动作

1. **先使 Gold Set 成为可执行审阅输入**：只修正自由文本 YAML 引号，不改变案例语义；再用当前冻结输入逐条定位 27 个 case 的实际表达和 Reader 入口。
2. **移除已知错误的 Reader 正文发布**：对 `CTPTY_SHORT_NAME`、`SHORT_NAME`、`CTPTY_LONG_NAME` 禁止由裸英文 token 生成 position_side；列名/注释冲突进入 Conflict。修订后 A01-A04、B01、F01 必须重跑。
3. **拆分 `reader:trade-order`**：创建独立 Order 和 Trade identity；区域可并列展示，字段标识不得跨对象继承。重跑 H01、G02 及所有订单/交易字段。
4. **拆分 SOURCE/TARGET 语义**：业务来源、映射角色和数据侧分别建模；`flow_side` 限定只在明确数据加工语境中启用。重跑 D01-D02、J01-J02。
5. **执行泛化词降级**：`状态/类型/金额/币种/日期/简称/缩写` 从 DOMAIN candidate 发布层移出，保留原始观察和待归类原因。重跑 E01-E04、L01。
6. **收敛轴模型**：删除宽 `DIRECTION`、`CONFIGURATION`、`measure_state` 和 `lifecycle_stage` 重复轴；`attribute_kind:IDENTIFIER` 并入字段属性；保留版本化 TRADEFLOW 专属 `flow_side`。
7. **重画顶层关系**：把运营治理改为横切支撑面；把估值风控、清算结算表示为合同存续中可重复发生的活动/事件链；“合同生命周期”业务区域改为“生命周期事件”对象区域或取消重复轴。
8. **矩阵入口证据化**：31 个入口默认保留为 CONFIGURATION_SEED；第一轮只为实际发布的 Reader 入口补独立 Evidence ID、对象/事件角色和反证。无证据入口不得升级。
9. **重算并改名计数**：将 57 命名为 `direct_attach source concepts`，48 命名为 `likely_concept candidates`，5 命名为 `bounded Reader candidates`；明确 source concept、Reader identity、expression、field instance、physical column、table 的不同分母。
10. **第二 Schema 验证另行授权**：在 D-010 选择 case 后，使用独立 case pack 重跑，不允许为通过而改 TRADEFLOW 专属词法。完成前不声称跨 Schema 可复用已验证。

### 修订后最低再验证集

- Gold Set 全 27 项必须可解析并逐项产生 PASS/FAIL/NOT_EVALUABLE。
- 决定性案例：A01-A04、B01、D01-D02、E01-E04、F01、H01、J01-J02、L01、M01。
- 24 个真实字段样本至少保持本报告的层次判断；任何新自动挂接都要加正例、歧义例和误导名称反例。
- Stage 5 页面不得再把已知错误表达显示为 SUPPORTED；空阶段和配置种子必须继续明确可见。

## 14. Final Boundary Statement

- 本审阅是工程代理执行的独立语义审阅，目标是证伪整合提案。
- 本审阅不代表用户验收。
- 本审阅不代表业务正式确认，也不把测试库元数据当作生产业务真值。
- 本审阅不代表跨 Schema 有效性；第二 Schema 尚未验证。
- 本审阅不授权替换当前字段语义地图入口，不授权自动发布概念、修改正式配置或推进 OpenSpec 任务状态。
- `REWORK` 只说明当前提案存在可具体修订的决定性缺陷；它不否定三栏页面、候选/证据分层和配置种子显式化这些可保留方向。
