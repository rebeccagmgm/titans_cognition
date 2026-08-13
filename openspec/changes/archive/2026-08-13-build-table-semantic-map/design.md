## Context

现有 `build-bounded-evidence-foundation` 已在固定 TRADEFLOW 233 张主体表上生成 Schema Matching、Leiden结构邻域和多维标签传播结果；实际运行产生25个候选族和903个业务分类候选。真实对照发现，结构邻域会因交易ID、审计字段等通用结构把配置、费用、审批、报表和业务记录混在一起；预设维度也会把全部表标为TRADEFLOW、把大量表传播为SWAP或CONTRACT_BOOKING。因此该结果适合作为调查底座，不足以成为读者面对的表语义。

固定Physical Facts同时包含477张TRADEFLOW表，其中244张后缀表被旧分类排除。名称初步归并发现53个多成员物理变体候选组、涉及221张表，但名称相似不能证明备份或等价。字段语义与上下文增强字段地图正在独立建设，本Change只能读取固定结果作为辅助证据，不得反向改写或与其形成循环证明。参见 `proposal.md` 与 `specs/table-semantic-map/spec.md`。

## Goals / Non-Goals

**Goals:**

- 在既有物理事实之上形成独立、可重放的表语义Projection。
- 将表身份、上下文、职责、表组和表间关系拆成可分别审阅的候选断言。
- 区分业务协作表组、物理变体组和结构邻域，并保留跨组、多值、冲突与Unknown。
- 让字段和Wiki真正用于支持、区分和反驳，而不是生成高覆盖标签。
- 先用五组真实调查卡验证模型，再生成读者导航。

**Non-Goals:**

- 不建设正式本体、通用元数据平台或跨Schema方法。
- 不重新实现或修正字段语义V2、上下文增强字段地图和旧分类流水线。
- 不读取业务数据行，不推断生产真实性、行级唯一性或业务公式。
- 不要求每张表唯一归类，不以标签数量或覆盖率作为质量目标。
- 不把所有后缀表自动认定为备份、废弃或等价版本。

## Decisions

### 1. 新结果是独立Projection，不覆盖任何上游结果

表语义命令读取固定输入并写入独立运行目录，建议逻辑数据集为：

```text
table-semantic-map/
├─ table_profiles.jsonl
├─ table_context_candidates.jsonl
├─ table_anchor_candidates.jsonl
├─ table_responsibility_candidates.jsonl
├─ table_groups.jsonl
├─ table_group_memberships.jsonl
├─ table_relations.jsonl
├─ assertions.jsonl
├─ evidence_refs.jsonl
├─ review_decisions.jsonl
├─ manifest.json
├─ diagnostics/
├─ investigation-cards/
└─ review/
```

`table_profiles`只保存稳定物理引用和候选结果摘要；候选、关系、证据和人工决定分别落盘，避免把一个宽表变成新的万能Claim Ledger。ID使用稳定物理ID或内容寻址ID；机器表组ID默认运行级稳定，只有人工Reviewed实体才能获得跨运行维护身份。

**替代方案：** 直接扩展旧`business_classification_results`。拒绝，因为旧契约以预设维度和标签传播为中心，无法表达异构业务协作组、物理变体和关系治理，也会改变历史运行解释。

### 2. 表语义由开放断言组成，不预设完整标签树

每张表可以获得多值的`BusinessContext`、`BusinessAnchor`和`TableResponsibility`候选。候选值从真实表语料、Wiki和人工种子归纳，配置只保存版本化的规范化、别名和已审阅值，不先写死完整分类枚举。

表间关系使用版本化Predicate Registry，首轮可包含`SPECIALIZES`、`EXTENDS`、`CONTAINS_DETAIL`、`EVENT_OF`、`CURRENT_HISTORY`、`CONFIGURES`、`INSTANTIATES`、`MAPS_TO`、`RESULT_OF`、`PHYSICAL_VARIANT`和`RELATED_TO`候选。Registry必须声明允许端点、方向、对称性和最低证据条件；证据不足时退回`RELATED_TO`或Unknown，不追求精确关系覆盖率。

**替代方案：** 先建立“产品→对象→角色”的固定三级分类。拒绝，因为共用表、跨产品关系和同一对象的事件/配置/结果会被强制复制或错误归属。层级只在导航Projection中生成。

