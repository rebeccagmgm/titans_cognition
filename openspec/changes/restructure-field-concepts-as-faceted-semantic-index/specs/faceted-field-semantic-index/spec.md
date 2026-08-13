## Purpose

本能力将物理字段组织成可重放、可追溯的多维语义索引，以基础概念、限定 Facet、Alias/Variant、冲突和未知支持概念—字段—表双向调查，而不把候选结果冒充正式本体或标准字段。

## ADDED Requirements

### Requirement: V2 运行必须固定输入范围并保留 V1 基线

系统 SHALL 从指定 Physical Facts Manifest、范围配置和 V1 运行标识启动 V2，记录输入哈希、纳入对象/字段数、排除规则和方法版本。系统 MUST NOT 原地修改或删除 V1 `concepts.jsonl`、`field_concept_links.jsonl`、历史审阅页、LLM Review 或 Physical Facts。

#### Scenario: 对批准的 TRADEFLOW 输入运行 V2

- **WHEN** 系统加载当前批准的 TRADEFLOW 233 表范围及对应 V1 运行
- **THEN** 系统 SHALL 验证范围未漂移，在独立 V2 输出目录生成结果，并在 Manifest 中引用 V1 基线

#### Scenario: 输入范围发生漂移

- **WHEN** 实际对象或字段范围与配置和输入 Manifest 不一致
- **THEN** 系统 SHALL 停止正式 V2 生成并报告差异，而 SHALL NOT 静默接受新范围

### Requirement: Canonical 结果必须区分基础概念、表达、Facet 和字段绑定

系统 SHALL 将 V2 Canonical 结果至少分为 `base_concepts.jsonl`、`concept_expressions.jsonl`、`field_semantic_results.jsonl`、`field_facets.jsonl` 和 `manifest.json`。基础概念 SHALL 表达可复用中心语义，分别标记 `support_status=SUPPORTED/PROVISIONAL` 和 `semantic_scope=DOMAIN/TECHNICAL/UNRESOLVED`；表达 SHALL 以 `SOURCE_EXPRESSION`、`ALIAS` 或 `VARIANT` 关联基础概念候选；Facet SHALL 独立记录维度和值；字段语义结果 SHALL 以一个字段一条任务记录表达 `SINGLE_CANDIDATE`、`COMPETING` 或 `UNKNOWN`，并在候选绑定中引用概念、方法、状态、`relation_kind=EXPRESSES/RELATED_TO` 和可定位证据。`RELATED_TO` SHALL 支持“相关字段集合”导航，但不得增加概念直接成员、独立支持或推断候选数量。

#### Scenario: 动态名义本金字段被处理

- **WHEN** 字段文本支持基础概念“名义本金”和限定词“动态”
- **THEN** 系统 SHALL 将字段绑定到“名义本金”候选，并将“动态”记录为独立 Facet 或 Variant 表达，而 SHALL NOT 必须创建固定三级父子节点

#### Scenario: 同一字段包含多个限定维度

- **WHEN** 字段同时表达调整前、多头、动态和结算币种
- **THEN** 系统 SHALL 允许同一字段绑定组合多个 Facet，且 SHALL NOT 为限定词笛卡尔积生成新的基础概念

#### Scenario: 字段只与中心概念相关

- **WHEN** 字段表达“名义本金重置时间”且剥离限定词后仍存在“重置时间”这一独立中心语义
- **THEN** 系统 SHALL 将“名义本金”记录为 `RELATED_TO` 导航绑定，并 SHALL NOT 将该字段作为名义本金的直接 `EXPRESSES` 成员或支持计数

#### Scenario: 高频技术审计概念获得充分复现

- **WHEN** 创建时间、更新人或同步状态等技术表达满足 SUPPORTED 门槛
- **THEN** 系统 SHALL 保留其 SUPPORTED 状态并标记 TECHNICAL 候选范围，使其可搜索但与默认 DOMAIN 候选分区展示

### Requirement: 数据形态必须与业务中心概念分离

