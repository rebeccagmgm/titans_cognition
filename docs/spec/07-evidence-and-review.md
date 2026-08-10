# 07 证据与评审规范

## 1. 目的

证据模型确保任何结构认知或业务语义候选都能回答：

1. 判断对象是什么。
2. 使用了哪些事实或派生观察。
3. 哪些证据支持它。
4. 哪些证据反对或限制它。
5. 判断由什么方法产生。
6. 人工如何处置它。

V1B必须实现支撑Identity、Grain、Role和Relation样本候选的最小Evidence与Review闭环。Object Family、Field Concept、Wiki和LLM相关证据在V1C启用；Panorama统计本身属于事实Projection，不需要伪装成候选评审。

## 2. 证据类型

### 2.1 声明证据

- PK、UK、FK、CHECK、NOT NULL声明。
- 索引定义。
- Oracle对象依赖。
- 对象和字段注释。
- View SQL和DDL原文。

### 2.2 派生证据

- SQL解析及解析状态。
- 名称和字段特征。
- 结构指纹和相似度分解。
- 依赖邻域和引用次数。
- SQL/结构分析形成的可定位Derived Observation。

### 2.3 文档证据

- Wiki目录项。
- Wiki正文片段。
- 文件路径、页面ID、更新时间等定位信息。

Wiki只证明文档表达，不自动证明测试库实现与文档完全一致。

### 2.4 上下文信息

能够帮助理解但不能直接支持判断的内容，使用`CONTEXT_ONLY`连接。

## 3. 不属于证据的内容

- LLM生成的解释。
- 人工接受或否定决定。
- 没有来源定位的常识。
- 单纯的算法分数。
- 规则命中或方法执行轨迹；它属于Method Trace。
- 另一个未经证据支持的候选。

候选可以作为推理上下文，但最终证据链必须落回Physical Fact、Derived Observation或可定位文档。

## 4. 证据立场

| Stance | 含义 |
|---|---|
| `SUPPORTS` | 直接或间接增强候选 |
| `CONTRADICTS` | 削弱、冲突或提供反例 |
| `CONTEXT_ONLY` | 提供背景但不足以支持候选 |

同一Evidence可以对不同候选具有不同立场。

## 5. 证据强度

### 5.1 Strong

直接声明或多个相互独立的结构信号指向同一判断，且没有未解释的关键冲突。

### 5.2 Moderate

有多个相关信号，但至少一个关键环节仍是间接推断，或存在范围限制。

### 5.3 Weak

主要依赖名称、单一注释、单一相似度或未验证语义。

强度属于Evidence Link，而不是Evidence Item自身的永久属性。

## 6. 候选证据等级

候选的`evidence_grade`由方法根据证据组合产生：

- `DECLARED`：候选内容本身就是数据库声明事实的直接结构解释，例如声明PK字段集合；不代表业务语义已确认。
- `STRONG`：多个独立信号支持且关键冲突已解释。
- `MODERATE`：合理但仍缺少关键验证。
- `WEAK`：主要是探索线索。
- `CONFLICTING`：存在无法消解的实质反证。
- `INSUFFICIENT`：不足以发布Candidate；结构任务形成UNKNOWN Inference Result，LLM任务形成ABSTAIN动作。

不得通过固定分数区间机械映射等级，除非该映射已在Gold Set上验证。

## 7. Evidence Pack与证据裁剪（仅V1C）

- V1B只建设Evidence Item和Candidate-Evidence Link，不建设Evidence Pack或LLM接口。
- Evidence Pack只裁剪用于单次LLM任务的内容，不改变Canonical Evidence。
- 摘要必须保留原始来源定位和内容哈希。
- 裁剪导致关键上下文缺失时，应降低结果等级或Abstain。
- 不得为了适应模型上下文窗口删除反证而保留支持证据。

## 8. 人工评审

### 8.1 决策

| 决策 | 使用条件 |
|---|---|
| `ACCEPTED` | 当前范围内可采用该候选 |
| `REJECTED` | 候选不成立 |
| `REFINED` | 候选方向有价值但需要明确修订 |
| `DEFERRED` | 需要更多证据或业务确认 |

### 8.2 评审不覆盖机器结果

- 原始Candidate保留。
- `REFINED`必须生成replacement内容并引用原Candidate。
- 评审理由必须说明关键证据或缺口。
- 评审者使用非敏感Label，不在公开结果中暴露无关个人信息。

## 9. 反证优先

每个高价值候选在进入地图显著位置前，应至少执行一次反证检查：

- 是否存在不符合该Grain的字段模式。
- 对象族内是否有明显异构成员。
- 同名字段是否在不同生命周期中使用。
- SQL关系是否因别名、Synonym或缺失Schema而歧义。
- Wiki是否只描述流程而非当前表实现。

无法解释的关键反证应将等级降为`CONFLICTING`或输出竞争候选。

## 10. Unknown是一等Inference Result

Unknown至少包括：

- `reason_code`：NO_KEY_SIGNAL/AMBIGUOUS_GRAIN/CONFLICTING_ROLE/MISSING_SQL等。
- `missing_evidence_types`。
- `next_verification`：需要Wiki、人工知识、数据剖析还是更完整SQL。
- 已尝试的方法。

Unknown不计为实现失败，但如果没有记录原因，则属于结果质量缺陷。缺少运行能力时应记录`NOT_EVALUABLE`，不能计作Unknown；LLM弃答应记录`ABSTAIN`，不能计作Unknown。

## 11. 审计检查

结果包必须能回答：

- 哪些Inference Result为Unknown，哪些任务因能力缺失Not Evaluable。
- 哪些Candidate没有支持证据。
- 哪些Candidate有未处理反证。
- 哪些LLM输出引用了无效Evidence ID。
- 哪些评审没有理由。
- 哪些高等级候选仅依赖名称或单一Wiki片段。
- 哪些地图摘要与Canonical Inference Result、Candidate或Review Decision不一致。
