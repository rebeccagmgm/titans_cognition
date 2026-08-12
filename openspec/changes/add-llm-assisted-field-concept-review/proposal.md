## Why

确定性字段概念 V1 已经形成可用的概念—字段—表导航，但仍存在过宽簇、错误父子关系、限定词维度混叠和候选命名不稳等问题。继续增加字段级特例会破坏可重放性；现在适合在不覆盖 V1 基线的前提下，引入一个只审阅疑难簇的有界 LLM 候选层。

## What Changes

- 从已固定的字段概念结果中，按确定性规则选择歧义、过宽、冲突或无法可靠命名的少量簇，不把全部字段发送给模型。
- 为每个选中簇生成内容寻址的最小审阅 Pack，只包含完成当前判断所需的代表字段、注释、类型提示、概念路径、反例、统计和已知缺口。
- 允许 LLM 以强类型输出提出 `KEEP`、`RENAME`、`SPLIT`、`PARENT_CHILD`、`FACET` 或 `ABSTAIN`；父子层级可以按证据形成不同深度，币种、方向、阶段等正交限定优先表达为 Facet。
- LLM 结果写入独立候选文件，与确定性 V1 并排展示；不得自动覆盖概念、移动字段、修改 Physical Facts 或形成正式本体。
- 第一条可运行路径复用当前 GPT 会话的离线导出/导入和内容哈希缓存。外部 SDK 调用继续默认禁用，只有 D-005 另行批准 Provider、账号和本 Change 的外发范围后才能启用。
- 记录 Pack、Prompt、响应、模型标识、Token（可得时）、校验状态和重放哈希；单个 Pack 失败或 Abstain 不阻塞确定性结果。
- 首轮仍限定 `TITANS_TRADEFLOW`，以固定疑难样本比较 V1 与 LLM 修订候选，不据此声明总体准确率、跨 Schema 泛化或业务验收。

## Capabilities

### New Capabilities

- `llm-assisted-field-concept-review`: 有界选择字段概念疑难簇，生成可重放审阅 Pack，导出/导入强类型 LLM 判断，并以不覆盖基线的方式展示修订候选。

### Modified Capabilities

- `cognition-delivery-governance`: 允许在已接受的确定性字段概念试验之后运行独立、有界且不提升业务验收或规模化状态的 LLM 审阅层，并继续受 D-005 控制。

## Impact

- 新增字段概念 LLM 审阅命令、Pack/响应 Schema、确定性校验器、内容哈希缓存索引和对比审阅投影。
- 读取现有 `concepts.jsonl`、`field_concept_links.jsonl`、Physical Facts 与 Manifest；不原地修改这些文件。
- 第一版不引入 Agent SDK、远程向量库、服务端队列、数据库或通用多 Provider 框架；当前 GPT 会话通过文件导出/导入工作，SDK 适配器为 D-005 批准后的条件实现。
- 运行结果保存在独立本地输出目录并保持 Git 忽略；密钥、连接信息、业务数据行、完整 DDL 和未经批准的 Wiki 正文不得进入 Pack、日志或缓存。
