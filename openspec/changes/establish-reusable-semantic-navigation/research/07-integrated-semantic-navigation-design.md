# OTC 字段语义导航端到端整合设计

> 状态：`REWORKED_INTEGRATED_RESEARCH_CANDIDATE`；范围：`TITANS_TRADEFLOW`；日期：2026-08-14。本文只整合研究契约，不实现 Provider，不修改现行 Stage 3/5、正式配置、OpenSpec 状态或 Git 状态。`09-independent-preimplementation-review.md` 第 1 轮实施前复审处置为 `REWORK`；本次只闭合其指定的契约缺口，不自行产生 `ACCEPT`。

## 1. 整合结论

Agent A 的业务导航骨架与 Agent B 的字段证据准备层可以接成一条可实现链路，但不能直接拼接字段，也不能把准备层 observation 当作业务决定。统一链路是：

```text
P0 Physical Fact
  -> P1 Prepared Evidence
  -> P2 Semantic Adjudication Candidate
  -> P3 Semantic Decision
  -> P4 Reader Candidate
  -> P5 Reader Projection
  -> governance queue / usability validation / independent review
```

整合后的关键裁定如下：

1. Agent B 的 Evidence Pack 是 Agent A 的唯一字段级输入；P1→P2 适配器按 `physical_column_id` 逐实例消费，并保留所有来源、Conflict 和 unresolved。
2. 只有原值保存、物理 identity、来源 hash、非破坏性规范化、切词、保护短语和同名实例隔离可以确定执行。
3. 对象、属性表达、正式字段属性、qualifier 与 Reader 归属只能形成候选并进入语义裁定；裸 token 永远不能越级。
4. identity 未决、名称/注释冲突、限定冲突、技术候选未隔离、决定性 Gold 未满足、逐表达支持状态缺失，均阻止 Reader 发布。
5. 13,611 是全量物理字段准备分母；6 是首批有界 Reader identity。两者之间不存在“13,611 个待归类概念”关系：所有字段先有 Evidence Pack，只有经 P2/P3 裁定的字段实例才可进入六个 Reader。
6. 23 个准备层 Gold、27 个语义 Gold 和 12 个跨层 Gold 分层执行，分别验证 P0→P1、P2→P4 和 P1→P3/P4 的接口，不可合并成一个“业务 Gold 通过数”。
7. 实施前先冻结 07 设计/契约/验证计划 bundle 和 source manifest，由独立审阅给出可进入的步骤范围。09 `REWORK_BOUNDED_AUTHORIZATION` 只授权步骤 1–2，不是 GateResult `PASS`，不授权 step 03–12 或 P2–P5。
8. 新页面只能在字段准备实现、三层验证的决定性失败关闭、六 Reader 的表达级证据可追溯且页面生成输入冻结后产生；该页面仍是候选，不是发布或验收。
9. 只有页面经过真实点击旅程、审阅包可隔离复现、正例/歧义/误导名称/技术反例齐备、没有 vacuous gate 时，才能交给新的独立 Agent 复审。
10. Customer/Counterparty、Agreement/Trade Contract、Position/Position View/Risk Exposure、Margin 各表达边界与方向、映射 SOURCE/TARGET、Gold 业务权威、第二 Schema 等仍需用户或业务人员裁定。

## 2. 输入状态和证据边界

### 2.1 Agent A

- `06-reworked-navigation-proposal.md`、`06-navigation-skeleton.yaml`、`06-gold-set.yaml` 是研究骨架候选。
- 22 个核心概念与 3 个不计入 22 的支撑 identity 仍是研究注册表。
- 首批 6 个 Reader 为 Counterparty、Order、Trade、Notional、Position、Margin；状态均为 `REWORKED_CANDIDATE`，发布均为 `BLOCKED_PENDING_INTEGRATION`。
- 10 个首批导航入口仍为 `CONFIGURATION_SEED`，没有独立 Evidence ID，不能作为已证实关系。
- 现行 Stage 3/5 未被修复，修订语义 Gold 为 `PENDING_RERUN`。

### 2.2 Agent B

- `06-field-evidence-preparation-proposal.md`、`06-field-evidence-preparation-contract.yaml`、`06-field-evidence-gold-set.yaml` 是字段证据准备候选契约。
- 输入是 477 个 TRADEFLOW 物理对象上的 13,611 个字段；Stage 3 的 5,512 字段只是当前下游语义工作集。
- 77 个唯一规则 ID 分为 69 个通用规则和 8 个 TRADEFLOW Profile 规则；输出含 16 个类型化区块。
- 每条 provenance 使用 `source_artifacts: 1..*`；当前 TRADEFLOW Profile 要求同时锚定 `columns.json` 与 `objects.json` 的独立 SHA-256。
- 23 个准备层 Gold 仅达到 `SOURCE_ANCHOR_VERIFIED`；规则状态仍为 `RULE_EXECUTION_NOT_PERFORMED`。Provider 尚未实现。

### 2.3 当前运行事实

