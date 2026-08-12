# TITANS Cognition 当前状态基线

本文件记录截至 2026-08-11 的当前解释。它不覆盖历史运行结果，而是限定这些结果能够支持的进展声明。

## 唯一交付目标

交付一张可从业务区域、业务对象和生命周期下钻到表、粒度、键、关系、证据与 Unknown 的 TITANS 业务全貌。物理目录、结构候选、Gold Set、评测器和静态页面都是支撑这一目标的工程资产，不是目标本身。

## 完成声明盘点

| 现有声明或结果 | 支撑证据 | 当前可证明 | 当前不能证明 |
|---|---|---|---|
| Panorama 提取与 Gate A `PASS` | 真实测试库元数据运行、独立 SQL 对账、Manifest 和失败记录 | 当前 allowlist 的物理对象、字段、定义和依赖已完成一次有界提取与对账 | 已建立业务区域、业务对象或生命周期全貌 |
| 静态 Panorama 与 Object Card 已生成 | Canonical Facts 的确定性 Projection | 物理对象可以按 Schema 下钻浏览 | 页面已经形成面向用户的业务认知交付 |
| TRADEFLOW V1B 候选闭环已运行 | 分层样本、确定性规则、Candidate、Evidence、Review 输出 | 样本级结构推断原型可运行，Unknown 和失败边界可保留 | 方法已理解 TRADEFLOW 业务，或可以推广到全部 TITANS |
| `11/11 ADJUDICATED` 且自动评估无错误 | 当前 Gold 与 `stage0-tradeflow-v1b-comments-20260810` 保存运行的确定性重算 | 当前规则与 11 个已裁定样例回归一致 | 独立方法有效性、业务真实性、读者可用性或用户价值；更早的 physical run 不应与当前 Gold 混用 |
| Gate B `BLOCKED` | 评测报告与未完成的测量材料 | 旧 V1B 工程门当前未满足 | 不能据此推断只差效率测量即可完成业务目标 |
| 历史 `v1c_authorized` 字段 | 旧评测代码将 Gate B 结果映射为布尔值 | 仅能说明旧自动化曾设计过放行条件 | 不构成用户对全量扩展、LLM、Wiki 或 V1C 的授权 |

## 五维状态

| 状态维度 | 当前状态 | 已确认事实 | 尚未满足的条件 |
|---|---|---|---|
| `physical_extraction` | `PASS_WITH_BOUNDARY` | allowlist 内完成过一次真实元数据提取、对账和物理页面生成；历史运行范围与数量可定位 | 结果仍只代表对应测试环境、run 和可见权限，不代表生产业务事实 |
| `structural_cognition` | `PROTOTYPE_REGRESSION_PASS` | TRADEFLOW 分层样本可生成 Identity、Grain、Role、Relation、Evidence 与 Unknown；当前 Gold 与 comments run 重算为 11/11 | Gold 与规则并非独立业务真值；缺少第二个 Schema 验证和更强外部证据；更早 physical run 已被后续 comment 修复取代 |
| `reader_delivery` | `NOT_DELIVERED` | 已有按 Schema/表浏览的物理页面和样本评审材料 | 尚无以业务区域、对象、生命周期为入口的业务全貌，也未完成真实读者任务验收 |
| `business_acceptance` | `NOT_ACCEPTED` | 用户已确认最终目的并否定以当前工程结果代表目标完成 | 用户尚未验收一份实际业务全貌；自动评测和开发过程中的确认不能替代验收 |
| `scale_authorization` | `PROHIBITED` | 当前 Change 明确冻结 V1C、全量深度推断、Wiki/LLM 接入和方法泛化 | 必须先交付读者可用结果、通过业务验收，再由用户对具体扩展范围作独立授权 |

## 当前结论

项目拥有可复用的物理提取底座和结构规则原型，当前结构回归在明确的 comments run 上一致，但尚未交付 TITANS 业务全貌。下一步不是扩大表级推断，而是先建设有界多源证据基础；其后再通过独立 Change 交付并验证业务全貌。

计划中的后续 Change 依次为：

1. `build-bounded-evidence-foundation`
2. `deliver-and-validate-business-panorama`

这些名称只表示后续规划边界；当前没有创建或授权对应实现。
