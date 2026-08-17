# -*- coding: utf-8 -*-
"""检查 8 个"仅 dpl"源表是否出现在 ods-source-mapping-final-v2.csv 中。"""
import csv

ONLY_DPL = [
    ("TITANS_DM", "ADM_EMPLOYEE"),
    ("TITANS_DM", "BK_BOOK_INVESTMENT_PURPOSE"),
    ("TITANS_DM", "KS_LEG_INFO"),
    ("TITANS_DM", "MKT_OTC_PROD_VALUATION_SOURCE"),
    ("TITANS_DM", "POS_CAL_SF_PNL"),
    ("TITANS_DM", "REF_INVESTMENT_ACCOUNT"),
    ("TITANS_DM", "REF_INVESTMENT_MANAGER"),
    ("TITANS_STATICDATA", "REF_COUNTERPARTY"),
]

rows = list(csv.DictReader(
    open('output/titans-collection-20260815/data/ods-source-mapping-final-v2.csv', encoding='utf-8-sig')))
print('final-v2 总行数:', len(rows))

# 1) 8 个源表是否出现在 source 列
src_pairs = set()
for r in rows:
    if r.get('source_schema') and r.get('source_table'):
        src_pairs.add((r['source_schema'].upper(), r['source_table'].upper()))
print('\n== 8 个仅 dpl 源表在 source 列出现情况 ==')
for s, t in ONLY_DPL:
    hit = (s, t) in src_pairs
    # 也查单表名（忽略 schema 差异）
    hit_name = any(t == x[1] for x in src_pairs)
    print(f'  {s}.{t}: source列={hit}, 仅表名命中={hit_name}')

# 2) odata 侧有没有命名上相似的表（说明"采了但命名不同"还是"没采"）
print('\n== odata 侧命名相近的 ODS 表 ==')
targets = {
    'ADM_EMPLOYEE': ['adm_employee', 'adm_emp'],
    'BK_BOOK_INVESTMENT_PURPOSE': ['bk_book_investment_purpose', 'book_investment'],
    'KS_LEG_INFO': ['ks_leg_info', 'ks_leg'],
    'MKT_OTC_PROD_VALUATION_SOURCE': ['mkt_otc_prod_valuation_source', 'prod_valuation'],
    'POS_CAL_SF_PNL': ['pos_cal_sf_pnl', 'sf_pnl'],
    'REF_INVESTMENT_ACCOUNT': ['ref_investment_account'],
    'REF_INVESTMENT_MANAGER': ['ref_investment_manager'],
    'REF_COUNTERPARTY': ['ref_counter_party', 'ref_counterparty'],
}
ods_names = [r['ods_table'].lower() for r in rows]
for t, kws in targets.items():
    found = [n for n in ods_names if any(k in n for k in kws)]
    print(f'  {t}: {"、".join(found) if found else "（odata_n_tit 无命名相近表）"}')
