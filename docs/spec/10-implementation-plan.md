# 10 实施计划

## TRADEFLOW 字段语义 V2 有界重构

`restructure-field-concepts-as-faceted-semantic-index` 在固定 233 表输入上分两段执行：先生成 Canonical 结果、V1→V2 对齐和五类调查报告；结构不变量及结果级双向查询通过后，才生成有界审阅 Projection。字段语义按“宽字段族 → 稳定复合概念 → 可组合限定条件”组织，禁止仅取日期/金额等尾词作为所有字段的基础概念。当前 GPT 用于压缩统计和代表样本的全局方向审阅，不替代确定性运行、不启用 Provider SDK，也不把模型判断自动写回 Canonical。另一个 Schema、正式本体和表级业务分类组合均需独立授权。

## 1. 实施结论

历史工程按三道阶段门组织，但阶段门只约束对应工程范围：

```text
V1A Panorama：先看全
        ↓ Gate A
V1B Deep Sample：运行结构原型和规则回归
        ↓ Gate B（不产生扩展授权）
V1C Deep Scale：当前冻结
```

三个阶段位于同一工程并复用 Physical Facts。V1A/V1B 成功不代表业务全貌交付；V1C 只有在读者交付、业务验收和独立规模化授权全部成立后，才能通过新的 Change 启动。

## 2. 建议工程结构

```text
titans-cognition/
├─ src/titans_cognition/
│  ├─ extract/
│  ├─ normalize/
│  ├─ panorama/
│  ├─ infer/
│  ├─ evidence/
│  ├─ evaluation/
│  ├─ llm/                 # V1C才创建实际实现
│  └─ render/
├─ cases/
│  ├─ titans-panorama/
│  │  └─ scope.yaml
│  └─ tradeflow/
│     ├─ scope.yaml
│     ├─ sample.yaml
│     ├─ terminology.yaml
│     ├─ gold-set.yaml
│     └─ review_decisions.yaml
├─ rules/
├─ prompts/                # V1C
├─ schemas/
├─ tests/fixtures/
└─ output/
```

V1不创建插件框架、Provider注册中心、通用规则DSL或候选类型注册平台。目录只在对应阶段出现真实代码时创建，不预建空层。

## 3. 阶段0：开工前决策

### 必须解决

- 确认Panorama Schema allowlist及排除项。
- 确认Oracle只读元数据访问方式和当前可见权限。
- 按能力降级矩阵探测对象、字段、约束、索引、DDL、View SQL和Dependency可见性。
- 重新核验TRADEFLOW表、视图和其他对象数量；477只作为规划基线。
- 确认输出目录的数据敏感级别。
- 确认独立Git仓库是否初始化。

Wiki形态、LLM Provider和数据外发不阻塞V1A/V1B，不应在阶段0提前建设。

### 退出门槛

- Extractor范围可以写成明确allowlist。
- 未经确认的安全和访问决策没有被代码默认值替代。

## 4. V1A：TITANS Panorama

### 4.1 目标

用最短路径回答“当前纳入的TITANS测试库里有什么”，并形成第一张真正可浏览的全貌地图。

### 4.2 实现

1. Scope Resolver和Oracle只读Extractor。
2. 对象、字段、注释、约束、索引、定义、依赖及失败清单标准化。
3. Schema级数量、对象类型、注释覆盖、命名特征、结构轮廓和依赖概况。
4. Panorama首页、Schema页面、对象清单和物理Object Card。
5. Manifest、结果Schema校验和有界运行日志。

### 4.3 明确不做

- Identity、Grain或业务用途全库推断。
- Object Family和Field Concept。
- SQLGlot列级Lineage。
- Gold Set认知准确率。
- Wiki和LLM。
- Evidence Pack或LLM接口占位实现。

### 4.4 Gate A

- allowlist内每个可见对象都有事实记录或失败记录。
- 表、视图、字段、约束等数量能与独立盘点SQL对齐。
- 无业务数据行查询。
- 任一对象可从Panorama在三次以内导航到物理Object Card。
- 用户能够看清各Schema有什么、注释覆盖如何、主要依赖和未知在哪里。

Gate A未通过，不得进入V1B。

## 5. V1B：TRADEFLOW Deep Sample

### 5.1 目标

不是覆盖477张表，而是在分层样本上建立以下可运行、可回归的结构推断原型：

```text
Physical Fact
→ Identity
→ Grain
→ Field/Object Role
→ Relation
→ Evidence / Counterevidence / Unknown
```

### 5.2 样本

样本在V1A事实完成后选择，不预先凭名称编造。必须覆盖：有PK、技术PK、无PK、复合键、事件、状态/快照、映射、结果、日志、结构相似反例和Unknown。样本规模由结构覆盖决定，不以固定百分比代替。

### 5.3 实现

1. 样本级Column/Object Feature。
2. Identity、Grain、Field/Object Role和Relation类型化候选。
3. Inference Result，严格区分Single、Competing、Unknown和Not Evaluable。
4. 最小Evidence Item、Candidate-Evidence和Review Decision闭环；Rule Match只进入Method Trace。
5. FK/Dependency事实、SQL Lineage观察、Structural Relation Candidate及`relation_index` Projection分层。
6. 可执行Gold Set及按任务评测。
7. 样本Object Card深度区、关系页和Unknown清单。

