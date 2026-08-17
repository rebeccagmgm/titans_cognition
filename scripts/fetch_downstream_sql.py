# -*- coding: utf-8 -*-
"""下游表 → Horae 任务 → 加工 SQL 全量落盘。

三阶段（各自断点续跑）：
  1) tables : 从 downstream-*.csv 去重下游表 -> downstream-tables.csv
  2) tasks  : 每张下游表 table-detail 拿 dbName/horaeTasks -> downstream-tables-tasks.csv
  3) sql    : 每个任务 task-sql --save-to 落盘 -> downstream-tasks-sql/

Usage:
    python scripts/fetch_downstream_sql.py tables
    python scripts/fetch_downstream_sql.py tasks
    python scripts/fetch_downstream_sql.py sql
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import time
from pathlib import Path

DATA = Path("output/titans-collection-20260815/data")
TABLES_CSV = DATA / "downstream-tables.csv"
TASKS_CSV = DATA / "downstream-tables-tasks.csv"
SQL_DIR = DATA / "downstream-tasks-sql"
SLEEP = 0.4


def run(cmd: list[str]) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, shell=True)
    return r.returncode, r.stdout.decode("utf-8", errors="replace")


def cmd_tables() -> None:
    """去重下游表清单。"""
    seen: dict[str, dict] = {}
    for f in ["downstream-odata.csv", "downstream-dpl.csv"]:
        p = DATA / f
        if not p.exists():
            print(f"跳过缺失输入: {f}")
            continue
        for r in csv.DictReader(p.open(encoding="utf-8-sig")):
            name = r.get("downstream_name", "")
            gid = r.get("downstream_guid", "")
            if name and gid and name not in seen:
                seen[name] = {"downstream_name": name, "downstream_guid": gid,
                              "downstream_type": r.get("downstream_type", "")}
    with TABLES_CSV.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["downstream_name", "downstream_guid", "downstream_type"])
        w.writeheader()
        for v in sorted(seen.values(), key=lambda x: x["downstream_name"]):
            w.writerow(v)
    print(f"去重下游表 {len(seen)} 张 -> {TABLES_CSV}")


def cmd_tasks() -> None:
    """每张下游表查 dbName + horaeTasks（断点续跑）。"""
    rows = list(csv.DictReader(TABLES_CSV.open(encoding="utf-8-sig")))
    done = set()
    if TASKS_CSV.exists():
        for r in csv.DictReader(TASKS_CSV.open(encoding="utf-8-sig")):
            done.add(r["downstream_name"])
    pending = [r for r in rows if r["downstream_name"] not in done]
    print(f"下游表 {len(rows)}，已完成 {len(done)}，待查 {len(pending)}")

    with TASKS_CSV.open("a" if TASKS_CSV.exists() else "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["downstream_name", "downstream_guid",
                                           "db_name", "horae_task_id", "horae_task_label",
                                           "probe_status"])
        if not TASKS_CSV.exists() or TASKS_CSV.stat().st_size == 0:
            w.writeheader()
        for i, r in enumerate(pending, 1):
            code, out = run(["opencli", "szdata", "table-detail", "--guid", r["downstream_guid"], "-f", "json"])
            task_id = ""
            label = ""
            db = ""
            status = "ERROR"
            if code == 0:
                try:
                    d = json.loads(out)
                    if isinstance(d, list):
                        d = d[0] if d else {}
                    db = str(d.get("dbName", ""))
                    ht = d.get("horaeTasks") or ""
                    m = re.search(r"ID:(\d+)", str(ht))
                    if m:
                        task_id = m.group(1)
                    label = str(ht)[:120]
                    status = "SUCCESS" if task_id else "NO_TASK"
                except Exception:
                    status = "PARSE_ERR"
            w.writerow({"downstream_name": r["downstream_name"],
                        "downstream_guid": r["downstream_guid"],
                        "db_name": db, "horae_task_id": task_id,
                        "horae_task_label": label, "probe_status": status})
            if i % 25 == 0 or i == len(pending):
                print(f"progress {i}/{len(pending)}: {r['downstream_name']} task={task_id or '-'} {status}", flush=True)
            if i < len(pending):
                time.sleep(SLEEP)
    print(f"done -> {TASKS_CSV}")


def cmd_sql() -> None:
    """每个任务拉 SQL 落盘（断点：文件已存在则跳过）。"""
    SQL_DIR.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(TASKS_CSV.open(encoding="utf-8-sig")))
    tasks = sorted({r["horae_task_id"] for r in rows if r["horae_task_id"]})
    todo = [t for t in tasks if not list(SQL_DIR.glob(f"tasksql-{t}-*.txt"))]
    print(f"任务 {len(tasks)}，已拉 {len(tasks) - len(todo)}，待拉 {len(todo)}")
    for i, tid in enumerate(todo, 1):
        code, out = run(["opencli", "szdata", "task-sql", "--task-id", tid,
                         "--save-to", str(SQL_DIR), "--full", "true"])
        ok = code == 0 and list(SQL_DIR.glob(f"tasksql-{tid}-*.txt"))
        print(f"{i}/{len(todo)}: {tid} {'OK' if ok else 'FAIL'}", flush=True)
        if i < len(todo):
            time.sleep(SLEEP)
    print(f"done -> {SQL_DIR}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["tables", "tasks", "sql"])
    args = parser.parse_args()
    {"tables": cmd_tables, "tasks": cmd_tasks, "sql": cmd_sql}[args.stage]()


if __name__ == "__main__":
    sys.exit(main())