- Stage 0：TRADEFLOW 有 477 个 `TABLE/SUCCESS` 对象、13,611 个唯一字段。源列键实际为 `column_id`，对象 join 键为 `asset_id`。
- 当前数字后缀过滤选择 233 对象、5,512 字段，排除 244 对象、8,099 字段。该选择不能把 8,099 字段变成删除或 Unknown。
- Stage 3：1,375 个 run-scoped source concept candidates、1,559 个 attribute expressions、5,347 个 observations、4,294 个候选关联字段实例；Manifest 的信息模型 Gate 为 PASS，但明确不等于业务接受。
- Stage 5：仍是 5 个 Reader、95 个表达，其中包含错误的 Order/Trade 合并 identity；页面是候选投影，不是本设计的目标实现。
- 当前 Stage 3 与 Stage 5 都按每个表达内的精确字段名分组物理实现。07 保留该右栏交互，但底层 identity 改用 Canonical 契约。
- 历史正式基线 `05-independent-review.md`、整合设计审阅 08 和实施前复审 09 均保留。当前有效实施授权来自 09 的有界 `REWORK`；Agent A 自报的 ACCEPT 没有独立审阅文件，不能继承。

## 3. Agent A/B 冲突裁定表

| 接口差异 | Canonical 裁定 | 禁止做法 |
|---|---|---|
| A 的 `table_name` / B 的 `object_name` | 底层只存 `object_name`；当 `object_type=TABLE` 时 UI 可显示标签“表名” | 另建 `table_name` identity 或对 VIEW 强制表语义 |
| A 的 `column_name`、`raw_column_name` / B 的 `column_name_raw` | 只存 `column_name_raw` | 同时保留两个近义 raw 字段 |
| A 的 `raw_column_comment` / B 的 `column_comment_raw` | 只存 `column_comment_raw` | 以规范化注释覆盖原值 |
| A 的 `raw_table_comment` / B 的 `object_comment_raw` | 只存 `object_comment_raw` | 丢掉 VIEW/对象语义或原始空格 |
| Stage 0 `column_id` / B 的 `physical_column_id` | 读取时作一次确定性 rename：`physical_column_id := column_id`；值不变 | 同时暴露 `column_id` 与 `physical_column_id` 为两套 identity |
| `asset_id` | 仅作 `columns.json`→`objects.json` 的 provenance locator | 把它当第二个字段 identity |
| A 的短币种枚举 | `ORIGINAL_CURRENCY`、`LOCAL_CURRENCY`、`UNDERLYING_CURRENCY`、`SETTLEMENT_CURRENCY` | 继续使用任何历史短值 |
| A 的字段属性 / B 的 observation | 用显式 P1→P2 mapping 产生候选，再由 P3 裁定 | 名称相同就直接等同 |
| A 的技术隔离 / B 的技术候选 | P1 仍为 `CANDIDATE` 或 `UNRESOLVED`；规则执行与 Suite A 后才能进入技术投影 | 直接认定为 AUDIT、静默删除或放入业务 Reader |
| A 的 formal qualifier / B 的 qualifier observation | 经过对象适用性、独立上下文、Conflict、维度兼容、Gold 与语义裁定 | token 或 observation 直接成为 formal qualifier |
| B 的最长保护短语与 Gold 的内层短语 | 最长外层 match 是 `GUARD`，可在其 span 内输出经注册的 `OBSERVATION_UNIT`，两者各有 span 与 rule provenance | 先拆裸 `SHORT/LONG/SOURCE/TARGET` 再补救 |
| B Gold 测试哨兵 | `NOT_APPLICABLE` 表示技术 observation 数组为空；`TECHNICAL_ISOLATED` 是 handoff route；度量竞争归入 P2 语义冲突 | 把测试哨兵写入 Provider 正式枚举 |

## 4. 六层端到端模型

| 层 | 允许消费 | 必须输出 | 明确禁止 |
|---|---|---|---|
| P0 Physical Fact | 冻结的 Stage 0 `objects.json`、`columns.json` 与其 hash | Schema、Object、Column、原始注释、数据类型、可空性、顺序、物理 identity、来源定位 | 规范化覆盖原值、业务行、语义推断、跨 Schema 推广 |
| P1 Prepared Evidence | P0 与版本化通用/Profile 规则 | 规范化词法、token、保护短语、缩写/属性/技术/qualifier observation、上下文、Conflict、unresolved、provenance、处置 | 正式概念、正式字段属性、正式 qualifier、Reader、静默删除 |
| P2 Semantic Adjudication Candidate | 完整 P1 Pack、已登记业务骨架、Gold 约束 | 对象锚点候选、属性表达归属候选、字段属性候选、qualifier 候选、反证、下一证据 | 把候选写回 P0/P1、按 token/表名/词频作结论、发布 Reader |
| P3 Semantic Decision | P2、可定位支持/反证、业务裁定规则、审阅决定 | 接受/拒绝/Deferred 的概念 identity、表达、字段属性、qualifier 与理由 | 用 score 冒充概率、删除反证、用一个概念支持状态覆盖全部表达 |
| P4 Reader Candidate | 只消费已接受的 P3 决定和仍可见的阻塞项 | 唯一 Reader identity、入口、表达、物理实现、逐表达证据状态、发布阻塞 | 合并 Order/Trade、复制 Reader identity、把配置种子当 Evidence、声明已发布 |
| P5 Reader Projection | 冻结的 P4 投影包与 P0/P1/P2/P3 引用 | 单页导航、表达矩阵、物理详情、Evidence/Conflict/unresolved、治理队列、计数 | 独立事实源、canonical 回写、隐藏 EXCLUDED/Conflict/Unknown、业务验收声明 |

P1 到 P2 的 join 必须是一对一 Evidence Pack 对一个 `physical_column_id`；P2 可为同一物理字段产生多个互斥解释，但每个解释必须单独记录 evidence、counterevidence 与 `required_next_evidence`。P3 的接受决定是对“对象 + 属性表达 + 字段属性 + qualifier 集合”的版本化决定，不是对 token 的接受。

