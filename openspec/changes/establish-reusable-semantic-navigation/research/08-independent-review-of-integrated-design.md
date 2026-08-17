# 07 整合设计实现前独立复审

> 审阅日期：2026-08-14  
> 审阅对象：`07-integrated-semantic-navigation-design.md`、`07-integrated-semantic-navigation-contract.yaml`、`07-integrated-validation-plan.yaml`  
> 审阅性质：实现前语义架构复审，不是实现验收、页面验收或业务验收  
> 最终处置：`REWORK`

## 1. 审阅结论

`07` 已经纠正 `05` 指出的多数方向性错误：P0–P5 分层总体单向，Order/Trade identity 已拆分，SHORT/LONG 和 SOURCE/TARGET 的裸 token 越级路径被禁止，六个 Reader 均有候选契约，顶层也不再声称一条普适六阶段串行生命周期。四入口、合同存续包络、可重复活动、横切支撑面和单页三栏投影的方向可以保留。

但 `07` 还不能作为完整语义实现基线。决定性问题不是 YAML 能否解析，而是：声明 ID 注册表漏项；冻结 Gold 的短币种负向断言没有完成 Canonical 适配；正式分类被写成闭集但没有开放候选保留路径；8 个字段属性/12 个 qualifier 的“可达”主要是静态声明而不是行为验证；P2/P3/P4 缺少可执行的唯一 grain；Position 与 Cash Flow 两处稳定定义仍混层；实现前独立复审被安排到了实现后；Gate 没有可机器复核的前驱结果和非空/NOT_EVALUABLE 白名单；页面旅程也没有逐 Reader 覆盖。

缺陷计数：`BLOCKER=0`、`MAJOR=10`、`MINOR=2`。

允许开始的工作仅限中性的 P0/P1：可推进实施顺序第 1–2 步，即实现 TRADEFLOW Field Evidence Provider，并为冻结的 13,611 个字段形成一字段一 Pack 的完整 Evidence Pack。不得把第 3 步 Suite A 声称为 PASS；不得开始第 4 步 handoff、P2/P3/P4 语义实现、页面生成或模型推理，直至本报告的最小返工完成并重新独立复审。

本结论不表示任何 Reader 已发布，不表示业务验收完成，也不授权第二 Schema。

## 2. 审阅范围与隔离性

本轮完整读取了项目规则、当前状态/开放决定、三份 `07` 核心文件、`05` 独立审阅、Agent A/B 的全部 `06` 输入；对 `01-*` 至 `04-*` 只读取与本次裁定直接相关的业务骨架、字段形态、歧义审计、历史 Gold 和导航结构。物理事实只沿已记录 provenance、Manifest 和 artifact path 回到 Stage 0 JSON；没有查询业务数据行。

隔离边界如下：

- 没有把 Agent A、B、C 的 disposition、自检或计数当作证据；本报告中的 YAML、ID、哈希、raw 字符、Stage 0 数量和路径结论均重新计算。
- 没有运行固定 Harness。当前没有本 Change 对应的新 Workflow Profile、Schema Case Pack 或生成物，Harness 不能回答当前设计未知项。
- 没有运行语义填充、页面生成、模型推理、外部搜索、数据库查询或业务行采样。
- 没有修改实现代码、测试、配置、既有研究文件、OpenSpec 状态或正式输出。
- 没有执行 Git stage、commit、branch、push，也没有执行其他 Git 操作。
- 本轮仅新增本文件。

## 3. 输入文件及 SHA-256

以下哈希均在本轮以文件字节重新计算；路径相对仓库根目录，算法为 SHA-256。

### 3.1 任务、规则与当前边界

| 输入 | SHA-256 |
|---|---|
| 任务附件 `pasted-text.txt` | `e24f91e66c73bef9178a4363160ddb4fcefd0f3a38d484585d6d0edcbeb1ea32` |
| `AGENTS.md` | `eff83715a70997c27b7cdb45b8ff389f30d36a7cdaae0e6af0368030a9cecd12` |
| `README.md` | `e924b1a9c601090a052823ebc6f7e90cf6f54385d7d71f0d47a602971f60ac2b` |
| `CONTEXT.md` | `5d27491efb0ddb218d541d5f744d7b480f5a31bb531ca90e49097f0b3bcf98d0` |
| `docs/spec/README.md` | `ab637fcc4561abeb4905ee3683eecb67ac7ad9d4fb7542bcc2a314fc5099ec02` |
| `docs/spec/12-open-decisions.md` | `73b306cb3c13e115cef55103be7aa062667ee9931de99b912aa917c5e28ff1cf` |
| `docs/current-status-baseline.md` | `325e19c0d10eacb397c2ff9ddae884a6c14d0b9970d8fd0eb78b784e9311de7a` |

### 3.2 历史研究、正式审阅与 Agent A/B 输入

| 输入 | SHA-256 |
|---|---|
| `research/01-domain-skeleton.md` | `0649d84e95031db027b106b2824d32d853f2268122c8ea60201328e4474b98c4` |
| `research/02-field-corpus-analysis.md` | `82a16aa3873820580e4e63761e13f3cbb5bc3d8cbfcf274584f9f4aaa48e4226` |
| `research/02-field-shapes.json` | `36c117eba0cf587b551063367d5eccd349583efdbab12f3f3777315f8599e093` |
| `research/03-disambiguation-audit.md` | `8baa5c955b6de07123138c4fe719b6fd02ede137477d3eb056da6171e6ee1c43` |
| `research/03-gold-set.yaml` | `6d0a500826c9a8473a66496c7e7dae4405d5c4eb59b2ab552ed80fc39a698586` |
| `research/04-integrated-navigation-proposal.md` | `65bb8b6d181f9067fa04f8ced90a2d275c4669a3f6f07ef823bd77f8a23f200b` |
| `research/04-navigation-skeleton.yaml` | `fd280d4a938c17efdcd442bcb339884766390bbff05956f0e971b918abb29c80` |
| `research/05-independent-review.md` | `79961978fd733ce992760ee27d2200c3bd707e300646d793f9ba012d355a38b4` |
| `research/06-reworked-navigation-proposal.md` | `ed9a95261ee0e6b78eabb281af197e29346388aa19be698abe6dd82cc1e6db83` |
| `research/06-navigation-skeleton.yaml` | `d23479acbcb0f93dc303279bfa99ba72a72d3bfc340f2eec9a65af402740759a` |
| `research/06-gold-set.yaml` | `cbe07e7bc61bfd8f4167fc740805219f92c9122c7f0ab82d7deb8cec42828df0` |
| `research/06-field-evidence-preparation-proposal.md` | `7d455c4db7ec8308f6a6ddd55492f6e74bfa6dd2572329f57c2383cfa5ea31c7` |
| `research/06-field-evidence-preparation-contract.yaml` | `99efa074b614477a7e32b334e20738fdf247f4861820572b3f3e6d77c53d0d8a` |
| `research/06-field-evidence-gold-set.yaml` | `db804025bc3d311912fd854cf34abcc83d3ec676ecbe90a3c0fb00d4d04e1f5c` |

