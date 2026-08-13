## Why

现有 TRADEFLOW 字段语义 V2 已能从基础概念反查字段与表，但业务审阅证明，仅靠“概念 + Facet + 物理字段”无法清楚说明一个概念有哪些稳定属性表达、这些表达出现于哪些业务上下文，以及相同表达是否跨上下文复用。与此同时，固定 Wiki Tree 快照已经提供可重放的标题与祖先路径，可用于发现候选产品、对象、过程、事件和文档场景，但不得直接冒充业务分类树或正式语义关系。

本 Change 在不修改 V2 Canonical 结果的前提下，建立数据库 Bottom-up 与 Wiki Tree Top-down 的候选语义对齐，并交付“业务导航树 → 属性表达矩阵 → 表达详情”的字段语义地图。

替身验收发现，若将机器候选直接物化为最终属性表达，任何上游误分都会在“放宽合并—误合并—加严冲突—冲突膨胀”之间反复。因此本 Change 将结果明确拆为 `Observation → Hypothesis → Review Decision → Published Projection`：原始事实不变，机器推断不冒充知识，只有满足确定性发布门槛或获得版本化复核决定的表达与关系才进入主地图。

## What Changes

- 新增上下文增强字段语义 Projection，以现有字段语义 V2 和固定 Wiki Tree 快照为只读输入，不回写 Physical Facts、V1/V2 Canonical 或 Wiki 缓存。
- 定义 5 类核心对象：`BusinessConcept`、`BusinessContext`、`AttributeExpression`、`Qualifier`、`TechnicalAsset`；业务对象、主体、事件和度量作为 `BusinessConcept` 的候选语义类型。
- 定义 6 类核心语义关系：`BROADER/NARROWER`、`EXPRESSION_OF`、`APPEARS_IN`、`QUALIFIED_BY`、`RELATED_TO`、`IMPLEMENTED_BY`；导航位置作为独立 Projection，不冒充上下位关系。
- 将“初始名义本金、动态名义本金、多头动态名义本金”等真实出现且有证据支持的组合物化为候选 `AttributeExpression`；Facet 用于解释差异，不消灭稳定表达，也不生成未观察到的笛卡尔组合。
- 属性表达默认跨业务上下文复用；TRS、期权、持仓或通用交易汇总通过多对多 `APPEARS_IN` 关联。只有存在业务定义、粒度或口径差异证据时，才提出上下文特定的拆分候选。
- 从 Wiki Tree 的标题和祖先路径抽取候选语义与文档场景，并与 V2 概念、表达、字段、表上下文进行有界召回和映射；Wiki 目录父子关系只作导航证据，不自动形成业务上下位关系。
- 为候选对象和候选关系统一保存 Evidence、Counterevidence、Method、内部排序分数和 Review Status；页面只显示“已确认、有证据候选、证据不足、存在冲突、已否定”等可读状态，不把分数解释为概率。
- 新增不可变 Observation、完整 Hypothesis、版本化 Review Decision 与 Published Projection 四层边界；`attribute_expressions.jsonl` 和主导航只消费发布合格结果，未合格项保留在调查/复核数据中。
- 将限定轴映射作为版本化配置契约，而不是在代码中随样例补词；持仓方向、交易方向、收付方向、源/目标侧、主体角色及不同状态轴保持正交。
- 交付三栏静态审阅页面：左侧业务语义导航树，中间可按开放限定筛选和比较的属性表达矩阵，右侧当前表达的限定、业务上下文、物理实现与证据；同名物理表达先聚合，再展开到具体 `Schema.Table.Column` 和 Panorama Object Card。
- 首轮仅使用固定 TRADEFLOW 233 表字段语义结果与 Wiki Tree 快照，以“名义本金”验证完整闭环，再使用至少一个不同语义形态的概念验证通用性；不扩展到全 Panorama、完整 Wiki 业务分类或正式企业本体。

## Capabilities

### New Capabilities

- `context-enriched-field-semantic-map`: 定义语义对象、稳定属性表达、开放限定、业务上下文、类型化关系、Wiki/数据双向候选发现、证据治理、导航 Projection 和三栏字段语义地图的行为契约。

### Modified Capabilities

- `cognition-delivery-governance`: 授权在固定 TRADEFLOW 与固定 Wiki Tree 快照内构建独立候选映射和审阅 Projection，同时继续禁止正式本体、自动 Canonical 写回、全 Wiki/全 Panorama 规模化和业务验收替代。

## Impact

- 影响字段语义派生模块、Wiki Tree 快照读取、候选/关系 Schema、CLI、Manifest、诊断报告、静态审阅页面和相关测试。
- 复用现有本地 Python、JSONL/YAML、内容哈希、分页分片和 Panorama 链接；不引入图数据库、向量数据库、远程服务、业务数据行读取或新的 Provider SDK 授权。
- 现有 `restructure-field-concepts-as-faceted-semantic-index` 保持独立，44/45 的工程结果不被本 Change 自动宣告通过业务验收。
