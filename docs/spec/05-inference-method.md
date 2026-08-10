# 05 推断方法规范

## 1. 方法目标

从物理事实和派生观察中生成可解释、可反驳的结构认知候选。方法优化目标是提升有效认知和调查价值，不是最大化分类覆盖率。

本规范的深度推断只适用于 Deep Case。V1A 仅计算全貌所需的确定性统计、命名特征和结构轮廓；V1B 在 TRADEFLOW 分层样本实现 Identity、Grain、Field/Object Role 和 Relation；Object Family、Field Concept、Semantic Concept及第二轮反馈推断属于V1C。

## 2. 推断主线

```text
Physical Facts
      ↓
Features / SQL / Similarity
      ├─ Identity / Key
      ├─ Field Role / Field Concept
      └─ Dependency / Lineage
              ↓
            Grain
              ↓
       Object Role / Relation
              ↓
         Object Family
              ↓
     Semantic Concept Candidate
```

该顺序是目标主推理路径，不是 V1B 必须一次实现的完整 DAG。V1B 在 Relation 后停止并评测；V1C 才允许对象族和字段概念反向增强或削弱 Identity、Grain 和 Role。

## 3. 方法注册

每个推断方法必须注册：

- `method_id`：如`rule.identity.declared_key`。
- `method_version`：代码版本或规则内容哈希。
- 输入数据集及Schema版本。
- 输出候选类型。
- 输出Inference Result及其Candidate引用规则。
- 适用范围和排除条件。
- 原始分数语义。
- 已知失败模式。
- 对应测试和Gold Set任务。

复杂逻辑使用Python；YAML只保存词典、正则、角色词根、权重和阈值，不建设通用规则DSL。

## 4. Identity推断

### 4.1 候选来源优先级

1. 数据库声明PK/UK。
2. FK目标与被多对象引用的键。
3. 唯一索引。
4. 名称、注释、数据类型和非空声明。
5. 跨对象重复出现及字段概念族。
6. 对象族中的共同身份结构。

### 4.2 身份分类

- `TECHNICAL`：ID、流水号、序列生成等记录级身份。
- `BUSINESS`：合约号、交易号等领域身份候选。
- `PARENT`：当前记录所属父对象的身份。
- 无法区分或证据冲突时不生成名为UNKNOWN的Identity Candidate，而输出UNKNOWN Inference Result。

同一字段组合允许承担多种Identity角色。例如事件表中的`CONTRACT_ID`既可能是Parent Identity，也是关联键。

### 4.3 必须保留的反证

- PK只有单一技术`ID`，但不包含业务字段。
- 唯一索引服务于技术去重或处理流程。
- 字段名含`ID`但类型、注释或使用方式不一致。
- 字段仅在局部对象中出现，不能支持稳定业务概念。

## 5. Grain推断

### 5.1 候选信号

- PK/UK的字段组合。
- Business/Parent Identity候选。
- 序列、版本、日期、时点、事件类型和状态字段。
- View中的`GROUP BY`、`DISTINCT`、窗口分区和聚合表达式。
- 对象Role和Family结构。

### 5.2 Grain输出

每个候选必须描述：

- 一行可能代表什么。
- 用哪些字段区分。
- 是否只是技术记录唯一性。
- 数据验证状态；V1固定为`NOT_PERFORMED`，不得解释成验证失败或验证通过。
- 竞争候选和无法排除的解释。

### 5.3 禁止推断

- 不因PK存在就直接宣称业务粒度。
- 不因字段名含`DATE`就认定是业务日期。
- 不因组合看似合理就宣称实际唯一。

## 6. Field Role推断

V1基础角色：

```text
IDENTIFIER
PARENT_IDENTIFIER
SEQUENCE
BUSINESS_DATE
EVENT_TIME
EFFECTIVE_DATE
EXPIRY_DATE
STATUS
TYPE_CODE
GENERIC_CODE
NAME
DESCRIPTION
AMOUNT
PRICE
QUANTITY
RATE
CURRENCY
FLAG
TECHNICAL_AUDIT
```

信号包括名称Token、数据类型、注释、键参与、伴随字段、对象Role和SQL使用。允许同字段多Role；无法判断时输出UNKNOWN Inference Result，不生成名为UNKNOWN的Role Candidate。

## 7. Object Role推断

V1结构角色：

```text
ENTITY_MASTER
EVENT_TRANSACTION
STATE_HISTORY
SNAPSHOT
DETAIL
RELATION_MAPPING
REFERENCE_CONFIG
AGGREGATE_RESULT
STAGING_INTERFACE
LOG_AUDIT
```

