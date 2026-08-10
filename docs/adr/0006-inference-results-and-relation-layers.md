# ADR-0006：推断结果与关系认识论分层

- 状态：Accepted
- 日期：2026-08-10

## 决策

V1将任务级Inference Result、实际Candidate、LLM Action和Human Review Decision分开：

- Inference Result表达`SINGLE_CANDIDATE/COMPETING/UNKNOWN`并引用Candidate。
- Candidate只保存实际提出的认知值，不保存Unknown或人工状态。
- LLM Task Result以`RESPOND/ABSTAIN`表达模型动作，不写入结构Inference Result。
- Review Decision只表达`ACCEPTED/REJECTED/REFINED/DEFERRED`。
- 能力缺失使用`NOT_EVALUABLE`，不伪装成Unknown。

关系同时按认识论来源分层：FK与Oracle Dependency是Physical Fact，SQL Lineage是Derived Observation，Structural/Semantic Relation才是Cognitive Candidate。地图通过可重建的`relation_index` Projection统一浏览。

## 理由

如果Unknown被建成Candidate、Abstain被当成Unknown、人工状态写进机器候选，就无法可靠评测或保留原始判断。如果把数据库声明、SQL解析和算法猜测都写入`relation_candidates`，用户也无法区分“数据库已声明”与“机器推断”。分层增加一个Inference Result和一个Projection，但避免了状态覆盖与认识论混淆。

## 后果

- Gold Set首先评测Inference Result，再匹配具体Candidate和Evidence。
- Review可以指向Candidate或Inference Result，不修改原始记录。
- Abstain不产生Semantic Candidate。
- Relation页面必须显示Canonical层级和来源。
- Rule Match属于Method Trace，不能作为唯一Evidence形成循环论证。
