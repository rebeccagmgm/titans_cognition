"""Writing canonical V1A fact datasets without mutating source facts."""

import json
from pathlib import Path
from typing import Any

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
