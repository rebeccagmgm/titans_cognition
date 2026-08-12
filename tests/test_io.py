import json
from pathlib import Path

import titans_cognition.io as io_module
from titans_cognition.extract import PhysicalFacts
from titans_cognition.io import write_json_fact_batches, write_json_facts


def test_write_json_facts_preserves_contract_dataset_paths(tmp_path):
    paths = write_json_facts(
        tmp_path / "run-001",
        PhysicalFacts(
            objects=[{"asset_id": "testdb:TITANS_DM:TABLE:T_A"}],
            failures=[{"target_id": "x", "failure_status": "FAILED"}],
        ),
    )

    assert paths["objects"].as_posix().endswith(
        "panorama/facts/objects.json"
    )
    assert paths["failures"].as_posix().endswith(
        "panorama/derived/extraction_failures.json"
    )
    assert json.loads(paths["objects"].read_text(encoding="utf-8")) == [
        {"asset_id": "testdb:TITANS_DM:TABLE:T_A"}
    ]


def test_write_json_fact_batches_streams_and_commits_all_datasets(tmp_path):
    output_dir = tmp_path / "run-002"
    batches = [
        PhysicalFacts(objects=[{"asset_id": "A"}], columns=[{"column_id": "A:C"}]),
        PhysicalFacts(objects=[{"asset_id": "B"}], columns=[{"column_id": "B:C"}]),
    ]

    paths = write_json_fact_batches(output_dir, iter(batches))

    assert json.loads(paths["objects"].read_text(encoding="utf-8")) == [
        {"asset_id": "A"},
        {"asset_id": "B"},
    ]
    assert json.loads(paths["columns"].read_text(encoding="utf-8")) == [
        {"column_id": "A:C"},
        {"column_id": "B:C"},
    ]
    assert not list(output_dir.glob(".facts-*"))


def test_write_json_fact_batches_keeps_existing_files_on_source_failure(tmp_path):
    output_dir = tmp_path / "run-003"
    paths = write_json_facts(
        output_dir,
        PhysicalFacts(objects=[{"asset_id": "OLD"}]),
    )

    def broken_batches():
        yield PhysicalFacts(objects=[{"asset_id": "NEW"}])
        raise RuntimeError("source failed")

    try:
        write_json_fact_batches(output_dir, broken_batches())
    except RuntimeError as exc:
        assert str(exc) == "source failed"
    else:
        raise AssertionError("expected source failure")

    assert json.loads(paths["objects"].read_text(encoding="utf-8")) == [
        {"asset_id": "OLD"}
    ]


def test_write_json_fact_batches_rolls_back_partial_commit(tmp_path, monkeypatch):
    output_dir = tmp_path / "run-004"
    paths = write_json_facts(
        output_dir,
        PhysicalFacts(
            objects=[{"asset_id": "OLD-OBJECT"}],
            columns=[{"column_id": "OLD-COLUMN"}],
        ),
    )
    original_replace = io_module.os.replace

    def fail_indexes_commit(source, target):
        source_path = Path(source)
        if (
            source_path.name == "indexes.json"
            and source_path.parent.name.startswith(".facts-")
        ):
            raise OSError("commit failed")
        return original_replace(source, target)

    monkeypatch.setattr(io_module.os, "replace", fail_indexes_commit)

    try:
        write_json_fact_batches(
            output_dir,
            [PhysicalFacts(objects=[{"asset_id": "NEW-OBJECT"}])],
        )
    except OSError as exc:
        assert str(exc) == "commit failed"
    else:
        raise AssertionError("expected commit failure")

    assert json.loads(paths["objects"].read_text(encoding="utf-8")) == [
        {"asset_id": "OLD-OBJECT"}
    ]
    assert json.loads(paths["columns"].read_text(encoding="utf-8")) == [
        {"column_id": "OLD-COLUMN"}
    ]
