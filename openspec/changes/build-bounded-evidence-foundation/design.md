## Context

现有工程已经落盘 Panorama Physical Facts，并在 TRADEFLOW 样本中实现了名称、字段、键和依赖的 Jaccard 相似度原型。该原型证明输入契约可用，但它仍是样本级、全对象对、固定权重的方法，尚未形成可扩展的 Panorama 对象关系发现，也没有业务分类种子。参见 `proposal.md` 与 `specs/bounded-evidence-foundation/spec.md`。

Wiki `175428801《研发分工》`提供业务线、能力和系统模块的文档表达，但其本质是组织职责页面，不是表级真值。现有治理又将 Wiki、LLM 和 Object Family 统一冻结为 V1C；本 Change 通过 `cognition-delivery-governance` delta 只打开一次交付前的有界候选分类基础，不打开全量 Deep Scale。

当前工作树已有并行修改。本 Change 的 Apply 必须复用这些当前实现并保留无关改动，不得重置或重写现有 V1A/V1B 结果。外部 LLM Provider 与数据外发仍未决定，因此确定性路线必须先完整成立。

## Goals / Non-Goals

**Goals:**

- 用成熟、可解释的 schema matching 组件从 Panorama 元数据形成稀疏对象相似图。
- 从同一张图得到运行级候选族，但不把 community 当成业务分类或独立标签证据。
- 将 Wiki 和其他标签方法以带来源血缘的弱监督信号表达，阻止同源证据重复计票。
- 对每个分类维度执行一次有界图标签传播，保留多标签、竞争、Unknown 与 Not Evaluable。
- 仅按候选族调用 LLM，并让无 LLM 路线能够独立重放。
- 产出一个最小审阅 Projection，帮助用户检查家族、分类、证据和异常，但不冒充最终业务全貌。

**Non-Goals:**

- 不证明 Wiki 分类、候选族或自动分类是业务真值。
- 不读取列值，不建立 joinability 或实际唯一性结论。
- 不实现完整 Snorkel 训练平台、GNN、向量数据库或正式本体。
- 不扩展全量 Identity、Grain、Field Concept 或语义关系推断。
- 不抓取 Wiki 页面树，不按每张表搜索 Wiki。
- 不在本 Change 中完成最终业务全貌页面和业务验收。

## Decisions

### 1. 使用多视角 Schema Matching，而不是规则分类器

新增一个有版本的 Panorama matcher，分别计算并保存以下信号：

- `physical_name`：Schema/Object 名称 Token、字符 n-gram 与稀有词权重。
- `physical_comment`：对象/字段注释的文本相似信号；缺失单独记录。
- `column_structure`：规范化字段名的 IDF 加权 Jaccard，以及字段类型族分布。
- `declared_key`：PK/UK/FK 和唯一索引字段骨架。
- `declared_dependency`：现有 Oracle Dependency 邻域及直接边。

这些信号保持独立列和 availability mask。只有注册为 `similarity.panorama.multi_view.v1` 的组合方法可以生成方法内 `combined_score`；其权重、缺失处理、阈值和版本进入配置哈希。不同 matcher 的原始分数不在结果层被随意平均，也不展示为概率。

候选对先经过 blocking：同 Schema、共享稀有名称词、字段签名近邻、直接依赖或明确系统词之一成立才进入精排。随后每个节点只保留配置的 top-k 候选，并优先保留 mutual k-nearest-neighbor 边。这样避免把现有样本级全对象对实现直接扩展成数百万行无界结果。

**备选方案：词典命中直接分类。** 实现快，但无法发现异名同构对象，也会让代码退化为 LLM 包装，因此拒绝。

**备选方案：通用文本 Embedding。** 内部缩写和结构字段可能被通用语义误导，且当前没有证据表明 TF-IDF、Jaccard 和声明结构不足，因此暂不引入。

### 2. 构造一张带来源族的稀疏相似图

每条边保存：左右对象、各 matcher 分数、availability mask、blocking 原因、`graph_run_id`、方法版本和边状态。通用审计字段 `root_source_refs` 指向最初的 Physical Fact/Derived Observation；任何后续 family、传播路径或 LLM Pack 都沿用这些根引用。

跨 Schema 边采用更严格的准入条件：仅共享通用字段（如 `ID`、`STATUS`、审计字段）不得形成跨 Schema 强边；直接依赖、共享稀有业务词或多视角一致才允许进入图。Boundary Node 只提供邻域上下文，不自动成为分类主体。

