## Why

TITANS Cognition 后续要接入多个 Schema，而当前 TRADEFLOW 语义导航治理仍依赖人工串联取证、候选、反例审阅、修订和验证。直接复制 TRADEFLOW 流程会放大局部假设；直接建设通用 Agent 平台又会重复项目已有 OpenSpec、Manifest、Candidate、Evidence 和 Review 状态，因此需要先做一个可验证的跨 Schema 薄切片。

## What Changes

- 建立明确的权威矩阵：OpenSpec 管意图和实施范围，现有 Manifest 管运行/Artifact 事实，现有 Review Decision 管领域处置，当前状态基线管读者/业务/规模化状态；Harness 报告只做带 `derived_from` 的不可变审计 Projection。
- 增加窄化的确定性 Runner。它只执行代码内注册的语义导航操作 ID 和类型化参数，在预检、每阶段后、审阅前、审阅后、报告定稿前强制验证；Profile 不得携带任意 Shell。
- 将复用契约拆成“语义导航 Workflow Profile × Schema Case Pack”：Profile 定义固定旅程和 Gate，Case Pack 定义具体 Schema 范围、批准的 Manifest/配置、数据类别、局部词汇和授权引用。
- 仅实现首个纵向切片：语义导航 Profile、TRADEFLOW Case Pack、真实现有 Artifact 的审计报告、一个薄仓库 Skill 和一个隔离的反例审阅 Agent。
- 本切片强制 Runner 模型调用数为 0；歧义触发器只用于形成隔离的 Reviewer 输入。Reviewer 由 Codex 工程审阅适配执行，不由 Runner 自动发起，也不冒充领域 Review Decision。未来若需要 Runner 自动调用低成本模型，必须通过独立 Change 补齐数据外发授权、跨重试累计用量账本和缓存契约。
- 使用结构显著不同的合成非 TRADEFLOW Fixture 只做 `CONTRACT_ISOLATION_CHECK`；真实第二 Schema 由 `D-010` 后续独立 Change 接入，未完成前不得宣称跨 Schema 有效。
- 本 Change 不增加 Evidence Scout、未来 Schema 模板、Hooks 或 Rules；这些只有在首个切片证明真实缺口后才能另行提案。

## Capabilities

### New Capabilities

- `cognition-governance-harness`: 定义复用现有权威结果的窄化语义导航 Runner、Workflow Profile、Schema Case Pack、固定验证点、独立反例审阅、成本控制和派生审计报告。

### Modified Capabilities

无。现有领域和交付治理规范保持权威，本能力只消费和验证其结果。

## Impact

- 实现范围限于 Profile/Case/报告 Schema、窄化 Runner 与校验、语义导航/TRADEFLOW 配置、一个 Skill、一个只读 Reviewer Agent 和聚焦测试。
- 不新增数据库、服务、队列、通用 Agent 框架、任意命令 DSL、Provider 注册中心或第二套状态机；不修改语义导航算法和现有页面入口。
- 当前项目仍禁止业务数据行扫描和通用外部模型调用；Case Pack 的自我声明不能替代已有授权记录。
