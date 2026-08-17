# 字段证据准备与规范化提案

> 状态：`CANDIDATE`；范围：`TITANS_TRADEFLOW` 的冻结元数据输入；日期：2026-08-14。本文是研究设计，不修改现有语义、Reader、代码、配置或 OpenSpec 状态。

## 1. 结论摘要

应在物理字段与业务语义导航之间增加一个独立的“字段证据准备层”。其输入边界是全量 13,611 个 `TITANS_TRADEFLOW` 物理字段，不是 Stage 3 的 5,512 字段工作集。它只封装物理事实、非破坏性词法标准化、词法/属性/技术观察、上下文、反证、冲突和未解析项；它不产出正式业务概念、正式 qualifier 或 Reader 表达。

现行 V2 的主要断点是：裸 `SHORT/LONG` 被 `direction` 规则命中，`SOURCE/TARGET` 被 `party_role` 规则命中，再被上下文配置投射为 `position_side` 或 `flow_side`。现行数据没有“完整短语优先、观察来源、字段名—注释冲突统一入账、对象锚定、技术字段隔离”的前置契约。因此，修正不应靠在导航树中追加反例；应先把这些词法结论降为可追溯的观察。

## 2. 当前规范化链路诊断

`field-semantics-v2.yaml` 将 `LONG/SHORT` 配进 `direction`，将 `SOURCE/TARGET` 配进 `party_role`；`context-enriched-field-semantic-map.yaml` 再将前者映射为 `position_side`、后者映射为 `flow_side`。`normalize_expression` 已做 NFKC、连接符、大小写及数字边界处理，但只保留原串、规范串和 token，未保留逐字符变换、短语命中、信息损失或复核标记。

这导致以下已观察问题不能在当前产物中被稳定表达：

- `CTPTY_SHORT_NAME`、`CTPTY_LONG_NAME` 的完整名称属性被拆成方向 token。
- `SOURCE_TYPE`、`TARGET_CTPTY_ID` 的名称和映射表上下文混为“数据流向”。
- 字段名、注释、表上下文和配置种子之间的矛盾只在少数下游 hypothesis 中出现，未形成统一 Conflict 记录。
- `ID/STATUS/TYPE/AMOUNT/DATE/CURRENCY/NAME` 可被提取为词形，却没有强制要求先锚定业务对象。
- 技术/审计模式只存在于配置与概念范围处理，当前字段级结果并没有可复算的技术隔离记录；因此不能从冻结输出复算“当前技术字段候选数”。

## 3. 输入数据与计数复算

下表是对冻结输入的直接复算，分母不可互换。

| 口径 | 值 | 解释 |
|---|---:|---|
| TRADEFLOW 物理表/视图 | 477（477 TABLE，0 VIEW） | Stage 0 `objects.json` 的全量 Schema 范围 |
| TRADEFLOW 物理字段 | 13,611 | 上述 477 表的 `columns.json` |
| 字段证据准备层输入 | 13,611 | 全量 TRADEFLOW 物理字段；每一项都必须有物理锚点与处置状态 |
| Stage 3 Manifest 声明源字段 | 5,512 | 后续语义工作集，只含 V2 选中的 233 张非数字后缀表；不是准备层输入边界 |
| semantic observations | 5,347 | observation 行，不等于字段数 |
| observation 覆盖的唯一字段实例 | 5,342 | 一个字段可有多个 observation |
| semantic normalization candidates | 1,602 | 来源概念规范化候选行 |
| data semantic candidates | 1,559 | 属性表达候选行 |
| candidate 覆盖的唯一字段实例 | 4,294 | `field_refs` 去重 |
| attribute expressions | 1,559 | 不是 Reader expression |
| review queue | 859 | 待复核条目 |
| 当前 Conflict | 71 个 conflict item / 66 个 hypothesis | 39 同源不一致、22 名称—注释不一致、10 多概念物理列 |
| 同名而注释不同 | 845 名称组 / 12,151 全量字段实例 | 全量 13,611 字段口径；V2 子集为 415 组 / 3,453 实例 |
| 空注释 | 7,973 全量；212 V2 子集 | 不能以名称补成事实 |
| 未进入 observation 层 | 170 V2 字段 | 5,512 减 5,342；不代表全量 TRADEFLOW Unknown |
| 仅凭字段名形成候选 | `NOT_RECOMPUTABLE_FROM_CURRENT_INPUT` | 下游候选未记录逐项“字段名唯一来源” provenance；40 个候选的全部物理实例注释为空只可作下界，不能替代该口径 |
| 技术/审计字段候选 | `NOT_RECOMPUTABLE_FROM_CURRENT_INPUT` | 当前字段级输出没有技术分类记录，不能以配置字符串命中冒充候选数 |