**理由**：相似图既是 Leiden 和 Label Propagation 的共同计算结构，也是最容易发生证据重复计算的地方。显式 `graph_run_id` 和根来源集合能让审计器识别“同一图被使用两次”，而不是误报两份证据。

### 3. 使用 Leiden 发现 candidate family，并单独判定社区强弱

在无向加权稀疏图上执行 Leiden，固定随机种子、resolution、权重列和实现版本。Leiden 的 partition 结果只生成运行级 community；随后通过独立的发布条件判断是否形成 `candidate_family`：

- 至少两个主体成员；
- 不是靠单一通用信号维系；
- 内部边满足配置的多视角支撑和连通要求；
- 边缘成员和异常成员显式保留。

没有达到条件的 community 仍保存算法分区记录，但业务输出为 singleton、weak family 或 Unknown。候选族的名称初始为技术性临时名称，不能由 Leiden 自动生成业务名称。

**备选方案：K-means。** 需要预设簇数并强制所有对象进入簇，不适合当前 Unknown 优先的边界，因此拒绝。

### 4. 以分类维度和来源族组织弱监督，不做朴素多数投票

分类词表从固定 Wiki 快照提取后写为人工可读 YAML，并区分：

- `business_line`
- `business_capability`
- `system_module`
- `technical_role`

研发小组和人员仅作为页面定位上下文，不成为上述稳定值。每个 Labeling Function 可以输出一个或多个标签或 `ABSTAIN`，但必须声明 `source_family` 和 `root_source_refs`。第一版来源族至少包括：`WIKI_DOCUMENT`、`PHYSICAL_NAME`、`PHYSICAL_COMMENT`、`DECLARED_STRUCTURE` 和 `LLM_INTERPRETATION`。

同一来源族内多个规则先归并，再进入冲突处理；支持数量按来源族而不是函数数量统计。LLM 虽可提出标签，但其 Evidence Pack 若复用了 Wiki 和结构证据，`root_source_refs` 仍指向这些原始来源，因此 LLM 不能提升“独立证据数量”或候选证据等级。`LF_CLUSTER_NEIGHBOR` 不实现；candidate family 只作为传播主体和 LLM 上下文。

第一版不引入完整 Snorkel generative label model：当前没有独立 Gold Set 足以估计 LF 准确率和相关性。先保留完整 LF 矩阵、弃权、冲突和来源族，为未来有真值后再决定是否学习权重。

**备选方案：简单多数投票。** 会把相同名称或图信号的多个变体重复计票，因此拒绝。

### 5. 在同一图上执行一次多维度、有界标签传播

标签传播按分类维度独立运行，使用归一化稀疏邻接矩阵和 clamped seeds。多标签维度采用每个标签独立得分，单标签维度同时检查第一/第二候选差距。运行配置固定：

- 最大迭代数和收敛容差；
- 传播衰减和最小种子支持；
- 跨 Schema 传播条件；
- 候选阈值与竞争差值；
- 每个对象最多保留的候选数。

“一次”表示流水线只执行一个传播阶段，不在 LLM 结果返回后重新建图、重聚类或开启自我修正循环。算法内部允许在最大迭代数内收敛。candidate family 本身不投票，因此 Leiden 与传播共同使用图不会产生额外证据份数。

自动输出只有 `SINGLE_CANDIDATE`、`COMPETING`、`UNKNOWN` 或 `NOT_EVALUABLE`。`ACCEPTED` 仍只来自人工 Review Decision。

### 6. LLM 按候选族解释，并保持条件启用

Evidence Pack 每次只包含一个候选族或一个明确异常集合：代表表、成员级结构分解、独立弱标签、Wiki 分类片段、反证、Unknown 和允许引用的 Evidence ID。模型任务限于：候选族临时命名、业务能力候选、异常成员、冲突解释和 `ABSTAIN`。

调用缓存键包含 Pack 哈希、Prompt 哈希、模型标识和输出 Schema 版本。Schema 或 Evidence 引用非法只允许一次结构修复重试；仍失败则落盘错误。Provider 和外发范围未批准时，仅生成可审计 Pack 和 `NOT_EVALUABLE` 任务，不发起网络调用。

**备选方案：逐表调用 LLM。** 成本高、缺少家族上下文且输出不稳定，因此拒绝。

### 7. 新结果作为 Panorama 候选层落盘，不污染 Physical Facts

在现有结果包中增加以下逻辑数据集；精确 Arrow Schema 在 Apply 时与 `04-result-contracts.md` 同步：

