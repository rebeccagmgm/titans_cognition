# TITANS Cognition 当前状态基线

本文件记录截至 2026-08-12 的当前解释。它不覆盖历史运行结果，而是限定这些结果能够支持的进展声明。

## 唯一交付目标

交付一张可从业务区域、业务对象和生命周期下钻到表、粒度、键、关系、证据与 Unknown 的 TITANS 业务全貌。物理目录、结构候选、Gold Set、评测器和静态页面都是支撑这一目标的工程资产，不是目标本身。

## 完成声明盘点

| 现有声明或结果 | 支撑证据 | 当前可证明 | 当前不能证明 |
|---|---|---|---|
| Panorama 提取与 Gate A `PASS` | 真实测试库元数据运行、独立 SQL 对账、Manifest 和失败记录 | 当前 allowlist 的物理对象、字段、定义和依赖已完成一次有界提取与对账 | 已建立业务区域、业务对象或生命周期全貌 |
| 静态 Panorama 与 Object Card 已生成 | Canonical Facts 的确定性 Projection | 物理对象可以按 Schema 下钻浏览 | 页面已经形成面向用户的业务认知交付 |
| TRADEFLOW V1B 候选闭环已运行 | 分层样本、确定性规则、Candidate、Evidence、Review 输出 | 样本级结构推断原型可运行，Unknown 和失败边界可保留 | 方法已理解 TRADEFLOW 业务，或可以推广到全部 TITANS |
| TRADEFLOW 字段语义调查地图已真实回放 | 5,512 个字段实例、1,197 个候选业务概念、2,208 个真实属性表达、固定 Wiki Tree 快照、Manifest 与三栏审阅页面 | 可以按候选概念、开放限定和物理字段反查；相同输入可确定性重放；字段仍是主数据源，Wiki 仅作弱上下文 | 候选归拢已成为正式术语、页面已通过最终读者验收、方法已跨第二个 Schema 泛化，或已形成企业级本体/字段字典 |
| TRADEFLOW 表语义地图模型 Gate `PASS`（替代评审返工后） | 固定 477 表 Physical Facts、233 张主体表、244 张后缀/其他表、旧 903 个分类候选、字段辅助运行、Wiki Tree、五组调查卡、一份无键值/无行样本的冻结 TEST 聚合和独立 Manifest | 表主体与变体未静默丢失；两个固定业务旅程均形成证据连通候选组；字段证据可定位到具体 Assertion；配置旅程不能冒充业务协作组；审阅页面已生成 | 全部表标签正确、TEST 快照代表生产规则、页面已完成读者验收或业务已接受 |
| `11/11 ADJUDICATED` 且自动评估无错误 | 当前 Gold 与 `stage0-tradeflow-v1b-comments-20260810` 保存运行的确定性重算 | 当前规则与 11 个已裁定样例回归一致 | 独立方法有效性、业务真实性、读者可用性或用户价值；更早的 physical run 不应与当前 Gold 混用 |
| Gate B `BLOCKED` | 评测报告与未完成的测量材料 | 旧 V1B 工程门当前未满足 | 不能据此推断只差效率测量即可完成业务目标 |
| 历史 `v1c_authorized` 字段 | 旧评测代码将 Gate B 结果映射为布尔值 | 仅能说明旧自动化曾设计过放行条件 | 不构成用户对全量扩展、LLM、Wiki 或 V1C 的授权 |

## 五维状态

| 状态维度 | 当前状态 | 已确认事实 | 尚未满足的条件 |
|---|---|---|---|
| `physical_extraction` | `PASS_WITH_BOUNDARY` | allowlist 内完成过一次真实元数据提取、对账和物理页面生成；历史运行范围与数量可定位 | 结果仍只代表对应测试环境、run 和可见权限，不代表生产业务事实 |
| `structural_cognition` | `PROTOTYPE_REGRESSION_PASS` | TRADEFLOW 分层样本可生成 Identity、Grain、Role、Relation、Evidence 与 Unknown；当前 Gold 与 comments run 重算为 11/11 | Gold 与规则并非独立业务真值；缺少第二个 Schema 验证和更强外部证据；更早 physical run 已被后续 comment 修复取代 |
| `field_semantic_investigation` | `PROTOTYPE_REPLAY_PASS_REVIEW_PENDING` | TRADEFLOW 字段语义地图可确定性生成；语义清洗候选、上下文提示、属性表达矩阵和物理字段反查均已落盘 | 同名异注释和候选语义族尚未完成批量复核；最终页面仍待用户验收；第二个 Schema 尚未验证 |
| `table_semantic_investigation` | `LIMITED_JOURNEYS_ACCEPTED_WITH_UNKNOWNS` | 477/477 表具有显式处置，五组调查卡齐备；TRS 与期权调查组均形成证据连通候选；期权 `EVENT_OF` 明示 TEST 快照限制；用户明确委托的代理读者评审接受五条固定旅程作为调查入口 | Unknown、冲突、候选关系和 TEST 聚合不能视为生产业务真值；限定旅程接受不覆盖全表语义或一般读者交付 |
| `reader_delivery` | `NOT_DELIVERED` | 已有按 Schema/表浏览的物理页面和样本评审材料 | 尚无以业务区域、对象、生命周期为入口的业务全貌，也未完成真实读者任务验收 |
| `business_acceptance` | `NOT_ACCEPTED` | 用户已确认最终目的并否定以当前工程结果代表目标完成 | 用户尚未验收一份实际业务全貌；自动评测和开发过程中的确认不能替代验收 |
| `scale_authorization` | `PROHIBITED` | 当前 Change 明确冻结 V1C、全量深度推断、Wiki/LLM 接入和方法泛化 | 必须先交付读者可用结果、通过业务验收，再由用户对具体扩展范围作独立授权 |

## 当前结论

项目拥有可复用的物理提取底座、字段语义调查地图和有界表语义候选 Projection。表语义替代评审识别并修正了固定词表、字段摘要、配置协作组和 Gate 空通过问题；TRS 的明确 `KEY_LEG_ID` 物理桥接回持仓分量，一份用户授权的冻结 TEST 聚合补足了期权事件到期权合约的候选连接。收紧后的工程 Gate 已通过并生成审阅页面。下一步是用户审阅固定旅程，而不是继续扩充标签或扩大到其他 Schema。

`build-table-semantic-map` 工程返工后的信息模型 Gate 为 `PASS`，五条固定旅程的委托代理评审为 `ACCEPT_WITH_UNKNOWNS`。任何全表读者交付、跨 Schema 扩展或业务验收声明仍需独立处置。
我之前