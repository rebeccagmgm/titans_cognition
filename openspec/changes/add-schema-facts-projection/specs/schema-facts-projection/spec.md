## Purpose

将现有 Schema Evidence 整理为共用、可查询、按数综 Metadata `guid` 分表的物理 Schema Facts，补足数据库定位、表和字段注释、类型、分区、DDL 证据及现有 Machine Facts 身份关联。

## ADDED Requirements

### Requirement: Shared Schema Facts layout

Schema Facts Projection SHALL 发布为一个共用的当前物理 Schema 事实目录，不得按 Task、路线或下游 Scope 生成不同的 Schema Facts 副本。输出 SHALL 使用以下结构：

```text
machine-facts/projections/schema-facts/
├─ manifest.json
├─ index.jsonl
└─ tables/
   └─ <table_storage_key>/
      ├─ table.json
      └─ columns.jsonl
```

`manifest.json` SHALL 描述 Projection 类型、契约版本、发布状态、表/字段数量、输出文件和边界；`index.jsonl` SHALL 一行表示一张表并提供 Table Storage Key、可用的 `guid`、`metadata_qualified_name`、`qualified_name`、状态和事实文件路径。Projection SHALL NOT 使用 `schema_bundle_sha256` 或 `scope_sha256` 作为目录身份或必备范围身份。

Table Storage Key SHALL 按以下顺序确定：有 `guid` 时使用 `guid`；没有 `guid` 但有完整 `metadata_qualified_name` 时使用该限定名的安全编码；两者都没有时使用 `logical_source_id + qualified_name` 的安全编码。该 Key 只用于文件定位，不得成为新的 Dataset Identity 算法。

#### Scenario: 发布共用 Schema Facts

- **WHEN** 使用现有 Schema Evidence 生成 Schema Facts
- **THEN** 系统 SHALL 发布一个共用 Manifest、表索引和按表分开的事实目录，且不同 Task 或路线 SHALL 读取同一份表事实

#### Scenario: 下游路线筛选

- **WHEN** OPTION、TRS、KS-TRS 或 FAST-TRS 需要盘点涉及的表
- **THEN** 下游 SHALL 根据已有 Task/Lineage Facts 的 `guid`、`dataset_id` 或 `field_id` 筛选共用 Schema Facts，不得要求 Schema Facts 为每条路线复制一份

#### Scenario: 发布失败或证据不足

- **WHEN** 某张表的 Schema Evidence 不可用或 Projection 无法完整发布
- **THEN** Manifest SHALL 记录非成功状态或表级缺口，不得将缺失证据伪装成完整物理 Schema

### Requirement: Table Metadata identity and index

Table Fact SHALL 优先复用现有 Schema Evidence/`schema-refs.jsonl` 中的 `guid` 作为数综 Metadata 表对象身份，不得新增平行的 `meta_id` 身份。`guid` SHALL 只表示 Metadata 对象身份，不得替代现有 `dataset_id` 或参与 `dataset_id`/`field_id` 算法。完整的 `metadata_qualified_name` SHALL 表示当前物理对象的 Metadata 限定名；`dataset_id` SHALL NOT 作为 Schema Facts 的目录身份。

每张表 SHALL 生成 `tables/<table_storage_key>/table.json` 和 `tables/<table_storage_key>/columns.jsonl`。没有 `guid` 的表 SHALL 继续按完整 `metadata_qualified_name` 或 `logical_source_id + qualified_name` 定位；系统不得伪造 GUID。

#### Scenario: 使用现有 GUID 定位表

- **WHEN** Schema Evidence 为 `odata_n_tit.d_ref_otc_option_deal` 提供 Metadata `guid`
- **THEN** 表事实 SHALL 使用该 `guid` 作为 Table Storage Key，并继续保留既有 `dataset_id`、`qualified_name` 和 `logical_source_id`（如果已有 Task/Lineage Facts 提供）

#### Scenario: 未注册 GUID 但存在物理限定名

- **WHEN** 表没有 Metadata `guid`，但存在 `odata_n_tit.some_table@gfhive` 这样的完整 `metadata_qualified_name`
- **THEN** 表事实 SHALL 使用该限定名的安全编码作为 Table Storage Key，并将 GUID 保持为空或标记为不可用

#### Scenario: GUID 不改变 Machine Facts 身份

- **WHEN** 同一表的 Metadata GUID、DDL 或注释发生变化
- **THEN** 现有 `dataset_id`/`field_id` 规则 SHALL 保持不变，除非 `logical_source_id` 或 Canonical `qualified_name` 本身发生变化

#### Scenario: GUID 和完整限定名均缺失

- **WHEN** 表记录没有 Metadata GUID
- **THEN** 系统 SHALL 使用 `logical_source_id + qualified_name` 的安全编码作为回退 Key，保留状态和缺口原因，并 SHALL NOT 生成虚假的 GUID

