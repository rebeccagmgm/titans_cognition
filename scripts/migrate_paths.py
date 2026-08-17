# -*- coding: utf-8 -*-
"""批量迁移 scripts/*.py 中的路径引用：szdata-inventory-20260815 → titans-collection-20260815（data/stats 分家）。"""
import glob

OLD = "output/titans-collection-20260815/data"

# 精确映射：先长后短，先具体文件后目录
STATS_FILES = [
    "ods-source-mapping-summary.txt",
    "titans-collection-stats.txt",
    "titans-coverage-stats.txt",
    "titans-collection-report.html",
    "titans-coverage-report.html",
    "titans-extra-sinks-summary.md",
]
MAPPINGS = []
MAPPINGS.append((f"{OLD}/collection-analysis", "output/titans-collection-20260815/data/collection-analysis"))
for f in STATS_FILES:
    MAPPINGS.append((f"{OLD}/{f}", f"output/titans-collection-20260815/stats/{f}"))
MAPPINGS.append((OLD, "output/titans-collection-20260815/data"))

changed = []
for path in glob.glob("scripts/*.py"):
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    new = src
    for old, new_p in MAPPINGS:
        new = new.replace(old, new_p)
    if new != src:
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(new)
        changed.append(path)

print("已更新脚本:")
for c in changed:
    print(f"  {c}")
print(f"共 {len(changed)} 个")
