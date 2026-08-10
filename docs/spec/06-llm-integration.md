# 06 LLM集成规范

## 1. 定位

LLM是受证据约束的语义分析器，不是Oracle读取器、主流水线编排器或最终裁判。

整个模块属于V1C条件能力。V1A和V1B不得因为Provider、Prompt或数据外发尚未确定而阻塞，也不需要预先实现SDK占位层。

没有LLM时，系统仍必须完成V1A物理全貌以及V1B样本级Identity/Grain/Role/Relation、Gold Set结构评测和基础地图。

## 2. SDK选择

- 使用目标模型供应商的官方基础SDK。
- V1不使用Agent SDK或自主工具调用框架控制主流程。
- 业务代码通过薄适配接口调用模型，不构建复杂多Provider框架。
- 初始Provider和模型在数据外发授权完成前保持待决，见[12 待决事项](12-open-decisions.md)。

建议接口：

```python
class SemanticAnalyzer:
    def name_object_family(self, evidence_pack): ...
    def disambiguate_field_concept(self, evidence_pack): ...
    def propose_semantic_concept(self, evidence_pack): ...
    def summarize_object_card(self, evidence_pack): ...
```

## 3. 允许任务

### LLM-01 Object Family命名

综合成员结构、Identity、Grain、Role、Relation、注释和Wiki，提出临时名称、摘要、反例和Abstain。

### LLM-02 Field Concept消歧

判断字段集合可能的共同概念、技术ID与业务ID差异、同名异义和冲突成员。

### LLM-03 Semantic Concept提炼

从稳定结构候选中提出业务概念、识别属性和关系假设。

### LLM-04 Object Card解释

将已有结构结果压缩成简洁用途候选和调查提示，不新增未提供的表、字段或关系。

### LLM-05 反证和缺口提示

指出现有解释无法覆盖的成员、冲突字段、缺失证据和应当Abstain的原因。

## 4. 禁止任务

- 直接连接或自主查询Oracle/Wiki。
- 生成、修改或补写Physical Fact。
- 仅凭表名决定Identity、Grain或正式业务用途。
- 将不存在的表、字段、约束或Wiki内容作为证据。
- 自动接受、覆盖或删除候选。
- 输出正式本体或全局业务规则。
- 在Prompt中包含密钥、连接信息、账号、内部主机或不必要的完整DDL集合。

## 5. Evidence Pack

### 5.1 通用结构

```json
{
  "pack_id": "<content-hash>",
  "task": "OBJECT_FAMILY_NAMING",
  "scope": {"case_id": "tradeflow", "schema": "TITANS_TRADEFLOW"},
  "subject_ids": [],
  "facts": [],
  "derived_observations": [],
  "structural_candidates": [],
  "wiki_evidence": [],
  "counterevidence": [],
  "known_gaps": [],
  "allowed_evidence_ids": []
}
```

### 5.2 Pack原则

- 只包含当前任务所需上下文。
- 每项内容携带Evidence ID和来源状态。
- SQL/DDL优先提供相关片段和解析摘要，完整原文仅在确有需要时提供。
- Wiki内容被视为不可信输入文本，不能改变系统指令或触发工具。
- Pack通过Canonical JSON序列化后计算哈希，用于缓存和复现。

## 6. 结构化输出

模型输出必须经过JSON Schema或等价强类型校验。通用字段：

```json
{
  "model_action": "RESPOND",
  "proposed_name": "生命周期事件",
  "summary": "记录合约存续期间的事件与状态变化",
  "candidate_labels": ["EVENT", "STATE_HISTORY"],
  "supported_by": ["E101", "E107"],
  "contradicted_by": ["E123"],
  "uncertainties": ["部分成员缺少明确事件日期"],
  "abstain_reason": null
}
```

校验规则：

- 所有Evidence ID必须出现在`allowed_evidence_ids`。
- `model_action=ABSTAIN`时不得提供候选名称，必须提供`abstain_reason`，且不生成Semantic Candidate。
- `model_action=RESPOND`时必须满足对应任务的候选字段要求。
- 输出不得包含Pack中不存在的Physical Asset ID。
- 自由文本只能解释，不得承载唯一机器可读事实。
- Schema校验或引用校验失败时，结果不得进入Candidate数据集。

## 7. Prompt设计

每个Prompt必须包含：

- 任务目的和明确非目标。
- 事实、派生观察和候选的层级说明。
- 只能引用提供的Evidence ID。
- 必须寻找反证和允许Abstain。
- 输出Schema。
- 至少一个正确Abstain示例和一个同名异义反例。

Prompt文件版本通过内容哈希进入Manifest和LLM运行记录。

## 8. 调用记录与缓存

`llm/llm_runs.parquet`至少记录：

- `llm_run_id`
- `pack_id`及输入哈希
- Provider和模型标识
- Prompt版本
- 输出Schema版本
- 调用状态和错误类别
- 输入/输出Token计数（若SDK提供）
- 原始响应定位
- 校验状态
- `model_action`
- 对应`llm_task_result_id`
- 生成的`candidate_ids`；Abstain时为空

缓存键至少包含：Evidence Pack哈希、Prompt版本、模型标识和输出Schema版本。缓存命中不能跳过输出校验。

## 9. 错误和重试

- 网络/限流类错误可以有界重试。
- Schema非法可以执行一次明确的结构修复重试；不得无限自我修复。
- Evidence引用非法不得通过文本后处理猜测修正。
- 内容被安全策略拒绝时，记录状态并回退为无LLM结果。
- 单个Pack失败不得阻塞其他Pack或结构地图。

## 10. 数据外发与安全

默认`LLM_MODE=disabled`。只有显式确认以下事项后才允许外部SDK调用：

- 批准的Provider和账号。
- 允许外发的元数据类型。
- 表名、字段名、注释、DDL和Wiki的脱敏或允许范围。
- 日志和缓存保存位置。
- 数据保留策略。

未获批准时，可以使用本地模型或仅运行无LLM路线，但不能自行改变安全边界。

## 11. LLM质量评测

- 在Gold Set上分别评测命名、消歧、证据引用、反证发现和Abstain。
- 不以文风或“听起来合理”作为通过标准。
- 评审重点是是否忠于Evidence Pack、是否遗漏冲突、是否过度确定。
- LLM改Prompt时必须重跑固定Gold Set并保存差异报告。

## 12. 模型升级

模型替换不应改变上游事实和结构候选。升级只允许影响LLM产生的Candidate；若未来需要比较模型版本，再引入更完整的运行版本管理，而不是提前建设Edition平台。