### 3.3 核心审阅对象与冻结运行事实

| 输入 | SHA-256 |
|---|---|
| `research/07-integrated-semantic-navigation-design.md` | `a5bf3ad61ef94f6a678a718e33a7001af19f318cd9bd9888036734206e2243af` |
| `research/07-integrated-semantic-navigation-contract.yaml` | `3754a8d077315b79e7249a0c723f003fb5a83f1a7ec11c9e2c5ba7cfe613f151` |
| `research/07-integrated-validation-plan.yaml` | `ef19778d4c892c02a740aae0e5ccbbe56254fae90c5e003f088c602ebef02953` |
| `output/stage0-panorama-comments-refresh-20260811/manifest.json` | `c075853613d99bf9c9d4c0f36d09b056f378e3dbe31b38dd74389a542a35daee` |
| `output/stage0-panorama-comments-refresh-20260811/panorama/facts/columns.json` | `a7b783781e53ccce713d43af3a177e8790d8a37c0455a2a4f2e1ce54d490f4b7` |
| `output/stage0-panorama-comments-refresh-20260811/panorama/facts/objects.json` | `3b196bf1b02e6edeafa0b604406b879dceb27edc978d053dea891d6ad969889c` |
| `output/stage3-tradeflow-context-semantic-map-v1-20260812/context-enriched-field-semantic-map/manifest.json` | `98fb504349b7c0570b4317439f8698c7d9972a5459988c7fbe318b2137f1218b` |
| `output/stage5-tradeflow-semantic-navigation-v1-20260813/semantic-navigation-review/manifest.json` | `24dfa77c412d587cef3ad834ce9df0986d417b7dec922289fb7e8c5442cb9273` |

## 4. 可复算工程事实

### 4.1 严格 YAML 解析

使用继承 PyYAML `SafeLoader`、在构造 mapping 时检测重复键并立即报错的 loader 完整解析两份 `07` YAML。结果：

| 文件 | 解析 | 重复 mapping key |
|---|---:|---:|
| `07-integrated-semantic-navigation-contract.yaml` | PASS | 0 |
| `07-integrated-validation-plan.yaml` | PASS | 0 |

这是结构事实，不是 Gold PASS 或语义正确性。历史 `03-gold-set.yaml` 仍在第 65 行附近因自由文本产生 YAML scanner error；当前被引用的 `06-gold-set.yaml` 可严格解析，所以 `05` 的“先获得可执行 Gold 输入”已通过新文件而不是通过篡改历史文件实现。

### 4.2 声明 ID：329、335 与 337 的口径

按各文件 `metadata.declaration_id_keys` 逐树遍历：

| 口径 | contract | validation | 合计 | 唯一数 | 解释 |
|---|---:|---:|---:|---:|---|
| 已登记声明键 | 239 | 90 | 329 | 329 | 当前注册表能复算出的数字 |
| 漏登但实际是声明 | 1 | 5 | 6 | 6 | 1 个 check-set + 5 个 validation assertion |
| 实际声明 | 240 | 95 | 335 | 335 | 应纳入唯一性校验的声明总数 |
| `physical_column_id` 字段实例 | 0 | 2 | 2 | 2 | A03/B01 overlay 的物理 identity 引用，不是声明 |
| 所有实际 `id`/`*_id` 实例 | 240 | 97 | 337 | 337 | 335 个声明 + 2 个物理引用 |

漏项是：

- `qualifier_candidate_check_set_id`：`07-integrated-semantic-navigation-contract.yaml:367`，但未列入该文件第 28–60 行的声明键。
- 5 个 `assertion_id`：`07-integrated-validation-plan.yaml:223-237`，但未列入该文件第 17–28 行的声明键。

335 个实际声明值目前互不重复；问题是注册表没有覆盖它们，因而“按声明键唯一”会漏检六项。两条 `physical_column_id` 是冻结物理引用，不能为了得到 337 而冒充声明。

### 4.3 两份 06 Gold 哈希

| 文件 | 本轮重算 | 07 冻结值 | 结果 |
|---|---|---|---|
| `06-field-evidence-gold-set.yaml` | `db804025bc3d311912fd854cf34abcc83d3ec676ecbe90a3c0fb00d4d04e1f5c` | 同值（`07-integrated-validation-plan.yaml:53-55`） | MATCH |
| `06-gold-set.yaml` | `cbe07e7bc61bfd8f4167fc740805219f92c9122c7f0ab82d7deb8cec42828df0` | 同值（`07-integrated-validation-plan.yaml:56-58`） | MATCH |

### 4.4 Stage 0 raw 字符与空格

沿 `asset_id` 将 `columns.json` 与 `objects.json` 关联，并按 Stage 0 `column_id` 定位：

| Case | Stage 0 原值 | 长度 | 空格位置 | 07 overlay |
|---|---|---:|---|---|
| A03 `object_comment_raw` | `" CLN 认购流水"` | 9 | 第 1 字符 `U+0020`；`CLN` 后另有一个 `U+0020` | 正确 |
| B01 `column_comment_raw` | `"交易对手长名 "` | 7 | 最后一个字符 `U+0020` | 正确 |
| B01 `object_comment_raw` | `"交易- 交易指令"` | 8 | `-` 为 `U+002D`，其后为 `U+0020` | 正确 |

`06-gold-set.yaml` 中名为 raw 的三处值确实丢失了这些空格；`06-field-evidence-gold-set.yaml`、Stage 0 和 `07` overlay 保存正确。因此 overlay 是必要的，但不能反向声称历史 Gold raw 已正确。

### 4.5 Canonical 接口与 identity

用户指定的七个核心字段已经形成一个合成接口：

- `CanonicalPhysicalIdentity`：`schema_name`、`object_name`、`object_type`、`physical_column_id`（`07` contract 第 129–164 行）。
- 同一 Evidence Pack 内的 `CanonicalRawPhysicalFact`：`column_name_raw`、`column_comment_raw`、`object_comment_raw`（第 166–187 行），另带 `data_type_raw`、`nullable`、`ordinal_position`。

没有保留 `table_name`、`raw_column_name`、`column_id` 等平行 identity。`physical_column_id := columns.json.column_id` 是值不变、只改字段名的一次确定性 rename（第 146–150 行）；`asset_id` 只用于 columns→objects 关联且明确不是 canonical identity member（第 151–164 行）。这个接口在当前 TRADEFLOW 范围内可执行。

