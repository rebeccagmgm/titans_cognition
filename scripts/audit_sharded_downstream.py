# -*- coding: utf-8 -*-
"""审计已落盘的 SZData 递归下游分片，不发起新的平台查询。"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict, deque
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "output" / "szdata-recursive-downstream-20260818-sharded"
SEEDS = ROOT / "output" / "downstream-dive-20260818" / "seed-scope.csv"
AUDIT = RUN / "audit"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_parts(directory: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(directory.glob("part-*.csv")):
        rows.extend(read_csv(path))
    return rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    seeds = read_csv(SEEDS)
    seed_by_guid = {row["seed_guid"]: row for row in seeds}
    query_rows = read_parts(RUN / "query-results")
    edge_rows = read_parts(RUN / "direct-edges")

    attempts: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in query_rows:
        attempts[row.get("guid", "")].append(row)

    query_status: dict[str, str] = {}
    for guid, rows in attempts.items():
        statuses = [row.get("status", "UNKNOWN") for row in rows]
        if "SUCCESS" in statuses:
            query_status[guid] = "SUCCESS_AFTER_RETRY" if len(rows) > 1 else "SUCCESS"
        else:
            query_status[guid] = statuses[-1] if statuses else "UNKNOWN"

    edges: dict[tuple[str, str], dict[str, str]] = {}
    for row in edge_rows:
        parent = row.get("parent_guid", "")
        child = row.get("child_guid", "")
        if parent and child:
            edges.setdefault((parent, child), row)

    child_names: dict[str, set[str]] = defaultdict(set)
    child_types: dict[str, set[str]] = defaultdict(set)
    adjacency: dict[str, set[str]] = defaultdict(set)
    reverse: dict[str, set[str]] = defaultdict(set)
    for (parent, child), row in edges.items():
        child_names[child].add(row.get("child_name", ""))
        child_types[child].add(row.get("child_type", ""))
        adjacency[parent].add(child)
        reverse[child].add(parent)

    hop_by_guid = {guid: 0 for guid in seed_by_guid}
    queue = deque(seed_by_guid)
    while queue:
        parent = queue.popleft()
        for child in sorted(adjacency.get(parent, set())):
            if child not in hop_by_guid:
                hop_by_guid[child] = hop_by_guid[parent] + 1
                queue.append(child)

    all_guids = set(seed_by_guid) | set(child_names)
    node_rows: list[dict[str, object]] = []
    for guid in sorted(all_guids):
        seed = seed_by_guid.get(guid)
        names = {seed["seed_table_name"]} if seed else set()
        names.update(name for name in child_names.get(guid, set()) if name)
        types = child_types.get(guid, set()) or {"hive_table"}
        is_table = any("table" in type_name.lower() for type_name in types)
        attempts_for_guid = attempts.get(guid, [])
        status = query_status.get(guid, "NOT_QUERIED")
        if seed:
            state = "SEED_EXPANDED" if status.startswith("SUCCESS") else "SEED_QUERY_INCOMPLETE"
        elif not is_table:
            state = "NON_TABLE_TERMINAL"
        elif status.startswith("SUCCESS"):
            state = "EXPANDED_SUCCESS"
        else:
            state = "UNEXPANDED_TABLE"

        name = sorted(names, key=str.lower)[0] if names else ""
        db_name = seed.get("seed_db_name", "") if seed else ""
        db_resolution = "SEED_TABLE_DETAIL" if seed and db_name else "NOT_PERSISTED_IN_EDGE"
        node_rows.append(
            {
                "guid": guid,
                "name": name,
                "node_type": "|".join(sorted(types)),
                "is_seed": "YES" if seed else "NO",
                "seed_db_name": db_name,
                "db_resolution": db_resolution,
                "min_hop_from_seed": hop_by_guid.get(guid, ""),
                "query_status": status,
                "query_attempt_count": len(attempts_for_guid),
                "node_state": state,
                "incoming_edge_count": len(reverse.get(guid, set())),
                "outgoing_edge_count": len(adjacency.get(guid, set())),
            }
        )

    query_status_rows = [
        {"status": status, "count": count}
        for status, count in sorted(Counter(query_status.values()).items())
    ]
    edge_type_rows = [
        {"child_type": child_type or "UNKNOWN", "edge_count": count}
        for child_type, count in Counter(row.get("child_type", "") for row in edges.values()).most_common()
    ]
    unexpanded_rows = [row for row in node_rows if row["node_state"] == "UNEXPANDED_TABLE"]

    AUDIT.mkdir(parents=True, exist_ok=True)
    node_fields = list(node_rows[0].keys()) if node_rows else []
    write_csv(AUDIT / "node-inventory.csv", node_fields, node_rows)
    write_csv(AUDIT / "unexpanded-table-nodes.csv", node_fields, unexpanded_rows)
    write_csv(AUDIT / "query-status-summary.csv", ["status", "count"], query_status_rows)
    write_csv(AUDIT / "edge-type-summary.csv", ["child_type", "edge_count"], edge_type_rows)

    query_parts = sorted((RUN / "query-results").glob("part-*.csv"))
    edge_parts = sorted((RUN / "direct-edges").glob("part-*.csv"))
    range_parts = sorted((RUN / "range").glob("part-*.csv"))
    table_nodes = [row for row in node_rows if "table" in str(row["node_type"]).lower()]
    manifest = {
        "schema_version": "szdata-recursive-downstream-audit-v1",
        "source_run": str(RUN.relative_to(ROOT)),
        "seed_source": str(SEEDS.relative_to(ROOT)),
        "szdata_called_by_audit": False,
        "source_run_completion": "PARTIAL_NO_RANGE_OUTPUT",
        "parts": {
            "query_results": len(query_parts),
            "direct_edges": len(edge_parts),
            "range": len(range_parts),
        },
        "counts": {
            "seed_count": len(seed_by_guid),
            "query_attempt_rows": len(query_rows),
            "unique_queried_guids": len(attempts),
            "unique_edges": len(edges),
            "reachable_nodes_from_seeds": len(hop_by_guid),
            "max_reached_hop": max(hop_by_guid.values(), default=0),
            "child_nodes": len(child_names),
            "table_nodes_seen": len(table_nodes),
            "expanded_table_nodes": sum(row["node_state"] == "EXPANDED_SUCCESS" for row in node_rows),
            "unexpanded_table_nodes": len(unexpanded_rows),
            "non_table_terminal_nodes": sum(row["node_state"] == "NON_TABLE_TERMINAL" for row in node_rows),
        },
        "query_status": dict(Counter(query_status.values())),
        "edge_file_schema": sorted({tuple(sorted(row.keys())) for row in edge_rows}),
        "known_limitations": [
            "No range parts or final manifest were written by the interrupted run.",
            "Existing direct-edge parts do not persist child_db_name/table-detail results.",
            "The audit cannot classify the discovered nodes as dm_otc_n without another table-detail pass or a persisted detail cache.",
            "The 374 duplicate query rows represent COMMAND_FAILED followed by SUCCESS; they are retained as retry history.",
        ],
    }
    (AUDIT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = f"""# SZData 递归下游分片审计

