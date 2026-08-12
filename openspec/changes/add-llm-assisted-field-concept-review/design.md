## Context

确定性字段概念引擎已经从 Physical Facts 生成 `concepts.jsonl`、`field_concept_links.jsonl`、Manifest 和分页审阅页。当前错误主要集中在少量语义混杂簇、标签证据不足簇和层级/Facet 难以靠字符串规则区分的簇，而不是所有 5,512 个字段都需要重新解释。参见 `proposal.md` 和本 Change 的 capability spec。

现行 D-005 仅允许当前 GPT 会话处理固定 TRADEFLOW Evidence Pack；通用 Provider SDK 尚未获授权。因此设计必须先支持文件式离线审阅，并保持确定性主线在没有模型时完整可运行。

## Goals / Non-Goals

**Goals:**

- 以算法和统一阈值选择最值得审阅的簇，把 Token 花在不确定性最高的位置。
- 将现有事实压缩为逐簇、可校验、可缓存的最小 Pack。
- 将模型的语义判断变成受约束的数据差异，而非直接修改概念树。
- 在同一轻量审阅页中比较 V1 与候选修订，并继续链接到字段、表和 Object Card。

**Non-Goals:**

- 不让模型重跑全量聚类或逐字段分类。
- 不把 LLM 判断训练成自动接受规则，也不在本 Change 建设本体治理平台。
- 不实现通用多 Provider 编排、Agent 工具调用、向量数据库或远程服务。
- 不以字段类型作为语义真值，不读取列值或业务数据行。

## Decisions

### 1. 在确定性 V1 之后增加旁路，而不是修改聚类器

新增独立 `llm_field_review` 模块和命令，输入是一个已完成且 Manifest 可校验的字段概念运行。流水线为：

```text
V1 concepts + links + facts
  -> deterministic issue scoring
  -> bounded review packs
  -> offline export / response import
  -> schema and evidence validation
  -> revision candidates
  -> comparison projection
```

候选层只引用 V1 的稳定 `concept_id`、`field_id` 和输入哈希。它不调用或重写 V1 聚类器，因此删除候选输出即可回滚。

**替代方案：** 把模型直接接入聚类循环。拒绝，因为同一输入将不再保证确定性基线，模型失败也会阻断字段导航。

### 2. 用统一疑难度评分排序，并用 Token 上限截断

选择器从现有概念、链接、字段文本和诊断信息计算簇级信号：

- 组内文本凝聚度低或离群成员比例高；
- 当前标签在成员名称/注释中的支持度低；
- 同一字段存在接近的竞争概念，或父子路径出现冲突；
- 一个簇内混合多个可能的阶段、方向、币种、口径限定。

每个信号保留原始值、阈值和触发原因。配置提供 `max_packs`、单 Pack 字符/Token 估算上限及整次运行 Token 预算；系统按疑难度与预计成本排序，在预算耗尽前截断。所有阈值适用于整个运行，不增加字段名、表名或“名义本金”特例。

类型族只作为低权重提示和矛盾信号，不能单独触发合并、拆分或否决。

**替代方案：** 全量字段送模型。拒绝，因为大量确定性容易样本没有增量，成本随 Schema 线性增长，也更难审阅。

### 3. Pack 是逐簇的规范化 JSON，而不是自由文本上下文

每个 Pack 包含：

- `pack_id`、输入 run/hash、目标 concept/path 和选择原因；
- 代表性成员、边界成员和反例，使用稳定 Evidence ID；
- 字段名、字段注释、表名/表注释的短上下文、类型提示和现有链接状态；
- 成员数、表数、限定词分布和证据缺失标记；
- 允许动作、Prompt 版本和响应 JSON Schema 版本。

代表成员按确定性策略选取：接近中心、接近边界、常见变体和离群点分别取有限数量；完整成员清单只保留 ID 和必要短文本，并受 Pack 预算限制。规范化 JSON 使用稳定键序和 UTF-8；`pack_hash` 覆盖 Pack、Prompt 模板和响应契约。

**替代方案：** 直接把审阅 HTML 或完整 JSONL 发给模型。拒绝，因为上下文重复、边界不清且无法对响应做 Evidence 白名单校验。

### 4. 响应表达结构化差异，不生成一棵替代树