Stage 0 复算得到 TRADEFLOW `477` 个对象，全部为 `TABLE/SUCCESS`；`13,611` 条字段记录具有 `13,611` 个唯一 `column_id` 和 `13,611` 个唯一 Schema/Object/Column 三元组。因此当前 scoped Provider 的一字段一 Pack 主键成立。

### 4.6 币种枚举

`07` 的正式注册表、handoff 输入和 mapping selector 只使用：

- `ORIGINAL_CURRENCY`
- `LOCAL_CURRENCY`
- `UNDERLYING_CURRENCY`
- `SETTLEMENT_CURRENCY`

见 contract 第 332、762、924 行；C01/C02/F01 的正向 overlay 也统一为 `SETTLEMENT_CURRENCY`（validation plan 第 193–207 行）。正式输出枚举通过。

但冻结测试中的负向/历史断言没有全部适配：`06-field-evidence-gold-set.yaml:141` 仍写 `currency_basis=ORIGINAL`，`06-gold-set.yaml:348,352` 仍写 `UNDERLYING`。它们可以作为历史原文保留，却不能直接作为 Canonical validator 比较值；否则错误输出 `ORIGINAL_CURRENCY`/`UNDERLYING_CURRENCY` 可能不被短值断言捕获。详见缺陷 D-002。

### 4.7 关键计数与 grain

本轮从 Stage 0 JSON、Stage 3/5 Manifest 和 Stage 3 JSONL 重新计算：

| 数字 | 独立结果 | grain/分母 | 判定 |
|---:|---:|---|---|
| 477 | 477 | TRADEFLOW Stage 0 object identity；全部 TABLE/SUCCESS | 一致 |
| 13,611 | 13,611 | TRADEFLOW unique `column_id` | 一致 |
| 5,512 | 5,512 | Stage 3 source field workset | 一致；不是 Provider 总输入 |
| 1,375 | 1,375 | Stage 3 run-scoped business concept candidate | 一致；不是业务概念总数 |
| 5,347 | 5,347 | Stage 3 semantic observation rows | 一致 |
| 1,559 | 1,559 | Stage 3 attribute expression candidates | 一致 |
| 1,326 | 1,326 | Stage 5 unattached source candidates | 一致；不是 Unknown |
| 618 | 618 | `semantic_hypotheses` 中 `INSUFFICIENT_EVIDENCE` rows | 一致 |
| 71 | 71 | 66 个 conflict hypothesis 中的 typed conflict items | 一致；66 与 71 分母不同 |
| 6 | 6 | 首批 Reader identity，发布数 0 | 一致 |

Provider 源契约还包含 77 个唯一规则 ID，独立计数为 `GEN=69`、`TF=8`。

## 5. 05 REWORK 要求追踪矩阵

| 05 最小返工要求 | 07 状态 | 本轮裁定 |
|---|---|---|
| 1. 使 27-case Gold 可执行 | `06-gold-set.yaml` 可严格解析；27 案例被 hash 冻结；当前仍 `PENDING_RERUN` | 设计输入已满足；运行未完成，不能称 PASS |
| 2. 禁止 SHORT/LONG 名称长度发布方向 | P1 guard、CXL-001、decisive Gate、Reader blockers 均明确禁止 | 设计层满足；待实际规则执行 |
| 3. 拆分 Order/Trade | 两个 concept/Reader identity、定义、证据和 Gate 均分开 | 设计层满足；Trade 直接正例缺失且已正确阻塞 |
| 4. 拆分 SOURCE/TARGET 语义 | mapping context 只形成 P2 candidate；formal `flow_side` 为 TRADEFLOW-only 且待业务裁定 | 边界受控；D01/D02 不得在未裁定时发布 |
| 5. 泛化词降级 | 裸状态/类型/金额/币种/日期不能形成 P3/Reader；未绑定进入 UNBOUND/DEFERRED | 方向满足；开放观察闭集问题见 D-003 |
| 6. 收敛轴模型 | 8 个 field attributes、12 个 qualifiers；宽 DIRECTION/CONFIGURATION 不再是正式轴 | 静态路由满足；行为覆盖不足见 D-004 |
| 7. 重画顶层关系 | `universal_sequence=false`，活动可重复/重入，运营/技术为横切面 | 大体满足；Cash Flow/obligation 仍混层，见 D-007 |
| 8. 入口证据化 | 10 个入口均为 `CONFIGURATION_SEED/NOT_PUBLISHED/evidence_id=null`；31 legacy seeds 不静默迁移 | 满足，且开放问题有 owner/blocker |
| 9. 重算并命名计数 | `07` 分开 physical column、workset、candidate、expression、Reader、conflict、Unknown grain | 满足；本轮复算与 contract 一致 |
| 10. 第二 Schema 另行授权 | D-010 与 step 12 都保持 `DEFERRED`，禁止 GLOBAL_VALIDATED | 满足；仍需注意 D-012 的跨范围 identity 反例 |

因此 `05 REWORK` 的主方向已被吸收，但不是全部关闭：新的 contract/Gate 缺陷和两处业务定义问题要求实现前返工。

## 6. Agent A/B 接口整合审查

### 6.1 P0→P5 单向性

| 层 | 可消费/输出 | 攻击结果 |
|---|---|---|
| P0 Physical Fact | 冻结 Stage 0 物理事实 | PASS；raw 与 identity 不被语义覆盖 |
| P1 Prepared Evidence | 16-block Pack、observation、Conflict、unresolved、provenance | PASS WITH GAP；禁止正式概念/qualifier/Reader，但新观察缺开放候选通道 |
| P2 Semantic Candidate | 完整 Pack + candidate registry + Gold 约束 | PASS WITH GAP；只允许五种候选状态，但 candidate grain/唯一键未定义 |
| P3 Semantic Decision | 接受/拒绝/延后 immutable P2 candidate | PASS WITH GAP；明确禁止反馈 P2，但 decision record/version uniqueness 未定义 |
| P4 Reader Candidate | 已接受 P3 + 可见 blockers | PASS WITH GAP；要求逐表达状态，但 Reader expression 唯一 grain 未机器化 |
| P5 Projection | 冻结 P0–P4 引用 | PASS；明确不是事实源且不得 canonical write-back |

没有发现 P3 反向补造 P2 的声明路径；P4/P5 也被明确禁止作为独立事实源。Conflict、counterevidence、unresolved、EXCLUDED、NOT_EVALUABLE 均有显示要求。不过只有定义状态还不够，D-005 与 D-009 会使重复记录或空 Gate 在实现中绕过这些边界。

### 6.2 16 个 Provider 区块路由

