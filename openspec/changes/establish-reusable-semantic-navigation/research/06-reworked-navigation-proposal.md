# OTC 衍生品字段语义导航返工提案

> 状态：`REWORKED_CANDIDATE`  
> 范围：业务骨架、五层语义模型、首批 Reader 研究范围  
> 非范围：字段清洗/切词算法、运行时代码、当前配置、正式输出、业务验收、跨 Schema 授权  
> 基线：`05-independent-review.md` 的处置为 `REWORK`；本提案只给出返工后的研究契约，不宣称已修复当前 Stage 3/5 运行结果。

## 1. 结论摘要

原六阶段串行模型不成立。修订后的顶层关系由四类结构组成：交易准备和交易形成是旅程入口；合同存在是承载交易后续状态与义务的包络；估值、风险、保证金、现金流、清算和结算是在包络内可反复发生并互相触发的活动；运营、对账、报表和技术审计是横切支撑面。用户沿入口找概念，但概念身份不因入口不同而复制。

首批 Reader 只保留 6 个身份：`Counterparty`、`Order`、`Trade`、`Notional`、`Position`、`Margin`。它们全部是 `REWORKED_CANDIDATE`，不发布、不继承当前 Stage 5 的 Reader 级 `SUPPORTED`。`reader:trade-order` 被禁止；Order 与 Trade 必须独立。

字段证据准备层是独立上游。当前仓库已有候选设计 `06-field-evidence-preparation-contract.yaml`，但其输出契约仍为 `REQUIRES_IMPLEMENTATION`，也没有经本导航契约验证的规范化观察包。因此本提案的消费规则统一标记 `PENDING_INTEGRATION`。业务骨架只消费规范化字段观察、不可变物理事实、表上下文、证据状态和冲突；token、保护短语或技术字段候选都不能直接决定业务概念、限定条件或 Reader 发布。

## 2. 对 05 十项返工要求的逐项处理

| # | 05 要求 | 06 处理 | 当前边界 |
|---|---|---|---|
| 1 | 27 项 Gold 可解析并可定位 | 新建独立 `06-gold-set.yaml`，保留 A01–M01 全部 27 个 ID；每项记录物理定位、期望层次、当前基线结果和重跑要求 | YAML 可执行输入不等于运行通过 |
| 2 | 删除错误 SHORT/LONG 发布 | 保护 `SHORT_NAME`、`LONG_NAME` 等短语；裸 token 不得产生 `position_side`；名称/注释冲突保留 Conflict | 当前 Stage 5 错误正文仍存在，未改运行产物 |
| 3 | 拆分 Order/Trade | 建立 `reader:order` 与 `reader:trade`，禁止 `reader:trade-order` 和标识跨对象继承 | 全量订单/交易字段仍需重跑 |
| 4 | 拆分 SOURCE/TARGET | 区分业务来源、映射角色和数据侧；`flow_side` 仅限 TRADEFLOW 的明确数据加工语境 | D01、J01、J02 仍需重跑 |
| 5 | 泛化词降级 | 状态、类型、金额、币种、日期、简称、缩写只形成未绑定属性观察，不发布为业务概念 | 原始观察必须保留 |
| 6 | 收敛轴模型 | 删除宽 `DIRECTION`、`CONFIGURATION`、`OPEN`；删除限定词 `measure_state`、`lifecycle_stage`、`attribute_kind` | `flow_side` 保留为版本化 TRADEFLOW 专属限定维度 |
| 7 | 重画顶层关系 | 改为旅程入口 + 合同包络 + 重复活动 + 横切面；取消“合同生命周期”同时充当阶段和区域 | 关系是候选模型，不是业务确认 |
| 8 | 入口证据化 | 原 31 个矩阵单元作为不可发布的 `CONFIGURATION_SEED` 保留；活跃候选只列首批 6 Reader 的 10 个入口 | 配置种子不是 Evidence ID |
| 9 | 统一计数口径 | 分开 source concept、Reader identity、expression、field instance、physical column、table；57 和 48 使用纠正后的名称 | 06 不虚构新表达数或覆盖数 |
| 10 | 第二 Schema 独立授权 | 明确标记 `DEFERRED`，需 D-010、独立 case pack 和独立规则审阅 | 不阻塞 TRADEFLOW 研究返工，也不声称跨 Schema 已验证 |

## 3. 顶层关系模型

```text
旅程入口（常见但非强制统一顺序；箭头表示候选 precedes/produces）
  交易准备
    ~> 询价 / 报价 / 订单
    ~> 执行 / 交易形成
    ~> 合同形成
                |
                v
+---------------------------------------------------------------+
| 合同存在包络                                                  |
| Agreement --governs--> Trade Contract                         |
| Trade Contract --composed_of--> Contract Leg                  |
| Trade Contract/Leg --specified_by--> Economic Terms           |
|                                                               |
| 可重复活动：                                                  |
| 生命周期事件 <-> 持仓/头寸变化                                |
| 估值/风险 <-> 保证金/抵押品                                   |
| 现金流 ~> 结算义务 ~> 清算 ~> 支付/转移或交割 ~> 结算结果     |
+---------------------------------------------------------------+
       ^                     ^                         ^
       | 市场参考/业务配置    | 运营/对账/报表           | 技术加工/审计
       +--------------------- 横切支撑面 ------------------------+
```

`~>` 不是全产品、全事件必经的生命周期顺序，只表示可能的先后或因果关系。既有合同可直接进入修订、终止等事件；估值、风险和保证金可以在现金流前后反复发生；生命周期事件可以不产生结算义务，也可以产生多个义务；失败或部分结算还可回到运营处理。重复活动采用可选、分支、可回入的偏序，而不是单链。

