## Context

现有字段语义 V2 已输出基础概念、表达、字段绑定、Facet、Conflict/Unknown 和物理 ID，但其审阅页没有稳定表达层和业务上下文层，用户无法从“名义本金”看清真实表达族。固定 Wiki Tree 快照包含 7,411 条可见目录节点、最深 10 层、固定内容哈希及错误清单，可用于候选语义发现；目录标题和父子路径本身不是业务事实。参见 `proposal.md` 与两份 delta spec。

## Goals / Non-Goals

**Goals:**

- 在不改变 V2 Canonical 的前提下派生稳定 AttributeExpression、候选上下文和类型化关系。
- 以数据库候选驱动 Wiki 候选召回，避免全量两两匹配和无界模型调用。
- 让对象、关系、Evidence 和 Review 分层，可重放、可否定、可保留 Unknown。
- 先用 Canonical/Markdown 调查卡证明信息模型，再生成双树三栏静态页面。

**Non-Goals:**

- 不建立正式 Data Concept/Data Entity、本体、图数据库或治理工作流平台。
- 不把 Wiki Tree 全量分类为业务树，不批量读取全部页面正文。
- 不重新训练或改写 V2 字段语义抽取，不扫描业务数据行。
- 不将上下文作为属性表达的强制分区，也不预生成所有限定组合。

## Decisions

### 1. 新结果是只读 Projection，不回写 V2

推荐输出：

```text
context-enriched-field-semantic-map/
├─ business_concepts.jsonl
├─ attribute_expressions.jsonl
├─ qualifiers.jsonl
├─ business_contexts.jsonl
├─ semantic_relations.jsonl
├─ assertions.jsonl
├─ evidence_refs.jsonl
├─ manifest.json
├─ diagnostics/
└─ review/
```

`business_concepts` 可引用 V2 `concept_id`，`IMPLEMENTED_BY` 引用稳定 `column_id/asset_id`。运行级语义 ID 由规范内容和输入版本确定性生成，但不承诺成为跨 Schema 企业主数据。

构建内部与输出边界调整为：

```text
SemanticObservation
  -> SemanticHypothesis
  -> ReviewDecision (optional, versioned)
  -> PublishedProjection
```

`semantic_observations.jsonl` 保存源事实引用及其原文；`semantic_hypotheses.jsonl` 保存全部机器候选和状态；`review_decisions.jsonl` 只保存独立处置；现有 BusinessConcept、AttributeExpression、Qualifier 和六类关系文件属于 Published Projection。未满足门槛的 Hypothesis 不因页面需要被提升为发布对象。

三个讨论中的中间产物 `wiki_semantic_candidates`、`data_semantic_candidates` 和 `semantic_mapping_candidates` 作为 `diagnostics/` 或构建输入保留，不把它们当最终用户交付。

**替代方案：** 在 V2 四个 JSONL 中加入 Context 和 Wiki 字段。拒绝，因为会改变已完成的字段语义契约并混淆 Canonical 与上下文候选。

### 2. AttributeExpression 是观察节点，Qualifier 是解释结构

同一个表达可跨上下文复用：

```text
BusinessConcept: 名义本金
  <- EXPRESSION_OF - AttributeExpression: 初始名义本金
       - QUALIFIED_BY -> 时点=初始
       - APPEARS_IN -> TRS候选
       - APPEARS_IN -> 期权候选
       - IMPLEMENTED_BY -> 多个Column
```

物化门综合真实字段/注释复现、Wiki表达或其他结构证据；单个字段可以形成 `PROVISIONAL` 表达，但不得因所有可能 Facet 组合而扩张。表达树采用“子节点限定集合严格包含父节点、且选择确定性主父”的 Projection；其他可行父路径作为关系提示，不形成额外语义断言。