独立对比 `field_evidence_provider.required_output_blocks` 与 `semantic_handoff.input_block_routes`：两边均为 16，集合差为 `missing=[]`、`extra=[]`。物理 identity、raw、处置、规范化、token、保护短语、缩写、generic attributes、technical、context、qualifier observations、conflicts、unresolved、rule IDs、provenance、evidence status 均有且只有一个声明的首要路由角色。

Agent B Evidence Pack 是 Agent A 字段层唯一输入（design 第 21 行、contract 第 272–297 行）。provenance 同时要求 columns/objects 两种源角色，`asset_id` 只做对象关联；同名跨表字段通过 `physical_column_id` 保持实例隔离。

### 6.3 越级与技术泄漏攻击

- token/表名/缩写不能单独产生正式概念、属性、qualifier 或 Reader（contract 第 286–289、379–389、410–414 行）。
- 技术 observation 先进入 `TECHNICAL_CANDIDATE`；要产生独立业务候选必须有非技术分类推导的业务证据（第 404–409 行）。
- D02 `SOURCE_CTPTY_ID` 同时有 LINEAGE_METADATA candidate 和业务映射含义。`07` 的 CXL-003、flow-side deferred issue 和 Counterparty blocker 已阻止它从 P1 直接发布；因此当前是受控开放问题，不单列缺陷。实现必须证明独立 input/output responsibility，不能把 FEP-006 的技术分类本身当业务证据。
- `PREPARED/EXCLUDED/DEFERRED` 被明确限定为 P1 处置，不等于 P3/P4/P5 状态；EXCLUDED 仍保留完整 anchor/provenance。

## 7. 业务骨架与多入口模型审查

| 结构 | 数量 | 裁定 |
|---|---:|---|
| 旅程入口 | 4 | 可作为进入模型的研究入口；不是四个串行阶段，也不自带 Evidence |
| 合同存续包络 | 1 | `serial_stage=false`，正确表达形成后到终止/关闭期间的状态和义务包络 |
| 可重复业务活动 | 7 | 明确 `ZERO_OR_MANY`，可分支、重叠、重入；不再是单向六阶段 |
| 横切支撑面 | 3 | 市场/配置、运营/报表、技术/审计均未被当生命周期阶段 |
| 业务区域 | 13 | contract 禁止原样铺成 13 个一级菜单；作为 contextual research classification 可保留 |

合同存续域、事件、活动和业务区域在结构上已经分层：一个 envelope 包含期间，活动可重复，区域用于页面 contextual projection。多入口必须解析到一个 Reader identity，入口只保留为 `CONFIGURATION_SEED`，不会复制 identity。

主要剩余问题有两项：

1. Position 的稳定定义把持有记录与“数量状态”并列，重新打开了 Position identity 与 MEASURE 的混同，见 D-006。
2. `activity:cashflow-obligation` 把现金流与结算义务并在一个活动名中，而 `concept:cash-flow` 又定义为“计划或实际收付义务记录”，与单独存在的 `concept:settlement-obligation` 冲突，见 D-007。

清算、支付/转移/交割、结算结果已经分成不同活动；`concept:clearing`、`concept:delivery`、`concept:payment-transfer`、`concept:settlement-result` 也有不同类型和排除边界。除 Cash Flow/obligation 外，没有发现将横切支撑面重新塞回生命周期或把 13 个区域强制变成 13 个菜单的路径。

## 8. 六 Reader 逐项审查

| Reader | 稳定 identity/定义 | 正例、歧义与名称反例 | 证据/边界 | 当前裁定 |
|---|---|---|---|---|
| Counterparty | `reader:counterparty`；Party-in-relation，而非 Party master | A01/A02/A04/A05/B01 为 Counterparty 表达兼名称方向反例；A03 是 Customer 歧义；D01/D02 是 mapping 歧义；G01 是 Seller side | 允许 IDENTIFIER/TEXT/RELATION/STATE/TIME；party/trade side 需对象语境；flow_side 另需 P3 | 候选边界可用；Customer、mapping role 未决时正确阻塞 |
| Order | `reader:order`；拟执行意图/指令，可撤销、拒绝或未成交 | H01 是直接 Order identifier；G02/CXL-007 用于阻止 Trade 继承 | 独立 Order anchor、状态/时间/责任；表名不能投票 | 可用候选；不能与 Trade 合并 |
| Trade | `reader:trade`；已执行并形成经济事实的交易记录 | CXL-011/FEP-016 只能暴露 anchor candidate；现有 Suite B 无直接 Trade 正例 | 要求 Trade 专属 identity/执行事实与 Order/Contract 区分 | 缺口被准确记录并阻塞页面，不是伪 PASS |
| Notional | `reader:notional`；合同计算基准度量 | C01/C02 正例；F01 名称/注释冲突；K01 初始时点；C03 防止 Ratio 误挂 Margin | MEASURE/CURRENCY/TIME/TEXT，各 qualifier 单独 provenance | 候选边界可用；币种测试适配缺陷见 D-002 |
| Position | `reader:position`；目标应是持有记录/状态 | CXL-012 证明 quantity token 不足；现有 Suite B 无直接 Position 正例；Risk Exposure 为反例 | 应要求 Position/holding responsibility anchor，数量、余额、方向、时点为表达 | publication blocker 正确，但稳定定义本身仍混入“数量状态”，见 D-006 |
| Margin | `reader:margin`；履约风险保障机制下的金额/状态候选 | M01 暴露 direction 未决；C03 阻止 ratio 因表语境进入 Margin | 金额、余额、阈值、比例、参数、方向均需独立表达状态 | 开放问题有 owner/blocker；不得把所有表达压成一项 |

六个 Reader 均给出稳定 ID、排除边界、允许字段属性/qualifier、入口、最低 P0 证据、Gold/反例和 publication blockers。P4 还明确要求每个表达独立计算支持状态，CXL-010 禁止一个表达使同 Reader 其他表达继承 `SUPPORTED`。

重点攻击结果：

- Customer 没有被正式等同 Counterparty；A03 和 `concept:customer` 均保持 DEFERRED/blocked。
- SHORT_NAME/LONG_NAME 没有通往 position_side 的裸 token 路径；名称只可产生 DESCRIPTIVE_TEXT candidate。
- SOURCE/TARGET 没有直达 formal `flow_side`；只在明确 mapping responsibility 下形成 TRADEFLOW-only P2 candidate。
- Order/Trade identity、定义和最低证据已分离；Trade 正例缺失未被 H01/CXL-011 偷换。
- Position View/Holding/Risk Exposure 没有默认继承；但 Position 定义需返工。
- Notional 排除了 generic amount、Margin、Position、Valuation、Payment Amount。
- Margin 的金额/余额/阈值/比例/参数/方向尚未裁定，但对应输出已被明确阻塞，未偷选答案。

## 9. 字段属性与 qualifier 审查

### 9.1 静态可达性

独立集合对账结果：