关系边界如下。

- `Agreement`：规定一组交易关系的法律或主协议安排，不等于单笔交易合同，也不等于经济条款集合。
- `Trade Contract`：交易达成并完成合同形成后，对单笔或一组被明确识别交易权利义务的合同身份；它不等于 Order 或 Trade 执行事实。
- `Contract Leg`：Trade Contract 的组成部分，承载一侧现金流、标的、利率或数量安排；腿编号首先标识 Contract Leg，不得被解释成 Notional 的编号。
- `Economic Terms`：约束 Trade Contract/Leg 的数值与条件集合，例如名义本金、期限、价格、频率；不是独立法律主体。
- `Position`：在指定时点、账户/组合和合约范围内的持有记录或数量状态；不等于风险计算结果。
- `Risk Exposure`：由估值、情景、净额或风险方法计算出的风险度量；不与 Position 共用身份。
- `Valuation`、`Margin`、`Collateral`、`Cash Flow` 分别是计量过程、履约保障要求/金额、被提供的资产、预期或已形成的收付义务，不共享概念身份。
- `Clearing` 计算、匹配、净额化或确认结算义务；`Settlement Obligation` 是应收/应付义务；`Payment/Transfer` 是资金或资产转移事件；`Delivery` 是约定标的交付；`Settlement Result` 是履行后的结果记录。一个词出现不能代替整条链。

## 4. 导航树与业务区域

用户界面采用“入口 → 业务区域 → 概念 → 表达 → 物理实现”，入口和区域只是索引，不改变 concept identity。

```text
OTC 衍生品语义导航
├─ 旅程入口
│  ├─ 交易准备
│  ├─ 询价/报价/订单
│  ├─ 执行/交易形成
│  └─ 合同形成
├─ 合同存在包络
│  ├─ 协议、合同与条款
│  ├─ 生命周期事件
│  ├─ 持仓与风险
│  ├─ 估值
│  ├─ 保证金与抵押品
│  └─ 现金流、清算与结算
└─ 横切支撑面
   ├─ 市场参考与业务配置
   ├─ 运营、对账与报表
   └─ 技术加工与审计
```

业务区域不机械维持十个，修订为 13 个边界清晰的候选区域：

| 区域 ID | 定义与包含 | 明确排除 | 对象/事件/关系 | TRADEFLOW 证据边界 | Reader 资格 |
|---|---|---|---|---|---|
| `area:parties-relations` | 法律实体、客户关系、交易对手关系、机构及人员 | 买卖方向、源/目标数据侧、纯名称形态 | Party；Customer/Counterparty relation；准入关系 | 对手方 ID/名称提供字段支持，但 Customer 边界仍有反证 | Counterparty 可候选；Customer 延后 |
| `area:products-underlyings` | 产品定义、产品实例、标的及二者关系 | 单笔合同条款、行情值本身 | Product、Underlying、references | 字段语料存在，但未完成稳定身份裁定 | 延后 |
| `area:inquiry-quote-order-trade` | 交易意向到执行事实 | 合同法律身份、持仓、后续结算结果 | Inquiry、Quote、Order、Trade；precedes/executes | Order/Trade 标识可区分，现 Reader 合并是反证 | Order、Trade 可候选 |
| `area:agreements-contracts-terms` | 主协议、交易合同、合约腿、经济条款 | 生命周期事件、运营批次 | Agreement、Trade Contract、Contract Leg、Economic Terms | 合同/腿/名义本金字段只提供候选锚点 | Notional 可候选；其余延后 |
| `area:lifecycle-events` | 重置、行权、修订、增减、终止等事件 | “当前/初始”等时间限定词 | Lifecycle Event；changes contract/position | 当前 Stage 5 没有 BUSINESS_EVENT 入口 | 延后 |
| `area:positions-risk` | 持仓记录、头寸视图、风险敞口及控制 | 订单数量、技术同步计数 | Position、Position View、Risk Exposure | 持仓数量有证据；同步总数是反例 | Position 可候选；头寸/敞口延后 |
| `area:valuation` | 估值过程、估值输入和结果 | 保证金、现金流、市场参考身份 | Valuation；values contract/position | 表名和来源字段不足以确认估值含义 | 延后 |
| `area:margin-collateral` | 保证金要求、金额、状态及抵押品提供 | 估值结果、一般金额字段 | Margin、Collateral；secures obligation | Margin 有当前 Reader；Collateral 冲突仍在治理队列 | Margin 可候选；Collateral 延后 |
| `area:cashflow-clearing-settlement` | 现金流、义务、清算、支付/转移、交割和结果 | 仅含“结算”字样的技术任务 | Cash Flow、Settlement Obligation、Clearing、Payment/Transfer、Delivery、Settlement Result | 当前两个旧阶段为空，不能推断已覆盖 | 全部延后 |
| `area:market-reference` | 市场、曲线、汇率、日历等外部业务参考 | 数据来源 token、ETL 来源 | Market Reference；prices/observes | `VALUATION_RATE_SOURCE_ID` 仅是定位线索 | 延后 |
| `area:business-configuration` | 明确改变业务处理的参数、规则和映射 | 任意 TYPE/FLAG、技术配置 | Business Rule/Mapping；governs | 映射表提供上下文，不自动产生方向 | 延后 |
| `area:operations-reconciliation-reporting` | 运营任务、对账、报表、监管报送 | 业务概念本体、技术审计字段 | Operational Process；reconciles/reports | 作为横切入口，不作为字段投票器 | 不进入首批 Reader |
| `area:technical-processing-audit` | 批次、同步、加工血缘、创建更新审计 | 客户、交易、合同等业务对象 | Processing/Audit observation | 技术字段候选必须隔离 | 不具备业务 Reader 资格 |

