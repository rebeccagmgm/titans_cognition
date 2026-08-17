## Context

See `proposal.md` and `specs/tag-catalog-visualization/spec.md`. 当前标签快照位于独立的 OpenCLI 输出目录，包含 `dimension-details.jsonl`、`catalog-tree.json`、`detail-manifest.json` 和 `dimension-sql/`。现有目录数据虽然保存了 `segments` 字段，但实际把完整路径作为单一段，不能直接作为读者树使用。

## Goals / Non-Goals

**Goals:**

- 建立从固定标签快照到静态阅读页面的单向、可重复投影。
- 在目录节点、标签叶子和右侧详情之间保持清晰分层。
- 让 SQL 成为可核验的证据附件，并显式区分 `FOUND` 与 `GENERATED_LOCAL`。
- 让输入校验、来源哈希、未归类标签和不可用字段都可见。

**Non-Goals:**

- 不接入调度任务 SQL、任务日志、SQL 执行或业务数据行。
- 不把标签目录当作业务语义分类或正式指标/标签治理结果。
- 不修改现有指标目录页面、SZData 源数据或快照生成逻辑。

## Decisions

### 1. 使用独立的标签投影入口

标签页面由显式的快照输入和输出参数驱动，不嵌入指标目录生成器，也不依赖 Cognition 的语义导航 Change。这样可以保持标签资产目录与指标目录、业务语义地图各自的来源责任。

### 2. 以 `dimension-details.jsonl` 为详情主表

目录树只负责提供导航；标签详情、SQL 元数据和证据状态统一从标签详情记录读取。`catalog-tree.json` 可作为校验或辅助输入，但不能覆盖详情记录中的源字段。

### 3. 按显式路径分隔规则构建树

生成器 SHALL 先确认快照的目录路径分隔规则，再逐段构建目录节点；不能无条件按标签名称、下划线或词法相似度猜测目录层级。无法安全拆分的路径进入保留原文的待确认/未归类分支。

### 4. SQL 使用受控文件链接和安全展示

页面嵌入或链接的 SQL 必须来自快照声明的 `sqlFile`，并通过路径范围校验、文件存在性校验和 SHA-256 校验。页面同时展示 SQL 证据状态；不会从任务号或目录名称推导任务 SQL。

### 5. 快照范围的静态投影

输出使用快照标识隔离，并写入投影 manifest。生成失败时不替换旧的完整输出；成功后页面、manifest 和输入哈希共同构成一次可审计的投影。

## Risks / Trade-offs

- [Risk] 目录路径的分隔符或编码不稳定，拆分后可能产生错误层级 → Mitigation：把路径解析规则作为输入校验和测试样例，无法确认时保留原路径并标记待确认。
- [Risk] 本地生成 SQL 被误认为平台定义 → Mitigation：详情和 SQL 区域强制显示证据状态，`GENERATED_LOCAL` 不得使用 `FOUND` 文案。
- [Risk] 数千条标签和 SQL 使单页过大 → Mitigation：首版保持快照级静态页面，测量文件大小和浏览器响应；只有真实读者验证显示性能不足时再考虑分片。
- [Risk] 标签目录被误解为业务分类 → Mitigation：页面显示快照时间、来源和“目录为平台快照字段”的边界说明，不发布未经审核的业务语义结论。

## Migration Plan

1. 使用现有标签快照生成第一版投影，并核对标签总数、目录节点数、未归类记录和 SQL 文件哈希。
2. 对代表性多级目录、无目录、`FOUND` SQL、`GENERATED_LOCAL` SQL 和缺失 SQL 进行读者检查。
3. 通过独立 surrogate review 后再将页面作为标签目录入口使用；旧快照和旧页面保持不变。
4. 回滚时停止生成或链接新投影即可，不删除源快照。

## Open Questions

- 调度任务 SQL 是否作为后续独立 Change 纳入，需基于任务关系快照的完整性另行决定。
