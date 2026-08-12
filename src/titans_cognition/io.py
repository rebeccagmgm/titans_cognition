"""Writing canonical V1A fact datasets without mutating source facts."""

import json
import os
from pathlib import Path
import tempfile
from collections.abc import Iterable
from typing import Any

from .derive import DerivedObservations
from .deep import TradeflowDerived
from .extract import PhysicalFacts
from .inference import TradeflowInference


class ResultWriteError(RuntimeError):
    """Raised when a result bundle cannot be written."""


def _write_json(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _json_fact_paths(output_dir: str | Path) -> dict[str, Path]:
    root = Path(output_dir)
    return {
        "objects": root / "panorama" / "facts" / "objects.json",
        "columns": root / "panorama" / "facts" / "columns.json",
        "constraints": root / "panorama" / "facts" / "constraints.json",
        "indexes": root / "panorama" / "facts" / "indexes.json",
        "object_definitions": root / "panorama" / "facts" / "object_definitions.json",
        "dependencies": root / "panorama" / "facts" / "dependencies.json",
        "failures": root / "panorama" / "derived" / "extraction_failures.json",
    }


def write_json_fact_batches(
    output_dir: str | Path,
    batches: Iterable[PhysicalFacts],
) -> dict[str, Path]:
    """Write fact batches without retaining the complete bundle in memory.

    All datasets are first written to temporary files. Existing canonical files are
    replaced only after every batch has been consumed successfully.
    """

    root = Path(output_dir)
    paths = _json_fact_paths(root)
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)

    rows_by_name = {
        "objects": "objects",
        "columns": "columns",
        "constraints": "constraints",
        "indexes": "indexes",
        "object_definitions": "object_definitions",
        "dependencies": "dependencies",
        "failures": "failures",
    }
    temp_root = Path(tempfile.mkdtemp(prefix=".facts-", dir=root))
    handles: dict[str, Any] = {}
    first_row: dict[str, bool] = {}
    temp_paths: dict[str, Path] = {}
    backups: dict[str, Path] = {}
    committed: list[str] = []
    try:
        for name in rows_by_name:
            temp_path = temp_root / f"{name}.json"
            temp_paths[name] = temp_path
            handle = temp_path.open("w", encoding="utf-8", newline="\n")
            handle.write("[\n")
            handles[name] = handle
            first_row[name] = True

        for batch in batches:
            for name, attribute in rows_by_name.items():
                for row in getattr(batch, attribute):
                    if not first_row[name]:
                        handles[name].write(",\n")
                    json.dump(
                        row,
                        handles[name],
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    first_row[name] = False

        for name, handle in handles.items():
            handle.write("\n]\n")
            handle.close()
        handles.clear()
        for name, temp_path in temp_paths.items():
            target = paths[name]
            if target.exists():
                backup = temp_root / f".backup-{name}.json"
                os.replace(target, backup)
                backups[name] = backup
            os.replace(temp_path, paths[name])
            committed.append(name)
    except Exception:
        for name in reversed(committed):
            paths[name].unlink(missing_ok=True)
            backup = backups.get(name)
            if backup and backup.exists():
                os.replace(backup, paths[name])
        for name, backup in backups.items():
            if name not in committed and backup.exists():
                os.replace(backup, paths[name])
        for handle in handles.values():
            handle.close()
        raise
    finally:
        for handle in handles.values():
            handle.close()
        for temp_path in temp_paths.values():
            temp_path.unlink(missing_ok=True)
        for backup in backups.values():
            backup.unlink(missing_ok=True)
        temp_root.rmdir()
    return paths


def write_json_facts(output_dir: str | Path, facts: PhysicalFacts) -> dict[str, Path]:
    """Write a portable JSON representation of all current physical fact rows."""

    write_json_fact_batches(output_dir, [facts])
    paths = _json_fact_paths(output_dir)
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


def write_json_tradeflow_derived(
    output_dir: str | Path,
    derived: TradeflowDerived,
) -> dict[str, Path]:
    """Write bounded V1B physical features below the Deep Case namespace."""

    root = Path(output_dir) / "deep-cases" / "tradeflow" / "derived"
    rows_by_name = {
        "sample_objects": derived.sample_objects,
        "column_features": derived.column_features,
        "object_features": derived.object_features,
        "structure_similarity": derived.structure_similarity,
    }
    paths: dict[str, Path] = {}
    for name, rows in rows_by_name.items():
        path = root / f"{name}.json"
        _write_json(path, rows)
        paths[name] = path
    return paths


def write_json_tradeflow_inference(
    output_dir: str | Path,
    inference: TradeflowInference,
) -> dict[str, Path]:
    """Write typed V1B candidates, results, and evidence as JSON."""

    root = Path(output_dir) / "deep-cases" / "tradeflow"
    rows_by_path = {
        "candidates/identity_candidates": inference.identity_candidates,
        "candidates/grain_candidates": inference.grain_candidates,
        "candidates/field_role_candidates": inference.field_role_candidates,
        "candidates/object_role_candidates": inference.object_role_candidates,
        "candidates/relation_candidates": inference.relation_candidates,
        "candidates/inference_results": inference.inference_results,
        "evidence/evidence_items": inference.evidence_items,
        "evidence/candidate_evidence": inference.candidate_evidence,
    }
    paths: dict[str, Path] = {}
    for name, rows in rows_by_path.items():
        path = root / f"{name}.json"
        _write_json(path, rows)
        paths[name] = path
    return paths