## 5. 五层语义模型

| 层 | 名称 | 职责 | 允许的判断 | 禁止的越级 |
|---|---|---|---|---|
| A | 业务概念 | 稳定识别对象、事件、过程、度量、控制或关系 | `concept:counterparty`、`concept:notional` | 由单个 token、表名或字段数投票生成概念 |
| B | 属性表达 | 记录某概念在业务语境中的具体表达 | “交易对手短名”“空头动态名义本金（结算币种）” | 将表达变体复制成新概念身份 |
| C | 字段属性 | 跨概念复用的属性形态 | `IDENTIFIER`、`MEASURE`、`TIME` | 用宽 `DIRECTION`/`CONFIGURATION` 包揽不同含义 |
| D | 限定条件 | 对 B/C 的正交限定，不改变 A 的身份 | `position_side=SHORT`、`currency_basis=SETTLEMENT` | 复制 `lifecycle_stage` 或用限定词决定 Reader |
| E | 物理实现 | Schema/Table/Column 事实、注释、类型和证据定位 | 一个表达对应多个字段实现；冲突并存 | 覆盖原始字段名/注释或把同名列合并为一个实例 |

示例：`concept:notional`（A）→“空头动态名义本金（结算币种）”（B）→`MEASURE`（C）→`position_side=SHORT`、`variability=DYNAMIC`、`currency_basis=SETTLEMENT`（D）→ `TITANS_TRADEFLOW.REF_FAST_TRS.SHORT_DYNAMIC_NOTIONAL`（E）。任何一层的候选状态都不能自动升级另一层。

## 6. 22 个核心概念审阅表

| 概念 ID / 中文 | 稳定定义 | 排除边界 | 类型 | 主要导航入口 | Reader 决定 | 当前证据边界 |
|---|---|---|---|---|---|---|
| `concept:customer` 客户 | 与本机构存在服务、准入或账户关系的 Party-in-relation | 不默认等于交易合同对手方 | 关系 | 交易准备；参与主体 | `DEFERRED` | “客户短名”不足以把 Customer 归并 Counterparty |
| `concept:counterparty` 交易对手 | 在协议、订单或交易关系中承担对手方角色的 Party-in-relation | 不等于客户，不等于独立法人主数据本身 | 关系 | 交易准备；交易形成；合同包络 | `REWORKED_CANDIDATE` | ID/名称字段支持；SHORT/LONG 当前有错误限定 |
| `concept:product` 产品 | 定义可交易经济结构和规则的产品类别/实例 | 不等于单笔交易合同 | 对象 | 交易准备；产品与标的 | `DEFERRED` | 当前字段锚点未完成身份审阅 |
| `concept:underlying` 标的 | 决定衍生价值或交付内容的资产、指数或参考项 | 不等于产品、行情值或估值结果 | 对象 | 产品与标的；合同条款 | `DEFERRED` | 跨产品线歧义未裁定 |
| `concept:inquiry` 询价 | 发起获取可交易条件的信息请求 | 不等于 Order 或已执行 Trade | 事件 | 询价/报价/订单 | `DEFERRED` | 未形成稳定 Reader 证据链 |
| `concept:quote` 报价 | 针对询价或市场意图给出的价格/条款提议 | 不等于 Order、Trade 或 Valuation | 对象 | 询价/报价/订单 | `DEFERRED` | 报价与估值/价格字段需消歧 |
| `concept:order` 订单 | 指示拟执行交易的意图或指令，可撤销、拒绝或未成交 | 不等于成交后的 Trade | 对象 | 询价/报价/订单；交易形成 | `REWORKED_CANDIDATE` | `KEY_STOCK_ORDER_ID` 是独立标识反例 |
| `concept:trade` 交易 | 已执行并形成经济事实的交易记录 | 不等于 Order 或法律 Trade Contract | 对象 | 执行/交易形成 | `REWORKED_CANDIDATE` | 交易 ID 与订单 ID 不得继承 |
| `concept:trade-contract` 合约 | 合同形成后承载一笔或一组交易权利义务的合同身份 | 不等于主协议、Trade 执行事实或条款集合 | 对象 | 合同形成；合同包络 | `DEFERRED` | Agreement/Contract 分界需业务材料 |
| `concept:contract-leg` 合约腿 | 合约中具有独立付款、标的或计算安排的组成部分 | 不等于 Notional 或腿编号属性 | 对象 | 合同包络；协议合同条款 | `DEFERRED` | 腿字段可定位，关系未审阅 |
| `concept:economic-terms` 经济条款 | 约束合同/腿经济结果的条件集合 | 不等于合同法律身份 | 控制 | 合同包络；协议合同条款 | `DEFERRED` | 仅作为组织层候选 |
| `concept:position` 持仓 | 指定时点、范围和口径下的持有记录/数量状态 | 不等于订单数量、同步任务数或 Risk Exposure | 对象 | 合同包络；持仓风险；估值风险 | `REWORKED_CANDIDATE` | `持仓数量`存在多物理实现；表数须去重 |
| `concept:position-view` 头寸 | 对持仓按账户、组合、方向或净额口径形成的业务视图/度量 | 不默认与底层 Position 同身份 | 度量 | 持仓风险 | `DEFERRED` | 中文术语易与持仓混用，需业务裁定 |
| `concept:notional` 名义本金 | 用于计算现金流、风险或条款规模的合同度量基准 | 不等于实际持仓、保证金或支付金额 | 度量 | 合同条款；估值风险 | `REWORKED_CANDIDATE` | 初始/动态/币种/方向表达有字段支持 |
| `concept:valuation` 估值 | 在给定时点和方法下计算合同/持仓价值的过程 | 不等于估值输入、价格、风险敞口或保证金 | 过程 | 估值；合同包络 | `DEFERRED` | 来源字段不能单独确认过程 |
| `concept:risk-exposure` 风险敞口 | 基于风险方法、情景或净额计算的潜在损失/敏感度度量 | 不等于 Position 或 Notional | 度量 | 持仓风险；估值风险 | `DEFERRED` | 当前无首批独立证据链 |
| `concept:margin` 保证金 | 为覆盖履约风险而计算、要求或记录的保证金额度/状态 | 不等于 Collateral 资产、Valuation 或一般金额 | 度量 | 保证金抵押品；估值风险 | `REWORKED_CANDIDATE` | `MARGIN_DIRECTION` 方向仍未解析 |
| `concept:collateral` 抵押品 | 为满足保证金或信用支持义务而提供/占用的资产 | 不等于 Margin 金额 | 对象 | 保证金抵押品；结算 | `DEFERRED` | 相关名义本金币种存在 Conflict，不能补造实体 |
| `concept:cash-flow` 现金流 | 由合同条款或事件产生的计划/实际收付义务记录 | 不等于支付事件或结算结果 | 对象 | 合同包络；现金流结算 | `DEFERRED` | 当前 Reader 阶段为空且语料碎片化 |
| `concept:delivery` 交割 | 按义务交付约定资产/标的的履行动作 | 不等于 Clearing 或结果状态 | 事件 | 支付/转移/交割 | `DEFERRED` | “交割”词不足以确认义务链 |
| `concept:clearing` 清算 | 对交易义务进行确认、匹配、净额化或形成结算指令的过程 | 不等于支付、交割或结算结果 | 过程 | 清算；现金流结算 | `DEFERRED` | 当前清算阶段无 Reader，不得宣称覆盖 |
| `concept:settlement-result` 结算结果 | 对结算义务履行成功、失败、部分完成等结果的记录 | 不等于 Cash Flow、义务或操作任务状态 | 对象 | 支付/转移/交割；结算结果 | `DEFERRED` | 需区分业务结果与技术任务状态 |

