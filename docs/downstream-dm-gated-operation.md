# 下游表探寻与 DM 门控操作文档

## 1. 这项工作为什么做

之前已经完成了模型层任务 Fact，以及贴源表到第一层下游的平台清单。本阶段要回答的是：

```text
已确认的下游种子
  → 平台 DOWNSTREAM 血缘
  → 更深层下游表
  → 到达 DM 层时停止或穿透
  → 形成可审阅的下游表范围和 Machine Facts
```

这样做有三个目的：

1. 不把“贴源 → 第一跳”误认为完整的模型层下游；
2. 不用本地任务 Fact 的名称匹配替代平台真实血缘；
3. 将平台边事实、表详情事实和 DM 门控后的范围事实分开保存，便于审计和后续合入。

本阶段是元数据探寻，只读取平台血缘和表详情，不读取业务数据行，不执行调度任务。

## 2. 当前探寻范围

本次递归运行使用的种子不是 1003 个任务目录本身，而是平台侧已经整理出的 483 个下游表种子：

```text
output/downstream-dive-20260818/seed-scope.csv
```

该文件由以下平台清单整理得到：

```text
output/titans-collection-20260815/data/downstream-tables-tasks.csv
output/titans-collection-20260815/data/downstream-odata.csv
output/titans-collection-20260815/data/downstream-dpl.csv
```

种子生成脚本：

```text
scripts/prepare_downstream_seed_scope.py
```

运行方式：

```powershell
python scripts/prepare_downstream_seed_scope.py
```

脚本从 `downstream-tables-tasks.csv` 取种子 GUID、表名和库名，再回连 OData/DPL 上游来源；同时用 1003 个任务目录中的 `dataset-io.jsonl` 做 WRITE 资产辅助对账。

注意：

- `seed-scope.csv` 是平台侧 483 个种子的范围事实；
- 它不是 1003 个任务目录的完整替代品；
- 它也不是最终递归下游清单；
- 之前基于 11 张 `dm_otc_n` 表的试跑不属于本次范围。

## 3. 探寻输入和输出

递归运行目录：

```text
output/szdata-recursive-downstream-20260818-sharded/
```

主要输入和输出：

| 路径 | 作用 |
|---|---|
| `query-results/part-*.csv` | 每个 GUID 的血缘查询状态 |
| `direct-edges/part-*.csv` | 已发现的直接 parent → child 边 |
| `table-details/part-*.csv` | 表详情、库名和失败状态 |
| `range/part-*.csv` | 递归完成后生成的 DM 门控范围；运行中可能不存在 |
| `manifest.json` | 递归最终状态和计数；没有它不能声称闭包完成 |
| `dm-gated-resume.log` | 低 token 进度日志 |

旧边分片可能只有五列：

```text
parent_guid,parent_name,child_guid,child_name,child_type
```

新边分片可以包含库名列。旧边没有库名时，必须通过 `table-details` 或明确的本地唯一映射补齐，不能从普通表名强行猜库。

## 4. 实际探寻算法

### 4.1 读取已有分片

使用：

```text
scripts/crawl_szdata_downstream.py
```

带 `--resume` 时：

1. 读取已有 `query-results`，成功查询不重新查询；
2. 读取已有 `direct-edges`，按 `(parent_guid, child_guid)` 去重；
3. 读取已有 `table-details`，成功详情按 GUID 复用；
4. 从 483 个种子重新计算当前可达图；
5. 只把还需要查询的节点放入下一批。

### 4.2 补齐表库名

平台边中经常只有未限定表名，例如：

```text
ref_fast_trs
```

DM 门控需要知道数据库名，因此按以下顺序解析：

1. 已持久化的 `table-detail` 成功结果；
2. 边分片中已有的 `child_db_name`；
3. 种子清单已有的库名；
4. `machine-facts/registry/tasks/*/bundle/dataset-io.jsonl` 中唯一的表名到库名映射；
5. 仍无法确定时调用：

```powershell
opencli szdata table-detail --guid <guid> -f json
```

每批详情结果保存为：

```text
output/szdata-recursive-downstream-20260818-sharded/table-details/part-*.csv
```

详情失败必须保存为 `COMMAND_FAILED`、`TIMEOUT` 或其他明确状态，不能当成普通非 DM 节点。

### 4.3 DM 门控规则

对每个种子沿直接边展开：

