---
status: accepted
---

# V1采用文件优先认知结果包

V1使用Parquet/JSON/YAML承载类型化事实、派生观察、认知候选、证据和评审，并由DuckDB本地分析；不引入PostgreSQL、图数据库或Catalog平台。当前目标是验证TRADEFLOW认知重建方法，尚无持续更新、并发评审、API或多源治理需求，先建长期存储会让平台设计先于结果价值验证。
