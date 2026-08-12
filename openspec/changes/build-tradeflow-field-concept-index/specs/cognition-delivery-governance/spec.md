## MODIFIED Requirements

### Requirement: 规模化必须获得独立授权

项目 SHALL NOT 启动 TRADEFLOW 全量 Deep Scale、全量 Identity/Grain/Role/Relation 深推断、正式业务语义、正式本体或方法泛化，除非读者交付已经存在、业务验收已经通过，并且用户对该次扩展作出明确授权。

项目 MAY 在独立 OpenSpec Change 中，于业务全貌交付前明确授权仅用于形成调查入口的有界候选分类基础或字段概念候选索引。每项例外授权必须固定输入范围、方法、Token 预算、资源保护上限、停止条件、Candidate/Conflict/Unknown 边界和数据外发门；资源保护上限仅防止意外计算爆炸，不得被当作节省本地计算时间的结果截断目标。它 SHALL NOT 自动提升 `reader_delivery`、`business_acceptance` 或一般性 `scale_authorization`，也 SHALL NOT 自动扩大到其他 Schema、证据源、正式本体或其他深度推断任务。

#### Scenario: 工程门通过但业务验收未通过

- **WHEN** 物理和结构工程门均通过，而业务验收仍未通过，且没有独立授权的交付前有界 Change
- **THEN** 规模化授权 SHALL 保持禁止，后续工作 SHALL 仅限于修正目标、证据、交付或验收缺口

#### Scenario: 用户授权有界候选分类基础

- **WHEN** 用户通过独立 Change 明确批准固定 Wiki 种子、指定 Panorama 范围、候选族发现和单次候选分类传播
- **THEN** 项目 MAY 实现该 Change 明确列出的有界分类能力，但 SHALL 继续报告业务全貌未交付、业务未验收，并 SHALL 禁止未列入 Change 的 Deep Scale 和方法泛化

#### Scenario: 用户授权 TRADEFLOW 字段概念候选切片

- **WHEN** 用户通过独立 Change 明确批准仅对固定 Physical Facts 中数字后缀过滤后的 233 张 `TITANS_TRADEFLOW` 表运行字段概念发现、限定词拆分、上下文消歧、Gold Cases 和最小双向索引
- **THEN** 项目 MAY 实现该字段概念候选切片，但 SHALL 保持另外 244 张表范围外、不得读取列值、不得建立正式本体或标准字段、不得扩展其他 Schema，并 SHALL 继续报告业务验收与一般规模化未完成

#### Scenario: 有界字段索引产生高覆盖候选

- **WHEN** 字段概念切片为大量字段产生候选概念或双向链接
- **THEN** 项目 SHALL 将结果报告为 TRADEFLOW 范围内的调查索引和候选覆盖，不得据此宣称业务真值、正式数据标准、跨 Schema 泛化或业务全貌完成