## 5. Canonical 数据接口

### 5.1 物理 identity 与原始事实

唯一 Canonical identity：

```yaml
schema_name: string
object_name: string
object_type: TABLE | VIEW | MATERIALIZED_VIEW | SYNONYM
physical_column_id: string
column_name_raw: string
column_comment_raw: string | null
object_comment_raw: string | null
data_type_raw: string
nullable: boolean
ordinal_position: integer
```

`physical_column_id` 的值来自 Stage 0 `column_id`，只改字段名、不改值。其唯一性只在 `(run_id, profile/schema scope)` 内成立，不声称跨运行、跨 Profile 全局唯一。对象事实通过 `asset_id` join，但 `asset_id` 仅出现在 provenance locator。新 Profile 必须先扫描 identity 冲突；非唯一时保留编码/解析失败，以可追溯的 asset + ordinal/source locator 生成 surrogate，不合并、不改名物理事实。页面展示“表名”时只是 `object_name` 的 label，不产生第二套字段。

### 5.2 Provenance

每个 Pack 的 `source_artifacts` 基数保持 `1..*`。当前 TRADEFLOW Profile 至少包含：

- `columns.json`：`COLUMN_PHYSICAL_FACT`，locator 为 Stage 0 `column_id`，SHA-256 独立记录；
- `objects.json`：`OBJECT_PHYSICAL_FACT`，locator 为 `asset_id`，SHA-256 独立记录。

每个 derived observation 必须有 observation ID、`physical_column_id`、source span、rule IDs 和 source artifact refs。人工 review 是 decision provenance，不是物理 Evidence。

### 5.3 Raw 空格修正覆盖

07 不改 06 Gold，但以 Stage 0 原值建立执行覆盖：

| Suite B case | Canonical raw 值 |
|---|---|
| A03 | `object_comment_raw = " CLN 认购流水"`（一个前导 U+0020） |
| B01 | `column_comment_raw = "交易对手长名 "`（一个尾随 U+0020） |
| B01 | `object_comment_raw = "交易- 交易指令"`（连字符后一个内部 U+0020） |

规范化值可以 trim/collapse，但 raw 值、长度、span 与 hash 必须保留。

同一 overlay 机制也用于币种枚举边界，且不改写 06：FEP-009 的历史禁止值 `ORIGINAL` 映射为 Canonical 比较值 `ORIGINAL_CURRENCY`；C02 的历史禁止/旧 oracle `UNDERLYING` 映射为 `UNDERLYING_CURRENCY`；C01/C02/F01 的历史正例 `SETTLEMENT` 映射为 `SETTLEMENT_CURRENCY`。每条 overlay 分别记录 version、source case、`historical_value`、`canonical_comparison_value`、authority 和 content hash；Canonical 比较只允许四个完整枚举值。

### 5.4 单向、闭合的 P1→P2→P3 接口

P1→P2 只形成候选，不依赖任何 P3 决定。16 个 Provider 输出区块必须全部有显式路由：物理事实、raw、词法、token、保护短语、规则与 provenance 只作 anchor/证据/追溯；`generic_attribute_observations` 按其 13 个枚举值进入显式候选映射；`candidate_qualifier_observations` 按 5 个维度及其 Canonical 值进入直接 qualifier 候选映射；Conflict、unresolved 和处置分别进入冲突、下一证据与下游资格路由；技术 observation 只进入技术治理路由。

Agent A 另有 7 个不在 Provider qualifier block 中的维度：`observation_time_role`、`party_relationship_role`、`aggregation_state`、`availability_condition`、`estimation_status`、`measure_basis`、`flow_side`。它们必须在 P2 的第二阶段由“不可变 P1 证据 + 第一阶段对象/表达/字段属性候选”组成复合候选规则，不能由 P3 回头补造。比如 C03 只有在比例/系数语义、MEASURE 候选和独立注释同时存在时才形成 `measure_basis=RATIO` 候选；K01 只有在“初始”中文注释、TIME/MEASURE 所属表达和非技术时间语义同时存在时才形成 `observation_time_role=INITIAL` 候选。裸 `RATE`、`TIME`、`SOURCE/TARGET`、缩写或 token 均不足以产生这些 qualifier。

同理，Agent A 的 8 个字段属性中，6 个可由 Provider generic observation 进入直接 P2 路由；`PARTY_RELATIONSHIP` 必须由有界 Party 关系对象候选与明确关系证据复合产生；`AUDIT` 只有在规则执行和 Suite A 约束满足后才能形成技术投影中的 P2 候选，且不能进入业务 Reader。“有 route”不等于“可达 Gate 通过”：8 个字段属性和 12 个 qualifier 每个都必须在 behavior-route matrix 中覆盖可促进正例、证据不足/UNBOUND，以及误导/Conflict（或明确 `NOT_APPLICABLE`）；空集、未执行、只有静态 route 都不得算通过。所有路径都尚不是 P3 决定。

`abbreviation_observations` 不得单独产生对象、属性、qualifier 或 Reader 候选。已有版本化展开且有非缩写 observation 佐证时，它只能作为现有候选的上下文；`UNRECOGNIZED_ABBREVIATION` 只产生 `required_next_evidence / DEFERRED`，不得补造展开。

P2 每条候选固定记录来源 observation、上下文、反证、Conflict、规则、下一证据和 `semantic_resolution_status`。该状态只允许 `CANDIDATE / UNBOUND / CONFLICT / DEFERRED / NOT_APPLICABLE`；`ACCEPTED / REJECTED / PUBLISHED` 不属于 P2。

