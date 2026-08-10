# 12 待决事项

本文件列出Spec无法替用户决定、且会实质改变实现或安全边界的问题。实现Agent不得通过默认值静默关闭这些问题。

## D-001 Oracle元数据访问方式

- **问题**：使用现有只读数据库适配器，还是为本工程配置独立只读连接？
- **当前状态**：初步决定复用现有 `gf-derivative-db` 只读适配器；已成功列出 `TITANS_TRADEFLOW` 全部477张表，并读取字段、注释、约束、索引和样例DDL。
- **阻塞**：不再阻塞阶段0；首次Extract仍需验证全Panorama范围的分页、失败恢复和输出完整性。
- **需要证据**：首次Extract的范围对账、失败清单和Manifest。
- **不可接受**：复制真实凭证到仓库；申请写权限。

## D-002 Panorama与Deep Case精确范围

- **问题**：Panorama准确包含哪些TITANS Schema和对象类型；TRADEFLOW当前477张表基线是否仍成立，视图、物化视图或Synonym如何处理？
- **当前状态**：已确认初始范围为所有非 `_PROD` 的 TITANS Schema；对象类型包括 TABLE、VIEW、MATERIALIZED_VIEW、SYNONYM。`TITANS_TRADEFLOW` 纳入首个Deep Case。
- **阻塞**：首次Extract必须重新核验数量和可见边界，不能把当前基线当成最终事实。
- **已知排除**：`GF_OTC`、`GF_FICC`不进入第一版。
- **默认边界**：明确allowlist中的Panorama对象；`TITANS_TRADEFLOW`为首个Deep Case；一跳直接依赖仅作为Boundary Node。具体配置见`cases/titans-panorama/scope.yaml`。

## D-003 DDL与View SQL权限

- **问题**：当前账号可以通过哪些方式读取完整DDL和View SQL？
- **当前状态**：已接入 `definition_mode=all`：表DDL通过只读适配器逐对象读取，View SQL通过 `ALL_VIEWS.TEXT` 批量读取；默认 `record-only` 仍只记录能力缺口。首次全量Extract仍需按对象统计成功、缺失、无权限和失败分布。
- **阻塞**：是否阻塞由[11 安全与运行的能力降级矩阵](11-security-and-operations.md)逐任务决定，不再笼统阻塞整个V1B。
- **降级方案**：保留MISSING/NO_PERMISSION；受影响任务标记NOT_EVALUABLE，不伪造Lineage，也不把未运行计作Unknown。

## D-004 Wiki输入形态

- **问题**：用户提供的是纯目录、导出文件树、页面正文还是仅标题清单？
- **当前状态**：待用户提供。
- **阻塞**：Wiki Evidence和LLM语义辅助，不阻塞结构认知。
- **边界**：标题只能作为弱导航证据，不能支撑具体业务关系。

## D-005 LLM Provider与数据外发

- **问题**：使用哪个Provider/模型；哪些内部元数据允许发送？
- **当前状态**：未授权，默认禁用。
- **阻塞**：`llm-enrich`阶段。
- **不阻塞**：Extract、Derive、Infer、无LLM Evaluate和基础Render。

## D-006 Gold Set评审人和标注方法

- **问题**：谁负责将Identity、Grain、Role、Relation和Unknown案例从DRAFT裁定为ADJUDICATED；争议如何标记DISPUTED？
- **当前状态**：待定。
- **阻塞**：方法质量正式判断和全量扩展门槛。
- **建议**：至少有一名熟悉TRADEFLOW结构的人；争议项保留多意见，不强制共识。

## D-007 纵向样本选择

- **问题**：哪些真实对象组成第一组纵向样本？
- **当前状态**：必须在Physical Facts提取后选择。
- **阻塞**：推断实现的第一个端到端Case。
- **原则**：按结构难度分层，不按容易解释的名称挑样本。

## D-008 静态地图保存和分享边界

- **问题**：地图仅本机查看，还是会分享给内部其他人员？
- **当前状态**：待决。
- **阻塞**：DDL/Wiki展示粒度、脱敏和输出目录权限。

## D-009 是否初始化独立Git仓库

- **问题**：`titans-cognition`是否作为独立Git仓库管理？
- **当前状态**：已执行；本地已初始化并推送到远端 `origin/main`。
- **阻塞**：不阻塞实现；后续Manifest使用Git提交号作为`code_version`。

## D-010 第二Schema验证对象

- **问题**：TRADEFLOW完成后选择哪个Schema验证方法泛化？
- **当前状态**：V1后决定。
- **阻塞**：不阻塞V1；阻塞把方法宣传为全TITANS通用和建设正式本体。

## 已决定事项

- V1只读、元数据级，不扫描业务数据行。
- V1不以`_PROD`映射为核心问题。
- V1使用类型化结果集，不使用万能Claim Ledger作为唯一底层模型。
- V1使用Parquet/JSON/YAML和DuckDB，不使用PostgreSQL或Neo4j。
- V1的LLM通过基础SDK受Evidence Pack约束，不使用Agent自治主流程。
- V1必须提供最小可浏览地图和Gold Set评测。
- V1采用V1A Panorama、V1B TRADEFLOW Deep Sample、V1C TRADEFLOW Deep Scale三道阶段门；V1C必须在Gate B通过并获用户确认后启动。
- 正式本体、长期Edition和Catalog平台延后到真实需求触发。