```text
panorama/derived/schema_match_signals.parquet
panorama/derived/similarity_edges.parquet
panorama/derived/community_partitions.parquet
panorama/candidates/family_candidates.parquet
panorama/candidates/family_memberships.parquet
panorama/candidates/label_source_outputs.parquet
panorama/candidates/business_class_candidates.parquet
panorama/candidates/business_classification_results.parquet
panorama/evidence/wiki_sources.parquet
panorama/llm/evidence_packs.jsonl
panorama/llm/llm_task_results.parquet
panorama/classification-review/index.html
```

`classification-review` 仅用于快速检查候选族、分类、冲突、Unknown 和证据血缘；最终业务入口及正式双向导航仍由后续 `deliver-and-validate-business-panorama` Change 完成。

旧 Panorama facts、V1B deep-case candidates 和历史输出均不原地修改。新阶段读取上游 Manifest，并生成独立阶段 Manifest；失败对象和未评估信号显式落盘。

### 8. 将成本和停止条件写成运行契约

配置必须限制候选对 blocking、每对象 top-k、最大边数、Leiden 参数、传播迭代数、每簇代表对象数、LLM Pack 字符数、LLM 调用数和重试数。超过任一硬上限时阶段停止为 `PARTIAL` 或 `FAILED`，不自动扩展预算。

流水线只有以下一次性顺序：

```text
fixed inputs
→ match signals
→ sparse graph
→ Leiden partition / candidate family
→ weak labels
→ one bounded propagation
→ optional LLM interpretation
→ validation / review projection
```

LLM 结果不会触发第二轮建图或传播。后续如需字段概念、关系语义或迭代校正，必须通过新的范围确认。

## Risks / Trade-offs

- [Wiki 研发分工不是业务分类真值] → 只作为版本固定的弱标签和词表来源，保留文档定位，不使用人员信息，不产生 Accepted。
- [Schema 名、表名和字段名高度相关] → 使用 `source_family` 与根来源集合归并，禁止按规则数量计票。
- [同一相似图同时用于 Leiden 和传播] → family 不投票，所有派生结果共享 `graph_run_id`；审计测试验证不会形成重复 Evidence Link。
- [通用字段造成跨域大社区] → IDF 降权、跨 Schema 强准入、mutual k-NN 和边数上限，并保留 singleton/weak community。
- [Leiden 参数改变社区] → 固定随机种子和配置哈希，输出社区稳定性对比；community ID 只在 run 内有效。
- [没有独立业务真值] → 第一轮只交付 Candidate/Conflict/Unknown 和少量人工审阅材料，不发布准确率或方法有效声明。
- [LLM 未授权导致用户预期落差] → 无 LLM 路线先完整运行；Manifest 和审阅页明确标记语义任务 Not Evaluable，待用户另行批准 Provider/外发范围。
- [新增算法依赖增加安装复杂度] → 优先使用少量固定版本依赖，并在引入前核对许可证、Windows 安装和离线可用性；不引入服务型基础设施。

## Migration Plan

1. 在不修改历史 Artifact 的前提下，为当前 Panorama run 增加独立分类配置、Wiki 快照引用和新阶段输出目录。
2. 将现有 TRADEFLOW token/Jaccard 实现中的通用特征逻辑提取为 Panorama 可复用组件，保留旧公共行为和回归测试。
3. 增加多视角 matcher、稀疏图、Leiden、弱标签矩阵和一次标签传播；先在合成小图和一个有界 Schema 上验证，再对 Panorama allowlist 运行。
4. 生成无 LLM 的完整候选结果和最小审阅页；确认没有同源重复计票、无静默丢失和自动 Accepted。
5. 只有在 Provider 与外发范围获批后启用真实 LLM 调用；否则仅验证 Pack、缓存和禁用路径。
6. 将实际结果交给用户审阅，后续业务全貌页面和业务验收由独立 Change 处理。

回滚时删除或忽略新 run 下的分类阶段输出，并恢复本 Change 的代码差异；现有 Physical Facts、V1B 候选和历史页面没有被覆盖，无需数据恢复。

## Open Questions

- LLM Provider、企业账号和允许外发的表名、字段名、注释及 Wiki 片段范围仍由现有 D-005 决策控制；它不影响确定性阶段实现，但决定真实 LLM 调用能否在 Apply 验证中执行。
- Leiden 与稀疏矩阵库的最终 Python 包在 Apply 前通过 Windows 安装、许可证和锁定版本检查确定；算法行为与结果契约不因此改变。
