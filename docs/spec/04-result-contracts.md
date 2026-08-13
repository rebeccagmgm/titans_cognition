# 04 结果数据契约

## 字段语义索引 V2（TRADEFLOW 有界重构）

V2 使用独立目录 `field-semantic-index-v2/`，Canonical 文件为：

- `base_concepts.jsonl`：运行级基础概念、确定性 `canonical_key`、`SUPPORTED/PROVISIONAL`、`DOMAIN/TECHNICAL/UNRESOLVED` 和独立支持计数。
- `concept_expressions.jsonl`：`SOURCE_EXPRESSION/ALIAS/VARIANT` 候选及原文、规范文本、来源和装饰摘要。
- `field_semantic_results.jsonl`：每个 `column_id` 一条 `SINGLE_CANDIDATE/COMPETING/UNKNOWN` 结果；可选 `field_family` 只表示日期/金额/代码/名称等宽发现入口，绑定必须区分 `relation_kind=EXPRESSES/RELATED_TO`。
- `field_facets.jsonl`：以 `binding_id` 关联的正交 Facet，不生成限定词笛卡尔层级。
- `manifest.json`：固定输入及哈希、配置/方法版本、结果计数、质量 Gate、无业务数据行/无表级分类/LLM disabled 边界。

`field_family`、稳定复合概念和 Facet 是三层不同语义：支付日期/终止日期/交易日期可以同属日期类，但不得因此互认 Alias/Variant；实际/预计/初始等只有在移除后不改变复合概念身份时才作为 Facet。`RELATED_TO` 只支持相关导航，不计入直接成员、支持强度或推断候选数。Unknown 由空的直接候选集合表达，不创建 Unknown 概念。机器可读契约的 JSON Schema 位于 `schemas/field-semantic-index-v2.schema.json`；Physical Facts、字段概念 V1、全树体检和 LLM Review 不得由 V2 改写。

## 1. 契约目标

结果契约定义V1各阶段可交换、可检查和可评测的数据。它优先服务真实分析任务，不为未来数据库或知识图谱提前扭曲模型。

## 2. Canonical与Projection

### 2.1 Canonical结果

- `panorama/facts/*`：全貌范围共享的数据库物理事实。
- `panorama/derived/*`：Schema统计、命名簇、结构轮廓和依赖概况。
- `deep-cases/<case_id>/derived/*`：Deep Case程序派生观察。
- `deep-cases/<case_id>/candidates/*`：类型化认知候选。
- `deep-cases/<case_id>/evidence/*`：证据实体和候选-证据关系。
- `deep-cases/<case_id>/evaluation/review_decisions.yaml`：本次结果包使用的人工决定副本；维护源位于对应`cases/<case_id>/review_decisions.yaml`。

### 2.2 Projection结果

- Object Card。
- 统一`candidate_index`或`claims_view`。
- 地图页面和汇总表。
- Excel/CSV导出。

Projection必须能够从Canonical结果重建，不得作为独立事实来源。

## 3. 文件布局

```text
output/<run_id>/
├─ manifest.json
├─ panorama/
│  ├─ facts/
│  ├─ derived/
│  └─ map/
├─ deep-cases/
│  └─ tradeflow/
│     ├─ derived/
│     ├─ candidates/
│     ├─ evidence/
│     ├─ evaluation/
│     ├─ llm/
│     └─ map/
└─ evaluation/
```

表格数据优先使用Parquet；原始大段文本可存在Parquet字符串列或带内容哈希的独立UTF-8文件。人工维护内容使用YAML。所有文本使用UTF-8。

### 3.1 契约启用阶段

| 阶段 | 必须实现的Canonical结果 |
|---|---|
| V1A | `panorama/facts/*`、必要的 `panorama/derived/*`、提取失败清单和Panorama地图 |
| V1B | 在V1A之上增加样本范围的Identity、Grain、Field/Object Role、Relation、Evidence、Review和Evaluation |
| V1C | 扩展到TRADEFLOW全量，并增加Object Family、Field Concept、Semantic、LLM和完整深度地图 |

后续章节定义的是目标契约全集。实现代码不得在对应阶段门开启前创建空表、空服务或通用抽象来“占位”。

## 4. 类型与标识约定

