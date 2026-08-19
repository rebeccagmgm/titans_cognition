## Why

下游 `table-details` 产出只有表 GUID、库名和物理表名，不能直接作为正式 Machine Facts 的 task 归属。此前按 seed 任务字段生成 staging 的做法会把已有 task 误当成新增范围，并给后续合并带来覆盖风险；现在需要先用实时 SZData 逐表解析真实 task_id，并保留未解决状态。

## What Changes

- 新增一个只读的下游表到真实 Horae `task_id` 映射能力。
- 使用 `task-inspect --table --include detail` 串行查询，每次只查一个表，并对数据源后缀做受控规范化。
- 默认采用保守查询间隔，识别限流、超时、鉴权、解析失败和部分成功，不把查询失败写成 `NOT_FOUND`。
- 将每条映射结果 checkpoint 到可恢复的 CSV；后续运行跳过已确认结果，只重试未解决对象。
- 支持对分片目录按文件名排序并限制最多处理的 `part-*.csv` 数量，避免误跑全量目录。
- 保留 `SUCCESS`、`NO_TASKS`、`PARTIAL`、`RATE_LIMITED` 等状态及证据等级，供后续 staging 生成使用。
- 补充操作文档和本地模拟测试。
- 不自动生成 Machine Facts，不修改正式 `machine-facts/registry/tasks`，不执行 merge。

## Capabilities

### New Capabilities

- `downstream-task-id-resolution`: 从已落盘的下游表详情证据出发，受控调用实时 SZData，生成可恢复、证据分层的表到 task_id 映射。

### Modified Capabilities

无。现有 Machine Facts 合并契约不在本 change 内修改。

## Impact

- 代码：`scripts/resolve_downstream_task_ids.py`。
- 测试：`tests/test_resolve_downstream_task_ids.py`，使用模拟 OpenCLI 响应，不依赖实时平台。
- 文档：`docs/downstream-dm-gated-operation.md`。
- 外部依赖：只读调用现有 `opencli szdata task-inspect`；Windows 下使用可由 Python 启动的 `opencli.cmd`。
- 产物：在 `output/` 下生成 task 映射 CSV，不写入正式 Machine Facts。

## Current Progress

截至 2026-08-19：

- 已完成串行查询脚本、断点 checkpoint、限流分类、Windows OpenCLI 入口兼容和 `--max-input-files` 分片边界。
- 已修正输入覆盖问题：只有 GUID、缺少 `qualified_name` 的记录标记为 `INPUT_INVALID / MISSING_QUALIFIED_NAME`，不再调用空表名。
- 已通过本地 pytest、py_compile、ruff 和严格 OpenSpec 校验。
- 前 50 个分片去重后 964 个对象；当前 v2 checkpoint 已得到 501 个有效查询结果，状态为 `SUCCESS=437`、`NO_TASKS=34`、`PARTIAL=8`、`COMMAND_ERROR=22`，另有 `INPUT_INVALID=251`、`PENDING=212`。
- 已提取 538 个 task_id token，其中 60 条记录包含多个 task_id；本批没有 `RATE_LIMITED`。
- 当前结果文件为 `output/downstream-dive-20260818/first-50-task-map-v2.csv`。原 `first-50-task-map.csv` 曾因打开占用导致 Windows 原子替换失败，未覆盖原文件。
- 没有修改正式 registry，也没有 merge；`COMMAND_ERROR` 尚未完成原因归类和 task bundle 校验，不能据此生成或合并 staging Machine Facts。
