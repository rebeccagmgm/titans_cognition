## Why

现有字段概念 V1 已证明“概念 → 字段 → 表”的导航有用，但全树体检显示其三级单继承模型把数据形态、基础概念、限定词和源注释压入同一层级，造成超大兜底类、错误挂载、重复父子节点和大量单成员概念。继续逐簇调用 LLM 或修补个别标签不会消除这些系统性问题，因此需要保留 V1 历史基线，并用新的多维语义索引契约重构确定性主线。

## What Changes

- **BREAKING**：新增 V2 字段语义索引契约，不再把固定三级树作为 Canonical 结果；旧 `concepts.jsonl`、`field_concept_links.jsonl`、审阅页和 LLM Review 结果保持只读可追溯，但 V2 消费者必须读取新的类型化结果。
- 将字段语义拆为基础概念、限定 Facet、Alias/Variant、字段绑定和显式 `UNKNOWN/CONFLICT`，避免把“动态、调整前、多头、结算币种”等正交维度组合成无限层级节点。
- 将金额、数量、比率、日期时间、标识符等现有根类降为非权威 `value_kind`；它们不再充当唯一业务父类，声明字段类型仍只作低权重提示。
- 建立确定性、配置驱动的中心词抽取、注释装饰剥离、中英文/格式 Alias 归一、同名父子阻断、Facet 提取和冲突检测；不得为“名义本金”或具体字段增加定点特例。
- 将证据状态与导航分区分开：`SUPPORTED/PROVISIONAL` 表示概念支持强弱，`DOMAIN/TECHNICAL/UNRESOLVED` 表示业务候选、技术字段或未决范围；单字段表达和技术字段都保持可搜索，但不会因高频复现挤占默认业务候选列表。
- 每个字段产生独立语义结果：可以有一个主要候选、多个竞争候选或零候选的 `UNKNOWN`，并可附带零到多个 Facet；序号后缀、疑似错字、缩写及跨父类同名只生成待核查候选，不做无证据自动合并。
- 输出最小但可扩展的本地 JSONL/Manifest 契约，并生成按需加载的审阅 Projection，支持概念 ↔ 字段 ↔ 表双向导航、Facet 组合筛选、Alias 搜索和冲突/未知查看。
- 分两段交付：先在真实 TRADEFLOW 输入上生成 Canonical 结果和轻量对比报告，通过语义形态 Gate 后才建设完整审阅页面；若 Gate 未通过，保留失败结果并停止 UI 投入。
- 首轮仍只在已经批准的 `TITANS_TRADEFLOW` 233 表固定输入上实施和评测；“名义本金、交易对手、成交时间、保证金、交易方向”作为覆盖不同错误模式的验收样本，不作为算法特例。
- LLM 仅作为确定性 V2 之后的可选候选审阅层；本 Change 不启用 Provider SDK、不把现有 LLM 建议自动写回 V2，也不要求通过模型处理全部概念。
- 本 Change 不整合表级业务主题分类；V2 只通过稳定 `column_id/asset_id` 保留未来组合 Projection 的连接点，避免在字段语义纠偏尚未验证时同时引入表级分类争议。

## Capabilities

### New Capabilities

- `faceted-field-semantic-index`: 定义基础概念、Facet、Alias/Variant、字段绑定、冲突/未知、确定性发现规则、V1→V2并行迁移、双向导航和 TRADEFLOW 首轮验收。

### Modified Capabilities

- `cognition-delivery-governance`: 明确授权在既有 TRADEFLOW 233 表范围内重构字段概念候选索引，同时继续禁止正式本体、自动业务主题确立、其他 Schema 扩展、业务验收替代和一般规模化。

## Impact

- 主要影响字段概念发现模块、CLI、配置、结果 Schema、审阅页面和相关测试；Physical Facts、Panorama Object Card、历史 V1 输出和现有 LLM Review 输出不原地修改。
- V2 仍使用本地 Python、JSONL/Parquet/YAML、静态 HTML 和内容哈希；不引入图数据库、向量数据库、远程服务、消息队列或新的认证体系。
- 首轮可复用已经安装的文本相似、聚类和本地分析依赖，但基础概念/Facet 拆分和质量门必须在无 LLM 时可重放运行。
- 生成结果继续保存在 Git 忽略的本地输出目录，不读取业务数据行，不增加数据库权限或外发范围。
