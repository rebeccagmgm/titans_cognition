# SQL 分析三阶段总览（Column Lineage → Logical Plan → Grain）

> 目的：让任何人在下次打开本仓库时，能快速知道"SQL 分析"这条线的三个阶段分别做了什么、成果在哪、怎么重跑。
> 固定日期：2026-08-15。本文只记录已落地且可核实的产物；未完成/未授权的工作不在此声明。

## 1. 三阶段定义

SQL 分析任务按三个递进阶段划分（来源：项目实践约定，未写入 spec 的正式契约）：

| 阶段 | 名称 | 回答的问题 | 主要载体 |
|---|---|---|---|
| 1 | **列血缘 / Column Provenance** | 这个字段的值从哪里来、怎么算出来 | sql-static-lineage `originsOf` / `lineageAt` 逐跳血缘 |
| 2 | **转换 / Logical Plan Facts** | JOIN/WHERE/GROUP BY/WINDOW/LATERAL VIEW 等加工结构是什么 | `plan-adapter.ts` 输出的 `plan-facts-*.json` |
| 3 | **粒度 / Grain Inference** | 处理后每行的业务含义、扩行/压行风险 | plan-facts 内的 `grain_inference` 块 + Grain Resolver |

设计原则（源自架构决策）：

- 阶段 1 由 sql-static-lineage 负责，阶段 2 将 sql-static-lineage IR 适配为简化的 Logical Plan Facts（语义对齐 Calcite/Substrait 标准操作符：Read/Filter/Join/Aggregate/Window），不自创 Transformation Facts 语义。
- 阶段 3 的 Grain Resolver 独立成层：基于结构规则（GROUP BY 必压行、JOIN 类型有扩行风险）+ 可选元数据（PK/UK/FK/统计）推断；无证据时诚实标注 `unknown`（never-wrong 原则）。
- 前两层是翻译与重组，研发重心在第三层。

## 2. 阶段 1：列血缘/溯源 —— 已完成单案例方法验证

### 2.1 完成标准（5 条）

1. 所有输出列都有 lineage；
2. terminal 能追到物理字段；
3. 派生表达式完整保留；
4. unresolved 显式 `unknown`；
5. CASE / Window / Union 有代表性 golden case。

不要求把表达式拆解为完整算子树，重点在依赖链和原始表达式的完整性（满足模型归并判断需求）。

### 2.2 验证案例：任务 118141（TITANS_TRADEFLOW 基线）

- SQL 原文：`.evidence-cache/tasksql-118141-20260814.txt`（Horae 调度任务 SQL，OTC 合约交叉销售收入日报 `OTC_SALE_DAILY_RPT` 建表 + 加工逻辑）。
- 规模：29,595 字符 / 6,847 tokens；含多层嵌套子查询、`lateral view posexplode`、窗口函数、自定义 UDF `default.gfgreatest`、`${yyyy-MM-dd}` 模板变量。
- 方言：**databricks（Spark SQL 的硬性约定方言，见 4.1）**。

### 2.3 验证结果（对照完成标准）

| 标准 | 结果 |
|---|---|
| ① 所有输出列有 lineage | 92/92 列命中（平面血缘 `originsOf`），穿透 4~5 层嵌套 |
| ② terminal 追到物理字段 | 逐跳血缘直达输入表物理列；阶段 2 中 57/60 条件列物理解析成功（见 golden README 断言 8） |
| ③ 派生表达式完整保留 | 逐跳血缘每跳输出 scope/投影/表达式原文（含注释）/IR 结构摘要，见 `sql-static-lineage/output/118141/sql-static-lineage-118141-hops.txt` |
| ④ unresolved 显式 unknown | 3 处 lateral view 盲区（c_sp/c_ba/cc 的 `busi_date`）显式记录，不猜测 |
| ⑤ 代表性 golden case | Union（3 分支，`setOpArmsOf`）、Window、CASE、lateral explode 均有覆盖 |

### 2.4 结构化视图 API 验证（阶段 1 的副产品，阶段 2 的输入）