术语边界：physical column 是 Stage 0 的列声明；field instance 是 `(schema, object, column)`；normalized field signature 是可复算词法投影；token observation 与 semantic observation 不同；normalization candidate、attribute expression、Reader expression 也分别是候选、投影和发布层对象。当前 Stage 3 没有产生 Reader expression，不能从 1,559 attribute expressions 推导 Reader 数量。

## 4. 字段证据准备层职责

该层按 `physical_column_id` 为全部 13,611 字段生成不可覆盖的证据包，并且：

1. 冻结原始字段、对象与来源 Manifest 的物理身份。
2. 对字段名、注释、表名、表注释作非破坏性词法处理，逐步记录规则和字符区间。
3. 识别完整保护短语、缩写、泛化属性形态、技术形态及其冲突；它们均是 observation。
4. 封装表与 Wiki 弱上下文为 `CONTEXT_ONLY`，而不是将表内词频或 Wiki 目录变成结论。
5. 将支持、反证、缺失与未识别缩写交给语义层；不合并同名物理列。

每个字段恰有一个 `preparation_disposition`：`PREPARED` 表示已形成完整证据包；`EXCLUDED` 表示已完成物理锚定与最小词法准备，但按可定位的 Profile 原因不进入某一后续语义工作集（例如 Stage 3 的对象筛选），绝不表示从准备层删除；`DEFERRED` 表示来源、编码或最小物理事实缺失，仍保留可用部分及阻塞原因。Stage 3 的 5,512 字段是 `PREPARED` 后可选择进入的语义工作集，不能反向定义其余 8,099 字段为 Unknown 或无效。

## 5. 明确非职责

- 不判断字段属于 Order、Trade、Contract、Position 或正式业务概念。
- 不决定客户与交易对手关系，或 `SOURCE/TARGET` 的业务含义。
- 不把方向、币种、时间、状态、类型、金额等泛化属性发布为概念。
- 不发布 Reader、替业务骨架 Agent 分类、以词频证明重要性，或跨 Schema 宣称规则有效。

## 6. 原始事实契约

每条 `physical_identity` 必须包含 `schema_name`、`object_name`、`object_type`、`physical_column_id`。`raw_physical_fact` 必须包含对象/字段原始注释、原始列名、数据类型、可空性和顺序。当前 Stage 0 的列事实没有每列 `source_manifest_id/source_hash`，因此契约改用 `source_artifacts`（`1..*`）：`panorama/facts/columns.json`（SHA-256 `A7B783781E53CCCE713D43AF3A177E8790D8A37C0455A2A4F2E1CE54D490F4B7`）以 `physical_column_id` 提供列事实；`panorama/facts/objects.json`（SHA-256 `3B196BF1B02E6EDEAFA0B604406B879DCEB27EDC978D053DEA891D6AD969889C`）以 `asset_id` join 提供对象事实。每个 artifact 记录 path、SHA-256、locator 和 evidence_role。`source_manifest_id` 仅可通过显式注入机制补入，不能作为当前 Stage 0 的必填事实。`physical_column_id` 是唯一 join key；相同 `column_name_raw` 永不合并。

## 7. 字符规范化规则

