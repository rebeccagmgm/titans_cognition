from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

from scripts import resolve_downstream_task_ids as resolver


def _payload(task_id: str = "196172", status: str = "SUCCEEDED") -> str:
    return json.dumps(
        [
            {
                "status": status,
                "taskCount": 1,
                "tableProfile": {"tasks": [{"taskId": task_id}]},
                "tasks": [{"taskId": task_id, "errors": []}],
                "evidenceLevel": "opencli_task_inspect_batch",
            }
        ]
    )


def test_normalize_query_table_strips_data_source_suffix() -> None:
    assert (
        resolver.normalize_query_table("dm_om_n.example@gfhive")
        == "dm_om_n.example"
    )
    assert resolver.normalize_query_table("dm_om_n.example") == "dm_om_n.example"


def test_build_command_uses_python_executable_shim() -> None:
    command = resolver.build_task_inspect_command("dm_om_n.example")
    assert command[0].lower().endswith(("opencli", "opencli.cmd"))
    assert command[command.index("--table") + 1] == "dm_om_n.example"


def test_load_input_rows_can_bound_sorted_part_files(tmp_path: Path) -> None:
    input_dir = tmp_path / "table-details"
    input_dir.mkdir()
    for name, guid in (
        ("part-00002.csv", "guid-2"),
        ("part-00001.csv", "guid-1"),
        ("part-00003.csv", "guid-3"),
    ):
        (input_dir / name).write_text(
            "guid,db_name,qualified_name\n"
            f"{guid},dm_test,dm_test.table_{guid}@gfhive\n",
            encoding="utf-8",
        )

    rows = resolver.load_input_rows(input_dir, max_input_files=2)

    assert [row["guid"] for row in rows] == ["guid-1", "guid-2"]


def test_classify_rate_limit_without_treating_it_as_not_found() -> None:
    result = resolver.classify_response(
        returncode=1,
        stdout="",
        stderr="MCP 全局限流命中, dimension=USER",
    )

    assert result.status == "RATE_LIMITED"
    assert result.error_class == "RATE_LIMIT"
    assert result.task_ids == ()

    garbled_safe = resolver.classify_response(
        returncode=1,
        stdout="",
        stderr="metadata.get_table_ddl failed, dimension=USER, threshold=5",
    )
    assert garbled_safe.status == "RATE_LIMITED"


def test_classify_success_and_partial() -> None:
    success = resolver.classify_response(0, _payload(), "")
    assert success.status == "SUCCESS"
    assert success.task_ids == ("196172",)

    partial_payload = json.dumps(
        [
            {
                "status": "PARTIAL",
                "taskCount": 2,
                "tableProfile": {"tasks": [{"taskId": "1"}, {"taskId": "2"}]},
                "tasks": [
                    {"taskId": "1", "errors": []},
                    {"taskId": "2", "errors": ["upstream failure"]},
                ],
            }
        ]
    )
    partial = resolver.classify_response(0, partial_payload, "")
    assert partial.status == "PARTIAL"
    assert partial.task_ids == ("1", "2")


def test_run_marks_missing_qualified_name_without_querying(
    tmp_path: Path, monkeypatch
) -> None:
    input_path = tmp_path / "part-00001.csv"
    output_path = tmp_path / "task-map.csv"
    input_path.write_text(
        "guid,db_name,qualified_name\n"
        "guid-missing,dm_test,\n",
        encoding="utf-8",
    )

    def fail_if_called(*_: object, **__: object) -> object:
        raise AssertionError("invalid input must not call task-inspect")

    monkeypatch.setattr(resolver, "query_table", fail_if_called)

    exit_code = resolver.run(
        input_path=input_path,
        output_path=output_path,
        interval_seconds=0,
    )

    assert exit_code == 1
    row = next(
        csv.DictReader(output_path.open(encoding="utf-8-sig", newline=""))
    )
    assert row["status"] == "INPUT_INVALID"
    assert row["error_class"] == "MISSING_QUALIFIED_NAME"
    assert row["attempts"] == "0"


def test_main_resumes_success_and_writes_rate_limit_state(
    tmp_path: Path, monkeypatch
) -> None:
    input_path = tmp_path / "part-00001.csv"
    output_path = tmp_path / "task-map.csv"
    with input_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["guid", "db_name", "qualified_name", "status"]
        )
        writer.writeheader()
        writer.writerow(
            {
                "guid": "guid-success",
                "db_name": "dm_om_n",
                "qualified_name": "dm_om_n.done@gfhive",
                "status": "SUCCESS",
            }
        )
        writer.writerow(
            {
                "guid": "guid-pending",
                "db_name": "dm_om_n",
                "qualified_name": "dm_om_n.pending@gfhive",
                "status": "SUCCESS",
            }
        )

    output_path.write_text(
        "guid,db_name,qualified_name,query_table,status,task_ids,task_count,attempts,checked_at_utc,error_class\n"
        "guid-success,dm_om_n,dm_om_n.done@gfhive,dm_om_n.done,SUCCESS,9,1,1,old,\n",
        encoding="utf-8",
    )

    calls: list[str] = []

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command[command.index("--table") + 1])
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr="MCP 全局限流命中, dimension=USER",
        )

    monkeypatch.setattr(resolver.subprocess, "run", fake_run)
    monkeypatch.setattr(resolver.time, "sleep", lambda _: None)

    exit_code = resolver.run(
        input_path=input_path,
        output_path=output_path,
        interval_seconds=15,
        timeout_seconds=10,
        rate_limit_backoff_seconds=1,
        rate_limit_retries=0,
    )

    assert exit_code == 2
    assert calls == ["dm_om_n.pending"]
    rows = list(csv.DictReader(output_path.open(encoding="utf-8-sig", newline="")))
    pending = next(row for row in rows if row["guid"] == "guid-pending")
    assert pending["status"] == "RATE_LIMITED"
    assert pending["error_class"] == "RATE_LIMIT"
