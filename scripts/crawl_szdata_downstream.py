# -*- coding: utf-8 -*-
"""递归查询数综平台表血缘的 DOWNSTREAM 范围。

只读取 szdata table-lineage，不读业务行、不执行调度。输入可以是已有的
downstream-tables.csv（字段 downstream_name/downstream_guid），输出为去重的
平台直接边和“种子表 -> 可达下游对象”范围，不展开完整路径。
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


def load_seeds(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as fh:
            source = csv.DictReader(fh)
            for row in source:
                name = str(
                    row.get("downstream_name")
                    or row.get("seed_table_name")
                    or row.get("name")
                    or ""
                ).strip()
                guid = str(
                    row.get("downstream_guid")
                    or row.get("seed_guid")
                    or row.get("guid")
                    or ""
                ).strip()
                db_name = str(
                    row.get("db_name")
                    or row.get("seed_db_name")
                    or row.get("db")
                    or ""
                ).strip()
                if name and guid:
                    rows.append({"name": name, "guid": guid, "db_name": db_name})
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload:
            name = str(
                row.get("downstream_name")
                or row.get("seed_table_name")
                or row.get("name")
                or ""
            ).strip()
            guid = str(
                row.get("downstream_guid")
                or row.get("seed_guid")
                or row.get("guid")
                or ""
            ).strip()
            db_name = str(
                row.get("db_name")
                or row.get("seed_db_name")
                or row.get("db")
                or ""
            ).strip()
            if name and guid:
                rows.append({"name": name, "guid": guid, "db_name": db_name})

    unique: dict[str, dict[str, str]] = {}
    for row in rows:
        unique.setdefault(row["guid"], row)
    return sorted(unique.values(), key=lambda row: (row["name"].lower(), row["guid"]))


def fetch_lineage(guid: str, timeout: int, retries: int) -> dict[str, Any]:
    command = ["opencli", "szdata", "table-lineage", "--guid", guid, "--status", "1", "-f", "json"]
    last_status = "COMMAND_FAILED"
    last_error = ""
    for attempt in range(max(0, retries) + 1):
        try:
            result = subprocess.run(command, capture_output=True, shell=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            last_status = "TIMEOUT"
            last_error = "command timeout"
            continue
        stdout = result.stdout.decode("utf-8", errors="replace")
        stderr = result.stderr.decode("utf-8", errors="replace")
        if result.returncode != 0:
            last_status = "COMMAND_FAILED"
            last_error = (stderr or stdout)[-2000:]
            continue
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            last_status = "INVALID_JSON"
            last_error = (stderr or stdout)[-2000:]
            continue
        return {"guid": guid, "status": "SUCCESS", "nodes": payload if isinstance(payload, list) else []}
    return {"guid": guid, "status": last_status, "nodes": [], "error": last_error}


def fetch_table_detail(guid: str, timeout: int, retries: int) -> dict[str, Any]:
    command = ["opencli", "szdata", "table-detail", "--guid", guid, "-f", "json"]
    last_status = "COMMAND_FAILED"
    last_error = ""
    for _ in range(max(0, retries) + 1):
        try:
            result = subprocess.run(command, capture_output=True, shell=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            last_status = "TIMEOUT"
            last_error = "command timeout"
            continue
        stdout = result.stdout.decode("utf-8", errors="replace")
        stderr = result.stderr.decode("utf-8", errors="replace")
        if result.returncode != 0:
            last_status = "COMMAND_FAILED"
            last_error = (stderr or stdout)[-2000:]
            continue
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            last_status = "INVALID_JSON"
            last_error = (stderr or stdout)[-2000:]
            continue
        detail = payload[0] if isinstance(payload, list) and payload else payload
        if not isinstance(detail, dict):
            last_status = "INVALID_PAYLOAD"
            last_error = stdout[-2000:]
            continue
        return {
            "guid": guid,
            "status": "SUCCESS",
            "db_name": str(detail.get("dbName") or "").strip(),
            "qualified_name": str(detail.get("qualifiedName") or "").strip(),
            "name": str(detail.get("name") or "").strip(),
        }
    return {"guid": guid, "status": last_status, "db_name": "", "qualified_name": "", "name": "", "error": last_error}


def is_table(type_name: str) -> bool:
    return "table" in type_name.lower()


def infer_db_name(name: str) -> str:
    return name.split(".", 1)[0].strip() if "." in name else ""


def normalize_db_name(value: str) -> str:
    return str(value or "").strip().lower()


def node_db_name(node: dict[str, str]) -> str:
    return str(node.get("db_name") or infer_db_name(node.get("name", ""))).strip()


def is_dm_db(db_name: str, stop_db_prefix: str) -> bool:
    return normalize_db_name(db_name).startswith(normalize_db_name(stop_db_prefix))


def is_passthrough_db(db_name: str, passthrough_db: str) -> bool:
    return normalize_db_name(db_name) == normalize_db_name(passthrough_db)


def can_expand(
    node: dict[str, str],
    allowed_db: str,
    stop_db_prefix: str,
    passthrough_db: str,
) -> bool:
    if not is_table(node.get("type_name", "")):
        return False
    db_name = node_db_name(node)
    if not db_name:
        return False
    if is_dm_db(db_name, stop_db_prefix) and not is_passthrough_db(db_name, passthrough_db):
        return False
    if not allowed_db:
        return True
    return normalize_db_name(db_name) == normalize_db_name(allowed_db)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_partitioned_csv(
    directory: Path,
    prefix: str,
    fieldnames: list[str],
    rows: list[dict[str, Any]],
    rows_per_part: int,
) -> int:
    directory.mkdir(parents=True, exist_ok=True)
    part_size = max(1, rows_per_part)
    for offset in range(0, len(rows), part_size):
        write_csv(
            directory / f"{prefix}-{offset // part_size + 1:05d}.csv",
            fieldnames,
            rows[offset : offset + part_size],
        )
    return (len(rows) + part_size - 1) // part_size


def load_csv_directory(directory: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not directory.exists():
        return rows
    for path in sorted(directory.glob("part-*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as fh:
            rows.extend(dict(row) for row in csv.DictReader(fh))
    return rows


DETAIL_FIELDS = ["guid", "status", "db_name", "qualified_name", "name", "error"]


def detail_success(detail: dict[str, Any]) -> bool:
    return str(detail.get("status") or "") == "SUCCESS"


def apply_detail(node: dict[str, str], detail: dict[str, Any]) -> None:
    if not detail_success(detail):
        return
    for key in ("db_name", "qualified_name", "name"):
        value = str(detail.get(key) or "").strip()
        if value:
            node[key] = value


def detail_row(detail: dict[str, Any]) -> dict[str, str]:
    return {field: str(detail.get(field) or "") for field in DETAIL_FIELDS}


def load_local_db_map(facts_root: Path, seeds: list[dict[str, str]]) -> dict[str, str]:
    candidates: dict[str, set[str]] = defaultdict(set)

    def add_qualified(value: str) -> None:
        qualified = str(value or "").strip()
        if "." not in qualified:
            return
        db_name, table_name = qualified.split(".", 1)
        if db_name.strip() and table_name.strip():
            candidates[table_name.strip().lower()].add(db_name.strip())

    for seed in seeds:
        add_qualified(f"{seed.get('db_name', '')}.{seed.get('name', '')}")
    if facts_root.exists():
        for path in facts_root.rglob("dataset-io.jsonl"):
            try:
                with path.open(encoding="utf-8") as fh:
                    for line in fh:
                        try:
                            row = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        add_qualified(row.get("physical_dataset", ""))
            except OSError:
                continue
    return {
        table_name: next(iter(db_names))
        for table_name, db_names in candidates.items()
        if len(db_names) == 1
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", required=True, help="CSV/JSON seed tables with name and GUID")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--workers", type=int, default=3, help="Concurrent read-only lineage calls")
    parser.add_argument("--timeout", type=int, default=60, help="Timeout per lineage call")
    parser.add_argument("--retries", type=int, default=2, help="Retries for transient CLI/API failures")
    parser.add_argument("--max-hops", type=int, default=0, help="0=unlimited")
    parser.add_argument("--limit-seeds", type=int, default=0, help="Smoke-test seed limit; 0=all")
    parser.add_argument("--batch-size", type=int, default=300, help="GUIDs submitted per progress batch")
    parser.add_argument("--rows-per-part", type=int, default=10000, help="Rows per final output part")
    parser.add_argument("--resume", action="store_true", help="Resume from query-results and direct-edges parts")
    parser.add_argument("--allowed-db", default="", help="Only expand tables from this database")
    parser.add_argument("--stop-db-prefix", default="dm_", help="DM database prefix; these nodes stop by default")
    parser.add_argument("--passthrough-db", default="dm_otc_n", help="DM database that remains expandable")
    parser.add_argument("--max-queried-nodes", type=int, default=0, help="Bounded smoke-test cap; 0=unlimited")
    parser.add_argument("--facts-root", default="machine-facts/registry/tasks", help="Optional local Fact root for unique table-to-database hints")
    args = parser.parse_args()

    seeds = load_seeds(Path(args.seeds))
    if args.allowed_db:
        seeds = [row for row in seeds if row.get("db_name", "").lower() == args.allowed_db.lower()]
    if args.limit_seeds > 0:
        seeds = seeds[: args.limit_seeds]
    if not seeds:
        raise SystemExit("no valid seed tables")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    local_db_map = load_local_db_map(Path(args.facts_root), seeds)

    seed_by_guid = {row["guid"]: row["name"] for row in seeds}
    known_nodes: dict[str, dict[str, str]] = {
        row["guid"]: {
            "guid": row["guid"],
            "name": row["name"],
            "type_name": "hive_table",
            "db_name": row.get("db_name", "") or local_db_map.get(row["name"].lower(), ""),
        }
        for row in seeds
    }
    direct_edges: dict[tuple[str, str], dict[str, str]] = {}
    queried: dict[str, dict[str, Any]] = {}
    detail_cache: dict[str, dict[str, Any]] = {}
    detail_retryable: set[str] = set()
    if args.resume:
        for row in load_csv_directory(output / "table-details"):
            guid = str(row.get("guid") or "").strip()
            if guid:
                detail_cache[guid] = dict(row)
                if str(row.get("status") or "") != "SUCCESS":
                    detail_retryable.add(guid)
                else:
                    detail_retryable.discard(guid)
        for row in load_csv_directory(output / "query-results"):
            guid = str(row.get("guid") or "").strip()
            if guid:
                queried[guid] = {
                    "guid": guid,
                    "status": str(row.get("status") or "UNKNOWN"),
                    "nodes": [],
                    "error": str(row.get("error") or ""),
                }
        for row in load_csv_directory(output / "direct-edges"):
            parent_guid = str(row.get("parent_guid") or "").strip()
            child_guid = str(row.get("child_guid") or "").strip()
            if not parent_guid or not child_guid:
                continue
            known_nodes.setdefault(parent_guid, {
                "guid": parent_guid,
                "name": str(row.get("parent_name") or ""),
                "type_name": "hive_table",
                "db_name": str(row.get("parent_db_name") or ""),
            })
            known_nodes.setdefault(child_guid, {
                "guid": child_guid,
                "name": str(row.get("child_name") or ""),
                "type_name": str(row.get("child_type") or ""),
                "db_name": str(row.get("child_db_name") or ""),
            })
            if not known_nodes[child_guid].get("db_name"):
                known_nodes[child_guid]["db_name"] = local_db_map.get(
                    known_nodes[child_guid].get("name", "").lower(), ""
                )
            direct_edges[(parent_guid, child_guid)] = {
                "parent_guid": parent_guid,
                "parent_name": str(row.get("parent_name") or ""),
                "child_guid": child_guid,
                "child_name": str(row.get("child_name") or ""),
                "child_type": str(row.get("child_type") or ""),
                "child_db_name": str(row.get("child_db_name") or ""),
            }

    for guid, node in known_nodes.items():
        if not node.get("db_name"):
            node["db_name"] = local_db_map.get(node.get("name", "").lower(), "")
        if guid in detail_cache:
            apply_detail(node, detail_cache[guid])

    for edge in direct_edges.values():
        parent = known_nodes.get(edge["parent_guid"], {})
        child = known_nodes.get(edge["child_guid"], {})
        edge["parent_db_name"] = node_db_name(parent)
        edge["child_db_name"] = node_db_name(child)

    resume_adjacency: dict[str, list[str]] = defaultdict(list)
    for parent_guid, child_guid in direct_edges:
        resume_adjacency[parent_guid].append(child_guid)
    hop_by_guid = {guid: 0 for guid in seed_by_guid}
    queue = deque(seed_by_guid)
    while queue:
        parent_guid = queue.popleft()
        for child_guid in resume_adjacency.get(parent_guid, []):
            child_hop = hop_by_guid[parent_guid] + 1
            if child_guid not in hop_by_guid or child_hop < hop_by_guid[child_guid]:
                hop_by_guid[child_guid] = child_hop
                queue.append(child_guid)
    detail_part_no = len(list((output / "table-details").glob("part-*.csv"))) + 1

    def resolve_missing_details(guids: set[str]) -> None:
        nonlocal detail_part_no
        pending_details = sorted(
            guid for guid in guids
            if guid in known_nodes
            and is_table(known_nodes[guid].get("type_name", ""))
            and not node_db_name(known_nodes[guid])
            and (guid not in detail_cache or guid in detail_retryable)
        )
        if not pending_details:
            return
        detail_batch_size = min(max(1, args.batch_size), 20)
        for offset in range(0, len(pending_details), detail_batch_size):
            batch = pending_details[offset : offset + detail_batch_size]
            for guid in batch:
                detail_retryable.discard(guid)
            with ThreadPoolExecutor(max_workers=max(1, args.workers)) as detail_executor:
                details = list(detail_executor.map(
                    lambda guid: fetch_table_detail(guid, args.timeout, args.retries),
                    batch,
                ))
            detail_rows: list[dict[str, str]] = []
            for detail in details:
                guid = str(detail.get("guid") or "")
                detail_cache[guid] = detail
                detail_rows.append(detail_row(detail))
                if guid in known_nodes:
                    apply_detail(known_nodes[guid], detail)
            if detail_rows:
                write_csv(
                    output / "table-details" / f"part-{detail_part_no:05d}.csv",
                    DETAIL_FIELDS,
                    sorted(detail_rows, key=lambda row: row["guid"]),
                )
                detail_part_no += 1
            print(
                f"detail_resolved={min(offset + len(batch), len(pending_details))}/{len(pending_details)}",
                flush=True,
            )

    def reachable_resume_frontier() -> tuple[set[str], set[str]]:
        frontier_nodes: set[str] = set()
        missing_details: set[str] = set()
        states = deque()
        visited: set[tuple[str, bool]] = set()
        for guid in seed_by_guid:
            seed = known_nodes[guid]
            seed_db_name = node_db_name(seed)
            dm_reached = is_table(seed.get("type_name", "")) and is_dm_db(
                seed_db_name, args.stop_db_prefix
            )
            states.append((guid, dm_reached))
        while states:
            parent_guid, dm_reached = states.popleft()
            state = (parent_guid, dm_reached)
            if state in visited:
                continue
            visited.add(state)
            parent = known_nodes.get(parent_guid, {})
            parent_db_name = node_db_name(parent)
            if is_table(parent.get("type_name", "")) and not parent_db_name:
                continue
            if is_dm_db(parent_db_name, args.stop_db_prefix) and not is_passthrough_db(
                parent_db_name, args.passthrough_db
            ):
                continue
            if queried.get(parent_guid, {}).get("status") != "SUCCESS":
                if can_expand(parent, args.allowed_db, args.stop_db_prefix, args.passthrough_db):
                    frontier_nodes.add(parent_guid)
                continue
            for child_guid in resume_adjacency.get(parent_guid, []):
                child = known_nodes.get(child_guid, {})
                if not child:
                    continue
                if (
                    is_table(child.get("type_name", ""))
                    and not node_db_name(child)
                    and (child_guid not in detail_cache or child_guid in detail_retryable)
                ):
                    missing_details.add(child_guid)
                    continue
                if is_table(child.get("type_name", "")) and not node_db_name(child):
                    continue
                child_db_name = node_db_name(child)
                child_is_dm = is_table(child.get("type_name", "")) and is_dm_db(
                    child_db_name, args.stop_db_prefix
                )
                if child_is_dm and not is_passthrough_db(child_db_name, args.passthrough_db):
                    continue
                child_state = (child_guid, dm_reached or child_is_dm)
                if queried.get(child_guid, {}).get("status") != "SUCCESS":
                    if can_expand(child, args.allowed_db, args.stop_db_prefix, args.passthrough_db):
                        frontier_nodes.add(child_guid)
                else:
                    states.append(child_state)
        return frontier_nodes, missing_details

    if args.resume:
        while True:
            frontier, missing_details = reachable_resume_frontier()
            if not missing_details:
                break
            resolve_missing_details(missing_details)
        for edge in direct_edges.values():
            parent = known_nodes.get(edge["parent_guid"], {})
            child = known_nodes.get(edge["child_guid"], {})
            edge["parent_db_name"] = node_db_name(parent)
            edge["child_db_name"] = node_db_name(child)
    else:
        frontier = set()
    if not args.resume:
        frontier = {
            guid for guid in seed_by_guid
            if can_expand(known_nodes[guid], args.allowed_db, args.stop_db_prefix, args.passthrough_db)
        }

    query_part_no = len(list((output / "query-results").glob("part-*.csv"))) + 1
    edge_part_no = len(list((output / "direct-edges").glob("part-*.csv"))) + 1
    traversal_complete = True
    stopped_reason = ""

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        while frontier:
            if args.max_hops and min(hop_by_guid[guid] for guid in frontier) >= args.max_hops:
                traversal_complete = False
                stopped_reason = "MAX_HOPS"
                break
            pending = sorted(
                guid for guid in frontier
                if guid not in queried or queried[guid]["status"] != "SUCCESS"
            )
            frontier = set()
            if not pending:
                break
            if args.max_queried_nodes:
                remaining = args.max_queried_nodes - len(queried)
                if remaining <= 0:
                    traversal_complete = False
                    stopped_reason = "MAX_QUERIED_NODES"
                    break
                pending = pending[:remaining]
            batch_size = max(1, args.batch_size)
            for offset in range(0, len(pending), batch_size):
                batch = pending[offset : offset + batch_size]
                batch_status: list[dict[str, Any]] = []
                batch_edges: list[dict[str, str]] = []
                futures = {
                    executor.submit(fetch_lineage, guid, args.timeout, args.retries): guid
                    for guid in batch
                }
                for future in as_completed(futures):
                    parent_guid = futures[future]
                    result = future.result()
                    queried[parent_guid] = result
                    batch_status.append({
                        "guid": parent_guid,
                        "status": result["status"],
                        "node_count": len(result.get("nodes", [])),
                        "error": result.get("error", ""),
                    })
                    if result["status"] != "SUCCESS":
                        continue
                    parent_hop = hop_by_guid.get(parent_guid, 0)
                    for node in result["nodes"]:
                        if node.get("direction") != "DOWNSTREAM":
                            continue
                        child_guid = str(node.get("id") or "").strip()
                        child_name = str(node.get("name") or "").strip()
                        child_type = str(node.get("typeName") or "").strip()
                        if not child_guid or not child_name:
                            continue
                        mapped_db_name = local_db_map.get(child_name.lower(), "")
                        if (
                            is_table(child_type)
                            and not infer_db_name(child_name)
                            and not mapped_db_name
                            and (child_guid not in detail_cache or child_guid in detail_retryable)
                        ):
                            detail_retryable.discard(child_guid)
                            detail_cache[child_guid] = fetch_table_detail(
                                child_guid, args.timeout, args.retries
                            )
                        detail = detail_cache.get(child_guid, {})
                        child_db_name = str(
                            detail.get("db_name") or infer_db_name(child_name)
                            or mapped_db_name
                        ).strip()
                        known_nodes.setdefault(child_guid, {
                            "guid": child_guid,
                            "name": child_name,
                            "type_name": child_type,
                            "db_name": child_db_name,
                        })
                        if child_db_name and not known_nodes[child_guid].get("db_name"):
                            known_nodes[child_guid]["db_name"] = child_db_name
                        edge_key = (parent_guid, child_guid)
                        edge_row = {
                            "parent_guid": parent_guid,
                            "parent_name": known_nodes.get(parent_guid, {}).get("name", ""),
                            "parent_db_name": known_nodes.get(parent_guid, {}).get("db_name", ""),
                            "child_guid": child_guid,
                            "child_name": child_name,
                            "child_type": child_type,
                            "child_db_name": child_db_name,
                        }
                        if edge_key not in direct_edges:
                            direct_edges[edge_key] = edge_row
                            batch_edges.append(edge_row)
                        child_hop = parent_hop + 1
                        if child_guid not in hop_by_guid or child_hop < hop_by_guid[child_guid]:
                            hop_by_guid[child_guid] = child_hop
                        if can_expand(
                            known_nodes[child_guid],
                            args.allowed_db,
                            args.stop_db_prefix,
                            args.passthrough_db,
                        ) and child_guid not in queried:
                            frontier.add(child_guid)
                write_csv(
                    output / "query-results" / f"part-{query_part_no:05d}.csv",
                    ["guid", "status", "node_count", "error"],
                    sorted(batch_status, key=lambda row: row["guid"]),
                )
                write_csv(
                    output / "direct-edges" / f"part-{edge_part_no:05d}.csv",
                    ["parent_guid", "parent_name", "parent_db_name", "child_guid", "child_name", "child_type", "child_db_name"],
                    sorted(batch_edges, key=lambda row: (row["parent_guid"], row["child_guid"])),
                )
                query_part_no += 1
                edge_part_no += 1
                print(
                    f"queried={len(queried)} frontier={len(frontier)} edges={len(direct_edges)} saved_query_parts={query_part_no - 1}",
                    flush=True,
                )
            if args.max_queried_nodes and len(queried) >= args.max_queried_nodes and frontier:
                traversal_complete = False
                stopped_reason = "MAX_QUERIED_NODES"
                break

    adjacency: dict[str, list[str]] = defaultdict(list)
    for parent_guid, child_guid in direct_edges:
        adjacency[parent_guid].append(child_guid)
    for children in adjacency.values():
        children.sort()

    range_rows: dict[tuple[str, str], dict[str, Any]] = {}
    dm_reached_seeds: set[str] = set()
    for seed_guid, seed_name in seed_by_guid.items():
        seed = known_nodes[seed_guid]
        seed_db_name = node_db_name(seed)
        initial_dm = is_table(seed.get("type_name", "")) and is_dm_db(seed_db_name, args.stop_db_prefix)
        first_dm = {
            "guid": seed_guid if initial_dm else "",
            "name": seed_name if initial_dm else "",
            "db_name": seed_db_name if initial_dm else "",
        }
        queue = deque([(seed_guid, 0, initial_dm, first_dm)])
        visited = {(seed_guid, initial_dm)}
        while queue:
            parent_guid, parent_hop, dm_reached, first_dm = queue.popleft()
            for child_guid in adjacency.get(parent_guid, []):
                child = known_nodes.get(child_guid, {})
                if not child:
                    continue
                hop = parent_hop + 1
                child_db_name = node_db_name(child)
                child_is_dm = is_table(child.get("type_name", "")) and is_dm_db(
                    child_db_name, args.stop_db_prefix
                )
                child_dm_reached = dm_reached or child_is_dm
                child_first_dm = first_dm
                if child_is_dm and not child_first_dm["guid"]:
                    child_first_dm = {
                        "guid": child_guid,
                        "name": child.get("name", ""),
                        "db_name": child_db_name,
                    }
                if child_dm_reached:
                    dm_reached_seeds.add(seed_guid)
                    key = (seed_guid, child_guid)
                    old = range_rows.get(key)
                    if old is None or hop < int(old["min_hop"]):
                        range_rows[key] = {
                            "seed_guid": seed_guid,
                            "seed_name": seed_name,
                            "downstream_guid": child_guid,
                            "downstream_name": child.get("name", ""),
                            "downstream_type": child.get("type_name", ""),
                            "downstream_db_name": child_db_name,
                            "min_hop": hop,
                            "first_dm_guid": child_first_dm["guid"],
                            "first_dm_name": child_first_dm["name"],
                            "first_dm_db_name": child_first_dm["db_name"],
                        }
                if is_table(child.get("type_name", "")) and not child_db_name:
                    continue
                if child_is_dm and not is_passthrough_db(child_db_name, args.passthrough_db):
                    continue
                state = (child_guid, child_dm_reached)
                if state in visited:
                    continue
                visited.add(state)
                queue.append((child_guid, hop, child_dm_reached, child_first_dm))

    direct_rows = sorted(direct_edges.values(), key=lambda row: (row["parent_name"].lower(), row["child_name"].lower(), row["child_guid"]))
    range_list = sorted(range_rows.values(), key=lambda row: (row["seed_name"].lower(), row["downstream_name"].lower(), row["downstream_guid"]))
    query_status_counts: dict[str, int] = defaultdict(int)
    for result in queried.values():
        query_status_counts[str(result["status"])] += 1
    detail_status_counts: dict[str, int] = defaultdict(int)
    for result in detail_cache.values():
        detail_status_counts[str(result["status"])] += 1

    range_fields = [
        "seed_guid", "seed_name", "downstream_guid", "downstream_name",
        "downstream_type", "downstream_db_name", "min_hop", "first_dm_guid",
        "first_dm_name", "first_dm_db_name",
    ]
    if range_list:
        write_partitioned_csv(output / "range", "part", range_fields, range_list, args.rows_per_part)
    else:
        write_csv(output / "range" / "part-00001.csv", range_fields, [])
    unresolved_db_nodes = sum(
        1 for node in known_nodes.values()
        if is_table(node.get("type_name", "")) and not node_db_name(node)
    )
    eligible_unqueried_nodes = sum(
        1 for guid, node in known_nodes.items()
        if can_expand(node, args.allowed_db, args.stop_db_prefix, args.passthrough_db)
        and queried.get(guid, {}).get("status") != "SUCCESS"
    )
    status = "SUCCESS"
    if not traversal_complete or eligible_unqueried_nodes:
        status = "PARTIAL"
    if any(value != "SUCCESS" for value in query_status_counts):
        status = "PARTIAL"
    if any(value != "SUCCESS" for value in detail_status_counts):
        status = "PARTIAL"
    (output / "manifest.json").write_text(json.dumps({
        "schema_version": "szdata-recursive-downstream-v2-dm-gated",
        "status": status,
        "traversal_complete": traversal_complete,
        "stopped_reason": stopped_reason,
        "seed_count": len(seeds),
        "local_unique_table_db_hint_count": len(local_db_map),
        "queried_node_count": len(queried),
        "known_node_count": len(known_nodes),
        "direct_edge_count": len(direct_rows),
        "range_relation_count": len(range_list),
        "unique_downstream_object_count": len({row["downstream_guid"] for row in range_list}),
        "max_hop": max((int(row["min_hop"]) for row in range_list), default=0),
        "seed_reaching_dm_count": len(dm_reached_seeds),
        "unresolved_db_node_count": unresolved_db_nodes,
        "eligible_unqueried_node_count": eligible_unqueried_nodes,
        "query_status_counts": dict(sorted(query_status_counts.items())),
        "detail_status_counts": dict(sorted(detail_status_counts.items())),
        "output_layout": {
            "query_results": "query-results/part-*.csv",
            "direct_edges": "direct-edges/part-*.csv",
            "table_details": "table-details/part-*.csv",
            "range": "range/part-*.csv",
            "rows_per_final_range_part": max(1, args.rows_per_part),
        },
        "boundaries": {
            "source": "szdata table-lineage DOWNSTREAM",
            "allowed_expand_db": args.allowed_db or "ALL",
            "stop_db_prefix": args.stop_db_prefix,
            "passthrough_db": args.passthrough_db,
            "range_policy": "retain only seed-to-node branches that have reached a DM database; dm_otc_n remains expandable; other dm_* nodes are terminal",
            "metadata_only": True,
            "business_rows_read": False,
            "schedule_execution": False,
            "full_paths_materialized": False,
            "non_table_nodes_are_terminal": True,
        },
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "seed_count": len(seeds),
        "queried_node_count": len(queried),
        "direct_edge_count": len(direct_rows),
        "range_relation_count": len(range_list),
        "unique_downstream_object_count": len({row["downstream_guid"] for row in range_list}),
        "max_hop": max((int(row["min_hop"]) for row in range_list), default=0),
        "seed_reaching_dm_count": len(dm_reached_seeds),
        "status": status,
        "traversal_complete": traversal_complete,
        "query_status_counts": dict(sorted(query_status_counts.items())),
        "detail_status_counts": dict(sorted(detail_status_counts.items())),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