| 类型 | 表示 |
|---|---|
| 字符串 | `string` |
| 布尔 | `bool` |
| 整数 | `int32`或`int64` |
| 方法原始分数 | `float64`，允许空 |
| 时间 | 带时区ISO-8601或Arrow timestamp |
| 字符串集合 | `list<string>`，顺序有语义时必须保序 |

### 4.1 稳定物理ID

```text
asset_id  = <source_label>:<schema>:<object_type>:<object_name>
column_id = <asset_id>:COLUMN:<column_name>
```

- Oracle未加引号标识符按数据库解析规则标准化，原始名称另存。
- ID中不包含账号、主机、端口或JDBC连接串。
- Boundary Node、Panorama对象与Deep Case对象使用同一ID规则。

### 4.2 运行级候选ID

候选ID在一次`run_id`内唯一，不承诺跨运行稳定：

```text
<run_id>:<candidate_type>:<generated-id>
```

算法聚类ID不得直接成为长期业务对象族ID。

## 5. 通用状态枚举

### 5.1 提取/解析状态

```text
SUCCESS
PARTIAL
MISSING
NO_PERMISSION
AMBIGUOUS
FAILED
NOT_APPLICABLE
```

### 5.2 证据等级

```text
DECLARED
STRONG
MODERATE
WEAK
CONFLICTING
INSUFFICIENT
```

证据等级是序数分类，不是概率。

### 5.3 Inference Outcome

```text
SINGLE_CANDIDATE
COMPETING
UNKNOWN
```

### 5.4 LLM Action

```text
RESPOND
ABSTAIN
```

仅V1C使用。Abstain不生成Semantic Candidate。

### 5.5 评审决定

```text
ACCEPTED
REJECTED
REFINED
DEFERRED
```

### 5.6 评测资格

```text
EVALUABLE
NOT_EVALUABLE
```

`NOT_EVALUABLE`表示运行该任务所需能力缺失；它不是Unknown。

### 5.7 数据验证状态

```text
NOT_PERFORMED
PASSED
FAILED
NOT_APPLICABLE
```

## 6. Physical Fact数据集

除另有说明，本节`facts/*`均位于`panorama/facts/*`，并由所有Deep Case按ID引用。

### 6.1 `panorama/facts/objects.parquet`

| 字段 | 类型 | 必填 | 含义 |
|---|---|---:|---|
| `run_id` | string | 是 | 本次运行 |
| `asset_id` | string | 是 | 物理对象ID |
| `source_label` | string | 是 | 逻辑数据源标签，不含连接细节 |
| `schema_name` | string | 是 | 原始Schema名 |
| `object_name` | string | 是 | 原始对象名 |
| `object_type` | string | 是 | TABLE/VIEW/MATERIALIZED_VIEW等 |
| `in_panorama_scope` | bool | 是 | 是否属于Panorama allowlist |
| `deep_case_ids` | list<string> | 是 | 所属Deep Case；不属于时为空列表 |
| `is_boundary` | bool | 是 | 是否为一跳边界节点 |
| `boundary_for_case_ids` | list<string> | 是 | 为哪些Deep Case提供边界上下文 |
| `object_comment` | string | 否 | 数据库对象注释 |
| `extraction_status` | string | 是 | 提取状态 |
| `last_ddl_time` | timestamp | 否 | 若权限可见，仅作为物理元数据 |
| `source_record_hash` | string | 否 | 仅在需要记录级Diff/缓存时生成的规范化内容哈希 |

不变量：`asset_id`唯一；`deep_case_ids`非空的主分析对象必须`in_panorama_scope=true`且`is_boundary=false`；Boundary Node必须有`boundary_for_case_ids`。

### 6.2 `facts/columns.parquet`

| 字段 | 类型 | 必填 | 含义 |
|---|---|---:|---|
| `column_id` | string | 是 | 字段ID |
| `asset_id` | string | 是 | 所属对象 |
| `column_name` | string | 是 | 原始字段名 |
| `ordinal_position` | int32 | 是 | 字段顺序 |
| `data_type` | string | 是 | Oracle类型 |
| `data_length` | int64 | 否 | 长度 |
| `data_precision` | int32 | 否 | 精度 |
| `data_scale` | int32 | 否 | 小数位 |
| `nullable_declared` | bool | 否 | 数据库声明是否可空 |
| `default_expression` | string | 否 | 默认表达式 |
| `column_comment` | string | 否 | 字段注释 |
| `source_record_hash` | string | 否 | 仅在需要记录级Diff/缓存时生成的内容哈希 |

