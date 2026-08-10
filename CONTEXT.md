# TITANS Cognition

本上下文描述从 TITANS 测试库元数据中逆向发现结构认知和业务语义候选时使用的统一语言。

## 物理事实

**Physical Asset（物理资产）**：
数据库中可被唯一识别的 Schema、表、视图或字段。
_Avoid_: 业务对象、语义概念

**Physical Fact（物理事实）**：
数据库直接声明或可原样读取的对象、字段、约束、索引、注释、定义和依赖。
_Avoid_: 结论、推断、认知

**Boundary Node（边界节点）**：
位于主分析范围之外、但与范围内资产存在直接依赖的物理资产；只保留识别和关系上下文，不进行完整认知分析。
_Avoid_: 范围内资产、完整外部资产

**Panorama Scope（全貌范围）**：
当前明确纳入的 TITANS Schema 集合；要求完整盘点可见物理对象并形成 Schema 级和粗结构视图，但不要求对每个对象执行深度语义推断。
_Avoid_: 全数据库、所有对象已理解

**Deep Case（深度案例）**：
从 Panorama 中选择、执行完整 Identity、Grain、Role、Relation、Family、Field Concept 和语义候选流水线的范围。V1 首个 Deep Case 为 `TITANS_TRADEFLOW`。
_Avoid_: Panorama 的同义词、通用方法已验证

**Stage Gate（阶段门）**：
进入下一阶段前必须满足的结果和质量条件。V1A 建全貌，V1B 在分层样本验证认知闭环，V1C 才将已验证方法扩展到全量并启用增强能力。
_Avoid_: 时间排期、可随意并行的任务列表

## 结构认知

**Derived Observation（派生观察）**：
由确定性程序从物理事实计算出的名称特征、结构指纹、SQL 解析或相似度结果；可失败或存在歧义。
_Avoid_: 数据库声明事实、业务结论

**Identity（身份）**：
用于区分或引用一个记录所代表对象的字段或字段组合，区分技术身份、业务身份和父对象身份。
_Avoid_: 主键、粒度

**Grain（粒度）**：
一行记录所代表的最小业务事实或状态，由身份、序列、时间及其他区分字段共同描述。
_Avoid_: 主键、唯一性

**Object Role（对象角色）**：
物理对象在数据结构中承担的角色，如实体、事件、快照、历史、映射、结果、接口或日志。
_Avoid_: 业务模块、业务概念

**Field Role（字段角色）**：
字段在对象结构中承担的角色，如标识、时间、状态、金额、数量、代码、名称或审计属性。
_Avoid_: 字段概念

**Object Family Candidate（对象族候选）**：
基于名称、结构、身份、粒度和关系形成的一组相似或协同物理对象；其边界和名称尚未被业务确认。
_Avoid_: 业务模块、已确认对象族

**Field Concept Candidate（字段概念候选）**：
可能表达同一业务属性或身份的一组物理字段；允许存在同名异义和同义异名的冲突成员。
_Avoid_: 字段角色、标准字段

**Relation Candidate（关系候选）**：
由外键、依赖、SQL、字段身份或结构邻域支持的对象或字段关系假设。
_Avoid_: 已声明依赖、已确认业务关系

## 业务语义

**Semantic Concept Candidate（业务语义候选）**：
由结构认知、注释、Wiki 和人工知识共同支持的业务概念或概念关系假设，例如合约、交易、事件、持仓或费用。
_Avoid_: 正式本体、已确认业务定义

**Business Module（业务模块）**：
用于组织相关业务概念和资产的语义区域；它不是 Schema 的同义词，也不要求与物理边界一一对应。V1只把它作为地图Projection或人工组织标签，不建立Business Module Candidate实体。
_Avoid_: Schema、对象族、V1机器候选

## 判断与质量

**Cognitive Candidate（认知候选）**：
对 Identity、Grain、Role、Family、Relation 或 Semantic Concept 作出的可反驳判断。
_Avoid_: 事实、策展结论

**Inference Result（推断结果）**：
结构推断方法对一个 Subject 和 Task 的本次处置，结果只能是单一候选、竞争候选或 Unknown，并引用零到多个候选。它不是候选本身；LLM使用独立的LLM Task Result。
_Avoid_: Candidate、Review Decision

**Evidence（证据）**：
支持、反对或限定一个认知候选的可定位事实、派生观察或文档片段。规则命中属于Method Trace，不构成独立证据。
_Avoid_: 人工决定、模型解释

**Evidence Pack（证据包）**：
V1C为单次LLM任务从Canonical Evidence裁剪出的有界输入；保留Evidence ID和反证，但不是新的证据来源，也不属于V1B证据闭环。
_Avoid_: Evidence Item、全部证据库

**Review Decision（评审决定）**：
人工对一个认知候选或推断结果作出的接受、否定、修订或延期处置。
_Avoid_: 证据、事实覆盖

**Unknown（未知）**：
推断任务已经运行，但当前证据不足或冲突而不应形成确定判断的Inference Outcome。
_Avoid_: 失败、遗漏、Not Evaluable、低质量分类

**Not Evaluable（不可评测）**：
运行某项推断所需的字段、约束、SQL或依赖能力缺失，因此该任务没有产生有效Inference Outcome。
_Avoid_: Unknown、错误候选、评测失败

**Abstain（模型弃答）**：
V1C中LLM面对Evidence Pack后选择不提出语义候选的模型动作；它不等于结构推断的Unknown，也不等于人工Deferred。
_Avoid_: Unknown、Deferred、模型失败

**Gold Set（黄金样本集）**：
由人工选择并裁定的代表性正例、反例、歧义和 Unknown 案例，用稳定Source Ref描述期望Inference Outcome、候选值和证据要求，用于分别评测 Identity、Grain、Role、Relation 和证据质量。
_Avoid_: 随机样本、训练集准确率

**Cognition Result Bundle（认知结果包）**：
一次 V1 运行产生的 Panorama 物理事实与粗结构结果，以及一个或多个 Deep Case 的派生观察、认知候选、证据、评测和可浏览地图的完整交付集合。
_Avoid_: Catalog、Edition、正式本体
