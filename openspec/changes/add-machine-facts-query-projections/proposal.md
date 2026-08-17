## Why

Machine Facts 已经能保存任务、关系、字段表达式和列血缘，但现有最小因果路径装配器仍依赖指标案例专用 graph JSONL。需要把这项 Consumer 能力接到 Bundle 上，同时保持路径结果是派生投影而不是基础事实。

## What Changes

- 增加 Machine Facts Bundle 到 GraphInputs 的确定性投影适配。
- 复用现有 `VALUE_FLOW` 和 `ROWSET_CONTROL` 最小路径装配器。
- 将投影结果和投影 Manifest 写入 `machine-facts/projections/`，不写回任务 Bundle。
- 记录 Profile Hash 和上游 Task Manifest Hash，保留投影的证据边界。
- 增加临时 Bundle 集成测试，验证当前两条最小路径仍可完整装配。

## Capabilities

### New Capabilities

- `machine-facts-query-projections`: 从任务级 Machine Facts 生成可复用的结构化查询/路径投影。

### Modified Capabilities

无。

## Impact

- 新增 `sqllens/scripts/query/` 投影适配和 CLI。
- 新增 `machine-facts/projections/` 派生产物。
- 不改变 `registry/tasks/*/bundle` 的 Canonical Fact 身份和文件边界。
- 依赖现有本地 JSONL、Profile 和 Machine Facts Manifest，不增加远程服务或数据库。
