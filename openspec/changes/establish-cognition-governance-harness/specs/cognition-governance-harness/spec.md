## Purpose

本能力为 TITANS Cognition 的多 Schema 语义导航治理提供一个窄化、可审计且可强制验证的首个切片，在不复制现有事实、候选、评审和交付状态的前提下固定执行与升级边界。

## ADDED Requirements

### Requirement: Harness 报告不得拥有独立业务状态

系统 SHALL 按以下优先级解析权威状态：OpenSpec Change 管意图和实施范围；阶段 Manifest 管运行与 Artifact 事实；现有 Review Decision 文件管领域处置；当前状态基线管读者交付、业务验收和规模化授权。Harness 报告 SHALL 只保存 `derived_from` 引用、哈希和验证观察，不得创建独立候选、证据、领域 disposition 或交付状态。

#### Scenario: 报告与权威来源冲突
- **WHEN** Harness 报告观察值与引用的 Manifest、Review Decision 或状态基线不一致
- **THEN** 校验 SHALL 失败并指向权威来源，不得由 Harness 报告覆盖或选择新值

#### Scenario: 权威来源显示尚未验收
- **WHEN** 工程检查通过但状态基线仍为读者未交付或业务未接受
- **THEN** Harness 报告 SHALL 原样引用该状态，并不得生成 `ACCEPT`、`VALIDATED` 或等价业务完成标签

### Requirement: Runner 只能执行代码注册的类型化操作

系统 SHALL 使用代码所有的语义导航操作注册表。Workflow Profile 只能引用已注册操作 ID；Schema Case Pack 只能提供该操作 Schema 允许的类型化参数和批准的 Manifest、配置及授权引用。Runner SHALL 拒绝任意命令文本、未注册操作、未知参数、工作区外路径、解析后越界路径和未批准数据类别。

#### Scenario: Profile 包含任意 Shell
- **WHEN** Profile 或 Case Pack 提供命令字符串、脚本片段或未注册操作 ID
- **THEN** Runner SHALL 在预检阶段拒绝执行

#### Scenario: Windows 路径解析后越界
- **WHEN** 输入路径通过相对段、符号链接或 Reparse Point 解析到允许工作区之外
- **THEN** Runner SHALL 拒绝该参数并报告解析后的目标边界

### Requirement: Workflow Profile 与 Schema Case Pack 必须正交分离

Workflow Profile SHALL 定义语义导航固定阶段、操作 ID、Artifact 角色、审阅输入和 Gate；Schema Case Pack SHALL 定义具体 Schema 范围、输入 Manifest、领域配置、局部词汇、数据政策、授权引用和预算。Profile SHALL NOT 包含 TRADEFLOW 专用表名、Wiki 页面、词种子或路径；Case Pack SHALL NOT 复制阶段顺序和治理逻辑。

#### Scenario: 新 Schema 使用同一工作流
- **WHEN** 一个后续 Schema 具有不同范围、Manifest、局部词汇和 Wiki 来源
- **THEN** 系统 SHALL 通过新的 Case Pack 表达差异，而无需修改 Runner 或语义导航 Workflow Profile

#### Scenario: TRADEFLOW 假设泄漏
- **WHEN** 通用 Profile 出现 TRADEFLOW 专用配置或合成 Case 依赖 TRADEFLOW 结构才能通过
- **THEN** 隔离检查 SHALL 失败，不得形成复用结论

### Requirement: 固定验证点必须由 Runner 强制执行

Runner SHALL 在预检、每个操作完成后、独立审阅前、独立审阅后和报告定稿前调用同一确定性校验器。任一硬检查失败 SHALL 停止后续发布相关操作；Skill、Agent 或可选宿主配置不得跳过或重新排序这些检查。

#### Scenario: Skill 试图跳过审阅前检查
- **WHEN** Skill 或调用者请求直接进入独立审阅而当前阶段 Artifact/哈希检查未通过
- **THEN** Runner SHALL 拒绝进入审阅阶段

#### Scenario: Hook 未加载
- **WHEN** Codex Hook 未配置、未信任或被禁用
- **THEN** 直接运行 Runner SHALL 仍执行全部固定验证点并产生相同结论

### Requirement: 模型调用必须默认关闭并具备总预算

模型和 Subagent 调用 SHALL 默认为 0。只有 Workflow Profile 声明可验证的歧义触发器、Schema Case Pack 引用有效授权记录且确定性阶段无法完成时，Runner 才能生成审阅包。模型阶段 SHALL 具备跨重试的总调用上限、总 Token 上限、冻结输入哈希缓存键和明确降级；实际用量无法测量时，模型依赖结果 SHALL 保持不可发布。

#### Scenario: 确定性校验足够
- **WHEN** 当前阶段仅需检查 Schema、哈希、引用、路径或已有 Gate
- **THEN** Runner SHALL 完成检查而不生成模型审阅包

#### Scenario: 预算耗尽或用量不可测
- **WHEN** 总调用/Token 上限已达到，或 Profile 要求测量但实际用量为 `UNMEASURED`
- **THEN** 模型阶段 SHALL 停止并形成不可发布缺口，不得通过增加重试或降低证据门槛继续

### Requirement: 独立审阅必须隔离实施结论

独立 Reviewer SHALL 只接收原始目标、验收标准、冻结 Evidence/Artifact、候选或 Projection、反例和已知缺口，不得接收实施 Agent 的自我评价。输出 MUST 包含 `ACCEPT`、`REWORK`、`STOP` 或 `DEFER`、决定性理由和最小下一动作；缺少来源或关键反例未处置时审阅无效。该 disposition 仅属于本次工程 surrogate review，不得写成领域 Review Decision 或用户业务验收。

#### Scenario: 审阅包泄漏预期答案
- **WHEN** 审阅包包含实施者的预期 disposition、修复建议结论或“应当通过”的提示
- **THEN** Runner SHALL 将该审阅标记无效并停止报告定稿

### Requirement: 合成隔离检查不得冒充跨 Schema 验证

本 Change SHALL 使用结构显著不同、包含缺失元数据、歧义关系和误导名称的合成非 TRADEFLOW Fixture 执行 `CONTRACT_ISOLATION_CHECK`。只有 `D-010` 选定的第二个真实 Schema 完成受治理运行、独立审阅和读者任务证据后，后续 Change 才能声明跨 Schema 证据成立。

#### Scenario: 合成 Case 通过
- **WHEN** 非 TRADEFLOW 合成 Fixture 无需修改 Runner/Profile 即通过契约检查
- **THEN** 报告 SHALL 仅记录 `CONTRACT_ISOLATION_CHECK=PASS`，不得记录 `CROSS_SCHEMA_VALIDATED`

### Requirement: 数据和交付边界必须保持不变

Runner SHALL 遵守项目当前只读元数据、无业务行扫描、无未授权模型外发和无源系统写入边界。测试、运行成功和 surrogate review SHALL 仅作为工程证据，不得自动改变 reader delivery、business acceptance 或 scale authorization。

#### Scenario: Case Pack 自称允许业务行
- **WHEN** Case Pack 声明业务数据行可访问但没有权威安全决策和对应 Change
- **THEN** Runner SHALL 拒绝执行，而不是把 Case Pack 声明当作授权
