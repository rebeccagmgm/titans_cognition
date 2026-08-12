# OTC 交易—合约—持仓主线（读者草稿）

> 状态：DRAFT / 待业务确认
>
> 本稿把已确认的物理事实、Wiki 中的实现关联和仍未确认的业务解释分开。它不是正式业务定义，也不代表已经完成 TITANS 业务全貌交付。

## 1. 读者要回答的问题

当一个 OTC 交易进入系统后，读者希望知道：

1. 哪个物理对象承载交易主记录？
2. 合约参数、合约属性和保证金参数在哪里承载？
3. 存续期事件如何记录，并如何影响持仓或持仓明细？
4. 期权合约与互换合约如何关联？
5. 哪些关系是数据库声明事实，哪些只是实现关联或待确认候选？

## 2. 当前可支持的主线

### 2.1 交易与合约承载

`TRD_OTC_TRADE` 的物理注释是“交易-OTC—交易表（父类）”，存在主键 `KEY_OTC_TRADE_ID`，并有 `INTERNAL_TRADE_ID`、`KEY_INSTRUMENT_ID` 等字段。

围绕该对象，当前 Panorama 中还存在：

- `TRD_OTC_CONTR_PROPS`：合约属性
- `TRD_OTC_CONTR_FILES`：合约文件
- `REF_OTC_OPTION_DEAL`：期权交易/合约明细候选
- `REF_OTC_CONTR_MARGIN_PARAM`：合约静态履约保证金参数

Wiki 页面《从综合业务平台导入期权合约》（pageId `150715552`）给出了实现层面的对象链：先按 `KEY_INSTRUMENT_ID` 或 `INTERNAL_TRADE_ID` 找到交易/合约，再按 `KEY_OTC_TRADE_ID` 访问合约属性、文件、保证金参数和期权明细。该页面支持“实现关联存在”的判断，但不等同于当前数据库已声明 FK。

### 2.2 存续期事件与持仓

`TRD_OPTION_EVENT` 的物理注释是“交易-OTCOption存续期事件表”，主键由 `KEY_OPTION_EVENT_ID`、`KEY_OPTION_DEAL_ID`、`EVENT_TYPE` 组成；字段中包含事件日期、事件状态、事件金额和事件描述。

`POS_MAIN_CONTR_EVENT_OPEN_QTY` 的物理注释是“主合约持仓明细”，唯一键包含 `KEY_OTC_TRADE_ID`、`KEY_EVENT_ID`、`EVENT_DATE` 和 `EXIST_KEY_EVENT_ID`。这支持“交易/事件与持仓明细之间存在结构化衔接线索”，但仍不证明完整业务生命周期。

对 TRS 方向，当前物理事实包括：

- `TRD_TRS_EVENT`
- `TRD_TRS_EVENT_STRUC_DETAIL`
- `POS_TRS_LEG_CURRENT_POS`
- `POS_TRS_LEG_HIS_POS`
- `REF_TRS`
- `REF_TRS_LEG`

Wiki 页面《1_多表关联总结》（pageId `310187749`）列出开仓、平仓、部分平仓和持仓查询 Mapper，涉及交易表、TRS 事件、结构化腿明细、TRS/腿定义、当前持仓和保证金参数。它是实现关联证据，不是业务人员确认的生命周期定义。

### 2.3 期权与互换合约关系

`REF_OPTION_MARGIN_TRS_RELATION` 的字段包括：

- `OPTION_KEY_OTC_TRADE_ID`
- `TRS_KEY_OTC_TRADE_ID`
- `STATUS`

因此可以提出“期权合约与互换合约之间存在关系表承载”的结构候选。当前未发现该对象与其他对象之间的 Oracle FK 或独立 Dependency 事实，关系方向、有效状态含义和业务使用时机仍需进一步确认。

## 3. 证据分层

| 结论 | 当前证据 | 当前等级 | 边界 |
|---|---|---|---|
| `TRD_OTC_TRADE` 是 OTC 交易主承载对象候选 | 表注释、主键、字段注释、DDL | DECLARED + COMMENT | “主承载”仍是读者解释，不是正式业务定义 |
| 合约相关对象按 `KEY_OTC_TRADE_ID` 组织 | Panorama 字段事实、Wiki 实现 SQL | MODERATE | Wiki 描述的是实现关联，需核对当前实现版本 |
| 存续期事件会进入事件/结构明细/持仓查询链 | Wiki Mapper 清单、对象和字段事实 | MODERATE | 尚未确认触发条件、状态迁移和责任系统 |
| 当前/历史持仓是不同物理承载 | 表注释、对象名、DDL | DECLARED + COMMENT | 尚未做业务口径和时间边界确认 |
| 期权与互换通过关系表关联 | 关系表注释、字段和唯一键 | DECLARED | 关系方向和业务含义仍是候选 |

## 4. 必须保留的 Unknown

- `OTC_OPTION_PARAMETER.ID`、`CONTRACT_NO` 与 `TRD_OTC_TRADE.KEY_OTC_TRADE_ID` 的正式对应关系。
- `KEY_INSTRUMENT_ID`、`INTERNAL_TRADE_ID` 和 `KEY_OTC_TRADE_ID` 在各系统中的身份层级。
- 事件类型、事件状态与开仓/平仓/部分平仓之间的完整状态变化。
- 当前持仓与历史持仓的切换时点、重算触发和数据责任系统。
- `REF_OPTION_MARGIN_TRS_RELATION.STATUS` 的有效性口径和失效处理。
- 以上对象是否覆盖用户所说的完整 OTC 交易—合约—持仓业务全貌。

## 5. 下一步验收问题

这份主线只有在读者能够确认以下问题后，才可以进入正式业务交付：

1. `TRD_OTC_TRADE` 是否确实是该业务主线的交易主对象？
2. 合约参数、合约属性、保证金参数和期权明细是否应作为同一合约对象的组成部分？
3. 事件和持仓之间的关系是否按当前草稿描述？
4. 期权—互换关系表是否代表业务关系，还是仅为技术映射？
5. 当前草稿是否能帮助读者定位一次真实业务问题，并下钻到表、粒度、键和证据？

## 6. 当前结论

可以开始制作读者交付，但目前只能交付为“证据分层的业务主线草稿”。在完成上述业务确认前，不应把它升级为正式业务对象、完整生命周期或全量业务全貌。
