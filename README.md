# TITANS Cognition

TITANS Cognition 用于从测试库的物理元数据中逆向发现可检查的结构认知和业务语义候选。V1 同时交付两条互补结果：以当前纳入的 TITANS Schema 建立可下钻的 `TITANS Panorama`，并以 `TITANS_TRADEFLOW`（当前已知基线 477 张表，运行时复核）作为首个 `Deep Case` 验证 Identity、Grain、Role、Relation 等深度认知方法。目标不是建设元数据目录或正式业务本体。

## 当前状态

- 当前阶段：V1A Panorama 已实现并通过 Gate A；下一步是 V1B TRADEFLOW Deep Sample。
- 数据环境：测试库，只读元数据盘点；不扫描业务数据行。
- 核心路线：一次 Oracle 元数据提取 → TITANS 全貌与粗结构地图 → TRADEFLOW 深度结构分析 → 类型化候选结果 → 受证据约束的 LLM 语义辅助 → Gold Set 评测 → 最小可浏览地图。
- V1 存储：Parquet/JSON/YAML + DuckDB 分析，不引入 PostgreSQL、Neo4j、DataHub 或 OpenMetadata。

## V1三阶段

| 阶段 | 目标 | 完成后回答 |
|---|---|---|
| V1A Panorama | 完整盘点当前纳入的 TITANS Schema，生成物理对象卡和全貌地图 | 数据库里有什么 |
| V1B Deep Sample | 在 TRADEFLOW 分层样本上验证 Identity → Grain → Role → Relation → Evidence | 这套认知方法是否真的有效 |
| V1C Deep Scale | 方法过门后扩展至 TRADEFLOW 全量，并条件引入 Family、Field Concept、Wiki/LLM | 如何规模化形成深度认知地图 |

三个阶段使用同一工程和同一套物理事实。V1C 是条件触发阶段，不得与 V1A/V1B 同时铺开。

## Spec 导航

完整规范入口：[docs/spec/README.md](docs/spec/README.md)。

| 模块 | 内容 |
|---|---|
| [01 需求](docs/spec/01-requirements.md) | 目标、用户任务、范围、非目标、验收边界 |
| [02 领域模型](docs/spec/02-domain-model.md) | 事实、结构认知、语义候选、证据和评审的概念关系 |
| [03 总体架构](docs/spec/03-architecture.md) | 组件、数据流、技术选型和阶段边界 |
| [04 结果数据契约](docs/spec/04-result-contracts.md) | Parquet/JSON/YAML 结果集及字段定义 |
| [05 推断方法](docs/spec/05-inference-method.md) | Identity、Grain、Role、Family、Relation 的规则和失败边界 |
| [06 LLM 集成](docs/spec/06-llm-integration.md) | SDK、Evidence Pack、结构化输出、安全和缓存 |
| [07 证据与评审](docs/spec/07-evidence-and-review.md) | 支持/反证、证据等级、人工决策和 Unknown |
| [08 评测](docs/spec/08-evaluation.md) | Gold Set、分任务指标、错误分类和质量门槛 |
| [09 地图交付](docs/spec/09-map-delivery.md) | 总览、对象卡、字段概念、关系和未知地图 |
| [10 实施计划](docs/spec/10-implementation-plan.md) | 分阶段落地、依赖、里程碑和停止条件 |
| [11 安全与运行](docs/spec/11-security-and-operations.md) | 只读边界、敏感信息、外发审批和运行记录 |
| [12 待决事项](docs/spec/12-open-decisions.md) | 实现前必须确认的问题和升级触发条件 |

## V1 核心原则

1. 从数据库声明事实出发，不把机器推断写成事实。
2. 以 Identity、Grain、Role、Relation 为结构认知主线，但允许相互校正。
3. Panorama 范围内物理盘点必须完整；Deep Case 的语义不确定必须显式保留为 Unknown。
4. 类型化候选结果是底层契约，统一 Claim 只作为派生视图。
5. LLM 只读取有限 Evidence Pack，只能产生候选，不能直接修改事实或形成策展结论。
6. 全貌覆盖不等于深度方法已泛化；在第二个 Deep Case 验证前，不抽象成通用框架。

