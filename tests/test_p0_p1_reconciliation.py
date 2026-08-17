import json
import shutil
import tempfile
from pathlib import Path

import pytest
import yaml

from titans_cognition.p0_p1_reconciliation import (
    PathBoundaryError,
    assert_path_within,
    evaluate_suite_a,
    load_bound_evidence_packs,
    load_reconciliation_config,
    run_p0_p1_reconciliation,
    validate_content_sha256,
)


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "cases" / "tradeflow" / "p0-p1-reconciliation.yaml"


@pytest.fixture
def workspace_output_tmp():
    base = Path(
        tempfile.mkdtemp(prefix=".test-p0-p1-reconciliation-", dir=ROOT / "output")
    )
    try:
        yield base
    finally:
        shutil.rmtree(base)


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_profile_binds_final_stage1_and_exact_gate_case_sets():
    config = load_reconciliation_config(PROFILE)

    assert config.stage1_manifest_sha256 == (
        "4991cdb185b22ffb776b8d3418031cd89ec09756c60c46b0925d1db72ac0a5ce"
    )
    assert config.stage1_pack_sha256 == (
        "0fa37a92d0c2250c78f0589fc625e4404c1316f9703186f9354356b80887c43e"
    )
    assert config.expected_case_refs["07c:step:01-provider"] == (
        "STEP01-PROVIDER-SCHEMA",
        "STEP01-OUTPUT-BLOCKS",
        "STEP01-ZERO-MODEL-EGRESS-ROWS-WRITES",
        "STEP01-PATH-ALLOWLIST",
    )
    assert len(config.expected_case_refs["07c:step:02-full-evidence-pack"]) == 5
    assert config.expected_case_refs["07c:step:03-suite-a"] == tuple(
        f"FEP-{number:03d}" for number in range(1, 24)
    )


def test_reconciliation_emits_pass_gates_and_separate_suite_a_records(
    workspace_output_tmp,
):
    output = workspace_output_tmp / "p0-p1-reconciliation"

    manifest = run_p0_p1_reconciliation(PROFILE, output)

    assert manifest["status"] == "PASS"
    step01 = _read(output / "step01-provider-gate-result.json")
    step02 = _read(output / "step02-full-evidence-pack-gate-result.json")
    step03_input = _read(output / "step03-suite-a-input-manifest.json")
    source_result = _read(output / "suite-a-source-verification.json")
    rule_result = _read(output / "suite-a-rule-execution.json")
    step03 = _read(output / "step03-suite-a-gate-result.json")

    assert all(
        validate_content_sha256(record)
        for record in (step01, step02, step03_input, source_result, rule_result, step03)
    )
    assert step01["status_distribution"] == {"PASS": 4}
    assert step02["predecessor_content_sha256"] == step01["content_sha256"]
    assert step02["status_distribution"] == {"PASS": 5}
    assert step03_input["stage1_manifest_sha256"] == (
        "4991cdb185b22ffb776b8d3418031cd89ec09756c60c46b0925d1db72ac0a5ce"
    )
    assert step03_input["stage1_pack_sha256"] == (
        "0fa37a92d0c2250c78f0589fc625e4404c1316f9703186f9354356b80887c43e"
    )
    assert source_result["status_distribution"] == {"PASS": 23}
    assert rule_result["status_distribution"] == {"PASS": 23}
    assert step03["expected_case_refs_exact"] == [
        f"FEP-{number:03d}" for number in range(1, 24)
    ]
    assert step03["observed_case_refs_exact"] == step03["expected_case_refs_exact"]
    assert step03["status"] == "PASS"
    assert step03["input_manifest_content_sha256"] == step03_input["content_sha256"]
    assert step03["controls"]["handoff_executed"] is False
    assert not list(output.glob("*handoff*"))


def test_suite_a_records_raw_tamper_as_fail():
    config = load_reconciliation_config(PROFILE)
    packs = load_bound_evidence_packs(config)
    physical_column_id = (
        "testdb:TITANS_TRADEFLOW:TABLE:TRD_CLN_TRADE_DEAL:COLUMN:CTPTY_SHORT_NAME"
    )
    packs[physical_column_id]["raw_physical_fact"]["column_comment_raw"] = "篡改"

    source_result, rule_result = evaluate_suite_a(config, packs)

    assert source_result["status"] == "FAIL"
    failed = {
        row["case_ref"]
        for row in source_result["case_results"]
        if row["status"] == "FAIL"
    }
    assert failed == {"FEP-001"}
    assert rule_result["status"] == "PASS"


def test_path_boundary_rejects_resolved_symlink_escape(tmp_path):
    allowed_root = tmp_path / "workspace"
    allowed_root.mkdir()
    lexical_path = allowed_root / "linked" / "artifact.json"
    outside = tmp_path / "outside" / "artifact.json"

    with pytest.raises(PathBoundaryError, match="symlink or junction escape"):
        assert_path_within(
            lexical_path,
            allowed_root,
            resolver=lambda _path: outside.resolve(),
        )


def test_hash_failure_does_not_publish_partial_output(tmp_path, workspace_output_tmp):
    payload = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    payload["stage1"]["manifest_sha256"] = "0" * 64
    profile = tmp_path / "tampered-profile.yaml"
    profile.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    output = workspace_output_tmp / "failed-output"

    with pytest.raises(ValueError, match="stage1 manifest hash mismatch"):
        run_p0_p1_reconciliation(profile, output)

    assert not output.exists()
