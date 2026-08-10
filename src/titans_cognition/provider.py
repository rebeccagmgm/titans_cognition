"""Read-only bridge to the existing gf-derivative-db query adapter."""

from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Callable, Iterable

from .extract import (
    ColumnMetadata,
    ConstraintMetadata,
    DefinitionMetadata,
    DependencyMetadata,
    IndexMetadata,
    ObjectMetadata,
    asset_id,
)
from .scope import ScopeConfig


class AdapterError(RuntimeError):
    """Raised when the read-only adapter cannot return metadata."""

    def __init__(self, status: str, category: str):
        super().__init__(f"metadata adapter {status}: {category}")
        self.status = status
        self.category = category


@dataclass(frozen=True)
class CommandResult:
    """Small subprocess result used to keep the provider testable."""

    returncode: int
    stdout: str
    stderr: str


CommandRunner = Callable[[list[str], int], CommandResult]
_IDENTIFIER = re.compile(r"^[A-Z][A-Z0-9_$#]*$")


class _BatchDefinitionStore:
    """File-backed definition chunks; only one chunk is held at a time."""

    def __init__(self, files_by_key: dict[tuple[str, str], Path]):
        self._files_by_key = files_by_key
        self._loaded_path: Path | None = None
        self._loaded: dict[tuple[str, str], dict[str, Any]] = {}

    @classmethod
    def from_manifest(cls, output_dir: Path, files: list[object]) -> "_BatchDefinitionStore":
        root = output_dir.resolve()
        files_by_key: dict[tuple[str, str], Path] = {}
        for raw_file in files:
            if not isinstance(raw_file, str):
                raise AdapterError("FAILED", "INVALID_BATCH_MANIFEST")
            path = (root / raw_file).resolve()
            if root not in path.parents or path.suffix.lower() != ".json":
                raise AdapterError("FAILED", "INVALID_BATCH_MANIFEST")
            try:
                rows = json.loads(path.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError) as exc:
                raise AdapterError("FAILED", "INVALID_BATCH_FILE") from exc
            if not isinstance(rows, list):
                raise AdapterError("FAILED", "INVALID_BATCH_FILE")
            for row in rows:
                if not isinstance(row, dict):
                    raise AdapterError("FAILED", "INVALID_BATCH_FILE")
                key = (
                    str(row.get("owner", "")).upper(),
                    str(row.get("object_name", "")).upper(),
                )
                if key[0] and key[1]:
                    files_by_key[key] = path
        return cls(files_by_key)

    def get(
        self,
        key: tuple[str, str],
        default: DefinitionMetadata,
    ) -> DefinitionMetadata:
        path = self._files_by_key.get(key)
        if path is None:
            return default
        if path != self._loaded_path:
            rows = json.loads(path.read_text(encoding="utf-8"))
            self._loaded = {
                (
                    str(row.get("owner", "")).upper(),
                    str(row.get("object_name", "")).upper(),
                ): row
                for row in rows
            }
            self._loaded_path = path
        row = self._loaded.get(key)
        if row is None:
            return default
        return DefinitionMetadata(
            definition_type=str(row.get("definition_type", "DDL")).upper(),
            definition_text=row.get("definition_text") or None,
            extraction_status=str(row.get("extraction_status", "FAILED")).upper(),
            error_category=row.get("error_category") or None,
        )


def _default_runner(command: list[str], timeout_seconds: int) -> CommandResult:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        check=False,
    )
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def _canonical_type(value: str) -> str:
    return value.strip().upper().replace(" ", "_")


def _owner_list(schemas: Iterable[str]) -> str:
    names = [_canonical_type(schema) for schema in schemas]
    if not names or not all(_IDENTIFIER.fullmatch(name) for name in names):
        raise ValueError("scope contains an invalid Oracle schema identifier")
    return ", ".join(f"'{name}'" for name in names)


def _rows_by_key(rows: Iterable[dict[str, Any]], *keys: str) -> dict[tuple[str, ...], list[dict[str, Any]]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(str(row.get(key, "")).upper() for key in keys)].append(row)
    return grouped


