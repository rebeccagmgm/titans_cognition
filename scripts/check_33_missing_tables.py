# -*- coding: utf-8 -*-
"""快速验证：33 个测试库无同名的数综源表，其表名在测试库是否存在于其他 schema。"""
import csv

lib = list(csv.DictReader(open("output/full-library-table-inventory-20260815/full-library-objects.csv", encoding="utf-8-sig")))

targets = [
    "BK_BOOK", "REF_COUNTERPARTY", "REF_COUNTER_PARTY", "REF_PORTFOLIO",
    "REF_PORTFOLIO_ELEMENT", "REF_QFII_PRODUCT_INFO", "TRD_DEAL", "OPE_SETTLE_NOTICE",
    "EQ_EQUITY_SOURCE", "REF_DIV_CURVE_DEF", "REF_INSTRUMENT_WIND_CURVE",
    "TRD_BOOK_MAPPING", "GPU_MA_EOD_CROSS_METRIC", "PRICING_BUCKET_METRIC",
]
for t in targets:
    hits = [(r["schema_name"], r["object_type"]) for r in lib if r["object_name"].upper() == t]
    msg = hits if hits else "测试库无"
    print(f"{t:32s} -> {msg}")