字符规范化只生成匹配值：NFKC、全半角、大小写折叠、首尾及连续空白、连接符、可分隔标点、字母—数字边界、camel/Pascal 边界、括号内容提取、控制字符检测和疑似乱码检测。每步保留 `raw_value`、`normalized_value`、`rule_id`、`source_span`、`information_loss`、`review_required`。括号内容不删除：主串和括号片段并列保留，以免丢失单位、币种、枚举或业务限定。

## 8. 字段名切词规则

tokenizer 以保护短语的最长匹配开始，然后处理 snake_case、camel/Pascal、连续大写缩写、数字/字母边界、数据库形态后缀。每一个 token 保存 raw/normalized 文本、原字段字符范围、来源（column name/comment/object name/object comment）和 `rule_match`；`rule_match` 是命中理由，绝不是业务概率。`ID/NO/NUM/CODE/TYPE/STATUS/DATE/TIME/AMT` 是形态观察，不能单独成为业务概念。

## 9. 保护短语与缩写规则

按最长、最具体短语优先识别 `SHORT_NAME`、`LONG_NAME`、`SHORT_DESC`、`LONG_DESC`、`SOURCE_TYPE`、`SOURCE_ID`、`SOURCE_SYSTEM`、`TARGET_CTPTY`、`TARGET_ACCOUNT`、`BUSINESS_TYPE`、`CONTRACT_ID`、`ORDER_ID`、`TRADE_ID`、`LEG_ID`、`CREATED_BY`、`UPDATED_DATETIME`、`PUSH_BATCH_NO`。

命中保护短语后，覆盖其 token 区间的裸 `SHORT/LONG/SOURCE/TARGET/LEG/ORDER/CONTRACT` 规则必须被抑制，并写入 `suppressed_rule_ids`。短语本身只形成例如 `NAME_VARIANT_OBSERVATION`、`SOURCE_TARGET_TERM_OBSERVATION` 或 `IDENTIFIER_SHAPE_OBSERVATION`；若没有注释或可信上下文，输出 `UNRESOLVED_PROTECTED_PHRASE`，而非方向、流向或概念结论。

缩写注册表分为通用形态（`AMT/CCY/QTY/DT/ID`）和 TRADEFLOW 词汇（`CTPTY/TRD/POS` 等）。缩写解析可产生 `ABBREVIATION_OBSERVATION` 或 `UNRECOGNIZED_ABBREVIATION`，不得把缩写展开当作已确认业务定义。

## 10. 中文注释处理

注释是独立物理声明证据，不是优先级总开关。准备层识别空、纯英文、中英混合、括号中的单位/币种/枚举、ID/编号/代码/主键、状态/类型/金额/日期/时间、币种基准、明确方向、买卖/收付、时点以及直接复制的名称。注释与字段名、表上下文或配置种子不一致时，分别产生 `CONTRADICT` 或 `CONTEXT_ONLY`，不覆盖原文。

## 11. 表上下文封装

上下文包记录 Schema、表名/注释、对象类型、已知产品候选、业务区域候选、Wiki 弱上下文、来源与证据等级。表名含 `TRADE/ORDER/POSITION/MARGIN/SETTLEMENT` 仅增加 `CONTEXT_ONLY` 提示。不得用同表字段投票来决定某一字段的业务含义；sibling 仅能给出可定位的支持或反证候选。

## 12. 泛化字段属性降级

`ID/编号/代码/名称/短名/状态/类型/金额/数量/日期/币种/来源/目标/是否` 默认产出 `GENERIC_ATTRIBUTE_OBSERVATION`。若可由同一字段的明确文本与后续语义层提供的业务对象共同锚定，才可移交为“对象 + 属性形态”候选；未锚定时状态固定为 `UNBOUND_ATTRIBUTE_OBSERVATION`，禁止生成业务概念。

## 13. 技术与审计字段隔离

