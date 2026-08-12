## MODIFIED Requirements

### Requirement: 规模化必须获得独立授权

项目 SHALL NOT 启动 TRADEFLOW 全量 Deep Scale、全量 Identity/Grain/Role/Relation 深推断、Field Concept、正式业务语义或方法泛化，除非读者交付已经存在、业务验收已经通过，并且用户对该次扩展作出明确授权。

项目 MAY 在一个独立 OpenSpec Change 中，于业务全貌交付前明确授权仅用于产生读者入口的有界候选分类基础，但该授权必须固定输入范围、Wiki 页面、结构算法、LLM 外发门、运行预算、停止条件和 Candidate/Unknown 边界；它 SHALL NOT 自动提升 `reader_delivery`、`business_acceptance` 或一般性 `scale_authorization`，也 SHALL NOT 自动扩大到其他 Schema、证据源或深度推断任务。

#### Scenario: 工程门通过但业务验收未通过

- **WHEN** 物理和结构工程门均通过，而业务验收仍未通过，且没有独立授权的交付前候选分类 Change
- **THEN** 规模化授权 SHALL 保持禁止，后续工作 SHALL 仅限于修正目标、证据、交付或验收缺口

#### Scenario: 用户授权有界候选分类基础

- **WHEN** 用户通过独立 Change 明确批准固定 Wiki 种子、指定 Panorama 范围、候选族发现和单次候选分类传播
- **THEN** 项目 MAY 实现该 Change 明确列出的有界能力，但 SHALL 继续报告业务全貌未交付、业务未验收，并 SHALL 禁止未列入 Change 的 Deep Scale 和方法泛化

#### Scenario: 有界基础产生高覆盖候选

- **WHEN** 候选分类基础为大量对象生成了候选族或业务标签
- **THEN** 项目 SHALL 将结果报告为候选分类覆盖和调查入口，不得据此宣称业务全貌完成、业务真实性成立或一般规模化获得授权
