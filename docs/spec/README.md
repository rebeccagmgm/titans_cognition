# TITANS Cognition V1 Spec

## 1. Spec目标

本 Spec 定义只读元数据提取、结构候选、证据、评测和地图 Projection 的技术契约。项目唯一交付目标是可从业务区域、业务对象和生命周期下钻到表、粒度、键、关系、证据与 Unknown 的 TITANS 业务全貌；当前技术结果只是支撑资产，不能单独构成业务交付或验收。

## 2. 模块和依赖

```text
01 Requirements
      ↓
02 Domain Model
      ↓
03 Architecture
      ↓
04 Result Contracts ──────────────┐
      ↓                           │
05 Inference Method              │
      ↓                           │
06 LLM Integration               │
      ↓                           │
07 Evidence & Review ◀────────────┘
      ↓
08 Evaluation
      ↓
09 Map Delivery
      ↓
10 Implementation Plan

11 Security & Operations 约束全部模块
12 Open Decisions 阻止未经授权的隐含选择
```

## 3. 文档清单

| Spec | 主问题 | 实施前何时必读 |
|---|---|---|
| [01 Requirements](01-requirements.md) | 为什么做、为谁做、做到什么程度 | 所有工作 |
| [02 Domain Model](02-domain-model.md) | 各类事实、候选、证据如何区分 | 数据模型、规则、LLM、地图 |
| [03 Architecture](03-architecture.md) | 组件如何协作，哪些技术明确不引入 | 工程骨架、流水线 |
| [04 Result Contracts](04-result-contracts.md) | 每个结果集有哪些字段和不变量 | 任何读写结果文件的代码 |
| [05 Inference Method](05-inference-method.md) | Identity/Grain/Role/Relation如何形成 | 特征和推断实现 |
| [06 LLM Integration](06-llm-integration.md) | 模型能看什么、输出什么、不能做什么 | SDK和Prompt实现 |
| [07 Evidence & Review](07-evidence-and-review.md) | 证据、反证、等级和人工决定 | 候选、评审、地图 |
| [08 Evaluation](08-evaluation.md) | Gold Set和质量门槛 | 规则、模型和全量运行 |
| [09 Map Delivery](09-map-delivery.md) | 用户最终看到什么 | 渲染和验收 |
| [10 Implementation Plan](10-implementation-plan.md) | 先做什么、何时停止和扩展 | 任务规划 |
| [11 Security & Operations](11-security-and-operations.md) | 测试库、密钥、数据外发和运行约束 | 所有外部访问和运行 |
| [12 Open Decisions](12-open-decisions.md) | 哪些问题仍需显式决定 | 开始相应实现前 |

## 4. 规范优先级

1. `AGENTS.md`中的安全和范围硬边界。
2. OpenSpec `cognition-delivery-governance` 中的产品目标、完成声明和授权规则。
3. `01-requirements.md`中的用户目标、范围和非目标。
4. `04-result-contracts.md`中的数据不变量。
5. 对应专项Spec。
6. ADR记录的已接受架构决策。

如模块间出现冲突，停止实现并修改Spec，不得用代码行为隐式决定。

## 5. 架构决策记录

- [ADR-0001：V1采用文件优先认知结果包](../adr/0001-file-first-v1.md)
- [ADR-0002：类型化候选优先于万能Claim表](../adr/0002-typed-candidates-over-universal-claims.md)
- [ADR-0003：LLM只作为受证据约束的语义分析器](../adr/0003-evidence-bounded-llm.md)
- [ADR-0004：V1采用Panorama与Deep Case双轨范围](../adr/0004-dual-track-panorama-and-deep-case.md)
- [ADR-0005：认知方法先样本验证再全量扩展](../adr/0005-validate-before-scale.md)
- [ADR-0006：推断结果与关系认识论分层](../adr/0006-inference-results-and-relation-layers.md)

## 6. 完成状态与工程阶段

项目分别报告 `physical_extraction`、`structural_cognition`、`reader_delivery`、`business_acceptance` 和 `scale_authorization`。任一状态的成功不得自动提升其他状态；当前基线见 [当前状态基线](../current-status-baseline.md)。

V1A、V1B、V1C 继续作为历史工程范围标签：

- V1A Gate A 检查物理提取、对账和物理页面，不验收业务全貌。
- V1B Gate B 检查样本结构规则、Evidence、Unknown 和测量材料，不证明独立方法有效，也不授权 V1C。
- V1C 当前冻结。后续只有在读者交付存在、业务验收通过且用户对具体范围作出独立授权后，才能由新的 Change 启动。

因此，第一轮 Gate A/Gate B 通过只表示相应工程检查完成；完整产品完成只由 TITANS 业务全貌的实际交付与业务验收定义。
