# 07 修订契约实现前独立复审（第 1 轮）

> 审阅日期：2026-08-14  
> 审阅 ID：`review-07-preimplementation-20260814-01`  
> 审阅性质：实现前独立反例复审；不是实现验收、页面验收或业务验收  
> 审阅对象：修订后的 `07-integrated-semantic-navigation-design.md`、`07-integrated-semantic-navigation-contract.yaml`、`07-integrated-validation-plan.yaml`  
> 复审处置：`REWORK`

## 1. 结论与允许范围

修订后的 07 已通过严格 YAML、声明唯一性和输入哈希等结构检查，并纠正了 Position identity/quantity 混层以及 obligation、cash-flow、履行事件、settlement result 混层的主要设计问题。但 Gate、运行 grain、安全控制和直接正例绑定仍存在可空通过或越权路径，尚不能授权 P2/P3/P4。

当前只允许继续：

- `07c:step:01-provider`
- `07c:step:02-full-evidence-pack`

禁止推进 step 03–12、P2/P3/P4、页面、第二 Schema 和规模化，直至最小返工完成并通过新的实现前独立复审。

## 2. 已独立复算的结构事实

- 两份 YAML 严格解析通过，无重复键。
- 声明遍历独立得到 contract 240、validation 95，合计 335；335 个值均唯一。
- 声明的 source/runtime/overlay 哈希均重新计算并匹配。
- 当前三份 07 的复审 bundle hash 为 `689230de6524a629f1162a9a310e62b536ce8d5529c30b33b533b7a5721f7e71`；算法为按路径和文件字节构造固定 bundle 后计算 SHA-256。

上述事实只证明结构可复算，不证明语义实现或 Gate 已就绪。

## 3. 决定性缺陷

1. **exact case set 未机器闭合。** step 00 使用 `D-001_THROUGH_D-012_EXACT` 等符号，但没有显式 D-001–D-012 case registry 与具体 case IDs；direct-positive 类型也没有绑定逐 case Evidence，仍可重标或空通过。
2. **有界 REWORK 与 PASS 前驱链矛盾。** step 00 允许 `REWORK_BOUNDED_AUTHORIZATION` 推进 step 01–02，但 GateResult 状态不包含该处置，通用规则又要求每个后续步骤消费立即前驱 PASS/hash。实现者只能让 step 01 无法合法执行，或把 REWORK 冒充 PASS。
3. **被复审的 07 bundle 没有自冻结。** source manifest 没有把当前 contract 与 validation plan 本身作为带哈希输入；修改 07 后仍可能复用旧 review/input hash。
4. **P2/P3/P4 grain 仍不完整。** P2 key 缺 `profile_ref/schema_name`；P4 expression key 缺 run/profile/schema/candidate version；Reader candidate grain 与 active-state grain 没有完整字段，跨 run/Profile 仍可能碰撞或重复激活。
5. **TRADEFLOW 隔离缺反例 Gate。** generic SOURCE/TARGET mapping 路径没有显式 Profile guard，也没有非 TRADEFLOW negative case，无法机器证明 `flow_side` 不外泄。
6. **零模型与安全运行边界未机器化。** Gate/Manifest 没有 `model_calls`、token budget、egress、business rows read 等断言；路径也没有 canonical workspace root、allowlist、symlink escape 和 output boundary 检查。
7. **行为矩阵仍有未提供案例。** 8/12 矩阵中 9 个行为 cell 只有 `REQUIRED_NOT_YET_PROVIDED` 类型，其余仍为 `NOT_EXECUTED`。当前 Gate 正确禁止把静态声明或空集当成通过，因此不能据此放行语义实现。
8. **Reader 正例绑定仍有缺口。** Trade、Position direct positive 尚未提供；Margin 把 M01 同时列为 direct positive 与 blocker，但 M01 本身是 unresolved direction 反例，可能让阻塞案例冒充正例。Margin 的 amount、balance、threshold、ratio、parameter、direction 也缺精确 expression-kind 契约。

## 4. 已改善但仍需保持的边界

- Position identity 已与 quantity、balance、direction、time expression 分离；仍需 direct positive 与 ownership anchor 才能生成 Reader。
- obligation、cash-flow schedule/item、payment/transfer/delivery event、settlement result 已明确拆分，应保持。
- Order/Trade、SHORT/LONG、SOURCE/TARGET 的禁止越级规则方向正确，但尚未执行验证。
- Customer/Counterparty、formal `flow_side` 与 Gold 业务权威继续保持 DEFERRED，不得由实现默认关闭。

## 5. 最小下一动作

仅对 07/validation 做最小返工：

- 枚举 D-001–D-012 与 exact case IDs，并把 direct-positive 类型绑定到具体 Evidence；
- 将 bounded-REWORK authorization 独立建模，不与 PASS 前驱链混用；
- 冻结并哈希被复审的 07 contract/design/validation bundle；
- 为 P2/P3/P4 与 active state 增加 run/Profile/Schema scoped grain；
- 增加非 TRADEFLOW `flow_side` negative case；
- 增加零模型、零外发、零业务行读取及路径根边界断言；
- 为 Margin 增加独立 direct positive，并禁止 M01 同时充当正例；
- 为 Margin expression kinds 建立不折叠的机器契约。

返工后必须由独立审阅者重新审查。`REWORK` 不等于业务验收、Reader 发布、第二 Schema 授权或规模化授权。