本报告只读取已有分片，不发起新的 SZData 查询。

## 当前状态

- 初始种子：{len(seed_by_guid)} 张
- 查询分片：{len(query_parts)} 个
- 直接边分片：{len(edge_parts)} 个
- 最终范围分片：{len(range_parts)} 个
- 唯一已查询节点：{len(attempts)} 个
- 去重直接边：{len(edges)} 条
- 从种子可达节点：{len(hop_by_guid)} 个
- 已达到最大跳数：{max(hop_by_guid.values(), default=0)}
- 待继续展开的表节点：{len(unexpanded_rows)} 个

## 重要限制

1. 这次运行没有生成 `range/part-*.csv`，因此还不是最终闭包结果。
2. 旧的 `direct-edges` 分片只有父子 GUID、名称和类型，没有持久化子表库名。
3. 因此当前审计只能确认平台图的结构扩展，不能直接判断哪些节点属于 `dm_otc_n`。
4. 374 个 GUID 曾出现一次 `COMMAND_FAILED`，随后又有 `SUCCESS`；按节点状态视为成功，但原始重试记录保留在查询分片中。

## 审计产物

- `node-inventory.csv`：全部已发现节点及状态；
- `unexpanded-table-nodes.csv`：已发现但尚未成功查询的表节点；
- `query-status-summary.csv`：查询状态汇总；
- `edge-type-summary.csv`：下游节点类型汇总；
- `manifest.json`：本次审计口径和限制。

下一步若要继续，应从 `unexpanded-table-nodes.csv` 续跑，并修正/补充 table-detail 持久化；不能根据当前分片直接宣称 `dm_otc_n` 范围已经完成。
"""
    (AUDIT / "README.md").write_text(report, encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