P3 的 22 个核心概念、8 个字段属性和 12 个 qualifier 是封闭注册表，但 P1/P2 发现词汇必须开放。新维度或新值不得为了通过穷尽性检查而被丢弃；它必须形成 `UNREGISTERED_CANDIDATE`，保留 raw span、provenance、建议维度和 `DEFERRED` 理由，且不得进入 P3 或 Reader。

P2/P3/P4 记录 grain 同样冻结：Candidate 唯一键包含 `run_id + profile_ref + schema_name + physical_column_id + candidate_type + candidate_value_ref + evidence_hash + candidate_version`；P3 decision、P4 expression、Reader candidate 和 active state 也都必须携带相同 run/Profile/Schema/candidate-version 范围。完全相同输入重跑必须产生相同 identity 和内容 hash，重复 active 记录立即失败。

qualifier observation 只有经过对象适用性候选、独立注释或上下文、维度兼容检查，才能成为 P2 qualifier candidate；缺对象适用性时只形成 UNBOUND assessment，开放 Conflict 时保留所有解释并标为 `CONFLICT`。随后 P2→P3 Gate 才检查已确认的对象适用性、独立上下文、无开放阻塞冲突、维度兼容、适用 Gold 约束和显式语义决定，并输出接受、拒绝或延后决定。方向严格为 `P1→P2→P3`，P3 不回写或再生成 P2 候选。

## 6. 确定性、候选和语义规则边界

### A. Deterministic Preparation

- 原始值逐字节保存；记录两个 Stage 0 artifact hash。
- `column_id` 一次性 rename 为 `physical_column_id`，并用 `asset_id` 补齐对象事实。
- NFKC、大小写比较键、空白比较形态、标点/连接符/字母数字边界、非破坏切词。
- 最长保护短语先作为 guard；同一 guard 内只允许注册的 observation unit。
- 相同字段名在不同对象中始终保留不同 `physical_column_id`。
- 处置、冲突、unresolved 和 provenance 的结构校验。

### B. Candidate-Producing Rules

- `CTPTY` 只能形成 Counterparty/Customer/其他主体关系的对象锚点候选。
- `IDENTIFIER_SHAPE + 单一有界对象锚点候选 + 无 identity 阻塞冲突` 只能形成 P2 `IDENTIFIER` 字段属性候选；正式属性仍由 P3 决定。
- `NAME_VARIANT_OBSERVATION + 单一有界所属对象候选` 只能形成 P2 `DESCRIPTIVE_TEXT` 候选；正式属性仍由 P3 决定。
- `MEASURE + 明确业务概念 + 度量语义证据` 只能形成 `MEASURE` 候选。
- 中文明确“多头/空头”可形成 `position_side` observation；仍须对象适用性与维度兼容检查。
- 映射对象中的 `SOURCE/TARGET` 只有在 active Profile 和 Schema 均为 `TITANS_TRADEFLOW`、且有输入/输出责任证据时才可形成数据侧或 lineage candidate；不能直接成为 `flow_side`。一个合成非 TRADEFLOW 反例必须只输出 lineage context，用于阻止 Profile 外泄。
- 技术模式只形成 `CANDIDATE/UNRESOLVED` 技术 observation。

### C. Semantic Decision Rules

- 字段属于 Order、Trade、Counterparty、Position、Notional 或 Margin。
- Customer 与 Counterparty 的关系；Position、Position View 与 Risk Exposure 的边界。
- Margin 本体、金额、余额、阈值、比率、参数与收付方向的表达归属。
- `SOURCE/TARGET` 是否在某一明确映射中成为 TRADEFLOW-only `flow_side`。
- qualifier 是否与对象/表达兼容；Reader 是否可生成、进入独立复审或发布。

B 类规则只能产出 P2；任何 B 类规则产生 P3/P4 结论都属于越权失败。

## 7. 六个 Reader 发布契约

### 7.1 Counterparty

- `reader_id`: `reader:counterparty`；`concept_id`: `concept:counterparty`。
- 稳定定义：在协议、订单或交易关系中承担对手方关系的 Party-in-relation。
- 排除：Customer 默认等同、Party master identity、SHORT/LONG 名称方向、SOURCE/TARGET 裸流向。
- 允许字段属性：IDENTIFIER、DESCRIPTIVE_TEXT、PARTY_RELATIONSHIP、BUSINESS_OBJECT_STATE、TIME。
- 允许 qualifier：party_relationship_role、trade_side；flow_side 仅限 TRADEFLOW 映射语境且须 P3 独立决定。
- 允许入口：交易准备、执行与交易形成；两者共用一个 Reader identity。
- 必须覆盖 Suite B A01–A05、B01、D01–D02、G01、I01–I02、L01，以及 Suite C 的短名、SOURCE/TARGET、技术隔离与 Conflict 案例。
- 阻塞：A03 Customer/Counterparty 未决、D01/D02 映射角色未决、任何名称方向误判、表达级证据继承。
- 最低物理证据：Canonical P0 anchor、字段名/注释分别入账、对象上下文、双 artifact provenance、无 identity-critical Conflict。
- 当前：`REWORKED_CANDIDATE / BLOCKED_PENDING_INTEGRATION`。

### 7.2 Order