- 8 个字段属性：6 个直接语义 target 为 `IDENTIFIER`、`DESCRIPTIVE_TEXT`、`BUSINESS_OBJECT_STATE`、`MEASURE`、`CURRENCY`、`TIME`；2 个复合 target 为 `PARTY_RELATIONSHIP`、`AUDIT`。`missing=[]`、`extra=[]`。
- 12 个 qualifier：5 个 Provider direct observation 维度为 `position_side`、`trade_side`、`cashflow_direction`、`variability`、`currency_basis`；7 个复合维度为 `observation_time_role`、`party_relationship_role`、`aggregation_state`、`availability_condition`、`estimation_status`、`measure_basis`、`flow_side`。`missing=[]`、`extra=[]`。

`PARTY_RELATIONSHIP` 要求 bounded Party-relation object + explicit role evidence + independent context；`AUDIT` 要求 Provider rule/Suite A/责任证据并只进入 technical projection。qualifier formation 还检查对象适用性、独立 comment/context、维度兼容和 Conflict。裸 RATE、TIME、SOURCE、TARGET、SHORT、LONG 都不能直接成为 formal semantic。

### 9.2 不能接受的两处缺口

第一，`undefined_observation_names_allowed: false` 把当前 Provider/Canonical 名称表变成闭集，却没有定义“未注册但可定位的新观察”怎样保留为开放候选。raw/unresolved 可以保留证据不足，却不能表达一个尚未注册、未来可能成立的维度。这违反项目要求的开放 taxonomy 边界，见 D-003。

第二，“全部可达”目前主要由 contract 布尔断言和 Suite C 的静态 assertion 表达。Suite B 的 formal qualifier 期望只明确覆盖 7 个维度；`cashflow_direction` 仅为未决案例，`party_relationship_role`、`aggregation_state`、`availability_condition`、`estimation_status` 没有可执行的正/反/歧义行为样本。存在 route 不等于 route 不会越级，见 D-004。

不适用、未绑定、冲突和延后在 P2 五值中被区分；P1 disposition、P2 resolution、governance state、publication state 也被概念上分开。但 candidate、decision、expression 的唯一 grain 和单一当前状态没有 schema 约束，见 D-005。

## 10. 三套 Gold 与 Gate 审查

| Suite | 数量/范围 | 当前状态 | 本轮核验 | 关键结论 |
|---|---|---|---|---|
| A | 23，P0→P1 | `SOURCE_ANCHOR_VERIFIED / RULE_EXECUTION_NOT_PERFORMED` | 23/23 source anchors 均定位 Stage 0；raw/object comments 与字段证据 Gold 一致 | source anchor 没有冒充 rule PASS；短币种负向断言需 Canonical adapter |
| B | 27，P2→P4；24 physical + E02–E04 NOT_EVALUABLE | `PENDING_RERUN` | 24/24 物理字段均定位；A03/B01 overlay 与 Stage 0 一致；06 文件 hash 匹配 | 只覆盖 4/6 Reader identity；Trade/Position direct positive 缺口已正确阻塞 |
| C | 12，P1→P2→P3→P4 | `NOT_EXECUTED` | 覆盖名称方向、SOURCE/TARGET、Order/Trade、同名 identity、技术隔离、Conflict、EXCLUDED、表达状态、Trade/Position 缺口 | 接口反例方向好；无法替代全 8/12 行为覆盖 |

`source_verification`、`rule_execution`、`semantic_adjudication`、`page_projection` 被分开记录；YAML parse 明确只是 structural。`historical_not_evaluable=4` 被标为 `05` 历史 counterevidence，而当前 Suite B whitelist 是 E02–E04 三项，这两个口径没有被混写。

历史 06 Gold 受 SHA-256 保护，直接改写会触发 stop，因此不能靠修改源文件让失败消失。但 07 的 overlay 自身没有独立 ID/version/hash/authority record，且执行 Gate 没有结果 schema 证明 exact case set、前驱 PASS 或 NOT_EVALUABLE whitelist。当前文案包含反空通过意图，却仍可被宽松实现绕过，见 D-009 与 D-011。

Trade/Position 的正例缺失不是本轮新增缺陷：`reader-positive-gap`、Reader-specific blocker、page generation gate 和 deferred owner 都明确阻止页面。只有在未来 validator 把 CXL-011/012 错当 direct positive 时才会空通过；D-009 的机器化要求必须禁止这种替代。

## 11. 页面目标与真实用户旅程审查

页面 contract 明确只有一个页面，布局为三栏加底部治理队列：

```text
业务拓扑上下文
  -> 唯一 Reader identity
  -> 独立属性表达矩阵 / qualifier filters
  -> physicalGroups / 具体物理字段实例
  -> Schema / 对象 / 对象注释 / 字段注释 / 数据类型
  -> 对象详情
  -> Evidence / Conflict / unresolved / governance queue
```

左栏只显示当前 topology context 相关区域/概念并禁止 13 个固定一级菜单；中栏有定义、排除、表达矩阵、字段/表计数、逐表达 evidence/publication status；右栏沿用 exact `column_name_raw` 物理分组但 identity 仍是 `physical_column_id`，并要求 concrete object-detail entry。`1,326` 被明确解释为 unpublished source candidates 而非 Unknown，所有主要数字都有 grain/分母。生成物被标为 Candidate，不能声称发布/验收。

当前状态仍是 `NOT_GENERATED/NOT_EXECUTED`，因此本轮不能审阅真实页面或点击结果。validation plan 的 5 条旅程只验证一个泛化入口、一个多入口 identity、Conflict、EXCLUDED 和技术隔离；没有六 Reader × 正例/边界/歧义的逐项矩阵，也没有每个 Reader 的 deep-link、对象详情、返回后上下文保持。一个 Reader 的链接或表达状态损坏仍可能被其他泛化旅程遮蔽，见 D-010。

## 12. 实施顺序与复审时点审查

`07` 的 12 步业务顺序基本合理：Provider→全量 Pack→Suite A→handoff→P3/P4→Suite B/C→修错→页面→点击→独立复审→用户验收→第二 Schema。第二 Schema 明确需要 D-010、独立 case pack/Manifest/反例/审阅，当前不得推进。

但当前顺序只包含实现后复审：design 第 385–399 行明确要求实现、三套验证、页面和点击完成后才由新 Agent 复审；step 10 也位于页面之后。这与项目 `AGENTS.md:43-54` 的实现前 surrogate review、以及本任务要求的“两次复审”不一致。本文件就是本轮实现前复审，但 `07` contract 仍需把它固化为 step 0/precondition；不能靠这次会话外记忆维持，见 D-008。