补充身份 `concept:agreement`、`concept:settlement-obligation`、`concept:payment-transfer` 用于关系模型完整性，但不增加到本轮 22 个审阅对象和首批 Reader 范围。

## 7. 首批 Reader 范围与排除

| Reader ID | 概念 | 状态 | 纳入理由 | 本轮明确排除 | 发布门槛 |
|---|---|---|---|---|---|
| `reader:counterparty` | Counterparty | `REWORKED_CANDIDATE` | 已有物理 ID/名称证据和当前 Reader 投影 | Customer 合并；SHORT/LONG 方向；SOURCE/TARGET 角色 | 字段证据接口集成、冲突清零或显式展示、Gold 重跑 |
| `reader:order` | Order | `REWORKED_CANDIDATE` | 有订单业务主键反例可建立独立身份 | Trade 字段和成交事实 | 全量订单/交易标识消歧 |
| `reader:trade` | Trade | `REWORKED_CANDIDATE` | 有独立 Trade ID 与执行事实 | Order、Trade Contract | 全量订单/交易标识消歧 |
| `reader:notional` | Notional | `REWORKED_CANDIDATE` | 初始、动态、币种及 position side 表达有证据 | 持仓、抵押品名义本金冲突 | 表达级证据，不继承 Reader 级 SUPPORTED |
| `reader:position` | Position | `REWORKED_CANDIDATE` | 当前持仓数量和字段族可作为有界入口 | 订单数量、任务同步计数、Risk Exposure、头寸术语自动合并 | 实例/表计数去重和上下文复核 |
| `reader:margin` | Margin | `REWORKED_CANDIDATE` | 当前有保证金候选表达 | Collateral、一般金额、未解析方向 | M01 方向取得值语义或保持未解析 |

禁止出现 `reader:trade-order`。Customer、Product、Underlying、Inquiry、Quote、Trade Contract、Contract Leg、Economic Terms、Position View、Valuation、Risk Exposure、Collateral、Cash Flow、Delivery、Clearing、Settlement Result 均为 `DEFERRED`，不能为了覆盖 22 个概念而发布。

## 8. 字段属性轴

| ID | 定义 | 正例 | 反例/排除 | 范围 |
|---|---|---|---|---|
| `IDENTIFIER` | 在明确对象语境内标识实例的字段形态 | Order ID、Trade ID、Counterparty ID | 裸 ID、UUID、批次号不形成业务概念 | 跨 Schema 候选 |
| `DESCRIPTIVE_TEXT` | 名称、简称、描述、备注等可读表达 | 交易对手短名、合约描述 | “简称”不能独立升概念；SHORT 不代表空头 | 跨 Schema 候选 |
| `PARTY_RELATIONSHIP` | 明确描述 Party 与交易/协议/机构之间关系的字段形态 | 客户关系、交易对手关系 | SOURCE/TARGET、BUY/SELL、INTERNAL 技术来源不自动进入 | 跨 Schema 候选 |
| `BUSINESS_OBJECT_STATE` | 绑定到特定业务对象的状态字段 | `Order.status`、`SettlementResult.status` | 裸“状态”或作业状态不能跨对象合并 | 跨 Schema 候选 |
| `MEASURE` | 数量、金额、比率等可计算度量 | Notional、Position quantity、Margin amount | 裸金额/数量不产生对象锚点 | 跨 Schema 候选 |
| `CURRENCY` | 币种身份或币种基准属性 | 结算币种、原币 | 裸“币种”不是业务概念 | 跨 Schema 候选 |
| `TIME` | 业务日期、时点、区间或期限 | 生效日、计息区间 | 创建/更新时间优先进入 AUDIT | 跨 Schema 候选 |
| `AUDIT` | 创建、修改、版本、批次和处理追踪形态 | CREATED_BY、UPDATED_DATETIME | 不因与交易表共表而变成业务对象 | 跨 Schema 候选 |

