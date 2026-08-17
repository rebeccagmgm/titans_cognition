# -*- coding: utf-8 -*-
"""提取名义本金(reader:notional)全部属性表达清单。

输入:
  - stage5/reader-notional-*.js  (用户记忆的 30 表达/55字段/19表)
  - stage6/reader-notional-*.js  (完整版 63 表达/118字段/34表)
输出:
  - notional-expressions.json / .csv  (按表达聚合)
  - notional-fields.json / .csv       (按字段实例展开)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output" / "notional-lineage-20260816"
OUT.mkdir(parents=True, exist_ok=True)

SHARDS = {
    "stage5": ROOT
    / "output/stage5-tradeflow-semantic-navigation-v1-20260813/semantic-navigation-review/data/concepts/reader-notional-4d3b0fce6f.js",
    "stage6": ROOT
    / "output/stage6-tradeflow-full-field-governed-map-v3-final-20260814/semantic-navigation-review/data/concepts/reader-notional-4d3b0fce6f.js",
}


def load_shard(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    m = re.search(r"window\.SEMANTIC_NAV_SHARDS=\[\"reader:notional\"\]=\{(.*)\};?$", raw, re.S)
    if not m:
        m = re.search(r"window\.SEMANTIC_NAV_SHARDS=window\.SEMANTIC_NAV_SHARDS\|\|\{\};window\.SEMANTIC_NAV_SHARDS\[\"reader:notional\"\]=\{(.*)\};?$", raw, re.S)
    if not m:
        raise ValueError(f"无法解析 shard: {path}")
    return json.loads("{" + m.group(1) + "}")


def main() -> None:
    all_expressions: list[dict] = []
    all_fields: list[dict] = []
    for stage, path in SHARDS.items():
        data = load_shard(path)
        concept = data["concept"]
        print(
            f"[{stage}] 表达={concept['expressionCount']} 字段={concept['fieldCount']} 表={concept['tableCount']}"
        )
        for expr in data.get("expressions", []):
            label = expr.get("label", "")
            qualifiers = [
                f"{q.get('dimension','')}={q.get('value','')}" for q in expr.get("qualifiers", [])
            ]
            for group in expr.get("physicalGroups", []):
                col_name = group.get("name", "")
                for inst in group.get("instances", []):
                    assignment_modes = [
                        a
                        for a in inst.get("readerAssignments", [])
                        if a.startswith("reader:notional:")
                    ]
                    mode = "DIRECT" if any("DIRECT" in a for a in assignment_modes) else (
                        "CONTEXT" if assignment_modes else "UNKNOWN"
                    )
                    all_fields.append(
                        {
                            "stage": stage,
                            "expression_label": label,
                            "qualifiers": ";".join(qualifiers),
                            "column_name": col_name,
                            "schema": inst.get("schema", ""),
                            "table": inst.get("table", ""),
                            "column_comment": inst.get("fieldComment", ""),
                            "table_comment": inst.get("tableComment", ""),
                            "data_type": inst.get("dataType", ""),
                            "assignment_mode": mode,
                            "conflict_types": ";".join(inst.get("conflictTypes", [])),
                            "unresolved_codes": ";".join(inst.get("unresolvedCodes", [])),
                        }
                    )
            all_expressions.append(
                {
                    "stage": stage,
                    "expression_label": label,
                    "qualifiers": ";".join(qualifiers),
                    "field_count": expr.get("fieldCount", 0),
                    "table_count": expr.get("tableCount", 0),
                    "support_status": expr.get("supportStatus", ""),
                    "conflict_types": ";".join(
                        t for c in expr.get("conflicts", []) for t in c.get("types", [])
                    ),
                    "uncertainty_codes": ";".join(
                        ";".join(u.get("codes", [])) for u in expr.get("uncertainties", [])
                    ),
                }
            )

    with (OUT / "notional-expressions.json").open("w", encoding="utf-8") as fh:
        json.dump(all_expressions, fh, ensure_ascii=False, indent=2)
    with (OUT / "notional-fields.json").open("w", encoding="utf-8") as fh:
        json.dump(all_fields, fh, ensure_ascii=False, indent=2)

    import csv

    with (OUT / "notional-expressions.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(all_expressions[0].keys()))
        w.writeheader()
        w.writerows(all_expressions)
    with (OUT / "notional-fields.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(all_fields[0].keys()))
        w.writeheader()
        w.writerows(all_fields)

    # 摘要
    stage6_fields = [f for f in all_fields if f["stage"] == "stage6"]
    direct = [f for f in stage6_fields if f["assignment_mode"] == "DIRECT"]
    ctx = [f for f in stage6_fields if f["assignment_mode"] == "CONTEXT"]
    tables = sorted({(f["schema"], f["table"]) for f in stage6_fields})
    print(f"\nstage6 字段实例: {len(stage6_fields)} (DIRECT={len(direct)}, CONTEXT={len(ctx)})")
    print(f"涉及表: {len(tables)} 张")
    for s, t in tables:
        cols = sorted({f["column_name"] for f in stage6_fields if f["schema"] == s and f["table"] == t})
        print(f"  {s}.{t}: {len(cols)} 字段 -> {', '.join(cols)}")
    print(f"\n[已保存] {OUT}")


if __name__ == "__main__":
    main()
