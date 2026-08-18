# Output Binding Surrogate Review

Disposition: `ACCEPT`

本次审查对象是 Machine Facts 新增的“表达式到物理输出字段”绑定，不代表业务验收、运行验收或跨任务血缘闭环。

## 证实案例

- 普通 `INSERT ... SELECT`：SELECT 输出数量与 Canonical Target Schema 非分区列数量一致时，按位置生成绑定。
- 显式 Target Column List：按字段名定位物理 Target Ordinal，覆盖列表重排，避免退回物理列序猜测。
- 86840：任务内 CREATE 与 89 个 SELECT 输出形成顺序证据，`Dyna_Nom_Prin` 绑定到目标字段 `dyna_nom_prin`。

## 反例与不确定性

- 当前物理 Target Schema 多出尾部字段 `ex_rate_model`：保留前 89 个已证实绑定，同时以 `DRIFT_EXTRA_TARGET_COLUMNS` 和 `TARGET_SCHEMA_DRIFT` 暴露未绑定字段；不把 Schema 漂移伪装成完全匹配。
- 仅有物理 Target Schema 且字段数量不一致：不输出绑定，记录 `OUTPUT_BINDING_NOT_PROVABLE`。
- 动态分区：不采用引擎相关的隐式末尾列规则，记录 `DYNAMIC_PARTITION_BINDING_NOT_PROVABLE`。
- 显式目标列在可用 Schema 中缺失或重复：不输出绑定，记录 `OUTPUT_BINDING_SCHEMA_CONFLICT`。

## 决定理由

实现同时覆盖正例、显式重排、Schema 漂移和不可证明反例；Reader/Consumer 能区分已解析绑定、目标 Schema 漂移和未评测缺口。最小后续动作是让跨任务 Consumer 消费 `output-field-bindings.jsonl`，该动作不属于本次 V1 Writer 变更。
