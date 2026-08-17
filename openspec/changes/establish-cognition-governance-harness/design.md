## Context

项目已有 OpenSpec、阶段 Manifest、Candidate/Evidence、Review Decision、Gate 和交付状态基线；缺口是固定执行顺序和跨 Schema 配置隔离，而不是新的事实系统。Codex Skill 适合承载工作流，Custom Agent 适合隔离审阅，但两者都不能替代确定性 Runner。Hooks 需信任且可禁用，Rules 主要控制沙箱外命令，因此本切片不依赖二者。

## Goals / Non-Goals

**Goals:**

- 用最小系统代码固定语义导航治理旅程和检查点。
- 将 TRADEFLOW 局部信息隔离到 Case Pack，为后续真实 Schema 接入留下受检入口。
- 为低成本 Reviewer 留出隔离输入契约，但本切片不让 Runner 自动调用模型。

**Non-Goals:**

- 不建设通用 Agent Runtime、工作流平台、第二状态机或任意命令 Runner。
- 不实现其他认知能力 Profile、未来 Schema 模板、Evidence Scout、Hooks 或 Rules。
- 不在本 Change 内完成真实第二 Schema 验证。

## Decisions

### 1. 权威矩阵固定，Harness 报告只是 Projection

| 信息 | 唯一权威来源 | Harness 行为 |
|---|---|---|
| 目标、范围、实施任务 | OpenSpec Change | 引用 Change 与 Artifact |
| 运行和输出事实 | 现有 Manifest | 校验并引用哈希 |
| 领域候选处置 | 现有 Review Decision | 只引用，不生成副本 |
| 读者/业务/规模化状态 | 当前状态基线 | 原样引用 |
| Harness 检查观察 | `governance-run-report.json` | 带 `derived_from` 的不可变 Projection |

报告不包含独立 `ACCEPT` 或 `TRADEFLOW_VALIDATED`。它只报告检查点 PASS/FAIL、来源冲突和缺口，删除后可从权威来源重建。

### 2. 窄 Runner 使用固定操作注册表

```text
Workflow Profile + Schema Case Pack
                 ↓ schema/preflight
       semantic-navigation operation registry
                 ↓ typed dispatch, no shell
 preflight → stage → verify → review-pack → verify-review → finalize
                 ↓
      derived governance run report
```

操作注册表由项目代码维护，只暴露首个语义导航切片需要的操作；Profile 使用操作 ID，Case Pack 使用类型化参数。路径先解析为绝对路径，再检查 workspace root、允许目录与 Windows Reparse Point。授权使用权威记录引用和可用范围，不接受 Case Pack 自证。

### 3. 一个 Profile 与一个真实 Case

本 Change 只实现 semantic-navigation Workflow Profile 和 TRADEFLOW Case Pack。Profile 不出现 TRADEFLOW 词汇或路径；Case Pack 引用现有语义导航配置、冻结输入和 Artifact。结构显著不同的合成 Case 只验证契约隔离。

职责边界修正：当前治理用例是字段语义导航，不是表语义地图。TRADEFLOW Case Pack 只冻结字段语义 Artifact（`FROZEN_INPUTS`、`SEMANTIC_CONFIG`、`FIELD_MANIFEST`、`CONTEXT_MANIFEST`），不再要求 Stage 4 表语义 Manifest；Profile 的 `required_artifact_roles` 同样不含 `TABLE_MANIFEST`。表只作为字段所在位置展示，其语义地图由未来独立 Case Pack 治理；Runner 仍保留对 `TABLE_MANIFEST` 角色的校验支持，合成隔离 Fixture 继续携带该角色以证明能力基线。

真实第二 Schema 仍由 `D-010` 选择，并通过后续独立 Change 接入。只有真实运行、独立审阅和读者任务证据才能支持跨 Schema 结论。

### 4. Skill 是薄入口，Reviewer 是唯一新增 Agent

`.agents/skills/govern-cognition-work` 只负责选择 Profile/Case、调用单一 Runner、展示失败/升级结果，不手工执行或重新排列阶段。第一版只配置 `counterexample_reviewer`，输入与实施上下文隔离；不增加 Evidence Scout，避免重复已有确定性 Evidence Resolver。

### 5. 首个切片保持零模型执行

Profile 和 Case Pack 的当前预算均固定为 `model_calls=0`、`tokens=0`，Runner 拒绝任何非零模型用量。歧义触发器仅用于校验独立 Reviewer 输入是否有明确理由；Reviewer 响应作为外部工程审阅 Artifact 被校验和引用，Runner 不负责发起调用或声称测量其成本。

自动低成本模型执行、跨 REWORK 累计用量账本和缓存命中属于后续独立 Change。这样保留未来入口，但不在尚无授权和真实第二 Schema 的阶段建设模型运行平台。

### 6. 固定点由 Runner 保证，不使用 Hooks/Rules

Skill 只能调用 Runner 的高层入口，不能调用内部阶段跳过校验。Hooks 即使将来增加，也只能调用同一入口作为便利；Rules 不承担领域或完成门禁。本 Change 不创建相应文件，避免未证明的宿主耦合。

## Risks / Trade-offs

- [Risk] 窄 Runner 仍被扩展成通用平台 → 注册表只接受语义导航操作，新增能力必须独立 Change。
- [Risk] 合成 Case 延续 TRADEFLOW 形状 → Fixture 强制缺失元数据、不同命名顺序、歧义关系和误导名称，并仅给隔离检查结论。
- [Risk] Reviewer 成本失控 → Runner 保持零模型执行；自动 Reviewer 与累计成本治理留给后续独立 Change。
- [Risk] 当前语义导航 Change 尚未用户验收 → Harness 原样引用状态，不替换页面或推动完成。

## Migration Plan

1. 先实现 Schema、权威冲突 Fixture 和固定操作注册表。
2. 实现 Runner 的固定检查点和派生报告，验证不依赖 Codex。
3. 接入 semantic-navigation Profile 与 TRADEFLOW Case Pack，读取现有 Artifact 而不改算法。
4. 用 skill-creator 初始化薄 Skill，并配置一个只读 Reviewer Agent。
5. 运行 TRADEFLOW 与合成隔离检查，完成独立 Harness 审阅。
6. 删除 Skill/Agent/Profile/Case 即可回滚；现有领域结果保持不变。
