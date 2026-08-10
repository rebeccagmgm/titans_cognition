# 03 总体架构规范

## 1. 架构结论

V1采用文件优先、阶段化、可重跑架构：

架构图展示目标能力，不代表所有组件同时开工。V1A只走Panorama分支；V1B在TRADEFLOW分层样本增加Deep Derive/Infer、Canonical Evidence闭环、Review、Evaluate和样本深度地图；只有面向LLM的Evidence Pack、Wiki、LLM和全量Deep Render属于V1C。

```text
Oracle数据字典 / 对象定义
                ↓
           只读Extractor
                ↓
    Panorama Canonical Physical Facts
          ↙                         ↘
Schema统计 / 粗结构 / 依赖地图       TRADEFLOW Deep Case过滤
          ↓                         ↓
   TITANS Panorama地图       特征 / 可用SQL解析 / 规则
                                    ↓
                          Structural Candidates
                         ↙                    ↘
          Canonical Evidence Link        V1C Evidence Pack + Wiki
                    ↓                          ↓
         Gold Set / Human Review          基础模型SDK语义辅助
                    ↓                          ↓
          V1B样本深度地图                V1C全量深度地图
```

## 2. 技术选型

| 能力 | V1选择 | 说明 |
|---|---|---|
| 主语言 | Python | 提取、特征、推断、SDK和渲染统一实现 |
| 表格结果 | Parquet | 保存类型化物理事实、派生观察和候选结果 |
| 本地分析 | DuckDB | 查询Parquet、汇总、联接和生成地图数据 |
| SQL解析 | SQLGlot作为首选解析器 | 必须配置Oracle方言和Schema，保留partial/failed |
| 规则配置 | Python为主，YAML为辅 | 复杂推断不建设通用DSL |
| LLM | 官方基础SDK的薄适配层 | 不使用Agent框架控制主流水线 |
| 人工评审 | YAML/Parquet | V1不建设多人评审服务 |
| 展示 | 生成式静态HTML | 无服务端、无权限和登录 |

## 3. 明确不引入

- PostgreSQL：没有持续写入、并发评审或API需求。
- Neo4j：V1关系规模可通过边表和Python/DuckDB处理。
- DataHub/OpenMetadata：当前不是多源治理和Catalog建设。
- pgvector：尚未证明规则、结构特征和普通文本召回不足。
- Airflow/消息队列/远程Worker：V1为本地批处理。
- Agent自治编排：流水线顺序和证据边界由代码控制。

## 4. 组件职责

### 4.1 Scope Resolver

- 解析 Panorama 和 Deep Case 配置。
- 固定 Panorama Schema allowlist、对象类型、Deep Case 成员规则和一跳边界策略。
- 输出允许查询的元数据范围。
- 禁止把依赖遍历自动扩大 Panorama，也禁止把 Panorama 自动升级为全量深度分析。

### 4.2 Oracle Extractor

- 只读查询允许的数据字典视图和对象定义。
- 生成Physical Fact数据集。
- 记录可见范围、权限缺口和提取失败。
- 不查询业务数据行。

### 4.3 Normalizer

- 生成稳定`asset_id`和`column_id`。
- 标准化对象类型、数据类型和空值表示。
- 保留原始名称和原始文本，不做语义覆盖。

### 4.4 Feature Engine

- 名称分词和词根。
- 字段角色基础特征。
- 约束、索引和依赖特征。
- 对象结构指纹和相似度输入。

### 4.5 SQL Analyzer

- 解析View SQL和其他批准的定义文本。
- 产生表级/字段级引用和表达式摘要。
- 记录方言、Schema上下文、歧义和失败。
- 不将解析结果伪装成数据库声明事实。

### 4.6 Inference Engine

- 只对明确的Deep Case产生任务级Inference Result，并按结果引用Identity、Grain、Role、Family、Field Concept和Relation候选。
- 每个候选附带方法、证据等级、原始方法分数和限制。
- 支持Single、Competing、Unknown和Not Evaluable，且不伪造Unknown Candidate。

### 4.7 Evidence Resolver（V1B）

- 将候选引用解析到Canonical Physical Fact、Derived Observation或可定位文档。
- 生成Evidence Item与Candidate-Evidence Link。
- 保存支持、反证和上下文立场。
- 规则命中写入Method Trace，不作为独立Evidence Item。

### 4.8 Evidence Pack Builder（V1C）

- 从已落盘事实、派生观察和候选中构造有限上下文。
- 复用Canonical Evidence ID，不重新定义证据身份。
- 控制字符数、对象数量和Wiki片段范围。
- 对LLM隐藏凭证、连接信息和非必要内部配置。

### 4.9 LLM Semantic Analyzer（V1C）

- 使用基础SDK和结构化输出。
- 只做命名、解释、语义映射、反例提示和Respond/Abstain判断。
- 输出经Schema及Evidence ID校验后才进入Candidate层。

### 4.10 Evaluator

- 对 Deep Case Gold Set分别运行各任务评测；对 Panorama 单独评测提取完整性和地图可达性。
- 输出错误类型、失败样本和证据质量。
- 不产生单一“总体认知准确率”。

