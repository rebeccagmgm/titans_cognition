# TITANS Cognition V1 Spec

## 1. Spec目标

本Spec定义如何在一次只读元数据采集中，同时建立当前纳入 TITANS Schema 的全貌地图，并对 `TITANS_TRADEFLOW` 执行首个深度业务语义逆向案例，交付一套可检查的 Cognition Result Bundle。它面向后续实现Agent、评审人和业务使用者，不是实现代码或长期平台蓝图。

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
2. `01-requirements.md`中的用户目标、范围和非目标。
3. `04-result-contracts.md`中的数据不变量。
4. 对应专项Spec。
5. ADR记录的已接受架构决策。

如模块间出现冲突，停止实现并修改Spec，不得用代码行为隐式决定。

## 5. 架构决策记录

- [ADR-0001：V1采用文件优先认知结果包](../adr/0001-file-first-v1.md)
- [ADR-0002：类型化候选优先于万能Claim表](../adr/0002-typed-candidates-over-universal-claims.md)
- [ADR-0003：LLM只作为受证据约束的语义分析器](../adr/0003-evidence-bounded-llm.md)
- [ADR-0004：V1采用Panorama与Deep Case双轨范围](../adr/0004-dual-track-panorama-and-deep-case.md)
- [ADR-0005：认知方法先样本验证再全量扩展](../adr/0005-validate-before-scale.md)
- [ADR-0006：推断结果与关系认识论分层](../adr/0006-inference-results-and-relation-layers.md)

## 6. V1完成定义

V1采用强制阶段门：

```text
V1A Panorama
    ↓ 物理覆盖与全貌地图验收
V1B TRADEFLOW Deep Sample
    ↓ 认知闭环与Gold Set验收
V1C TRADEFLOW Deep Scale
```

现阶段工程承诺是先完成 V1A 和 V1B。V1C 的目标契约保留在 Spec 中，但只有 V1B 质量门通过并由用户确认后才启动。

以下是完整V1（含V1C）的最终完成定义；第一轮开工以Gate A和Gate B为完成边界：

- Panorama Schema allowlist 内全部可见物理对象已纳入，提取失败和权限缺口显式列出，并可按 Schema 查看对象类型、字段、注释和依赖概况。
- TRADEFLOW 当前目标表数已现场复核；其中每个目标表均可生成物理事实完整的 Object Card。深度推断证据不足时允许输出Unknown，V1A物理Card不强制业务解释。
- Identity、Grain、Role、Family、Field Concept和Relation候选均使用类型化结果契约。
- 每个认知候选均可追溯到方法和证据，支持与反证分开。
- LLM只产生通过结构校验且引用有效证据ID的候选。
- Gold Set分任务评测完成，错误案例和无法判断案例被保留。
- 最小静态地图能够从 TITANS 全貌下钻到 Schema；对 TRADEFLOW 可继续下钻到对象族、对象、字段概念、关系和原始证据。
- 未引入V1非目标中的平台能力。