技术观察的分类枚举只能取 `TECHNICAL_IDENTIFIER`、`AUDIT_ACTOR`、`AUDIT_TIME`、`INGESTION_METADATA`、`BATCH_METADATA`、`LINEAGE_METADATA`、`EXTENSION_SLOT`、`SOFT_DELETE`、`VERSION_CONTROL`、`UNRESOLVED_TECHNICAL`；每一项还必须有 `CANDIDATE` 或 `UNRESOLVED` 处置，不能凭名称变为确定事实。创建/修改人和时间、删除标记、版本、批次、推送/同步、来源系统、ETL 时间、UUID、行号、分区日期、扩展/备用槽及数据加工 SOURCE/TARGET 都先在这里隔离。特别是 `NUM/SEQ_NO/SOURCE/TARGET` 以及数量/余额差异只能产生候选或冲突，不能确定性裁定。技术观察不自动排除其可能的业务相关性，但不得进入业务导航候选。

## 14. 证据优先级

不设“注释永远优先”。同一断言分别记录 column name、column comment、object name、object comment、data type、sibling、缩写、保护短语、Wiki、现有种子和人工决策。它们只能声明 `SUPPORT`、`CONTRADICT`、`CONTEXT_ONLY`、`NOT_APPLICABLE`、`NOT_OBSERVED`；人工 review 是处置，不能重写物理证据。强弱取决于可定位性与断言类型，不能折算为单一业务概率。

## 15. 冲突模型

每个 conflict 固定记录 `conflict_id`、`physical_column_id`、`conflict_type`、`evidence_a`、`evidence_b`、`candidate_interpretations`、`prohibited_auto_resolution`、`required_next_evidence`、`review_status`。至少覆盖名称—注释、名称内部 token、表上下文—注释、配置种子—字段证据、竞争对象、竞争限定、信息缺失、未识别缩写。冲突只阻止自动下结论；它不删除任何候选解释。

## 16. Unknown 与未解析模型

`NOT_OBSERVED` 表示输入没有该证据；`UNRECOGNIZED_ABBREVIATION` 表示未解析缩写；`UNBOUND_ATTRIBUTE_OBSERVATION` 表示属性形态没有对象锚点；`UNRESOLVED_PROTECTED_PHRASE` 表示短语无法消歧；`SEMANTIC_LAYER_REQUIRED` 表示准备层已完成而业务裁定尚未发生。它们不得被合并为失败或自动补全。

## 17. 通用规则与 TRADEFLOW 专属规则

通用层包含字符/切词、原始值保留、泛化属性、技术隔离、证据/冲突/Unknown 和 provenance 契约。TRADEFLOW Profile 只登记 `CTPTY/TRD/POS/MARGIN/NOTIONAL` 等缩写、指定保护短语、映射表的 SOURCE/TARGET 数据加工语境、冻结产品/表/Wiki 弱上下文。二者都是 `CANDIDATE` 或 `DETERMINISTIC_PROPOSAL`；第二 Schema 验证为 `DEFERRED`，不得出现 `GLOBAL_VALIDATED`。

## 18. 规范化字段证据包

输出包包含 `physical_identity`、`raw_physical_fact`、`preparation_disposition`、`normalized_lexical_form`、`tokens`、`protected_phrases`、`abbreviation_observations`、`generic_attribute_observations`、`technical_observations`、`contextual_evidence`、`candidate_qualifier_observations`、`conflicts`、`unresolved_items`、`applied_rule_ids`、`provenance`、`evidence_status`。每个区块的字段、类型、必填性、基数、枚举、join key 与 provenance 已在 YAML 契约中类型化。任何“概念候选提示”必须标为 `SEMANTIC_LAYER_REQUIRED`；包内禁止最终 Reader concept。

## 19. 21 个真实字段实例：完整输入—输出样例

所有下列输入均来自 Stage 0 的 `TITANS_TRADEFLOW` 物理列；输出是本提案的候选契约示例，不改写当前运行。

