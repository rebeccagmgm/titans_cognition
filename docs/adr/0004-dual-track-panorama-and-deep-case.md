# ADR-0004：V1采用Panorama与Deep Case双轨范围

- 状态：Accepted
- 日期：2026-08-10

## 决策

V1 同时建设两个不同深度的结果范围：

1. `TITANS Panorama`：覆盖配置中明确纳入的 TITANS Schema，提供完整物理盘点、Schema 级统计、粗结构分组、依赖概况和信息缺口。
2. `TRADEFLOW Deep Case`：复用同一批物理事实，对 `TITANS_TRADEFLOW` 执行 Identity、Grain、Role、Relation、Object Family、Field Concept 和语义候选的完整认知流水线。

Deep Case内部再遵循ADR-0005的“样本验证后扩量”阶段门。

Panorama 覆盖不代表深度方法已在所有 Schema 验证。Deep Case 也不得独立重复抓取一份事实或成为整个项目的永久边界。

## 理由

用户首先需要的是 TITANS 数据资产全貌；仅做 TRADEFLOW 会缺失横向视野。反过来，把尚未验证的深度规则直接应用到所有 Schema，会制造大量看似完整但未经检验的业务判断。双轨设计把“先知道有什么”和“深入理解为什么”分开，同时共享物理事实和工程能力。

## 后果

- 范围配置、输出目录、Manifest、地图和验收必须区分 Panorama 与 Deep Case。
- Candidate、Evidence、Gold Set 和 LLM 在 V1 主要属于 Deep Case。
- 后续 Schema 可以新增为 Deep Case，而不改变 Panorama 的基本契约。
- Panorama 的精确 Schema allowlist 仍是实现前开放决策。
