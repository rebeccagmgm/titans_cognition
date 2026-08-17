# -*- coding: utf-8 -*-
"""对比 dpl 库 tit_* 表与 odata_n_tit 采集的源表重叠度。"""
import json
import csv
import re

dpl_tables = json.load(open('output/titans-collection-20260815/data/dpl_tables.json', encoding='utf-8'))
tit = [t for t in dpl_tables if t.get('name', '').startswith('tit_titans_')]

def parse_src(name):
    m = re.match(r'tit_titans_([a-z0-9_]+?)_(.+)$', name, re.I)
    if m:
        return f'TITANS_{m.group(1).upper()}.{m.group(2).upper()}'
    return ''

dpl_src = {}
for t in tit:
    s = parse_src(t['name'])
    if s:
        dpl_src.setdefault(s, []).append(t['name'])
print('dpl 覆盖源表数:', len(dpl_src))

rows = list(csv.DictReader(open('output/titans-collection-20260815/data/ods-source-mapping-v2.csv', encoding='utf-8-sig')))
odata_src = set()
for r in rows:
    if r.get('source_schema'):
        odata_src.add(r['source_schema'].upper() + '.' + r['source_table'].upper())
print('odata 覆盖源表数:', len(odata_src))

overlap = set(dpl_src) & odata_src
only_dpl = set(dpl_src) - odata_src
print(f'双链路重叠: {len(overlap)} | 仅 dpl: {len(only_dpl)}')
for s in sorted(only_dpl):
    print('  仅dpl:', s, dpl_src[s])
