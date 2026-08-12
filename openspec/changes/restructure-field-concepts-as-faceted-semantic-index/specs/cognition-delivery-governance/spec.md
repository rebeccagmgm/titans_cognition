## ADDED Requirements

### Requirement: 字段语义索引重构授权必须保持有界

项目 MAY 在本 Change 下重构已经批准的 TRADEFLOW 233 表字段概念候选索引，形成基础概念、Facet、Alias/Variant、字段绑定和 Conflict/Unknown 的 V2 结果。该授权 SHALL 仅覆盖固定输入上的方法纠偏和双向调查 Projection；它 SHALL NOT 授权其他 Schema、全量 Deep Scale、正式本体、标准字段、自动业务主题确立、业务验收替代或一般性方法泛化。

#### Scenario: V2 在固定 TRADEFLOW 范围完成

- **WHEN** 确定性 V2 已生成、测试通过并形成五类代表性概念的对比结果
- **THEN** 项目 MAY 报告字段语义索引重构已实现及该范围的可见改进，但 SHALL 继续将 reader delivery、business acceptance 和一般 scale authorization 分开报告

#### Scenario: 请求扩大到另一个 Schema

- **WHEN** 用户希望将 V2 应用于另一个 Schema、数据库或跨 Schema 合并
- **THEN** 项目 SHALL 要求新的明确范围授权和验证，不得因引擎配置化或当前 TRADEFLOW 结果自动扩大

### Requirement: 历史字段概念结果必须作为基线而非真值保留

现有字段概念 V1、其审阅页面、全树体检和 LLM Review SHALL 保持可定位且不得原地修改。V2 比较 MAY 将其作为历史候选基线，但 SHALL NOT 将 V1 聚类、LLM 建议或当前会话分析直接视为已接受业务真值。

#### Scenario: V2 替代日常导航入口

- **WHEN** 用户选择使用 V2 页面进行字段调查
- **THEN** 项目 SHALL 保留返回 V1 基线及其运行边界的定位，并 SHALL 明确 V2 仍是候选语义索引而非正式本体

