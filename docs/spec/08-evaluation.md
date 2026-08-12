# 08 评测规范

## 1. 评测目标

评测分两种，不得混成一个“V1准确率”：V1A评测Panorama提取覆盖、失败可见性和地图可达性；V1B在TRADEFLOW分层样本评测Identity、Grain、Role、Relation、Evidence和Unknown；Object Family、Field Concept与LLM评测只在V1C启用。

评测要回答的是“方法在哪些结构场景中可靠、在哪些场景中应当Unknown”，而不是制造一个总体准确率证明系统成功。

## 2. Gold Set原则

### 2.1 分层选样

V1B Gold Set不是从当前规划基线477张表简单随机抽样。至少覆盖：

- 声明PK与业务Identity一致。
- 只有技术PK，业务Identity另有字段。
- 无PK但存在UK或强结构键候选。
- 无任何可靠键线索。
- 事件、状态历史、快照、映射、结果、主数据、接口和日志角色。
- 同名字段语义一致和语义冲突。
- 明确FK、只有弱字段匹配、方向歧义和无真实关系。
- 结构相似但业务用途不同。
- 应输出Unknown或竞争候选。
- SQL解析成功、部分成功、歧义和失败。

### 2.2 正例、反例、歧义

每个任务均应同时包含：

- Positive：期望方法识别。
- Negative：名称或结构看似相似但不应识别。
- Ambiguous：允许多个解释。
- Unknown：证据不足时应克制输出。

### 2.3 开发集与保留集

如果样本量允许，Gold Set分为：

- Development：用于调规则、Prompt和阈值。
- Holdout：在方法冻结后评测，不参与调整。

样本过少时可以暂不分割，但必须在报告中明确“仅为开发评测，不能证明泛化”。

## 3. Gold Set格式

`cases/tradeflow/gold-set.yaml`建议结构：

```yaml
version: v2
scope_id: tradeflow-deep-v1
cases:
  - case_id: grain_event_001
    task: GRAIN
    subject_ref: testdb:TITANS_TRADEFLOW:TABLE:T_EVENT
    annotation_status: ADJUDICATED
    expected:
      outcome: SINGLE_CANDIDATE
      accepted_values:
        - - testdb:TITANS_TRADEFLOW:TABLE:T_EVENT:COLUMN:CONTRACT_ID
          - testdb:TITANS_TRADEFLOW:TABLE:T_EVENT:COLUMN:EVENT_SEQ
      unacceptable_values:
        - - testdb:TITANS_TRADEFLOW:TABLE:T_EVENT:COLUMN:ID
      expected_subject_refs:
        - testdb:TITANS_TRADEFLOW:TABLE:T_EVENT:COLUMN:CONTRACT_ID
        - testdb:TITANS_TRADEFLOW:TABLE:T_EVENT:COLUMN:EVENT_SEQ
      required_evidence_types: [CONSTRAINT, FEATURE]
      required_source_refs:
        - testdb:TITANS_TRADEFLOW:TABLE:T_EVENT
    ambiguity: false
    annotation:
      reviewer_label: domain-reviewer
      rationale: "示例，真实标注必须由当前证据确认"
      adjudicated_at: "<timestamp>"
```

规则：

- `expected.outcome`只允许`SINGLE_CANDIDATE/COMPETING/UNKNOWN`。
- `annotation_status`只允许`DRAFT/ADJUDICATED/DISPUTED`；只有ADJUDICATED案例进入正式Gate指标。
- `accepted_values`使用任务专属Schema和稳定ID；Identity/Grain是字段Ref集合，Role是标签集合，Relation是端点Ref与谓词。
- Gold Set引用稳定的Physical/Derived Source Ref和Evidence Type，不直接绑定运行期`evidence_id`。
- LLM任务另用`expected_model_action: RESPOND/ABSTAIN`，不把Abstain写进结构Inference Outcome。
- Gold Set的人工标注不是运行期Review Decision；Review Decision按`candidate_id`或`inference_result_id`另行保存。
- Gold Set不得将未核实的示例表名或业务解释作为正式标注。

## 4. 分任务评测

### 4.1 Physical Extraction

- Panorama allowlist对象覆盖率。
- 字段、约束、索引、定义和依赖提取状态分布。
- 无权限、缺失和失败是否显式记录。
- 对象数量与独立盘点SQL是否一致。

物理范围覆盖要求为100%的“可见对象被记录”，不要求所有对象定义都成功提取。

### 4.2 Identity

- 先检查Inference Result是Single、Competing还是Unknown。
- 关键Identity是否被召回。
- 第一候选是否可接受。
- 技术Identity是否被错误当成业务Identity。
- Parent Identity是否遗漏。
- Unknown是否合理。

### 4.3 Grain

每个案例分为：

- Exact：字段集合和解释均可接受。
- Acceptable Alternative：不同字段表达但业务粒度等价。
- Partial：识别部分区分字段或解释不完整。
- Incorrect：形成错误粒度。
- Unknown Correct：证据不足时正确Unknown。
- Overconfident：证据不足却给出强候选。

### 4.4 Field/Object Role

Role为多标签任务，检查：

- 必要角色召回。
- 无关角色数量。
- 多角色是否被保留。
- Inference Outcome应为UNKNOWN的对象是否被强行生成Role Candidate。

### 4.5 Relation

