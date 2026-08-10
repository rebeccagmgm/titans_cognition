"""Writing canonical V1A fact datasets without mutating source facts."""

import json
from pathlib import Path
from typing import Any

from .derive import DerivedObservations
from .extract import PhysicalFacts


class ResultWriteError(RuntimeError):
    """Raised when a result bundle cannot be written."""


def _write_json(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_json_facts(output_dir: str | Path, facts: PhysicalFacts) -> dict[str, Path]:
    """Write a portable JSON representation of all current physical fact rows."""

    root = Path(output_dir)
    paths = {
        "objects": root / "panorama" / "facts" / "objects.json",
        "columns": root / "panorama" / "facts" / "columns.json",
        "constraints": root / "panorama" / "facts" / "constraints.json",
        "indexes": root / "panorama" / "facts" / "indexes.json",
        "object_definitions": root / "panorama" / "facts" / "object_definitions.json",
        "dependencies": root / "panorama" / "facts" / "dependencies.json",
        "failures": root / "panorama" / "derived" / "extraction_failures.json",
    }
    _write_json(paths["objects"], facts.objects)
    _write_json(paths["columns"], facts.columns)
    _write_json(paths["constraints"], facts.constraints)
    _write_json(paths["indexes"], facts.indexes)
    _write_json(paths["object_definitions"], facts.object_definitions)
    _write_json(paths["dependencies"], facts.dependencies)
    _write_json(paths["failures"], facts.failures)
    return paths


def read_json_facts(input_dir: str | Path) -> PhysicalFacts:
    """Read the JSON canonical facts written by ``write_json_facts``."""

    root = Path(input_dir)

    def read(name: str, subdirectory: str = "facts") -> list[dict[str, object]]:
        path = root / "panorama" / subdirectory / f"{name}.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ResultWriteError(f"missing canonical facts file: {path}") from exc
        if not isinstance(value, list) or not all(
            isinstance(row, dict) for row in value
        ):
            raise ResultWriteError(f"canonical facts file is not a row list: {path}")
        return value

    return PhysicalFacts(
        objects=read("objects"),
        columns=read("columns"),
        constraints=read("constraints"),
        indexes=read("indexes"),
        object_definitions=read("object_definitions"),
        dependencies=read("dependencies"),
        failures=read("extraction_failures", "derived"),
    )


def write_json_derived(
    output_dir: str | Path,
    derived: DerivedObservations,
) -> dict[str, Path]:
    """Write deterministic V1A derived observations as JSON."""

    root = Path(output_dir)
    rows_by_name = {
        "schema_summary": derived.schema_summary,
        "object_inventory_profiles": derived.object_inventory_profiles,
        "dependency_summary": derived.dependency_summary,
        "extraction_failures": derived.extraction_failures,
    }
    paths: dict[str, Path] = {}
    for name, rows in rows_by_name.items():
        path = root / "panorama" / "derived" / f"{name}.json"
        _write_json(path, rows)
        paths[name] = path
    return paths


def write_parquet_facts(output_dir: str | Path, facts: PhysicalFacts) -> dict[str, Path]:
    """Write canonical fact tables as Parquet when the project dependency is installed."""

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ResultWriteError(
            "Parquet output requires the project dependency 'pyarrow'"
        ) from exc

    root = Path(output_dir)
    rows_by_name = {
        "objects": facts.objects,
        "columns": facts.columns,
        "constraints": facts.constraints,
        "indexes": facts.indexes,
        "object_definitions": facts.object_definitions,
        "dependencies": facts.dependencies,
        "extraction_failures": facts.failures,
    }
    paths: dict[str, Path] = {}
    for name, rows in rows_by_name.items():
        subdirectory = "derived" if name == "extraction_failures" else "facts"
        path = root / "panorama" / subdirectory / f"{name}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        table = pa.Table.from_pylist(rows)
        pq.write_table(table, path)
        paths[name] = path
    return paths


def write_parquet_derived(
    output_dir: str | Path,
    derived: DerivedObservations,
) -> dict[str, Path]:
    """Write deterministic V1A derived observations as Parquet."""

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ResultWriteError(
            "Parquet output requires the project dependency 'pyarrow'"
        ) from exc

    root = Path(output_dir)
    rows_by_name = {
        "schema_summary": derived.schema_summary,
        "object_inventory_profiles": derived.object_inventory_profiles,
        "dependency_summary": derived.dependency_summary,
        "extraction_failures": derived.extraction_failures,
    }
    paths: dict[str, Path] = {}
    for name, rows in rows_by_name.items():
        path = root / "panorama" / "derived" / f"{name}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pylist(rows), path)
        paths[name] = path
    return paths
