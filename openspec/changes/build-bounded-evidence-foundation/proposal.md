## Why

现有 Panorama 已能浏览物理 Schema、表、字段和依赖，但还缺少从业务区域与能力反向定位物理对象的候选分类基础。现在已有可固定版本的 Wiki `175428801《研发分工》`，也已有名称、字段、键和依赖等物理元数据，适合用一次有界、可重放的结构发现与弱监督流程建立业务全貌的第一层语义入口，而无需先抓取整个 Wiki 或启动全量深度认知。

## What Changes

- 固定 Wiki `175428801` 的只读页面快照，将其中的业务线、业务能力和系统/模块表述整理为可追溯的分类种子；人员姓名、合作方和组织编制不进入稳定分类依据。
- 将 Schema Matching 明确定义为结构证据底座：从名称、注释、字段、类型、键和已有依赖产生可解释的对象相似信号与候选关系排名，不直接输出业务分类。
- 基于一张去重后的 schema similarity graph 运行 Leiden 社区发现，生成运行级 `candidate_family`；community 不等于业务分类，单例、弱社区和不稳定成员保持 Unknown 或边缘状态。
- 使用 Wiki、Schema 上下文、高精度名称规则和有界 LLM 解释作为可弃权的弱监督标签源；删除 `LF_CLUSTER_NEIGHBOR`，不得把同一相似图通过聚类、邻居投票和传播重复计算成多份独立证据。
- 将候选族与独立分类种子送入一次有界 Label Propagation，输出 `candidate_business_class`、Conflict 和 Unknown；不得无限迭代，也不得将传播分数描述为正确概率。
- LLM 只解释候选族、歧义和反证，输出必须引用固定 Evidence Pack；Provider、数据外发范围未批准时保持禁用，并将相应任务标为不可运行，而不是偷偷改走外部模型。
- 生成可重放的类型化结果、Manifest、错误与证据来源，并为后续业务全貌页面提供“业务分类到表、表到候选分类”的投影输入。
- 明确本 Change 不建设全 Wiki 目录抓取、正式业务本体、完整关系图谱、全量 Identity/Grain 深推断、人工审核平台或第二 Schema 泛化。
- **BREAKING**：将现有“Wiki/LLM、Object Family 一律只能在业务全貌验收后启动”的笼统冻结规则，收紧为“本 Change 仅授权交付前的有界候选分类基础”；TRADEFLOW 全量 Deep Scale、Field Concept、正式业务语义和方法泛化继续禁止，且本 Change 不改变 `reader_delivery`、`business_acceptance` 或一般性 `scale_authorization` 状态。

## Capabilities

### New Capabilities

- `bounded-evidence-foundation`: 定义固定 Wiki 分类种子、结构匹配证据、候选族、独立弱监督标签、单次标签传播、受证据约束的 LLM 解释，以及 Conflict/Unknown 和可重放结果的行为边界。

### Modified Capabilities

- `cognition-delivery-governance`: 允许一次明确授权、不能自动外扩的交付前候选分类基础，同时继续禁止将其解释为业务全貌交付、业务验收、全量 Deep Scale 或方法泛化。

## Impact

- 主要影响 Panorama 派生结果、Evidence/Manifest 契约、候选分类流水线和静态地图的数据输入；复用现有只读物理事实，不重新查询业务数据行。
- 预计在现有 Python、Parquet/JSON/YAML、DuckDB 和静态 HTML 边界内实现；可引入经过锁定和审查的本地图算法依赖，但不引入 PostgreSQL、Neo4j、向量数据库、远程 Worker 或 Agent 自治编排。
- Wiki 访问保持只读并优先复用 OpenCLI Wiki 页面缓存；只固定指定页面及实际使用的定向证据，不抓取整个空间。
- 外部 LLM 网络调用仍受现有数据外发决策约束；本 Change 的确定性结构阶段必须在 LLM 禁用时独立运行和交付。
- 现有 V1A/V1B 事实、候选、Gold Set、评测和历史输出保持不变，不因新分类结果被覆盖或重新解释。