### 4.11 Map Renderer

- 从共享事实构建 Panorama 页面，从 Deep Case 候选构建深度 Object Card 和地图页面。
- 页面不是权威数据源。
- 支持从候选回溯Evidence。

## 5. 阶段和中间结果

| 阶段 | 输入 | 输出 | 无LLM可运行 |
|---|---|---|---:|
| Panorama Extract | Oracle metadata | panorama/facts/* | 是 |
| Panorama Derive | panorama/facts/* | panorama/derived/* | 是 |
| Panorama Render | panorama facts + derived | panorama/map/* | 是 |
| Deep Derive（V1B样本） | panorama facts + case config | deep-cases/tradeflow/derived/* | 是 |
| Deep Infer（V1B样本） | deep derived + facts | deep-cases/tradeflow/candidates/core/* | 是 |
| Evidence/Review（V1B样本） | core candidates + canonical sources | evidence/* + review_decisions | 是 |
| Deep Evaluate（V1B样本） | core candidates + Gold Set | deep-cases/tradeflow/evaluation/* | 是 |
| Deep Sample Render（V1B） | sample facts + candidates + evidence | deep-cases/tradeflow/map/* | 是 |
| Deep Scale（V1C） | 已验证方法 + TRADEFLOW全量 | candidates/core + family + field-concept | 是 |
| Deep Semantic（V1C） | candidates + evidence + Wiki | candidates/semantic | 否 |
| Deep Render（V1C） | 全部有效Deep结果 | deep-cases/tradeflow/map/* | 是 |

每个阶段必须支持独立重跑，并验证上游Manifest和Schema版本。

### 5.1 阶段门约束

- V1A不得为了未来候选类型预先实现空的推断框架。
- V1B只实现支撑 `Identity → Grain → Role → Relation → Evidence` 纵向闭环所需的最小代码和契约。
- V1C不得在V1B Gold Set、Unknown行为和用户效用验收通过前启动。
- Evidence Pack、SQLGlot列级Lineage、Object Family、Field Concept、Wiki和LLM均不是V1A/V1B关键路径；Canonical Evidence与样本深度地图是V1B必需结果。

## 6. 最小运行Manifest

V1不建设Edition体系，但每个运行阶段必须更新或生成可审计的`manifest.json`：

```json
{
  "run_id": "titans-<generated-id>",
  "stage_id": "panorama-extract",
  "scope_ids": ["titans-panorama-v1", "tradeflow-deep-v1"],
  "source_label": "testdb",
  "started_at": "<timestamp>",
  "completed_at": "<timestamp>",
  "visibility_boundary": "current-account-accessible-metadata",
  "source_capture": {
    "consistency_mode": "BEST_EFFORT_METADATA_CAPTURE",
    "source_scn": null,
    "query_bundle_sha256": "<sha256>"
  },
  "scope_config_sha256": "<sha256>",
  "code_version": "<git-commit-or-working-tree-marker>",
  "rules_version": "<content-hash>",
  "schema_version": "v1",
  "prompt_versions": {},
  "model_configs": {},
  "inputs": [
    {
      "artifact_id": "<upstream-id>",
      "logical_name": "<name>",
      "relative_path": "<path>",
      "schema_version": "<version>",
      "content_sha256": "<sha256>"
    }
  ],
  "outputs": [
    {
      "artifact_id": "<artifact-id>",
      "logical_name": "objects",
      "relative_path": "panorama/facts/objects.parquet",
      "media_type": "application/vnd.apache.parquet",
      "schema_version": "v1",
      "row_count": 0,
      "content_sha256": "<sha256>",
      "producer_stage": "panorama-extract",
      "status": "SUCCESS"
    }
  ],
  "known_gaps": []
}
```

`inputs`引用上游Artifact；首个Extract阶段可以为空。`outputs`必须逐项记录逻辑名、相对路径、Schema版本、记录数、内容SHA-256、生产阶段和状态。Oracle无法提供统一SCN时必须使用`BEST_EFFORT_METADATA_CAPTURE`并记录提取起止时间，不得声称获得事务一致快照。Manifest用于复现和审计，不提供历史治理、发布审批或版本比较功能。

## 7. 运行失败语义

- 单个对象提取失败不得中止全量提取；写入失败清单。
- SQL解析失败不得删除原始定义；输出失败状态和错误类别。
- 某类推断失败不得阻塞其他候选类型。
- LLM不可用时，交付物必须仍包含完整物理事实、结构候选和无LLM地图。
- 输出Schema校验失败的记录不得进入正式Parquet结果。

## 8. 未来演化门槛

只有满足专项Spec中的触发条件，才允许升级：

- 持续刷新/多人评审/API → PostgreSQL。
- 多源采集与治理 → Catalog平台。
- 图查询成为核心且边表方案形成真实瓶颈 → 图数据库。
- 结构和文本方法无法满足已定义检索任务 → Embedding。
- 第二个 Deep Case 验证出稳定概念和关系 → 轻量本体。