不变量：`column_id`唯一；Panorama范围对象的字段提取失败必须在失败清单中显式出现。

### 6.3 `facts/constraints.parquet`

| 字段 | 类型 | 必填 | 含义 |
|---|---|---:|---|
| `constraint_id` | string | 是 | 约束ID |
| `asset_id` | string | 是 | 所属对象 |
| `constraint_name` | string | 是 | 数据库名称 |
| `constraint_type` | string | 是 | PRIMARY_KEY/UNIQUE_KEY/FOREIGN_KEY/CHECK |
| `column_ids` | list<string> | 否 | 保序字段集合 |
| `referenced_asset_id` | string | 否 | FK目标对象 |
| `referenced_column_ids` | list<string> | 否 | FK目标字段 |
| `declared_status` | string | 否 | ENABLED/DISABLED等原始状态 |
| `search_condition` | string | 否 | CHECK表达式 |
| `extraction_status` | string | 是 | 提取状态 |

NOT NULL以`columns.nullable_declared`为主，不重复伪造成独立业务约束。

### 6.4 `facts/indexes.parquet`

| 字段 | 类型 | 必填 | 含义 |
|---|---|---:|---|
| `index_id` | string | 是 | 索引ID |
| `asset_id` | string | 是 | 所属对象 |
| `index_name` | string | 是 | 原始名称 |
| `is_unique` | bool | 是 | 是否唯一索引 |
| `index_type` | string | 否 | Oracle索引类型 |
| `column_ids` | list<string> | 否 | 保序字段集合 |
| `expressions` | list<string> | 否 | 函数索引表达式 |
| `declared_status` | string | 否 | 原始状态 |

普通索引只能作为访问和候选关系线索，不能自动升级为业务键。

### 6.5 `facts/object_definitions.parquet`

| 字段 | 类型 | 必填 | 含义 |
|---|---|---:|---|
| `definition_id` | string | 是 | 定义ID |
| `asset_id` | string | 是 | 所属对象 |
| `definition_type` | string | 是 | VIEW_SQL/DDL/SOURCE等 |
| `definition_text` | string | 否 | 原始提取文本 |
| `extraction_status` | string | 是 | 状态 |
| `error_category` | string | 否 | 失败分类 |
| `content_hash` | string | 否 | 文本哈希 |

### 6.6 `facts/dependencies.parquet`

| 字段 | 类型 | 必填 | 含义 |
|---|---|---:|---|
| `dependency_id` | string | 是 | 依赖ID |
| `source_asset_id` | string | 是 | 依赖方 |
| `target_asset_id` | string | 是 | 被依赖方 |
| `dependency_type` | string | 是 | Oracle声明类型 |
| `source_kind` | string | 是 | `ORACLE_DICTIONARY` |
| `target_is_boundary` | bool | 是 | 目标是否边界节点 |

## 7. Derived Observation数据集

### 7.0 Panorama派生结果（V1A）

- `panorama/derived/schema_summary.parquet`：每个Schema的对象类型、字段、注释、约束、索引、定义、依赖和失败数量。
- `panorama/derived/object_inventory_profiles.parquet`：对象级名称Token、字段数、注释状态、约束/依赖摘要和粗结构指纹；不包含业务Identity、Grain或Object Family结论。
- `panorama/derived/dependency_summary.parquet`：Schema内/跨Schema依赖数量及枢纽对象摘要。
- `panorama/derived/extraction_failures.parquet`：阶段、目标、失败类别、降级结果和非敏感错误摘要。

以下7.1至7.4属于Deep Case目录；V1B按样本生成，V1C按启用能力扩展。Panorama若复用其中确定性字段，只能作为粗结构特征，不能生成深度候选。

### 7.1 `derived/column_features.parquet`

包括：`column_id`、标准化Token、名称模式、类型族、是否参与PK/UK/FK/索引、Field Role基础信号、注释Token、伴随字段摘要、方法版本和状态。

### 7.2 `derived/object_features.parquet`

包括：`asset_id`、字段数、约束数、名称Token、字段角色分布、Identity基础信号、日期/状态/金额/审计字段数量、依赖入度/出度、结构指纹、注释覆盖和方法版本。