| 节点分类 | 是否记录 | 是否继续展开 |
|---|---:|---:|
| 普通非 DM 表 | 仅当后续到达 DM 后进入范围 | 是 |
| `dm_*` 且不是 `dm_otc_n` | 是，作为 DM 命中 | 否 |
| `dm_otc_n` | 是，作为 DM 命中 | 是 |
| 到 DM 前库名未知 | 不进入已确认范围 | 否，等待补证据 |
| 到 DM 后库名未知 | 可保留已确认边 | 否 |
| 非表节点 | 作为终端观察保留 | 否 |

最终范围只保留已经到达某个 DM 的种子—下游关系，不输出完整路径，只保留最短跳数和首个 DM 命中信息。

### 4.4 为什么会有“下一轮”

详情补齐不是一次固定清单就结束：

1. 第一轮先判定当前可达图中的未知节点；
2. 某些节点判定为普通库或 `dm_otc_n` 后，允许继续穿透；
3. 穿透后会发现原来没有进入待判定集合的新 child 节点；
4. 脚本重新计算可达图，将新节点加入下一轮。

因此下一轮的目标集合可能大于上一轮，但成功详情不应重复查询。失败详情可以按显式重试策略重试；失败不能被当成已分类成功。

进度日志中的：

```text
detail_resolved=5480/5684
```

表示本轮已处理的详情查询数，不表示 5480 个都成功，也不表示最终唯一 GUID 数。最终应查看 `table-details` 的唯一 GUID 和 status 分布。

## 5. 运行命令

### 5.1 从下游表实时解析真实 task_id

`table-details/part-*.csv` 只有表 GUID、库名和物理表名，不能直接作为 Machine Facts 的 task 归属。需要用实时 SZData 逐表查询：

```powershell
python scripts/resolve_downstream_task_ids.py `
  --input output/szdata-recursive-downstream-20260818-sharded/table-details/part-00001.csv `
  --output output/downstream-dive-20260818/part-00001-task-map.csv
```

处理分片目录的有界范围时，按文件名排序并显式限制数量，例如前 50 个分片：

```powershell
python scripts/resolve_downstream_task_ids.py `
  --input output/szdata-recursive-downstream-20260818-sharded/table-details `
  --max-input-files 50 `
  --output output/downstream-dive-20260818/first-50-task-map.csv `
  --interval-seconds 10
```

脚本约束：

- 一次只调用一个 `task-inspect --table`，固定 `--concurrency 1`；
- 如果输入只有 GUID、缺少 `qualified_name`，记录为 `INPUT_INVALID / MISSING_QUALIFIED_NAME`，不发起空表名查询；
- 默认查询间隔 15 秒，避免连续触发用户级限流；
- 明确区分 `SUCCESS`、`NO_TASKS`、`PARTIAL`、`RATE_LIMITED`、`TIMEOUT` 和命令/解析失败；
- 每条结果查询后立即 checkpoint 到 CSV；
- 后续重跑跳过已确认的 `SUCCESS`/`NO_TASKS`，只处理未解决项；
- 遇到限流先退避，重试仍限流就停止，保留断点，不把限流写成 `NOT_FOUND`。
- Windows 下自动使用可由 Python 直接启动的 `opencli.cmd` shim。

默认参数可以按实际限流情况调整：

```text
--interval-seconds 15
--rate-limit-backoff-seconds 120
--rate-limit-retries 1
```

该脚本只生成表到 task 的映射证据，不生成或合并 Machine Facts。只有映射状态经过检查后，才进入后续 staging 生成。

当前使用的典型续跑命令：

```powershell
python scripts/crawl_szdata_downstream.py `
  --seeds output/downstream-dive-20260818/seed-scope.csv `
  --output output/szdata-recursive-downstream-20260818-sharded `
  --resume `
  --workers 3 `
  --batch-size 20 `
  --rows-per-part 10000 `
  --timeout 45 `
  --retries 1
```

烟测可以限制种子和查询节点：

```powershell
python scripts/crawl_szdata_downstream.py `
  --seeds output/downstream-dive-20260818/seed-scope.csv `
  --output output/szdata-recursive-downstream-dm-gated-smoke10-20260818 `
  --limit-seeds 10 `
  --max-queried-nodes 10 `
  --workers 2 `
  --batch-size 5 `
  --timeout 20 `
  --retries 0
```

运行期间只看日志尾部，不把完整日志复制到对话：

```powershell
Get-Content output/szdata-recursive-downstream-20260818-sharded/dm-gated-resume.log -Tail 1
```

