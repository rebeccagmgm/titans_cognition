"""Independent read-only SQL baseline for V1A reconciliation."""

from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable

from .scope import ScopeConfig


@dataclass(frozen=True)
class CommandResult:
    """Small subprocess result for baseline tests and adapter calls."""

    returncode: int
    stdout: str
    stderr: str


BaselineRunner = Callable[[list[str], int], CommandResult]
_IDENTIFIER = re.compile(r"^[A-Z][A-Z0-9_$#]*$")


def _default_runner(command: list[str], timeout_seconds: int) -> CommandResult:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        check=False,
    )
    return CommandResult(result.returncode, result.stdout, result.stderr)


def build_independent_baseline(
    scope: ScopeConfig,
    *,
    python_executable: str | Path,
    query_script: str | Path,
    database: str,
    max_rows: int = 100_000,
    timeout_seconds: int = 120,
    runner: BaselineRunner = _default_runner,
) -> dict[str, object]:
    """Run independent dictionary SQL for object names and column counts."""

    owners = _owner_list(scope.schemas)
    object_types = _object_type_list(scope.object_types)
    object_rows = _query_json(
        python_executable,
        query_script,
        database,
        (
            "SELECT OWNER, OBJECT_NAME, OBJECT_TYPE FROM ALL_OBJECTS "
            f"WHERE OWNER IN ({owners}) AND OBJECT_TYPE IN ({object_types}) "
            "ORDER BY OWNER, OBJECT_TYPE, OBJECT_NAME"
        ),
        max_rows=max_rows,
        timeout_seconds=timeout_seconds,
        runner=runner,
    )
    column_rows = _query_json(
        python_executable,
        query_script,
        database,
        (
            "SELECT C.OWNER, COUNT(*) AS COLUMN_COUNT "
            "FROM ALL_TAB_COLUMNS C "
            "JOIN ALL_OBJECTS O ON O.OWNER = C.OWNER "
            "AND O.OBJECT_NAME = C.TABLE_NAME "
            f"AND O.OBJECT_TYPE IN ({object_types}) "
            f"WHERE C.OWNER IN ({owners}) "
            "GROUP BY C.OWNER ORDER BY C.OWNER"
        ),
        max_rows=max_rows,
        timeout_seconds=timeout_seconds,
        runner=runner,
    )
    return {
        "baseline_kind": "INDEPENDENT_ORACLE_DICTIONARY_SQL",
        "scope_id": scope.scope_id,
        "objects": [
            {
                "schema_name": str(row["OWNER"]).upper(),
                "object_name": str(row["OBJECT_NAME"]).upper(),
                "object_type": str(row["OBJECT_TYPE"]).upper().replace(" ", "_"),
            }
            for row in object_rows
        ],
        "columns": [
            {
                "schema_name": str(row["OWNER"]).upper(),
                "column_count": int(row["COLUMN_COUNT"]),
            }
            for row in column_rows
        ],
    }


def _query_json(
    python_executable: str | Path,
    query_script: str | Path,
    database: str,
    sql: str,
    *,
    max_rows: int,
    timeout_seconds: int,
    runner: BaselineRunner,
) -> list[dict[str, Any]]:
    result = runner(
        [
            str(python_executable),
            str(query_script),
            "query",
            "--db",
            database,
            "--sql",
            sql,
            "--max-rows",
            str(max_rows),
            "--format",
            "json",
        ],
        timeout_seconds,
    )
    if result.returncode != 0:
        raise RuntimeError("independent baseline SQL failed")
    payload = json.loads(result.stdout)
    if not isinstance(payload, list) or not all(
        isinstance(row, dict) for row in payload
    ):
        raise ValueError("independent baseline SQL returned an invalid row list")
    return payload


def _owner_list(schemas: tuple[str, ...]) -> str:
    if not schemas or not all(_IDENTIFIER.fullmatch(schema) for schema in schemas):
        raise ValueError("scope contains an invalid Oracle schema identifier")
    return ", ".join(f"'{schema}'" for schema in schemas)


def _object_type_list(object_types: tuple[str, ...]) -> str:
    return ", ".join(f"'{object_type.replace('_', ' ')}'" for object_type in object_types)
