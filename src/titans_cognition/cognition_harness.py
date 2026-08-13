"""Deterministic governance harness for semantic-navigation work.

The harness is deliberately narrow: it validates references and execution
boundaries, then emits a rebuildable audit projection. It never owns domain
candidates, evidence, review decisions, or reader/business delivery status.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import yaml


PROFILE_VERSION = "cognition-workflow-profile-v1"
CASE_VERSION = "cognition-schema-case-pack-v1"
REPORT_VERSION = "cognition-governance-run-report-v1"
REVIEW_VERSION = "cognition-surrogate-review-v1"
REVIEW_INPUT_VERSION = "cognition-review-input-v1"

MANDATORY_CHECKPOINTS = (
    "PREFLIGHT",
    "POST_STAGE",
    "PRE_REVIEW",
    "POST_REVIEW",
    "PRE_FINALIZE",
)
OPERATION_ORDER = (
    "authority-snapshot",
    "artifact-integrity",
    "review-readiness",
    "final-audit",
)
REVIEW_PROJECTION_ROLES = frozenset(
    {"FIELD_MANIFEST", "CONTEXT_MANIFEST", "TABLE_MANIFEST"}
)
ISOLATION_PROHIBITED_TOKENS = ("TRADEFLOW", "TITANS_")
# Pinned from the repository's intentionally non-TRADEFLOW fixture and semantic
# config. The complete canonical content rejects count-preserving semantic swaps.
ISOLATION_STRUCTURE_FINGERPRINT = (
    "02634a3f3a3a1ce4fe55408195619679aa315a19862ce1f0fcdaf1abb36b463b"
)

AUTHORITY_POLICY: Mapping[str, frozenset[str]] = {
    "docs/spec/11-security-and-operations.md": frozenset(
        {"METADATA", "WIKI_CONTEXT", "SYNTHETIC_METADATA"}
    ),
}

FORBIDDEN_COMMAND_KEYS = frozenset(
    {"command", "commands", "shell", "script", "powershell", "executable"}
)
FORBIDDEN_REPORT_KEYS = frozenset(
    {
        "candidate",
        "candidates",
        "evidence",
        "review_decision",
        "review_decisions",
        "business_acceptance",
        "reader_delivery",
        "scale_authorization",
        "domain_disposition",
        "disposition",
        "business_status",
        "reader_status",
        "review_status",
        "delivery_status",
        "acceptance",
        "validated",
    }
)
REVIEW_LEAK_KEYS = frozenset(
    {
        "expected_disposition",
        "recommended_disposition",
        "implementer_self_evaluation",
        "should_pass",
    }
)
REVIEW_LEAK_PHRASES = (
    "should pass",
    "expected disposition",
    "应当通过",
    "应该通过",
    "预期结论",
    "实现者自评",
)


class HarnessError(ValueError):
    """A bounded validation failure with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class LoadedDocument:
    path: Path
    relative_path: str
    sha256: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class RunContext:
    root: Path
    profile: LoadedDocument
    case_pack: LoadedDocument
    artifacts: tuple[dict[str, str], ...]
    authority_refs: tuple[dict[str, str], ...]
    model_usage: dict[str, Any]
    review_input: LoadedDocument | None
    review_response: LoadedDocument | None


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_path(path: Path) -> str:
    if path.is_file():
        return sha256_file(path)
    files = sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
    digest = hashlib.sha256()
    for candidate in files:
        digest.update(candidate.relative_to(path).as_posix().encode("utf-8"))
        digest.update(bytes.fromhex(sha256_file(candidate)))
    return digest.hexdigest()