| # | 物理输入（对象.字段；注释；类型） | 规范化/观察输出 | 禁止自动结论与交接 |
|---:|---|---|---|
| 1 | `TRD_CLN_TRADE_DEAL.CTPTY_SHORT_NAME`；客户短名；VARCHAR2 | tokens `CTPTY,SHORT_NAME`；保护 `SHORT_NAME`；`CTPTY` 缩写候选；`NAME_VARIANT` | 禁止 `position_side=SHORT`；主体与名称归属交语义层 |
| 2 | `TRD_TRS_ORDER.CTPTY_LONG_NAME`；`交易对手长名␠`；VARCHAR2 | `CTPTY,LONG_NAME`；保护 `LONG_NAME`；名称变体观察 | 禁止 `position_side=LONG` |
| 3 | `TRD_PRE_TRADE_VALIDATION_LOG.SHORT_NAME`；交易对手简称；VARCHAR2 | 保护 `SHORT_NAME`；泛化 `NAME` | 禁止“空头”；对象锚定候选为交易对手但未发布 |
| 4 | `TRANS_HKFT_ORIGINAL_DEAL.SOURCE_TYPE`；委托类别(客户委托、强制召回)；VARCHAR2 | 保护 `SOURCE_TYPE`；泛化 `TYPE`；括号枚举；名称—注释支持“委托类别” | 禁止 `flow_side=SOURCE`；类别对象交语义层 |
| 5 | `TRS_FAST_MAPPING_CONFIG.TARGET_CTPTY_ID`；目标交易对手ID；NUMBER | 保护 `TARGET_CTPTY`；`CTPTY` 缩写、`IDENTIFIER` 形态；映射表 context-only；`LINEAGE_METADATA` 仅为 candidate | 禁止 `flow_side=TARGET`；仅交“可能映射语境” |
| 6 | `TRS_FAST_MAPPING_CONFIG.SOURCE_CTPTY_ID`；源侧交易对手ID；NUMBER | `SOURCE_CTPTY` 保护；`IDENTIFIER`；TRADEFLOW 映射语境候选；`LINEAGE_METADATA` 仅为 candidate | 禁止数据血缘或业务主体结论 |
| 7 | `REF_FAST_TRS.SHORT_DYNAMIC_NOTIONAL`；空头动态名义本金（结算币种）；NUMBER | 保护 `SHORT_DYNAMIC_NOTIONAL` 后拆出明确中文“空头”、动态、结算币种观察 | 可产生 `position_side=SHORT`、`currency_basis=SETTLEMENT_CURRENCY` 候选，仍 `SEMANTIC_LAYER_REQUIRED` |
| 8 | `REF_FAST_TRS.LONG_DYNAMIC_NOTIONAL`；多头动态名义本金（结算币种）；NUMBER | 同上，中文明确“多头” | 可产生 `position_side=LONG`、`currency_basis=SETTLEMENT_CURRENCY` 候选，不发布 Reader |
| 9 | `REF_LS_TRS.SHORT_DYNAMIC_NOTIONAL_ORG`；多头动态名义本金（结算币种）；NUMBER | 名称短语与注释方向/币种均矛盾；两侧证据保留 | `NAME_COMMENT_CONFLICT`；禁止选择 SHORT 或 LONG |
| 10 | `REF_LS_TRS.LONG_DYNAMIC_NOTIONAL_ORG`；结算币种；NUMBER | 名称为名义本金形态，注释为币种；数据类型也可反驳 | `NAME_COMMENT_CONFLICT`；禁止补成多头名义本金 |
| 11 | `ACCOUNT_AMT_FAILED_EVENT_INFO.AMOUNT`；发生金额；NUMBER | `AMT→AMOUNT` 形态、`MEASURE` 泛化观察 | 禁止“金额”业务概念；对象锚定待语义层 |
| 12 | `HKFT_ORIGINAL_DEAL_202607.STATUS`；委托状态；VARCHAR2 | `STATUS` 泛化属性；注释提供“委托”对象候选 | 禁止独立状态概念；是否为订单待裁定 |
| 13 | `OTC_OPTION_PARAMETER.TYPE`；`类型␠`；VARCHAR2 | `TYPE` 泛化属性；对象未锚定 | `UNBOUND_ATTRIBUTE_OBSERVATION` |
| 14 | `CURRENT_POS_202300213.CURRENCY`；空；VARCHAR2 | `CURRENCY` 泛化属性；空注释 | `NOT_OBSERVED` 注释；禁止币种概念 |
| 15 | `ADM_LEND_INFO_AUDIT_LOG.ID`；ID；VARCHAR2 | `IDENTIFIER` 形态；表 context-only | 禁止把 `ID` 当业务对象或技术主键事实 |
| 16 | `REF_IRS.TRADE_ID`；交易编号；VARCHAR2 | 保护 `TRADE_ID`；`IDENTIFIER`；注释支持交易词 | 禁止正式 Trade identity；交语义层 |
| 17 | `TRANS_SMT_ATP_T_REPORT.ORDER_ID`；空；VARCHAR2 | 保护 `ORDER_ID`；`IDENTIFIER`；空注释 | 禁止订单概念确认 |
| 18 | `TRD_FAST_TRS_HMS_POS_SUM.POSITION_TOTAL_QTY`；全部证券余额；NUMBER | `POS` 缩写候选、`QTY→QUANTITY`、计量形态；名称—注释可能不一致 | 不将持仓/余额二选一；记录需业务裁定 |
| 19 | `ADM_UPDATE_AUDIT_LOG.CREATED_BY`；创建人；VARCHAR2 | 保护 `CREATED_BY`；`AUDIT_ACTOR` | 禁止进入业务主体导航 |
| 20 | `ACCOUNT_AMT_FAILED_EVENT_INFO.UPDATED_DATETIME`；修改时间；DATE | 保护 `UPDATED_DATETIME`；`AUDIT_TIME` | 禁止作为业务事件时间 |
| 21 | `TRD_OPTION_TRANS_DEAL.PUSH_BATCH_NO`；推送批次号；VARCHAR2 | 保护 `PUSH_BATCH_NO`；`BATCH_METADATA` | 禁止业务批次概念；扩展槽未见明确物理声明，标记 `NOT_OBSERVED` |

