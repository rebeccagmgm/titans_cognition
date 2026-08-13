# Semantic Navigation Proposal v1

## Scope

This is a bounded prototype from the frozen TRADEFLOW semantic runs. It is a
navigation candidate, not a business-accepted taxonomy.

Observed input summary:

- 1,375 observed business-concept rows;
- 1,559 observed attribute-expression rows;
- 477 table profiles;
- 8,801 bounded Wiki candidates;
- 10 configurable OTC derivatives business areas;
- 9 reusable field-attribute axes plus an open axis.

## Projection contract

```text
OTC derivatives business navigation
├─ Participants
├─ Products and underlyings
├─ Inquiry, order and trade
├─ Contract and structure
├─ Contract lifecycle
├─ Position and risk
├─ Valuation, collateral and cashflow
├─ Execution, clearing and settlement
├─ Reference data and configuration
└─ Operations, reporting and data processing

Selected business concept
├─ Attribute expressions
├─ Field attributes
├─ Qualifier axes
├─ Business contexts / related concepts
├─ Physical implementations
└─ Unresolved queue by reason
```

The prototype publishes only configured business-area entries and concepts with
explicit area and evidence references. The business skeleton alone cannot
create a concept, field, relation, or physical implementation.

## Representative entries

| Concept | Navigation candidate | Attribute/detail projection | Current boundary |
|---|---|---|---|
| 名义本金 | 估值、履约保障与现金流 | 金额、时点、状态、币种、属性表达 | Candidate; requires review |
| 交易对手 | 参与主体 | 标识、名称、角色、状态 | Subject/role split required |
| 交易 / 订单 | 询价、订单与交易 | 标识、状态、方向、时间 | Object/event boundary required |
| 持仓 | 持仓与风险 | 标识、数量、方向、状态、时点 | Position versus snapshot measure requires review |
| 保证金 | 估值、履约保障与现金流 | 金额、币种、状态、时间 | Payment/event versus measure requires review |

## Explicit non-publication rules

- Wiki-only hierarchy is context evidence and is not published as business
  hierarchy.
- A role such as buyer/seller/甲方/乙方 is not automatically a new business
  subject.
- A suffix such as ID/编号/类型/状态 is a field-attribute signal, not a
  business concept by itself.
- Unknown concepts, unknown attributes, unknown qualifiers, relationship
  candidates, insufficient evidence and conflicts remain separately reviewable.
