## Context

现有 Schema Evidence/Snapshot 已保存 DDL、表描述、字段原始定义、分区、`guid`、`qualified_name`、`metadata_qualified_name` 和 DDL Hash；现有 Task Bundle 的 `schema-refs.jsonl` 已证明 `guid` 能随表引用落下，但其字段内容仍偏薄，不能作为完整的物理 Schema 查询入口。

本次设计把 Schema Facts 定位为一个共用的当前物理事实目录，而不是按 Task 或路线生成的分析结果。Task/路线只在消费时通过现有 Machine Facts 身份筛选。Schema Facts 仍是派生 Projection，不是新的 Canonical Source。

## Goals / Non-Goals

**Goals:**

- 建立一个共用的物理 Schema Facts 目录。
- 使用已有 `guid` 优先定位数综 Metadata 表对象，并为未注册 GUID 的表提供物理限定名回退。
- 按表拆分表级和字段级事实，支持单表追溯和批量查询。
- 保持既有 `logical_source_id`、`dataset_id`、`field_id`、`qualified_name` 和 `metadata_qualified_name` 兼容。
- 补足数据库、表/字段注释、字段类型、原始定义、分区、DDL 和观察来源映射。

**Non-Goals:**

- 不使用 `schema_bundle_sha256` 或 `scope_sha256` 作为目录层或 Schema Facts 身份。
- 不按 OPTION/TRS/KS-TRS/FAST-TRS 生成四套 Schema Facts。
- 不把 Schema Facts 变成 Task Bundle 的副本。
- 不新增 `meta_id`、约束、候选键、Grain、Cardinality、业务语义或人工 Review。
- 不从 Metadata 来源映射推断完整 SQL/字段级 Lineage。

## Decisions

### 1. Schema Facts 是共用当前目录

采用：

```text
machine-facts/projections/schema-facts/
├─ manifest.json
├─ index.jsonl
└─ tables/
   └─ <table_storage_key>/
      ├─ table.json
      └─ columns.jsonl
```

不再按 Schema Snapshot Hash 或 Task Read Scope 创建目录。原因是该目录表达的是当前可共用的物理 Schema 事实，而不是某一批 Task 的分析输入。若未来需要保存 Snapshot 历史，应由 Snapshot 层负责，不把历史版本机制混入当前 Schema Facts Projection。

### 2. Table Storage Key 与 Dataset/Field Identity 分离

当前 `schema-refs.jsonl` 已有 `guid`、`qualified_name`、`metadata_qualified_name` 和 `ddl_sha256`。Projection 按以下优先级生成 Table Storage Key：

```text
guid
  → metadata_qualified_name 的安全编码
  → logical_source_id + qualified_name 的安全编码
```

该 Key 只负责物理文件定位，不是新的业务身份算法。

`guid` 是数综 Metadata 对象身份，不替换：

```text
dataset_id = existing logical_source_id + qualified_name rule
field_id   = existing field identity rule
```

没有 `guid` 的表仍然生成完整表事实；如果有完整 `metadata_qualified_name`，优先用它定位，否则使用 `logical_source_id + qualified_name`。`guid` 作为可选属性保留为空或标记不可用，不伪造 GUID。

`dataset_id` 不是 Schema Evidence 表记录的通用原始字段，不能被假定为所有 Schema Facts 的目录键。它只在已有 Task/Lineage Facts 中作为关联身份使用。

### 3. Manifest 和 Index 分工

`manifest.json` 只描述共用 Projection 的契约版本、发布状态、表/字段数量、文件列表、证据边界和生成方法，不承担 Task Scope 或 Snapshot Version 身份。

`index.jsonl` 一行一张表，包含 `guid`、`dataset_id`、`qualified_name`、事实路径、表状态和字段数量。它提供批量发现和按表定位入口，不复制完整表事实。

### 4. 表和字段分开存储

`table.json` 只保存一张表的表级事实；`columns.jsonl` 保存该表的字段事实。字段记录通过 `table_guid`（存在时）、`dataset_id` 和 `field_id` 关联表及现有字段表达式事实。

这样既避免把不同表混在一个文件中，也避免为每条字段记录重复保存数据库、表注释和 DDL 信息。

### 5. 观察来源映射受限表达

当 Metadata 明确返回来源对象时，在 `table.json` 中保留 `observed_source_refs[]`。固定关系类型为 `OBSERVED_SOURCE_MAPPING`，只表示平台观察到的映射，不表示完整加工血缘。该字段不参与任何 Dataset/Field Identity 计算。

### 6. 注释、DDL 和分区以物理证据为准

表/字段注释使用 `OBSERVED`、`ABSENT`、`UNAVAILABLE` 和原因区分。`database_name` 只接受 Metadata/DDL 明确提供的值。DDL 保留在现有 Evidence/Snapshot 中，Table Fact 只保存 `ddl_sha256`、`ddl_ref` 和证据引用。`partition_spec` 是表级唯一规范表达，字段级分区属性由其派生。

### 7. 四路线只作为验证消费者

用四条路线验证共用目录是否能支持：

- 按 `guid` 找到表；
- 按 `dataset_id`/`field_id` 关联字段表达式；
- 读取 `dynamic_notional` 等字段的物理注释和定义；
- 区分当前 Hive 数据库与观察到的 Oracle 来源映射。

四条路线不写入 Schema Facts 的 Scope，也不生成四份 Schema Facts。

## Risks / Trade-offs

- [表数量较多导致文件数量增加] → 每张表只保留一个表 JSON 和一个字段 JSONL，并用统一 `index.jsonl` 批量发现；当前范围优先保证对象边界和增量定位。
- [部分表没有 GUID] → 使用完整 `metadata_qualified_name` 或 `logical_source_id + qualified_name` 回退定位，不伪造 GUID；仍保留物理名称和缺口原因。
- [GUID 与 Dataset Identity 被混用] → 在 Contract、Index 和回归测试中同时保留并校验 `guid` 与 `dataset_id` 的不同职责。
- [来源映射被误读为完整血缘] → 固定 `OBSERVED_SOURCE_MAPPING` 并在 Manifest/文档中声明边界。
- [表/字段注释状态被压成 UNKNOWN] → 用 `ABSENT` 与 `UNAVAILABLE` 两条测试路径覆盖。
- [DDL 被重复复制] → DDL 只保留在 Evidence/Snapshot，事实中保存 Hash、引用和字段原始定义。

## Migration Plan

1. 保持现有 Task Bundle 和 `schema-refs.jsonl` 不变，新增共用 Schema Facts Projection。
2. 从已有 Schema Evidence 读取 `guid`、表名、Metadata 限定名、DDL Hash、字段原始定义和分区信息。
3. 生成共用 `manifest.json`、`index.jsonl` 和按 GUID 分表的 `table.json`/`columns.jsonl`。
4. 对没有 GUID 的记录输出明确缺口，不生成伪造表身份。
5. 用四条路线做垂直验证；验证失败时只停止发布 Schema Facts，不修改现有 Task Bundle 或源数据。
