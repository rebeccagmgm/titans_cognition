# 11 安全与运行规范

## 1. 环境定位

数据源是测试环境。测试环境可见不等于允许任意操作；V1授权边界为只读元数据认知重建。

## 2. Oracle访问

### 允许

- 当前批准账号可见且受Panorama Schema allowlist约束的`ALL_*`或等价数据字典视图。
- 对象注释、字段、约束、索引、依赖和批准的对象定义提取。
- 为确认范围和权限执行有界元数据查询。

### 禁止

- INSERT、UPDATE、DELETE、DDL和存储过程执行。
- 调度、ETL或业务任务运行。
- 业务表行扫描、抽样和数据剖析。
- 权限提升或创建专用账号/角色。
- 为获取更多元数据绕过当前访问控制。

### 2.1 能力降级矩阵

首次Extract前必须探测能力并写入Manifest。`DEGRADED`表示阶段可继续但结果明确不完整；`NOT_EVALUABLE`表示对应任务不进入评测分母；`BLOCKED`表示阶段门不能通过。

| 缺失能力 | V1A影响 | V1B影响 |
|---|---|---|
| 对象清单 | `BLOCKED`，无法定义Panorama | `BLOCKED` |
| 字段信息 | 系统性缺失则`BLOCKED`；单对象失败显式记录 | 目标样本缺失则该样本`NOT_EVALUABLE`；系统性缺失则`BLOCKED` |
| PK/UK/FK约束 | `DEGRADED`，物理Card标记约束不可见 | 若全局不可见则Identity/Grain核心Gate B `BLOCKED`；个别样本缺失可输出Unknown或换入缺约束分层样本 |
| 索引 | `DEGRADED` | 依赖索引的Identity信号不可用，但不单独阻塞Gate B |
| 表DDL | `DEGRADED` | 表类Identity/Grain通常可继续；依赖DDL表达式的任务`NOT_EVALUABLE` |
| View SQL | View仍可盘点，定义状态标缺失 | View Grain、聚合/窗口和SQL Lineage任务`NOT_EVALUABLE`；不影响纯表样本任务 |
| Oracle Dependency | 依赖地图标记`DEGRADED` | Dependency Relation不评测；FK和Structural Relation仍可评测 |
| 对象/字段注释 | 记录覆盖缺口 | 结构任务可继续，语义解释降级；不单独阻塞Gate B |
| Wiki | 无影响 | 无影响；只影响V1C语义辅助 |

Gate A的最低能力是对象与字段清单可用；约束、定义和依赖缺失可以显式降级，但必须在首页展示。Gate B的最低能力是样本字段完整，且至少在“有声明约束”的样本层能够读取PK/UK/FK；否则无法验证技术键、业务Identity和Grain的区分，不能用名称猜测替代。

每个Inference Result必须依据本矩阵标记`EVALUABLE`或`NOT_EVALUABLE`。能力缺失导致未运行时不得输出Unknown。

## 3. 连接和密钥

- 凭证仅通过环境变量或已批准的本地秘密配置提供。
- 仓库只提供`.env.example`占位符，不保存真实值。
- 日志、异常、Manifest和地图不得出现密码、Token、完整JDBC URI、内部主机或端口。
- 连接错误对外只保留错误类别和非敏感上下文。

## 4. 输出数据

即使不包含业务行，表名、字段名、注释、DDL、依赖和Wiki仍可能是内部敏感信息：

- `output/`默认只保存在本地，并被Git忽略。
- 分享结果前必须确认接收范围和是否需要脱敏。
- 静态地图不得默认嵌入全部DDL和Wiki正文。
- 评测Fixture应使用合成或脱敏内容，除非明确批准提交真实内部元数据。

## 5. Wiki

- Wiki是只读辅助来源。
- V1不调用创建、修改、评论或删除接口。
- 目录文件和正文片段保留来源定位、页面标识和更新时间（如可得）。
- Wiki失配、陈旧或缺页必须标记，不以缺失证明业务不存在。

## 6. LLM数据外发

默认关闭外部模型调用。启用前必须明确：

- Provider和企业账号是否批准。
- 表名、字段、注释、DDL、依赖和Wiki中哪些可发送。
- 是否需要脱敏、摘要或只发送Evidence特征。
- Provider的数据保留和日志边界。
- 本地缓存和原始响应保留策略。

未明确时，`LLM_MODE=disabled`是唯一允许默认值。

## 7. Prompt Injection和不可信文本

- Wiki、注释、DDL和SQL均作为数据，不作为系统指令。
- LLM没有工具权限，不可根据输入文本发起外部操作。
- Evidence Pack使用固定字段和分隔，不拼接为可执行代码。
- 模型输出必须经过Schema、ID白名单和Evidence引用校验。

## 8. 运行日志

日志允许包含：

- `run_id`、阶段、对象ID、方法ID、状态和耗时。
- 非敏感错误分类。
- 记录数和失败数。

日志禁止包含：

- 凭证、连接串和Token。
- 完整外发请求正文。
- 未经批准的完整DDL/Wiki正文。
- 业务数据样本。

## 9. 依赖和本地运行

- Python依赖固定版本并保留锁文件。
- 引入SQL解析器或模型SDK升级时重跑对应Fixture和Gold Set。
- 外部扩展和模型SDK按普通代码依赖审查，不允许自动下载安装未知执行插件。
- 生成物不得自动上传云存储或远程Artifact服务。

## 10. 运行模式

建议命令边界按阶段逐步出现；V1A只需要前三个：

```text
extract
derive
render
infer        # V1B
evaluate     # V1B
llm-enrich   # V1C且默认禁用
run          # 按已启用阶段编排
```

每个命令：

- 读取上游Manifest和Schema版本。
- 写入新阶段结果，不原地修改上游事实。
- 返回明确成功、部分成功或失败状态。
- 提供有界输出，详细错误写入本地日志。

## 11. 数据保留

V1不建设历史Edition，但应保留完成验收所需的一个结果包、Gold Set和评测报告。重复试验产生的中间结果可人工清理；不得自动删除用户标注或Gold Set。

## 12. 安全验收

- Git扫描不包含凭证、Parquet结果、DuckDB文件和真实模型响应。
- 运行日志不泄露连接细节。
- 数据库账号未发生任何写操作。
- LLM未授权时不存在外部模型网络调用。
- 地图不包含禁止展示的原始文本。