删除 `DIRECTION`、`CONFIGURATION`、`OPEN`。技术字段候选是字段证据准备层的观察状态，不是第九个业务属性轴。

## 9. 限定条件注册表

| ID | 定义/允许值 | 适用层 | 明确排除 | 适用性 | 正例 | 反例 |
|---|---|---|---|---|---|---|
| `observation_time_role` | `INITIAL/CURRENT/END/BEFORE_ADJUSTMENT/AFTER_ADJUSTMENT` | B/D | 不表示生命周期阶段 | 跨 Schema 候选 | 初始名义本金 | CREATED_DATETIME |
| `position_side` | `LONG/SHORT`，持仓方向 | B/D | 名称长短、文本长度、买卖方向 | 跨 Schema 候选 | 空头动态名义本金 | CTPTY_SHORT_NAME |
| `trade_side` | `BUY/SELL`，交易买卖侧 | B/D | Position long/short、Party source/target | 跨 Schema 候选 | 买入数量、卖方 | SHORT_POSITION |
| `cashflow_direction` | `PAY/RECEIVE`，经济收付方向 | B/D | 保证金“方向”无值语义时不得猜测 | 跨 Schema 候选 | 保证金支付方向 | MARGIN_DIRECTION 单独出现 |
| `currency_basis` | `ORIGINAL/LOCAL/UNDERLYING/SETTLEMENT` | B/D | 币种代码本身、来源系统 | 跨 Schema 候选 | 结算币种动态名义本金 | CURRENCY 无上下文 |
| `party_relationship_role` | `CUSTOMER/COUNTERPARTY/INTERNAL_PARTY/EXTERNAL_PARTY` | B/D | BUY/SELL、SOURCE/TARGET、LONG/SHORT | 跨 Schema 候选 | 合同交易对手 | TARGET_CTPTY_ID 的裸 TARGET |
| `variability` | `DYNAMIC/FIXED` | B/D | 当前/历史、初始/期末 | 跨 Schema 候选 | 动态名义本金 | 当前名义本金 |
| `aggregation_state` | `ACCUMULATED/NET/GROSS` | B/D | 未证明的表级汇总推断 | `DEFERRED` | 注释明确“汇总前/求和” | 字段名含 TOTAL 即认定 |
| `availability_condition` | `AVAILABLE/FROZEN` | B/D | 对象生命周期状态 | 跨 Schema 候选 | 可用保证金 | 任务冻结状态 |
| `estimation_status` | `ESTIMATED/OBSERVED` | B/D | SUPPORTED/PROVISIONAL 证据状态 | 跨 Schema 候选 | 估算现金流 | Reader SUPPORTED |
| `measure_basis` | `ABSOLUTE/RATIO/PERCENTAGE` | B/D | measure_state | 跨 Schema 候选 | 内在价值系数 | “金额”裸词 |
| `flow_side` | `SOURCE/TARGET`，仅表示明确数据加工/映射的数据侧 | B/D | 业务来源、事件来源、估值来源、交易对手关系 | `TRADEFLOW_ONLY` | 明确源侧映射输入 | 事件来源类型、目标交易对手 |

拒绝 `lifecycle_stage`、`measure_state`、`attribute_kind`。`IDENTIFIER` 已属于 C 层；生命周期位置属于导航关系；二者都不得作为 D 层重复编码。

## 10. 误分类禁令与不可判定处理

| 触发 | 禁止动作 | 必需上下文 | 正确归宿 | 仍不可判定时 |
|---|---|---|---|---|
| `SHORT/LONG` 出现在 `SHORT_NAME/LONG_NAME` | 生成 `position_side` | 完整保护短语、字段注释、对象上下文 | B 层名称表达 + `DESCRIPTIVE_TEXT` | `UNRESOLVED_OBSERVATION`，阻止发布 |
| `SOURCE/TARGET` | 一律生成 `flow_side` | 是否为明确数据加工/映射数据侧 | 业务来源、映射角色或 TRADEFLOW-only `flow_side` | 保留候选解释和 Conflict |
| 状态/类型/金额/币种/日期/简称/缩写 | 作为独立 A 层概念 | 同字段的对象锚点 | C 层属性或未绑定观察 | `UNBOUND_ATTRIBUTE_OBSERVATION` |
| Order/Trade 同表或同名 ID | 合并身份或互相继承标识 | 业务事件、主键职责、表注释 | `concept:order` 或 `concept:trade` | 不进入任一 Reader |
| Customer/Counterparty | 默认同义 | 关系对象、准入/合同语境 | 两个 Party relation 身份 | `CONFLICT` 或 `DEFERRED` |
| Position/头寸/Risk Exposure | 作为同一对象 | 时点、聚合口径、风险方法 | Position、Position View、Risk Exposure | `DEFERRED` |
| Valuation/Margin/Collateral/Cash Flow | 共享一个概念身份 | 过程、度量、资产、义务关系 | 四个独立概念 | 阻止 Reader 继承 |
| Agreement/Trade Contract/Leg/Terms | 只凭“合同/合约”合并 | 法律层级、组成关系、承载字段 | 四层身份与关系 | `DEFERRED` |
| Clearing/Obligation/Payment/Delivery/Result | 用“结算”覆盖整条链 | 输入义务、动作、资产类型、结果 | 对应过程/对象/事件 | `DEFERRED` |
| CREATED/UPDATED/BATCH/PUSH/UUID | 发布为业务概念 | 原始字段、数据类型、处理上下文 | AUDIT/技术字段候选 | 隔离，不丢弃 |
| 字段名与注释冲突 | 设固定优先级并覆盖一侧 | 两侧原文、表上下文、独立证据 | Conflict + 并列解释 | 禁止 Reader 发布 |
| 表名或 sibling token 多数 | 给字段“投票”成概念 | 可定位的字段级支持/反证 | 只作 CONTEXT_ONLY | 保持 Unknown/未解析 |