### 3. 三种表集合使用不同生成与发布门

- `STRUCTURAL_NEIGHBORHOOD`：直接读取现有相似边/Leiden结果，只作为调查召回，不增加业务证据票数。
- `PHYSICAL_VARIANT_GROUP`：以保守名称归一化召回，再比较对象类型、字段签名、键、注释和结构差异；发布候选时必须展示主体选择和反例。
- `BUSINESS_COLLABORATION_GROUP`：围绕业务锚点，由表级直接语义、字段桥接、Wiki正文明确提表、人工知识或多源一致关系形成；成员必须带独立职责，不要求结构相似。

同一表可以属于多个业务协作组和一个或多个竞争物理变体候选，但结构邻域不会自动成为另外两种组。

**替代方案：** 统一使用`Object Family`。拒绝，因为三种集合的稳定性、证据和读者问题不同，统一命名会再次混淆“像谁”和“共同做什么”。

### 4. 233张主体表与244张后缀表分层处置

首轮语义画像以旧分类实际处理的233张主体表为主，保证可与历史结果逐表比较。477张Physical Facts全量进入变体发现：

1. 生成保守基础名和规则原因；
2. 优先检查是否存在无后缀主体；
3. 比较字段集合、键、注释和对象类型；
4. 输出`LIKELY_VARIANT`、`COMPETING_PARENT`、`STANDALONE`或`UNKNOWN`等候选处置；
5. 审阅页面默认折叠高支持变体，但始终可展开全部成员和差异。

首轮不得把后缀表加入业务标签传播，也不得通过排除它们制造100%分类覆盖。

**替代方案：** 继续完全排除后缀表。拒绝，因为用户无法判断477张表与233张分析主体之间的关系，历史版本和真实并存分支也会静默消失。

### 5. 字段辅助证据以“角色”而不是“投票”接入

对每张表构造有界Field Support Summary，分开保存：

- 物理字段、注释、类型和声明键；
- 锚点字段组合，如合约、腿、事件、持仓、配置和源/目标标识；
- 固定字段语义运行中的候选概念、限定和来源；
- 支持、区分、反驳三种作用；
- 根来源集合与可用状态。

字段摘要只参与具体Assertion的证据评估，不进行表级标签多数投票。若字段侧上下文来自表名或表场景，该路径与表名归并为同一`root_source_family`，不得形成循环自证。字段运行缺失时，相关任务为Not Evaluable但主流程可继续。

**替代方案：** 按字段标签占比生成表标签。拒绝，因为宽表、审计字段和通用ID会主导数量，且字段侧本身可能使用了表上下文。

### 6. Wiki采用两阶段有界证据

第一阶段只读取固定Tree快照，保存标题、原始祖先路径、文档场景和候选词，用表名、注释、锚点和字段摘要构造Top-K召回。目录父子边永不直接产生业务上下位关系。

第二阶段只读取已固定缓存或配置批准的少量正文：正文明确提表时形成`MENTIONS_TABLE`证据；明确列出核心关联、用途或输入输出时形成候选组或关系证据。每个片段记录pageId、版本、hash和定位。测试、生产事件、项目、年份和团队目录作为`DocumentContext`，不成为表标签。

**替代方案：** 抓取整个Wiki并构建分类树。拒绝，因为目录混合业务、组织、项目和事件，且全量正文超出本Change范围。

### 7. Assertion层统一治理标签、成员关系和表间关系

所有判断落为Assertion：

```text
subject + predicate + object/value
+ method/version
+ evidence_refs/counterevidence_refs
+ root_source_families
+ method-local score/rank
+ inference outcome
+ review_decision_ref
```

旧传播候选可以作为`STRUCTURAL_PROPAGATION_HINT`导入，但没有直接证据时不得进入推荐表标签。人工Review Decision只处置候选，不修改原始证据或机器输出。页面使用“有直接证据候选、仅结构线索、存在冲突、证据不足、已确认、已否定”等业务可读状态，不显示概率或星级可信度。

### 8. 五组调查卡先验证信息模型

模型Gate固定覆盖：