Facet 还必须区分“表达限定”和“上下文提示”。只有当限定词在属性表达或物理字段名中词法化出现时，才参与 AttributeExpression 身份；仅由说明性注释、表场景或上游推断带出的生命周期信息保留为 `contextual_qualifiers`，不得把同名同物理字段拆成两个表达。例如 `TARGET_HMS_ACCOUNT_ID` 的“成交”仅来自说明性上下文时，仍与同名“对手方对冲账户”合并；`TRADE_AMOUNT` 的“成交”直接出现在字段语义中时仍是表达限定。

**替代方案：** 运行时动态拼接所有 Facet。拒绝，因为无法稳定搜索、统计和连接跨表实际表达。另一替代是把每个表达当 `NARROWER` 概念；拒绝，因为限定表达不等于概念分类层级。

### 3. Context 是多对多标签化语义对象，不是流水线强制层

BusinessContext 可包含产品、业务对象、过程或场景维度的候选组合，但必须保存组成部分和证据，不能只存不可解释的标签。无上下文证据时表达仍然有效。只有差异证据触发 `SPLIT_SUGGESTION`，不自动复制表达。

**替代方案：** 为 TRS/期权/持仓分别生成表达树。拒绝，因为通用交易汇总和跨产品属性会被强迫拆分，产生重复。

### 4. Wiki Tree 先规范化和候选化

确定性阶段完成：去编号/日期/工单噪声、保留原题、构造祖先路径、识别文档场景、抽取词项、统计共现和受控候选类型。页面正文仅在映射候选需要消歧时进入待读队列；首轮可使用现有页面缓存或有界 `opencli wiki page`，但任何正文读取必须进入 Manifest 和 Evidence Ref。

LLM 可对压缩后的标题路径簇、类型歧义和冲突映射提出候选，不进入必需主线，不自动更新规则或关系。

**替代方案：** 把目录父子边转换为业务树。拒绝，因为目录混合设计、测试、验收、生产事件、年份和团队空间。

### 5. 映射采用分阶段有界召回

```text
V2 Concept/Expression/Column/Table
  -> data candidate + lexical/context tokens
  -> inverted Wiki candidate index
  -> top-K lexical/path/context recall
  -> compatible-type checks
  -> evidence/counterevidence aggregation
  -> assertion status
```

召回至少区分文字重合、Alias重合、产品上下文重合、对象/过程兼容、目录场景噪声和矛盾上下文。Top-K、每概念/表达预算及正文读取预算写入配置和 Manifest。分数只用于排序，外部状态由证据规则和Review决定。

### 6. Assertion 承载治理，而不是把 Candidate 变成关系类型

对象候选和语义关系分别有稳定内容；`assertions` 记录 subject、predicate、object/value、status、method、method_score、evidence_refs、counterevidence_refs、review_decision_ref。Confirmed/Rejected 是处置状态，不覆盖原始候选或删除证据。

### 7. 页面采用双树三栏和分片索引

```text
左栏：Navigation Projection
中栏：选中Concept的AttributeExpression Faceted Matrix
右栏：选中Expression的Qualifier、Context、Physical、Evidence
底部/折叠：Related Concepts与技术详情
```

首屏只加载导航摘要和选中概念的表达摘要；表达、字段实例、Wiki证据按概念/表达哈希分片并分页。全局搜索使用紧凑的概念/表达/物理名称索引，避免首次输入就加载全部字段目录。

### 8. 两阶段验收阻止再次“页面掩盖模型失败”

阶段一先生成名义本金调查卡，必须能回答：有哪些稳定表达、每个表达的限定、跨哪些上下文复用、哪些物理命名/字段/表实现、哪些邻近概念、证据与冲突是什么。表达之间的限定可交叉组合，不强制解释为唯一父子层级；中栏以分面矩阵比较真实表达。再用至少一个不同形态概念验证开放限定和非金额关系。

阶段二仅在阶段一通过后生成完整页面，并以真实浏览测试验证搜索、两棵树、分页、表链接和竞态。工程测试通过与用户业务验收继续分开记录。