此外，step 的 sequence number 和 prose Gate 没有 `GateResult`、前驱结果引用、输入 hash、exact expected case set、状态转移或 non-empty proof。`steps 1 through 7 are complete` 不是可验证 token；`NOT_EVALUABLE` 也没有机器白名单绑定。见 D-009。

安全实施边界：

- 可开始 step 1–2：只读 Stage 0、无业务行、无 LLM、无外发、P1 只产生 Evidence/observation/Conflict/unresolved；当前 TRADEFLOW `physical_column_id` 唯一。
- step 3 可以编写 runner/test，但在 D-002、D-009、D-011 修复前不得声称 Suite A Gate PASS。
- step 4 及以后必须等待 D-001–D-005、D-008–D-011 的 contract/validation 返工与新的实现前复审。
- step 5/page 还必须等待 D-006、D-007 和现有 Customer/Counterparty、Position、Margin、flow_side、Trade/Position direct Gold 等业务 blocker。
- 外部模型与数据外发继续受 `docs/spec/12-open-decisions.md:35-42` 和 `AGENTS.md:20,31` 限制；本设计没有任何模型阶段授权。

## 13. 反例和失败尝试

| 攻击 | 证据/方法 | 结果 |
|---|---|---|
| YAML PASS 是否掩盖结构错误 | duplicate-key strict loader + ID 全树遍历 | 成功证伪：YAML 无重复键，但 declaration registry 漏 6 项 |
| 335 是否只是复制来的数字 | 分别计算 239、90、1、5、2 | 独立得到 329 registered、335 declarations、337 all id-like instances |
| 06 Gold hash 是否漂移 | 对两个文件重新 SHA-256 | 未证伪；均与 07 冻结值一致 |
| A03/B01 raw 是否被 trim | 直接读取 Stage 0 字符与 code point 位置 | 成功发现 06 semantic Gold trim；07 overlay 正确保留 |
| Customer 是否等同 Counterparty | `01-domain-skeleton.md:148-153`、`02-field-shapes.json` 独立 corpus/concept、A03 | 等同被证伪；07 保持 DEFERRED/blocked，边界正确 |
| SHORT/LONG 是否仍能直达方向 | 追踪 P1 guard、mapping、CXL-001、Reader Gate | 未找到直达路径；当前设计通过 |
| SOURCE/TARGET 是否仍直达 flow_side | 追踪 FEP-006、D02、CXL-003、composite mapping | 未找到直达 formal 路径；需 P3 mapping responsibility，当前受控 |
| Order/Trade 是否仍合并 | 对比 Reader ID、定义、证据、H01/CXL-007 | 未发现 identity 合并；Trade direct positive 仍缺且被阻塞 |
| quantity 是否能单独成为 Position | 对比 `01` 的 object/measure 边界、CXL-012 与稳定定义 | Gate 禁止，但定义“数量状态”重新混层；反例成立 |
| 清算/支付/交割/结算是否混同 | 对比 topology、concept type/excludes、原始骨架 | 大部已拆；Cash Flow/settlement obligation 仍自相矛盾 |
| 8/12 可达是否等于行为安全 | 对比 30 mappings、Suite B qualifier expectation、12 CXL cases | 成功证伪；5 个 qualifier 无 formal 行为样本，static assertion 可空过 |
| NOT_EVALUABLE 是否只限 E02–E04 | 对比 whitelist、layer prerequisite、Gate completion 文案 | 人工意图明确；缺机器状态/白名单 binding，宽松 runner 仍可重标 |
| 同名跨表 identity 是否会合并 | Stage 0 复算 + FEP-001/FEP-023 | TRADEFLOW 未合并，CXL-008 可验证；当前通过 |
| `physical_column_id` 是否全 Panorama 都唯一 | 对全 Stage 0 `column_id` 计数 | 反例成立：TRADEFLOW 外 TITANS_DM 有 17 个 collision group、32 个额外行；当前 scoped TF 无 collision |
| 页面是否已支持真实 Reader 旅程 | 检查 status 与 journey matrix | 无法证明；页面未生成、旅程未执行且未逐 Reader |

## 14. 缺陷清单

### D-001 — 声明 ID 注册表漏六项

- **defect_id**：`D-001`
- **severity**：`MAJOR`
- **精确文件和行号**：`07-integrated-semantic-navigation-contract.yaml:28-60,367`；`07-integrated-validation-plan.yaml:17-28,223-237`
- **事实**：按登记键只能得到 329 个唯一声明；`qualifier_candidate_check_set_id` 和 5 个 `assertion_id` 是真实声明却未登记。实际声明为 335，另有 2 个 physical identity 引用。
- **风险**：唯一性/引用完整性 validator 会漏检 check-set/assertion 的重复或漂移；不同实现可能各自宣称 329 或 335 正确。
- **最小修复**：把两种键加入对应 `declaration_id_keys`，重算并冻结 `declaration_count=335`、`unique_declaration_count=335`；保留 `physical_column_id` 为 reference 分类，不计声明。
- **阻塞范围**：step 3 Gate 结果 schema、step 4 handoff 及所有后续 validation/review bundle。

### D-002 — Canonical 币种适配未覆盖负向/历史断言

- **defect_id**：`D-002`
- **severity**：`MAJOR`
- **精确文件和行号**：`06-field-evidence-gold-set.yaml:131-142`；`06-gold-set.yaml:309,346-352`；`07-integrated-validation-plan.yaml:170-207`；`07-integrated-semantic-navigation-contract.yaml:332,762,920-929`
- **事实**：正式 `07` 枚举和 C01/C02/F01 正向 overlay 已使用完整值，但 FEP-009 的 forbidden `ORIGINAL`、C02 的 forbidden/legacy `UNDERLYING` 未被 Canonical adapter 转成 `*_CURRENCY`。
- **风险**：validator 若作字符串比较，错误的 `ORIGINAL_CURRENCY` 或 `UNDERLYING_CURRENCY` 输出不会命中短值 forbidden expectation，形成 vacuous pass；若直接接受短值，又污染正式 qualifier value。
- **最小修复**：冻结历史文本不变；在 versioned overlay 中分别记录 `historical_value` 与 `canonical_comparison_value`，覆盖所有正向、负向和 legacy expectation；加入 full-enum-only schema assertion。
- **阻塞范围**：Suite A FEP-009、Suite B C02 及 step 3 PASS 声明。

### D-003 — observation vocabulary 被静默写成闭集