确认是否完成：

```powershell
Test-Path output/szdata-recursive-downstream-20260818-sharded/manifest.json
```

没有最终 `manifest.json` 时，只能称为部分运行，不能称为平台闭包完成。

## 6. Machine Facts 落盘

平台递归结果先单独落到 staging，不直接污染正式任务 Fact：

```text
machine-facts/staging/downstream-dm-gated-20260818/
```

当前采用原有 Machine Facts 的 bundle 组织方式：

```text
machine-facts/staging/downstream-dm-gated-20260818/
├── indexes/
└── registry/tasks/<seed-or-run-id>/
    ├── analysis-status.json
    └── bundle/
        ├── lineage-edges.jsonl
        ├── table-details.jsonl
        ├── downstream-scope.jsonl
        └── manifest.json
```

三类事实含义不同：

1. `lineage-edges.jsonl`：平台已经返回的直接血缘边；
2. `table-details.jsonl`：表 GUID、库名、详情查询状态；
3. `downstream-scope.jsonl`：经过 DM 门控后的阶段性范围。

staging Fact 统一标记：

```text
fact_status=PROVISIONAL
closure_status=PARTIAL
```

只有在递归没有待展开节点、查询和详情失败已经单独处置、DM 规则校验通过后，才可以生成最终范围投影。staging 不自动合入正式 `machine-facts/registry/tasks/`。

## 7. 已确认边、表节点和范围的区别

`direct-edges/part-*.csv` 中的 parent/child 表，可以先提取为独立的表节点事实：

```text
table_guid
table_name
table_type
db_name
observed_as_parent
observed_as_child
db_resolution_status
evidence_file
```

但要注意：

- 一个 edge 分片不是完整表清单；
- 表节点事实不等于 DM 门控后的下游范围；
- 表名出现不等于库名已确认；
- 表详情失败不能被当成非 DM；
- 最终去重表清单应从所有稳定 edge 分片合并，而不是只读 `part-00001.csv`。

## 8. 校验和运行审计

每次运行至少核对：

1. 种子数量是否仍为当前配置的 483；
2. query GUID 是否按 GUID 去重；
3. direct edge 是否按 parent/child GUID 去重；
4. table-detail 是否区分 SUCCESS、失败和未知；
5. 已成功详情是否被重复查询；
6. 失败或未知节点是否错误穿透；
7. `dm_otc_n` 后是否继续；
8. 其他 `dm_*` 后是否停止；
9. 没有到达 DM 的分支是否进入 scope；
10. staging manifest 的 hash、行数和状态是否一致。

可使用已有审计脚本检查旧分片：

```text
scripts/audit_sharded_downstream.py
```

审计输出目录：

```text
output/szdata-recursive-downstream-20260818-sharded/audit/
```

## 9. 当前已知问题和处理要求

### 9.1 详情进度名称不准确

`detail_resolved=x/y` 的 `x` 是本轮已经处理的查询数，不是成功详情数。最终报告必须按唯一 GUID 和 status 重新统计。

### 9.2 失败详情不能穿透

任何 `table-detail` 失败或库名未知的节点，在到达 DM 前都不能被当成普通库继续展开。否则会把未知分支误纳入平台闭包，造成过度扩散。

该规则已在当前脚本中收紧，并由：

```text
tests/test_crawl_szdata_downstream.py
```

锁定最小回归行为。修复后的脚本满足：

```text
detail_status != SUCCESS
  → db_resolution_status = UNRESOLVED
  → 不继续穿透
```

### 9.3 当前 staging 不是最终结果

staging machine-fact 可以边跑边更新，但它只代表某个输入分片快照。递归继续发现新节点后，必须重新生成或增量刷新 staging manifest 和范围 Fact。

## 10. 完成标准

本次下游探寻只能在以下条件都满足后声明完成：

- 所有种子和可达节点都已按 DM 规则处理；
- 没有未处理的可展开节点；
- 查询失败、详情失败和权限/限流异常均已保留并单独报告；
- 失败或未知节点没有被错误穿透；
- `dm_otc_n` 穿透规则验证通过；
- 其他 `dm_*` 停止规则验证通过；
- 已确认边、表详情和范围 Fact 的证据链可回指源分片；
- 最终 `manifest.json`、行数和 hash 一致；
- 最终结果与 staging 结果边界清楚；
- 不把平台下游闭包误称为 1003 个任务或 1001 张模型表的完整范围。
