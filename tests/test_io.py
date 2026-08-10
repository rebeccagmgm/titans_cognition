import json

from titans_cognition.extract import PhysicalFacts
from titans_cognition.io import write_json_facts


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