### 7.3 `derived/structure_similarity.parquet`

| 字段 | 含义 |
|---|---|
| `left_asset_id` / `right_asset_id` | 对象对 |
| `method_id` / `method_version` | 相似度方法 |
| `name_score` | 名称相似原始分数 |
| `column_score` | 字段结构相似原始分数 |
| `key_score` | 键结构相似原始分数 |
| `relation_neighborhood_score` | 关系邻域相似分数 |
| `combined_score` | 方法内部排序分数 |
| `feature_breakdown` | JSON字符串，固定Schema |

任何分数都不是业务相似概率。

### 7.4 `derived/view_lineage.parquet`

仅在View SQL可见且对应Parser能力启用时生成；缺失时相关任务标记`NOT_EVALUABLE`，不得创建猜测Lineage。

| 字段 | 含义 |
|---|---|
| `lineage_id` | 派生关系ID |
| `view_asset_id` | View对象 |
| `target_column_id` | 目标字段，表级时为空 |
| `source_asset_id` | 来源对象 |
| `source_column_id` | 来源字段，未知时为空 |
| `expression_summary` | 表达式摘要 |
| `parse_status` | SUCCESS/PARTIAL/AMBIGUOUS/FAILED |
| `resolution_status` | RESOLVED/MISSING_SCHEMA/AMBIGUOUS |
| `method_id` | 解析方法和版本 |

## 8. Candidate通用推断信封

### 8.1 `candidates/inference_results.parquet`

Inference Result是任务级结果，不是Candidate：

| 字段 | 含义 |
|---|---|
| `inference_result_id` | 运行级唯一ID |
| `run_id` / `case_id` | 运行和Deep Case |
| `task_type` | IDENTITY/GRAIN/FIELD_ROLE/OBJECT_ROLE/RELATION等 |
| `subject_id` | 被分析对象或字段 |
| `method_id` / `method_version` | 产生方法 |
| `evaluation_eligibility` | EVALUABLE/NOT_EVALUABLE |
| `not_evaluable_reason` | 缺失能力；可评测时为空 |
| `outcome` | SINGLE_CANDIDATE/COMPETING/UNKNOWN；不可评测时为空 |
| `candidate_ids` | 零到多个候选ID |
| `evidence_grade` | Unknown通常为INSUFFICIENT或CONFLICTING |
| `reason` | 结果解释或Unknown原因 |
| `missing_evidence_types` | Unknown时缺少的证据类型 |
| `next_verification` | 下一步验证方式 |

不变量：

- `SINGLE_CANDIDATE`必须引用一个Candidate。
- `COMPETING`必须引用至少两个Candidate。
- `UNKNOWN`不得引用伪造的Unknown Candidate。
- `NOT_EVALUABLE`时`outcome`和`candidate_ids`均为空，并记录能力缺口。

### 8.2 Candidate通用信封

每个类型化候选表至少包含：

| 字段 | 含义 |
|---|---|
| `candidate_id` | 运行级唯一ID |
| `run_id` | 本次运行 |
| `case_id` | Deep Case标识；V1为`tradeflow` |
| `subject_id` | 被判断对象/字段/候选实体 |
| `method_id` | 规则、统计、聚类或LLM方法 |
| `method_version` | 方法版本/内容哈希 |
| `evidence_grade` | 序数证据等级 |
| `raw_method_score` | 方法内部原始分数，可空 |
| `explanation` | 简洁可检查解释 |
| `limitations` | `list<string>` |

规则：

- `raw_method_score`不得展示为“置信概率”。
- Candidate至少关联一个支持证据；规则命中自身不能作为唯一证据。
- `evidence_grade=INSUFFICIENT`不得作为Candidate发布，应形成UNKNOWN Inference Result。
- Unknown由Inference Result表达，不写入类型化Candidate表。

## 9. Structural Candidate数据集

V1B只启用9.1至9.4及9.7，用于分层样本的核心认知闭环。9.5和9.6属于V1C。

### 9.1 `candidates/identity_candidates.parquet`

附加字段：

- `asset_id`
- `column_ids`：保序字段集合。
- `identity_kind`：TECHNICAL/BUSINESS/PARENT。
- `declared_key_kind`：PK/UK/NONE。
- `identity_description`
- `data_validation_status`：V1恒为`NOT_PERFORMED`。

