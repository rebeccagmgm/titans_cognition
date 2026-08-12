# ADR-0005：认知方法先样本验证再全量扩展

- 状态：Accepted
- 日期：2026-08-10

> 2026-08-11 当前解释：本 ADR 保留为历史工程分段决策，但“Gate B + 用户确认即可启动 V1C”的授权语义已被 `rebaseline-titans-cognition-goal` 取代。Gate B 只保留结构规则回归用途；V1C 当前冻结，必须在读者交付、业务验收和独立规模化授权全部成立后通过新的 Change 启动。

## 决策

V1按三道强制阶段门实施：

1. V1A先完成TITANS Panorama物理全貌。
2. V1B只在TRADEFLOW分层样本实现并评测`Identity → Grain → Role → Relation → Evidence`闭环。
3. V1C只有在Gate B通过并经用户确认后，才扩展TRADEFLOW全量并启用Object Family、Field Concept、Wiki、SQL深度Lineage和LLM语义辅助。

完整结果契约可以提前定义目标形态，但不得据此预建未启用阶段的空框架、空数据集或通用平台抽象。

## 理由

本工程的技术栈本身较轻，主要风险来自一次性承担过多认知类型和全量对象。未经Gold Set和用户效用验证就扩展477张表，会扩大错误、增加评审负担，并掩盖Identity、Grain等基础方法是否真正有效。阶段门使每次新增复杂度都由可见结果和证据触发。

## 后果

- 第一轮工程承诺为V1A和V1B，不包含V1C。
- V1A完成后已经形成可使用的全貌地图，不必等待语义层。
- V1B失败时优先修正方法，不以扩大样本或LLM解释掩盖问题。
- V1C仍在同一工程内复用已有事实和契约，不另建系统。