sql-static-lineage IR 之上的 `clausesOf` / `frameAt` / `nodeAt` / `setOpArmsOf` 均已实测：

- `frameAt` 定位字段所属查询块（如 `Ddct_Ptrn` 在子查询 T 内，`Curr_Prvs_Sales_Income` 在主查询）；
- `nodeAt` 返回光标处最小表达式；
- `setOpArmsOf` 正确返回 union 分支；
- 实测揭示 118141 为 **4 层嵌套**（root → casttable → x → t），7 个 JOIN 全部位于最内层 t 层 —— 因此取 JOIN 结构必须**递归遍历整个 scope 树**，只看顶层会遗漏。

## 3. 阶段 2 与阶段 3 当前状态（截至 2026-08-15）

| 阶段 | 状态 | 关键证据 |
|---|---|---|
| 2 转换/Logical Plan Facts | 118141 单案例闭环完成 | `sql-static-lineage/output/118141/plan-facts-118141.json`（246KB）；`scripts/verification/verify-golden.ts` 22 断言 0 失败，与 `golden/118141/plan-facts.json` 结构一致（忽略易变 `generated_at`） |
| 3 粒度/Grain Inference | 首版原型随 plan-facts 输出 | `grain_inference` 块含 grain_candidate/cardinality/confidence/requires/evidence |

### 3.1 阶段 2 固定断言要点（详见 `sql-static-lineage/golden/118141/README.md`）

- 47 个关系节点、9 张物理表、4 层嵌套；
- JOIN 链：`join.1`(inner, det) + `join.2..7`(left)，左深链；
- 4 个 expand（lateral view 行扩展，fanout 模型：cardinality=unknown + per_input_rows=0..N + grain_effect=expanded）；
- 聚合 `actl.aggregate`：GROUP BY `Contr_Id`，measures = `sum(Dev_Dept_Rwd)` + `max(Sett_End_Date)`；
- star 展开：`info.project` 92 列 / `m.project` 60 列 / `x.project` 76 列，无 star 残留；
- machine truth 不截断（`*_expr`/`expr_text` 完整原文），截断仅出现在 display 字段（≤20 字符，全量 20 条）；
- 条件列物理解析：`info.agt_id → T98_OTC_DERI_COMP_SALE_INFO.agt_id`、`s_sp.CONTRACT_CODE → T99_DERI_COMP_SPRD_COEF_REF.Inr_Comp_No`（穿透子查询别名）等；
- grain 传播：`x.join.1` requires=[]（右表 grain key 由上游 GROUP BY 传播），其余 join requires 精确到右表列。

### 3.2 阶段 3 输出样例

- `actl.aggregate`: grain=["Contr_Id"], cardinality=non-increasing, confidence=high；
- expand: cardinality=unknown, cardinality_effect=fanout（explode 空集合/NULL 不产生行）。

## 4. 关键约定与踩坑（重跑前必读）

1. **Spark SQL 一律用 databricks 方言解析**（基于 sql-static-lineage 实测验证的硬性约定），其他方言见 sql-static-lineage CLAUDE.md 方言表。
2. **`clausesOf` 坐标系陷阱**：多语句 SQL 文档必须用 `doc.clausesOf(scope)` 实例方法（自动平移坐标），自由函数 `clausesOf` 在多语句文档中返回空。
3. **JOIN 深嵌套**：必须递归遍历所有 scope 层，不能只检查顶层（118141 的 7 个 JOIN 在最内层 t 层）。
4. **`lineageAt` offset 是 cell 坐标**（与 IR 的 cst/partSpans 同坐标系），且 `nodeAt` 是裸数值比较 —— 必须精确锚定到列名 token 起始位置（`ColumnRef.partSpans[0].start`），否则命中父表达式导致"张冠李戴"（返回整个投影的来源）。输出 span 才是 doc 坐标（需加 cell.span.start 平移）。
5. **调度模板占位符先做等长可逆预处理**：`${yyyyMM}`、`${yyyyMM,-1M}` 等只作为解析哨兵，不解释日期语义；解析完成后恢复原文，避免破坏表名、字段名和 span。
5. **`hop.terminal` 两种失败形态**：字符串 `"unresolved"`（sql-static-lineage 显式判定）与 `undefined`（followColumn 无来源，如 lateral view 子查询别名列在 JOIN ON 中引用）。`JSON.stringify(undefined)` 返回字符串 `"undefined"` 易误判，必须用严格 `===` 区分。
6. **PowerShell 重定向中文乱码**：不要用 `> file` 重定向脚本输出；用 `fs.createWriteStream(path, { encoding: "utf8" })` 直接写文件。
7. sql-static-lineage 工具本身**无 transform provenance 与 grain 模型**（`grain` 零匹配、hop 血缘明确排除 WHERE/JOIN 条件），但 IR 保留完整结构（where/joins/groupBy/joinConditions），是阶段 2/3 的原料。