### 9.2 `candidates/grain_candidates.parquet`

附加字段：

- `asset_id`
- `grain_column_ids`
- `grain_kind`：DECLARED_KEY/STRUCTURAL/VIEW_OUTPUT。
- `grain_description`：一行可能代表什么。
- `data_validation_status`：V1恒为`NOT_PERFORMED`；不使用`false`混淆“未执行”和“验证失败”。
- `competing_candidate_ids`

### 9.3 `candidates/field_role_candidates.parquet`

附加字段：`column_id`、`field_role`、`role_qualifier`。同一字段允许多行多角色。

### 9.4 `candidates/object_role_candidates.parquet`

附加字段：`asset_id`、`object_role`、`role_qualifier`。同一对象允许多行多角色。

### 9.5 Object Family

`object_family_candidates.parquet`：

- `family_candidate_id`
- `provisional_name`
- `family_summary`
- `clustering_method`
- `coherence_score`
- 通用推断信封

`object_family_memberships.parquet`：

- `family_candidate_id`
- `asset_id`
- `membership_role`
- `membership_score`
- `membership_explanation`
- `evidence_grade`

### 9.6 Field Concept

`field_concept_candidates.parquet`：

- `field_concept_candidate_id`
- `provisional_name`
- `concept_kind`：IDENTIFIER/TIME/STATUS/AMOUNT/CODE/ATTRIBUTE/UNSPECIFIED；`UNSPECIFIED`只表示候选概念类型尚未命名，不等于Inference Outcome的UNKNOWN。
- `concept_summary`
- 通用推断信封

`field_concept_memberships.parquet`：

- `field_concept_candidate_id`
- `column_id`
- `membership_status`：MEMBER/CONFLICT/EXCLUDED。
- `semantic_qualifier`
- `membership_explanation`
- `evidence_grade`

### 9.7 `candidates/relation_candidates.parquet`

附加字段：

- `source_id`
- `predicate`
- `target_id`
- `relation_level`：OBJECT/FIELD/SEMANTIC。
- `epistemic_kind`：STRUCTURAL/SEMANTIC；V1B只允许STRUCTURAL。
- `generation_origin`：RULE/STATISTICAL/LLM/HUMAN_PROPOSAL；V1B不允许LLM。
- `direction_is_resolved`
- `relation_qualifiers`：固定Schema JSON字符串。

FK和Oracle Dependency只存在于Physical Fact数据集；SQL Lineage只存在于Derived Observation。三者不得复制进`relation_candidates`。

## 10. Semantic Candidate数据集

本节全部属于V1C；V1A/V1B不得以空数据集或占位实现作为完成条件。

### 10.1 `semantic_concept_candidates.parquet`

- `semantic_candidate_id`
- `provisional_name`
- `concept_definition`
- `identity_pattern_ids`
- `grain_pattern_ids`
- `attribute_concept_ids`
- 通用推断信封

LLM选择Abstain时只产生`llm_run`及`llm_task_result`，不生成Semantic Candidate，也不改写为结构UNKNOWN Inference Result。

### 10.2 `semantic_concept_mappings.parquet`

- `semantic_candidate_id`
- `mapped_id`：对象族、对象、字段概念或关系候选。
- `mapping_predicate`：IMPLEMENTS/EXPRESSES/SUPPORTS/RELATED_TO。
- `mapping_explanation`
- `evidence_grade`

### 10.3 `llm/llm_task_results.parquet`

- `llm_task_result_id`
- `llm_run_id`
- `subject_id`
- `task_type`
- `model_action`：RESPOND/ABSTAIN。
- `candidate_ids`：Respond时引用生成的语义候选；Abstain时为空。
- `abstain_reason`：Abstain时必填。
- `supported_evidence_ids` / `contradicted_evidence_ids`

LLM Task Result与结构Inference Result分开评测。

## 11. Evidence数据集

### 11.1 `evidence/evidence_items.parquet`

