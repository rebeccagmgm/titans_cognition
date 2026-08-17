## Context

现有 `minimal-causal-path-assembler.ts` 已能从案例 graph JSONL 装配结构化路径，但这些 graph JSONL 由指标案例脚本重新解析 SQL 生成。Machine Facts Bundle 已包含同等的任务级关系、字段表达式、输入字段、数据集 IO 和结构化 Relation 原始事实。

## Goals / Non-Goals

**Goals:**

- 将现有路径装配能力接到 Machine Facts Bundle。
- 保持路径结果为 `machine-facts/projections/` 下的派生结果。
- 用 Profile 声明目标字段和路径类型，用 Bundle 提供结构化证据。
- 保留现有 `COMPLETE/PARTIAL/PASS` 和证据边界。

**Non-Goals:**

- 不把 `VALUE_FLOW` 或 `ROWSET_CONTROL` 写进 Canonical Bundle。
- 不在投影层重新解析 SQL、调用 SZData 或读取业务数据。
- 不把 Profile 角色、Focus Output 或指标目标字段提升为通用物理事实。
- 不声称生成完整跨任务血缘或业务正确性证明。

## Decisions

1. **适配而非复制解析**：新增 Bundle → GraphInputs 适配层，保留现有 assembler 的路径逻辑；避免第二次运行 SQL 解析器。
2. **派生边留在 Projection**：`TASK_DATASET_FLOW`、字段写入目标、表达式馈入和 Relation-to-field 读取边由 Bundle 与 Profile 派生，带明确 Projection provenance，不写入基础 JSONL。
3. **上游 Hash 绑定**：Projection Manifest 记录 Profile Hash 和每个 Task Manifest Hash；加载时同时校验 Profile 任务 SQL Snapshot SHA-256 与 Bundle Manifest 的 `inputs.sql_sha256`，防止新 Profile 与旧事实混用。
4. **输出隔离**：结果写入 `machine-facts/projections/minimal-causal-paths/<case_id>/`，与 `registry/tasks/*/bundle` 分离。

## Risks / Trade-offs

- [Profile 声明的目标字段可能无法证明物理输出绑定] → 通过 Projection provenance 和 Gap 保留声明边界，不升级为 Canonical Lineage。
- [适配层重建的 GraphInputs 与旧案例 graph 略有差异] → 用当前两条路径的集成测试和既有验证器共同校验。
- [Projection 被误读为事实] → 单独 Manifest、目录和 boundaries 字段，明确其 Derived Projection 身份。

## Migration Plan

1. 从已校验 Bundle 构造 GraphInputs。
2. 复用现有最小路径 assembler，生成 Projection JSON 和 Manifest。
3. 保留旧案例 graph JSONL 作为对照和回归输入。
4. 后续 Consumer 逐步改为读取 Projection，不修改基础 Bundle。
