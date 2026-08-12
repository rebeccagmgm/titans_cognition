## Purpose

本能力确保 TITANS Cognition 始终围绕可用的业务全貌交付报告真实状态，并将工程证据、读者可用性、业务验收和规模化授权保持为不可互相替代的独立判断。

## ADDED Requirements

### Requirement: 唯一业务全貌目标
项目 SHALL 将“可从业务区域、对象和生命周期下钻到表、粒度、键、关系、证据与 Unknown 的 TITANS 业务全貌”作为唯一产品完成目标。物理元数据目录、结构分类器、评测器和静态页面 SHALL 仅被表述为实现该目标的组成部分或支持证据。

#### Scenario: 物理盘点已经完成
- **WHEN** 全部允许范围内的物理对象已经抽取、对账并生成 Object Card
- **THEN** 项目状态 SHALL 报告物理覆盖的完成情况，同时 SHALL NOT 将其表述为 TITANS 业务全貌已经完成

### Requirement: 分层状态不可互相替代
项目 SHALL 分别维护并报告物理抽取、结构认知、读者交付、业务验收和规模化授权五个状态。任一状态的成功 SHALL NOT 自动提升其他状态。

#### Scenario: 规则回归全部通过但没有业务地图
- **WHEN** 自动测试和 Gold 回归全部通过，但不存在当前运行对应的读者可用业务地图
- **THEN** 结构认知状态 MAY 报告相应工程结果，读者交付和业务验收 SHALL 继续报告未完成，规模化授权 SHALL 保持禁止

#### Scenario: 用户未接受业务价值
- **WHEN** 用户尚未确认结果能帮助理解 TITANS 业务区域、对象、生命周期和数据关系
- **THEN** 业务验收 SHALL 报告未通过，不论候选覆盖率、证据链接率或自动评测结果如何

### Requirement: 完成声明必须与证据类型匹配
每项进展或完成声明 SHALL 指明它证明的是实现存在、测试通过、真实运行、读者可用、业务接受或规模化授权中的哪一类。自动生成的测试、Gold Set、评估报告或 Gate 结果 SHALL NOT 作为自身业务价值的独立证明。

#### Scenario: 自动生成标准与当前规则一致
- **WHEN** 当前规则输出与由同一开发过程建立或修订的 Gold Set 完全一致
- **THEN** 项目 SHALL 将结果表述为规则回归一致性，并 SHALL NOT 单独据此宣称认知方法有效或用户价值成立

#### Scenario: 真实运行结果存在
- **WHEN** 抽取或推断命令在真实测试库元数据上成功运行
- **THEN** 项目 SHALL 报告真实运行范围、run 标识和结果边界，但 SHALL NOT 将命令成功等同于读者可用或业务验收

### Requirement: 当前V1B结果重新定级
现有 TRADEFLOW V1B 候选、Evidence、Review Decision、Gold Set和评估报告 SHALL 保留为历史结构推断原型与规则回归证据。它们 SHALL NOT 被表述为已验证的业务认知方法，当前 Gate B SHALL 保持阻塞。

#### Scenario: 展示现有11项Gold结果
- **WHEN** 项目展示现有 `11/11 ADJUDICATED` 或零评估错误结果
- **THEN** 同一展示 SHALL 明确这些结果不构成业务全貌交付、独立方法验证或用户价值确认

### Requirement: 规模化必须获得独立授权
项目 SHALL NOT 启动 V1C、全量深度语义推断或方法泛化，除非读者交付已经存在、业务验收已经通过，并且用户对该次扩展作出明确授权。

#### Scenario: 工程门通过但业务验收未通过
- **WHEN** 物理和结构工程门均通过，而业务验收仍未通过
- **THEN** 规模化授权 SHALL 保持禁止，后续工作 SHALL 仅限于修正目标、证据、交付或验收缺口

### Requirement: 历史结果必须可追溯
重置目标和状态时，项目 SHALL 保留现有代码、测试、Canonical Facts、历史运行目录和原始评估报告，并通过状态说明改变其解释边界。项目 SHALL NOT 删除、覆盖或重写历史证据来制造新的完成状态。

#### Scenario: 状态口径发生纠偏
- **WHEN** README、Spec或状态报告将旧结果从“方法有效”降级为“结构原型”
- **THEN** 对应历史Artifact SHALL 保持可定位，且新说明 SHALL 能指出其run、适用范围和不再支持的完成声明