## 5. 产物与脚本索引（sql-static-lineage/ 目录）

### 5.1 证据文件

| 文件 | 内容 |
|---|---|
| `.evidence-cache/tasksql-118141-20260814.txt` | 118141 SQL 原文（阶段 1/2 唯一输入） |
| `sql-static-lineage/output/118141/sql-static-lineage-118141-output.txt` | 平面血缘输出（92 列） |
| `sql-static-lineage/output/118141/sql-static-lineage-118141-hops.txt` | 逐跳血缘 + 加工表达式还原 |
| `sql-static-lineage/output/118141/sql-static-lineage-118141-full-output.txt` | 完整解析输出 |
| `sql-static-lineage/output/118141/struct-views-118141.txt` | 结构化视图 API 验证结果 |
| `sql-static-lineage/output/118141/plan-facts-118141.json` | 阶段 2 产物（plan + grain_inference） |
| `sql-static-lineage/output/118141/plan-facts-118141.explain.txt` / `fingerprint-118141.json` | plan 解释 / 指纹 |
| `sql-static-lineage/golden/118141/` | golden 回归基准（README / plan-facts.json / sql.txt） |

### 5.2 脚本清单（运行方式均为 `cd sql-static-lineage && npx tsx <script>.ts`）

| 脚本 | 阶段 | 用途 |
|---|---|---|
| `spark-demo.ts` / `demo.ts` | 1 | sql-static-lineage 探索：databricks 方言解析 Spark ETL 验证 |
| `real-sql-demo.ts` | 1 | 118141 解析 + 平面血缘（92 列） |
| `scripts/demos/hop-demo.ts` | 1 | 逐跳血缘 + 表达式还原 → `output/118141/sql-static-lineage-118141-hops.txt` |
| `struct-views-demo.ts` / `struct-views-118141.ts` | 1 | clausesOf/frameAt/nodeAt/setOpArmsOf 验证 |
| `schema-118141.ts` / `schema-experiment.ts` | 2 | pdata_n 库 schema 实测（info 92 列/det 23 列/m 60 列），物理解析输入 |
| `compare-demo.ts` / `resolve-audit.ts` | 1 | 对比 / 解析审计（辅助） |
| `plan-contract.ts` | 2 | Logical Plan Facts 契约（v1.2.0）定义 |
| `plan-adapter.ts` | 2 | sql-static-lineage IR → plan-facts 适配器（v0.3.0，含原生 LineageHop 投影） |
| `scripts/plans/plan-118141.ts` | 2 | 生成 `output/118141/plan-facts-118141.json` |
| `plan-batch.ts` / `plan-fingerprint.ts` / `plan-explain.ts` | 2 | 批量 / 指纹 / 解释工具 |
| `verify-golden.ts` | 2 | golden 回归：22 断言 + 与 golden 完全一致性比对 |

### 5.3 重跑命令