1. `TRD_OTC_TRADE / REF_TRS / REF_TRS_LEG / TRD_TRS_EVENT / POS_* / TRD_TRS_UDLY_DEAL_ALLO`；
2. `TRD_OTC_TRADE / REF_OTC_OPTION_DEAL / REF_OPTION_DEAL_STRUCTURE / TRD_OPTION_EVENT / REF_OTC_CONTR_MARGIN_PARAM`；
3. `POS_TRS_LEG_CURRENT_POS / POS_TRS_LEG_HIS_POS`；
4. `REF_IRS / OTC_OPTION_PARAMETER / REF_CONTR_DAILY_MARGIN_PARAM / ADM_UPDATE_AUDIT_LOG / TRD_FAST_TRS_FEE_LOG / TRD_PRE_TRADE_VALIDATION_LOG / TRD_OTC_CONTR_REPORT / TRD_OTC_REPORT_RESULT / TRD_ATP_TRADE_REPORT`等名称反例；
5. `TRD_OPTION_DEAL_MAPPING / TRD_OTC_CONTR_MAIN_SUB_MAPPING / TRS_CONTRACT_MAPPING_CONFIG / TRS_CONTRACT_MAPPING_RELATION`。

每张卡必须展示表身份、上下文、职责、组成员关系、关系端点、直接证据、结构线索、反证和Unknown。Gate先验证“能否解释差异”，不验证全量覆盖率。失败Artifact保留在diagnostics中，完整页面不得先行掩盖失败。

### 9. 页面是浅层导航与审阅Projection

Gate通过后生成静态页面：左侧为“业务上下文→业务锚点/协作表组”，中间为成员职责与表目录，右侧为表语义画像、关系、字段辅助摘要和证据。另提供物理变体、结构邻域、Conflict和Unknown专门入口。

导航路径只保存为Projection；同一表在多个入口复用同一`asset_id`和详情分片，不复制Canonical候选。首屏使用紧凑目录，表、组、证据和变体详情按hash分片并分页。

### 10. 运行必须有界、可回滚且与并行字段工作隔离

配置固定表范围、变体规则上限、结构邻域Top-K、Wiki召回与正文预算、每表候选数、关系候选数、调查卡范围和页面分片上限。超过硬上限时阶段停止为PARTIAL或FAILED，不自动扩大预算。

新命令和输出目录独立存在；回滚只需删除或忽略新运行及恢复本Change代码，不触碰旧分类、字段语义、Wiki缓存和Physical Facts。实现时必须先读取当前脏工作树，复用并行字段模块的公共契约但不改写其行为。

### 11. 替代评审后的返工采用发现层、评审层与发布层三段式

2026-08-12 替代评审证明首轮实现把配置种子近似实现成了封闭词表。返工后：

- 发现层保存名称、注释、字段和正文中观察到的原始职责表达，不要求先属于规范枚举；
- 评审层可以把多个原始表达映射为规范值，但必须保留原表达、映射方法、差异和Unknown；
- 发布层只展示满足直接证据条件的推荐职责，未满足条件的种子命中仍留在调查视图。

现有固定责任值保留为兼容的种子Registry，不再代表完整业务分类。首轮优先解决固定反例中已经观察到的职责差异，不尝试一次建立全TRADEFLOW正式词典。

**替代方案：** 继续扩充固定枚举直到覆盖反例。拒绝，因为新表仍会不断迫使枚举膨胀，且无法区分原始表达与评审规范化。

### 12. 字段辅助通过Assertion-Evidence链接生效

Field Support Summary继续作为浏览摘要，但不能证明字段已参与判断。返工增加候选级链接：字段证据必须指向具体表级Assertion，并标明`SUPPORTS`、`DISTINGUISHES`、`COUNTERS`或`NOT_USED`。同根来源仍合并，名称派生字段上下文不得成为第二票。

首轮只为具有清晰组合证据的职责建立确定性链接，例如审批字段组合、事件标识与事件时间、源/目标标识组合、配置标识组合；单一通用ID或审计时间不产生职责。

**替代方案：** 用字段标记数量调整候选分数。拒绝，因为这仍是隐式投票，无法说明哪个字段支持了哪条判断。

### 13. 调查集合与业务协作组使用不同实体状态

配置中的五组表只生成`INVESTIGATION_SET`输入和调查卡。只有同时满足以下条件才升级生成`BUSINESS_COLLABORATION_GROUP`候选：

