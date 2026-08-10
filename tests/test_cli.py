import json

from titans_cognition.cli import main


def test_extract_command_writes_json_facts(tmp_path, capsys):
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "objects": [
                    {
                        "schema_name": "TITANS_TRADEFLOW",
                        "object_name": "T_EVENT",
                        "object_type": "TABLE",
                        "columns": [
                            {
                                "column_name": "ID",
                                "ordinal_position": 1,
                                "data_type": "NUMBER",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    scope_path = tmp_path / "scope.yaml"
    scope_path.write_text(
        """
scope_id: test-scope
source_label: testdb
include:
  schemas: [TITANS_TRADEFLOW]
  object_types: [TABLE]
exclude: {}
""",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "extract",
                "--scope",
                str(scope_path),
                "--input-json",
                str(metadata_path),
                "--output",
                str(tmp_path / "output"),
                "--run-id",
                "run-001",
            ]
        )
        == 0
    )

    output = json.loads(capsys.readouterr().out)
    assert output["object_count"] == 1
    assert (tmp_path / "output" / "panorama" / "facts" / "objects.json").exists()

    assert (
        main(
            [
                "derive",
                "--input-dir",
                str(tmp_path / "output"),
                "--output",
                str(tmp_path / "derived-output"),
            ]
        )
        == 0
    )

    derived_output = json.loads(capsys.readouterr().out)
    assert derived_output["schema_count"] == 1
    assert (
        tmp_path
        / "derived-output"
        / "panorama"
        / "derived"
        / "schema_summary.json"
    ).exists()

    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(
            {
                "objects": [
                    {
                        "schema_name": "TITANS_TRADEFLOW",
                        "object_type": "TABLE",
                        "object_name": "T_EVENT",
                    }
                ],
                "columns": [{"schema_name": "TITANS_TRADEFLOW", "column_count": 1}],
            }
        ),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "reconcile",
                "--scope",
                str(scope_path),
                "--facts-dir",
                str(tmp_path / "output"),
                "--baseline-json",
                str(baseline_path),
                "--output",
                str(tmp_path / "reconciliation.json"),
            ]
        )
        == 0
    )

    reconciliation = json.loads(capsys.readouterr().out)
    assert reconciliation["data_reconciliation_status"] == "PASS"
    assert reconciliation["gate_a_status"] == "BLOCKED"

    assert (
        main(
            [
                "render",
                "--scope",
                str(scope_path),
                "--facts-dir",
                str(tmp_path / "output"),
                "--output",
                str(tmp_path / "rendered"),
                "--code-version",
                "test-commit",
            ]
        )
        == 0
    )

    rendered = json.loads(capsys.readouterr().out)
    assert rendered["schema_page_count"] == 1
    assert rendered["object_card_count"] == 1
    assert (tmp_path / "rendered" / "panorama" / "index.html").exists()
    assert (tmp_path / "rendered" / "manifest.json").exists()

    assert (
        main(
            [
                "reconcile",
                "--scope",
                str(scope_path),
                "--facts-dir",
                str(tmp_path / "output"),
                "--baseline-json",
                str(baseline_path),
                "--render-dir",
                str(tmp_path / "rendered"),
            ]
        )
        == 0
    )
    delivered_reconciliation = json.loads(capsys.readouterr().out)
    assert delivered_reconciliation["data_reconciliation_status"] == "PASS"
    assert delivered_reconciliation["gate_a_status"] == "PASS"
