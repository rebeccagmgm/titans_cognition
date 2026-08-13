## Surrogate Bottom-Data Review

**Disposition:** `ACCEPT`（仅接受固定 TRADEFLOW 输入下的底层发布边界；不代表用户业务验收）

**Boundary:** 接受的是固定 TRADEFLOW 输入下的底层候选数据完整性与可审阅性，不是用户业务验收、正式业务定义或跨 Schema 规模化授权。

### Decisive findings

- 初次替身审阅为 `REWORK`：最终 `qualifiers.jsonl` 中 350 个限定项有 317 个来自未经复核的 corpus modifier；同一物理列可无冲突地进入多个基础概念；中文观察表达与基础概念不一致时仍发布为普通候选；正交语义被挤入 `party_role` 和 `measure_state`。
- 最终实现把 5,347 条字段绑定观察、2,243 条机器假设和正式发布投影分开；Observation 保留字段类型、原始 Facet 与 binding，Hypothesis 直接引用 Observation、方法、证据和反证；Review Decision 当前为空且单独版本化，不再由机器候选冒充人工决定。
- 真实重放只发布 1,559 个有直接或 Facet 可解释支持的属性表达；66 个冲突和 618 个证据不足假设留在 `semantic_hypotheses.jsonl`，没有进入主地图。
- 正式投影覆盖 4,294 个唯一物理字段；全部假设覆盖 5,342 个唯一字段。覆盖差额被明确解释为未绑定或待复核，而非静默丢失。
- 名义本金保留 62 个候选字段，其中 55 个达到发布门槛；另有跨概念列、错误中文注释和“期初”等未被当前限定词证据完整解释的实例留在候选层。交易对手正式覆盖 60 个字段。
- `party_role / direction / measure_state` 的混轴已拆为数据侧、主体角色、持仓方向、交易方向、收付方向、可用状态、变化状态、估算状态和聚合状态；映射迁至版本化 TRADEFLOW 配置。
- 同一语义组中的冲突字段会单独隔离，不再让一个坏实例污染或阻断其余干净实例。

### Falsification attempts

- 以 `COLLATERAL_NOTIONAL_CURRENCY` 反证单列单概念假设：相关表达被降为跨概念冲突。
- 以 `LONG_DYNAMIC_NOTIONAL_ORG` 的“结算币种”注释反证字段名主导：该关联保留为证据不足假设，不进入正式名义本金地图。
- 以目标侧对冲账户反证 `party_role` 单轴：目标侧与交易对手角色拆为 `flow_side` 和 `party_role`。
- 以“预估冻结金额”反证笼统状态轴：拆为 `estimation_status` 和 `availability_state`。
- 以 corpus recurrence 反证自动清洗：未经复核的修饰词全部只留在 diagnostics/review queue，不进入最终 Qualifier。
- 以“频率”和“手机号”反证宽泛后缀分类：更具体的期限周期和联系信息模式优先，避免分别误入比率和标识。

### Residual limits

- 正式投影仍是有证据的机器候选，不应被解释为已确认字段标准；确认只能来自版本化 Review Decision。
- Wiki 只提供有界辅助上下文；Unknown 大量存在是诚实结果，不是缺陷掩盖。
- 上游 V2 的误分仍保留为冲突/复核项；本 Change 不回写或修正 V2 Canonical。
- 尚未证明的表达仍需后续模型或人工批量复核；本轮接受的是“不污染正式地图”的架构边界，不是 100% 召回率。
- 用户审阅任务仍未完成，推荐入口和 `business_acceptance` 不得更新。
