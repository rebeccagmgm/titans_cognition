# case-learn-86840：一步步读懂 T98_OPTION_BRANCH

这个 case 只学习任务 `86840` 如何生成 `dyna_nom_prin`，不试图复现完整指标链路。

## 运行

在仓库根目录执行：

```text
npx tsx sqllens/scripts/analysis/case-learn-86840.ts
npx tsx sqllens/scripts/verification/verify-case-learn-86840.ts
```

默认 profile 依赖已有的本地证据快照：

- `.evidence-cache/tasksql-86840-20260816122735.txt`；
- `output/indicator-processing-graph-rgstcomp-mthend/szdata-schema-evidence.json`；
- 阶段 8 还会读取同目录下已有的 processing-graph JSONL（缺失时只将阶段 8 标为 `NOT_AVAILABLE`）。

前两个文件不是这个 case 自己重新采集的；脚本会在启动时做 preflight，并明确报出缺失的前置文件。

可指定 profile 和输出目录：

```text
npx tsx sqllens/scripts/analysis/case-learn-86840.ts `
  cases/case-learn-86840/learning-profile.json `
  output/case-learn-86840
```

## 八个学习阶段

每个阶段都会写成带 `stage_no` 的独立 JSON 文件：

1. `01-input.json`：SQL 快照、Schema 证据、hash 和边界。
2. `02-parse.json`：语句数量、语法错误、诊断和 span。
3. `03-ir.json`：原始 sqllens `QueryExpr` IR（去除 CST 回指和循环字段）以及 plan-adapter 关系操作轮廓。
4. `04-scope.json`：当前查询块可见的表、别名、CTE 和输出。
5. `05-binding.json`：`dyna_nom_prin` 表达式中的列引用如何绑定到物理字段。
6. `06-lineage.json`：输出列向基表字段的来源追踪。
7. `07-plan-facts.json`：完整的 Logical Plan Facts 及 Unknown。
8. `08-graph-slice.json`：处理图中与任务 86840 相关的实体、字段、关系和边。

输出目录还会有：

- `README.md`：按阶段阅读的提示；
- `learning-manifest.json`：8 个阶段的文件、hash、状态和边界。

生成数据位于 `output/`，按项目约定不进入 Git。这个 case 的配置和脚本是可重放的来源。
