# 从平台下游种子继续下钻

## 目的

本说明固定“先整理存量、再决定是否继续调用 SZData”的范围和证据顺序。

本阶段不调用 SZData，不声称已经完成新的递归下钻；只整理仓库已有的平台侧 CSV、table-detail 结果和 Task Machine Facts，形成可审阅的种子范围。

## 证据分工

### 平台侧证据

目录：`output/titans-collection-20260815/data/`

- `downstream-odata.csv`：OData 贴源表到第一层下游的 DOWNSTREAM 关系；
- `downstream-dpl.csv`：DPL 侧贴源表到第一层下游的 DOWNSTREAM 关系；
- `downstream-tables.csv`：两侧下游表去重汇总；
- `downstream-tables-tasks.csv`：下游表的 GUID、库名和 Horae 任务补充信息。

其中 `downstream-tables-tasks.csv` 不是完整路径表。它是继续下钻的种子清单；上游来源需要回连 `downstream-odata.csv` / `downstream-dpl.csv` 才能说明该种子来自 OData 还是 DPL。

例如：

```text
OData 贴源 d_ref_fast_trs
  → 下游 ref_fast_trs
  → table-detail 解析为 PDATA_NDS.REF_FAST_TRS
```

相对于 OData 贴源表，`ref_fast_trs` 是第一跳下游；相对于更早的源头，它可以是整体链路的第二跳。两种口径必须分开记录。

### 任务 Fact 侧证据

目录：`machine-facts/registry/tasks/<task_id>/bundle/dataset-io.jsonl`

当前目录包含 1003 个任务。每条 `dataset-io` 记录表达任务的 READ/WRITE 资产观察，可用于校验或补充：

```text
任务 A WRITE 表 X
  → 任务 B READ 表 X
  → 任务 B WRITE 表 Y
```

本阶段只做种子与 Fact 的存量对账，不用 Task Fact 侧结果替代平台侧种子边界。

## 当前整理口径

输入：

```text
output/titans-collection-20260815/data/downstream-tables-tasks.csv
```

每行按 `downstream_guid` 作为物理对象身份；同时保留表名、库名、任务和平台来源信息。

整理时：

1. 以 `downstream-tables-tasks.csv` 的全部行作为种子，不使用之前 11 张的临时清单；
2. 按 GUID 回连 OData/DPL 关系，记录 `odata`、`dpl` 或两者来源；
3. 保留所有已落盘的库名和任务信息，不从表名猜库；
4. 用 Task Fact 的 WRITE 资产尾部名称做辅助匹配；匹配失败保留 `NOT_FOUND`，不强行补齐；
5. 已经位于 `dm_otc_n` 的种子标记为 `ALREADY_DM_OTC_N_SEED`；
6. 其他 `dm_*` 种子标记为 `DM_OTHER_SEED`；
7. 非 DM 种子标记为 `NON_DM_SEED_CONTINUE`，只有在后续用户确认后才用 SZData 继续展开；
8. 库名为空或为 `-` 的记录标记为 `DB_UNKNOWN`，不按名称推断。

当前整理产物：

```text
output/downstream-dive-20260818/seed-scope.csv
output/downstream-dive-20260818/manifest.json
```

`seed-scope.csv` 是存量种子审计表，不是递归下钻结果。它不证明任何新的下游关系，也不把任务标签当成物理库名证据。

本次存量快照：

| 项目 | 数量 |
|---|---:|
| `downstream-tables-tasks.csv` 种子行 | 483 |
| OData 来源种子 | 470 |
| DPL 来源种子 | 13 |
| 已是 `dm_otc_n` 的种子 | 9 |
| 其他 `dm_*` 种子 | 102 |
| 非 DM 层、后续可继续展开的种子 | 371 |
| 库名未知的种子 | 1 |
| Task Fact WRITE 尾部名称匹配 | 467 |
| Task Fact WRITE 未匹配 | 16 |

这里的 467/16 只是本地 Fact 对账结果，不是对平台血缘的通过/失败判定；未匹配项必须保留，后续由真实下游查询或更精确的资产规范化再核对。

## 已有 Fact 下游 Projection 的处理

仓库中还存在两套基于 Task Fact 的下游 Projection：

- `machine-facts/projections/downstream-candidates/`：1003 个任务、1105 个 WRITE 种子、一跳候选 913 条；
- `machine-facts/projections/downstream-candidates-transitive/`：同一 1105 个 WRITE 种子递归到最多 6 跳，候选 2679 条，下游资产 568 张、下游任务 510 个。

这两套结果暂不并入 `seed-scope.csv`，因为它们的种子口径是 `ALL_TASK_WRITE_ASSETS`，不是平台侧 `downstream-tables-tasks.csv` 的 483 行种子。它们保留为辅助对账材料，不能直接当成 1001 张模型表，也不能替代后续 SZData 下钻。

## 后续续跑规则（本阶段暂不执行）

用户确认种子范围后，才从 `seed-scope.csv` 继续：

```text
种子 GUID
  → SZData table-lineage DOWNSTREAM
  → 新下游 GUID 去重
  → table-detail 解析 db_name
```

边界：

- 非 DM 层继续展开；
- 到达 `dm_otc_n` 时记录并停止该分支；
- 到达其他 `dm_*` 时停止且不纳入目标结果；
- 已访问 GUID 去重，保留最短跳数和证据状态；
- 限流、权限、空结果和解析失败单独落盘；
- 结果按分片保存，不把完整递归结果塞进一个文件；
- 最终范围只保留 `dm_otc_n`，不宣称完整路径已经闭合。

## 当前边界结论

- 平台种子清单与 Task Fact 全量范围不是同一个集合；
- 当前全量 Task Fact 的去重 WRITE 资产是 1105 个，不能直接等同于用户所说的 1001 张模型表；
- 1001 张的精确筛选规则仍需从种子来源和层级边界中继续核对；
- 之前基于 11 张 `dm_otc_n` 表的递归结果属于错误试跑，不进入本次存量整理，也不作为续跑输入。

## 已暂停的 483 种子递归运行

曾经以这 483 张种子启动过一轮 SZData 平台递归下钻，分片保存在：

```text
output/szdata-recursive-downstream-20260818-sharded/
```

该运行已落盘但未完成闭包。当前审计结果：

- 156 个查询分片、156 个直接边分片；
- 16,194 个唯一节点查询成功；
- 77,202 条去重直接边；
- 从 483 个种子可达 28,022 个节点，已达到 4 跳；
- 5,912 个表节点已经发现但尚未展开；
- 没有生成最终 `range/part-*.csv`，所以不能视为最终范围；
- 旧边分片没有持久化下游库名，当前不能直接筛出 `dm_otc_n`。

审计产物位于：

```text
output/szdata-recursive-downstream-20260818-sharded/audit/
```

包括节点库存、待展开表节点、查询状态、节点类型汇总和审计 Manifest。后续应优先从 `unexpanded-table-nodes.csv` 续跑，并补齐 table-detail 持久化；不应重新从 483 张种子起跑，也不应把当前 77,202 条边当作已经闭合的最终结果。
