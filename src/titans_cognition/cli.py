"""Command-line entry points for the deterministic V1A core."""

import argparse
import json
from pathlib import Path
from typing import Any

from .extract import (
    ColumnMetadata,
    ConstraintMetadata,
    DefinitionMetadata,
    DependencyMetadata,
    IndexMetadata,
    ObjectMetadata,
    extract_facts,
)
from .io import write_json_facts, write_parquet_facts
from .provider import GfDerivativeDbProvider
from .scope import load_scope


def _object_metadata_from_mapping(data: dict[str, Any]) -> ObjectMetadata:
    return ObjectMetadata(
        schema_name=data["schema_name"],
        object_name=data["object_name"],
        object_type=data["object_type"],
        object_comment=data.get("object_comment"),
        columns=tuple(ColumnMetadata(**item) for item in data.get("columns", [])),
        constraints=tuple(
            ConstraintMetadata(
                **{
                    **item,
                    "column_names": tuple(item.get("column_names", [])),
                    "referenced_column_names": tuple(
                        item.get("referenced_column_names", [])
                    ),
                }
            )
            for item in data.get("constraints", [])
        ),
        indexes=tuple(
            IndexMetadata(
                **{
                    **item,
                    "column_names": tuple(item.get("column_names", [])),
                    "expressions": tuple(item.get("expressions", [])),
                }
            )
            for item in data.get("indexes", [])
        ),
        definitions=tuple(
            DefinitionMetadata(**item) for item in data.get("definitions", [])
        ),
        dependencies=tuple(
            DependencyMetadata(**item) for item in data.get("dependencies", [])
        ),
        is_boundary=data.get("is_boundary", False),
        boundary_for_case_ids=tuple(data.get("boundary_for_case_ids", [])),
        extraction_status=data.get("extraction_status", "SUCCESS"),
        error_category=data.get("error_category"),
    )


def _load_metadata_json(path: Path) -> list[ObjectMetadata]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("objects", payload) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError("metadata JSON must be a list or an object with an objects list")
    return [_object_metadata_from_mapping(item) for item in records]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="titans-cognition")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-scope")
    validate.add_argument("--scope", required=True, type=Path)

    extract = subparsers.add_parser("extract")
    extract.add_argument("--scope", required=True, type=Path)
    source = extract.add_mutually_exclusive_group(required=True)
    source.add_argument("--input-json", type=Path)
    source.add_argument("--db")
    extract.add_argument("--adapter-python", default="python")
    extract.add_argument("--adapter-script", type=Path)
    extract.add_argument(
        "--definition-mode",
        choices=("record-only", "all"),
        default="record-only",
        help="record capability gaps or retrieve DDL/View SQL",
    )
    extract.add_argument("--output", required=True, type=Path)
    extract.add_argument("--run-id", required=True)
    extract.add_argument(
        "--format",
        choices=("json", "parquet", "both"),
        default="json",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "validate-scope":
        scope = load_scope(args.scope)
        print(
            json.dumps(
                {
                    "scope_id": scope.scope_id,
                    "source_label": scope.source_label,
                    "schema_count": len(scope.schemas),
                    "object_types": list(scope.object_types),
                },
                ensure_ascii=False,
            )
        )
        return 0

    scope = load_scope(args.scope)
    if args.input_json:
        metadata = _load_metadata_json(args.input_json)
    else:
        if not args.adapter_script:
            raise ValueError("--adapter-script is required when --db is used")
        provider = GfDerivativeDbProvider(
            python_executable=args.adapter_python,
            query_script=args.adapter_script,
            database=args.db,
            definition_mode=args.definition_mode,
        )
        metadata = provider.iter_objects(scope)
    facts = extract_facts(
        scope,
        metadata,
        run_id=args.run_id,
    )
    written: dict[str, Path] = {}
    if args.format in ("json", "both"):
        written.update(write_json_facts(args.output, facts))
    if args.format in ("parquet", "both"):
        written.update(write_parquet_facts(args.output, facts))
    print(
        json.dumps(
            {
                "run_id": args.run_id,
                "object_count": len(facts.objects),
                "column_count": len(facts.columns),
                "constraint_count": len(facts.constraints),
                "index_count": len(facts.indexes),
                "dependency_count": len(facts.dependencies),
                "failure_count": len(facts.failures),
                "outputs": {name: str(path) for name, path in written.items()},
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
