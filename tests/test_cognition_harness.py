from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

from titans_cognition.cognition_harness import (
    HarnessError,
    OPERATION_ORDER,
    load_document,
    resolve_workspace_path,
    run_harness,
    sha256_file,
    validate_report,
    validate_review_input,
    validate_review_package,
    write_immutable_report,
)


ROOT = Path(__file__).resolve().parents[1]
PROFILE = "cases/cognition-governance/workflows/semantic-navigation.yaml"
SYNTHETIC_CASE = "tests/fixtures/cognition_harness/nova-rates-case-pack.yaml"
TRADEFLOW_CASE = "cases/tradeflow/semantic-navigation-case-pack.yaml"

ROLES = (
    "CHANGE_SCOPE",
    "FROZEN_INPUTS",
    "SEMANTIC_CONFIG",
    "FIELD_MANIFEST",
    "CONTEXT_MANIFEST",
    "TABLE_MANIFEST",
    "SURROGATE_REVIEW",
    "STATUS_BASELINE",
)


def _write_yaml(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def _workspace(
    tmp_path: Path,
    *,
    calls: int = 0,
    tokens: int = 0,
    isolation: bool = False,
) -> tuple[str, str]:
    profile = {
        "schema_version": "cognition-workflow-profile-v1",
        "profile_id": "semantic-navigation-governance-v1",
        "capability": "semantic-navigation",
        "operations": list(OPERATION_ORDER),
        "required_artifact_roles": list(ROLES),
        "mandatory_checkpoints": [
            "PREFLIGHT",
            "POST_STAGE",
            "PRE_REVIEW",
            "POST_REVIEW",
            "PRE_FINALIZE",
        ],
        "ambiguity_triggers": ["MISSING_METADATA", "MISLEADING_NAME"],
        "model_policy": {
            "default_calls": 0,
            "max_total_calls": calls,
            "max_total_tokens": tokens,
            "require_measured_usage": True,
        },
    }
    profile_path = tmp_path / "profile.yaml"
    _write_yaml(profile_path, profile)

    authority = tmp_path / "docs/spec/11-security-and-operations.md"
    authority.parent.mkdir(parents=True, exist_ok=True)
    authority.write_text("metadata only; no rows; no writes\n", encoding="utf-8")

    artifacts = []
    for index, role in enumerate(ROLES):
        artifact_dir = (
            tmp_path / "tests/fixtures/cognition_harness/runtime"
            if isolation
            else tmp_path / "artifacts"
        )
        path = artifact_dir / f"{index}-{role.lower()}.yaml"
        if isolation and role == "FROZEN_INPUTS":
            payload = {
                "schema_name": "NOVA_RATES",
                "objects": [
                    {
                        "object_name": "QUOTE_EVENT",
                        "comment": None,
                        "columns": [
                            {
                                "name": "STATUS",
                                "comment": "Counterparty display label",
                            },
                            {"name": "LEG_REF", "comment": None},
                        ],
                    },
                    {
                        "object_name": "PARTY_AMOUNT",
                        "comment": (
                            "Misleading amount-like table that stores party references."
                        ),
                        "columns": [
                            {
                                "name": "PARTY_ID",
                                "comment": "External participant key",
                            }
                        ],
                    },
                ],
                "missing_metadata": [
                    "QUOTE_EVENT.comment",
                    "QUOTE_EVENT.LEG_REF.comment",
                ],
                "ambiguous_relations": [
                    {
                        "left": "QUOTE_EVENT.LEG_REF",
                        "right": "PARTY_AMOUNT.PARTY_ID",
                        "reason": "Same type and overlapping values are not a proved business relation.",
                    }
                ],
                "misleading_names": [
                    {
                        "field": "QUOTE_EVENT.STATUS",
                        "reason": "Physical name suggests state but comment suggests a participant label.",
                    }
                ],
            }
        elif isolation and role == "SEMANTIC_CONFIG":
            payload = {
                "schema_name": "NOVA_RATES",
                "token_order": "suffix_first",
                "attribute_patterns": [
                    {"pattern": "* Name", "attribute_kind": "NAME"}
                ],
                "unknown_policy": "PRESERVE",
            }
        elif role.endswith("_MANIFEST"):
            marker = role.removesuffix("_MANIFEST").lower()
            output_path = path.parent / f"{marker}.jsonl"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("{}\n", encoding="utf-8")
            payload = {
                "schema_version": f"synthetic-{marker}-projection-v1",
                "run_id": f"{marker}-fixture-v1",
                "outputs": [
                    {
                        "logical_name": f"{marker}_rows",
                        "relative_path": f"{marker}.jsonl",
                        "content_sha256": sha256_file(output_path),
                    }
                ],
            }
        else:
            payload = {"role": role, "fixture": True}
        _write_yaml(path, payload)
        artifacts.append(
            {"role": role, "path": path.relative_to(tmp_path).as_posix(), "sha256": sha256_file(path)}
        )
    case = {
        "schema_version": "cognition-schema-case-pack-v1",
        "case_id": "test-case-v1",
        "workflow_profile_id": profile["profile_id"],
        "schema_name": "NOVA_RATES",
        "artifacts": artifacts,
        "data_policy": {
            "allowed_classes": ["SYNTHETIC_METADATA"],
            "business_rows": False,
            "source_writes": False,
            "model_egress": False,
        },
        "authority_refs": [
            {
                "role": "SECURITY_POLICY",
                "path": authority.relative_to(tmp_path).as_posix(),
                "sha256": sha256_file(authority),
            }
        ],
        "model_budget": {
            "max_total_calls": calls,
            "max_total_tokens": tokens,
            "require_measured_usage": True,
        },
        "contract_isolation_check": isolation,
    }
    case_path = tmp_path / "case.yaml"
    _write_yaml(case_path, case)
    return profile_path.name, case_path.name


def _keys(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            found.add(str(key).lower().replace("-", "_"))
            found.update(_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_keys(child))
    return found


def _rehash_report(report: dict[str, object]) -> None:
    payload = dict(report)
    payload.pop("report_id", None)
    from titans_cognition.cognition_harness import canonical_json, sha256_bytes

    report["report_id"] = sha256_bytes(canonical_json(payload).encode("utf-8"))[:24]


def test_synthetic_case_is_deterministic_and_only_claims_contract_isolation() -> None:
    first = run_harness(ROOT, PROFILE, SYNTHETIC_CASE)
    second = run_harness(ROOT, PROFILE, SYNTHETIC_CASE)

    assert first == second
    assert first["contract_isolation_check"] == "PASS"
    assert "CROSS_SCHEMA_VALIDATED" not in json.dumps(first)
    assert [item["operation_id"] for item in first["operations"]] == list(OPERATION_ORDER)


def test_tradeflow_run_is_a_projection_and_does_not_promote_current_status() -> None:
    report = run_harness(ROOT, PROFILE, TRADEFLOW_CASE)

    assert report["report_kind"] == "DERIVED_AUDIT_PROJECTION"
    assert report["contract_isolation_check"] == "NOT_APPLICABLE"
    assert {item["role"] for item in report["derived_from"]} >= {
        "STATUS_BASELINE",
        "SURROGATE_REVIEW",
        "FIELD_MANIFEST",
    }
    forbidden = {
        "candidate",
        "candidates",
        "evidence",
        "review_decision",
        "reader_delivery",
        "business_acceptance",
        "scale_authorization",
        "domain_disposition",
    }
    assert not (_keys(report) & forbidden)
    assert "INDEPENDENT_REVIEW_NOT_ATTACHED" in {
        gap["code"] for gap in report["gaps"]
    }


def test_profile_is_generic_and_has_no_case_path_or_vocabulary() -> None:
    text = (ROOT / PROFILE).read_text(encoding="utf-8").lower()
    assert "tradeflow" not in text
    assert "titans_" not in text
    assert "output/" not in text


def test_synthetic_fixture_contains_required_counterexamples() -> None:
    fixture = yaml.safe_load(
        (ROOT / "tests/fixtures/cognition_harness/nova_rates/frozen-inputs.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert fixture["missing_metadata"]
    assert fixture["ambiguous_relations"]
    assert fixture["misleading_names"]
    assert fixture["schema_name"] != "TITANS_TRADEFLOW"


def test_hash_drift_is_localized_to_the_reference(tmp_path: Path) -> None:
    profile, case = _workspace(tmp_path)
    payload = yaml.safe_load((tmp_path / case).read_text(encoding="utf-8"))
    payload["artifacts"][2]["sha256"] = "0" * 64
    _write_yaml(tmp_path / case, payload)

    with pytest.raises(HarnessError, match=r"HASH_DRIFT.*SEMANTIC_CONFIG"):
        run_harness(tmp_path, profile, case)


def test_unapproved_authority_reference_is_rejected(tmp_path: Path) -> None:
    profile, case = _workspace(tmp_path)
    payload = yaml.safe_load((tmp_path / case).read_text(encoding="utf-8"))
    rogue = tmp_path / "self-authorized.yaml"
    _write_yaml(rogue, {"allowed": True})
    payload["authority_refs"] = [
        {"role": "SELF_ASSERTED", "path": rogue.name, "sha256": sha256_file(rogue)}
    ]
    _write_yaml(tmp_path / case, payload)

    with pytest.raises(HarnessError, match="UNAUTHORIZED_REFERENCE"):
        run_harness(tmp_path, profile, case)


def test_open_decision_register_cannot_grant_authority(tmp_path: Path) -> None:
    profile, case = _workspace(tmp_path)
    open_decisions = tmp_path / "docs/spec/12-open-decisions.md"
    open_decisions.write_text("unresolved decisions\n", encoding="utf-8")
    payload = yaml.safe_load((tmp_path / case).read_text(encoding="utf-8"))
    payload["authority_refs"] = [
        {
            "role": "OPEN_DECISIONS",
            "path": open_decisions.relative_to(tmp_path).as_posix(),
            "sha256": sha256_file(open_decisions),
        }
    ]
    _write_yaml(tmp_path / case, payload)
    with pytest.raises(HarnessError, match="UNAUTHORIZED_REFERENCE"):
        run_harness(tmp_path, profile, case)


def test_business_rows_and_arbitrary_commands_are_rejected(tmp_path: Path) -> None:
    profile, case = _workspace(tmp_path)
    payload = yaml.safe_load((tmp_path / case).read_text(encoding="utf-8"))
    payload["data_policy"]["business_rows"] = True
    _write_yaml(tmp_path / case, payload)
    with pytest.raises(HarnessError, match="DATA_POLICY"):
        run_harness(tmp_path, profile, case)

    profile_payload = yaml.safe_load((tmp_path / profile).read_text(encoding="utf-8"))
    profile_payload["shell"] = "echo bypass"
    _write_yaml(tmp_path / profile, profile_payload)
    with pytest.raises(HarnessError, match="ARBITRARY_COMMAND"):
        run_harness(tmp_path, profile, case)


def test_path_escape_and_reparse_point_are_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    outside = tmp_path.parent / "outside.yaml"
    outside.write_text("outside: true\n", encoding="utf-8")
    with pytest.raises(HarnessError, match="PATH_ESCAPE"):
        resolve_workspace_path(tmp_path, str(outside))

    inside = tmp_path / "inside.yaml"
    inside.write_text("inside: true\n", encoding="utf-8")
    monkeypatch.setattr(
        "titans_cognition.cognition_harness._has_reparse_point",
        lambda path: path == inside,
    )
    with pytest.raises(HarnessError, match="REPARSE_POINT"):
        resolve_workspace_path(tmp_path, "inside.yaml")


def test_checkpoint_and_operation_bypass_are_rejected() -> None:
    report = run_harness(ROOT, PROFILE, SYNTHETIC_CASE)
    missing_checkpoint = copy.deepcopy(report)
    missing_checkpoint["checkpoints"].pop(2)
    _rehash_report(missing_checkpoint)
    with pytest.raises(HarnessError, match="CHECKPOINT_BYPASS"):
        validate_report(missing_checkpoint)

    reordered = copy.deepcopy(report)
    reordered["operations"].reverse()
    _rehash_report(reordered)
    with pytest.raises(HarnessError, match="OPERATION_BYPASS"):
        validate_report(reordered)


def test_model_budget_and_unmeasured_usage_are_rejected(tmp_path: Path) -> None:
    profile, case = _workspace(tmp_path)
    with pytest.raises(HarnessError, match="MODEL_DISABLED"):
        run_harness(
            tmp_path,
            profile,
            case,
            model_usage={"calls": 1, "tokens": 10, "measurement_status": "MEASURED"},
        )
    with pytest.raises(HarnessError, match="UNMEASURED_USAGE"):
        run_harness(
            tmp_path,
            profile,
            case,
            model_usage={"calls": 0, "tokens": 0, "measurement_status": "UNMEASURED"},
        )
    with pytest.raises(HarnessError, match="MODEL_USAGE"):
        run_harness(
            tmp_path,
            profile,
            case,
            model_usage={"calls": -1, "tokens": -1, "measurement_status": "UNMEASURED"},
        )


def test_nonzero_model_budget_is_out_of_scope_for_this_slice(tmp_path: Path) -> None:
    profile, case = _workspace(tmp_path, calls=1, tokens=100)
    with pytest.raises(HarnessError, match="MODEL_SCOPE"):
        run_harness(tmp_path, profile, case)


@pytest.mark.parametrize(
    "payload",
    [
        {"expected_disposition": "ACCEPT"},
        {"notes": "The implementer says this should pass."},
        {"notes": "实现者自评：应该通过"},
    ],
)
def test_reviewer_input_cannot_leak_expected_answer(payload: dict[str, str]) -> None:
    with pytest.raises(HarnessError, match="REVIEW_LEAKAGE"):
        validate_review_input(payload)


def test_uncontaminated_forward_review_inputs_cover_three_case_types() -> None:
    paths = sorted(
        (ROOT / "tests/fixtures/cognition_harness").glob("review-input-*.json")
    )
    assert {path.stem for path in paths} == {
        "review-input-positive",
        "review-input-ambiguous",
        "review-input-misleading-name",
    }
    for path in paths:
        validate_review_input(json.loads(path.read_text(encoding="utf-8")))
        report = run_harness(
            ROOT,
            PROFILE,
            SYNTHETIC_CASE,
            review_input_path=path.relative_to(ROOT).as_posix(),
        )
        assert "INDEPENDENT_REVIEW_NOT_ATTACHED" in {
            gap["code"] for gap in report["gaps"]
        }


def test_project_reviewer_agent_is_read_only_and_uses_valid_contract() -> None:
    config = tomllib.loads(
        (ROOT / ".codex/agents/counterexample-reviewer.toml").read_text(encoding="utf-8")
    )
    assert config["sandbox_mode"] == "read-only"
    instructions = config["developer_instructions"]
    assert "cognition-surrogate-review-v1" in instructions
    assert "not a domain Review Decision" in instructions
    assert "implementer's self-evaluation" in instructions


def test_valid_reviewer_response_is_only_referenced(tmp_path: Path) -> None:
    profile, case = _workspace(tmp_path)
    source = tmp_path / "artifacts/0-change_scope.yaml"
    # Use the exact fixture path created by _workspace.
    source = next((tmp_path / "artifacts").glob("0-*.yaml"))
    source_ref = {
        "role": "CHANGE_SCOPE",
        "path": source.relative_to(tmp_path).as_posix(),
        "sha256": sha256_file(source),
    }
    projection = next((tmp_path / "artifacts").glob("4-*.yaml"))
    projection_ref = {
        "role": "CONTEXT_MANIFEST",
        "path": projection.relative_to(tmp_path).as_posix(),
        "sha256": sha256_file(projection),
    }
    review_input = {
        "schema_version": "cognition-review-input-v1",
        "objective": "Challenge the frozen projection.",
        "acceptance_criteria": ["Counterexamples remain visible."],
        "trigger_codes": ["MISLEADING_NAME"],
        "source_refs": [source_ref],
        "projection_ref": projection_ref,
        "counterexamples": ["A physical name can mislead."],
        "known_gaps": [],
    }
    review_input_path = tmp_path / "review-input.json"
    review_input_path.write_text(json.dumps(review_input), encoding="utf-8")
    review = {
        "schema_version": "cognition-surrogate-review-v1",
        "review_id": "review-1",
        "objective_ref": review_input_path.relative_to(tmp_path).as_posix(),
        "source_refs": [source_ref, projection_ref],
        "disposition": "REWORK",
        "decisive_reasons": ["Misleading names are not challenged."],
        "smallest_next_action": "Add one counterexample assertion.",
        "reviewed_output_hash": projection_ref["sha256"],
    }
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")

    report = run_harness(
        tmp_path,
        profile,
        case,
        review_input_path=review_input_path.name,
        review_response_path=review_path.name,
    )

    assert "disposition" not in _keys(report)
    assert any(
        item["role"] == "ENGINEERING_REVIEW_RESPONSE"
        for item in report["operations"][2]["derived_from"]
    )
    assert report["gaps"] == [
        {
            "code": "ENGINEERING_REVIEW_FOLLOW_UP_REQUIRED",
            "source_ref": review_path.relative_to(tmp_path).as_posix(),
        }
    ]

    for disposition in ("STOP", "DEFER"):
        review["disposition"] = disposition
        review_path.write_text(json.dumps(review), encoding="utf-8")
        report = run_harness(
            tmp_path,
            profile,
            case,
            review_input_path=review_input_path.name,
            review_response_path=review_path.name,
        )
        assert report["gaps"][0]["code"] == "ENGINEERING_REVIEW_FOLLOW_UP_REQUIRED"

    review["disposition"] = "ACCEPT"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    report = run_harness(
        tmp_path,
        profile,
        case,
        review_input_path=review_input_path.name,
        review_response_path=review_path.name,
    )
    assert report["gaps"] == []


def test_review_response_without_validated_input_is_rejected(tmp_path: Path) -> None:
    profile, case = _workspace(tmp_path)
    response = tmp_path / "review.json"
    response.write_text("{}", encoding="utf-8")
    with pytest.raises(HarnessError, match="REVIEW_INPUT_REQUIRED"):
        run_harness(tmp_path, profile, case, review_response_path=response.name)


def test_review_package_sources_must_be_frozen(tmp_path: Path) -> None:
    profile, case = _workspace(tmp_path)
    rogue = tmp_path / "rogue.yaml"
    rogue.write_text("rogue: true\n", encoding="utf-8")
    rogue_ref = {"role": "ROGUE", "path": rogue.name, "sha256": sha256_file(rogue)}
    payload = {
        "schema_version": "cognition-review-input-v1",
        "objective": "Try an unfrozen source.",
        "acceptance_criteria": ["Reject it."],
        "trigger_codes": ["MISLEADING_NAME"],
        "source_refs": [rogue_ref],
        "projection_ref": rogue_ref,
        "counterexamples": [],
        "known_gaps": [],
    }
    path = tmp_path / "review-input.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    document = load_document(tmp_path, path.name)
    with pytest.raises(HarnessError, match="REVIEW_SOURCE_NOT_FROZEN"):
        validate_review_package(
            tmp_path,
            document,
            allowed_refs=[],
            ambiguity_triggers=["MISLEADING_NAME"],
        )


def test_review_projection_must_be_a_generated_manifest(tmp_path: Path) -> None:
    rogue = tmp_path / "not-a-manifest.yaml"
    _write_yaml(rogue, {"schema_version": "context-ish"})
    ref = {
        "role": "CONTEXT_MANIFEST",
        "path": rogue.name,
        "sha256": sha256_file(rogue),
    }
    payload = {
        "schema_version": "cognition-review-input-v1",
        "objective": "Reject a relabeled ordinary file.",
        "acceptance_criteria": ["Projection identity is verified."],
        "trigger_codes": ["MISLEADING_NAME"],
        "source_refs": [ref],
        "projection_ref": ref,
        "counterexamples": ["A role label alone does not create a Manifest."],
        "known_gaps": [],
    }
    path = tmp_path / "review-input.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(HarnessError, match="REVIEW_PROJECTION_INVALID"):
        validate_review_package(
            tmp_path,
            load_document(tmp_path, path.name),
            allowed_refs=[ref],
            ambiguity_triggers=["MISLEADING_NAME"],
        )


def test_review_package_requires_a_counterexample(tmp_path: Path) -> None:
    profile, case = _workspace(tmp_path)
    case_payload = yaml.safe_load((tmp_path / case).read_text(encoding="utf-8"))
    projection_ref = next(
        ref for ref in case_payload["artifacts"] if ref["role"] == "CONTEXT_MANIFEST"
    )
    payload = {
        "schema_version": "cognition-review-input-v1",
        "objective": "Reject a vacuous review package.",
        "acceptance_criteria": ["A counterexample is present."],
        "trigger_codes": ["MISLEADING_NAME"],
        "source_refs": [projection_ref],
        "projection_ref": projection_ref,
        "counterexamples": [],
        "known_gaps": [],
    }
    path = tmp_path / "review-input.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    profile_payload = yaml.safe_load((tmp_path / profile).read_text(encoding="utf-8"))
    with pytest.raises(HarnessError, match="REVIEW_COUNTEREXAMPLE_REQUIRED"):
        validate_review_package(
            tmp_path,
            load_document(tmp_path, path.name),
            allowed_refs=case_payload["artifacts"],
            ambiguity_triggers=profile_payload["ambiguity_triggers"],
        )


def test_isolation_pass_is_derived_not_case_self_asserted(tmp_path: Path) -> None:
    profile, case = _workspace(tmp_path, isolation=True)
    assert run_harness(tmp_path, profile, case)["contract_isolation_check"] == "PASS"
    payload = yaml.safe_load((tmp_path / case).read_text(encoding="utf-8"))
    frozen_ref = next(ref for ref in payload["artifacts"] if ref["role"] == "FROZEN_INPUTS")
    frozen_path = tmp_path / frozen_ref["path"]
    fixture = yaml.safe_load(frozen_path.read_text(encoding="utf-8"))
    fixture["misleading_names"] = []
    _write_yaml(frozen_path, fixture)
    frozen_ref["sha256"] = sha256_file(frozen_path)
    _write_yaml(tmp_path / case, payload)
    with pytest.raises(HarnessError, match="INVALID_ISOLATION_CASE"):
        run_harness(tmp_path, profile, case)


@pytest.mark.parametrize(
    "mutation",
    [
        "object_comment",
        "column_comment",
        "ambiguous_reason",
        "misleading_reason",
        "semantic_policy",
    ],
)
def test_isolation_rejects_count_preserving_semantic_swaps(
    tmp_path: Path, mutation: str
) -> None:
    profile, case = _workspace(tmp_path, isolation=True)
    payload = yaml.safe_load((tmp_path / case).read_text(encoding="utf-8"))
    role = "SEMANTIC_CONFIG" if mutation == "semantic_policy" else "FROZEN_INPUTS"
    artifact_ref = next(ref for ref in payload["artifacts"] if ref["role"] == role)
    artifact_path = tmp_path / artifact_ref["path"]
    fixture = yaml.safe_load(artifact_path.read_text(encoding="utf-8"))

    if mutation == "object_comment":
        fixture["objects"][1]["comment"] = "Amount-bearing rate object."
    elif mutation == "column_comment":
        fixture["objects"][0]["columns"][0]["comment"] = "Lifecycle status."
    elif mutation == "ambiguous_reason":
        fixture["ambiguous_relations"][0]["reason"] = "Relation is confirmed."
    elif mutation == "misleading_reason":
        fixture["misleading_names"][0]["reason"] = "The physical name is reliable."
    else:
        fixture["unknown_policy"] = "DROP"

    _write_yaml(artifact_path, fixture)
    artifact_ref["sha256"] = sha256_file(artifact_path)
    _write_yaml(tmp_path / case, payload)

    with pytest.raises(HarnessError, match="INVALID_ISOLATION_CASE"):
        run_harness(tmp_path, profile, case)


def test_tradeflow_shaped_content_cannot_pass_synthetic_isolation(tmp_path: Path) -> None:
    profile, case = _workspace(tmp_path, isolation=True)
    payload = yaml.safe_load((tmp_path / case).read_text(encoding="utf-8"))
    frozen_ref = next(ref for ref in payload["artifacts"] if ref["role"] == "FROZEN_INPUTS")
    frozen_path = tmp_path / frozen_ref["path"]
    fixture = {
        "schema_name": "NOVA_RATES",
        "objects": [
            {
                "object_name": "TITANS_TRADEFLOW_TRADE_EVENT",
                "columns": [{"name": "TRADE_ID"}],
            }
        ],
        "missing_metadata": ["x"],
        "ambiguous_relations": [{"left": "x", "right": "y"}],
        "misleading_names": [{"field": "STATUS"}],
    }
    _write_yaml(frozen_path, fixture)
    frozen_ref["sha256"] = sha256_file(frozen_path)
    _write_yaml(tmp_path / case, payload)
    with pytest.raises(HarnessError, match="INVALID_ISOLATION_CASE"):
        run_harness(tmp_path, profile, case)


def test_tradeflow_case_identifier_cannot_request_isolation(tmp_path: Path) -> None:
    profile, case = _workspace(tmp_path, isolation=True)
    payload = yaml.safe_load((tmp_path / case).read_text(encoding="utf-8"))
    payload["case_id"] = "tradeflow-contract-isolation-v1"
    _write_yaml(tmp_path / case, payload)
    with pytest.raises(HarnessError, match="INVALID_ISOLATION_CASE"):
        run_harness(tmp_path, profile, case)

    payload = yaml.safe_load((tmp_path / case).read_text(encoding="utf-8"))
    payload["schema_name"] = "TITANS_TRADEFLOW"
    _write_yaml(tmp_path / case, payload)
    with pytest.raises(HarnessError, match="INVALID_ISOLATION_CASE"):
        run_harness(tmp_path, profile, case)


def test_forged_report_cannot_add_domain_state_or_change_results() -> None:
    report = run_harness(ROOT, PROFILE, SYNTHETIC_CASE)
    forged = copy.deepcopy(report)
    forged["business_status"] = "ACCEPTED"
    _rehash_report(forged)
    with pytest.raises(HarnessError, match="UNKNOWN_KEY|REPORT_OWNS_DOMAIN_STATE"):
        validate_report(forged)

    forged = copy.deepcopy(report)
    forged["checkpoints"][0]["result"] = "FAIL"
    _rehash_report(forged)
    with pytest.raises(HarnessError, match="CHECKPOINT_FAILURE"):
        validate_report(forged)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("model_usage", "REPORT_DERIVATION"),
        ("isolation", "REPORT_DERIVATION"),
        ("gaps", "REPORT_DERIVATION"),
    ],
)
def test_verified_report_rederives_claims_from_sources(mutation: str, message: str) -> None:
    forged = copy.deepcopy(run_harness(ROOT, PROFILE, SYNTHETIC_CASE))
    if mutation == "model_usage":
        forged["model_usage"].update(
            {
                "calls": 1,
                "tokens": 1,
                "measurement_status": "UNMEASURED",
                "max_total_calls": 1,
                "max_total_tokens": 1,
            }
        )
    elif mutation == "isolation":
        forged["contract_isolation_check"] = "NOT_APPLICABLE"
    else:
        forged["gaps"] = []
    _rehash_report(forged)
    with pytest.raises(HarnessError, match=message):
        validate_report(forged, root=ROOT)


def test_report_is_immutable(tmp_path: Path) -> None:
    profile, case = _workspace(tmp_path)
    report = run_harness(tmp_path, profile, case)
    write_immutable_report(tmp_path, "output/report.json", report)
    write_immutable_report(tmp_path, "output/report.json", report)
    changed = copy.deepcopy(report)
    changed["case_id"] = "changed"
    with pytest.raises(HarnessError, match="IMMUTABLE_REPORT"):
        write_immutable_report(tmp_path, "output/report.json", changed)


def test_focused_cli_runs_without_touching_general_cli(tmp_path: Path) -> None:
    output_path = (
        f"output/pytest-cognition-harness/{os.getpid()}-{tmp_path.name}/report.json"
    )
    command = [
        sys.executable,
        "-m",
        "titans_cognition.cognition_harness",
        "--root",
        str(ROOT),
        "run",
        "--profile",
        PROFILE,
        "--case-pack",
        SYNTHETIC_CASE,
        "--output",
        output_path,
    ]
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    assert result.returncode == 0, result.stderr
    generated = ROOT / output_path
    assert generated.exists()
    verify = subprocess.run(
        [
            sys.executable,
            "-m",
            "titans_cognition.cognition_harness",
            "--root",
            str(ROOT),
            "verify-report",
            "--report",
            output_path,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    assert verify.returncode == 0, verify.stderr


def test_review_input_cli_rejects_contaminated_fixture() -> None:
    contaminated = ROOT / "output/pytest-cognition-harness/contaminated-review-input.json"
    contaminated.parent.mkdir(parents=True, exist_ok=True)
    contaminated.write_text(
        json.dumps({"expected_disposition": "ACCEPT"}), encoding="utf-8"
    )
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "titans_cognition.cognition_harness",
            "--root",
            str(ROOT),
            "validate-review-input",
            "--profile",
            PROFILE,
            "--case-pack",
            SYNTHETIC_CASE,
            "--input",
            contaminated.relative_to(ROOT).as_posix(),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    assert result.returncode == 2
    assert "REVIEW_LEAKAGE" in result.stderr


def test_model_usage_cli_path_cannot_escape_workspace(tmp_path: Path) -> None:
    outside = tmp_path / "model-usage.json"
    outside.write_text(
        json.dumps({"calls": 0, "tokens": 0, "measurement_status": "MEASURED"}),
        encoding="utf-8",
    )
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "titans_cognition.cognition_harness",
            "--root",
            str(ROOT),
            "run",
            "--profile",
            PROFILE,
            "--case-pack",
            SYNTHETIC_CASE,
            "--output",
            "output/pytest-cognition-harness/escaped-usage/report.json",
            "--model-usage",
            str(outside),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    assert result.returncode == 2
    assert "PATH_ESCAPE" in result.stderr