系统 SHALL 将金额、数量、比率、日期时间、代码、名称、文本、状态和标识符等记录为非权威 `value_kind` 或技术角色提示。系统 MAY 依据通用审计、同步、来源追踪和配置模式提出 `TECHNICAL` semantic scope，但该 scope 仍是候选且 SHALL 保留依据；`value_kind`、数据库声明类型、semantic scope 或字段名前缀 SHALL NOT 单独决定基础概念或唯一父类。

#### Scenario: 带有当日前缀的费用字段

- **WHEN** 字段表达“当日产生费用”
- **THEN** 系统 SHALL 优先生成“费用”基础概念候选并记录“当日”时态 Facet，而 SHALL NOT 仅因“当日”将其归入日期时间概念

#### Scenario: 声明类型与语义不一致

- **WHEN** 名称和注释支持金额概念而数据库字段类型或历史根类指向其他形态
- **THEN** 系统 SHALL 保留类型冲突作为提示或反证，并继续依据其他信号形成候选或 Conflict

### Requirement: 稳定复合业务概念必须优先于尾部数据形态词

系统 SHALL 区分宽泛 `field_family`、稳定复合 `semantic_core` 和正交 `Facet`。日期、时间、金额、数量、比率、代码和名称等宽泛形态 SHALL 只用于调查入口与召回，不得仅因共同尾词或声明类型把不同业务概念合并为 Alias/Variant。系统 MUST NOT 使用“最后一个词作为基础概念、其余词全部作为 Facet”的通用简化。

#### Scenario: 多种日期字段共同出现

- **WHEN** 范围内同时存在支付日期、交易日期、终止日期、敲入日期和结算日期
- **THEN** 系统 SHALL 将它们归入可搜索的日期字段族，但 SHALL 保留为不同稳定基础概念，而 SHALL NOT 发布为“日期”的 Alias/Variant

#### Scenario: 实际终止日期被处理

- **WHEN** 字段表达“实际终止日期”
- **THEN** 系统 SHALL 优先产生“终止日期”基础概念，并把“实际”作为限定候选，而 SHALL NOT 产生“日期 + TERMINATION + ACTUAL”作为默认业务解释

#### Scenario: 每年期权支付日期被处理

- **WHEN** 字段表达“期权每年支付日期”
- **THEN** 系统 SHALL 至少保留“支付日期”这一稳定中心语义，并将“期权”和“每年”作为上下文或限定候选，而 SHALL NOT 把该字段直接归为宽泛“日期”概念

#### Scenario: 形态尾词前的片段是否可拆不确定

- **WHEN** 移除动作、事件、对象或口径片段后无法证明剩余表达仍保持同一业务身份
- **THEN** 系统 SHALL 保留完整表达为 PROVISIONAL 或 COMPETING，并 SHALL NOT 强制将被移除片段转成 Facet

### Requirement: 中心概念与限定词提取必须通用且可重放

系统 SHALL 使用配置化、版本化的通用规范化、中心词识别、限定词拆分和候选规则处理所有范围内字段。规则 SHALL NOT 包含表名、字段名、概念名或“名义本金”等定点白名单/黑名单；相同输入、配置和程序版本 SHALL 产生相同结果。

#### Scenario: 验收样本包含名义本金

- **WHEN** 系统评测名义本金相关字段
- **THEN** 系统 SHALL 使用与其他字段完全相同的中心词和 Facet 规则，样本名称 SHALL 只用于验收查询而不影响算法分支

#### Scenario: 通用规则无法确定中心概念

- **WHEN** 字段文本只有低信息词、未知缩写或相互冲突的中心词候选
- **THEN** 系统 SHALL 输出 UNKNOWN 或 COMPETING 状态，并 SHALL NOT 通过范围覆盖率要求强行选择概念

### Requirement: 注释装饰必须与规范概念名分离

系统 SHALL 从候选表达中识别并单独保存数据字典标记、枚举和值域、日期格式、单位、币种、精度、缩放、废弃说明和实现备注。只有支持语义身份的文本 SHALL 参与规范基础概念名；被剥离内容 SHALL 保留来源定位，不得丢失。

#### Scenario: 交易方向包含枚举说明