1. 每个成员至少有一个非配置来源的职责Assertion；
2. 每个成员至少有一个直接Evidence Ref；
3. 组内成员通过已登记Predicate或证据不足时的显式`RELATED_TO`候选形成连通图；
4. 每条边保留方向、证据、反证和Unknown，不以共享字段冒充外键。

若不满足，卡片必须显示缺少职责、证据或连接的成员，不能用配置成员列表生成业务组。

### 14. Gate验证必要结果而不只验证已有输出

每张调查卡定义最低回答契约：关键成员、预期差异问题、至少一个应被证明或保持Unknown的关系问题，以及字段/Wiki辅助是否实际生效。Gate同时检查：

- 已输出对象是否合法；
- 必要对象是否存在；
- 关键图是否连通；
- 字段证据是否连接到具体Assertion；
- 全局预算是否造成按表顺序偏置；
- 页面是否只在所有关键卡通过后标记就绪。

Wiki候选先按表独立生成Top-K，再进行确定性轮转/排序截断总预算；诊断保存被截断表数和每表候选分布。这样总预算仍有界，但不会由资产遍历顺序决定谁获得全部机会。

### 15. 测试数据聚合证据通过配置冻结而不进入建图运行时查询

用户已单独授权对 `TRD_OPTION_EVENT.KEY_OPTION_DEAL_ID` 与 `REF_OTC_OPTION_DEAL.KEY_OTC_TRADE_ID` 执行一次只读、单行聚合核验。建图代码不持有数据库连接，也不重跑 SQL；配置只冻结查询指纹、测试环境、核验时间和不含业务键值的聚合统计。

精确 `EVENT_OF` 需要两个根来源：表注释/事件字段支持事件职责，测试快照支持键值匹配和一对多基数。任何一项缺失、快照未授权、目标键不唯一或事件侧存在未匹配，都退回 `RELATED_TO` 或 Unknown。该证据不成为物理 FK、生产事实或业务确认。

**替代方案：** 在每次建图时查询测试库。拒绝，因为这破坏确定性、扩大数据访问范围，并使一次用户授权变成持续授权。

## Risks / Trade-offs

- [表语义仍可能受命名规则主导] → 名称只生成候选，调查卡必须展示字段反例和直接/传播来源分层。
- [业务协作组变成新的人工目录] → 每个成员要求职责与关系证据，组ID默认运行级，Reviewed后才允许维护身份。
- [共享字段造成伪关系] → 共享ID只作召回，精确Predicate要求组合证据和反例检查。
- [字段侧结果漂移或形成循环] → 固定哈希、保存根来源、辅助输入可Not Evaluable、禁止反向写回。
- [物理变体折叠隐藏真实并存表] → 默认候选、展示结构差异、允许竞争主体和Standalone处置。
- [Wiki正文不完整或过时] → 记录版本、只引用必要片段、保留Counterevidence和Unknown，不把实现文档当生产事实。
- [关系Registry过早本体化] → 首轮仅使用可验证关系候选，允许退回RELATED_TO，第二批表验证前不宣称正式关系体系。
- [页面再次制造完成错觉] → 模型Gate先行，Manifest和页面同时展示reader/business/scale边界。
- [开放原始表达产生大量噪声] → 原表达只进入发现层，推荐发布仍要求直接证据和可解释规范化。
- [为满足连通性而滥发RELATED_TO] → 每条RELATED_TO仍需明确的非配置调查线索；无法支持时保留断点和Unknown。

## Migration Plan

1. 固定233张主体表、477张全量Physical Facts、旧分类运行、字段语义运行、Wiki Tree/已使用正文缓存和配置哈希。
2. 在新目录建立类型化契约、Evidence/Assertion治理和独立CLI，不修改任何上游文件。
3. 先实现物理变体候选、表级信号摘要和旧结构邻域只读导入。
4. 加入字段辅助摘要、Wiki有界召回、表级候选与关系生成，运行五组调查卡。
5. 只有模型Gate通过后生成完整审阅Projection，并取得用户对限定表组的审阅结果。
6. 回滚时删除或忽略新运行并恢复本Change差异；上游结果没有被覆盖，无需数据恢复。