- 分认识论层统计，不把FK、Oracle Dependency和SQL Lineage计作算法候选。
- Physical Fact关系检查提取完整性；Derived SQL Lineage检查解析正确性；Structural/LLM候选使用Precision@K或人工Top-K有效率。
- 检查方向是否正确、是否把同名字段误当关系、是否区分依赖与业务关系。
- 明确关系缺失可评估召回；未知关系不假设存在完整真值。

### 4.6 Object Family

仅V1C启用。

- 族内结构是否具有可解释共同点。
- 是否存在明显异构成员。
- 核心成员和边缘成员是否区分。
- 聚类结果是否只依赖名称。
- 人工能否理解成员被放在一起的原因。

不使用单一聚类内部指标替代业务可解释性。

### 4.7 Field Concept

仅V1C启用。

- 同义字段是否被召回。
- 技术ID和业务编号是否错误合并。
- 同名异义是否标为Conflict/Excluded。
- 类型、对象族和生命周期差异是否进入解释。

### 4.8 LLM Semantic Tasks

仅V1C且数据外发获批后启用。

- 是否只引用允许的Evidence ID。
- 是否忠于Evidence Pack。
- 是否发现关键反证。
- 是否在证据不足时Abstain。
- 命名是否帮助理解且没有制造正式业务定义。
- 不同Prompt/模型的结果差异。

## 5. Evidence质量评测

每个候选检查：

- Candidate至少有一个可定位支持证据；证据不足时应形成INSUFFICIENT的UNKNOWN Inference Result，而不是发布Candidate。
- 高等级候选是否有多个独立信号。
- 反证是否被隐藏。
- Evidence摘要是否与原文一致。
- LLM解释是否错误地被当成Evidence。
- Rule Match是否被错误地当成独立Evidence形成循环论证。

## 6. 错误分类

`evaluation/error_cases.md`至少按以下类别归档：

```text
EXTRACTION_GAP
CAPABILITY_NOT_EVALUABLE
PARSER_DIALECT_FAILURE
MISSING_SCHEMA_CONTEXT
TECHNICAL_KEY_CONFUSION
GRAIN_OVERREACH
ROLE_OVERCLASSIFICATION
FALSE_FIELD_SYNONYM
FALSE_RELATION
CLUSTER_BY_NAME_ONLY
LLM_UNSUPPORTED_CLAIM
MISSED_COUNTEREVIDENCE
SHOULD_ABSTAIN
REVIEW_DISAGREEMENT
```

错误案例必须进入后续规则测试或Gold Set候选，不得只修当前输出。

## 7. 质量门槛

V1不预设虚假的90%目标，但设定硬门槛：

1. Panorama allowlist内所有可见对象都有成功记录或失败记录。
2. Parser无静默失败。
3. 候选无方法ID或无证据链时不得发布。
4. LLM输出Schema或证据引用非法时不得进入候选。
5. Gold Set中应为Unknown的案例，不得全部被强行分类。
6. 评测报告必须按任务和证据等级分解，不能只显示汇总数字。
7. 全量运行前，纵向样本必须通过上述完整性门槛。
8. V1A未通过物理覆盖与地图可达性验收时，不得进入V1B。
9. V1B核心任务、Unknown和用户效用未通过时，Gate B不得通过；即使 Gate B 通过，也不自动产生 V1C 全量扩展授权。
10. 因能力缺失而`NOT_EVALUABLE`的任务不得计入正确Unknown或分母；报告必须单列。

## 8. 用户效用验收

### 8.1 Gate A任务

至少固定两个任务：定位指定Schema的对象类型/注释覆盖，以及从Schema下钻到指定物理对象与约束。检查完成正确性、导航步数和缺口可见性。

### 8.2 Gate B任务

Gold Set冻结后，另选至少四个Holdout调查任务：

1. 区分一张表的技术PK、候选业务Identity和可能Grain。
2. 判断一个对象的Field/Object Role并找到关键反证。
3. 查看一条关系属于FK、Dependency、SQL Lineage还是Structural Candidate，并判断方向。
4. 找到一个应为Unknown或Not Evaluable的案例，说明缺少什么证据或能力。

每个任务分别使用基线材料（Oracle元数据/DDL清单，不含生成地图）和认知地图完成，记录：完成与否、结论正确性、Unsupported Claim数、耗时、打开对象数、导航路径和主观误导点。单一评审者时使用不同但同难度的Holdout对象降低学习效应；有多名评审者时交换工具顺序。

Gate B最低通过条件（仅用于结构原型工程回归）：

- 四类任务均能完成或正确给出Unknown/Not Evaluable。
- 不产生Unsupported High-Confidence Claim。
- 至少三类任务在不降低正确性的前提下，耗时或打开对象数优于基线。
- 用户确认地图提供了原始元数据清单没有直接提供的结构解释或证据导航价值。

这些任务衡量现有样本地图是否改善结构调查，不等同于业务全貌验收。项目最终价值以业务全貌是否帮助用户理解业务区域、对象、生命周期及其数据承载为准。

## 9. 评测报告

`evaluation/evaluation_report.json`保存机器可读结果；同时生成面向人的Markdown/HTML摘要：

- 输入和Gold Set版本。
- 各任务结果。
- Evidence质量。
- LLM合规性。
- Unknown表现。
- Not Evaluable任务及缺失能力。
- 主要错误模式。
- 不能证明的结论。
- 是否通过Gate A、Gate B；另行报告 reader delivery、business acceptance 和 scale authorization，禁止由 Gate 结果自动计算扩展授权。