- **defect_id**：`D-003`
- **severity**：`MAJOR`
- **精确文件和行号**：`AGENTS.md:43-52`；`07-integrated-semantic-navigation-contract.yaml:298-355,1006-1018`
- **事实**：contract 声明 `undefined_observation_names_allowed: false`，却没有“未注册 observation/qualifier dimension 仍按 raw span + provenance 保留”的开放世界记录类型。`unresolved_items` 只表达下一证据不足，不足以表达新类别候选。
- **风险**：新业务形态只能被强塞进 8/12 现有类或在 schema 校验前丢弃；研究 seed 被误当成封闭本体，Unknown/counterevidence 不完整。
- **最小修复**：区分“formal P3 registry closed”与“P1/P2 discovery open”；新增 `UNREGISTERED_CANDIDATE`/等价开放记录，要求 raw span、provenance、suggested dimension、DEFERRED reason，禁止其进入 P3/Reader；增加一个新维度反例。
- **阻塞范围**：step 4 handoff schema 与所有 P2 candidate generation。

### D-004 — 8/12 可达性是静态声明，行为覆盖不闭合

- **defect_id**：`D-004`
- **severity**：`MAJOR`
- **精确文件和行号**：`07-integrated-semantic-navigation-contract.yaml:797-1018`；`07-integrated-validation-plan.yaml:215-237,238-337`
- **事实**：8 个 field attributes 和 12 个 qualifier 均有 syntactic route；但 Suite C 的 `canonical-semantic-reachability` 只是静态 assertion。Suite B formal qualifier expectations 只覆盖 7 个维度，`cashflow_direction` 仅未决，`party_relationship_role`、`aggregation_state`、`availability_condition`、`estimation_status` 无正/反/歧义行为样本。
- **风险**：route 存在即可通过，却不能证明裸 token 不越级、对象适用性被检查、Conflict/UNBOUND/NOT_APPLICABLE 正确分流。
- **最小修复**：为 8 个属性和 12 个 qualifier 建 route matrix；每个维度至少覆盖 promotable、insufficient/UNBOUND、misleading/conflict 或明确 NOT_APPLICABLE 的行为断言；未执行或零实例不得满足 reachability Gate。
- **阻塞范围**：step 4–6、所有 formal qualifier/field attribute promotion。

### D-005 — P2/P3/P4 缺少可执行的唯一 grain 与幂等键

- **defect_id**：`D-005`
- **severity**：`MAJOR`
- **精确文件和行号**：`07-integrated-semantic-navigation-contract.yaml:272-355,416-454,1048-1177,1295-1324`
- **事实**：P2 candidate 要求 `candidate_id`，P3/P4 要求 decision/Reader/expression 语义，但 declaration registry、record schema 和 invariants 未定义 candidate ID 生成、decision version、one-active-state-per-grain 或 Reader expression 唯一键。`ZERO_OR_MORE_MUTUALLY_VISIBLE_CANDIDATES` 也不等于互斥状态约束。
- **风险**：同一 run 可产生重复候选、重复 P3 决定或重复 Reader expression；计数、支持状态和页面 identity 可以同时不一致而仍通过字段存在性检查。
- **最小修复**：声明并校验 candidate/decision/expression IDs；至少冻结 `(run_id, physical_column_id, candidate_type, candidate_value_ref, evidence_hash)` 幂等键、one P3 decision per candidate version、one expression per Reader+expression key、one active state per grain；重复即 FAIL。
- **阻塞范围**：step 4 handoff、step 5 P3/P4、计数与页面生成。

### D-006 — Position 稳定定义混合对象 identity 与数量度量

- **defect_id**：`D-006`
- **severity**：`MAJOR`
- **精确文件和行号**：`01-domain-skeleton.md:264-272,320-336`；`02-field-shapes.json:11481-11616`；`07-integrated-semantic-navigation-contract.yaml:523-527,635-645`；`07-integrated-semantic-navigation-design.md:230-241`
- **事实**：原始骨架和字段形态把 Position identity/record 与 Position quantity 分成不同 concept；`07` 却将 Position 定义为“持有记录或数量状态”。CXL-012 同时又规定 quantity observation 不能单独确认 Position。
- **风险**：实现者可用“数量状态”解释绕过 ownership anchor，把 generic quantity/balance 投入 Position Reader；Position、Position View 与 Risk Exposure 边界重新漂移。
- **最小修复**：把 Position 定义限定为某主体/账户/组合在时点与范围下的持有状态记录；数量、余额、方向、时点只作为该 identity 下的独立表达。保留 CXL-012，并新增 Position 直接正例与 quantity-only 反例。
- **阻塞范围**：Position 的 step 5 P3/P4、direct-positive Gold、Reader page generation。

### D-007 — Cash Flow 与 settlement obligation 在骨架中仍混层

- **defect_id**：`D-007`
- **severity**：`MAJOR`
- **精确文件和行号**：`01-domain-skeleton.md:87-94,190-194,284-292`；`07-integrated-semantic-navigation-contract.yaml:474-495,538-542,677-715`
- **事实**：topology 使用合并节点 `cashflow-obligation`；`concept:cash-flow` 定义为“计划或实际收付义务记录”，但同一 registry 又单列 `concept:settlement-obligation`，并声称 obligation、cash flow、fulfillment、delivery、result 必须不同。
- **风险**：左栏活动和后续 concept/Reader 可把应收应付义务、计划现金流、实际支付/转移事件及结果折成同一 identity，重现 `05` 的清算结算混层。
- **最小修复**：明确四层：obligation（应收/应付责任）、cash-flow schedule/item（计算/计划表达）、payment/transfer/delivery event（履行动作）、settlement result（结果状态）；重命名合并 activity 或显式声明它只是 group，不是 concept identity，并增加一组边界反例。
- **阻塞范围**：相关 topology/concept contract、未来 Cash Flow/settlement Reader 或页面导航；不阻塞中性 P0/P1。

### D-008 — 只定义实现后复审，缺少实现前 checkpoint

- **defect_id**：`D-008`
- **severity**：`MAJOR`
- **精确文件和行号**：`AGENTS.md:41-56`；`07-integrated-semantic-navigation-design.md:343-360,385-399`；`07-integrated-validation-plan.yaml:547-574`
- **事实**：12 步只有页面/点击后的 step 10 独立复审；design 还写明实现和页面完成后“才”复审，没有冻结 contract/Gold/Gate 的 pre-implementation review precondition。
- **风险**：在当前正式结论仍为 `05 REWORK` 时即可先实现 P2–P5，随后用已实现结构反向固化语义；未来也无法区分设计审阅与真实页面审阅。
- **最小修复**：增加 step 0：冻结 07 contract/validation/hash 后进行实现前独立复审；只有 `ACCEPT` 或明确允许的有界 `REWORK` 范围可进入相应步骤。保留 step 10 作为实现后页面/Gold/点击复审，两者使用不同 artifact/disposition 记录。
- **阻塞范围**：step 3 PASS、step 4 及以后；本报告仅允许 step 1–2。

### D-009 — Gate 顺序、非空性与 NOT_EVALUABLE 白名单不可机器复核