- `reader_id`: `reader:order`；`concept_id`: `concept:order`。
- 稳定定义：指示拟执行交易的意图或指令，可撤销、拒绝或未成交。
- 排除：Trade、Trade Contract、Trade identifier 继承。
- 允许字段属性：IDENTIFIER、DESCRIPTIVE_TEXT、PARTY_RELATIONSHIP、BUSINESS_OBJECT_STATE、MEASURE、CURRENCY、TIME。
- 允许 qualifier：trade_side、observation_time_role、currency_basis、aggregation_state；均需 Order 对象锚点。
- 允许入口：询价、报价与订单。
- 必须覆盖 Suite B H01、G02 的错误入口反例，以及 Suite C 的 Order/Trade identity 分离案例。
- 阻塞：任何 Order/Trade 合并 identity、Order ID 被映射到 Trade、表名投票、缺少 Order 直接正例。
- 最低物理证据：独立 Order 标识/状态/时间字段的 P0 anchor 与明确 Order 责任证据。
- 当前：`REWORKED_CANDIDATE / BLOCKED_PENDING_INTEGRATION`。

### 7.3 Trade

- `reader_id`: `reader:trade`；`concept_id`: `concept:trade`。
- 稳定定义：已经执行并形成经济事实的交易记录。
- 排除：Order、Trade Contract、Order identifier 继承。
- 允许字段属性：IDENTIFIER、DESCRIPTIVE_TEXT、PARTY_RELATIONSHIP、BUSINESS_OBJECT_STATE、MEASURE、CURRENCY、TIME。
- 允许 qualifier：trade_side、observation_time_role、currency_basis、aggregation_state。
- 允许入口：执行与交易形成。
- 必须覆盖 Order/Trade identity 反例，并在实现前补充至少一个可定位、经业务裁定的 Trade 正例；现有 27 个 Suite B 没有直接 Trade Reader 正例。
- 阻塞：合并 Reader、订单标识继承、只靠 `TRADE` token 或表名、缺少直接正例。
- 最低物理证据：Trade 专属 identity 或执行事实的 P0 anchor，并有与 Order/Contract 区分的责任证据。
- 当前：`REWORKED_CANDIDATE / BLOCKED_PENDING_INTEGRATION`。

### 7.4 Notional

- `reader_id`: `reader:notional`；`concept_id`: `concept:notional`。
- 稳定定义：用于计算现金流、风险或条款规模的合同度量基准。
- 排除：Margin、Position、Valuation、Payment Amount、generic amount。
- 允许字段属性：MEASURE、CURRENCY、TIME、DESCRIPTIVE_TEXT。
- 允许 qualifier：position_side、variability、currency_basis、observation_time_role、aggregation_state、availability_condition、estimation_status、measure_basis。
- 允许入口：合同存在域、估值与风险；多入口不复制 identity。
- 必须覆盖 Suite B C01–C02、F01、K01 和 Suite C 的中文方向适用、Conflict、逐表达状态案例。
- 阻塞：F01 方向冲突、短币种枚举、裸 token、Notional 与其他金额概念混同。
- 最低物理证据：数值字段 P0 anchor、明确 Notional 文本或已裁定合同条款关系、度量/币种/方向各自 provenance。
- 当前：`REWORKED_CANDIDATE / BLOCKED_PENDING_INTEGRATION`。

### 7.5 Position

- `reader_id`: `reader:position`；`concept_id`: `concept:position`。
- 稳定定义：某主体、账户或组合在指定时点与业务范围下的持有状态记录。数量、余额、方向和时点是该 identity 下的独立表达，不参与 Position identity 投票。
- 排除：Order quantity、技术同步计数、Position View 默认合并、Risk Exposure、Notional。
- 允许字段属性：IDENTIFIER、DESCRIPTIVE_TEXT、BUSINESS_OBJECT_STATE、MEASURE、CURRENCY、TIME。
- 允许 qualifier：position_side、observation_time_role、currency_basis、aggregation_state、availability_condition、estimation_status、measure_basis。
- 允许入口：合同存在域、估值与风险；多入口不复制 identity。
- 必须覆盖 Suite C 的 CXL-012 “数量不是 identity”反例、Position/Risk Exposure 边界，并在实现前补充至少一个经业务裁定的 Position 直接正例；现有 27 个 Suite B 没有该正例，契约只记录 `POSITION_DIRECT_POSITIVE / REQUIRED_NOT_YET_PROVIDED`，不伪造案例。
- 阻塞：名称长短变方向、数量/余额竞争未裁定、Risk Exposure 继承、缺少直接正例。
- 最低物理证据：Position 对象/持有责任锚点和可区分数量、余额、方向、时点的字段实例证据。
- 当前：`REWORKED_CANDIDATE / BLOCKED_PENDING_INTEGRATION`。

### 7.6 Margin