### 5.4 明确不做

- 在全部TRADEFLOW对象上运行深度候选。
- Object Family、Field Concept和Semantic Concept。
- Wiki/LLM命名解释。
- 因样本成功而宣称方法适用于全部TITANS。

### 5.5 Gate B

- 技术PK、业务Identity和Grain可区分，竞争候选可表达。
- 每个发布候选有方法、支持证据、反证或限制。
- 应为Unknown的Gold Set样本不会被强行分类。
- 能力缺失的任务标记Not Evaluable，不计作Unknown。
- Parser和规则没有静默失败。
- 四类Holdout调查任务满足[08评测](08-evaluation.md)定义的正确性、Unsupported Claim和效率门槛。
- 主要错误模式已有明确分类，而不是靠人工改展示掩盖。

Gate B未通过，回到特征、规则、证据或结果契约；不得扩大对象数量。

Gate B 即使通过，也只表示上述工程检查满足，不证明业务认知方法有效，不完成业务全貌验收，也不授权 V1C。

## 6. V1C：TRADEFLOW Deep Scale

### 6.1 启动条件

V1C 当前禁止启动。未来必须同时满足：

- 已存在面向读者的业务全貌交付。
- 用户已对该交付完成业务验收。
- 用户对明确的扩展对象、证据源、成本和失败边界作出独立规模化授权。
- 新 OpenSpec Change 已接受；Gate B 通过只能作为其中一项工程输入。

### 6.2 递进顺序

1. 将已验证核心候选扩展到TRADEFLOW全量，保留Unknown。
2. 增加Object Family和成员级解释。
3. 增加Field Concept及同名异义/同义异名冲突。
4. 条件增加SQLGlot View Lineage。
5. 用户提供Wiki目录后，只把相关片段作为辅助证据。
6. 数据外发获批后，才通过基础SDK启用LLM命名、消歧和语义候选。
7. 生成TRADEFLOW全量深度地图。

以上步骤仍是逐项启用，不要求一次并行实现。

### 6.3 完成门槛

- 全量运行无静默失败，Unknown和孤立对象显式保留。
- 不因扩大覆盖降低Gold Set质量。
- Family和Field Concept能展示成员级结构原因与冲突。
- LLM禁用时仍可重建全部确定性和结构结果。
- 任一深度候选可回溯到事实、方法和证据。

## 7. V1后：方法泛化

选择第二个Deep Case验证：

- 哪些规则是Oracle/TITANS通用事实处理。
- 哪些方法只对TRADEFLOW命名和结构有效。
- 哪些概念关系经过第二个Schema仍稳定。
- 是否出现PostgreSQL、Embedding、正式本体或Catalog的真实需求。

第二个Deep Case验证前，方法标记为`TRADEFLOW-validated`，不得宣传为全TITANS通用。

## 8. 测试策略

- V1A Unit：ID、类型归一化、复合约束保序、范围过滤、失败状态。
- V1A Reconciliation：对象/字段数量与独立SQL对账。
- V1A End-to-end：小型合成元数据到Panorama地图链接。
- V1B Fixture：技术PK、业务Identity、复合Grain、关系歧义、Unknown。
- V1B Golden：固定输入产生稳定核心候选和Evidence引用。
- V1B Evaluation：Gold Set分任务指标和错误清单。
- V1C按启用能力增加聚类、Parser和LLM Contract测试。

不为尚未启用的V1C模块编写空实现和占位测试。

## 8. 有界表语义地图

当前已授权且实现的范围仅为固定 `TITANS_TRADEFLOW` 运行上的表语义候选 Projection。实施顺序为：冻结 477/233/244 输入边界；建立类型化契约与关系注册表；保留全部物理变体处置；接入名称、注释、字段、固定 Wiki 与旧结构提示；生成 Assertion、关系和协作组；运行五组调查卡 Gate；Gate 通过后才生成审阅页面。

2026-08-12 替代评审将首轮结果处置为 `REWORK`。返工后的 TRS 调查图通过共享 `KEY_OTC_TRADE_ID`、`KEY_LEG_ID` 和当前/历史关系形成证据连通候选组；用户随后授权的一次一行 TEST 聚合证明当前快照中期权事件键非空且全部匹配唯一合约键，结合事件表元数据形成 `EVENT_OF` 候选。工程 Gate 现为 `PASS` 并生成审阅页面，但该聚合不是声明外键、生产规则或业务验收；用户审阅前不得改变推荐项目入口、宣称读者可用或启动其他 Schema 深度表语义扩展。

## 9. 全局停止条件

- 物理范围无法确认。
- 当前权限无法提取关键事实且未显式降级。
- Gate A数量对账失败。
- Identity与Grain在V1B持续混淆。
- 候选没有有效Evidence链。
- 地图无法显著优于原始对象清单。
- LLM数据外发未授权时试图启动外部模型调用。
