"""Bounded P0/P1 reconciliation for the frozen TRADEFLOW Evidence Pack."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml


JsonObject = dict[str, object]
PathResolver = Callable[[Path], Path]


class PathBoundaryError(ValueError):
    """Raised when a configured artifact resolves outside its allowed root."""


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_mapping(
    loader: _UniqueKeyLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[object, object]:
    result: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"duplicate YAML key: {key!r}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


def _load_yaml(path: Path) -> JsonObject:
    loaded = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    if not isinstance(loaded, dict):
        raise ValueError(f"expected YAML mapping: {path}")
    return cast(JsonObject, loaded)


def _mapping(value: object, label: str) -> JsonObject:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    return cast(JsonObject, value)


def _sequence(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a sequence")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    return value


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    return value


def _strings(value: object, label: str) -> tuple[str, ...]:
    return tuple(_string(item, label) for item in _sequence(value, label))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_bytes(record: Mapping[str, object]) -> bytes:
    return json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _with_content_sha256(record: JsonObject) -> JsonObject:
    payload = dict(record)
    payload.pop("content_sha256", None)
    payload["content_sha256"] = hashlib.sha256(_canonical_bytes(payload)).hexdigest()
    return payload


def validate_content_sha256(record: Mapping[str, object]) -> bool:
    expected = record.get("content_sha256")
    if not isinstance(expected, str):
        return False
    payload = dict(record)
    payload.pop("content_sha256", None)
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest() == expected


def _windows_key(path: Path) -> str:
    return os.path.normcase(str(path)).casefold().rstrip("\\/")


def _is_within(path: Path, root: Path) -> bool:
    path_key = _windows_key(path)
    root_key = _windows_key(root)
    return path_key == root_key or path_key.startswith(root_key + os.sep.casefold())


def assert_path_within(
    path: Path,
    allowed_root: Path,
    *,
    resolver: PathResolver | None = None,
) -> Path:
    """Apply lexical then resolved-target root checks, including junctions."""
    lexical = path.absolute()
    root = allowed_root.resolve(strict=True)
    if not _is_within(lexical, root):
        raise PathBoundaryError(f"path is outside allowed root: {lexical}")
    resolved = resolver(lexical) if resolver else lexical.resolve(strict=False)
    if not _is_within(resolved, root):
        raise PathBoundaryError(
            f"symlink or junction escape detected: {lexical} -> {resolved}"
        )
    return resolved


@dataclass(frozen=True)
class ReconciliationConfig:
    profile_path: Path
    profile_id: str
    run_id: str
    schema_name: str
    gate_version: str
    workspace_root: Path
    output_root: Path
    stage1_directory: Path
    stage1_manifest_path: Path
    stage1_manifest_sha256: str
    stage1_pack_path: Path
    stage1_pack_sha256: str
    expected_objects: int
    expected_columns: int
    expected_dispositions: Mapping[str, int]
    columns_path: Path
    columns_sha256: str
    objects_path: Path
    objects_sha256: str
    gold_path: Path
    gold_sha256: str
    validation_path: Path
    contract_path: Path
    design_path: Path
    bundle_sha256: str
    review_path: Path
    review_sha256: str
    authorization_status: str
    allowed_steps: tuple[str, ...]
    prohibited_steps: tuple[str, ...]
    result_schema_path: Path
    result_schema_id: str
    controls: Mapping[str, object]
    expected_case_refs: Mapping[str, tuple[str, ...]]


def _rooted(root: Path, value: object, label: str) -> Path:
    relative = Path(_string(value, label))
    return relative if relative.is_absolute() else root / relative


def load_reconciliation_config(profile_path: Path) -> ReconciliationConfig:
    profile_path = profile_path.resolve()
    raw = _load_yaml(profile_path)
    workspace_root = Path(_string(raw["canonical_workspace_root"], "workspace root"))
    output_root = Path(_string(raw["canonical_output_root"], "output root"))
    stage1 = _mapping(raw["stage1"], "stage1")
    sources = _mapping(raw["source_artifacts"], "source_artifacts")
    columns = _mapping(sources["columns"], "columns source")
    objects = _mapping(sources["objects"], "objects source")
    gold = _mapping(raw["gold_set"], "gold_set")
    contract = _mapping(raw["integration_contract"], "integration_contract")
    authorization = _mapping(raw["authorization"], "authorization")
    result_schema = _mapping(raw["result_schema"], "result_schema")
    controls = _mapping(raw["controls"], "controls")

    validation_path = _rooted(
        workspace_root,
        contract["validation_plan_path"],
        "validation plan path",
    )
    validation = _load_yaml(validation_path)
    gate_sets = _mapping(validation["gate_expected_case_sets"], "gate sets")
    expected: dict[str, tuple[str, ...]] = {}
    for item in _sequence(gate_sets["sets"], "gate sets.sets"):
        row = _mapping(item, "gate set")
        step_ref = _string(row["step_ref"], "step_ref")
        expected[step_ref] = _strings(
            row["expected_case_refs_exact"],
            "expected_case_refs_exact",
        )

    dispositions = _mapping(stage1["expected_dispositions"], "dispositions")
    return ReconciliationConfig(
        profile_path=profile_path,
        profile_id=_string(raw["profile_id"], "profile_id"),
        run_id=_string(raw["run_id"], "run_id"),
        schema_name=_string(raw["schema_name"], "schema_name"),
        gate_version=_string(raw["gate_version"], "gate_version"),
        workspace_root=workspace_root,
        output_root=output_root,
        stage1_directory=_rooted(workspace_root, stage1["directory"], "stage1 dir"),
        stage1_manifest_path=_rooted(
            workspace_root, stage1["manifest_path"], "stage1 manifest"
        ),
        stage1_manifest_sha256=_string(
            stage1["manifest_sha256"], "stage1 manifest hash"
        ),
        stage1_pack_path=_rooted(workspace_root, stage1["pack_path"], "pack path"),
        stage1_pack_sha256=_string(stage1["pack_sha256"], "pack hash"),
        expected_objects=_integer(
            stage1["expected_physical_objects"], "expected objects"
        ),
        expected_columns=_integer(
            stage1["expected_physical_columns"], "expected columns"
        ),
        expected_dispositions={
            name: _integer(dispositions[name], f"disposition {name}")
            for name in ("PREPARED", "EXCLUDED", "DEFERRED")
        },
        columns_path=_rooted(workspace_root, columns["path"], "columns path"),
        columns_sha256=_string(columns["sha256"], "columns hash"),
        objects_path=_rooted(workspace_root, objects["path"], "objects path"),
        objects_sha256=_string(objects["sha256"], "objects hash"),
        gold_path=_rooted(workspace_root, gold["path"], "gold path"),
        gold_sha256=_string(gold["sha256"], "gold hash"),
        validation_path=validation_path,
        contract_path=_rooted(
            workspace_root, contract["contract_path"], "contract path"
        ),
        design_path=_rooted(workspace_root, contract["design_path"], "design path"),
        bundle_sha256=_string(contract["candidate_bundle_sha256"], "bundle hash"),
        review_path=_rooted(
            workspace_root, authorization["review_path"], "review path"
        ),
        review_sha256=_string(authorization["review_sha256"], "review hash"),
        authorization_status=_string(
            authorization["predecessor_status"], "authorization status"
        ),
        allowed_steps=_strings(authorization["allowed_steps"], "allowed steps"),
        prohibited_steps=_strings(
            authorization["prohibited_steps"], "prohibited steps"
        ),
        result_schema_path=_rooted(
            workspace_root, result_schema["path"], "result schema path"
        ),
        result_schema_id=_string(result_schema["schema_id"], "schema id"),
        controls=controls,
        expected_case_refs=expected,
    )


def _verify_hash(path: Path, expected: str, label: str) -> None:
    observed = _sha256_file(path)
    if observed != expected.lower():
        raise ValueError(f"{label} hash mismatch: expected {expected}, got {observed}")


def _bundle_hash(config: ReconciliationConfig) -> str:
    payload = bytearray()
    for path in (config.design_path, config.contract_path, config.validation_path):
        raw = path.read_bytes()
        if path == config.contract_path:
            text_value, count = re.subn(
                rb"(?m)^(\s*candidate_bundle_sha256:\s*)[0-9a-f]{64}(\s*)$",
                rb"\1SELF_EXCLUDED\2",
                raw,
            )
            if count != 1:
                raise ValueError(
                    "contract candidate bundle self-exclusion is not unique"
                )
            raw = text_value
        relative = path.relative_to(config.workspace_root).as_posix().encode("utf-8")
        payload.extend(relative)
        payload.extend(b"\0")
        payload.extend(str(len(raw)).encode("ascii"))
        payload.extend(b"\0")
        payload.extend(raw)
        payload.extend(b"\0")
    return hashlib.sha256(payload).hexdigest()


def load_bound_evidence_packs(
    config: ReconciliationConfig,
) -> dict[str, JsonObject]:
    _verify_hash(
        config.stage1_manifest_path,
        config.stage1_manifest_sha256,
        "stage1 manifest",
    )
    _verify_hash(config.stage1_pack_path, config.stage1_pack_sha256, "stage1 pack")
    packs: dict[str, JsonObject] = {}
    with config.stage1_pack_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            pack = json.loads(line)
            if not isinstance(pack, dict):
                raise ValueError(f"pack line {line_number} is not an object")
            identity = _mapping(pack.get("physical_identity"), "physical_identity")
            physical_id = _string(
                identity.get("physical_column_id"), "physical_column_id"
            )
            if physical_id in packs:
                raise ValueError(f"duplicate physical_column_id: {physical_id}")
            packs[physical_id] = cast(JsonObject, pack)
    return packs


def _load_json_rows(path: Path) -> list[JsonObject]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, list) or not all(isinstance(row, dict) for row in loaded):
        raise ValueError(f"expected JSON row list: {path}")
    return cast(list[JsonObject], loaded)


def _source_maps(
    config: ReconciliationConfig,
) -> tuple[dict[str, JsonObject], dict[str, JsonObject]]:
    columns = {
        _string(row["column_id"], "column_id"): row
        for row in _load_json_rows(config.columns_path)
    }
    objects = {
        _string(row["asset_id"], "asset_id"): row
        for row in _load_json_rows(config.objects_path)
    }
    return columns, objects


def _case_record(case_ref: str, passed: bool, checks: Sequence[str]) -> JsonObject:
    return {
        "case_ref": case_ref,
        "status": "PASS" if passed else "FAIL",
        "checks": list(checks),
    }


def _result_record(
    record_type: str,
    config: ReconciliationConfig,
    case_results: Sequence[JsonObject],
) -> JsonObject:
    distribution = Counter(
        _string(row["status"], "case status") for row in case_results
    )
    status = "PASS" if distribution == {"PASS": len(case_results)} else "FAIL"
    return _with_content_sha256(
        {
            "record_type": record_type,
            "run_id": config.run_id,
            "profile_ref": config.profile_id,
            "schema_name": config.schema_name,
            "case_results": list(case_results),
            "expected_case_refs_exact": list(
                config.expected_case_refs["07c:step:03-suite-a"]
            ),
            "observed_case_refs_exact": [row["case_ref"] for row in case_results],
            "status": status,
            "status_distribution": dict(sorted(distribution.items())),
            "model_calls": 0,
            "external_egress": False,
            "business_rows_read": False,
            "database_writes": 0,
        }
    )


def _physical_id(physical_field: str) -> str:
    schema, object_name, column_name = physical_field.split(".")
    return f"testdb:{schema}:TABLE:{object_name}:COLUMN:{column_name}"


def _observed_strings(rows: object, key: str) -> list[str]:
    return [_string(_mapping(row, key)[key], key) for row in _sequence(rows, key)]


def evaluate_suite_a(
    config: ReconciliationConfig,
    packs: Mapping[str, JsonObject],
) -> tuple[JsonObject, JsonObject]:
    """Execute the 23 P0->P1 cases with source and rule records separated."""
    _verify_hash(config.gold_path, config.gold_sha256, "gold set")
    gold = _load_yaml(config.gold_path)
    cases = _sequence(gold["cases"], "gold cases")
    expected_refs = config.expected_case_refs["07c:step:03-suite-a"]
    observed_refs = tuple(
        _string(_mapping(case, "gold case")["case_id"], "case_id") for case in cases
    )
    if observed_refs != expected_refs:
        raise ValueError("Suite A case set does not exactly match validation plan")

    source_columns, source_objects = _source_maps(config)
    source_results: list[JsonObject] = []
    rule_results: list[JsonObject] = []
    identity_by_case: dict[str, str] = {}

    for case_object in cases:
        case = _mapping(case_object, "gold case")
        case_ref = _string(case["case_id"], "case_id")
        physical_field = _string(case["physical_field"], "physical_field")
        physical_id = _physical_id(physical_field)
        identity_by_case[case_ref] = physical_id
        pack = packs.get(physical_id)
        if pack is None:
            source_results.append(_case_record(case_ref, False, ["pack_missing"]))
            rule_results.append(_case_record(case_ref, False, ["pack_missing"]))
            continue

        identity = _mapping(pack["physical_identity"], "physical_identity")
        raw = _mapping(pack["raw_physical_fact"], "raw_physical_fact")
        object_id = physical_id.rsplit(":COLUMN:", 1)[0]
        column_source = source_columns.get(physical_id)
        object_source = source_objects.get(object_id)
        artifacts = _sequence(
            _mapping(pack["provenance"], "provenance")["source_artifacts"],
            "source_artifacts",
        )
        artifact_by_role = {
            _string(
                _mapping(item, "source artifact")["evidence_role"], "role"
            ): _mapping(item, "source artifact")
            for item in artifacts
        }
        expected_column_raw = case.get("column_comment_raw")
        expected_object_raw = case.get("object_comment_raw")
        source_checks = {
            "physical_identity": identity.get("physical_column_id") == physical_id,
            "gold_column_raw": raw.get("column_comment_raw") == expected_column_raw,
            "gold_object_raw": raw.get("object_comment_raw") == expected_object_raw,
            "stage0_column_raw": column_source is not None
            and column_source.get("column_comment") == expected_column_raw,
            "stage0_object_raw": object_source is not None
            and object_source.get("object_comment") == expected_object_raw,
            "column_provenance": artifact_by_role.get("COLUMN_PHYSICAL_FACT", {}).get(
                "sha256"
            )
            == config.columns_sha256
            and artifact_by_role.get("COLUMN_PHYSICAL_FACT", {}).get("locator")
            == f"physical_column_id={physical_id}",
            "object_provenance": artifact_by_role.get("OBJECT_PHYSICAL_FACT", {}).get(
                "sha256"
            )
            == config.objects_sha256
            and artifact_by_role.get("OBJECT_PHYSICAL_FACT", {}).get("locator")
            == f"asset_id={object_id}",
        }
        source_results.append(
            _case_record(
                case_ref,
                all(source_checks.values()),
                [name for name, passed in source_checks.items() if not passed]
                or ["all_source_bindings_exact"],
            )
        )

        tokens = _observed_strings(pack["tokens"], "normalized_text")
        phrases = _observed_strings(pack["protected_phrases"], "phrase")
        generic = _observed_strings(pack["generic_attribute_observations"], "attribute")
        technical_rows = [
            _mapping(row, "technical observation")
            for row in _sequence(
                pack["technical_observations"], "technical observations"
            )
        ]
        conflicts = _observed_strings(pack["conflicts"], "conflict_type")
        unresolved = _observed_strings(pack["unresolved_items"], "code")
        qualifiers = {
            f"{_string(row['dimension'], 'dimension')}={_string(row['value'], 'value')}"
            for row in (
                _mapping(item, "qualifier")
                for item in _sequence(
                    pack["candidate_qualifier_observations"], "qualifiers"
                )
            )
        }
        expected_technical = _string(
            case["expected_technical_class"], "expected technical class"
        )
        if expected_technical == "NOT_APPLICABLE":
            technical_pass = technical_rows == []
        else:
            technical_pass = any(
                row.get("technical_class") == expected_technical
                and row.get("status") == case.get("expected_technical_status")
                for row in technical_rows
            )
        expected_conflicts = set(
            _strings(case["expected_conflicts"], "expected conflicts")
        )
        semantic_conflicts = {
            value for value in conflicts if value != "UNRECOGNIZED_ABBREVIATION"
        }
        expected_qualifiers = set(
            _strings(
                case.get("allowed_candidate_qualifier_observations", []),
                "allowed qualifiers",
            )
        )
        unknown_abbreviations = unresolved.count("UNRECOGNIZED_ABBREVIATION")
        unknown_conflicts = conflicts.count("UNRECOGNIZED_ABBREVIATION")
        handoff_status = _string(
            case["expected_handoff_status"], "expected handoff status"
        )
        if handoff_status == "TECHNICAL_ISOLATED":
            handoff_pass = bool(technical_rows)
        else:
            handoff_pass = handoff_status in unresolved
        rule_checks = {
            "tokens_exact": tokens == list(_strings(case["expected_tokens"], "tokens")),
            "protected_phrases_exact": phrases
            == list(_strings(case["expected_protected_phrases"], "phrases")),
            "generic_attributes_exact": generic
            == list(_strings(case["expected_generic_attributes"], "attributes")),
            "technical_expectation": technical_pass,
            "conflicts_exact": semantic_conflicts == expected_conflicts,
            "unknown_abbreviation_conflict_parity": unknown_abbreviations
            == unknown_conflicts,
            "allowed_qualifiers_exact": not expected_qualifiers
            or qualifiers == expected_qualifiers,
            "handoff_route_observed_without_handoff": handoff_pass,
        }
        rule_results.append(
            _case_record(
                case_ref,
                all(rule_checks.values()),
                [name for name, passed in rule_checks.items() if not passed]
                or ["all_rule_expectations_exact"],
            )
        )

    if identity_by_case.get("FEP-001") == identity_by_case.get("FEP-023"):
        raise ValueError("FEP-001 and FEP-023 physical identities are not distinct")
    return (
        _result_record("SUITE_A_SOURCE_VERIFICATION", config, source_results),
        _result_record("SUITE_A_RULE_EXECUTION", config, rule_results),
    )


def _controls(config: ReconciliationConfig) -> JsonObject:
    return {
        "model_calls": config.controls["model_calls"],
        "model_token_budget": config.controls["model_token_budget"],
        "model_token_usage": config.controls["model_token_usage"],
        "external_egress": config.controls["external_egress"],
        "business_rows_read": config.controls["business_rows_read"],
        "database_writes": config.controls["database_writes"],
    }


def _gate_result(
    config: ReconciliationConfig,
    *,
    step_ref: str,
    gate_ref: str,
    predecessor_gate_ref: str,
    predecessor_status: str,
    predecessor_sha256: str,
    input_manifest_ref: str,
    input_manifest_sha256: str,
    case_results: Sequence[JsonObject],
) -> JsonObject:
    expected = config.expected_case_refs[step_ref]
    observed = tuple(_string(row["case_ref"], "case_ref") for row in case_results)
    distribution = Counter(_string(row["status"], "status") for row in case_results)
    exact = observed == expected
    status = "PASS" if exact and distribution == {"PASS": len(expected)} else "FAIL"
    controls = _controls(config)
    return _with_content_sha256(
        {
            "run_id": config.run_id,
            "profile_ref": config.profile_id,
            "schema_name": config.schema_name,
            "gate_ref": gate_ref,
            "gate_version": config.gate_version,
            "step_ref": step_ref,
            "predecessor_gate_ref": predecessor_gate_ref,
            "predecessor_status": predecessor_status,
            "predecessor_content_sha256": predecessor_sha256,
            "input_manifest_ref": input_manifest_ref,
            "input_manifest_content_sha256": input_manifest_sha256,
            "expected_case_refs_exact": list(expected),
            "observed_case_refs_exact": list(observed),
            "expected_direct_positive_case_types_exact": [],
            "observed_direct_positive_case_types_exact": [],
            "expected_direct_positive_case_refs_exact": [],
            "observed_direct_positive_case_refs_exact": [],
            "direct_positive_evidence_bindings": [],
            "case_results": list(case_results),
            "status": status,
            "status_distribution": dict(sorted(distribution.items())),
            "not_evaluable_case_refs": [],
            "zero_omission_assertion": exact,
            "nonempty_execution_assertion": bool(case_results),
            "active": True,
            **controls,
            "canonical_workspace_root": config.workspace_root.as_posix(),
            "canonical_output_root": config.output_root.as_posix(),
            "path_allowlist_passed": True,
            "symlink_escape_detected": False,
        }
    )


def _validate_gate_schema(config: ReconciliationConfig, record: JsonObject) -> None:
    schema = json.loads(config.result_schema_path.read_text(encoding="utf-8"))
    if schema.get("$id") != config.result_schema_id:
        raise ValueError("GateResult schema id mismatch")
    required = schema.get("required")
    if not isinstance(required, list):
        raise ValueError("GateResult schema required list missing")
    missing = [key for key in required if key not in record]
    if missing:
        raise ValueError(f"GateResult missing required fields: {missing}")
    if not validate_content_sha256(record):
        raise ValueError("GateResult content hash invalid")


def _write_json(path: Path, record: Mapping[str, object]) -> None:
    path.write_text(
        json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _verify_all_inputs(config: ReconciliationConfig, output_path: Path) -> None:
    assert_path_within(config.stage1_directory, config.output_root)
    assert_path_within(config.stage1_manifest_path, config.output_root)
    assert_path_within(config.stage1_pack_path, config.output_root)
    for path in (
        config.columns_path,
        config.objects_path,
        config.gold_path,
        config.validation_path,
        config.contract_path,
        config.design_path,
        config.review_path,
        config.result_schema_path,
    ):
        assert_path_within(path, config.workspace_root)
    assert_path_within(output_path, config.output_root)
    _verify_hash(config.review_path, config.review_sha256, "round-2 review")
    _verify_hash(config.gold_path, config.gold_sha256, "gold set")
    _verify_hash(config.columns_path, config.columns_sha256, "columns source")
    _verify_hash(config.objects_path, config.objects_sha256, "objects source")
    observed_bundle = _bundle_hash(config)
    if observed_bundle != config.bundle_sha256:
        raise ValueError(
            f"07 bundle hash mismatch: expected {config.bundle_sha256}, "
            f"got {observed_bundle}"
        )


def _full_scope_checks(
    config: ReconciliationConfig,
    packs: Mapping[str, JsonObject],
) -> tuple[JsonObject, dict[str, JsonObject], dict[str, JsonObject]]:
    manifest = json.loads(config.stage1_manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("stage1 manifest is not an object")
    manifest = cast(JsonObject, manifest)
    columns, objects = _source_maps(config)
    scoped_objects = {
        asset_id: row
        for asset_id, row in objects.items()
        if row.get("schema_name") == config.schema_name
        and row.get("object_type") == "TABLE"
        and row.get("in_panorama_scope") is True
        and row.get("is_boundary") is False
    }
    scoped_columns = {
        column_id: row
        for column_id, row in columns.items()
        if row.get("asset_id") in scoped_objects
    }
    if len(scoped_objects) != config.expected_objects:
        raise ValueError("scoped object cardinality mismatch")
    if len(scoped_columns) != config.expected_columns:
        raise ValueError("scoped column cardinality mismatch")
    if set(packs) != set(scoped_columns):
        raise ValueError("13,611 physical_column_id exact case set mismatch")
    counts = _mapping(manifest["counts"], "stage1 counts")
    for key, expected in (
        ("physical_objects", config.expected_objects),
        ("physical_columns", config.expected_columns),
        ("evidence_packs", config.expected_columns),
        ("unique_physical_column_ids", config.expected_columns),
        ("missing_physical_column_ids", 0),
        ("duplicate_physical_column_ids", 0),
    ):
        if counts.get(key) != expected:
            raise ValueError(f"stage1 manifest count mismatch: {key}")
    for disposition, expected in config.expected_dispositions.items():
        if counts.get(disposition) != expected:
            raise ValueError(f"stage1 disposition mismatch: {disposition}")
    controls = _mapping(manifest["controls"], "stage1 controls")
    if controls != {
        "model_calls": 0,
        "external_egress": False,
        "business_rows_read": False,
        "database_writes": 0,
        "suite_a_formal_status": "NOT_CLAIMED",
    }:
        raise ValueError("stage1 safety envelope mismatch")
    for physical_id, pack in packs.items():
        column = scoped_columns[physical_id]
        object_row = scoped_objects[_string(column["asset_id"], "asset_id")]
        raw = _mapping(pack["raw_physical_fact"], "raw fact")
        identity = _mapping(pack["physical_identity"], "physical identity")
        expected_raw = {
            "column_name_raw": column.get("column_name"),
            "column_comment_raw": column.get("column_comment"),
            "data_type_raw": column.get("data_type"),
            "nullable": column.get("nullable_declared"),
            "ordinal_position": column.get("ordinal_position"),
            "object_comment_raw": object_row.get("object_comment"),
        }
        if raw != expected_raw:
            raise ValueError(f"raw physical fact mismatch: {physical_id}")
        if identity != {
            "schema_name": config.schema_name,
            "object_name": object_row.get("object_name"),
            "object_type": "TABLE",
            "physical_column_id": physical_id,
        }:
            raise ValueError(f"physical identity mismatch: {physical_id}")
    return manifest, scoped_columns, scoped_objects


def run_p0_p1_reconciliation(
    profile_path: Path,
    output_path: Path,
) -> JsonObject:
    """Verify, execute Suite A, and atomically publish the bounded result."""
    config = load_reconciliation_config(profile_path)
    output_path = output_path.absolute()
    _verify_all_inputs(config, output_path)
    if output_path.exists():
        raise FileExistsError(f"output already exists: {output_path}")
    if tuple(config.allowed_steps) != (
        "07c:step:01-provider",
        "07c:step:02-full-evidence-pack",
        "07c:step:03-suite-a",
    ):
        raise ValueError("bounded authorization does not exactly allow steps 01-03")
    if "07c:step:04-handoff" not in config.prohibited_steps:
        raise ValueError("step04 handoff is not explicitly prohibited")

    packs = load_bound_evidence_packs(config)
    manifest, _, _ = _full_scope_checks(config, packs)
    schema_ids: list[str] = []
    for schema_path in (config.workspace_root / "schemas").glob("*.json"):
        schema_value = json.loads(schema_path.read_text(encoding="utf-8"))
        if isinstance(schema_value, dict) and isinstance(schema_value.get("$id"), str):
            schema_ids.append(schema_value["$id"])
    schema_unique = schema_ids.count(config.result_schema_id) == 1
    provider = _mapping(manifest["provider"], "provider")
    provider_path = _rooted(config.workspace_root, provider["path"], "provider path")
    stage1_schema = _mapping(manifest["schema"], "stage1 schema")
    stage1_schema_path = _rooted(
        config.workspace_root, stage1_schema["path"], "stage1 schema path"
    )
    provider_schema_pass = (
        _sha256_file(provider_path) == provider.get("sha256")
        and _sha256_file(stage1_schema_path) == stage1_schema.get("sha256")
        and schema_unique
    )
    block_registry = _mapping(manifest["block_registry"], "block registry")
    first_pack = next(iter(packs.values()))
    blocks_pass = (
        block_registry.get("count") == 16
        and len(first_pack) == 16
        and set(first_pack)
        == set(_strings(block_registry.get("names"), "block registry names"))
    )
    step01_cases = [
        _case_record(
            "STEP01-PROVIDER-SCHEMA",
            provider_schema_pass,
            ["bound_provider_and_unique_schema"],
        ),
        _case_record("STEP01-OUTPUT-BLOCKS", blocks_pass, ["sixteen_blocks_exact"]),
        _case_record(
            "STEP01-ZERO-MODEL-EGRESS-ROWS-WRITES", True, ["zero_safety_envelope"]
        ),
        _case_record(
            "STEP01-PATH-ALLOWLIST", True, ["all_paths_canonical_and_within_roots"]
        ),
    ]
    step01 = _gate_result(
        config,
        step_ref="07c:step:01-provider",
        gate_ref="07g:gate:step01-provider",
        predecessor_gate_ref="review:10-round2-bounded-authorization",
        predecessor_status=config.authorization_status,
        predecessor_sha256=config.review_sha256,
        input_manifest_ref=config.profile_path.relative_to(
            config.workspace_root
        ).as_posix(),
        input_manifest_sha256=_sha256_file(config.profile_path),
        case_results=step01_cases,
    )
    _validate_gate_schema(config, step01)
    if step01["status"] != "PASS":
        raise ValueError("step01 GateResult failed")

    step02_cases = [
        _case_record(
            "STEP02-FULL-13611-CARDINALITY", len(packs) == 13611, ["13611_exact"]
        ),
        _case_record(
            "STEP02-DUAL-SOURCE-HASH", True, ["columns_and_objects_hash_exact"]
        ),
        _case_record(
            "STEP02-SCOPED-PHYSICAL-IDENTITY", True, ["physical_id_set_and_raw_exact"]
        ),
        _case_record(
            "STEP02-ZERO-MODEL-EGRESS-ROWS-WRITES", True, ["zero_safety_envelope"]
        ),
        _case_record(
            "STEP02-PATH-ALLOWLIST", True, ["all_paths_canonical_and_within_roots"]
        ),
    ]
    step02 = _gate_result(
        config,
        step_ref="07c:step:02-full-evidence-pack",
        gate_ref="07g:gate:step02-full-evidence-pack",
        predecessor_gate_ref=_string(step01["gate_ref"], "gate_ref"),
        predecessor_status=_string(step01["status"], "status"),
        predecessor_sha256=_string(step01["content_sha256"], "content hash"),
        input_manifest_ref=config.stage1_manifest_path.relative_to(
            config.workspace_root
        ).as_posix(),
        input_manifest_sha256=config.stage1_manifest_sha256,
        case_results=step02_cases,
    )
    _validate_gate_schema(config, step02)

    step03_input = _with_content_sha256(
        {
            "manifest_type": "FROZEN_STEP03_SUITE_A_INPUT_V1",
            "run_id": config.run_id,
            "profile_ref": config.profile_id,
            "schema_name": config.schema_name,
            "predecessor_gate_ref": step02["gate_ref"],
            "predecessor_status": step02["status"],
            "predecessor_content_sha256": step02["content_sha256"],
            "stage1_manifest_ref": config.stage1_manifest_path.relative_to(
                config.workspace_root
            ).as_posix(),
            "stage1_manifest_sha256": config.stage1_manifest_sha256,
            "stage1_pack_ref": config.stage1_pack_path.relative_to(
                config.workspace_root
            ).as_posix(),
            "stage1_pack_sha256": config.stage1_pack_sha256,
            "gold_set_ref": config.gold_path.relative_to(
                config.workspace_root
            ).as_posix(),
            "gold_set_sha256": config.gold_sha256,
            "expected_case_refs_exact": list(
                config.expected_case_refs["07c:step:03-suite-a"]
            ),
            "controls": {**_controls(config), "handoff_executed": False},
            "authorization_ref": config.review_path.relative_to(
                config.workspace_root
            ).as_posix(),
            "authorization_sha256": config.review_sha256,
            "allowed_step": "07c:step:03-suite-a",
            "next_step": "07c:step:04-handoff",
            "next_step_status": "PROHIBITED_NOT_EXECUTED",
        }
    )
    source_result, rule_result = evaluate_suite_a(config, packs)
    combined_cases = []
    for source_case, rule_case in zip(
        cast(list[JsonObject], source_result["case_results"]),
        cast(list[JsonObject], rule_result["case_results"]),
        strict=True,
    ):
        passed = source_case["status"] == rule_case["status"] == "PASS"
        combined_cases.append(
            _case_record(
                _string(source_case["case_ref"], "case_ref"),
                passed,
                ["source_verification", "rule_execution"],
            )
        )
    step03 = _gate_result(
        config,
        step_ref="07c:step:03-suite-a",
        gate_ref="07g:gate:step03-suite-a",
        predecessor_gate_ref=_string(step02["gate_ref"], "gate_ref"),
        predecessor_status=_string(step02["status"], "status"),
        predecessor_sha256=_string(step02["content_sha256"], "content hash"),
        input_manifest_ref="step03-suite-a-input-manifest.json",
        input_manifest_sha256=_string(step03_input["content_sha256"], "content hash"),
        case_results=combined_cases,
    )
    step03["controls"] = {**_controls(config), "handoff_executed": False}
    step03 = _with_content_sha256(step03)
    _validate_gate_schema(config, step03)

    run_manifest = _with_content_sha256(
        {
            "manifest_type": "P0_P1_RECONCILIATION_RUN_V1",
            "run_id": config.run_id,
            "profile_ref": config.profile_id,
            "schema_name": config.schema_name,
            "status": step03["status"],
            "stage1_manifest_sha256": config.stage1_manifest_sha256,
            "stage1_pack_sha256": config.stage1_pack_sha256,
            "counts": {
                "physical_objects": config.expected_objects,
                "physical_columns": config.expected_columns,
                "suite_a_cases": len(combined_cases),
                **config.expected_dispositions,
            },
            "gate_results": {
                "step01": step01["content_sha256"],
                "step02": step02["content_sha256"],
                "step03": step03["content_sha256"],
            },
            "controls": {**_controls(config), "handoff_executed": False},
            "business_acceptance": "NOT_CLAIMED",
            "reader_delivery": "NOT_DELIVERED",
        }
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output_path.name}.staging-", dir=output_path.parent)
    )
    try:
        for name, record in (
            ("step01-provider-gate-result.json", step01),
            ("step02-full-evidence-pack-gate-result.json", step02),
            ("step03-suite-a-input-manifest.json", step03_input),
            ("suite-a-source-verification.json", source_result),
            ("suite-a-rule-execution.json", rule_result),
            ("step03-suite-a-gate-result.json", step03),
            ("manifest.json", run_manifest),
        ):
            _write_json(staging / name, record)
        staging.replace(output_path)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return run_manifest