- **WHEN** 多个表达分别为“交易方向”“交易方向 数据字典”和“交易方向 1买 2卖”
- **THEN** 系统 SHALL 召回共同基础概念“交易方向”，并把字典和值域保存为附加信息而非三个基础概念

#### Scenario: 日期字段包含格式

- **WHEN** 字段注释为“成交日期 YYYYMMDD”
- **THEN** 系统 SHALL 将格式保存为属性，且基础概念候选仍为“成交日期”

### Requirement: Alias、Variant 和独立概念必须有明确边界

系统 SHALL 将仅由大小写、空格、连接符、中英文常见映射或格式差异形成的表达优先作为 Alias 候选；将共享基础概念但带有可解释限定词的表达作为 Variant 候选。基础概念状态 SHALL 由配置化独立支持门决定：默认至少要求中心语义在不同物理字段中复现，且跨对象复现或多个不同 Facet/表达共同支持时才标记 `SUPPORTED`；未达到门槛但中心语义可解析的单字段表达 SHALL 作为 `PROVISIONAL` 保持可搜索但不进入默认主要概念导航。支持门及实际计数 SHALL 写入 Manifest，单成员聚类 SHALL NOT 自动成为 `SUPPORTED` 基础概念。

#### Scenario: 规范化同名父子表达

- **WHEN** 两个表达规范化后相同且仅存在大小写、空格或连接符差异
- **THEN** 系统 SHALL 折叠为同一基础概念下的 Alias，并 SHALL 通过质量校验阻止形成同名父子节点

#### Scenario: 单成员表达具有业务限定词

- **WHEN** 一个单成员表达由基础概念和可识别限定词组成
- **THEN** 系统 SHALL 默认保存为 PROVISIONAL 基础概念候选、Variant 与 Facet并保持可搜索，而 SHALL NOT 仅因其成员数为一进入默认主要概念导航

#### Scenario: 多个独立表达支持同一中心语义

- **WHEN** 同一中心语义在多个物理字段中复现，并满足配置记录的跨对象或多表达支持门
- **THEN** 系统 SHALL 将对应基础概念标记为 SUPPORTED，并保留组成该判断的字段、表达、Facet 和方法计数

#### Scenario: 同属日期字段族但业务身份不同

- **WHEN** 两个表达分别为“交易日期”和“终止日期”
- **THEN** 系统 SHALL 允许它们共享日期字段族，但 SHALL NOT 将两者标记为 Alias 或 Variant

### Requirement: 冲突、疑似噪声和序号后缀必须显式保留

系统 SHALL 对同名跨概念冲突、多个接近候选、疑似错字/截断/拼接、未知缩写和数字后缀表达生成 `CONFLICT`、`COMPETING`、`UNKNOWN` 或待核查候选。`UNKNOWN` SHALL 由字段语义结果中空的候选集合表达，不得伪造 Unknown 基础概念。系统 MUST NOT 在缺少字段与表上下文证据时自动覆盖源文本、合并序号字段或选择唯一解释。

#### Scenario: 同名字段落入不同语义候选

- **WHEN** 同一规范化标签同时获得不同基础概念支持
- **THEN** 系统 SHALL 保留竞争绑定及各自依据，并在审阅 Projection 中显示 Conflict

#### Scenario: 字段名只以数字结尾区分

- **WHEN** 价格1至价格4或日期1至日期4被召回为同族候选
- **THEN** 系统 SHALL 生成合并或序列 Facet 候选，但 SHALL NOT 在缺少上下文时自动断言它们语义等价

### Requirement: 字段、概念、Facet 和表必须支持双向查询

系统 SHALL 先以机器可读结果和轻量对比报告验证双向查询及语义形态 Gate。Gate 通过后，审阅 Projection SHALL 按 `DOMAIN/TECHNICAL/UNRESOLVED` 分区，支持从基础概念及任意 Facet 组合查找字段和所在表，也 SHALL 支持从字段或表反查基础概念、表达、Facet、竞争候选和状态。默认 DOMAIN 列表 SHALL NOT 删除或掩盖 TECHNICAL/UNRESOLVED；页面 SHALL 分页并按需加载详情，初始 DOM 和单次渲染量 SHALL 由配置上限约束而不随全量字段线性增长。

