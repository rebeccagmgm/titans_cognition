## Why

现有 Schema Snapshot 和 Task Bundle 已保留部分 DDL、表描述、字段定义、分区、`guid` 和证据引用，但 `schema-refs.jsonl` 主要服务 SQL 任务解析，无法作为稳定的物理 Schema 查询入口。需要把这些证据整理成一个共用的 Physical Schema Facts Projection，支持表字段盘点、四条路线的字段溯源和后续 Grain/Cardinality 研究。

该 Projection 本身不是按任务或路线生成的结果，而是数综当前物理表的共用事实目录。数综已有的 `guid` 在有值时可以定位 Metadata 表对象；未注册 GUID 的表则使用完整 `metadata_qualified_name`，再以 `logical_source_id + qualified_name` 回退。因此不需要新增 `meta_id`，也不需要用 Schema Bundle 或 Scope Hash 构造目录身份。

## What Changes

- 新增共用 `schema-facts` Projection，目录包含一个总 Manifest、一个表索引以及按稳定 Table Storage Key 分开的表事实目录。
- 每张表单独保存表级事实和字段级事实，避免不同表和不同事实粒度混在同一文件中。
- 复用现有 `guid`、`logical_source_id`、`field_id`、`qualified_name` 和 `metadata_qualified_name` 语义；`dataset_id` 只作为已有 Task/Lineage Facts 的关联字段，不作为 Schema Facts 目录身份。
- 在表事实中保存当前数据库、Metadata 限定名、表注释、分区、DDL Hash/引用、表状态和证据引用。
- 在字段事实中保存字段顺序、类型、字段注释、原始定义、分区属性、字段身份和证据引用。
- 对已有 Metadata 明确返回的来源对象保留 `observed_source_refs[]`，但只表示观察到的来源映射，不表示完整 Lineage。
- Schema Facts 不绑定 OPTION/TRS/KS-TRS/FAST-TRS 或某组 Task；路线和 Task 在下游消费时通过 `guid`、`dataset_id`、`field_id` 筛选。
- V1 不新增约束事实、不推断 Candidate Key、Grain、Cardinality、业务语义或 Semantic Review。

## Capabilities

### New Capabilities

- `schema-facts-projection`: 从现有 Schema Evidence 生成共用、可查询、按数综 `guid` 分表的表级和字段级 Physical Schema Facts。

### Modified Capabilities

无。

## Impact

- 新增 `machine-facts/projections/schema-facts/` 下的共用派生产物和查询入口。
- 需要与现有 Schema Snapshot、`schema-refs.jsonl`、Dataset/Physical Field Identity 和 `field-expression-nodes` 兼容。
- 需要用 OPTION `86840`、TRS `86841`、KS-TRS `86842`、FAST-TRS `220650` 做垂直切片验证，但这些路线只作为验证消费者，不成为 Schema Facts 的存储范围。
- 不查询业务数据、不执行调度、不写入源系统、不引入外部服务或数据库。
