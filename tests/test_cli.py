import json

from titans_cognition.cli import main
from titans_cognition.extract import PhysicalFacts
from titans_cognition.io import write_json_facts


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


def test_deep_review_pack_cli_never_reports_scale_authorization(tmp_path, capsys):
    report_path = tmp_path / "evaluation-report.json"
    report_path.write_text(
        json.dumps(
            {
                "gold_set_status": "ADJUDICATED",
                "gold_set_case_count": 0,
                "adjudicated_case_count": 0,
                "gate_b": {
                    "status": "PASS",
                    "reasons": [],
                },
                "business_acceptance": {"status": "NOT_ACCEPTED"},
                "scale_authorization": {"status": "PROHIBITED"},
                "case_reports": [],
            }
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "deep-review-pack",
                "--evaluation-report",
                str(report_path),
                "--output",
                str(tmp_path / "review-pack.md"),
            ]
        )
        == 0
    )

    output = json.loads(capsys.readouterr().out)
    assert output["gate_b_status"] == "PASS"
    assert output["gate_b_scope"] == "STRUCTURAL_REGRESSION_ONLY"
    assert output["business_acceptance_status"] == "NOT_ACCEPTED"
    assert output["scale_authorization_status"] == "PROHIBITED"
    assert output["v1c_authorized"] is False


def test_classify_panorama_cli_filters_one_schema(tmp_path, capsys):
    facts = PhysicalFacts(
        objects=[
            {
                "run_id": "run-001",
                "asset_id": "testdb:TITANS_TRADEFLOW:TABLE:REF_OPTION_DEAL",
                "schema_name": "TITANS_TRADEFLOW",
                "object_name": "REF_OPTION_DEAL",
                "object_type": "TABLE",
                "object_comment": "期权交易簿记",
                "in_panorama_scope": True,
                "is_boundary": False,
            },
            {
                "run_id": "run-001",
                "asset_id": "testdb:TITANS_ADMIN:TABLE:ADM_USER",
                "schema_name": "TITANS_ADMIN",
                "object_name": "ADM_USER",
                "object_type": "TABLE",
                "object_comment": "用户配置",
                "in_panorama_scope": True,
                "is_boundary": False,
            },
        ],
        columns=[
            {
                "asset_id": "testdb:TITANS_TRADEFLOW:TABLE:REF_OPTION_DEAL",
                "column_id": "trade-id",
                "column_name": "ID",
                "data_type": "NUMBER",
            },
            {
                "asset_id": "testdb:TITANS_ADMIN:TABLE:ADM_USER",
                "column_id": "user-id",
                "column_name": "ID",
                "data_type": "NUMBER",
            },
        ],
    )
    facts_dir = tmp_path / "facts"
    write_json_facts(facts_dir, facts)
    config = tmp_path / "classification.yaml"
    config.write_text(
        """
wiki_source: {page_id: "175428801"}
limits:
  top_k: 2
  max_candidate_pairs: 10
  max_edges: 10
  propagation_max_iterations: 5
  llm_max_families: 2
matching: {min_edge_score: 0.2}
families: {min_size: 2, min_multi_view_edges: 1}
propagation: {max_candidates_per_dimension: 2}
taxonomy:
  business_line:
    OPTION: {terms: [OPTION]}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    wiki = tmp_path / "wiki.json"
    wiki.write_text(
        json.dumps(
            {
                "pageId": "175428801",
                "title": "研发分工",
                "version": 44,
                "contentHash": "abc123",
                "cachedAt": 1786430709879,
            }
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "classify-panorama",
                "--facts-dir",
                str(facts_dir),
                "--config",
                str(config),
                "--wiki-metadata",
                str(wiki),
                "--output",
                str(tmp_path / "classified"),
                "--schema",
                "TITANS_TRADEFLOW",
                "--format",
                "json",
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["object_count"] == 1
    assert output["schema"] == "TITANS_TRADEFLOW"
    assert (tmp_path / "classified" / "classification-manifest.json").exists()