## 11. 多入口模型

原 31 个“区域 × 六阶段”单元必须保留为迁移审计记录，全部降为 `CONFIGURATION_SEED`，不得继续显示为已证实入口。它们位于 YAML 的 `legacy_configuration_seeds`，不计入首批 Reader 条目。

首批只保留以下 10 个“指向真实首批 Reader identity 的未发布候选入口”。这里的“真实”只表示目标是本轮 6 个有界 Reader identity，不表示入口关系已经被证据证明或已经发布。YAML 使用 `candidate_reader_entries`，每项共用同一 Reader/concept identity；`placement_basis` 均为 `CONFIGURATION_SEED`、`evidence_id=null`、`publication_status=NOT_PUBLISHED`，因为现有字段证据不能证明导航位置关系。

| Entry ID | Reader | 导航入口 | 角色/关系 | 反证或限制 | 状态 |
|---|---|---|---|---|---|
| `entry:counterparty:trade-preparation` | `reader:counterparty` | 交易准备 | RELATION / participates_in eligibility | Customer 不默认等同 | `REWORKED_CANDIDATE` |
| `entry:counterparty:trade-formation` | `reader:counterparty` | 执行/交易形成 | RELATION / counterparty_to trade | SOURCE/TARGET 不作 party role | `REWORKED_CANDIDATE` |
| `entry:order:order-intent` | `reader:order` | 询价/报价/订单 | OBJECT / records instruction | 不继承 Trade ID | `REWORKED_CANDIDATE` |
| `entry:trade:trade-formation` | `reader:trade` | 执行/交易形成 | OBJECT / records execution | 不继承 Order ID | `REWORKED_CANDIDATE` |
| `entry:notional:contract-terms` | `reader:notional` | 合同存在包络 | MEASURE / specifies contract | 不是 Position 或支付金额 | `REWORKED_CANDIDATE` |
| `entry:notional:valuation-risk` | `reader:notional` | 估值/风险重复活动 | MEASURE / calculation_basis_for | 入口不复制概念 | `REWORKED_CANDIDATE` |
| `entry:position:contract-envelope` | `reader:position` | 合同存在包络 | OBJECT / position_of contract | 头寸视图另行裁定 | `REWORKED_CANDIDATE` |
| `entry:position:valuation-risk` | `reader:position` | 估值/风险重复活动 | OBJECT / input_to valuation | 风险敞口不是 Position | `REWORKED_CANDIDATE` |
| `entry:margin:margin-collateral` | `reader:margin` | 保证金/抵押品重复活动 | MEASURE / secures obligation | Collateral 资产不继承身份 | `REWORKED_CANDIDATE` |
| `entry:margin:valuation-risk` | `reader:margin` | 估值/风险重复活动 | MEASURE / derived_from exposure | MARGIN_DIRECTION 仍未解析 | `REWORKED_CANDIDATE` |

任何入口在具备独立 Evidence ID 前不得升级。物理字段证据支持概念或表达，不自动支持 `participates_in`、`calculation_basis_for` 等导航关系。

## 12. 计数口径

| 名称 | 数值 | 分母/含义 | 禁止解释 |
|---|---:|---|---|
| TRADEFLOW physical columns | 13,611 | Stage 0 的物理列实例 | 不是概念数，也不是 Reader 字段数 |
| TRADEFLOW physical tables | 477 | Stage 0 表实例 | 不等于候选覆盖表 |
| source concept candidates | 1,375 | Stage 3 run-scoped 源概念候选 | 不是已确认概念 |
| attribute expressions | 1,559 | Stage 3 属性表达候选 | 不能与 concept identity 相加 |
| semantic observations | 5,347 | 观察记录；其中 5,342 个唯一字段实例 | 不等于物理列总数 |
| candidate-linked field instances | 4,294 | 被候选表达引用的唯一字段实例 | 不等于 source_field_count |
| source fields | 5,512 | Stage 3 manifest 的输入字段口径 | 不等于全 Schema 物理列 |
| candidate-covered tables | 233 / 477 | 至少一个候选字段引用的表 | 不表示整表语义已确认 |
| direct_attach source concepts | 57 | 02 分类中的源概念候选类别 | 不是 57 个对象，也不是 Reader 数 |
| likely_concept candidates | 48 | 未分类分析中的调查候选 | 不能称“48 个真概念” |
| current bounded Reader identities | 5 | 当前 Stage 5 投影 | 含错误合并 `reader:trade-order` |
| proposed first Reader identities | 6 | 本提案有界身份数 | 尚无新运行表达/字段覆盖数 |
| current Reader expressions | 95 | 当前 5 Reader 的表达；48 SUPPORTED / 47 PROVISIONAL | Reader 级 SUPPORTED 不能向下继承 |
| navigation-unattached source concepts | 1,326 | Stage 5 未发布到五个 Reader 的源概念 | 不等于 Unknown，也不与 6 相加 |
| insufficient hypotheses | 618 | Stage 3/5 假设粒度 | 不等于 02 分类中的 2 个 insufficient source concepts |
| out-of-scope count | `NOT_COMPUTED` | 本研究未建立排除全集 | 不得用 1,326 代替 |
| true Unknown count | `NOT_COMPUTED` | 未建立统一 Unknown 粒度 | 不得用未发布或证据不足代替 |