### 9. 语义清洗采用语料复现发现，不枚举业务特例

字段语义 V2 与上下文地图之间增加只读 `Semantic Cleaning Projection`：从整个概念语料自动发现被多个表达复用的最长稳定核心，分离前后修饰片段，并结合既有 Facet、字段名、注释、类型和物理分布形成候选族。固定规则只处理 `ID/编号/编码` 等语言级格式等价，不列举交易对手、交易流水、名义本金或产品专用词。

确定性阶段仅自动应用语言级等价；其余候选输出 `semantic_normalization_candidates` 和 `semantic_review_queue`。同物理字段名但中文注释不同的情况必须进入复核队列。模型或人工只能在 `EQUIVALENT_ALIAS / QUALIFIED_VARIANT / RELATED_ATTRIBUTE / CONFLICT / DEFER` 中处置，结果写入独立版本化决策资产，不覆盖源字段、注释或 V2 Canonical。

最终 Projection 不消费未经复核的 corpus modifier。若同一物理列存在多个直接基础概念，或中文观察表达与基础概念明显不一致，则保留所有来源并把相关表达降为 `CONFLICT`。限定轴在 Projection 中按语义正交性规范化：源侧/目标侧与主体角色分开，动态/固定、可用/冻结、预估和累计不再共用一个笼统状态轴；原始 Facet 仍保留在上游只读输入和证据链中。

复核包使用 provider-neutral JSON；导入器校验 `item_key` 白名单、决策枚举、重复响应和必填理由，只输出 `IMPORTED_NOT_APPLIED` 决策记录。任何导入结果都不会自动回写候选族、表达、字段注释或人工 Review。

### 10. 发布门槛独立于候选生成

候选生成追求召回，Published Projection 追求不误导。首轮确定性发布仅接受：精确语义一致、语言级标识符等价、由同源 Facet 完整解释的限定表达，或版本化 ReviewDecision 明确接受的假设。裸子串、不同中文表达、跨概念物理绑定、同名异注释、仅 Wiki 目录支持和未解释残差不得自动发布；它们进入 `INSUFFICIENT_EVIDENCE`、`CONFLICT` 或复核队列。

发布 Gate 必须同时检查来源 Observation 与 Published Projection，使用独立反例集验证“应拦截但未拦截”的情况，不能只检查构建器已经识别出的 Conflict 是否自洽。

限定轴由 case 配置中的版本化 registry 映射，例如把上游 `direction` 分解为持仓方向、交易方向和收付方向，把 `party_role` 的源/目标侧分离为流向侧。registry 是通用值映射，不包含名义本金、交易对手等概念特例。

## Risks / Trade-offs

- [Wiki标题语义弱且目录结构混杂] → 单独抽取 Document Context，目录只召回候选，关键关系需正文/数据库/人工证据。
- [AttributeExpression 数量膨胀] → 只物化真实观察组合，设置支持状态、合并等价表达并分页；禁止笛卡尔生成。
- [表达树主父选择掩盖多路径] → 主父只属于 Projection，显示其他限定路径，不写成 `BROADER`。
- [表名让 Context 产生循环自证] → 数据上下文与 Wiki 上下文保留来源独立性；同源派生不得计作多份证据。
- [当前V2存在误分] → 本 Change 不修正 V2；继承的异常在诊断和业务卡中显式暴露，必要时回到上游 Change 修复。
- [静态页面随全 Panorama 放大] → 首轮固定范围、分片索引、分页与加载预算；不得据此自动扩展。

## Migration Plan

1. 冻结并记录 V2、Wiki Tree、配置和 Panorama 链接根的哈希。
2. 生成独立新目录及调查卡，不修改现有审阅入口。
3. 通过模型 Gate 后生成新页面，与旧页面并存。
4. 用户明确接受新入口后才更新文档中的推荐审阅路径。
5. 回滚时删除/忽略新 Projection 并恢复旧入口；V2和Wiki缓存无需恢复。
