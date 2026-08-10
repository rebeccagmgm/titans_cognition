# 09 地图交付规范

## 1. 地图定位

地图是Cognition Result Bundle的可浏览Projection，用于帮助用户快速建立全貌和下钻证据。V1不建设正式Web产品，但不能只交付Parquet文件和算法日志。

## 2. 交付形态

- 生成式静态HTML，可本地打开。
- 可选生成Excel/CSV明细用于筛选和复核。
- 不需要服务端、数据库、登录、权限和在线编辑。
- 页面数据由Canonical结果生成，不手工维护。

地图分阶段交付：V1A交付Panorama和物理Object Card；V1B为TRADEFLOW分层样本增加核心认知卡；V1C才交付全量对象族、字段概念、语义候选和LLM解释页面。

## 3. 地图不是单一树

完整V1目标提供五种互补视图，各阶段只显示已启用能力：

1. 层级导航：V1A为范围 → Schema → 对象 → 字段；V1C再增加对象族入口。
2. 表格比较：数量、覆盖、角色、证据等级和Unknown。
3. 关系视图：依赖、Lineage和关系候选。
4. 认知卡片：对象、对象族、字段概念和语义候选。
5. 未知地图：证据缺口、冲突和失败。

Schema是物理入口，不能把它展示成唯一业务分类树。

V1C如需“业务模块”导航，只能由人工维护标签或Reviewed结果生成Business Module Projection；它不要求独立Canonical结果表，也不能由Schema名称自动继承。

## 4. 页面规范

### 4.1 `panorama/index.html`（V1A）

必须显示：

- 分析范围、运行标识和可见边界。
- 表、边界对象、字段、约束、索引、定义和依赖数量。
- 对象/字段注释覆盖。
- 提取成功、部分、失败和无权限分布。
- 各Schema的对象类型、字段数、注释覆盖、约束/索引和依赖概况。
- 粗结构/命名分组及其明确的非语义标签。
- 能力缺口和解析失败概览；V1A不把提取失败称为认知Unknown。
- 明确声明“测试库元数据认知候选，不代表生产业务事实”。

每个Schema页面必须列出对象并可打开物理Object Card；如果Schema配置为Deep Case，则提供进入深度地图的入口。

### 4.2 `deep-cases/tradeflow/index.html`（V1B/V1C）

- V1B只显示分层样本及Identity、Grain、Role、Relation、Evidence和Unknown。
- V1C扩展为TRADEFLOW全量，并增加Object Family、Field Concept和Semantic Candidate汇总。

### 4.3 对象族页面（V1C）

每个Family显示：

- 临时名称和状态。
- 形成该族的结构原因。
- 核心、辅助、边缘和冲突成员。
- 共同Identity、Grain和Field Role模式。
- 族内/族外关系。
- LLM命名建议、反证和人工决定。
- 证据等级和Unknown成员。

### 4.4 Object Card

Object Card按阶段扩展，未启用区块不得以空面板、`Coming Soon`或默认Unknown占位。

#### V1A物理Card

```text
物理标识区
- Schema / Object / Type
- 注释和提取状态

声明事实
- 字段、PK、UK、FK、索引、NOT NULL
- DDL/定义状态
- Oracle依赖

能力与缺口
- 当前账号可见能力
- MISSING / NO_PERMISSION / FAILED
- 测试库元数据边界
```

#### V1B样本深度扩展

仅TRADEFLOW分层样本增加：

```text
结构认知
- Inference Outcome：Single / Competing / Unknown / Not Evaluable
- Identity候选
- Grain候选
- Field Role摘要
- Object Role候选
- Structural Relation候选

证据与评审
- 支持证据
- 反证
- Review Decision
- Unknown原因 / 缺失能力 / 下一步验证

固定警示
- 仅基于测试库元数据推断
- 未读取业务数据行
- Identity和Grain未经过数据级唯一性验证
```

#### V1C深度扩展

TRADEFLOW全量在V1B区块之上按实际启用能力增加：

```text
对象族与字段概念
- Object Family成员关系
- Field Concept映射与冲突

语义候选
- 用途候选
- 相关业务概念
- LLM Action：Respond / Abstain（仅启用LLM时）
```

技术PK和候选业务Grain必须分开展示。`data_validation_status=NOT_PERFORMED`必须使用文字警示，不得仅隐藏在详情字段中。

### 4.5 Field Concept页面（V1C）

- 候选概念名称和类型。
- 物理字段成员及所在对象。
- Member/Conflict/Excluded状态。
- 数据类型、键参与和对象族分布。
- 同名异义和同义异名说明。
- 证据和评审状态。

### 4.6 Relation页面

- 关系来源、认识论层级、方向和证据等级。
- FK/Oracle Dependency显示为Physical Fact，SQL Lineage显示为Derived Observation，Structural/Semantic Relation显示为Candidate。
- 统一页面读取`relation_index` Projection，但不得将所有层级统称为“候选”或“血缘”。
- Boundary Node醒目标识。
- 图形过密时优先提供邻接表和局部一跳视图，不追求“全库蜘蛛网”。

### 4.7 Semantic Candidate页面（V1C）

- 临时概念名和定义候选。
- Identity/Grain模式。
- 相关Object Family、Field Concept和Relation。
- 支持证据、反证、Unknown和Abstain。
- 不使用“正式业务定义”措辞。

### 4.8 `unknowns.html`

按原因分组：

- 缺少键或约束。
- 粒度歧义。
- Role冲突。
- SQL解析失败。
- 缺少注释/Wiki。
- 外部边界被截断。
- LLM Abstain或非法输出。
- 结构Unknown、LLM Abstain和人工Deferred分别列示。

每项显示下一步最有价值的验证方式。

## 5. 导航和筛选

必须支持：

- 按对象名、字段名、注释关键词搜索。
- 按Object Role、Field Role、证据等级和评审状态筛选。
- 从对象跳转到对象族、字段概念、关系和Evidence。
- 从Evidence返回所有引用候选。
- 保留当前范围和筛选上下文。

V1不要求自然语言搜索、向量检索或复杂图交互。

## 6. 证据呈现

- 声明事实、派生观察、结构候选、语义候选和人工决定使用不同视觉标识。
- 支持与反证并列，不把反证折叠隐藏。
- 原始DDL/Wiki仅显示必要片段和定位，不默认渲染全部敏感文本。
- 原始算法分数放在详情中，不展示成概率或星级可信度。

## 7. 敏感信息

地图不得包含：

- Oracle连接信息、账号、主机、端口。
- API Key和Wiki Token。
- 未批准外发或展示的完整Wiki/DDL内容。
- 业务数据样本。

输出目录和分享边界见[11 安全与运行](11-security-and-operations.md)。

## 8. 地图验收

- 任何Panorama范围对象可在三次以内的层级导航中打开物理Object Card。
- V1B样本对象可继续打开Identity、Grain、Role、Relation及其Evidence；V1C全量对象同样满足。
- 任何候选可跳转到支持和反对Evidence。
- 用户能区分数据库声明、程序推断、LLM建议和人工决定。
- Unknown和失败可以被搜索和汇总。
- 页面中不存在只在展示层维护、无法回溯Canonical结果的业务属性。
- 地图确实帮助用户完成[08 评测](08-evaluation.md)中的效用任务。