角色由字段分布、Identity、Grain、键结构、依赖方向、名称/注释和对象族共同决定。Role是结构解释，不自动等同于业务模块；无法判断时输出UNKNOWN Inference Result。

## 8. Relation推断

### 8.1 关系层级

| 来源 | Canonical层级 | 是否进入Relation Candidate |
|---|---|
| 声明FK | Physical Fact | 否 |
| Oracle依赖 | Physical Fact | 否 |
| SQL解析 | Derived Observation | 否 |
| Identity/字段结构匹配 | Structural Candidate | 是 |
| Object Family邻域 | Structural Candidate（V1C） | 是 |
| LLM语义解释 | Semantic Candidate（V1C） | 是 |

地图通过`relation_index` Projection统一浏览这些关系，但不能改变其Canonical层级。

### 8.2 关系候选规则

- 字段同名同类型只能生成弱候选。
- Identity与被引用键一致可增强候选。
- 有方向性证据时才确定方向。
- 关系必须保存来源层级，不能全部显示为“血缘”。
- 循环依赖和自引用必须保留，不视为解析错误。

## 9. Object Family发现

本节属于V1C，V1B只允许生成用于选样和比较的粗结构分组，不得称为Object Family候选。

### 9.1 特征视角

- 名称词根和注释。
- 字段结构和角色分布。
- Identity/Grain模式。
- 约束和索引骨架。
- 依赖邻域。
- SQL Lineage。

### 9.2 聚类约束

- 聚类只产生运行级Candidate Cluster。
- 聚类算法必须输出成员级原因和相似特征分解。
- 仅名称前缀一致不得独立形成高等级对象族。
- 对象可以属于多个候选族，但必须标记主要/辅助成员关系。
- 明显冲突对象必须保留为边缘成员或排除成员，不能为了簇纯度静默删除。

### 9.3 命名

初始算法只生成技术性临时标签。业务名称由Evidence Pack、LLM和人工评审提出，仍是候选。

## 10. Field Concept发现

本节属于V1C。

### 10.1 候选生成

- 名称词根和缩写。
- 类型、长度和精度。
- 键和关系参与。
- 伴随字段及对象Role。
- 注释和SQL表达式。

### 10.2 冲突检查

- 同名字段是否处于不同对象族或粒度。
- 技术ID和业务编号是否被错误合并。
- 日期字段是否代表不同时间语义。
- 状态字段是否属于不同生命周期。
- 金额字段是否缺少币种或计量单位上下文。

输出必须允许`CONFLICT`和`EXCLUDED`成员。

## 11. Semantic Concept候选

本节属于V1C。

Semantic Candidate只能基于已有结构候选和证据产生。最低输入应包含：

- 至少一个Identity或Grain模式。
- 一个或多个Object Family/Field Concept。
- 关系或对象Role线索。
- 注释/Wiki/人工知识中的至少一种语义证据；如没有，必须降低证据等级或Abstain。

合约、交易、事件、持仓、费用等名称不得根据单一表名直接确立。

## 12. 迭代和收敛

V1C建议两轮结构推断：

1. 第一轮：基于事实和局部特征生成初始Identity、Grain、Role和Relation。
2. 第二轮：加入Family、Field Concept和关系邻域后重新评分，保留前后变化原因。

V1不追求无限迭代。第二轮后如仍不稳定，输出竞争候选或Unknown。

## 13. Unknown策略

触发Unknown Inference Result的典型条件：

- 无声明键且结构信号不足。
- 多个候选得分接近且无区分证据。
- SQL部分解析导致来源不确定。
- 名称/注释与结构冲突。
- 语义解释只能依赖通用词汇。

Unknown Inference Result必须说明缺少哪类证据以及下一步可如何验证。运行所需能力缺失时使用`NOT_EVALUABLE`，不能使用Unknown掩盖未运行。

## 14. 分数与证据等级

- 算法可以输出`raw_method_score`用于同一方法内部排序。
- 不同方法的分数不得直接平均，除非定义并测试组合方法。
- 不使用`0.87 confidence`表达未经校准的正确概率。
- 对外主要展示证据等级、支持证据、反证和评审状态。

## 15. 失败保留

- SQL无法解析：保留原文、错误类别和table-level fallback。
- 规则异常：记录方法、对象和错误，不生成半有效候选。
- 聚类孤立点：保留为单例，或输出UNKNOWN Family Inference Result，不强制并簇。
- LLM输出无证据或Schema非法：拒绝进入Candidate，保留运行错误记录；模型主动不回答则记录ABSTAIN，不生成候选。