当前 Stage 5 基于非 replay 的 Stage 3 bundle；06 不把不同 run 的计数混合为一个基线。

## 13. Gold Set 设计

`06-gold-set.yaml` 是新的可解析回归输入，不覆盖 `03-gold-set.yaml`。它保留 27 个 case ID，并为每项固定：物理字段身份、表上下文、基础概念、字段属性、限定条件、禁止推断、Reader identity、证据要求、当前 05 基线结果和重跑状态。24 项已用冻结 Stage 0 的 Schema/Table/Column 定位；E02–E04 仍是无单字段定位的聚合例，明确 `NOT_EVALUABLE`。新增定位使用真实 `TRD_FAST_TRS_FEE.AUDIT_STATUS` 作为 E01 的“状态”反例，没有伪造第 28 个 case。

关键修订：

- C02 以冻结物理注释中的“结算币种”为准，期望 `currency_basis=SETTLEMENT`，同时保留旧 Gold 冲突说明。
- C03 的基础概念候选观察改为“内在价值系数”，保留 `position_side=SHORT`；该观察不是新概念身份，也不把表归属自动提升为 Margin Reader。
- F01 保留字段名 SHORT 与注释“多头”的冲突，禁止自动优先级和 Reader 发布。
- H01 只允许 `reader:order`，用来阻止 Order/Trade 合并。
- D01/J01/J02 禁止业务/映射“来源、目标”进入 `flow_side`；D02 只有在明确数据侧映射语境下才允许 TRADEFLOW-only `flow_side=SOURCE`。
- E01 使用冻结输入中的真实 `AUDIT_STATUS/状态` 作为可定位反例；E02–E04 无法定位单字段，明确为 `NOT_EVALUABLE`。

其中 E01 已在冻结输入中定位为 `TRD_FAST_TRS_FEE.AUDIT_STATUS`，因此仅 E02–E04 保持 `NOT_EVALUABLE`。C03、C04、G02、J01、J02 的未裁定基础语义进入 `candidate_observation_registry`，其 ID 是 A 层之前的观察 ID，不计入 22 个概念、不能进入 Reader。

05 第 1 项“只修 YAML 引号、不改变语义”用于重建原 03 历史基线；本文件不修改 03。用户随后明确要求 06 修正 Gold 自身的方向矛盾和冻结描述不一致，因此 C02/C03 在 06 中采用“`legacy_oracle` 原样保留 + `expected_after_rework` 候选修正”的双记录方式。修正不是对历史结果的追认，仍须重跑和独立审阅。

05 的现行结果 `PASS=6 / FAIL=17 / NOT_EVALUABLE=4` 作为历史基线保留，不能因 Gold 文件已修正就改写成通过。修订后的运行结果为 `PENDING_RERUN`。

## 14. 单页 Reader 概念图

```text
+---------------------------+--------------------------------+------------------------------------+
| 左栏：业务入口            | 中栏：概念与表达              | 右栏：物理事实与证据               |
|                           |                                |                                    |
| 旅程入口                  | Reader identity               | 物理字段名                         |
| - 交易准备                | - Counterparty                | 实现数量 / 去重表数量              |
| - 询价/报价/订单          | - Order                       | Schema                             |
| - 执行/交易形成           | - Trade                       | Table / 表注释                     |
| - 合同形成                | - Notional                    | Column / 字段注释                  |
|                           | - Position                    | Data type                          |
| 合同存在包络              | - Margin                      | Evidence state / Conflict          |
| - 生命周期事件            |                                | [表详情] -> Stage 0 object page     |
| - 估值/风险               | 属性表达                       |                                    |
| - 保证金/抵押品           | 字段属性 + 限定条件            | 原始事实不可覆盖                   |
| - 现金流/清算/结算        | 反证 + 候选状态                | 未发布/未知/范围外分开显示          |
|                           |                                |                                    |
| 横切：参考/配置、运营、   | 同一概念可显示多个入口，       | 配置种子明确标为非证据             |
| 对账/报表、技术/审计      | 但只保留一个 concept identity  |                                    |
+---------------------------+--------------------------------+------------------------------------+
```

用户路径：先沿旅程或重复活动找到业务区域；再选择唯一概念身份；中栏比较属性表达及限定；右栏查看物理字段名、实现数、去重表数、Schema、表名/表注释、字段注释、数据类型、证据状态和冲突；最后通过表详情链接回到当前 Stage 0 物理对象页。单页不得把空区域隐藏，也不得把配置种子渲染成证据支持。

## 15. TRADEFLOW 与跨 Schema 边界

