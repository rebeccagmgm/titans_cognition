# -*- coding: utf-8 -*-
"""扫描数综模型层加工 SQL，定位引用名义本金贴源表的任务。

对 177 个 downstream-tasks-sql 文件:
  1) 正则提取每条语句的目标表(insert into / create table)
  2) 检查 FROM/JOIN 是否引用 8 张名义本金贴源表(odata_n_tit.d_*)
  3) 输出: 命中文件/目标表/引用贴源表/名义本金关键词命中

输出:
  - model-sql-hits.csv   命中加工任务明细
  - model-sql-hits.json
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = ROOT / "output/titans-collection-20260815/data/downstream-tasks-sql"
OUT = ROOT / "output/notional-lineage-20260816"

# 8 张名义本金贴源表(odata_n_tit)
ODS_TABLES = [
    "d_pos_fast_trs_leg_his_pos",
    "d_ref_fast_trs",
    "d_ref_fx_forward",
    "d_ref_option_deal_structure",
    "d_ref_otc_option_deal",
    "d_ref_trs",
    "d_trd_option_event",
    "d_trd_trs_event_p",
]
ODS_SET = {t.lower() for t in ODS_TABLES}

# 名义本金关键词(英文列名形态 + 中文注释)
KEYWORDS = re.compile(
    r"NOTIONAL|PRINCIPAL|名义本金|本金|NOM_|PRIN_|MXQSBJ|_NOTL_|CLEAR_PRINCIPAL", re.I
)

INSERT_RE = re.compile(
    r"insert\s+(?:overwrite\s+)?into\s+([a-zA-Z0-9_\.`\"\-]+)", re.I
)
CREATE_RE = re.compile(
    r"create\s+table\s+(?:if\s+not\s+exists\s+)?([a-zA-Z0-9_\.`\"\-]+)", re.I
)
# 表引用: from/join 后跟 可选的 库名. 表名(带反引号)
TABLE_REF_RE = re.compile(
    r"(?:from|join)\s+([a-zA-Z0-9_`\"\.\-]+)\s*", re.I
)

SQL_NAME_RE = re.compile(r"tasksql-(\d+)-")


def norm(name: str) -> str:
    n = name.strip().strip("`\"").lower()
    return n.split(".")[-1]


def main() -> None:
    hits = []
    files = sorted(SQL_DIR.glob("tasksql-*.txt"))
    for f in files:
        text = f.read_text(encoding="utf-8")
        task_id = SQL_NAME_RE.search(f.name).group(1) if SQL_NAME_RE.search(f.name) else ""
        # 目标表
        target = ""
        m = INSERT_RE.search(text)
        if m:
            target = norm(m.group(1))
        else:
            m = CREATE_RE.search(text)
            if m:
                target = norm(m.group(1))
        # 引用的表
        refs = [norm(m.group(1)) for m in TABLE_REF_RE.finditer(text)]
        ods_refs = sorted({r for r in refs if r in ODS_SET})
        if not ods_refs:
            continue
        # 名义本金关键词是否出现在文本
        kw_hits = len(KEYWORDS.findall(text))
        hits.append(
            {
                "sql_file": f.name,
                "task_id": task_id,
                "target_table": target,
                "ods_refs": ";".join(ods_refs),
                "notional_keyword_count": kw_hits,
                "sql_length": len(text),
            }
        )
    hits.sort(key=lambda r: (r["ods_refs"], r["target_table"]))
    with (OUT / "model-sql-hits.json").open("w", encoding="utf-8") as fh:
        json.dump(hits, fh, ensure_ascii=False, indent=2)
    with (OUT / "model-sql-hits.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(hits[0].keys()) if hits else [])
        w.writeheader()
        w.writerows(hits)

    # 摘要
    by_ods: dict[str, list] = {}
    for h in hits:
        for t in h["ods_refs"].split(";"):
            by_ods.setdefault(t, []).append(h)
    print(f"共扫描 {len(files)} 个任务 SQL，命中 {len(hits)} 个加工任务\n")
    for ods in sorted(by_ods):
        hs = by_ods[ods]
        targets = sorted({h["target_table"] for h in hs})
        print(f"◆ {ods}: {len(hs)} 个任务 -> 目标表: {', '.join(targets)}")
        for h in hs:
            print(f"    {h['sql_file']} -> {h['target_table']} (名义关键词x{h['notional_keyword_count']})")
    print(f"\n[已保存] {OUT / 'model-sql-hits.csv'}")


if __name__ == "__main__":
    main()