- `reader_id`: `reader:margin`；`concept_id`: `concept:margin`。
- 稳定定义：为覆盖履约风险而计算、要求或记录的保证金额度或状态。
- 排除：Collateral、Notional、Position、Valuation、generic amount。
- 允许字段属性：DESCRIPTIVE_TEXT、BUSINESS_OBJECT_STATE、MEASURE、CURRENCY、TIME。
- 允许 qualifier：cashflow_direction、currency_basis、observation_time_role、availability_condition、estimation_status、measure_basis、aggregation_state；position_side 仅在 Margin 参数表达的 P3 所有权与适用性均已裁定时允许。
- 允许入口：保证金与抵押品、估值与风险；多入口不复制 identity。
- 必须覆盖 Suite B M01、C03 的边界/阻塞反例，以及 Suite C 的 qualifier/技术/Conflict 隔离。M01 不得同时充当直接正例；当前 `MARGIN_DIRECT_POSITIVE` 诚实标记为 `REQUIRED_NOT_YET_PROVIDED`。
- Margin 表达 kind 只允许 `AMOUNT / BALANCE / THRESHOLD / RATIO / PARAMETER / DIRECTION`，每个 expression version 只有一个 kind；任何跨 kind 折叠都停止 Reader candidate。
- 阻塞：MARGIN_DIRECTION 无值语义、金额/余额/阈值/比例/参数被折叠为同一表达、表上下文直接归属。
- 最低物理证据：每种表达分别拥有 P0 anchor、明确 Margin 语义、度量或阈值/比率证据、独立 qualifier provenance。
- 当前：`REWORKED_CANDIDATE / BLOCKED_PENDING_INTEGRATION`。

所有 Reader 的共同 publication gate：Provider 与 adapter 已实现；Suite A 已执行并审阅；Suite B/C 的决定性案例达到预期或明确 NOT_EVALUABLE；Reader 有正例和误导名称反例；identity/定义无开放阻塞；每个表达独立计算支持状态；10 个入口有 Evidence ID 或继续明确标为非证据且不发布；页面投影可回溯到 P0–P4；独立复审尚未通过时只能保持 Candidate。

## 8. 业务入口与 Reader 关系

研究模型保留 4 个旅程入口、1 个“合同存续域”、7 个可重复业务活动和 3 个横切支撑面。13 个业务区域是模型分类，不原样平铺为 13 个一级菜单。

- 旅程入口：交易准备；询价、报价与订单；执行与交易形成；合同形成。
- 合同存续域：从合同形成到到期、终止或关闭，承载状态、义务和重复活动。
- 可重复业务活动：生命周期事件、估值与风险、保证金与抵押品、义务与现金流计算（只是页面分组，不合并 concept identity）、清算、支付/转移/交割、结算结果。
- 横切支撑面：市场参考与业务配置；运营、对账与报表；技术加工与审计。

“待收/待付责任”、“经计算或计划的现金流计划/明细”、“支付/转移/交割事件”、“结算结果”是四个独立层次。例如“计划付款 100”只能证明 obligation/cash-flow item，不能证明已发生 payment 或 settlement success。

同一 Reader 可以从多个入口到达，但 URL/identity/定义只有一份。10 个首批入口全部继续标记 `CONFIGURATION_SEED / NOT_PUBLISHED / evidence_id=null`；在独立 Evidence ID 建立前，它们只帮助研究导航，不证明业务关系。Agent A 另有 31 个 legacy configuration seeds；07 不删除、不覆盖，也不把 10 个首批入口视为其迁移结果。31→10 的映射、保留、合并或退役方案继续 `DEFERRED`。

## 9. 三层 Gold 体系

### Suite A：Field Evidence Preparation Gold

- 来源：`06-field-evidence-gold-set.yaml`，23 个案例。
- 验证：raw 事实、identity、双来源 hash、规范化、保护短语、技术候选、Conflict、禁止自动推断。
- 当前状态：`SOURCE_ANCHOR_VERIFIED / RULE_EXECUTION_NOT_PERFORMED`。
- `NOT_APPLICABLE` 等测试哨兵由验证 adapter 解释，不扩展 Provider 正式枚举。

### Suite B：Semantic Navigation Gold

- 来源：`06-gold-set.yaml`，27 个案例，其中 24 个真实物理字段；E02–E04 为 `NOT_EVALUABLE`。
- 验证：业务概念、属性表达、字段属性、qualifier、Reader identity、发布阻塞、已知误判。
- 当前状态：`PENDING_RERUN`；07 以 Stage 0 raw overlay 修正 A03/B01 三处空格，并把币种值映射为完整枚举，不改写 06。

### Suite C：Cross-Layer Handoff Gold

- 本轮新增 12 个跨层案例，覆盖用户指定的 10 类接口，并额外暴露 Trade/Position 直接正例缺口。
- 验证：P1 observation 不越级、P2 候选条件、P3 阻塞、物理 identity 隔离、技术隔离、逐表达状态。
- 当前状态：`NOT_EXECUTED`。

两个 06 文件以路径与 SHA-256 引用，不复制历史结果。验证记录把 `source_verification`、`rule_execution`、`semantic_adjudication` 分开。YAML 能解析不等于 Gold 满足；Gold 满足不等于业务验收。

实施/复审输入另有 allowlisted source manifest：Agent A/B 六份 06 输入、05/08/09 审阅、current-status baseline 和四份 runtime fact/manifest 均记录 path、role 与 SHA-256。三份 07 按固定相对路径顺序、精确字节、NUL/长度分隔构造 bundle；契约内唯一 `candidate_bundle_sha256` 值在计算前替换为 `SELF_EXCLUDED`，以避免自引用。新 bundle 仍需新的实施前独立复审才可进入 step 03。

Provider、Manifest 和每个 GateResult 必须记录 `model_calls=0`、`model_token_budget=0`、`model_token_usage=NOT_USED`、`external_egress=false`、`business_rows_read=false`、`database_writes=0`。路径先解析为 Windows canonical absolute target，再解析 symlink/junction；读只允许项目 workspace root，写只允许项目 `output` root，任何 escape 立即 `STOP`。

## 10. 页面投影

只生成一个三栏页面：

