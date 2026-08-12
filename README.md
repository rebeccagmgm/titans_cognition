# TITANS Cognition

TITANS Cognition 的唯一交付目标，是形成一张可从业务区域、业务对象和生命周期下钻到表、粒度、键、关系、证据与 Unknown 的 TITANS 业务全貌。项目从测试库只读元数据起步，并保留可检查的结构认知候选；物理目录、规则、Gold Set、评测器和静态页面只是支撑资产，不是目标本身。项目不建设通用元数据平台或正式业务本体。

## 当前状态

- 当前结论：物理提取底座和 TRADEFLOW 结构规则原型可复用，但业务全貌尚未交付。
- 数据环境：测试库，只读元数据盘点；不扫描业务数据行。
- 当前授权：冻结 V1C、全量深度推断和方法泛化；仅允许当前 GPT 会话对固定 TRADEFLOW Evidence Pack 做离线候选审阅，通用 SDK 仍禁用，Gate B 不产生规模化授权。
- 完整基线：[docs/current-status-baseline.md](docs/current-status-baseline.md)。
- V1 存储：Parquet/JSON/YAML + DuckDB 分析，不引入 PostgreSQL、Neo4j、DataHub 或 OpenMetadata。

## 历史工程阶段

这些标签用于描述已有工程资产，不能替代读者交付、业务验收或规模化授权。

| 阶段 | 工程范围 | 当前解释 |
|---|---|---|
| V1A Panorama | 盘点当前纳入的 TITANS Schema，生成物理对象卡和 Schema 入口地图 | 已有一次真实物理提取与对账证据，不等于业务全貌 |
| V1B Deep Sample | 在 TRADEFLOW 分层样本上运行 Identity → Grain → Role → Relation → Evidence | 已有结构推断原型和规则回归证据，不证明独立方法有效或业务可用 |
| V1C Deep Scale | 历史规划中的全量深度推断及 Family、Field Concept、Wiki/LLM | 当前禁止启动；必须经过后续交付、业务验收和独立授权 |

三个阶段使用同一工程和同一套物理事实。自动化 Gate、Gold Set 或用户效用字段均不能自动触发 V1C。

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
- V1B 物理准备切片已实现：`select-sample` 从 Gate A 通过的 TRADEFLOW facts 按 PK/UK/索引/无声明键分层选样，并保留结构相似对照；按用户指定，数字结尾的测试/快照类命名对象只在 V1B sample 中排除，Panorama 物理事实仍完整保留；`deep-derive` 生成样本对象、字段特征、对象特征和结构相似度。
- V1B 结构候选原型已实现：`deep-infer` 生成技术 Identity、声明 Grain、保守 Role、Inference Result、Evidence Item 和 Candidate-Evidence Link。这些结果只说明规则可运行并保留证据边界，不代表已理解对应业务对象或生命周期。
- V1B Gold Set/Review/Evaluation 保留核心与 4 个 Holdout 的既有裁定：当前 Gold 与 `stage0-tradeflow-v1b-comments-20260810` 保存运行重算为 11/11 `ADJUDICATED` 且无自动错误；更早的 physical run 已被后续 comment 修复取代，不应与当前 Gold 混用。11/11 只表示当前结构规则回归一致，不证明业务真实性、读者可用性或用户价值。旧 Gate B 保持工程回归用途，当前为 `BLOCKED`，且即使未来 `PASS` 也不授权 V1C。
- 全量 Panorama 运行共记录 2,636 个对象、68,458 个字段，表 DDL 和 View SQL 定义均成功；批量定义入口按块落盘并读取，避免一次性保留全部定义文本。
- DDL/View SQL 已接入 Provider 的 `--definition-mode all` 路径；默认 `record-only` 仍只记录能力缺口，避免全景扫描隐式执行大量 DDL 子命令。Parquet 实际写出仍需安装项目依赖。
- TRADEFLOW 字段概念 V1 已形成独立的概念—字段—表候选导航；LLM 辅助审阅作为旁路，只对统一算法选出的疑难簇生成最小 Pack，通过当前 GPT 会话离线导入结构化候选，不修改 V1 概念或字段链接。

## 字段概念 LLM 辅助审阅

该流程分为三个可独立重放的阶段：

```text
python -m titans_cognition.cli prepare-field-concept-llm-review \
  --field-concepts-dir <run>/field-concepts \
  --config cases/tradeflow/field-concept-llm-review.yaml \
  --output <run> \
  --max-packs 8 \
  --token-budget 24000

python -m titans_cognition.cli import-field-concept-llm-review \
  --review-dir <run>/field-concepts/llm-review \
  --responses <responses.jsonl> \
  --model-id <approved-model-id> \
  --cache-dir output/.cache/llm-field-review

python -m titans_cognition.cli render-field-concept-llm-review \
  --review-dir <run>/field-concepts/llm-review \
  --source-panorama-root <panorama-root>
```

`prepare` 用疑难度和整次 Token 预算截断 Pack；`import` 逐行校验动作、Pack 哈希和 Evidence ID 白名单；`render` 只展示基线与候选差异，并按需分页字段。缓存命中只表示输入、Prompt、契约和模型标识相同，不代表候选已被接受。未获 D-005 Provider 授权时，SDK 路径保持 `NOT_EVALUABLE`；启用 SDK 或将候选写回正式概念树都需要另行授权。

```text
python -m pytest -q
python -m titans_cognition.cli validate-scope --scope cases/titans-panorama/scope.yaml
```