## 20. Gold Set 说明

独立 Gold Set 只保存 `SOURCE_ANCHOR_VERIFIED` 的 Stage 0 物理锚点；本轮规则尚未实现或执行，因此统一记录 `RULE_EXECUTION_NOT_PERFORMED`，不称规则 PASS。它验证的是未来实现必须满足的原值和身份保存、规范化、切词、保护短语、技术隔离、属性降级、冲突、上下文和禁止自动推断；它不验证业务导航正确性。

## 21. 与业务骨架 Agent 的接口

准备层提供原始物理事实、词法、保护短语、字段属性/限定候选观察、技术观察、表上下文、支持/反证、冲突、未解析项和 provenance。业务骨架层负责概念 identity/定义、属性表达归属、正式字段属性与 qualifier、多入口导航和 Reader 发布。

跨界项包括：`CTPTY` 是否为交易对手还是客户、`SOURCE/TARGET` 是数据加工端还是业务关系、`ORDER/TRADE/CONTRACT/POSITION` 的对象边界、明确方向是否适用于该对象、`DATA_SOURCE` 是业务来源还是技术血缘。这些必须由后续整合 Agent 以证据包裁定。

## 22. 实施前置条件

实施前需另行授权并确定：冻结输入版本、字段级稳定 ID 与 source hash、规则执行的顺序/版本化策略、Conflict 的 review owner、第二 Schema 的独立测试语料。不得复用本提案直接修改 V2 配置或把输出写回 canonical facts。

## 23. 已知限制与 DEFER 事项

- 当前 source manifest 未给出逐字段“候选仅由字段名形成”的证据来源，故该计数不可复算。
- 当前字段级产物未输出技术/审计分类，故无法复算现行技术候选数。
- 全量 13,611 字段的准备层尚未实现；`PREPARED/EXCLUDED/DEFERRED` 是待执行处置，不是当前运行结果。
- Wiki 仅有弱上下文，不能裁定业务对象或方向。
- 第二 Schema 验证、规则提升、正式 Reader 发布和任何业务验收均为 `DEFERRED`。