- 左栏：只显示当前旅程/合同存续域/活动/横切面相关的业务区域与概念；13 个区域不作为 13 个固定一级菜单。
- 中栏：唯一 Reader identity、稳定定义、排除边界、表达矩阵、字段属性、qualifier 筛选、字段数/表数、逐表达 Evidence/Conflict/发布状态。
- 右栏：沿用 Stage 3 的 `physicalGroups` 交互，显示物理字段名、实现数量、表数量、Schema、对象名（TABLE 时标签“表名”）、对象注释、字段注释、数据类型、对象详情入口、Evidence、Conflict、unresolved。
- 底部：治理队列和口径说明。

页面中的 `SUPPORTED` 只能由当前表达自己的已接受决定与证据计算。一个 source concept 有支持，不能使同 Reader 的其他表达继承 `SUPPORTED`。字段和表计数都按 Canonical physical identity 去重，不能按展示名去重。

页面 Gate 使用六 Reader 旅程矩阵，而不只测一条通用链路。Counterparty、Order、Trade、Notional、Position、Margin 每行都必须有：绑定四类 Evidence 的直接正例、边界/误导名反例、阻塞项可见、可到达具体物理字段和对象详情、deep link 可恢复、返回时保留树、Reader、表达和字段上下文。Trade、Position 和 Margin 目前都缺少直接业务正例，整个页面 Gate 必须停止。

## 11. 治理队列状态

统一状态及含义：

- `OUT_OF_SCOPE`：明确不在本研究边界，仍保留来源和理由。
- `NOT_IN_FIRST_READER_SCOPE`：可有业务价值，但不属于首批 6 Reader。
- `ATTRIBUTE_LAYER`：已识别为属性/表达，不是业务概念 identity。
- `TECHNICAL_CANDIDATE`：技术/审计候选，仍为候选或未解析。
- `EVIDENCE_INSUFFICIENT`：证据不足以进入 P3。
- `CONFLICT`：可定位证据相互矛盾，禁止自动解决。
- `NOT_EVALUABLE`：测试或定位前提缺失，不能伪造字段。
- `TRUE_UNKNOWN`：在声明 grain 与完整处理后仍无法解释。
- `NOT_YET_PROCESSED`：尚未跑到相应层，不是 Unknown。

不再使用“待归类”大桶。`PREPARED/EXCLUDED/DEFERRED` 是 P1 处置，不是上述语义/发布状态；`EXCLUDED` 也不表示删除。

## 12. 计数契约

| 计数 | grain/分母 | 当前值或状态 |
|---|---|---:|
| physical schema | Stage 0 Schema identity | 1（本研究 TRADEFLOW） |
| physical object | Stage 0 object identity | 477 |
| physical column | Stage 0 `physical_column_id` | 13,611 |
| prepared field evidence package | 每个物理字段一个 Pack | `NOT_EXECUTED`，目标 13,611 |
| downstream semantic workset field | 进入当前语义工作集的物理字段 | 5,512 |
| source concept candidate | Stage 3 run-scoped candidate | 1,375 |
| semantic observation | Stage 3 observation record | 5,347 |
| attribute expression | Stage 3 expression candidate | 1,559 |
| Reader identity | 首批研究 identity | 6，均未发布 |
| Reader expression | 一个 Reader 下的独立表达 | `NOT_COMPUTED_FOR_07` |
| Reader physical field instance | Reader 表达引用的唯一 `physical_column_id` | `NOT_COMPUTED_FOR_07` |
| Reader table | Reader 引用的唯一 TABLE object | `NOT_COMPUTED_FOR_07` |
| unpublished source concept | Stage 5 未挂 Reader 的 source candidate | 1,326，不是 Unknown |
| out-of-scope item | 明确范围排除的声明 grain | `NOT_COMPUTED` |
| evidence-insufficient item | Stage 3 hypothesis | 618 |
| conflict item | 类型化 Conflict item | 当前 71；66 是 conflict hypothesis，分母不同 |
| true unknown | 完整处理后同一声明 grain 的 Unknown | `NOT_COMPUTED` |

13,611 不是待归类概念；5,512 不是准备层总输入；1,375 不是业务概念总数；6 不是已发布概念；23 与 27 不是 50 个业务 Gold；1,326 不是 Unknown。

## 13. 实施顺序与 Gate