## V1 不做

- 不写测试库，不运行生产或调度任务。
- 不扫描表内业务数据，不验证实际唯一率或关联命中率。
- 不要求 Panorama 中所有对象都完成 Identity、Grain 或业务语义推断，也不要求 TRADEFLOW 477/477 表全部业务分类成功。
- 不建设长期 Catalog、历史 Edition、多用户评审或权限平台。
- 不建设正式本体、图数据库、向量数据库或复杂 Web 应用。
- 不让 Agent 或 LLM 自主访问 Oracle。

## 当前实现进度

- 阶段 0：已确认初始 Panorama allowlist，已建立 `cases/titans-panorama/scope.yaml` 和 `cases/tradeflow/scope.yaml`。
- V1A 核心切片：已实现 scope 校验、Provider-neutral 元数据记录、物理对象/字段/约束/索引/定义/依赖的规范化，以及 JSON 结果写出；Parquet 写出需要安装项目依赖。
- 当前 Extract 命令支持 Provider-neutral JSON 快照和现有只读数据库适配器；真实 Panorama smoke 已完成对象、字段、约束、索引、依赖和边界对象的结果完整性核验。
- V1A `derive` 命令已可从 canonical facts 重建 Schema 汇总、对象结构轮廓、依赖汇总和失败清单；派生结果不生成 Identity、Grain 或业务语义结论。
- V1A `reconcile` 命令已支持与独立 SQL 基线对账；真实 Panorama 的对象数、字段数、对象名覆盖、Boundary、失败记录覆盖均通过，且全量定义抽取成功，Gate A 为 `PASS`。
- V1A `baseline` 命令已生成独立对象名/字段数量基线；静态 Panorama、Schema 页面、物理 Object Card 和 Manifest 已可由 facts 生成。
- V1B 物理准备切片已实现：`select-sample` 从 Gate A 通过的 TRADEFLOW facts 按 PK/UK/索引/无声明键分层选样，并保留结构相似对照；按用户指定，数字结尾的测试/快照类命名对象只在 V1B sample 中排除，Panorama 物理事实仍完整保留；`deep-derive` 生成样本对象、字段特征、对象特征和结构相似度。该切片不生成业务 Identity、Grain、Role 或 Relation 结论，下一步才进入带 Evidence 的候选推断。
- V1B 第一版候选闭环已实现：`deep-infer` 生成技术 Identity、声明 Grain、保守 Field Role、Inference Result、Evidence Item 和 Candidate-Evidence Link；Object Role 的名称信号和结构相似度只保留为观察，不直接发布候选 Relation/Object Role。无声明键、无关系证据和未确定语义均保留为 `UNKNOWN`。核心案例和 4 个 Holdout 已完成用户确认，11/11 Gold 案例评估无错误；效率证据、用户价值确认和 Gate B 尚未完成。
- V1B Gold Set/Review/Evaluation 已完成核心与 4 个 Holdout 的人工裁定：当前 11/11 `ADJUDICATED` 且自动评估无错误；`deep-evaluate` 继续检查候选证据覆盖、Unknown、错误模式和 Gate B 条件。效率测量模板与可执行测量单已建立，但尚无真实测量和用户价值确认，Gate B 保持 `BLOCKED`，不授权 V1C。
- 全量 Panorama 运行共记录 2,636 个对象、68,458 个字段，表 DDL 和 View SQL 定义均成功；批量定义入口按块落盘并读取，避免一次性保留全部定义文本。
- DDL/View SQL 已接入 Provider 的 `--definition-mode all` 路径；默认 `record-only` 仍只记录能力缺口，避免全景扫描隐式执行大量 DDL 子命令。Parquet 实际写出仍需安装项目依赖。

```text
python -m pytest -q
python -m titans_cognition.cli validate-scope --scope cases/titans-panorama/scope.yaml
```