| 字段 | 含义 |
|---|---|
| `evidence_id` | 唯一ID |
| `evidence_type` | OBJECT/COLUMN/CONSTRAINT/INDEX/COMMENT/DEFINITION/ORACLE_DEPENDENCY/SQL_LINEAGE/FEATURE/WIKI；不得使用RULE_MATCH |
| `source_id` | 对象、字段、定义、Wiki资源或派生观察ID |
| `locator` | 字段名、SQL位置、Wiki路径/片段位置等 |
| `summary` | 不改变原意的证据摘要 |
| `content_hash` | 原始内容哈希 |
| `source_status` | SUCCESS/PARTIAL等 |

### 11.2 `evidence/candidate_evidence.parquet`

- `candidate_id`
- `evidence_id`
- `stance`：SUPPORTS/CONTRADICTS/CONTEXT_ONLY。
- `strength`：STRONG/MODERATE/WEAK。
- `reason`

## 12. Review与统一Projection

### 12.1 `evaluation/review_decisions.yaml`

每项包含：`review_id`、`target_type`（CANDIDATE/INFERENCE_RESULT/LLM_TASK_RESULT）、`target_id`、`decision`（ACCEPTED/REJECTED/REFINED/DEFERRED）、`reviewer_label`、`reason`、`replacement_value`、`reviewed_at`。

维护源为`cases/tradeflow/review_decisions.yaml`；运行时将本次实际使用的内容复制进对应 Deep Case 结果目录。不得修改或删除原始候选。

### 12.2 `derived/candidate_index.parquet`

可生成统一浏览索引：`candidate_id`、`candidate_type`、`subject_id`、`predicate`、`object_or_value`、关联Inference Outcome、Review Decision和证据摘要。它是Projection，不替代类型化候选表。

### 12.3 `derived/relation_index.parquet`

统一展示不同认识论层级的关系，但不覆盖来源：

| 字段 | 含义 |
|---|---|
| `relation_index_id` | Projection记录ID |
| `source_id` / `target_id` | 关系两端 |
| `epistemic_layer` | PHYSICAL_FACT/DERIVED_OBSERVATION/COGNITIVE_CANDIDATE |
| `origin` | FK/ORACLE_DEPENDENCY/SQL_LINEAGE/STRUCTURAL/SEMANTIC |
| `canonical_ref_id` | 原始Fact、Observation或Candidate ID |
| `direction_is_resolved` | 方向是否已解析 |
| `display_predicate` | 展示用谓词，不改变Canonical来源 |

地图从该Projection统一浏览关系，不能将三层都显示成“候选”或“血缘”。

## 13. 跨数据集不变量

1. 所有引用ID必须能在对应Canonical数据集中解析；Boundary Node也必须存在最小Object记录。
2. Deep Case只引用共享Panorama事实或其显式Boundary Node，不得复制一套独立物理事实。
3. 所有候选必须能定位`method_id`和`method_version`。
4. 所有LLM候选必须关联有效Evidence ID，且输出通过Schema校验。
5. Parser失败、无权限和Unknown不得被过滤出结果包。
6. Object Card和地图不得覆盖Canonical结果中的冲突候选。
7. 任何数值分数不得跨方法直接比较，除非后续建立了明确校准Spec。
8. Unknown、Abstain、Deferred和Not Evaluable必须分别落在Inference Result、LLM Action、Review Decision和Evaluation Eligibility中。
9. Identity和Grain页面必须展示`data_validation_status=NOT_PERFORMED`，不得暗示已验证实际唯一性或业务粒度。

## 14. 表语义候选 Projection

`table-semantic-map/` 是固定 TRADEFLOW 输入之上的独立 Projection，不修改 Physical Facts、旧分类或字段语义结果。核心类型化数据集包括 `table_profiles`、三类开放候选、`table_groups`、`table_group_memberships`、`table_relations`、`assertions`、`evidence_refs`、`review_decisions`、`field_support_summaries` 和 `structural_propagation_hints`，并同时写出 JSONL 与 Parquet。

表是唯一判断主体。字段摘要不得通过数量或多数投票生成表标签；旧分类候选必须标记为 `STRUCTURAL_PROPAGATION_HINT` 且 `recommended_profile_eligible=false`。业务协作组、物理变体组与结构邻域使用不同 `group_kind`，不得自动转换。所有精确关系必须经过版本化 Predicate Registry 校验；证据不足时降级为 `RELATED_TO`/Unknown。Review Decision 只能引用并处置原 Assertion，不得删除或改写机器候选和 Evidence。