- 本轮深层语义范围仍是 `TITANS_TRADEFLOW`；Panorama 的其他 Schema 只能提供物理导航，不继承本轮概念标签。
- `flow_side` 明确为 `TRADEFLOW_ONLY`，需要显式数据加工/映射上下文。其他限定和属性轴最多是跨 Schema 候选，不是已验证通用规则。
- 第二 Schema 选择属于 D-010 用户决策，需要独立 case pack、独立 Gold、独立反例和独立运行；状态 `DEFERRED`。
- 第二 Schema 尚未授权不会阻塞本次 TRADEFLOW 提案，但会阻止“可复用已验证”“跨 Schema 成立”和规模授权等表述。
- 不允许为让第二 Schema 通过而修改 TRADEFLOW 专属词法，也不允许把 TRADEFLOW 的 Wiki/表名种子复制成跨 Schema 证据。

## 16. 实施前置条件与字段证据输入接口

### 16.1 消费边界

业务骨架只接受以下五类输入：

1. `normalized_field_observations`：规范化 token、保护短语、缩写/泛化词/候选限定观察；均为观察，不是语义裁定。
2. `raw_physical_facts`：不可变的 Schema/Table/Column identity、原始字段名、原始字段注释和数据类型。
3. `table_context`：表名、表注释、对象类型及可定位来源；只作上下文证据。
4. `evidence_state`：SUPPORT、CONTRADICT、CONTEXT_ONLY、NOT_OBSERVED 等可追溯状态。
5. `conflicts_and_unresolved`：字段名/注释冲突、候选解释、所需下一证据和未解析观察。

最小接口必须保留：

- `schema_name`、`table_name`、`column_name` 组成的 Schema/Table/Column identity，以及稳定 `physical_column_id`；
- `raw_column_name`、`raw_column_comment`；
- `raw_table_name`、`raw_table_comment`；
- `data_type`；
- `normalized_tokens`；
- `protected_phrases`；
- `technical_field_candidates`；
- `name_comment_conflicts`；
- `unresolved_observations`；
- 每个派生观察的 source span、rule ID、provenance 和 evidence state。

上游可以输出 `candidate_qualifier_observations`，但必须标为 `SEMANTIC_LAYER_REQUIRED`。切词、短语命中、缩写展开、表名命中、技术字段候选或字段数都不得直接写入 A 层概念、D 层正式限定或 Reader 发布状态。本提案不设计字符规范化、切词、短语匹配或冲突自动消解算法。

### 16.2 当前集成状态

`06-field-evidence-preparation-contract.yaml` 是候选 provider contract，且声明不输出正式概念/Reader；其 output 仍是 `REQUIRES_IMPLEMENTATION`。本导航骨架没有消费过可复现输出包，也未验证字段覆盖、冲突保留和 provenance。因此：

- `field_evidence_provider_status = CANDIDATE_CONTRACT_OBSERVED`
- `field_evidence_integration_status = PENDING_INTEGRATION`
- 所有依赖规范化观察的规则状态 = `PENDING_INTEGRATION`
- 所有首批 Reader 的 publication gate = `BLOCKED_PENDING_INTEGRATION`

provider 设计文件出现不等于“字段证据已准备完成”，更不等于已解决 SHORT/LONG、SOURCE/TARGET 或泛化词问题。

### 16.3 其他实现前置条件

- 明确区分当前 CONFIG 输入 `reusable-semantic-navigation-v1`、目标 result bundle schema 同名冲突，以及现行 Stage 5 `semantic-navigation-reader-v1` / `semantic-navigation-review-manifest-v1`；实现前必须消除契约名碰撞。
- 用修订 Gold 全 27 项重跑，并输出逐项 PASS/FAIL/NOT_EVALUABLE；失败和未定位不得被跳过。
- Reader 支持状态按表达和物理证据计算；Reader 只因任一 source concept 被支持而显示 SUPPORTED 的现行聚合规则不得作为发布依据。
- 对用户可见页面执行独立反例审阅；工程 Gate 通过、YAML 解析或页面生成均不等于 reader delivery 或 business acceptance。
- 不修改当前 cases/config、Stage 3/5 输出或代码，直到另有实施授权。

## 17. 开放问题与 DEFER

| 问题 | 状态 | 需要的最小下一证据/决策 |
|---|---|---|
| 字段证据准备层的可复现输出和消费适配 | `PENDING_INTEGRATION` | 版本化输出包、schema validation、覆盖/冲突/provenance 抽查 |
| 第二 Schema 选择与验证 | `DEFERRED` | D-010 用户授权 + 独立 case pack |
| Customer 与 Counterparty 的业务关系边界 | `DEFERRED` | 准入、账户、合同关系材料；A03 人工裁定 |
| Agreement 与 Trade Contract 法律层级 | `DEFERRED` | 可定位 Wiki/业务规则与合同对象职责 |
| Position 与“头寸”是否需要独立身份 | `DEFERRED` | 聚合口径、净额、账户/组合上下文样本 |
| `MARGIN_DIRECTION` 的收付值域 | `DEFERRED` | 枚举/业务规则/可定位值语义；不查询业务行 |
| 31 个旧矩阵 seed 的迁移/删除 | `DEFERRED` | 逐入口证据审阅；没有 Evidence ID 不升级 |
| 目标 result bundle 与当前 Stage 5 契约命名碰撞 | `DEFERRED` | 实施设计时确定唯一 schema ID 和迁移路径 |
| Gold 的业务权威性 | `DEFERRED` | 用户/领域审阅；本文件不自授 Gold authority |
| Reader 发布、业务验收、规模授权 | `DEFERRED` | 实现、重跑、独立审阅、用户决策分别完成 |

本提案的最高结论是“研究返工候选已形成”。它不改变 `reader_delivery=NOT_DELIVERED`、`business_acceptance=NOT_ACCEPTED` 或 `scale_authorization=PROHIBITED` 的当前边界。
