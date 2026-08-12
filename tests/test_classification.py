import json

import pytest

from titans_cognition.classification import (
    load_classification_config,
    run_classification,
    run_llm_interpretation,
    validate_llm_response,
    write_classification_results,
)
from titans_cognition.extract import PhysicalFacts


def _facts() -> PhysicalFacts:
    objects = []
    columns = []
    constraints = []
    for schema, name, comment, field_names in [
        (
            "TITANS_TRADEFLOW",
            "REF_OPTION_DEAL",
            "期权交易簿记",
            ["ID", "CONTRACT_ID", "TRADE_DATE", "STATUS"],
        ),
        (
            "TITANS_TRADEFLOW",
            "REF_OPTION_DEAL_STRIKE",
            "期权交易行权信息",
            ["ID", "CONTRACT_ID", "TRADE_DATE", "STRIKE_PRICE"],
        ),
        (
            "TITANS_TRADING",
            "SWAP_CONTRACT",
            "互换合约簿记",
            ["ID", "CONTRACT_ID", "EFFECTIVE_DATE", "STATUS"],
        ),
        (
            "TITANS_TRADING",
            "SWAP_CONTRACT_EVENT",
            "互换合约存续期事件",
            ["ID", "CONTRACT_ID", "EFFECTIVE_DATE", "EVENT_TYPE"],
        ),
        (
            "TITANS_ADMIN",
            "ADM_HEARTBEAT",
            "技术心跳",
            ["ID", "UPDATE_TIME"],
        ),
    ]:
        asset_id = f"testdb:{schema}:TABLE:{name}"
        objects.append(
            {
                "run_id": "synthetic-run",
                "asset_id": asset_id,
                "source_label": "testdb",
                "schema_name": schema,
                "object_name": name,
                "object_type": "TABLE",
                "in_panorama_scope": True,
                "is_boundary": False,
                "object_comment": comment,
                "extraction_status": "SUCCESS",
            }
        )
        for position, field_name in enumerate(field_names, 1):
            columns.append(
                {
                    "asset_id": asset_id,
                    "column_id": f"{asset_id}:COLUMN:{field_name}",
                    "column_name": field_name,
                    "ordinal_position": position,
                    "data_type": "NUMBER" if field_name in {"ID", "STRIKE_PRICE"} else "VARCHAR2",
                    "column_comment": field_name,
                }
            )
        constraints.append(
            {
                "asset_id": asset_id,
                "constraint_id": f"{asset_id}:PK",
                "constraint_type": "PRIMARY_KEY",
                "column_ids": [f"{asset_id}:COLUMN:ID"],
                "extraction_status": "SUCCESS",
            }
        )
    return PhysicalFacts(
        objects=objects,
        columns=columns,
        constraints=constraints,
        indexes=[],
        object_definitions=[],
        dependencies=[],
        failures=[],
    )


def _config(tmp_path):
    path = tmp_path / "classification.yaml"
    path.write_text(
        """
version: v1
wiki_source:
  page_id: "175428801"
limits:
  top_k: 3
  max_candidate_pairs: 100
  max_edges: 30
  rare_token_max_frequency: 10
  propagation_max_iterations: 20
  llm_max_families: 5
matching:
  min_edge_score: 0.18
  cross_schema_min_signals: 2
families:
  min_size: 2
  min_multi_view_edges: 1
propagation:
  alpha: 0.75
  tolerance: 0.000001
  candidate_threshold: 0.20
  competition_margin: 0.05
  max_candidates_per_dimension: 3
taxonomy:
  business_line:
    OPTION:
      terms: [OPTION, 期权]
    SWAP:
      terms: [SWAP, 互换]
  business_capability:
    CONTRACT_BOOKING:
      terms: [DEAL, CONTRACT, 合约, 簿记]
  technical_role:
    VIEW_PROJECTION:
      object_types: [VIEW]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return load_classification_config(path)


def _wiki_metadata():
    return {
        "pageId": "175428801",
        "title": "研发分工",
        "version": 44,
        "contentHash": "abc123",
        "cachedAt": 1786430709879,
    }


def test_classification_builds_graph_families_and_bounded_results(tmp_path):
    result = run_classification(_facts(), _config(tmp_path), _wiki_metadata())

    assert result.similarity_edges
    assert all(row["graph_run_id"] == result.graph_run_id for row in result.similarity_edges)
    assert all("signal_scores" in row for row in result.similarity_edges)
    assert all(row["status"] in {"CANDIDATE", "WEAK"} for row in result.family_candidates)
    assert all("business_category" not in row for row in result.community_partitions)
    assert all(row["outcome"] != "ACCEPTED" for row in result.classification_results)
    assert any(row["outcome"] == "UNKNOWN" for row in result.classification_results)


def test_label_sources_are_deduplicated_by_source_family(tmp_path):
    result = run_classification(_facts(), _config(tmp_path), _wiki_metadata())
    option_asset = "testdb:TITANS_TRADEFLOW:TABLE:REF_OPTION_DEAL"
    option_rows = [
        row
        for row in result.label_source_outputs
        if row["asset_id"] == option_asset
        and row["dimension"] == "business_line"
        and row["label"] == "OPTION"
    ]

    assert option_rows
    assert len({(row["source_family"], row["label"]) for row in option_rows}) == len(option_rows)
    assert all(row["method_id"] != "LF_CLUSTER_NEIGHBOR" for row in result.label_source_outputs)
    assert all("candidate_family" not in row["source_family"].lower() for row in option_rows)


def test_llm_disabled_and_invalid_references_are_preserved(tmp_path):
    result = run_classification(_facts(), _config(tmp_path), _wiki_metadata())
    llm_rows = run_llm_interpretation(result.evidence_packs, mode="disabled")
    assert llm_rows
    assert all(row["evaluation_eligibility"] == "NOT_EVALUABLE" for row in llm_rows)

    pack = result.evidence_packs[0]
    with pytest.raises(ValueError, match="Evidence"):
        validate_llm_response(
            pack,
            {
                "model_action": "RESPOND",
                "proposed_name": "期权交易",
                "candidate_labels": ["OPTION"],
                "supported_by": ["fabricated-evidence"],
                "contradicted_by": [],
                "uncertainties": [],
            },
        )


def test_writer_is_replayable_and_emits_review_page(tmp_path):
    result = run_classification(_facts(), _config(tmp_path), _wiki_metadata())
    first = write_classification_results(tmp_path / "first", result, formats=("json", "parquet"))
    second = write_classification_results(tmp_path / "second", result, formats=("json", "parquet"))

    first_manifest = json.loads(first["manifest"].read_text(encoding="utf-8"))
    second_manifest = json.loads(second["manifest"].read_text(encoding="utf-8"))
    first_hashes = {row["logical_name"]: row["content_sha256"] for row in first_manifest["outputs"]}
    second_hashes = {row["logical_name"]: row["content_sha256"] for row in second_manifest["outputs"]}
    assert first_hashes == second_hashes
    html = first["review_index"].read_text(encoding="utf-8")
    assert "尚未业务验收" in html
    assert "Unknown" in html
