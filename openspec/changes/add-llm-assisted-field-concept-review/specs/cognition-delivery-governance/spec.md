## ADDED Requirements

### Requirement: 字段概念 LLM 审阅不得提升交付状态

字段概念 LLM 审阅 SHALL 被报告为已接受确定性试验之上的独立候选层。其完成、覆盖率、模型接受率或与确定性结果的差异 SHALL NOT 自动提升业务验收、总体准确率、跨 Schema 泛化或规模化授权状态。该层 SHALL 持续受 D-005 数据外发决策约束。

#### Scenario: TRADEFLOW 疑难样本全部完成审阅

- **WHEN** `TITANS_TRADEFLOW` 固定疑难样本均获得契约有效的模型响应
- **THEN** 项目 SHALL 只报告该样本的候选审阅完成，并 SHALL NOT 声明整个 Schema、Panorama 或其他数据库的字段概念已经验证

#### Scenario: 人工接受部分模型候选

- **WHEN** 用户接受一个或多个 LLM 修订候选
- **THEN** 项目 SHALL 保留接受决定及其适用范围，但 SHALL NOT 将人工决定改写为新的独立证据或自动推广到未审阅对象