def _has_reparse_point(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    attributes = getattr(metadata, "st_file_attributes", 0)
    return path.is_symlink() or bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def resolve_workspace_path(
    root: Path,
    raw_path: str,
    *,
    must_exist: bool = True,
) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise HarnessError("INVALID_PATH", "path must be a non-empty string")
    root = root.resolve(strict=True)
    requested = Path(raw_path)
    candidate = requested if requested.is_absolute() else root / requested

    # Reject links/reparse points before resolve() follows them.
    probe = root
    try:
        relative_parts = candidate.absolute().relative_to(root).parts
    except ValueError:
        relative_parts = ()
    for part in relative_parts:
        probe = probe / part
        if probe.exists() and _has_reparse_point(probe):
            raise HarnessError("REPARSE_POINT", f"path uses a link/reparse point: {probe}")

    try:
        resolved = candidate.resolve(strict=must_exist)
    except FileNotFoundError as exc:
        raise HarnessError("MISSING_PATH", str(candidate)) from exc
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise HarnessError(
            "PATH_ESCAPE",
            f"resolved target is outside workspace: {resolved}",
        ) from exc
    return resolved


def relative_posix(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _load_mapping(path: Path) -> dict[str, Any]:
    try:
        if path.suffix.lower() == ".json":
            value = json.loads(path.read_text(encoding="utf-8"))
        else:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise HarnessError("INVALID_DOCUMENT", f"cannot parse {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise HarnessError("INVALID_DOCUMENT", f"root must be a mapping: {path}")
    return value


def load_document(root: Path, raw_path: str) -> LoadedDocument:
    path = resolve_workspace_path(root, raw_path)
    return LoadedDocument(
        path=path,
        relative_path=relative_posix(root, path),
        sha256=sha256_file(path),
        payload=_load_mapping(path),
    )


def _walk(value: Any, path: str = "$") -> Sequence[tuple[str, str, Any]]:
    found: list[tuple[str, str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            found.append((path, str(key), child))
            found.extend(_walk(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_walk(child, f"{path}[{index}]"))
    return found


def _reject_keys(payload: Any, forbidden: frozenset[str], code: str) -> None:
    normalized = {item.lower().replace("-", "_") for item in forbidden}
    for location, key, _ in _walk(payload):
        if key.lower().replace("-", "_") in normalized:
            raise HarnessError(code, f"forbidden key {key!r} at {location}")


def _require_exact_keys(
    payload: Mapping[str, Any],
    allowed: frozenset[str],
    required: frozenset[str],
    label: str,
) -> None:
    unknown = set(payload) - allowed
    missing = required - set(payload)
    if unknown:
        raise HarnessError("UNKNOWN_KEY", f"{label} has unknown keys: {sorted(unknown)}")
    if missing:
        raise HarnessError("MISSING_KEY", f"{label} misses keys: {sorted(missing)}")


def validate_profile(profile: Mapping[str, Any]) -> None:
    _reject_keys(profile, FORBIDDEN_COMMAND_KEYS, "ARBITRARY_COMMAND")
    _require_exact_keys(
        profile,
        frozenset(
            {
                "schema_version",
                "profile_id",
                "capability",
                "operations",
                "required_artifact_roles",
                "mandatory_checkpoints",
                "ambiguity_triggers",
                "model_policy",
            }
        ),
        frozenset(
            {
                "schema_version",
                "profile_id",
                "capability",
                "operations",
                "required_artifact_roles",
                "mandatory_checkpoints",
                "ambiguity_triggers",
                "model_policy",
            }
        ),
        "profile",
    )
    if profile["schema_version"] != PROFILE_VERSION:
        raise HarnessError("PROFILE_VERSION", str(profile["schema_version"]))
    if profile["capability"] != "semantic-navigation":
        raise HarnessError("CAPABILITY", "only semantic-navigation is registered")
    if tuple(profile["operations"]) != OPERATION_ORDER:
        raise HarnessError("OPERATION_ORDER", "operation list must match code-owned order")
    if tuple(profile["mandatory_checkpoints"]) != MANDATORY_CHECKPOINTS:
        raise HarnessError("CHECKPOINT_ORDER", "mandatory checkpoints cannot be changed")
    text = canonical_json(profile).lower()
    if "tradeflow" in text or "titans_tradeflow" in text:
        raise HarnessError("PROFILE_LEAKAGE", "generic profile contains case vocabulary")
    model_policy = profile["model_policy"]
    _require_exact_keys(
        model_policy,
        frozenset({"default_calls", "max_total_calls", "max_total_tokens", "require_measured_usage"}),
        frozenset({"default_calls", "max_total_calls", "max_total_tokens", "require_measured_usage"}),
        "profile.model_policy",
    )
    if model_policy["default_calls"] != 0:
        raise HarnessError("MODEL_DEFAULT", "model calls must default to zero")
    if model_policy["max_total_calls"] != 0 or model_policy["max_total_tokens"] != 0:
        raise HarnessError("MODEL_SCOPE", "this slice requires a zero model budget")
    if not isinstance(profile["ambiguity_triggers"], list):
        raise HarnessError("AMBIGUITY_TRIGGERS", "must be a list")


def _validate_ref(root: Path, ref: Mapping[str, Any], label: str) -> dict[str, str]:
    _require_exact_keys(
        ref,
        frozenset({"role", "path", "sha256"}),
        frozenset({"role", "path", "sha256"}),
        label,
    )
    path = resolve_workspace_path(root, str(ref["path"]))
    actual = sha256_file(path)
    expected = str(ref["sha256"]).lower()
    if actual != expected:
        raise HarnessError(
            "HASH_DRIFT",
            f"{label} role={ref['role']} {relative_posix(root, path)} "
            f"expected {expected} actual {actual}",
        )
    return {"role": str(ref["role"]), "path": relative_posix(root, path), "sha256": actual}


def validate_case_pack(
    root: Path,
    case_pack: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> tuple[tuple[dict[str, str], ...], tuple[dict[str, str], ...]]:
    _reject_keys(case_pack, FORBIDDEN_COMMAND_KEYS, "ARBITRARY_COMMAND")
    _require_exact_keys(
        case_pack,
        frozenset(
            {
                "schema_version",
                "case_id",
                "workflow_profile_id",
                "schema_name",
                "artifacts",
                "data_policy",
                "authority_refs",
                "model_budget",
                "contract_isolation_check",
            }
        ),
        frozenset(
            {
                "schema_version",
                "case_id",
                "workflow_profile_id",
                "schema_name",
                "artifacts",
                "data_policy",
                "authority_refs",
                "model_budget",
                "contract_isolation_check",
            }
        ),
        "case_pack",
    )
    if case_pack["schema_version"] != CASE_VERSION:
        raise HarnessError("CASE_VERSION", str(case_pack["schema_version"]))
    if case_pack["workflow_profile_id"] != profile["profile_id"]:
        raise HarnessError("PROFILE_MISMATCH", "case references a different profile")
    policy = case_pack["data_policy"]
    _require_exact_keys(
        policy,
        frozenset({"allowed_classes", "business_rows", "source_writes", "model_egress"}),
        frozenset({"allowed_classes", "business_rows", "source_writes", "model_egress"}),
        "case_pack.data_policy",
    )
    if policy["business_rows"] is not False or policy["source_writes"] is not False:
        raise HarnessError("DATA_POLICY", "business rows and source writes are forbidden")
    if policy["model_egress"] is not False:
        raise HarnessError("MODEL_EGRESS", "this slice does not authorize model egress")
    allowed_classes = set(policy["allowed_classes"])

    authority_refs: list[dict[str, str]] = []
    covered_classes: set[str] = set()
    for index, ref in enumerate(case_pack["authority_refs"]):
        normalized = _validate_ref(root, ref, f"authority_refs[{index}]")
        approved = AUTHORITY_POLICY.get(normalized["path"])
        if approved is None:
            raise HarnessError(
                "UNAUTHORIZED_REFERENCE",
                f"not a code-approved authority source: {normalized['path']}",
            )
        covered_classes.update(approved)
        authority_refs.append(normalized)
    if not allowed_classes or not allowed_classes.issubset(covered_classes):
        raise HarnessError(
            "UNAUTHORIZED_DATA_CLASS",
            f"requested {sorted(allowed_classes)} covered {sorted(covered_classes)}",
        )

    artifacts = tuple(
        _validate_ref(root, ref, f"artifacts[{index}]")
        for index, ref in enumerate(case_pack["artifacts"])
    )
    roles = {ref["role"] for ref in artifacts}
    required_roles = set(profile["required_artifact_roles"])
    missing_roles = required_roles - roles
    if missing_roles:
        raise HarnessError("MISSING_ARTIFACT_ROLE", str(sorted(missing_roles)))

    budget = case_pack["model_budget"]
    _require_exact_keys(
        budget,
        frozenset({"max_total_calls", "max_total_tokens", "require_measured_usage"}),
        frozenset({"max_total_calls", "max_total_tokens", "require_measured_usage"}),
        "case_pack.model_budget",
    )
    for key in ("max_total_calls", "max_total_tokens"):
        if not isinstance(budget[key], int) or budget[key] < 0:
            raise HarnessError("MODEL_BUDGET", f"{key} must be a non-negative integer")
    if budget["max_total_calls"] != 0 or budget["max_total_tokens"] != 0:
        raise HarnessError("MODEL_SCOPE", "this slice requires a zero model budget")
    return artifacts, tuple(authority_refs)


def validate_review_input(payload: Any) -> None:
    _reject_keys(payload, REVIEW_LEAK_KEYS, "REVIEW_LEAKAGE")
    lowered = canonical_json(payload).lower()
    for phrase in REVIEW_LEAK_PHRASES:
        if phrase.lower() in lowered:
            raise HarnessError("REVIEW_LEAKAGE", f"review input contains {phrase!r}")


def _reference_identity(ref: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(ref["role"]), str(ref["path"]), str(ref["sha256"]))


def _validate_projection_manifest(root: Path, ref: Mapping[str, Any]) -> None:
    role = str(ref["role"])
    if role not in REVIEW_PROJECTION_ROLES:
        raise HarnessError(
            "REVIEW_PROJECTION_REQUIRED",
            "projection_ref must identify a generated semantic projection Manifest",
        )
    payload = _load_mapping(resolve_workspace_path(root, str(ref["path"])))
    manifest_path = resolve_workspace_path(root, str(ref["path"]))
    manifest_root = manifest_path.parent.resolve()
    schema_version = payload.get("schema_version")
    run_id = payload.get("run_id")
    outputs = payload.get("outputs")
    if not isinstance(schema_version, str) or not schema_version:
        raise HarnessError("REVIEW_PROJECTION_INVALID", "projection schema_version is missing")
    if not isinstance(run_id, str) or not run_id:
        raise HarnessError("REVIEW_PROJECTION_INVALID", "projection run_id is missing")
    if not isinstance(outputs, list) or not outputs:
        raise HarnessError("REVIEW_PROJECTION_INVALID", "projection outputs are missing")
    expected_marker = role.removesuffix("_MANIFEST").lower()
    if expected_marker not in schema_version.lower():
        raise HarnessError(
            "REVIEW_PROJECTION_INVALID",
            f"projection schema {schema_version!r} does not match role {role}",
        )
    for index, output in enumerate(outputs):
        if not isinstance(output, dict):
            raise HarnessError(
                "REVIEW_PROJECTION_INVALID", f"projection outputs[{index}] is not an object"
            )
        for key in ("logical_name", "relative_path", "content_sha256"):
            if not isinstance(output.get(key), str) or not output[key]:
                raise HarnessError(
                    "REVIEW_PROJECTION_INVALID",
                    f"projection outputs[{index}].{key} is missing",
                )
        if re.fullmatch(r"[0-9a-f]{64}", output["content_sha256"]) is None:
            raise HarnessError(
                "REVIEW_PROJECTION_INVALID",
                f"projection outputs[{index}].content_sha256 is invalid",
            )
        output_path = resolve_workspace_path(
            root,
            str(manifest_root / output["relative_path"]),
        )
        try:
            output_path.relative_to(manifest_root)
        except ValueError as exc:
            raise HarnessError(
                "REVIEW_PROJECTION_INVALID",
                f"projection outputs[{index}] escapes its Manifest root",
            ) from exc
        actual_hash = sha256_path(output_path)
        if actual_hash != output["content_sha256"]:
            raise HarnessError(
                "REVIEW_PROJECTION_INVALID",
                f"projection outputs[{index}] hash drift: expected "
                f"{output['content_sha256']} actual {actual_hash}",
            )


def validate_review_package(
    root: Path,
    document: LoadedDocument,
    *,
    allowed_refs: Sequence[Mapping[str, Any]],
    ambiguity_triggers: Sequence[str],
) -> tuple[dict[str, str], ...]:
    payload = document.payload
    validate_review_input(payload)
    _require_exact_keys(
        payload,
        frozenset(
            {
                "schema_version",
                "objective",
                "acceptance_criteria",
                "trigger_codes",
                "source_refs",
                "projection_ref",
                "counterexamples",
                "known_gaps",
            }
        ),
        frozenset(
            {
                "schema_version",
                "objective",
                "acceptance_criteria",
                "trigger_codes",
                "source_refs",
                "projection_ref",
                "counterexamples",
                "known_gaps",
            }
        ),
        "review_input",
    )
    if payload["schema_version"] != REVIEW_INPUT_VERSION:
        raise HarnessError("REVIEW_INPUT_VERSION", str(payload["schema_version"]))
    for key in ("objective",):
        if not isinstance(payload[key], str) or not payload[key].strip():
            raise HarnessError("REVIEW_INPUT", f"{key} is required")
    for key in ("acceptance_criteria", "counterexamples", "known_gaps"):
        if not isinstance(payload[key], list) or not all(
            isinstance(item, str) and item.strip() for item in payload[key]
        ):
            raise HarnessError("REVIEW_INPUT", f"{key} must contain non-empty strings")
    triggers = payload["trigger_codes"]
    if not isinstance(triggers, list) or not triggers:
        raise HarnessError("REVIEW_TRIGGER", "at least one ambiguity trigger is required")
    unknown_triggers = set(triggers) - set(ambiguity_triggers)
    if unknown_triggers:
        raise HarnessError("REVIEW_TRIGGER", f"unregistered triggers: {sorted(unknown_triggers)}")

    allowed = {_reference_identity(ref) for ref in allowed_refs}
    validated: list[dict[str, str]] = []
    refs = [*payload["source_refs"], payload["projection_ref"]]
    if not payload["source_refs"]:
        raise HarnessError("REVIEW_SOURCES", "source_refs are required")
    for index, ref in enumerate(refs):
        normalized = _validate_ref(root, ref, f"review_input.refs[{index}]")
        if _reference_identity(normalized) not in allowed:
            raise HarnessError(
                "REVIEW_SOURCE_NOT_FROZEN",
                f"review source is outside the frozen allowlist: {normalized['path']}",
            )
        validated.append(normalized)
    if not payload["counterexamples"]:
        raise HarnessError("REVIEW_COUNTEREXAMPLE_REQUIRED", "at least one counterexample is required")
    _validate_projection_manifest(root, payload["projection_ref"])
    return tuple(validated)


def validate_review_response(
    root: Path,
    document: LoadedDocument,
    *,
    review_input: LoadedDocument | None = None,
) -> None:
    payload = document.payload
    _require_exact_keys(
        payload,
        frozenset(
            {
                "schema_version",
                "review_id",
                "objective_ref",
                "source_refs",
                "disposition",
                "decisive_reasons",
                "smallest_next_action",
                "reviewed_output_hash",
            }
        ),
        frozenset(
            {
                "schema_version",
                "review_id",
                "objective_ref",
                "source_refs",
                "disposition",
                "decisive_reasons",
                "smallest_next_action",
                "reviewed_output_hash",
            }
        ),
        "review_response",
    )
    if payload["schema_version"] != REVIEW_VERSION:
        raise HarnessError("REVIEW_VERSION", str(payload["schema_version"]))
    if payload["disposition"] not in {"ACCEPT", "REWORK", "STOP", "DEFER"}:
        raise HarnessError("REVIEW_DISPOSITION", str(payload["disposition"]))
    if not payload["decisive_reasons"] or not all(
        isinstance(item, str) and item.strip() for item in payload["decisive_reasons"]
    ):
        raise HarnessError("REVIEW_REASONS", "decisive reasons are required")
    if not isinstance(payload["smallest_next_action"], str) or not payload[
        "smallest_next_action"
    ].strip():
        raise HarnessError("REVIEW_NEXT_ACTION", "smallest next action is required")
    if not isinstance(payload["objective_ref"], str) or not payload["objective_ref"].strip():
        raise HarnessError("REVIEW_OBJECTIVE", "objective_ref is required")
    if not isinstance(payload["reviewed_output_hash"], str) or re.fullmatch(
        r"[0-9a-f]{64}", payload["reviewed_output_hash"]
    ) is None:
        raise HarnessError("REVIEW_OUTPUT_HASH", "reviewed_output_hash must be SHA-256")
    refs = payload["source_refs"]
    if not isinstance(refs, list) or not refs:
        raise HarnessError("REVIEW_SOURCES", "source_refs are required")
    validated_refs = tuple(
        _validate_ref(root, ref, f"review_response.source_refs[{index}]")
        for index, ref in enumerate(refs)
    )
    if review_input is not None:
        allowed = {
            _reference_identity(ref)
            for ref in [
                *review_input.payload["source_refs"],
                review_input.payload["projection_ref"],
            ]
        }
        if any(_reference_identity(ref) not in allowed for ref in validated_refs):
            raise HarnessError(
                "REVIEW_SOURCE_NOT_FROZEN",
                "review response cites a source outside the validated review input",
            )
        projection_identity = _reference_identity(review_input.payload["projection_ref"])
        if projection_identity not in {_reference_identity(ref) for ref in validated_refs}:
            raise HarnessError(
                "REVIEW_PROJECTION_REQUIRED",
                "review response must cite the frozen projection",
            )
        if payload["objective_ref"] != review_input.relative_path:
            raise HarnessError(
                "REVIEW_OBJECTIVE",
                "review response objective_ref must identify the frozen review input",
            )
        expected_hash = str(review_input.payload["projection_ref"]["sha256"])
        if payload["reviewed_output_hash"] != expected_hash:
            raise HarnessError(
                "REVIEW_OUTPUT_HASH",
                "review response does not match the frozen projection",
            )


def _normalize_model_usage(
    profile: Mapping[str, Any],
    case_pack: Mapping[str, Any],
    supplied: Mapping[str, Any] | None,
) -> dict[str, Any]:
    value = dict(supplied or {"calls": 0, "tokens": 0, "measurement_status": "MEASURED"})
    _require_exact_keys(
        value,
        frozenset({"calls", "tokens", "measurement_status"}),
        frozenset({"calls", "tokens", "measurement_status"}),
        "model_usage",
    )
    if value["measurement_status"] not in {"MEASURED", "UNMEASURED"}:
        raise HarnessError("MODEL_USAGE", "invalid measurement_status")
    if any(
        not isinstance(value[key], int) or isinstance(value[key], bool) or value[key] < 0
        for key in ("calls", "tokens")
    ):
        raise HarnessError("MODEL_USAGE", "calls and tokens must be non-negative integers")
    p = profile["model_policy"]
    c = case_pack["model_budget"]
    max_calls = min(p["max_total_calls"], c["max_total_calls"])
    max_tokens = min(p["max_total_tokens"], c["max_total_tokens"])
    require_measured = bool(p["require_measured_usage"] or c["require_measured_usage"])
    if require_measured and value["measurement_status"] == "UNMEASURED":
        raise HarnessError("UNMEASURED_USAGE", "required model usage is unmeasured")
    if value["calls"] != 0 or value["tokens"] != 0:
        raise HarnessError("MODEL_DISABLED", "this slice permits no model execution")
    return {
        **value,
        "max_total_calls": max_calls,
        "max_total_tokens": max_tokens,
    }


def _checkpoint(identifier: str, phase: str, observations: Sequence[str]) -> dict[str, Any]:
    return {
        "checkpoint": identifier,
        "phase": phase,
        "result": "PASS",
        "observations": list(observations),
    }


def _authority_snapshot(context: RunContext) -> dict[str, Any]:
    return {
        "operation_id": "authority-snapshot",
        "result": "PASS",
        "observations": [
            "AUTHORITY_REFERENCES_MATCH",
            "CASE_PACK_IS_NOT_SELF_AUTHORIZING",
        ],
        "derived_from": list(context.authority_refs),
    }


def _artifact_integrity(context: RunContext) -> dict[str, Any]:
    return {
        "operation_id": "artifact-integrity",
        "result": "PASS",
        "observations": ["ARTIFACT_HASHES_MATCH"],
        "derived_from": list(context.artifacts),
    }


def _review_readiness(context: RunContext) -> dict[str, Any]:
    observations: list[str] = []
    derived: list[dict[str, str]] = []
    if context.review_input is None and context.review_response is None:
        observations.append("INDEPENDENT_REVIEW_NOT_ATTACHED")
    elif context.review_input is None:
        raise HarnessError("REVIEW_INPUT_REQUIRED", "review response requires frozen review input")
    else:
        derived.append(
            {
                "role": "REVIEW_INPUT",
                "path": context.review_input.relative_path,
                "sha256": context.review_input.sha256,
            }
        )
        observations.append("REVIEW_INPUT_ISOLATED_FROM_IMPLEMENTER_CONCLUSION")
        if context.review_response is None:
            observations.append("INDEPENDENT_REVIEW_NOT_ATTACHED")
        else:
            validate_review_response(
                context.root,
                context.review_response,
                review_input=context.review_input,
            )
            observations.append("SURROGATE_REVIEW_CONTRACT_VALID")
            derived.append(
                {
                    "role": "ENGINEERING_REVIEW_RESPONSE",
                    "path": context.review_response.relative_path,
                    "sha256": context.review_response.sha256,
                }
            )
    return {
        "operation_id": "review-readiness",
        "result": "PASS",
        "observations": observations,
        "derived_from": derived,
    }


def _final_audit(context: RunContext) -> dict[str, Any]:
    return {
        "operation_id": "final-audit",
        "result": "PASS",
        "observations": [
            "RUNNER_PERFORMED_NO_BUSINESS_ROW_ACCESS",
            "RUNNER_PERFORMED_NO_SOURCE_WRITE",
            "RUNNER_PERFORMED_NO_MODEL_EGRESS",
            "SOURCE_OWNED_DELIVERY_STATUS_NOT_PROMOTED",
        ],
        "derived_from": [],
    }


Operation = Callable[[RunContext], dict[str, Any]]
OPERATION_REGISTRY: Mapping[str, Operation] = {
    "authority-snapshot": _authority_snapshot,
    "artifact-integrity": _artifact_integrity,
    "review-readiness": _review_readiness,
    "final-audit": _final_audit,
}


def _cache_key(context: RunContext) -> str:
    frozen = [ref["sha256"] for ref in context.artifacts if ref["role"] == "FROZEN_INPUTS"]
    payload = {
        "frozen_input_hashes": frozen,
        "review_contract": REVIEW_VERSION,
        "model_policy": context.profile.payload["model_policy"],
        "model_budget": context.case_pack.payload["model_budget"],
    }
    return sha256_bytes(canonical_json(payload).encode("utf-8"))


def _derive_contract_isolation(context: RunContext) -> str:
    if context.case_pack.payload["contract_isolation_check"] is not True:
        return "NOT_APPLICABLE"
    schema_name = str(context.case_pack.payload["schema_name"])
    case_identifiers = canonical_json(
        {
            "case_id": context.case_pack.payload["case_id"],
            "schema_name": schema_name,
        }
    ).upper()
    if any(token in case_identifiers for token in ISOLATION_PROHIBITED_TOKENS):
        raise HarnessError(
            "INVALID_ISOLATION_CASE",
            "a TRADEFLOW-shaped Case identifier cannot request contract-isolation PASS",
        )
    frozen_refs = [ref for ref in context.artifacts if ref["role"] == "FROZEN_INPUTS"]
    if len(frozen_refs) != 1:
        raise HarnessError("INVALID_ISOLATION_CASE", "exactly one frozen input is required")
    frozen_ref = frozen_refs[0]
    fixture_prefix = "tests/fixtures/cognition_harness/"
    if any(not ref["path"].startswith(fixture_prefix) for ref in context.artifacts):
        raise HarnessError(
            "INVALID_ISOLATION_CASE",
            "all isolation artifacts must come from the repository fixture boundary",
        )
    if not frozen_ref["path"].startswith(fixture_prefix):
        raise HarnessError(
            "INVALID_ISOLATION_CASE",
            "isolation input must be a repository test fixture",
        )
    frozen = _load_mapping(resolve_workspace_path(context.root, frozen_ref["path"]))
    if frozen.get("schema_name") != schema_name:
        raise HarnessError("INVALID_ISOLATION_CASE", "fixture and Case schema names differ")
    for key in ("objects", "missing_metadata", "ambiguous_relations", "misleading_names"):
        if not isinstance(frozen.get(key), list) or not frozen[key]:
            raise HarnessError(
                "INVALID_ISOLATION_CASE",
                f"fixture does not demonstrate required structural condition: {key}",
            )
    for index, item in enumerate(frozen["objects"]):
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("object_name"), str)
            or not item["object_name"]
            or not isinstance(item.get("columns"), list)
            or not item["columns"]
        ):
            raise HarnessError(
                "INVALID_ISOLATION_CASE", f"objects[{index}] lacks object/column structure"
            )
        if any(
            not isinstance(column, dict)
            or not isinstance(column.get("name"), str)
            or not column["name"]
            for column in item["columns"]
        ):
            raise HarnessError(
                "INVALID_ISOLATION_CASE", f"objects[{index}] has an invalid column"
            )
    if not all(isinstance(item, str) and item for item in frozen["missing_metadata"]):
        raise HarnessError("INVALID_ISOLATION_CASE", "missing_metadata entries are invalid")
    for index, item in enumerate(frozen["ambiguous_relations"]):
        if not isinstance(item, dict) or any(
            not isinstance(item.get(key), str) or not item[key]
            for key in ("left", "right", "reason")
        ):
            raise HarnessError(
                "INVALID_ISOLATION_CASE", f"ambiguous_relations[{index}] is invalid"
            )
    for index, item in enumerate(frozen["misleading_names"]):
        if not isinstance(item, dict) or any(
            not isinstance(item.get(key), str) or not item[key]
            for key in ("field", "reason")
        ):
            raise HarnessError(
                "INVALID_ISOLATION_CASE", f"misleading_names[{index}] is invalid"
            )
    semantic_refs = [ref for ref in context.artifacts if ref["role"] == "SEMANTIC_CONFIG"]
    if len(semantic_refs) != 1:
        raise HarnessError("INVALID_ISOLATION_CASE", "exactly one semantic config is required")
    semantic_config = _load_mapping(
        resolve_workspace_path(context.root, semantic_refs[0]["path"])
    )
    if semantic_config.get("schema_name") != schema_name:
        raise HarnessError(
            "INVALID_ISOLATION_CASE",
            "semantic config and Case schema names differ",
        )
    fixture_text = canonical_json({"frozen": frozen, "semantic_config": semantic_config}).upper()
    leaked = [token for token in ISOLATION_PROHIBITED_TOKENS if token in fixture_text]
    if leaked:
        raise HarnessError(
            "INVALID_ISOLATION_CASE",
            f"fixture contains prohibited case identifiers: {leaked}",
        )
    fixture_contract = {
        "frozen": frozen,
        "semantic_config": semantic_config,
    }
    fingerprint = sha256_bytes(canonical_json(fixture_contract).encode("utf-8"))
    if fingerprint != ISOLATION_STRUCTURE_FINGERPRINT:
        raise HarnessError(
            "INVALID_ISOLATION_CASE",
            f"fixture structure fingerprint drifted: {fingerprint}",
        )
    return "PASS"


def run_harness(
    root: Path,
    profile_path: str,
    case_pack_path: str,
    *,
    review_input_path: str | None = None,
    review_response_path: str | None = None,
    model_usage: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    profile = load_document(root, profile_path)
    case_pack = load_document(root, case_pack_path)
    validate_profile(profile.payload)
    artifacts, authority_refs = validate_case_pack(root, case_pack.payload, profile.payload)
    usage = _normalize_model_usage(profile.payload, case_pack.payload, model_usage)
    review_input = load_document(root, review_input_path) if review_input_path is not None else None
    review_response = (
        load_document(root, review_response_path) if review_response_path is not None else None
    )
    if review_input is not None:
        validate_review_package(
            root,
            review_input,
            allowed_refs=(*artifacts, *authority_refs),
            ambiguity_triggers=profile.payload["ambiguity_triggers"],
        )
    if review_response is not None and review_input is None:
        raise HarnessError("REVIEW_INPUT_REQUIRED", "review response requires frozen review input")
    context = RunContext(
        root=root,
        profile=profile,
        case_pack=case_pack,
        artifacts=artifacts,
        authority_refs=authority_refs,
        model_usage=usage,
        review_input=review_input,
        review_response=review_response,
    )

    checkpoints: list[dict[str, Any]] = [
        _checkpoint("PREFLIGHT", "before-operations", ["PROFILE_AND_CASE_VALID"])
    ]
    operations: list[dict[str, Any]] = []
    for operation_id in OPERATION_ORDER:
        if operation_id == "review-readiness":
            checkpoints.append(
                _checkpoint("PRE_REVIEW", "before-review", ["PRIOR_STAGES_VERIFIED"])
            )
        operation = OPERATION_REGISTRY[operation_id](context)
        operations.append(operation)
        checkpoints.append(
            _checkpoint(
                "POST_STAGE",
                operation_id,
                [f"{operation_id.upper().replace('-', '_')}_VERIFIED"],
            )
        )
        if operation_id == "review-readiness":
            checkpoints.append(
                _checkpoint("POST_REVIEW", "after-review", list(operation["observations"]))
            )
    checkpoints.append(
        _checkpoint("PRE_FINALIZE", "before-report", ["ALL_FIXED_CHECKPOINTS_EXECUTED"])
    )

    derived_from = [
        {"role": "WORKFLOW_PROFILE", "path": profile.relative_path, "sha256": profile.sha256},
        {"role": "SCHEMA_CASE_PACK", "path": case_pack.relative_path, "sha256": case_pack.sha256},
        *authority_refs,
        *artifacts,
    ]
    if review_input is not None:
        derived_from.append(
            {
                "role": "REVIEW_INPUT",
                "path": review_input.relative_path,
                "sha256": review_input.sha256,
            }
        )
    if review_response is not None:
        derived_from.append(
            {
                "role": "ENGINEERING_REVIEW_RESPONSE",
                "path": review_response.relative_path,
                "sha256": review_response.sha256,
            }
        )
    report: dict[str, Any] = {
        "schema_version": REPORT_VERSION,
        "report_kind": "DERIVED_AUDIT_PROJECTION",
        "profile_id": profile.payload["profile_id"],
        "case_id": case_pack.payload["case_id"],
        "derived_from": derived_from,
        "checkpoints": checkpoints,
        "operations": operations,
        "model_usage": {**usage, "cache_key": _cache_key(context)},
        "conflicts": [
            {
                "source_ref": ref["path"],
                "source_sha256": ref["sha256"],
                "observation": "REFER_TO_SOURCE; HARNESS_DID_NOT_REEVALUATE_DOMAIN_CONFLICTS",
            }
            for ref in artifacts
            if ref["role"] == "SURROGATE_REVIEW"
        ],
        "gaps": (
            [{"code": "INDEPENDENT_REVIEW_NOT_ATTACHED", "source_ref": profile.relative_path}]
            if review_response is None
            else (
                []
                if review_response.payload["disposition"] == "ACCEPT"
                else [
                    {
                        "code": "ENGINEERING_REVIEW_FOLLOW_UP_REQUIRED",
                        "source_ref": review_response.relative_path,
                    }
                ]
            )
        ),
        "contract_isolation_check": _derive_contract_isolation(context),
    }
    report["report_id"] = sha256_bytes(canonical_json(report).encode("utf-8"))[:24]
    validate_report(report, root=root)
    return report


def _validate_report_reference(ref: Any, label: str) -> tuple[str, str, str]:
    if not isinstance(ref, dict):
        raise HarnessError("REPORT_SCHEMA", f"{label} must be an object")
    _require_exact_keys(
        ref,
        frozenset({"role", "path", "sha256"}),
        frozenset({"role", "path", "sha256"}),
        label,
    )
    if not all(isinstance(ref[key], str) and ref[key] for key in ("role", "path")):
        raise HarnessError("REPORT_SCHEMA", f"{label} has an empty role or path")
    if re.fullmatch(r"[0-9a-f]{64}", str(ref["sha256"])) is None:
        raise HarnessError("REPORT_SCHEMA", f"{label} has an invalid SHA-256")
    return _reference_identity(ref)


def _validate_report_against_sources(root: Path, report: Mapping[str, Any]) -> None:
    refs = report["derived_from"]

    def single(role: str, *, required: bool = True) -> Mapping[str, Any] | None:
        matches = [ref for ref in refs if ref["role"] == role]
        if len(matches) > 1 or (required and len(matches) != 1):
            raise HarnessError("REPORT_SOURCE", f"expected one {role} reference")
        return matches[0] if matches else None

    profile_ref = single("WORKFLOW_PROFILE")
    case_ref = single("SCHEMA_CASE_PACK")
    assert profile_ref is not None and case_ref is not None
    profile = load_document(root, str(profile_ref["path"]))
    case_pack = load_document(root, str(case_ref["path"]))
    validate_profile(profile.payload)
    artifacts, authority_refs = validate_case_pack(root, case_pack.payload, profile.payload)

    review_input_ref = single("REVIEW_INPUT", required=False)
    review_response_ref = single("ENGINEERING_REVIEW_RESPONSE", required=False)
    review_input = (
        load_document(root, str(review_input_ref["path"]))
        if review_input_ref is not None
        else None
    )
    review_response = (
        load_document(root, str(review_response_ref["path"]))
        if review_response_ref is not None
        else None
    )
    if review_response is not None and review_input is None:
        raise HarnessError("REPORT_SOURCE", "review response has no frozen review input")
    if review_input is not None:
        validate_review_package(
            root,
            review_input,
            allowed_refs=(*artifacts, *authority_refs),
            ambiguity_triggers=profile.payload["ambiguity_triggers"],
        )
    if review_response is not None:
        validate_review_response(root, review_response, review_input=review_input)

    expected_refs = {
        _reference_identity(
            {"role": "WORKFLOW_PROFILE", "path": profile.relative_path, "sha256": profile.sha256}
        ),
        _reference_identity(
            {
                "role": "SCHEMA_CASE_PACK",
                "path": case_pack.relative_path,
                "sha256": case_pack.sha256,
            }
        ),
        *(_reference_identity(ref) for ref in authority_refs),
        *(_reference_identity(ref) for ref in artifacts),
    }
    if review_input is not None:
        expected_refs.add(("REVIEW_INPUT", review_input.relative_path, review_input.sha256))
    if review_response is not None:
        expected_refs.add(
            ("ENGINEERING_REVIEW_RESPONSE", review_response.relative_path, review_response.sha256)
        )
    actual_refs = {_reference_identity(ref) for ref in refs}
    if len(actual_refs) != len(refs):
        raise HarnessError("REPORT_SOURCE", "derived_from contains duplicate references")
    if actual_refs != expected_refs:
        raise HarnessError("REPORT_SOURCE", "derived_from does not match Profile/Case sources")

    usage = report["model_usage"]
    expected_usage = _normalize_model_usage(profile.payload, case_pack.payload, None)
    context = RunContext(
        root=root,
        profile=profile,
        case_pack=case_pack,
        artifacts=artifacts,
        authority_refs=authority_refs,
        model_usage=expected_usage,
        review_input=review_input,
        review_response=review_response,
    )
    expected_operations = [
        OPERATION_REGISTRY[operation_id](context) for operation_id in OPERATION_ORDER
    ]
    if report["operations"] != expected_operations:
        raise HarnessError("REPORT_DERIVATION", "operations were not re-derived")
    expected_checkpoints: list[dict[str, Any]] = [
        _checkpoint("PREFLIGHT", "before-operations", ["PROFILE_AND_CASE_VALID"])
    ]
    for operation in expected_operations:
        operation_id = operation["operation_id"]
        if operation_id == "review-readiness":
            expected_checkpoints.append(
                _checkpoint("PRE_REVIEW", "before-review", ["PRIOR_STAGES_VERIFIED"])
            )
        expected_checkpoints.append(
            _checkpoint(
                "POST_STAGE",
                operation_id,
                [f"{operation_id.upper().replace('-', '_')}_VERIFIED"],
            )
        )
        if operation_id == "review-readiness":
            expected_checkpoints.append(
                _checkpoint("POST_REVIEW", "after-review", list(operation["observations"]))
            )
    expected_checkpoints.append(
        _checkpoint("PRE_FINALIZE", "before-report", ["ALL_FIXED_CHECKPOINTS_EXECUTED"])
    )
    if report["checkpoints"] != expected_checkpoints:
        raise HarnessError("REPORT_DERIVATION", "checkpoints were not re-derived")
    expected_model_usage = {**expected_usage, "cache_key": _cache_key(context)}
    if usage != expected_model_usage:
        raise HarnessError("REPORT_DERIVATION", "model_usage is not derived from Profile/Case")
    if report["profile_id"] != profile.payload["profile_id"]:
        raise HarnessError("REPORT_DERIVATION", "profile_id differs from source")
    if report["case_id"] != case_pack.payload["case_id"]:
        raise HarnessError("REPORT_DERIVATION", "case_id differs from source")
    expected_isolation = _derive_contract_isolation(context)
    if report["contract_isolation_check"] != expected_isolation:
        raise HarnessError("REPORT_DERIVATION", "contract isolation was not re-derived")
    expected_gaps = (
        [{"code": "INDEPENDENT_REVIEW_NOT_ATTACHED", "source_ref": profile.relative_path}]
        if review_response is None
        else (
            []
            if review_response.payload["disposition"] == "ACCEPT"
            else [
                {
                    "code": "ENGINEERING_REVIEW_FOLLOW_UP_REQUIRED",
                    "source_ref": review_response.relative_path,
                }
            ]
        )
    )
    if report["gaps"] != expected_gaps:
        raise HarnessError("REPORT_DERIVATION", "gaps do not match attached review sources")
    expected_conflicts = [
        {
            "source_ref": ref["path"],
            "source_sha256": ref["sha256"],
            "observation": "REFER_TO_SOURCE; HARNESS_DID_NOT_REEVALUATE_DOMAIN_CONFLICTS",
        }
        for ref in artifacts
        if ref["role"] == "SURROGATE_REVIEW"
    ]
    if report["conflicts"] != expected_conflicts:
        raise HarnessError("REPORT_DERIVATION", "conflicts were not re-derived")


def validate_report(report: Mapping[str, Any], *, root: Path | None = None) -> None:
    _require_exact_keys(
        report,
        frozenset(
            {
                "schema_version",
                "report_kind",
                "report_id",
                "profile_id",
                "case_id",
                "derived_from",
                "checkpoints",
                "operations",
                "model_usage",
                "conflicts",
                "gaps",
                "contract_isolation_check",
            }
        ),
        frozenset(
            {
                "schema_version",
                "report_kind",
                "report_id",
                "profile_id",
                "case_id",
                "derived_from",
                "checkpoints",
                "operations",
                "model_usage",
                "conflicts",
                "gaps",
                "contract_isolation_check",
            }
        ),
        "report",
    )
    if report.get("schema_version") != REPORT_VERSION:
        raise HarnessError("REPORT_VERSION", str(report.get("schema_version")))
    if report.get("report_kind") != "DERIVED_AUDIT_PROJECTION":
        raise HarnessError("REPORT_KIND", str(report.get("report_kind")))
    _reject_keys(report, FORBIDDEN_REPORT_KEYS, "REPORT_OWNS_DOMAIN_STATE")
    if "CROSS_SCHEMA_VALIDATED" in canonical_json(report).upper():
        raise HarnessError("FALSE_CROSS_SCHEMA_CLAIM", "synthetic isolation is not validation")
    if report["contract_isolation_check"] not in {"NOT_APPLICABLE", "PASS", "FAIL"}:
        raise HarnessError("REPORT_SCHEMA", "invalid contract_isolation_check")

    report_without_id = dict(report)
    supplied_report_id = report_without_id.pop("report_id")
    expected_report_id = sha256_bytes(
        canonical_json(report_without_id).encode("utf-8")
    )[:24]
    if supplied_report_id != expected_report_id:
        raise HarnessError(
            "REPORT_HASH",
            f"expected report_id {expected_report_id}, got {supplied_report_id}",
        )

    if not isinstance(report["derived_from"], list) or not report["derived_from"]:
        raise HarnessError("REPORT_SCHEMA", "derived_from references are required")
    source_identities = {
        _validate_report_reference(ref, f"derived_from[{index}]")
        for index, ref in enumerate(report["derived_from"])
    }
    if root is not None:
        for index, ref in enumerate(report["derived_from"]):
            _validate_ref(root, ref, f"derived_from[{index}]")

    required_sequence = [
        ("PREFLIGHT", "before-operations"),
        ("POST_STAGE", "authority-snapshot"),
        ("POST_STAGE", "artifact-integrity"),
        ("PRE_REVIEW", "before-review"),
        ("POST_STAGE", "review-readiness"),
        ("POST_REVIEW", "after-review"),
        ("POST_STAGE", "final-audit"),
        ("PRE_FINALIZE", "before-report"),
    ]
    actual = [(item.get("checkpoint"), item.get("phase")) for item in report.get("checkpoints", [])]
    if actual != required_sequence:
        raise HarnessError("CHECKPOINT_BYPASS", f"unexpected checkpoint sequence: {actual}")
    for index, checkpoint in enumerate(report["checkpoints"]):
        if not isinstance(checkpoint, dict):
            raise HarnessError("REPORT_SCHEMA", f"checkpoints[{index}] must be an object")
        _require_exact_keys(
            checkpoint,
            frozenset({"checkpoint", "phase", "result", "observations"}),
            frozenset({"checkpoint", "phase", "result", "observations"}),
            f"checkpoints[{index}]",
        )
        if checkpoint["result"] != "PASS":
            raise HarnessError("CHECKPOINT_FAILURE", f"checkpoints[{index}] is not PASS")
        if not isinstance(checkpoint["observations"], list) or not all(
            isinstance(item, str) and item for item in checkpoint["observations"]
        ):
            raise HarnessError("REPORT_SCHEMA", f"checkpoints[{index}] observations invalid")
    if [item.get("operation_id") for item in report.get("operations", [])] != list(
        OPERATION_ORDER
    ):
        raise HarnessError("OPERATION_BYPASS", "operation sequence changed")
    for index, operation in enumerate(report["operations"]):
        if not isinstance(operation, dict):
            raise HarnessError("REPORT_SCHEMA", f"operations[{index}] must be an object")
        _require_exact_keys(
            operation,
            frozenset({"operation_id", "result", "observations", "derived_from"}),
            frozenset({"operation_id", "result", "observations", "derived_from"}),
            f"operations[{index}]",
        )
        if operation["result"] != "PASS":
            raise HarnessError("OPERATION_FAILURE", f"operations[{index}] is not PASS")
        if not isinstance(operation["observations"], list) or not all(
            isinstance(item, str) and item for item in operation["observations"]
        ):
            raise HarnessError("REPORT_SCHEMA", f"operations[{index}] observations invalid")
        if not isinstance(operation["derived_from"], list):
            raise HarnessError("REPORT_SCHEMA", f"operations[{index}] derived_from invalid")
        for ref_index, ref in enumerate(operation["derived_from"]):
            identity = _validate_report_reference(
                ref, f"operations[{index}].derived_from[{ref_index}]"
            )
            if identity not in source_identities:
                raise HarnessError(
                    "REPORT_SOURCE",
                    f"operation source is absent from top-level derived_from: {identity[1]}",
                )

    model_usage = report["model_usage"]
    if not isinstance(model_usage, dict):
        raise HarnessError("REPORT_SCHEMA", "model_usage must be an object")
    _require_exact_keys(
        model_usage,
        frozenset(
            {
                "calls",
                "tokens",
                "measurement_status",
                "max_total_calls",
                "max_total_tokens",
                "cache_key",
            }
        ),
        frozenset(
            {
                "calls",
                "tokens",
                "measurement_status",
                "max_total_calls",
                "max_total_tokens",
                "cache_key",
            }
        ),
        "model_usage",
    )
    for key in ("calls", "tokens", "max_total_calls", "max_total_tokens"):
        if (
            not isinstance(model_usage[key], int)
            or isinstance(model_usage[key], bool)
            or model_usage[key] < 0
        ):
            raise HarnessError("REPORT_SCHEMA", f"model_usage.{key} is invalid")
    if model_usage["measurement_status"] not in {"MEASURED", "UNMEASURED"}:
        raise HarnessError("REPORT_SCHEMA", "model measurement status is invalid")
    if re.fullmatch(r"[0-9a-f]{64}", str(model_usage["cache_key"])) is None:
        raise HarnessError("REPORT_SCHEMA", "model cache key is invalid")

    if not isinstance(report["conflicts"], list) or not isinstance(report["gaps"], list):
        raise HarnessError("REPORT_SCHEMA", "conflicts and gaps must be arrays")
    for index, conflict in enumerate(report["conflicts"]):
        if not isinstance(conflict, dict):
            raise HarnessError("REPORT_SCHEMA", f"conflicts[{index}] must be an object")
        _require_exact_keys(
            conflict,
            frozenset({"source_ref", "source_sha256", "observation"}),
            frozenset({"source_ref", "source_sha256", "observation"}),
            f"conflicts[{index}]",
        )
    for index, gap in enumerate(report["gaps"]):
        if not isinstance(gap, dict):
            raise HarnessError("REPORT_SCHEMA", f"gaps[{index}] must be an object")
        _require_exact_keys(
            gap,
            frozenset({"code", "source_ref"}),
            frozenset({"code", "source_ref"}),
            f"gaps[{index}]",
        )
    if root is not None:
        _validate_report_against_sources(root, report)


def write_immutable_report(root: Path, raw_path: str, report: Mapping[str, Any]) -> Path:
    path = resolve_workspace_path(root, raw_path, must_exist=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if path.exists():
        existing = path.read_bytes()
        if existing != encoded:
            raise HarnessError("IMMUTABLE_REPORT", f"refusing to overwrite {path}")
        return path
    path.write_bytes(encoded)
    return path


def _read_model_usage(root: Path, path: str | None) -> Mapping[str, Any] | None:
    if path is None:
        return None
    resolved = resolve_workspace_path(root, path)
    value = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise HarnessError("MODEL_USAGE", "usage file must contain an object")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m titans_cognition.cognition_harness")
    parser.add_argument("--root", default=".", help="workspace root")
    subparsers = parser.add_subparsers(dest="action", required=True)

    run = subparsers.add_parser("run", help="run the fixed governance workflow")
    run.add_argument("--profile", required=True)
    run.add_argument("--case-pack", required=True)
    run.add_argument("--output", required=True)
    run.add_argument("--review-input")
    run.add_argument("--review-response")
    run.add_argument("--model-usage")

    verify = subparsers.add_parser("verify-report", help="validate an existing report")
    verify.add_argument("--report", required=True)

    review_input = subparsers.add_parser(
        "validate-review-input", help="reject contaminated independent-review input"
    )
    review_input.add_argument("--input", required=True)
    review_input.add_argument("--profile", required=True)
    review_input.add_argument("--case-pack", required=True)

    review_response = subparsers.add_parser(
        "validate-review-response", help="validate an independent-review response"
    )
    review_response.add_argument("--response", required=True)
    review_response.add_argument("--review-input", required=True)
    review_response.add_argument("--profile", required=True)
    review_response.add_argument("--case-pack", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        if args.action == "run":
            report = run_harness(
                root,
                args.profile,
                args.case_pack,
                review_input_path=args.review_input,
                review_response_path=args.review_response,
                model_usage=_read_model_usage(root, args.model_usage),
            )
            path = write_immutable_report(root, args.output, report)
            print(json.dumps({"report": relative_posix(root, path), "report_id": report["report_id"]}))
        elif args.action == "verify-report":
            document = load_document(root, args.report)
            validate_report(document.payload, root=root)
            print(json.dumps({"report": document.relative_path, "valid": True}))
        elif args.action == "validate-review-input":
            document = load_document(root, args.input)
            profile = load_document(root, args.profile)
            case_pack = load_document(root, args.case_pack)
            validate_profile(profile.payload)
            artifacts, authority_refs = validate_case_pack(
                root, case_pack.payload, profile.payload
            )
            validate_review_package(
                root,
                document,
                allowed_refs=(*artifacts, *authority_refs),
                ambiguity_triggers=profile.payload["ambiguity_triggers"],
            )
            print(json.dumps({"input": document.relative_path, "valid": True}))
        else:
            document = load_document(root, args.response)
            review_input_document = load_document(root, args.review_input)
            profile = load_document(root, args.profile)
            case_pack = load_document(root, args.case_pack)
            validate_profile(profile.payload)
            artifacts, authority_refs = validate_case_pack(
                root, case_pack.payload, profile.payload
            )
            validate_review_package(
                root,
                review_input_document,
                allowed_refs=(*artifacts, *authority_refs),
                ambiguity_triggers=profile.payload["ambiguity_triggers"],
            )
            validate_review_response(
                root,
                document,
                review_input=review_input_document,
            )
            print(json.dumps({"response": document.relative_path, "valid": True}))
    except (HarnessError, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
