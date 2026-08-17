## 1. Bundle 投影适配

- [x] 1.1 实现 Task Bundle 到 GraphInputs 的确定性适配
- [x] 1.2 从 Bundle Relation 和字段表达式重建结构化读取、表达式馈入和任务数据集流边
- [x] 1.3 保留 Profile 声明边界和上游 Artifact/Manifest 引用

## 2. 路径 Projection

- [x] 2.1 接入现有 VALUE_FLOW / ROWSET_CONTROL 装配器
- [x] 2.2 写入独立 Projection JSON 和 projection-manifest.json
- [x] 2.3 明确 Projection 不修改 Canonical Task Bundle

## 3. 验证

- [x] 3.1 增加 Machine Facts Bundle 到最小路径的集成测试
- [x] 3.2 验证当前两条路径均为 COMPLETE 且整体 PASS
- [x] 3.3 运行 Machine Facts、指标图、最小路径和 OpenSpec 校验
