## ADDED Requirements

### Requirement: 表级语义地图必须保持候选与交付边界

项目 SHALL 允许本 Change 在固定 TRADEFLOW Physical Facts、固定既有分类/字段运行和固定 Wiki Tree/正文缓存范围内生成独立的表语义画像、业务协作表组、物理变体组、表间候选关系和审阅Projection。该授权 SHALL NOT 扩展为修改既有Canonical结果、读取业务数据行、构建正式企业本体、执行全Panorama深度语义推断、推广到其他Schema或自动形成读者交付和业务验收结论。

#### Scenario: 表语义模型Gate通过

- **WHEN** 固定代表案例的信息模型Gate通过且确定性运行可重放
- **THEN** 项目 SHALL 记录表语义工程结果和限定范围，同时 SHALL 继续分别报告读者交付、业务验收和规模化授权状态

#### Scenario: 表级候选覆盖全部主体表

- **WHEN** 表语义运行为全部主体表生成画像、标签或Unknown处置
- **THEN** 项目 SHALL 将其报告为候选处置覆盖，不得据此宣称表语义正确、TITANS业务全貌完成或其他Schema获得扩展授权

#### Scenario: 用户接受局部业务表组

- **WHEN** 用户确认某个TRS、期权或其他限定表组能够帮助理解表职责和关系
- **THEN** 项目 MAY 记录该限定案例的读者接受结果，但 SHALL NOT 自动接受全部表标签、全部物理变体或整个方法

#### Scenario: 用户授权限定测试数据聚合核验

- **WHEN** 用户明确授权对指定测试库表和键执行只读聚合核验
- **THEN** 项目 MAY 冻结不含业务主键值或业务明细的计数、匹配率和基数结果作为测试快照证据，同时 SHALL NOT 将其解释为生产数据、声明外键、正式业务规则、业务验收或一般性业务数据访问授权
