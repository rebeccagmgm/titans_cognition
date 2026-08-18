## Why

当前 sql-static-lineage 产物已经证明字段溯源和逻辑计划事实可以被提取，但结果仍按具体案例组织。现在需要建立稳定、可重放的一任务一份当前事实包，让后续分析复用同一套可观察 SQL 事实，同时避免把跨任务绑定、业务解释或旧分析版本误当成当前事实。

## What Changes

- 新增文件优先的 `machine-facts/` 本地分析仓库，保存内容寻址且不可变的 SQL/Schema 快照，以及每个 `task_id` 唯一的一份当前 Core Bundle。
- `task_id` 是当前任务事实的唯一仓库身份；`sql_sha256`、Schema Bundle、方言、Parser、Adapter、Contract 和分析配置只作为当前输入及生成来源。任何来源变化都重建并替换该任务当前 Bundle，不保存旧 Bundle、Fact Diff 或 Edition。
- 新增任务级 `analysis-status.json`，记录当前请求的输入指纹和 `ANALYZING`、`SUCCESS` 或 `FAILED` 状态。失败状态必须持久化；旧成功 Bundle 即使为恢复目的暂时保留，也不得继续进入当前发现索引。
- 将阶段 1 字段溯源和阶段 2 逻辑计划沉淀为类型化 JSONL：语句、Dataset I/O、关系节点与边、字段表达式节点、任务内字段血缘边、Schema 引用和显式 Unknown。
- 新增仅由任务状态和已校验 Bundle 重建的当前任务索引；一项任务最多产生一条当前成功记录。
- 新增 Schema、引用、数量、Hash、Span 和确定性重放校验，并采用适合 Windows 本地单写者场景的可恢复发布流程，不声称非空目录替换具有不可证明的原子性。
- 使用当前六任务指标案例和至少一个独立于该指标 Profile 的本地分析输入验证 Generic Writer；指标角色、Focus Output、最小因果路径和跨任务边不得进入 Core Bundle。
- 保留证据来源和确定性边界，包括区分 SQL Plan 观察到的读取与 Profile 声明的写入。
- V1 不定义或实现通用 Derived Package、Projection、Capability Negotiation、阶段 3 Grain/Cardinality、跨任务字段拼接、ProductionUnit、指标解释或查询层；这些能力只有出现真实 Consumer 后才能通过独立 Change 定义。

## Capabilities

### New Capabilities

- `sql-machine-facts`：定义以 `task_id` 为唯一当前身份的本地任务级 SQL 机器事实包、当前分析状态、类型化阶段 1/2 数据集、可恢复替换、失败保留、校验和当前任务索引。

### Modified Capabilities

无。

## Impact

- 影响范围仅限本地 `sql-static-lineage/` 分析脚本、契约、验证 Fixture，以及生成到 `machine-facts/` 下的结果。
- `machine-facts` 是 SQL 静态分析产生的 Derived Observation 底座，不修改 Panorama Physical Facts、Cognitive Candidate、Review Decision 或现有案例 Projection；任何正式接入由后续 Consumer Change 负责。
- 现有案例产物保持不变，只作为迁移输入和验证证据。
- V1 不建设历史 Registry、Fact Diff、Edition、通用扩展框架或服务端能力；只有输入快照不可变，当前事实包属于可重建物化结果。
- 不引入数据库写入、业务数据行查询、外部模型调用、远程服务、图数据库或服务端依赖。
- 生成的 SQL/Schema 快照与机器事实包只保存在本地且不得提交；只有经过刻意脱敏的 Fixture 可以进入版本控制。