#### Scenario: 从名义本金查看相关字段

- **WHEN** 用户打开“名义本金”并选择“调整前”和“结算币种”Facet
- **THEN** 页面 SHALL 返回满足组合条件的字段及表链接，并允许清除 Facet 查看全部名义本金相关字段

#### Scenario: 从物理表查看字段语义

- **WHEN** 用户从 Panorama Object Card 或 V2 表入口打开一张表
- **THEN** 页面 SHALL 分页显示该表字段的基础概念、Facet、Alias/Variant 和 Conflict/Unknown，并提供返回概念视图的链接

#### Scenario: 业务用户审阅一个概念

- **WHEN** 用户打开任一概念或字段族
- **THEN** 页面 SHALL 默认使用“字段族、基础概念、别名、限定条件、直接字段、相关字段”等业务可读中文组织信息，并将 `EXPRESSES/RELATED_TO` 与英文 Facet 枚举放入解释或技术详情，而 SHALL NOT 要求用户先理解内部数据契约

#### Scenario: 语义形态 Gate 未通过

- **WHEN** 真实 V2 运行仍产生规范化重复、装饰型基础概念、强制兜底概念，或五类调查无法从结果文件完成概念—字段—表查询
- **THEN** 系统 SHALL 保留本次 Canonical 结果和失败报告并停止完整页面建设，而 SHALL NOT 用展示层掩盖语义缺陷

### Requirement: V2 必须与表级业务分类解耦

V2 SHALL 使用稳定 `column_id` 和 `asset_id` 支持未来 Projection 组合，但本 Change SHALL NOT 读取表级业务分类作为中心概念或 Facet 输入，也 SHALL NOT 生成业务模块、业务对象或正式本体标签。

#### Scenario: 已有表级业务分类结果存在

- **WHEN** V2 与表级分类结果同时存在
- **THEN** V2 SHALL 独立完成并保持可通过物理 ID 关联，当前审阅页 SHALL NOT 因表级分类改变基础概念、Facet 或候选状态

### Requirement: V2 首轮验收必须覆盖结构性错误模式

首轮 SHALL 在固定 TRADEFLOW 范围内以至少五类代表性概念检查基础概念召回、Facet 拆分、Alias 归一、Conflict/Unknown 和双向导航。验收样本 SHALL 至少覆盖名义本金、交易对手、成交时间、保证金和交易方向，但不得参与算法配置或阈值调整，也不得据此声明总体准确率或跨 Schema 泛化。首轮 Gate 只证明结构不变量和调查入口成立，不证明成员语义总体正确。

#### Scenario: 运行首轮比较

- **WHEN** V2 在固定输入上完成
- **THEN** 系统 SHALL 生成 V1/V2 对比报告，至少列出规范化同名父子数量、注释装饰独立概念数量、单成员基础概念数量、Conflict/Unknown 数量及五类样本的可见差异

#### Scenario: V2 仍主要复述源注释

- **WHEN** 大量单成员表达仍被提升为基础概念或五类样本无法形成有用组合检索
- **THEN** 项目 SHALL 保留失败结果并停止扩大范围，而 SHALL NOT 通过全量 LLM 调用掩盖结构缺陷

#### Scenario: 高频数据形态吞并稳定复合概念

- **WHEN** 日期、金额、代码或名称等宽泛概念吸收大量具有不同动作、事件、对象或口径身份的表达
- **THEN** 语义形态 Gate SHALL 失败，项目 SHALL 保留失败样本并修正通用复合概念边界，而 SHALL NOT 将页面完成或结构校验通过视为业务验收

### Requirement: LLM 必须保持为候选旁路

V2 的基础概念、Facet、Alias/Variant、字段绑定、冲突和审阅页面 SHALL 在不调用 LLM 时完整生成。任何 LLM 建议 SHALL 使用独立候选数据集，不得自动覆盖 V2；Provider SDK 继续受 D-005 独立授权约束。

#### Scenario: 没有 Provider SDK 授权

- **WHEN** 用户运行 V2 确定性流程
- **THEN** 系统 SHALL 完成全部 V2 Canonical 结果和 Projection，且 SHALL NOT 发起模型网络请求
