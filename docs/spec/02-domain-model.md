# 02 领域模型规范

## 1. 模型目的

领域模型必须回答“什么是事实、什么是程序观察、什么是认知候选、什么是证据、什么是人工决定”，避免元数据、推断和业务语义相互覆盖。

统一术语见项目根目录的 [CONTEXT.md](../../CONTEXT.md)。

## 2. 认知层次

```text
业务语义层
Semantic Concept Candidate / Business Module Projection
                ↑ 映射、证据、反证

结构认知层
Identity / Grain / Field Role / Object Role
Object Family / Field Concept / Relation Candidate
                ↑ 解析、特征、推断

物理资产层
Schema / Table / View / Column
Constraint / Index / Definition / Dependency
```

### 2.1 物理边界不是业务边界

- Schema是物理命名空间，不等于业务模块。
- Panorama Scope 是一组明确纳入的 Schema；Deep Case 是对其中一个受控范围执行更深推断。两者是分析范围，不是新的物理资产类型。
- 同一物理对象可以既属于 Panorama，又属于一个 Deep Case；事实只存一份，深度候选按 `case_id` 隔离。
- 表是物理资产，不等于业务对象。
- 一张表可能承载多个业务概念。
- 一个业务概念可能分布在主表、扩展表、历史表和视图中。
- Object Role是结构标签，可以多选。
- 对象和字段关系构成网络，不能压缩成唯一树结构。

## 3. 核心实体

### 3.1 Physical Asset

稳定识别Schema、对象和字段。V1只有一次主运行，不建设历史Observation实体，但每个Physical Fact必须关联`run_id`和逻辑数据源标识。范围成员关系通过 Panorama/Deep Case 配置和结果字段表达，不复制物理事实。

### 3.2 Physical Fact

包括：

- 对象存在及类型。
- 字段、顺序和数据类型。
- 数据库声明的约束和索引。
- 对象/字段注释。
- 可提取的对象定义。
- Oracle声明的依赖。

物理事实可以缺失或提取失败，但不得被推断值补写。

### 3.3 Derived Observation

由程序计算：

- 名称分词和标准化。
- 字段与对象结构特征。
- 结构相似度。
- SQL AST、引用和Lineage。
- 规则输入、命中条件和失败条件组成的Method Trace。

Derived Observation必须记录产生方法和状态。确定性程序输出不等于数据库事实。

### 3.4 Cognitive Candidate

所有结构认知和语义解释均为候选。一个Subject可以同时拥有多个相互竞争的候选，系统不得通过覆盖保留“唯一最新值”。

### 3.5 Inference Result

Inference Result描述结构方法对某个`subject + task + method`的处置结果：

```text
SINGLE_CANDIDATE
COMPETING
UNKNOWN
```

它通过`candidate_ids`引用零到多个Candidate。Unknown属于Inference Result，不通过伪造一个“Unknown Candidate”表达。LLM使用独立的LLM Task Result表达Respond/Abstain。

### 3.6 Evidence

Evidence连接到候选，并带有立场：支持、反对或仅提供上下文。模型生成解释、算法分数和规则命中本身不是独立证据；它们引用的事实、派生观察和文档才是证据。

### 3.7 Evidence Pack

Evidence Pack仅在V1C为LLM任务生成，是Canonical Evidence的有界Projection。它不修改Evidence、不产生新的证据等级，也不属于V1B证据闭环。

### 3.8 Review Decision

人工决定是对Candidate或Inference Result的处置，不改变原始机器结果。评审可以基于错误或不完整知识，因此必须记录理由和适用范围。

## 4. Identity、Grain、Role、Relation

### 4.1 Identity不是PK同义词

| 类型 | 示例性含义 | 主要证据 |
|---|---|---|
| Technical Identity | 自增ID、内部流水ID | PK、序列命名、单字段唯一约束 |
| Business Identity | 合约号、交易号、事件号 | UK、注释、跨表重复引用、业务字段组合 |
| Parent Identity | 事件表中的合约ID | FK、依赖、对象族结构、字段概念 |
| Identity Inference Result = UNKNOWN | 无法判断身份语义，不生成Identity Candidate | 证据缺失或冲突 |

### 4.2 Grain不是唯一性同义词

Grain描述一行代表什么。技术PK可能只保证记录唯一，不能自动解释业务粒度。一个对象允许多个候选Grain，并分别声明：

- 组成字段。
- 粒度文字解释。
- 依据是声明、结构、SQL还是语义。
- 是否缺少数据级唯一性验证。

### 4.3 Role支持多标签

对象可能同时是事件记录和状态历史；字段可能同时是父对象标识和关联键。Role不得设计成单值枚举覆盖。

### 4.4 Relation有不同认识论等级

```text
Declared FK
Oracle Dependency
Parsed SQL Lineage
Structural Relation Candidate
Semantic Relation Candidate
```

它们不能使用同一个“已关联”标签掩盖来源差异。

## 5. 对象族与业务模块

### 5.1 Candidate Cluster

算法运行产生、仅在当前运行内稳定的聚类。它可以在重新运行后拆分、合并或消失。

### 5.2 Reviewed Object Family

V1允许评审者为高价值候选族赋予人工名称或修订成员，但不建设跨版本的稳定实体注册表。若未来持续维护，再引入Curated Entity生命周期。

### 5.3 Business Module

业务模块是对多个对象族和语义候选的组织方式，不从Schema名称直接继承。V1不建立`Business Module Candidate`实体；V1C地图可以用人工维护或Reviewed结果生成`Business Module Projection`，但该Projection不是Canonical事实或机器候选。

## 6. 状态维度必须分开

```text
Inference Outcome: SINGLE_CANDIDATE / COMPETING / UNKNOWN
LLM Action:       RESPOND / ABSTAIN
Review Decision:  ACCEPTED / REJECTED / REFINED / DEFERRED
Evaluation:       EVALUABLE / NOT_EVALUABLE
```

- Candidate只保存机器或LLM实际提出的候选值，不承担Unknown或人工状态。
- `UNKNOWN`是结构推断结果；`ABSTAIN`是LLM动作；`DEFERRED`是人工决定，三者不得互换。
- 数据缺失导致任务无法运行时使用`NOT_EVALUABLE`，不能伪装成Unknown。

## 7. 关键场景约束

### 场景A：技术PK不等于业务粒度

```text
PK = ID
字段 = CONTRACT_ID + EVENT_SEQ + EVENT_DATE
```

允许产生：

- Technical Identity候选：`ID`。
- Business/Parent Identity候选：`CONTRACT_ID`。
- Grain候选：`CONTRACT_ID + EVENT_SEQ`。

不得因存在`ID`而停止后续推断。

### 场景B：没有PK

没有PK不等于没有Identity。系统可以根据UK、索引、字段结构和关系提出候选，但必须明确缺少数据库声明键和数据唯一性验证。

### 场景C：同名字段语义不同

两个表都有`STATUS`，不能直接归为同一Field Concept。必须结合对象族、注释、伴随字段和关系，并允许保留冲突。

### 场景D：外部依赖

Deep Case 对象引用 Panorama 外对象时，外部对象作为 Boundary Node 出现。不得为了补全关系自动扩大 Panorama allowlist，也不得把边界节点自动升级为深度分析对象。

### 场景E：LLM给出合理但无证据的解释

无有效Evidence ID的输出不得进入候选结果；应记为被验证器拒绝的LLM运行结果。