```bash
cd sql-static-lineage
npx tsx scripts/demos/real-sql-demo.ts      # 阶段1：平面血缘
npx tsx scripts/demos/hop-demo.ts           # 阶段1：逐跳血缘 → output/118141/sql-static-lineage-118141-hops.txt
npx tsx scripts/plans/plan-118141.ts        # 阶段2：重新生成 output/118141/plan-facts-118141.json
npx tsx scripts/verification/verify-golden.ts      # 阶段2：回归校验（当前 22 通过 / 0 失败）
# output/118141/plan-facts 与 golden/118141/plan-facts.json diff，任何节点级差异都需说明
```

### 5.4 当前任务机器事实包（V1）

机器事实包是任务级当前 Derived Observation 底座：每个 `task_id` 只有一份当前 Bundle，SQL/Schema Hash 记录在 Manifest 中作为输入指纹。生成结果不修改现有案例图、Panorama Physical Facts 或业务候选；失败状态不会进入当前索引。

```bash
cd sql-static-lineage
npx tsx scripts/machine-facts/machine-facts.ts `
  --profile cases/indicator-journey-rgstcomp-mthend/processing-graph-profile.json `
  --output machine-facts `
  --source-id gfhive-test

# 独立于指标 Profile 的本地回放输入（包含已验证的 118141 Schema Evidence）
npx tsx scripts/machine-facts/machine-facts.ts `
  --profile sql-static-lineage/fixtures/machine-facts-independent-profile.json `
  --output machine-facts `
  --source-id gfhive-test `
  --refresh-schema
