---
status: accepted
---

# LLM只作为受证据约束的语义分析器

主流水线由Python确定性编排。V1B先建设Canonical Evidence闭环；V1C才由官方基础SDK读取从Canonical Evidence裁剪的有限Evidence Pack，并输出经过Schema和Evidence ID校验的语义候选或Abstain动作。不使用Agent框架让模型自主访问Oracle、修改事实或接受候选。这样保留LLM在命名、消歧和语义提炼上的价值，同时确保无LLM路线可运行、模型错误可隔离、数据外发可控制。
