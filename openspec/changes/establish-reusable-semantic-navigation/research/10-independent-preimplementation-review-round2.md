# 07 修订契约实现前独立复审（第 2 轮）

> 审阅日期：2026-08-14  
> 审阅 ID：`review-07-preimplementation-20260814-02`  
> 审阅性质：只读独立反例复审；不是实现验收、页面验收或业务验收  
> 复审处置：`REWORK`

## 1. 结论

首轮指出的 9 类契约结构缺陷已经闭合，但当前仍不能授权 P2/P3/P4、页面、第二 Schema 或规模化。阻断原因已收敛为执行态对账缺口：最终 P0/P1 产物尚未绑定为 step 01/02 的 `PASS` GateResult，Suite A 的 23 个 P0→P1 用例尚未执行并记录，9 个行为矩阵单元仍为 `REQUIRED_NOT_YET_PROVIDED`。

当前只授权一次有界 P0/P1 对账与 Suite A 执行。

## 2. 独立复算事实

- 两份 YAML 均可严格解析且无重复键。
- 声明数独立复算为 contract 240、validation 95，合计 335，全部唯一。
- 15 项 source manifest、09 复审 hash 与候选 bundle 自引用 SHA-256 均与声明一致。
- 当前 07 bundle hash：`b213b5d97575bbcd5b3dec9cd094f6426eade55081b8f58f4b986ac463a335b7`。
- 最终 P0/P1 产物包含 13,611 行与 13,611 个唯一物理字段 ID；Pack SHA-256 为 `0fa37a92d0c2250c78f0589fc625e4404c1316f9703186f9354356b80887c43e`。
- P0/P1 disposition 为 `PREPARED=5512`、`EXCLUDED=8099`、`DEFERRED=0`；`model_calls=0`、`external_egress=false`、`business_rows_read=false`、`database_writes=0`。
- P0/P1 manifest 对 Suite A 的正式状态仍为 `NOT_CLAIMED`。

## 3. 首轮缺陷闭合情况

以下结构问题已实质闭合：

1. 显式 `PRE09-D001` 至 `PRE09-D012` case registry 与 exact gate sets。
2. bounded authorization 与 `PASS` 前驱链分离。
3. 07 bundle 自冻结与历史审查 hash 绑定。
4. P2/P3/P4 的 run/Profile/Schema/candidate/decision/expression/Reader/active grain。
5. 非 TRADEFLOW SOURCE/TARGET negative case 与 Profile guard。
6. 零模型、零外发、零业务行读取、零数据库写入安全信封。
7. canonical workspace/output root 与 symlink escape 检查。
8. Margin direct-positive 与 M01/C03 blocker 分离。
9. Margin 六类 expression-kind 不折叠约束。

## 4. 仍然阻断的执行证据

- 9 个 behavior-matrix 单元仍为 `REQUIRED_NOT_YET_PROVIDED`，其余相关单元与 Suite C 仍为 `NOT_EXECUTED`。
- Trade、Position、Margin 的 concrete direct-positive evidence 尚未提供；registry 明确将三者列为 current gaps。
- M01 已正确禁止充当 Margin direct positive，但尚无替代正例。
- 最终 stage1 manifest/pack 尚未形成 step 02 `PASS` GateResult，也未作为冻结的 step 03 input manifest 记录。
- 产物存在和 hash 一致只证明 P0/P1 构建完成，不等于 Suite A、语义 handoff 或业务验收通过。

## 5. 最小下一动作与禁止项

仅允许：

1. 绑定最终 stage1 manifest 与 Pack hash。
2. 生成 step 01/02 GateResult，机器校验 13,611 exact case set、scope、安全信封与路径边界。
3. 执行并单独记录 Suite A 的 23 个 P0→P1 cases。
4. 完成后再次进行独立实现前复审。

继续禁止：step 04 handoff、P2/P3/P4、页面生成、第二 Schema、规模化，以及把任何工程结果表述为用户业务验收。