```

`--refresh-schema` 会先从 SQL/Plan 的 `physical_inputs` 自动发现表，与现有
`schema_evidence.records` 做差集，只通过只读 `szdata table`/`table-ddl` 补缺失表，成功后原子更新
Schema Evidence；不传该参数时仍可完全离线重放。字段输入依赖按证据强度分层：

- 表和字段都能被 Schema Evidence 验证时，写入 `PHYSICAL` 及 `SCHEMA_BOUND` 血缘边；
- Schema 缺失但 SQL 结构明确指向单一物理来源时，写入 `SQL_CANDIDATE`，并将候选字段和边标为 `UNVERIFIED_SCHEMA`，不能冒充 `PHYSICAL`；此时不再额外生成重复的 `SCHEMA_BINDING_NOT_EVALUABLE`；
- 多个可能来源、星号展开或无法唯一绑定时，保留 `UNRESOLVED`，同时将缺失的读表保留为 `NOT_EVALUABLE`/Unknown。

因此缺 Schema 不再导致所有简单直接加工都被静默丢弃，也不会因为 SQL 看起来简单就伪造物理字段事实。补齐真实 Schema Evidence 后重跑，候选绑定才会升级为 Schema-backed `PHYSICAL`。

输出位于仓库根目录 `machine-facts/`（已忽略，不提交原始 SQL/Schema）：

```text
machine-facts/
├─ snapshots/sql/<sha256>.sql
├─ snapshots/schema/<sha256>.json
├─ registry/tasks/<task_id>/analysis-status.json
├─ registry/tasks/<task_id>/bundle/*.jsonl
└─ indexes/task-fact-index.jsonl
```

当前 Bundle 还包含原生值传播 Hop 投影：

```text
registry/tasks/<task_id>/bundle/
├─ lineage-hop-roots.jsonl   # requested expression → native head + coverage/status
├─ lineage-hop-nodes.jsonl   # native Hop、Scope Relation、terminal、has_downstream、via
└─ lineage-hop-edges.jsonl   # 仅 PHYSICAL_FIELD_TO_HOP / HOP_TO_HOP，生产者→消费者
```

这三份文件直接由 `sql-static-lineage` 的 `lineageOf()` / `LineageHop` 生成；Relation Facts 不会反向猜测 Hop。`via=rename/expand` 保留在 Node 上，物理表只作为 terminal，Setop 只保留原生分支 Hop，不伪造 Setop Hop。`column-lineage-edges.jsonl` 继续是 Physical Base Origin → Field Expression 的来源摘要，不能用它替代 Hop DAG。

每个 Hop Root 都声明 `flow_kind=VALUE_LINEAGE`，并保留 `FULL_HOP`、`FLAT_ORIGIN_ONLY`、`UNKNOWN_COVERAGE` 或 `NOT_EVALUABLE` 与 `PROJECTED`、`PARTIAL_NATIVE` 或 `NOT_EVALUABLE`。Scalar/EXISTS 当前只压平到 Origins；Adapter 合成的最终 Star 字段因没有原生逐字段锚点而不可评测；candidate、unresolved 和未建模 Expr/Source 不得升级为完整投影。对 `FULL_HOP` 且已投影的 Root，发布前必须验证可达 physical terminal 与既有来源摘要守恒。

Hop 只表达任务内值传播，不表达 Filter、Join、Group By 的行集控制、Window Role、Grain 或 Cardinality。需要解释完整加工因果时，Consumer 必须组合 Hop Facts、Relation Facts 和 Expression Facts；Hop DAG 不是业务因果图，也不生成跨 Task 边。所有 Hop 的 Relation、Expression、Field、Node 和 Edge ID 在 Adapter 使用 Task/Statement 内稳定结构身份持久化，缺失 Scope 映射时不发布悬空节点。

共享物理 Schema Facts 作为 Machine Facts 的附加 Projection，不按 Task 或路线复制，也不使用 Schema Bundle/Scope Hash 作为目录层级：

```text
machine-facts/projections/schema-facts/
├─ manifest.json
├─ index.jsonl
└─ tables/<table_storage_key>/
   ├─ table.json
   └─ columns.jsonl
```

从当前 source-layer 事实重建该 Projection：

```powershell
cd sql-static-lineage
npx tsx scripts/machine-facts/schema-facts-projection.ts `
  ../machine-facts/registry/source-layer/source-layer-table-facts.jsonl `
  ../machine-facts/projections/schema-facts `
  gfhive-test
```

`table_storage_key` 优先使用数综已提供的 `guid`；缺失时依次回退到 Metadata 限定名、`logical_source_id + qualified_name` 的安全编码，不伪造 GUID。`table.json` 只表达当前物理对象位置、对象类型、注释/分区/DDL 证据和 Metadata 明确给出的 `OBSERVED_SOURCE_MAPPING`；`columns.jsonl` 提供既有 `dataset_id`/`field_id` 兼容身份，便于与任务级字段表达式关联。该 Projection 不生成约束、候选键、粒度、基数、业务语义、Review 或完整血缘结论；完整 DDL仍由既有 Schema Evidence/Snapshot 保管，`ddl_ref` 以 DDL 内容 SHA-256 关联已有证据，不复制完整 DDL。

同一输入重跑返回 `REUSED`；输入或方法变化在校验成功后替换同一 Task 的当前 Bundle。Windows 发布采用单写者的 Staging/Recovery 可恢复流程，不保存 Fact Diff、历史 Edition 或旧版本目录。V1 不生成 Grain、跨任务血缘、指标/影响 Projection、Capability Package 或查询层结果。

### 5.4.1 一跳直接下游候选发现

在已有 Task Machine Facts 之上，可以先按已确认的模型层（或其他种子资产）扫描直接消费者，圈出候选范围；该命令只消费现有 `dataset-io` 和字段表达式事实，不查询业务行、不执行调度，也不递归追下游的下游：

```powershell
cd sql-static-lineage
npx tsx scripts/query/downstream-candidates-from-machine-facts.ts `
  --facts-root ../machine-facts `
  --output ../machine-facts/projections/downstream-candidates `
  --seed t98_otc_deri_comp_sale_info `
  --seed t05_otc_comp_rgst_sac_evt
```

若要覆盖当前 Fact Registry 中的全量任务，可使用 `--all-write-assets`，自动将 1003 个任务观察到的全部去重 WRITE 资产作为种子；任务内部同一资产的自读自写不计为下游，重复 READ 证据归并为一条候选关系：

```powershell
cd sql-static-lineage
npx tsx scripts/query/downstream-candidates-from-machine-facts.ts `
  --facts-root ../machine-facts `
  --output ../machine-facts/projections/downstream-candidates `
  --all-write-assets
```

在一跳 Projection 基础上继续找全量下游，可加 `--recursive` 并写入独立目录。递归按任务/资产图做 BFS，每个“起始资产—下游任务”只保留最短路径，并对已访问资产/任务去重以处理环：

```powershell
npx tsx scripts/query/downstream-candidates-from-machine-facts.ts `
  --facts-root ../machine-facts `
  --output ../machine-facts/projections/downstream-candidates-transitive `
  --all-write-assets `
  --recursive
```

递归目录同时生成 `range.jsonl`，将结果进一步压成“起始资产—下游资产”的去重范围；不要求消费者路径完整展开。`manifest.json` 同时记录去重后的下游资产数、任务数和起始资产—下游资产关系数。

结果写入被忽略的 `machine-facts/projections/downstream-candidates/`：`manifest.json` 记录种子、扫描任务数、跳数和边界；`candidates.jsonl` 一行表示“种子资产—直接消费者任务”候选，并保留下游写表、字段绑定摘要、证据引用和 `PHYSICAL/PARTIAL/UNRESOLVED` 状态。候选关系不是已确认业务血缘；同一消费者同时读取多个种子时保留多条关系。

环境要求：Node.js ≥ 20.11，`npm install` 后 `npm run gen:all`（生成 ANTLR parser）。

### 5.5 下游 `SELECT *` 元数据批处理

下游任务 SQL 中出现 `SELECT *` 时，先用 sql-static-lineage 生成
`star-metadata-targets.json`，再通过只读 SZData 查询缓存表元数据和 DDL。批处理脚本会：

- 从任务数据库映射和既有血缘清单复用 GUID，减少重复的表查询；
- 正确处理 SZData 的外层数组和 `table.guid` 嵌套返回；
- 采用单写者追加 JSONL 缓存，支持断点续跑和失败项重试；
- 默认单路调用，避免触发用户级限流；`--workers 2` 需要在确认限流余量后显式开启。

```powershell
.venv\Scripts\python.exe scripts\szdata_star_metadata_batch.py `
  --targets output\downstream-machine-facts-20260817\star-metadata-targets.json `
  --cache output\downstream-machine-facts-20260817\szdata-schema-cache.jsonl `
  --task-map output\titans-collection-20260815\data\downstream-tables-tasks.csv `
  --odata-lineage output\titans-collection-20260815\data\downstream-odata.csv `
  --guid-overrides cases\downstream-machine-facts\szdata-guid-overrides.json `
  --retry-errors --retry-empty
```

脚本只查询元数据和 DDL，不查询业务行、不运行调度任务、不写入源系统。缓存采用 latest-wins：同一
`cache_key` 的最后一条记录为当前状态；需要重新验证空结果时使用 `--retry-empty`，需要重试接口错误时使用
`--retry-errors`。当 SZData 对同名异物理对象返回歧义时，必须通过 `--guid-overrides` 显式绑定 GUID，不能
按名称自动猜测。

## 6. 当前状态与边界

- **单案例垂直切片**：以上全部结论基于任务 118141；方法有效性、业务真实性、读者可用性均未跨 Schema 验证。
- **V1C 冻结**：全量深度推断、跨 Schema 扩展、Wiki/LLM 接入均需用户独立授权（见 `docs/current-status-baseline.md`）。
- **语料扩展中**：2026-08-15 起 `.evidence-cache` 已批量拉取 20+ 个调度任务 SQL（如 144141/152881/62517 等），为 118141 之外的下一批案例做准备；szdata 侧同期在做 ODS 源映射对账（`output/szdata-inventory-20260815/`）。
- **sql-static-lineage 已知边界**（阶段 2 v1.1 不覆盖）：read 节点 `columns` 恒为 null（需 qualify 展开 v2）；lateral 子查询别名列的物理解析为 null（followColumn 盲区，unknowns 显式记录）。
