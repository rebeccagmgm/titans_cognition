# -*- coding: utf-8 -*-
"""查 final-v2 中几个疑点 ODS 表的源标注。"""
import csv

rows = list(csv.DictReader(
    open('output/titans-collection-20260815/data/ods-source-mapping-final-v2.csv', encoding='utf-8-sig')))
targets = ('a_adm_employee', 'd_ref_counterparty', 'd_ref_counterparty_p',
           'd_ref_counterparty_pb', 'd_ref_counter_party', 't_ref_counter_party')
for r in rows:
    if r['ods_table'] in targets:
        print(f"{r['ods_table']} | 源: {r.get('source_schema')}.{r.get('source_table')}"
              f" | match: {r.get('match')} | evidence: {r.get('evidence')}"
              f" | note: {(r.get('note') or '')[:50]}")