响应顶层绑定 `pack_id`、`pack_hash`、模型标识和一个动作。动作载荷分别为：

- `KEEP`：保留现有概念并解释证据；
- `RENAME`：给出候选标签和受影响 concept；
- `SPLIT`：给出候选子组、组标签、成员 Evidence ID 和未决成员；
- `PARENT_CHILD`：给出明确的父、子和“是一种”依据；
- `FACET`：给出基础概念、维度、值及适用成员；
- `ABSTAIN`：给出缺失证据或未解决冲突。

校验器检查枚举、ID 白名单、成员不重复、目标仍属于输入簇、证据引用存在、标签非空及动作特有约束。自由说明被保存但不能绕过结构校验。有效响应被投影成 `revision_candidates.jsonl`；无效响应进入错误数据集。

**替代方案：** 让模型返回任意 Markdown 建议。拒绝，因为无法自动比较、重放或阻止越界引用。

### 5. 当前 GPT 使用批次导出/导入，SDK 是封闭扩展点

第一版命令分成三个可独立执行阶段：

1. `prepare`：选择疑难簇并生成 Pack 与批次导出文件；
2. `import`：读取当前 GPT 返回的 JSONL，逐行校验并生成候选；
3. `render`：生成比较审阅页。

批次导出同时包含简短系统约束、响应 Schema 和多个 Pack；批次大小由 Token 预算控制。手工在当前会话传递文件不改变 Pack 哈希。未来 Provider 适配器只能消费同一 Pack 并返回同一响应契约；未满足 D-005 时入口返回 `NOT_EVALUABLE`，不提供绕过开关。

### 6. 内容寻址缓存与运行清单分离

输出建议为：

```text
field-concepts/llm-review/
├─ selection.jsonl
├─ packs.jsonl
├─ responses.jsonl
├─ revision_candidates.jsonl
├─ errors.jsonl
├─ manifest.json
└─ review/index.html
```

响应缓存使用配置的本地 Git 忽略目录，以 `pack_hash + response_schema_version + model_id` 的联合哈希为键。运行目录记录实际采用的响应副本和校验状态，避免缓存成为不可见事实来源。缓存命中只表示内容完全相同，不代表模型结论已被接受。

### 7. 比较页延续有界 DOM 设计

页面首屏只载入概念级摘要；候选详情、字段列表和表链接按需分页渲染，字段反查继续放在 Web Worker 中。每个候选显示基线、建议动作、证据/反证、未决成员和验证状态，并复用现有 Object Card URI 生成规则。

人工决定若在首版落盘，仅保存为独立 `ACCEPT/REJECT/DEFER` 决定及操作者说明；它不修改模型响应，也不自动改写 V1。

## Risks / Trade-offs

- [选择器可能漏掉真正错误的簇] → 保留全量 V1 浏览入口，并报告未送审范围；首轮评估选择质量而非只看模型输出质量。
- [模型把相似命名误当业务等价] → Pack 同时提供边界成员、表上下文和反例，要求引用 Evidence ID，并允许 `ABSTAIN`。
- [层级和 Facet 仍可能有主观性] → 响应必须显式声明关系类型；比较页并排展示而不自动落入概念树。
- [Token 预算导致部分疑难簇未审阅] → 使用稳定排序和预算截断，Manifest 记录入选、跳过及预计成本。
- [当前会话模型标识不等于可复现的远程模型版本] → 同时记录模型标识、Prompt/Pack/响应哈希；只声明响应可重放校验，不声明模型重新调用必然一致。
- [字段类型质量不可靠] → 类型只作提示，所有候选仍需名称、注释或上下文证据。

## Migration Plan

1. 在不改 V1 文件契约的前提下增加候选层数据契约、选择器与 Pack 生成器。
2. 用合成 fixture 验证选择、预算、哈希、Evidence 白名单和动作校验。
3. 固定当前 TRADEFLOW 运行，导出少量高疑难 Pack，并通过当前 GPT 会话导入一批真实响应。
4. 生成分页比较页，人工检查明显错误簇、合理保持簇和 `ABSTAIN`。
5. 只有结果相对 V1 提供可见增量时，才讨论将人工接受候选合并为后续独立 Change。

回滚只需停止使用或删除 `llm-review` 独立输出；V1 概念、字段链接及原审阅页不受影响。