- **defect_id**：`D-009`
- **severity**：`MAJOR`
- **精确文件和行号**：`07-integrated-semantic-navigation-contract.yaml:1317-1431`；`07-integrated-validation-plan.yaml:402-422,456-510`
- **事实**：步骤有 sequence 和 prose Gate，但没有 GateResult schema、predecessor result/hash、exact expected case set、单调状态转移或 non-empty proof。layer prerequisite 缺失时只说 case 不能执行；common wording 又允许“明确 NOT_EVALUABLE”。反空通过 stop 存在但无法从记录结构证明已触发。
- **风险**：缺 P1/handoff 的案例可被批量重标 NOT_EVALUABLE；CXL-011/012 可被错当 Trade/Position positive；未执行/空集合仍可能让 `steps complete` 成真，甚至先生成页面后才在独立复审发现。
- **最小修复**：为每一步定义 versioned GateResult：前驱 PASS/hash、输入 manifest、expected/observed case IDs、状态分布、E02–E04 唯一 NOT_EVALUABLE 白名单、direct-positive case type、zero-omission/non-empty assertion；越序、缺失或重标立即 STOP，不能只在 independent review 前检查。
- **阻塞范围**：step 3 Gate 声明、step 4–10、页面生成和独立复审。

### D-010 — 页面旅程不是逐 Reader 的真实可达性验证

- **defect_id**：`D-010`
- **severity**：`MAJOR`
- **精确文件和行号**：`07-integrated-semantic-navigation-contract.yaml:1295-1330`；`07-integrated-validation-plan.yaml:512-545,561-568`
- **事实**：页面 contract 正确，但 5 条 journey 是泛化路径；没有六 Reader 各自的 direct positive、boundary/misleading、ambiguous/conflict、deep-link、object-detail、return-state 测试矩阵。
- **风险**：一个 Reader 的表达、链接或返回上下文损坏可被其他 Reader 的通用 journey 掩盖；“能点到聚合节点”会冒充用户可到达具体记录。
- **最小修复**：建立六 Reader journey matrix；每个 Reader 至少跑 direct positive、边界/误导、阻塞项可见、具体字段与对象详情、deep-link、返回后上下文保持；Trade/Position 无 direct positive 时整页 Gate 必须停。
- **阻塞范围**：step 9–10、reader delivery request。

### D-011 — review/source/overlay 冻结清单不完整

- **defect_id**：`D-011`
- **severity**：`MINOR`
- **精确文件和行号**：`07-integrated-semantic-navigation-contract.yaml:62-122`；`07-integrated-validation-plan.yaml:30-59,170-207`
- **事实**：runtime facts 有 hash，validation 只冻结两个 06 Gold；Agent A/B proposal/skeleton/contract、`05` review、current baseline 只有 path，五个 overlay 也没有独立 ID/version/hash/authority。
- **风险**：review 与实现之间可以发生来源或 overlay drift；即使历史 Gold 未变，修改 overlay 也可能改变预期而不触发 source hash mismatch。
- **最小修复**：为本次实现/复审建立一个 allowlisted source manifest，记录所有输入 path、content hash、role；每个 overlay 有 ID、版本、来源 case、旧/新值、authority、content hash，并纳入 run Gate。
- **阻塞范围**：step 3 可复算 PASS、step 8–10 review bundle；不阻塞 Provider 代码编写。

### D-012 — `physical_column_id` 唯一性 invariant 未明确限定到 scoped Profile

- **defect_id**：`D-012`
- **severity**：`MINOR`
- **精确文件和行号**：`07-integrated-semantic-navigation-contract.yaml:129-164,189-204`；`07-integrated-semantic-navigation-design.md:50-56,362-367`
- **事实**：contract 写“frozen input 中一个 physical_column_id 恰好一个实例”。当前 TRADEFLOW 13,611 条确实唯一；但全 Stage 0 有 17 个 TITANS_DM collision group、32 个额外重复行，来自含替换字符的 VIEW column names。全局 invariant 因而不成立。
- **风险**：未来第二 Schema 或 Panorama 复用时会把 scoped 成功误宣传为通用 identity 保证，并可能合并原始编码失败字段。
- **最小修复**：把 invariant 明确限定为 `(run_id, profile/schema scope)`；每个新 Profile 先执行 collision scan，保留编码/解析失败；若 `column_id` 非唯一，使用可追溯的 asset+ordinal/source locator 复合 surrogate，不静默改名或合并。
- **阻塞范围**：第二 Schema/跨 Schema 与 Panorama-wide Provider；不阻塞当前 TRADEFLOW step 1–2。

## 15. 最小返工要求

不需要推翻 P0–P5、六 Reader 或三栏页面。最小返工按 checkpoint 分组：

1. **在 step 3 Gate 前**：修 D-001、D-002、D-009、D-011；严格登记 335 个声明；统一所有币种正/负/历史 comparison value；建立 exact-case GateResult 和完整 source/overlay manifest。
2. **在 step 4 前**：修 D-003、D-004、D-005；保留开放观察候选；把 8/12 route matrix 变成非空行为验证；定义 candidate/decision/expression grain、ID 和幂等/状态唯一约束。
3. **在 step 5 前**：修 D-006、D-007；重写 Position identity 与 quantity expression 边界；拆清 obligation、cash-flow item、payment/transfer/delivery event、settlement result。Customer/Counterparty、Margin、formal flow_side 继续按现有 owner/blocker 取证，不得由实现者默认关闭。
4. **在任何页面生成前**：补经业务裁定的 Trade 与 Position direct positive；不得用 CXL-011/012 或 token candidate 替代。所有六 Reader 均需 direct positive + boundary/misleading case。
5. **在实现后独立复审前**：修 D-010，执行逐 Reader journey matrix，冻结页面 bundle/Manifest；复审页面而不是只看 schema/count。
6. **在第二 Schema 前**：修 D-012，并继续遵守 D-010 用户授权、独立 case pack 和禁止规模化声明的边界。

当前可以安全推进到实施顺序第 2 步，前提是：只读 metadata-only；只处理 TITANS_TRADEFLOW scoped 13,611 字段；`model_calls=0`、`business_rows_read=false`、`egress=false`；P1 输出不含正式业务语义；不对 step 3 或更后 Gate 作 PASS 声明。

## 16. 最终 disposition

**REWORK**

决定性理由：整体方向可保留，且没有发现需要推翻 P0–P5 或六 Reader 结构的系统性错误；但当前 contract/validation 仍有 10 个会把语义实现或 Gate 带偏的 MAJOR 缺陷，不能接受为完整实现基线。

允许开始实现：**是，但仅允许推进到第 2 步的中性 P0/P1 Evidence Pack；第 3 步不得宣称 PASS，第 4 步及以后全部阻塞。**

本 disposition 不是业务验收、Reader 发布、第二 Schema 授权或规模化授权。