| # | 输入 | 输出 | Gate | 失败停止条件 |
|---:|---|---|---|---|
| 0 | 冻结的 07 设计/契约/验证计划 bundle、source manifest、09 独立复审 | 实施前处置和有界授权范围 | `REWORK_BOUNDED_AUTHORIZATION` 独立于 GateResult PASS；当前仅合法允许 1–2 | 缺失审阅/hash/manifest，或 `STOP/DEFER`，或尝试越过授权范围 |
| 1 | 07 契约、Stage 0 schema | 字段证据准备 Provider | 规则版本、16 区块、raw 不可变、无语义输出；配置 schema ID 与结果 bundle schema ID 分离 | schema/identity/provenance 任一不满足，或命名碰撞未解决 |
| 2 | Provider、13,611 个 P0 字段 | 版本化 Evidence Pack | 一字段一 Pack、双 hash、处置全覆盖 | 少字段、重复 identity、hash 不匹配、静默删除 |
| 3 | Evidence Pack、Suite A | 分离的 source/rule 结果 | 23 案例执行并审阅失败 | raw/identity/hash/禁止推断任一决定性失败 |
| 4 | 通过准备 Gate 的 P1 | P1→P2 handoff adapter | 16 区块全路由、输入枚举闭合、8 字段属性/12 qualifier 均有 P2 路径、只产候选、P2 状态值域闭合、无 P3 依赖 | 未路由区块、不可达正式语义、未定义 observation、P3→P2 回边、provenance/Conflict/unresolved 丢失 |
| 5 | P2、六 Reader 边界 | 有界 P3/P4 候选包 | P2→P3 单向接受 Gate、identity 分离、逐表达状态、入口非证据标识 | P3 回写 P2、合并 Reader、对象锚点缺失、技术候选泄漏 |
| 6 | P3/P4、Suite B/C | 三套分层验证结果 | B 27、C 12 全量执行；E02–E04 保持不适用 | 决定性失败、未执行冒充满足、Gold 被改写 |
| 7 | 失败与反证 | 修正后的候选包 | 已知误判与所有决定性失败关闭 | 弱化测试、隐藏 Conflict、缺 Trade/Position 正例 |
| 8 | 冻结 P0–P4 bundle | 新单页 Reader 候选页面 | hash/Manifest、表达级状态、治理状态齐全 | 任何 Reader/表达无追溯或开放发布阻塞 |
| 9 | 页面与真实点击旅程 | 可用性记录 | 能从入口到 Reader、表达、字段、对象详情和返回 | 只有聚合节点、链接失效、口径不可理解 |
| 10 | 隔离审阅包 | 新独立 Agent 审阅文件 | 正例、歧义、误导名称、技术反例与非空 Gate | 输入不隔离、代表案例不足、vacuous pass |
| 11 | 独立审阅结论与页面 | 用户业务验收请求 | 仅独立审阅达到未来允许的进入条件后请求 | REWORK/STOP/DEFER 或业务问题未决 |
| 12 | D-010 授权与第二 Schema 语料 | 第二 Schema 研究 | 独立 case pack、Manifest、反例与审阅 | 当前固定 `DEFER`，无授权即停止 |

步骤 0 的授权与步骤 1–12 的执行 GateResult 是两类记录：步骤 1 无执行前驱，但必须被 09 有界授权覆盖；步骤 2 另需步骤 1 PASS/hash；步骤 3–12 除前一执行步骤 PASS/hash 外，还需绑定当前 candidate bundle 的新实施前授权。每个 GateResult 引用显式 exact case registry，不允许符号化 case group；它同时记录状态分布、E02–E04 白名单、直接正例 Evidence 绑定和六个零模型/外发/业务行/写入安全值。

## 14. TRADEFLOW 与跨 Schema 边界

- 69 个通用规则仍只是 cross-schema candidate；8 个 TF 规则仅属于 TRADEFLOW Profile。
- `flow_side` 为 `TRADEFLOW_ONLY`，不能从 `SOURCE/TARGET` 复制到其他 Schema。
- 22 个业务概念、12 个 qualifier 与六 Reader 也不因本整合而成为通用本体。
- 在第二 Schema 前，必须同时满足 D-010 用户授权、新 Profile identity 冲突扫描、独立 case pack/Manifest/反例/审阅，并保留编码与 parser 失败。任一不满足就停在 TRADEFLOW；不得合并、改名或沿用冲突的 `physical_column_id`。
- 第二 Schema 选择、case pack、Manifest、独立反例和审阅均为 `DEFERRED`；禁止 `GLOBAL_VALIDATED`、通用本体或规模化声明。

## 15. 尚待业务裁定的问题

1. Customer 与 Counterparty 在准入、协议、订单、交易语境中的关系。
2. Agreement、Trade Contract、Trade 与 Contract Leg 的法律/业务层级。
3. Position、Position View/Holding 与 Risk Exposure 的边界和中文命名。
4. Margin 本体、金额、余额、阈值、比例、参数、抵押品和方向的表达模型。
5. `MARGIN_DIRECTION` 的值语义及是否可成为 cashflow_direction。
6. SOURCE/TARGET 在具体映射中的输入/输出责任，及何时允许 formal `flow_side`。
7. Trade 与 Position 的直接正例 Gold；现有 Suite B 未覆盖这两个 Reader。
8. 10 个入口的关系 Evidence ID 与 review owner。
9. Gold Set 的业务 reviewer、ADJUDICATED/DISPUTED 方法与业务权威。
10. 31 个 legacy configuration seeds 与 10 个首批入口之间的迁移、保留和退役规则。
11. 当前配置 schema ID 与目标 Reader/result bundle schema ID 的唯一命名。
12. Wiki 输入、地图分享/脱敏/权限、外部模型数据外发。
13. 第二 Schema 的选择和通用性验证。

## 16. 最终独立复审要求

本轮只允许契约自检，不能自我给出 `ACCEPT`。已有实施前独立复审 `09-independent-preimplementation-review.md`，处置为有界 `REWORK`，仅允许实施步骤 1–2。本次修订产生新 candidate bundle；它不继承 09 为 ACCEPT，步骤 3 前仍需新的实施前独立复审。实施后页面/Gold/点击复审又是另一份独立产物。

- reviewer scope；
- isolated inputs 与 hash；
- positive cases；
- ambiguous cases；
- misleading-name counterexamples；
- technical cases；
- disposition（未来仅允许 `ACCEPT`、`REWORK`、`STOP`、`DEFER` 中一个）；
- decisive reasons；
- smallest next action。

独立复审也不能设置 `business_acceptance=ACCEPTED`，不能替代用户业务验收，不能授权第二 Schema 或规模化。