### Requirement: Table-level physical facts

每张表的 `table.json` SHALL 能表达以下物理事实（证据存在时提供）：

- `guid`、`logical_source_id`、`dataset_id`、`qualified_name`；
- 当前数据库 `database_name`；
- Metadata 当前物理限定名 `metadata_qualified_name`；
- `object_type`、表状态和表注释；
- 表注释的 `comment_status` 和 `comment_reason_code`；
- 规范化的 `partition_spec`；
- `ddl_observation_status`、`ddl_reason_code`、`ddl_sha256`、稳定的 `ddl_ref`；
- `observed_source_refs[]`（已有 Metadata 明确提供时）；
- `evidence_refs[]`。

`database_name` SHALL 优先来自 Metadata/DDL 明确提供的数据库属性，不得仅凭字符串分割推断。`metadata_qualified_name` SHALL 复用现有 Schema Reference 语义。

#### Scenario: 记录当前数据库和 Metadata 限定名

- **WHEN** Metadata 明确返回当前表数据库 `odata_n_tit` 和限定名 `odata_n_tit.d_ref_otc_option_deal@gfhive`
- **THEN** `table.json` SHALL 同时记录 `database_name`、现有 Canonical `qualified_name` 和 `metadata_qualified_name`，且不得将 `logical_source_id` 当作数据库名

#### Scenario: 表注释状态

- **WHEN** 证据成功取得但表没有注释，或证据根本无法取得
- **THEN** 系统 SHALL 分别记录 `comment_status=ABSENT` 或 `comment_status=UNAVAILABLE`，并保留相应原因

#### Scenario: 观察到来源映射

- **WHEN** Metadata 明确返回 `TITANS_DM.REF_OTC_OPTION_DEAL@gforacle_gftzdb#gftzdb` 作为当前表的来源对象
- **THEN** `table.json` MAY 写入 `observed_source_refs[]`，其关系类型 SHALL 为 `OBSERVED_SOURCE_MAPPING`，且不得将其表述为完整 Lineage

### Requirement: Column-level physical facts

每张表的 `columns.jsonl` SHALL 一行表示一个被 Schema Evidence 观察到的物理字段。每条字段事实 SHALL 包含 `table_guid`（有 GUID 时）、`dataset_id`、与现有规则兼容的 `field_id`、`column_name`、`ordinal_position`，并在证据存在时保留 `data_type`、`column_comment`、`raw_definition`、`is_partition_column`、`partition_ordinal` 和 `evidence_refs[]`。

字段注释 SHALL 至少区分 `OBSERVED`、`ABSENT`、`UNAVAILABLE`，并在非 `OBSERVED` 时提供 reason code。字段事实 SHALL 描述物理观察结果，不得根据字段名或注释确认业务语义、主键、候选键、粒度或基数。

`partition_spec` SHALL 是表级分区的规范表达；字段级分区标志和序号 SHALL 与之保持一致，不得维护互相独立的分区真值。

#### Scenario: 记录字段注释和定义

- **WHEN** DDL 观察到字段 `dynamic_notional`、其类型、顺序、原始定义和注释 `动态名义本金`
- **THEN** `columns.jsonl` SHALL 保留这些物理属性及证据引用，并 SHALL NOT 将注释升级为业务语义确认

#### Scenario: 记录字段缺口

- **WHEN** 表存在但字段 DDL/Metadata 不可用
- **THEN** 系统 SHALL 保留表级状态和字段缺口，或输出带 Gap 的状态，不得生成看似完整的字段记录

### Requirement: Evidence and publication boundaries

完整 DDL SHALL 继续保留在已有 Schema Evidence/Snapshot 中；Table Fact SHALL 通过 `ddl_sha256` 和稳定 `ddl_ref` 回溯 DDL，Projection 不得复制完整 DDL 到每个表或字段目录。所有引用 SHALL 不依赖本机绝对路径。

Schema Facts Projection V1 SHALL NOT 生成或确认 PRIMARY KEY、UNIQUE、FOREIGN KEY、CHECK、Candidate Key、Grain、Cardinality、业务口径、Semantic Review 或完整 Lineage。Task/路线范围、消费关系和字段加工关系 SHALL 由其他 Machine Facts 或下游 Projection 表达。

#### Scenario: DDL 含有潜在约束

- **WHEN** DDL 文本包含可能表示约束的语句
- **THEN** V1 SHALL 只保留 DDL 证据引用，不得额外生成约束事实或 Grain/Cardinality 结论

#### Scenario: 来源映射不参与身份

- **WHEN** 当前 Hive 表观察到一个或多个 Oracle 来源对象
- **THEN** `observed_source_refs[]`、`metadata_qualified_name` 和 `database_name` SHALL 不改变 `dataset_id` 或 `field_id`