class GfDerivativeDbProvider:
    """Fetch Oracle metadata through the existing read-only CLI adapter."""

    def __init__(
        self,
        *,
        python_executable: str | Path,
        query_script: str | Path,
        database: str,
        max_rows: int = 100_000,
        timeout_seconds: int = 120,
        definition_mode: str = "record-only",
        runner: CommandRunner = _default_runner,
    ) -> None:
        if definition_mode not in {"record-only", "all"}:
            raise ValueError("definition_mode must be 'record-only' or 'all'")
        self.python_executable = str(python_executable)
        self.query_script = str(query_script)
        self.database = database
        self.max_rows = max_rows
        self.timeout_seconds = timeout_seconds
        self.definition_mode = definition_mode
        self.runner = runner

    def _run_result(
        self,
        *args: str,
        timeout_seconds: int | None = None,
    ) -> CommandResult:
        command = [self.python_executable, self.query_script, *args]
        command_timeout = timeout_seconds or self.timeout_seconds
        try:
            result = self.runner(command, command_timeout)
        except subprocess.TimeoutExpired as exc:
            raise AdapterError("TIMEOUT", "COMMAND_TIMEOUT") from exc
        except OSError as exc:
            raise AdapterError("FAILED", "COMMAND_START") from exc
        if result.returncode != 0:
            status, category = _classify_command_error(result.stderr)
            raise AdapterError(status, category)
        return result

    def _run(self, *args: str) -> str:
        return self._run_result(*args).stdout

    def _query_json(self, sql: str) -> list[dict[str, Any]]:
        text = self._run(
            "query",
            "--db",
            self.database,
            "--sql",
            sql,
            "--max-rows",
            str(self.max_rows),
            "--format",
            "json",
        )
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AdapterError("FAILED", "INVALID_JSON") from exc
        if not isinstance(payload, list) or not all(
            isinstance(row, dict) for row in payload
        ):
            raise AdapterError("FAILED", "UNEXPECTED_JSON_SHAPE")
        return payload

    def _fetch_objects(self, scope: ScopeConfig) -> list[dict[str, Any]]:
        owners = _owner_list(scope.schemas)
        types = ", ".join(
            f"'{object_type.replace('_', ' ')}'" for object_type in scope.object_types
        )
        return self._query_json(
            "SELECT OWNER, OBJECT_NAME, OBJECT_TYPE "
            "FROM ALL_OBJECTS "
            f"WHERE OWNER IN ({owners}) AND OBJECT_TYPE IN ({types}) "
            "ORDER BY OWNER, OBJECT_TYPE, OBJECT_NAME"
        )

    def _fetch_columns(self, scope: ScopeConfig) -> list[dict[str, Any]]:
        owners = _owner_list(scope.schemas)
        return self._query_json(
            "SELECT OWNER, TABLE_NAME, COLUMN_NAME, COLUMN_ID, DATA_TYPE, "
            "DATA_LENGTH, DATA_PRECISION, DATA_SCALE, NULLABLE "
            "FROM ALL_TAB_COLUMNS "
            f"WHERE OWNER IN ({owners}) "
            "ORDER BY OWNER, TABLE_NAME, COLUMN_ID"
        )

    def _fetch_column_comments(self, scope: ScopeConfig) -> list[dict[str, Any]]:
        owners = _owner_list(scope.schemas)
        return self._query_json(
            "SELECT OWNER, TABLE_NAME, COLUMN_NAME, COMMENTS "
            "FROM ALL_COL_COMMENTS "
            f"WHERE OWNER IN ({owners}) AND COMMENTS IS NOT NULL"
        )

    def _fetch_object_comments(self, scope: ScopeConfig) -> list[dict[str, Any]]:
        owners = _owner_list(scope.schemas)
        return self._query_json(
            "SELECT OWNER, TABLE_NAME, COMMENTS "
            "FROM ALL_TAB_COMMENTS "
            f"WHERE OWNER IN ({owners}) AND COMMENTS IS NOT NULL"
        )

    def _fetch_constraints(self, scope: ScopeConfig) -> list[dict[str, Any]]:
        owners = _owner_list(scope.schemas)
        return self._query_json(
            "SELECT OWNER, TABLE_NAME, CONSTRAINT_NAME, CONSTRAINT_TYPE, STATUS, "
            "R_OWNER, R_CONSTRAINT_NAME "
            "FROM ALL_CONSTRAINTS "
            f"WHERE OWNER IN ({owners})"
        )

    def _fetch_constraint_columns(self, scope: ScopeConfig) -> list[dict[str, Any]]:
        owners = _owner_list(scope.schemas)
        return self._query_json(
            "SELECT OWNER, TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME, POSITION "
            "FROM ALL_CONS_COLUMNS "
            f"WHERE OWNER IN ({owners}) ORDER BY OWNER, TABLE_NAME, CONSTRAINT_NAME, POSITION"
        )

    def _fetch_indexes(self, scope: ScopeConfig) -> list[dict[str, Any]]:
        owners = _owner_list(scope.schemas)
        return self._query_json(
            "SELECT OWNER, INDEX_NAME, TABLE_NAME, UNIQUENESS, INDEX_TYPE, STATUS "
            "FROM ALL_INDEXES "
            f"WHERE OWNER IN ({owners})"
        )

    def _fetch_index_columns(self, scope: ScopeConfig) -> list[dict[str, Any]]:
        owners = _owner_list(scope.schemas)
        return self._query_json(
            "SELECT INDEX_OWNER, INDEX_NAME, TABLE_NAME, COLUMN_NAME, COLUMN_POSITION "
            "FROM ALL_IND_COLUMNS "
            f"WHERE INDEX_OWNER IN ({owners}) ORDER BY INDEX_OWNER, INDEX_NAME, COLUMN_POSITION"
        )

    def _fetch_dependencies(self, scope: ScopeConfig) -> list[dict[str, Any]]:
        owners = _owner_list(scope.schemas)
        return self._query_json(
            "SELECT OWNER, NAME, TYPE, REFERENCED_OWNER, REFERENCED_NAME, REFERENCED_TYPE "
            "FROM ALL_DEPENDENCIES "
            f"WHERE OWNER IN ({owners})"
        )

    def _fetch_view_sql(self, scope: ScopeConfig) -> dict[tuple[str, str], str]:
        owners = _owner_list(scope.schemas)
        rows = self._query_json(
            "SELECT OWNER, VIEW_NAME, TEXT "
            "FROM ALL_VIEWS "
            f"WHERE OWNER IN ({owners}) ORDER BY OWNER, VIEW_NAME"
        )
        return {
            (
                str(row.get("OWNER", "")).upper(),
                str(row.get("VIEW_NAME", "")).upper(),
            ): str(row["TEXT"]).strip()
            for row in rows
            if row.get("OWNER") and row.get("VIEW_NAME") and row.get("TEXT")
        }

    def _fetch_batch_definitions(
        self,
        scope: ScopeConfig,
        output_dir: Path | None = None,
    ) -> dict[tuple[str, str], DefinitionMetadata] | _BatchDefinitionStore:
        supported_types = {
            "TABLE": "table",
            "VIEW": "view",
            "MATERIALIZED_VIEW": "materialized-view",
        }
        requested_types = [
            supported_types[object_type]
            for object_type in scope.object_types
            if object_type in supported_types
        ]
        if not requested_types:
            return {}
        args = ["ddl-batch", "--db", self.database]
        for schema_name in scope.schemas:
            args.extend(["--schema", schema_name])
        for object_type in requested_types:
            args.extend(["--type", object_type])
        args_with_output = list(args)
        if output_dir is not None:
            args_with_output.extend(["--output-dir", str(output_dir)])
        text = self._run_result(
            *args_with_output,
            timeout_seconds=max(self.timeout_seconds, 900),
        ).stdout
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AdapterError("FAILED", "INVALID_JSON") from exc
        if isinstance(payload, dict) and output_dir is not None:
            files = payload.get("files")
            if payload.get("format") != "titans-cognition-definitions-v1" or not isinstance(files, list):
                raise AdapterError("FAILED", "INVALID_BATCH_MANIFEST")
            return _BatchDefinitionStore.from_manifest(output_dir, files)
        if not isinstance(payload, list) or not all(
            isinstance(row, dict) for row in payload
        ):
            raise AdapterError("FAILED", "UNEXPECTED_JSON_SHAPE")
        definitions: dict[tuple[str, str], DefinitionMetadata] = {}
        for row in payload:
            schema_name = str(row.get("owner", "")).upper()
            object_name = str(row.get("object_name", "")).upper()
            if not schema_name or not object_name:
                continue
            definitions[(schema_name, object_name)] = DefinitionMetadata(
                definition_type=str(row.get("definition_type", "DDL")).upper(),
                definition_text=row.get("definition_text") or None,
                extraction_status=str(
                    row.get("extraction_status", "FAILED")
                ).upper(),
                error_category=row.get("error_category") or None,
            )
        return definitions

    def _fetch_adapter_definition(
        self,
        schema_name: str,
        object_name: str,
    ) -> DefinitionMetadata:
        try:
            result = self._run_result(
                "ddl",
                "--db",
                self.database,
                "--table",
                f"{schema_name}.{object_name}",
            )
        except AdapterError as exc:
            return DefinitionMetadata(
                definition_type="DDL",
                extraction_status=exc.status,
                error_category=exc.category,
            )
        definition_text = result.stdout.strip()
        if not definition_text:
            return DefinitionMetadata(
                definition_type="DDL",
                extraction_status="MISSING",
                error_category="EMPTY_DEFINITION",
            )
        return DefinitionMetadata(
            definition_type="DDL",
            definition_text=definition_text,
        )

    def _definition_for_object(
        self,
        schema_name: str,
        object_name: str,
        object_type: str,
        view_sql: dict[tuple[str, str], str] | None,
        view_sql_error: AdapterError | None,
        batch_definitions: dict[tuple[str, str], DefinitionMetadata] | _BatchDefinitionStore | None = None,
        batch_error: AdapterError | None = None,
    ) -> DefinitionMetadata:
        if self.definition_mode != "all":
            return DefinitionMetadata(
                definition_type="DDL",
                extraction_status="FAILED",
                error_category="PROVIDER_CAPABILITY_NOT_ENABLED",
            )
        if batch_error:
            return DefinitionMetadata(
                definition_type="VIEW_SQL" if object_type == "VIEW" else "DDL",
                extraction_status=batch_error.status,
                error_category=batch_error.category,
            )
        if batch_definitions is not None and object_type != "SYNONYM":
            return batch_definitions.get(
                (schema_name, object_name),
                DefinitionMetadata(
                    definition_type="VIEW_SQL" if object_type == "VIEW" else "DDL",
                    extraction_status="MISSING",
                    error_category="BATCH_OBJECT_NOT_RETURNED",
                ),
            )
        if object_type == "VIEW":
            if view_sql_error:
                return DefinitionMetadata(
                    definition_type="VIEW_SQL",
                    extraction_status=view_sql_error.status,
                    error_category=view_sql_error.category,
                )
            text = (view_sql or {}).get((schema_name, object_name))
            if not text:
                return DefinitionMetadata(
                    definition_type="VIEW_SQL",
                    extraction_status="MISSING",
                    error_category="VIEW_SQL_NOT_VISIBLE",
                )
            return DefinitionMetadata(
                definition_type="VIEW_SQL",
                definition_text=text,
            )
        if object_type == "SYNONYM":
            return DefinitionMetadata(
                definition_type="DDL",
                extraction_status="FAILED",
                error_category="ADAPTER_UNSUPPORTED_OBJECT_TYPE",
            )
        return self._fetch_adapter_definition(schema_name, object_name)

    def iter_objects(self, scope: ScopeConfig) -> Iterable[ObjectMetadata]:
        """Yield objects while cleaning up file-backed batch definitions."""
        if self.definition_mode != "all":
            yield from self._iter_objects(scope, None)
            return
        with tempfile.TemporaryDirectory(prefix="titans-cognition-definitions-") as raw_dir:
            yield from self._iter_objects(scope, Path(raw_dir))

    def _iter_objects(
        self,
        scope: ScopeConfig,
        batch_output_dir: Path | None,
    ) -> Iterable[ObjectMetadata]:
        """Yield all in-scope objects with metadata available from dictionary views."""

        object_rows = self._fetch_objects(scope)
        view_sql: dict[tuple[str, str], str] | None = None
        view_sql_error: AdapterError | None = None
        batch_definitions: dict[tuple[str, str], DefinitionMetadata] | _BatchDefinitionStore | None = None
        batch_error: AdapterError | None = None
        if self.definition_mode == "all":
            try:
                batch_definitions = self._fetch_batch_definitions(scope, batch_output_dir)
            except AdapterError as exc:
                batch_error = exc
        columns = _rows_by_key(self._fetch_columns(scope), "OWNER", "TABLE_NAME")
        column_comments = {
            (
                str(row.get("OWNER", "")).upper(),
                str(row.get("TABLE_NAME", "")).upper(),
                str(row.get("COLUMN_NAME", "")).upper(),
            ): row.get("COMMENTS")
            for row in self._fetch_column_comments(scope)
        }
        object_comments = {
            (
                str(row.get("OWNER", "")).upper(),
                str(row.get("TABLE_NAME", "")).upper(),
            ): row.get("COMMENTS")
            for row in self._fetch_object_comments(scope)
        }
        constraint_rows = self._fetch_constraints(scope)
        constraint_columns = _rows_by_key(
            self._fetch_constraint_columns(scope),
            "OWNER",
            "TABLE_NAME",
            "CONSTRAINT_NAME",
        )
        constraint_by_name = {
            (
                str(row.get("OWNER", "")).upper(),
                str(row.get("CONSTRAINT_NAME", "")).upper(),
            ): row
            for row in constraint_rows
        }
        index_rows = self._fetch_indexes(scope)
        index_columns = _rows_by_key(
            self._fetch_index_columns(scope), "INDEX_OWNER", "INDEX_NAME"
        )
        dependencies = _rows_by_key(self._fetch_dependencies(scope), "OWNER", "NAME")

        boundary_targets: dict[tuple[str, str, str], DependencyMetadata] = {}
        for row in object_rows:
            schema_name = str(row["OWNER"]).upper()
            object_name = str(row["OBJECT_NAME"]).upper()
            object_type = _canonical_type(str(row["OBJECT_TYPE"]))
            if not scope.accepts_object(schema_name, object_type):
                continue
            key = (schema_name, object_name)
            object_columns = tuple(
                ColumnMetadata(
                    column_name=str(item["COLUMN_NAME"]).upper(),
                    ordinal_position=int(item["COLUMN_ID"]),
                    data_type=str(item["DATA_TYPE"]),
                    data_length=_optional_int(item.get("DATA_LENGTH")),
                    data_precision=_optional_int(item.get("DATA_PRECISION")),
                    data_scale=_optional_int(item.get("DATA_SCALE")),
                    nullable_declared=str(item.get("NULLABLE", "")).upper() == "Y",
                    column_comment=column_comments.get(
                        (schema_name, object_name, str(item["COLUMN_NAME"]).upper())
                    ),
                )
                for item in sorted(
                    columns.get(key, []), key=lambda value: int(value["COLUMN_ID"])
                )
            )
            object_constraints = tuple(
                self._to_constraint(
                    item,
                    constraint_columns,
                    constraint_by_name,
                )
                for item in constraint_rows
                if str(item.get("OWNER", "")).upper() == schema_name
                and str(item.get("TABLE_NAME", "")).upper() == object_name
            )
            object_indexes = tuple(
                self._to_index(item, index_columns)
                for item in index_rows
                if str(item.get("OWNER", "")).upper() == schema_name
                and str(item.get("TABLE_NAME", "")).upper() == object_name
            )
            object_dependencies = tuple(
                DependencyMetadata(
                    target_schema_name=str(item["REFERENCED_OWNER"]),
                    target_object_name=str(item["REFERENCED_NAME"]),
                    dependency_type=str(item.get("TYPE", "UNKNOWN")),
                    target_object_type=str(item.get("REFERENCED_TYPE", "TABLE")),
                    target_is_boundary=not scope.accepts_schema(
                        str(item["REFERENCED_OWNER"])
                    ),
                )
                for item in dependencies.get(key, [])
                if item.get("REFERENCED_OWNER") and item.get("REFERENCED_NAME")
            )
            for dependency in object_dependencies:
                if dependency.target_is_boundary:
                    boundary_key = (
                        dependency.target_schema_name.upper(),
                        dependency.target_object_name.upper(),
                        _canonical_type(dependency.target_object_type),
                    )
                    boundary_targets[boundary_key] = dependency
            definition = self._definition_for_object(
                schema_name,
                object_name,
                object_type,
                view_sql,
                view_sql_error,
                batch_definitions,
                batch_error,
            )
            yield ObjectMetadata(
                schema_name=schema_name,
                object_name=object_name,
                object_type=object_type,
                object_comment=object_comments.get(key),
                columns=object_columns,
                constraints=object_constraints,
                indexes=object_indexes,
                dependencies=object_dependencies,
                definitions=(definition,),
            )

        for dependency in boundary_targets.values():
            yield ObjectMetadata(
                schema_name=dependency.target_schema_name,
                object_name=dependency.target_object_name,
                object_type=dependency.target_object_type,
                is_boundary=True,
                boundary_for_case_ids=(scope.scope_id,),
            )

    def _to_constraint(
        self,
        row: dict[str, Any],
        column_rows: dict[tuple[str, ...], list[dict[str, Any]]],
        constraint_by_name: dict[tuple[str, ...], dict[str, Any]],
    ) -> ConstraintMetadata:
        owner = str(row["OWNER"]).upper()
        table_name = str(row["TABLE_NAME"]).upper()
        constraint_name = str(row["CONSTRAINT_NAME"]).upper()
        names = tuple(
            str(item["COLUMN_NAME"]).upper()
            for item in sorted(
                column_rows.get((owner, table_name, constraint_name), []),
                key=lambda value: int(value.get("POSITION") or 0),
            )
        )
        referenced_asset_id = None
        referenced_column_names: tuple[str, ...] = ()
        referenced_owner = row.get("R_OWNER")
        referenced_constraint_name = row.get("R_CONSTRAINT_NAME")
        if referenced_owner and referenced_constraint_name:
            target_key = (
                str(referenced_owner).upper(),
                str(referenced_constraint_name).upper(),
            )
            target = constraint_by_name.get(target_key)
            if target:
                target_table = str(target["TABLE_NAME"]).upper()
                referenced_asset_id = asset_id(
                    self.database,
                    str(referenced_owner),
                    "TABLE",
                    target_table,
                )
                referenced_column_names = tuple(
                    str(item["COLUMN_NAME"]).upper()
                    for item in column_rows.get(
                        (
                            str(referenced_owner).upper(),
                            target_table,
                            str(referenced_constraint_name).upper(),
                        ),
                        []
                    )
                )
        return ConstraintMetadata(
            constraint_name=constraint_name,
            constraint_type=_constraint_type(str(row.get("CONSTRAINT_TYPE", ""))),
            column_names=names,
            referenced_asset_id=referenced_asset_id,
            referenced_column_names=referenced_column_names,
            declared_status=row.get("STATUS"),
        )

    @staticmethod
    def _to_index(
        row: dict[str, Any],
        column_rows: dict[tuple[str, ...], list[dict[str, Any]]],
    ) -> IndexMetadata:
        owner = str(row["OWNER"]).upper()
        index_name = str(row["INDEX_NAME"]).upper()
        names = tuple(
            str(item["COLUMN_NAME"]).upper()
            for item in sorted(
                column_rows.get((owner, index_name), []),
                key=lambda value: int(value.get("COLUMN_POSITION") or 0),
            )
        )
        return IndexMetadata(
            index_name=index_name,
            is_unique=str(row.get("UNIQUENESS", "")).upper() == "UNIQUE",
            index_type=row.get("INDEX_TYPE"),
            column_names=names,
            declared_status=row.get("STATUS"),
        )


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _classify_command_error(stderr: str) -> tuple[str, str]:
    """Map adapter diagnostics to non-sensitive contract status categories."""

    text = stderr.upper()
    if "PRIVILEGE" in text or "PERMISSION" in text or "ORA-01031" in text:
        return "NO_PERMISSION", "ADAPTER_PERMISSION"
    if "MULTIPLE LOCATIONS" in text or "AMBIGUOUS" in text:
        return "AMBIGUOUS", "OBJECT_AMBIGUOUS"
    if "NOT FOUND" in text or "DID NOT RETURN DDL" in text:
        return "MISSING", "OBJECT_DEFINITION_NOT_FOUND"
    return "FAILED", "ADAPTER_COMMAND"


def _constraint_type(value: str) -> str:
    return {
        "P": "PRIMARY_KEY",
        "U": "UNIQUE_KEY",
        "R": "FOREIGN_KEY",
        "C": "CHECK",
    }.get(value.upper(), value.upper() or "UNKNOWN")
