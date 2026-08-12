"""Bounded, replayable LLM review of deterministic field-concept candidates."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Iterable
import unicodedata

import yaml


METHOD_ID = "llm_field_review.bounded.v1"
METHOD_VERSION = "v1"
PROMPT_VERSION = "field-concept-review-prompt-v1"
RESPONSE_SCHEMA_VERSION = "field-concept-review-response-v1"
ALLOWED_ACTIONS = frozenset(
    {"KEEP", "RENAME", "SPLIT", "PARENT_CHILD", "FACET", "ABSTAIN"}
)
_WORD = re.compile(r"[A-Z0-9]+|[\u4e00-\u9fff]+")


@dataclass(frozen=True)
class ReviewConfig:
    """Validated controls for a bounded field-concept review run."""

    raw: dict[str, object]
    config_hash: str
    min_members: int
    low_cohesion_threshold: float
    outlier_similarity_threshold: float
    outlier_ratio_threshold: float
    weak_label_support_threshold: float
    ambiguity_ratio_threshold: float
    mixed_qualifier_count: int
    max_packs: int
    max_fields_per_pack: int
    max_pack_tokens: int
    token_budget: int
    chars_per_token: float
    representative_count: int
    boundary_count: int
    outlier_count: int
    qualifier_dimensions: dict[str, dict[str, tuple[str, ...]]]
    provider_approved: bool
    provider_id: str | None

    def with_run_limits(
        self, *, max_packs: int | None = None, token_budget: int | None = None
    ) -> "ReviewConfig":
        """Return a copy with explicit one-run cost controls."""

        if max_packs is not None and max_packs <= 0:
            raise ValueError("max_packs must be positive")
        if token_budget is not None and token_budget <= 0:
            raise ValueError("token_budget must be positive")
        return replace(
            self,
            max_packs=max_packs if max_packs is not None else self.max_packs,
            token_budget=(
                token_budget if token_budget is not None else self.token_budget
            ),
        )


def load_review_config(path: str | Path) -> ReviewConfig:
    """Load review configuration and freeze it with a content hash."""

    value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("LLM field review config must be a mapping")
    selection = _mapping(value, "selection")
    limits = _mapping(value, "limits")
    sampling = _mapping(value, "sampling")
    qualifier_value = value.get("qualifier_dimensions", {})
    if not isinstance(qualifier_value, dict):
        raise ValueError("qualifier_dimensions must be a mapping")
    qualifiers: dict[str, dict[str, tuple[str, ...]]] = {}
    for dimension, entries in qualifier_value.items():
        if not isinstance(entries, dict):
            raise ValueError(f"qualifier_dimensions.{dimension} must be a mapping")
        normalized_entries: dict[str, tuple[str, ...]] = {}
        for label, terms in entries.items():
            if not isinstance(terms, list) or not terms:
                raise ValueError(
                    f"qualifier_dimensions.{dimension}.{label} must be a non-empty list"
                )
            normalized_entries[str(label)] = tuple(str(term).upper() for term in terms)
        qualifiers[str(dimension)] = normalized_entries
    provider = value.get("provider_sdk", {})
    if not isinstance(provider, dict):
        raise ValueError("provider_sdk must be a mapping")
    provider_approved = bool(provider.get("d005_approved", False))
    provider_id = str(provider["provider_id"]) if provider.get("provider_id") else None
    if provider_approved and not provider_id:
        raise ValueError("provider_sdk.provider_id is required when D-005 is approved")
    canonical = _canonical_json(value)
    return ReviewConfig(
        raw=value,
        config_hash=_sha256_text(canonical),
        min_members=_positive_int(selection, "min_members", 2),
        low_cohesion_threshold=_ratio(selection, "low_cohesion_threshold", 0.42),
        outlier_similarity_threshold=_ratio(
            selection, "outlier_similarity_threshold", 0.18
        ),
        outlier_ratio_threshold=_ratio(selection, "outlier_ratio_threshold", 0.25),
        weak_label_support_threshold=_ratio(
            selection, "weak_label_support_threshold", 0.35
        ),
        ambiguity_ratio_threshold=_ratio(
            selection, "ambiguity_ratio_threshold", 0.20
        ),
        mixed_qualifier_count=_positive_int(
            selection, "mixed_qualifier_count", 2
        ),
        max_packs=_positive_int(limits, "max_packs", 12),
        max_fields_per_pack=_positive_int(limits, "max_fields_per_pack", 40),
        max_pack_tokens=_positive_int(limits, "max_pack_tokens", 4_000),
        token_budget=_positive_int(limits, "token_budget", 20_000),
        chars_per_token=_positive_float(limits, "chars_per_token", 2.0),
        representative_count=_positive_int(sampling, "representative_count", 4),
        boundary_count=_positive_int(sampling, "boundary_count", 3),
        outlier_count=_positive_int(sampling, "outlier_count", 3),
        qualifier_dimensions=qualifiers,
        provider_approved=provider_approved,
        provider_id=provider_id,
    )


def prepare_review(
    field_concepts_dir: str | Path,
    config: ReviewConfig,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Select difficult clusters and export content-addressed review Packs."""

    baseline = Path(field_concepts_dir)
    concepts = _read_jsonl(baseline / "concepts.jsonl")
    concept_by_id = {str(row["concept_id"]): row for row in concepts}
    links = _read_jsonl(baseline / "field_concept_links.jsonl")
    manifest = _read_object(baseline / "manifest.json")
    members_by_concept: dict[str, list[dict[str, object]]] = defaultdict(list)
    alternatives_by_field: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in links:
        if int(row.get("rank", 1)) == 1:
            members_by_concept[str(row["concept_id"])].append(row)
        else:
            alternatives_by_field[str(row["field_id"])].append(row)
    scored = []
    for concept in concepts:
        concept_id = str(concept["concept_id"])
        members = sorted(
            members_by_concept.get(concept_id, []), key=lambda row: str(row["field_id"])
        )
        if len(members) < config.min_members:
            continue
        issue = _score_issue(
            concept,
            members,
            alternatives_by_field,
            concept_by_id,
            config,
        )
        if issue["reasons"]:
            scored.append(issue)
    scored.sort(
        key=lambda row: (
            -float(row["issue_score"]),
            str(row["concept_id"]),
        )
    )

    root = Path(output_dir) / "field-concepts" / "llm-review"
    root.mkdir(parents=True, exist_ok=True)
    selected_rows: list[dict[str, object]] = []
    packs: list[dict[str, object]] = []
    used_tokens = 0
    max_pack_skipped = 0
    oversized_pack_skipped = 0
    token_budget_skipped = 0
    for issue in scored:
        if len(packs) >= config.max_packs:
            max_pack_skipped += 1
            continue
        concept_id = str(issue["concept_id"])
        concept = next(row for row in concepts if str(row["concept_id"]) == concept_id)
        pack = _build_pack(
            concept,
            members_by_concept[concept_id],
            alternatives_by_field,
            issue,
            manifest,
            config,
        )
        estimated_tokens = int(pack["estimated_tokens"])
        if estimated_tokens > config.max_pack_tokens:
            oversized_pack_skipped += 1
            continue
        if used_tokens + estimated_tokens > config.token_budget:
            token_budget_skipped += 1
            continue
        used_tokens += estimated_tokens
        selected_rows.append(issue)
        packs.append(pack)

    selection_path = root / "selection.jsonl"
    packs_path = root / "packs.jsonl"
    batch_path = root / "current_gpt_batch.json"
    errors_path = root / "errors.jsonl"
    responses_path = root / "responses.jsonl"
    candidates_path = root / "revision_candidates.jsonl"
    _write_jsonl(selection_path, selected_rows)
    _write_jsonl(packs_path, packs)
    _write_jsonl(errors_path, [])
    _write_jsonl(responses_path, [])
    _write_jsonl(candidates_path, [])
    batch = {
        "prompt_version": PROMPT_VERSION,
        "response_schema_version": RESPONSE_SCHEMA_VERSION,
        "instruction": _prompt_instruction(),
        "allowed_actions": sorted(ALLOWED_ACTIONS),
        "response_contract": _response_contract(),
        "packs": packs,
    }
    batch_path.write_text(_pretty_json(batch), encoding="utf-8")
    run_manifest = {
        "stage_id": "llm-assisted-field-concept-review",
        "stage_status": "AWAITING_RESPONSES" if packs else "SUCCESS",
        "method_id": METHOD_ID,
        "method_version": METHOD_VERSION,
        "input_run_id": manifest.get("run_id"),
        "input_manifest_sha256": _sha256_path(baseline / "manifest.json"),
        "input_concepts_sha256": _sha256_path(baseline / "concepts.jsonl"),
        "input_links_sha256": _sha256_path(baseline / "field_concept_links.jsonl"),
        "config_sha256": config.config_hash,
        "prompt_version": PROMPT_VERSION,
        "response_schema_version": RESPONSE_SCHEMA_VERSION,
        "llm_mode": "offline-current-gpt",
        "sdk_status": provider_status(config),
        "source_field_concepts_dir": str(baseline.resolve()),
        "stats": {
            "eligible_issue_count": len(scored),
            "selected_pack_count": len(packs),
            "max_pack_skipped_count": max_pack_skipped,
            "oversized_pack_skipped_count": oversized_pack_skipped,
            "token_budget_skipped_count": token_budget_skipped,
            "budget_skipped_count": oversized_pack_skipped + token_budget_skipped,
            "estimated_token_count": used_tokens,
            "token_budget": config.token_budget,
            "actual_token_count": None,
            "actual_token_status": "NOT_AVAILABLE_CURRENT_SESSION",
        },
        "outputs": [],
        "known_gaps": [
            "LLM output is a candidate and does not modify the deterministic baseline",
            "token counts are estimates until a model response reports actual usage",
            "only algorithmically selected clusters are reviewed",
        ],
    }
    manifest_path = root / "manifest.json"
    run_manifest["outputs"] = _output_entries(
        root,
        [selection_path, packs_path, batch_path, errors_path, responses_path, candidates_path],
    )
    manifest_path.write_text(_pretty_json(run_manifest), encoding="utf-8")
    return {
        "root": root,
        "selection": selection_path,
        "packs": packs_path,
        "batch": batch_path,
        "responses": responses_path,
        "candidates": candidates_path,
        "errors": errors_path,
        "manifest": manifest_path,
    }


def import_review_responses(
    review_dir: str | Path,
    responses: str | Path,
    *,
    model_id: str,
    cache_dir: str | Path | None = None,
) -> dict[str, int]:
    """Import model responses independently and preserve every validation result."""

    root = Path(review_dir)
    pack_rows = _read_jsonl(root / "packs.jsonl")
    packs = {str(row["pack_id"]): row for row in pack_rows}
    response_rows: list[dict[str, object]] = []
    candidates: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    path = Path(responses)
    lines = path.read_text(encoding="utf-8").splitlines()
    response_count = sum(bool(line.strip()) for line in lines)
    parsed_inputs: list[tuple[int, dict[str, object], bool]] = []
    provided_pack_ids: set[str] = set()
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(
                _error_row(line_number, "INVALID_JSON", str(exc), raw=line[:1_000])
            )
            continue
        if not isinstance(value, dict):
            errors.append(
                _error_row(line_number, "INVALID_RESPONSE", "response must be an object")
            )
            continue
        parsed_inputs.append((line_number, value, False))
        provided_pack_ids.add(str(value.get("pack_id") or ""))
    if cache_dir is not None:
        for pack_id, pack in sorted(packs.items()):
            if pack_id in provided_pack_ids:
                continue
            try:
                cached = _read_cache(Path(cache_dir), pack, model_id)
            except (json.JSONDecodeError, ValueError) as exc:
                response_count += 1
                errors.append(
                    _error_row(
                        len(lines) + len(parsed_inputs) + 1,
                        "INVALID_CACHE",
                        str(exc),
                        value={"pack_id": pack_id},
                    )
                )
                continue
            if cached is not None:
                response_count += 1
                parsed_inputs.append((len(lines) + len(parsed_inputs) + 1, cached, True))

    for line_number, value, cache_hit in parsed_inputs:
        error = _validate_response(value, packs)
        payload = {
            key: item
            for key, item in value.items()
            if key
            not in {
                "model_id",
                "response_schema_version",
                "validation_status",
                "response_hash",
                "error_code",
                "cache_hit",
            }
        }
        stored = dict(payload)
        stored["model_id"] = model_id
        stored["response_schema_version"] = RESPONSE_SCHEMA_VERSION
        stored["validation_status"] = "INVALID" if error else "VALID"
        stored["cache_hit"] = cache_hit
        stored["response_hash"] = _sha256_text(_canonical_json(payload))
        if error:
            stored["error_code"] = error[0]
            response_rows.append(stored)
            errors.append(_error_row(line_number, error[0], error[1], value=value))
            continue
        response_rows.append(stored)
        pack = packs[str(value["pack_id"])]
        candidate = {
            **payload,
            "concept_id": pack["concept"]["concept_id"],
            "baseline_label": pack["concept"]["label"],
            "model_id": model_id,
            "method_id": METHOD_ID,
            "method_version": METHOD_VERSION,
            "status": "CANDIDATE",
            "response_hash": stored["response_hash"],
        }
        candidates.append(candidate)
        if cache_dir is not None:
            _write_cache(Path(cache_dir), pack, stored, model_id)

    _write_jsonl(root / "responses.jsonl", response_rows)
    _write_jsonl(root / "revision_candidates.jsonl", candidates)
    _write_jsonl(root / "errors.jsonl", errors)
    manifest = _read_object(root / "manifest.json")
    stats = dict(manifest.get("stats", {}))
    stats.update(
        {
            "response_count": response_count,
            "valid_response_count": len(candidates),
            "response_error_count": len(errors),
            "abstain_count": sum(row.get("action") == "ABSTAIN" for row in candidates),
        }
    )
    manifest["stats"] = stats
    manifest["stage_status"] = "PARTIAL" if errors else "SUCCESS"
    manifest["model_id"] = model_id
    manifest["outputs"] = _output_entries(
        root,
        [
            root / "selection.jsonl",
            root / "packs.jsonl",
            root / "current_gpt_batch.json",
            root / "responses.jsonl",
            root / "revision_candidates.jsonl",
            root / "errors.jsonl",
        ],
    )
    (root / "manifest.json").write_text(_pretty_json(manifest), encoding="utf-8")
    return {
        "response_count": response_count,
        "valid_count": len(candidates),
        "error_count": len(errors),
    }


def provider_status(config: ReviewConfig) -> dict[str, str]:
    """Report whether a future SDK route is authorized; never call a provider."""

    if not config.provider_approved:
        return {
            "status": "NOT_EVALUABLE",
            "reason": "D-005 provider SDK approval is absent",
        }
    return {"status": "ENABLED", "provider_id": str(config.provider_id)}


def render_review(
    review_dir: str | Path,
    *,
    source_panorama_root: str | Path | None = None,
) -> Path:
    """Render a bounded-DOM comparison projection for baseline and candidates."""

    root = Path(review_dir)
    packs = _read_jsonl(root / "packs.jsonl")
    candidates = _read_jsonl(root / "revision_candidates.jsonl")
    errors = _read_jsonl(root / "errors.jsonl")
    candidate_by_pack = {str(row["pack_id"]): row for row in candidates}
    error_by_pack: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in errors:
        pack_id = str(row.get("pack_id") or "")
        error_by_pack[pack_id].append(row)
    object_urls = _object_urls(packs, source_panorama_root)
    summaries = []
    fields = []
    for pack in packs:
        pack_id = str(pack["pack_id"])
        candidate = candidate_by_pack.get(pack_id)
        summaries.append(
            {
                "pack": pack_id,
                "concept": pack["concept"],
                "reasons": pack["selection"]["reasons"],
                "signals": pack["selection"]["signals"],
                "action": candidate.get("action") if candidate else None,
                "candidate": candidate,
                "validation": "VALID" if candidate else (
                    "INVALID" if error_by_pack.get(pack_id) else "PENDING"
                ),
                "status": "CANDIDATE" if candidate else "PENDING",
                "errors": error_by_pack.get(pack_id, []),
            }
        )
        for evidence in pack["evidence"]:
            fields.append(
                {
                    "pack": pack_id,
                    **evidence,
                    "object_url": object_urls.get(str(evidence.get("asset_id") or ""), ""),
                }
            )
    page = _review_html(summaries, fields)
    path = root / "review" / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
    return path


def _score_issue(
    concept: dict[str, object],
    members: list[dict[str, object]],
    alternatives_by_field: dict[str, list[dict[str, object]]],
    concept_by_id: dict[str, dict[str, object]],
    config: ReviewConfig,
) -> dict[str, object]:
    signals_by_field = {str(row["field_id"]): _signal_tokens(row) for row in members}
    similarities: dict[str, float] = {}
    for field_id, tokens in signals_by_field.items():
        peers = [
            _jaccard(tokens, other)
            for other_id, other in signals_by_field.items()
            if other_id != field_id
        ]
        similarities[field_id] = sum(peers) / len(peers) if peers else 1.0
    cohesion = sum(similarities.values()) / len(similarities)
    outlier_count = sum(
        value < config.outlier_similarity_threshold for value in similarities.values()
    )
    outlier_ratio = outlier_count / len(members)
    label = str(concept.get("label") or "").upper().replace(" ", "")
    label_support = sum(
        label and label in _combined_text(row).upper().replace(" ", "")
        for row in members
    ) / len(members)
    ambiguous = 0
    ignored_equivalent_alternatives = 0
    current_label = str(concept.get("label") or "")
    for row in members:
        meaningful_alternative = False
        for alternative in alternatives_by_field.get(str(row["field_id"]), []):
            alternative_concept = concept_by_id.get(str(alternative["concept_id"]), {})
            alternative_label = str(alternative_concept.get("label") or "")
            if _equivalent_candidate_label(current_label, alternative_label):
                ignored_equivalent_alternatives += 1
            else:
                meaningful_alternative = True
        ambiguous += meaningful_alternative
    ambiguity_ratio = ambiguous / len(members)
    qualifier_values: dict[str, list[str]] = {}
    for dimension, entries in config.qualifier_dimensions.items():
        found = []
        for value, terms in entries.items():
            if any(
                any(term in _combined_text(row).upper() for term in terms)
                for row in members
            ):
                found.append(value)
        qualifier_values[dimension] = sorted(found)
    mixed_dimensions = sum(
        len(values) >= config.mixed_qualifier_count
        for values in qualifier_values.values()
    )
    reasons = []
    if cohesion < config.low_cohesion_threshold:
        reasons.append("LOW_COHESION")
    if outlier_ratio >= config.outlier_ratio_threshold:
        reasons.append("OUTLIER_MEMBERS")
    if label_support < config.weak_label_support_threshold:
        reasons.append("WEAK_LABEL_SUPPORT")
    if ambiguity_ratio >= config.ambiguity_ratio_threshold:
        reasons.append("RELATIONSHIP_CONFLICT")
    if mixed_dimensions:
        reasons.append("MIXED_QUALIFIER_DIMENSIONS")
    issue_score = (
        max(0.0, config.low_cohesion_threshold - cohesion)
        + outlier_ratio
        + max(0.0, config.weak_label_support_threshold - label_support)
        + ambiguity_ratio
        + 0.25 * mixed_dimensions
    )
    signals: dict[str, object] = {
        "cohesion": round(cohesion, 6),
        "outlier_ratio": round(outlier_ratio, 6),
        "label_support_ratio": round(label_support, 6),
        "ambiguity_ratio": round(ambiguity_ratio, 6),
        "mixed_qualifier_dimension_count": mixed_dimensions,
        "qualifier_values": qualifier_values,
    }
    if ignored_equivalent_alternatives:
        signals["ignored_equivalent_alternative_count"] = (
            ignored_equivalent_alternatives
        )
    return {
        "concept_id": str(concept["concept_id"]),
        "label": str(concept.get("label") or ""),
        "member_count": len(members),
        "issue_score": round(issue_score, 6),
        "reasons": reasons,
        "signals": signals,
        "field_centrality": {
            field_id: round(value, 6)
            for field_id, value in sorted(similarities.items())
        },
    }


def _build_pack(
    concept: dict[str, object],
    members: list[dict[str, object]],
    alternatives_by_field: dict[str, list[dict[str, object]]],
    issue: dict[str, object],
    manifest: dict[str, object],
    config: ReviewConfig,
) -> dict[str, object]:
    centrality = {
        str(key): float(value)
        for key, value in dict(issue["field_centrality"]).items()
    }
    ordered = _sample_members(members, centrality, config)
    evidence = []
    for role, row in ordered[: config.max_fields_per_pack]:
        field_id = str(row["field_id"])
        alternatives = [
            {
                "concept_id": str(item["concept_id"]),
                "score": float(item.get("method_score", 0.0)),
            }
            for item in alternatives_by_field.get(field_id, [])
        ]
        evidence.append(
            {
                "evidence_id": f"FIELD::{field_id}",
                "field_id": field_id,
                "asset_id": str(row.get("asset_id") or ""),
                "schema_name": str(row.get("schema_name") or ""),
                "object_name": str(row.get("object_name") or ""),
                "field_name": str(row.get("field_name") or ""),
                "field_comment": row.get("field_comment"),
                "data_type": str(row.get("data_type") or ""),
                "type_family_hint": str(row.get("type_family") or ""),
                "sample_role": role,
                "centrality": centrality[field_id],
                "current_link_status": str(row.get("status") or ""),
                "alternative_concepts": alternatives,
            }
        )
    base = {
        "pack_id": f"pack-{_sha256_text(str(concept['concept_id']))[:16]}",
        "input_run_id": manifest.get("run_id"),
        "input_config_sha256": manifest.get("config_sha256"),
        "concept": {
            "concept_id": str(concept["concept_id"]),
            "label": str(concept.get("label") or ""),
            "level": int(concept.get("level", 0)),
            "parent_id": concept.get("parent_id"),
            "member_count": len(members),
        },
        "selection": {
            "issue_score": issue["issue_score"],
            "reasons": issue["reasons"],
            "signals": issue["signals"],
        },
        "evidence": evidence,
        "known_gaps": {
            "missing_comments": sum(not row.get("field_comment") for row in members),
            "omitted_member_count": max(0, len(members) - len(evidence)),
            "business_rows_available": False,
            "field_types_authoritative": False,
        },
        "allowed_actions": sorted(ALLOWED_ACTIONS),
        "prompt_version": PROMPT_VERSION,
        "response_schema_version": RESPONSE_SCHEMA_VERSION,
    }
    estimated_tokens = _estimate_tokens(base, config.chars_per_token)
    base["estimated_tokens"] = estimated_tokens
    base["pack_hash"] = _sha256_text(_canonical_json(base))
    return base


def _sample_members(
    members: list[dict[str, object]],
    centrality: dict[str, float],
    config: ReviewConfig,
) -> list[tuple[str, dict[str, object]]]:
    by_high = sorted(
        members, key=lambda row: (-centrality[str(row["field_id"])], str(row["field_id"]))
    )
    by_low = list(reversed(by_high))
    median = sorted(centrality.values())[len(centrality) // 2]
    by_boundary = sorted(
        members,
        key=lambda row: (
            abs(centrality[str(row["field_id"])] - median),
            str(row["field_id"]),
        ),
    )
    by_variant = sorted(
        members,
        key=lambda row: (
            str(row.get("field_name") or ""),
            str(row.get("field_comment") or ""),
            str(row["field_id"]),
        ),
    )
    candidates = (
        [("REPRESENTATIVE", row) for row in by_high[: config.representative_count]]
        + [("BOUNDARY", row) for row in by_boundary[: config.boundary_count]]
        + [("VARIANT", row) for row in by_variant[: config.boundary_count]]
        + [("OUTLIER", row) for row in by_low[: config.outlier_count]]
        + [("MEMBER", row) for row in sorted(members, key=lambda row: str(row["field_id"]))]
    )
    result = []
    seen = set()
    for role, row in candidates:
        field_id = str(row["field_id"])
        if field_id not in seen:
            seen.add(field_id)
            result.append((role, row))
    return result


def _validate_response(
    value: dict[str, object], packs: dict[str, dict[str, object]]
) -> tuple[str, str] | None:
    pack_id = str(value.get("pack_id") or "")
    if pack_id not in packs:
        return "UNKNOWN_PACK", f"unknown pack_id {pack_id!r}"
    pack = packs[pack_id]
    if value.get("pack_hash") != pack.get("pack_hash"):
        return "STALE_PACK_HASH", "response pack_hash does not match current Pack"
    action = str(value.get("action") or "")
    if action not in ALLOWED_ACTIONS:
        return "INVALID_ACTION", f"unsupported action {action!r}"
    if not str(value.get("rationale") or "").strip():
        return "INVALID_PAYLOAD", "rationale is required"
    known = {str(row["evidence_id"]) for row in pack["evidence"]}
    referenced = _referenced_evidence_ids(value)
    unknown = sorted(referenced - known)
    if unknown:
        return "UNKNOWN_EVIDENCE", f"unknown Evidence IDs: {unknown}"
    evidence_ids = value.get("evidence_ids")
    if action != "ABSTAIN" and (
        not isinstance(evidence_ids, list) or not evidence_ids
    ):
        return "MISSING_EVIDENCE", f"{action} requires at least one Evidence ID"
    if action == "RENAME" and not str(value.get("candidate_label") or "").strip():
        return "INVALID_PAYLOAD", "RENAME requires candidate_label"
    if action == "SPLIT":
        groups = value.get("groups")
        if not isinstance(groups, list) or len(groups) < 2:
            return "INVALID_PAYLOAD", "SPLIT requires at least two groups"
        members: list[str] = []
        for group in groups:
            if not isinstance(group, dict) or not str(group.get("label") or "").strip():
                return "INVALID_PAYLOAD", "each SPLIT group requires a label"
            group_members = group.get("member_evidence_ids")
            if not isinstance(group_members, list) or not group_members:
                return "INVALID_PAYLOAD", "each SPLIT group requires members"
            members.extend(str(item) for item in group_members)
        undecided = value.get("undecided_evidence_ids", [])
        if not isinstance(undecided, list):
            return "INVALID_PAYLOAD", "undecided_evidence_ids must be a list"
        members.extend(str(item) for item in undecided)
        if len(members) != len(set(members)):
            return "DUPLICATE_MEMBER", "SPLIT members must not repeat"
        if set(members) != known:
            return "INCOMPLETE_SPLIT", "SPLIT groups and undecided members must cover the Pack"
    if action == "PARENT_CHILD":
        required = ("parent_label", "child_label", "member_evidence_ids")
        if any(not value.get(key) for key in required):
            return "INVALID_PAYLOAD", "PARENT_CHILD payload is incomplete"
    if action == "FACET":
        required = ("base_label", "dimension", "value", "member_evidence_ids")
        if any(not value.get(key) for key in required):
            return "INVALID_PAYLOAD", "FACET payload is incomplete"
    if action == "ABSTAIN":
        missing = value.get("missing_evidence")
        if not isinstance(missing, list) or not missing:
            return "INVALID_PAYLOAD", "ABSTAIN requires missing_evidence"
    return None


def _referenced_evidence_ids(value: dict[str, object]) -> set[str]:
    ids = set()
    for key in (
        "evidence_ids",
        "counterevidence_ids",
        "member_evidence_ids",
        "undecided_evidence_ids",
    ):
        item = value.get(key, [])
        if isinstance(item, list):
            ids.update(str(entry) for entry in item)
    groups = value.get("groups", [])
    if isinstance(groups, list):
        for group in groups:
            if isinstance(group, dict) and isinstance(group.get("member_evidence_ids"), list):
                ids.update(str(entry) for entry in group["member_evidence_ids"])
    return ids


def _write_cache(
    cache_dir: Path,
    pack: dict[str, object],
    response: dict[str, object],
    model_id: str,
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(cache_dir, pack, model_id)
    path.write_text(_pretty_json(response), encoding="utf-8")


def _read_cache(
    cache_dir: Path, pack: dict[str, object], model_id: str
) -> dict[str, object] | None:
    path = _cache_path(cache_dir, pack, model_id)
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"cached response {path} must be a JSON object")
    return value


def _cache_path(
    cache_dir: Path, pack: dict[str, object], model_id: str
) -> Path:
    key = _sha256_text(
        "|".join(
            [
                str(pack["pack_hash"]),
                PROMPT_VERSION,
                RESPONSE_SCHEMA_VERSION,
                model_id,
            ]
        )
    )
    return cache_dir / f"{key}.json"


def _object_urls(
    packs: list[dict[str, object]], source_panorama_root: str | Path | None
) -> dict[str, str]:
    if not source_panorama_root:
        return {}
    from .render import _slug

    root = Path(source_panorama_root) / "objects"
    asset_ids = {
        str(evidence.get("asset_id") or "")
        for pack in packs
        for evidence in pack.get("evidence", [])
    }
    result = {}
    for asset_id in asset_ids:
        target = (root / f"{_slug(asset_id)}.html").resolve()
        if target.exists():
            result[asset_id] = target.as_uri()
    return result


def _review_html(
    summaries: list[dict[str, object]], fields: list[dict[str, object]]
) -> str:
    summary_json = _json_for_script(summaries)
    field_json = _json_for_script(fields)
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>字段概念 LLM 辅助审阅</title>
<style>:root{{font-family:Arial,"Microsoft YaHei",sans-serif;color:#25324a;background:#f6f8fb}}*{{box-sizing:border-box}}body{{margin:0}}main{{max-width:1450px;margin:auto;padding:20px}}.warning,.panel{{background:#fff;border:1px solid #d8deea;border-radius:9px;padding:14px;margin-bottom:14px}}.warning{{background:#fff7da;border-color:#dfbd56}}.grid{{display:grid;grid-template-columns:minmax(300px,.8fr) minmax(500px,1.6fr);gap:14px}}button{{cursor:pointer}}.item{{display:block;width:100%;text-align:left;background:#fff;border:1px solid #d8deea;border-radius:7px;padding:10px;margin:7px 0}}.item:hover{{border-color:#4777c7}}.badge{{display:inline-block;font-size:12px;background:#edf2f8;border-radius:12px;padding:2px 7px;margin:2px}}.candidate{{color:#9b4b00}}.field-card{{border-top:1px solid #e4e8ef;padding:10px 0}}.field-name{{font-family:Consolas,monospace;font-weight:bold}}.table-link{{color:#265eae}}.pager{{display:flex;gap:8px;align-items:center;margin-top:10px}}.muted{{color:#667085}}pre{{white-space:pre-wrap;word-break:break-word;background:#f7f8fa;padding:10px;border-radius:6px;max-height:280px;overflow:auto}}@media(max-width:850px){{.grid{{grid-template-columns:1fr}}}}</style></head>
<body><main><h1>基线与 LLM 修订候选</h1><div class="warning"><strong>LLM 结果始终是 CANDIDATE。</strong> 页面不会覆盖确定性 V1；关系、命名和拆分仍需人工决定。</div><div class="grid"><section class="panel"><h2>疑难概念簇</h2><div id="items"></div></section><section class="panel"><h2 id="title">请选择概念</h2><div id="detail" class="muted">按需加载候选与字段，不预渲染全量字段。</div><div id="fields"></div><div id="pager" class="pager"></div></section></div></main>
<script id="summary-data" type="application/json">{summary_json}</script><script id="field-data" type="application/json">{field_json}</script><script>
const FIELD_PAGE_SIZE=50;const summaries=JSON.parse(document.getElementById('summary-data').textContent);document.getElementById('summary-data').remove();let rawFields=document.getElementById('field-data').textContent;document.getElementById('field-data').remove();
const workerSource=`let rows=[];self.onmessage=e=>{{const m=e.data;if(m.type==='init'){{rows=JSON.parse(m.raw);self.postMessage({{type:'ready'}});return}}if(m.type==='page'){{const all=rows.filter(row=>row.pack===m.pack);const start=m.page*m.size;self.postMessage({{type:'page',request:m.request,total:all.length,rows:all.slice(start,start+m.size)}})}}}}`;const workerUrl=URL.createObjectURL(new Blob([workerSource],{{type:'text/javascript'}}));const worker=new Worker(workerUrl);URL.revokeObjectURL(workerUrl);worker.postMessage({{type:'init',raw:rawFields}});rawFields=null;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));let selected=null,page=0,request=0;
document.getElementById('items').innerHTML=summaries.map((row,index)=>`<button class="item" data-index="${{index}}"><strong>${{esc(row.concept.label)}}</strong><br><span class="badge">${{esc(row.validation)}}</span><span class="badge candidate">${{esc(row.action||'等待响应')}}</span><span class="muted">${{esc(row.reasons.join(' / '))}}</span></button>`).join('')||'<div class="muted">没有入选 Pack</div>';
function select(index){{selected=summaries[index];page=0;document.getElementById('title').textContent=selected.concept.label;document.getElementById('detail').innerHTML=`<div><span class="badge">基线 ${{esc(selected.concept.label)}}</span><span class="badge candidate">候选 ${{esc(selected.action||'PENDING')}}</span><span class="badge">${{esc(selected.status)}}</span></div><p><strong>选择原因：</strong>${{esc(selected.reasons.join(' / '))}}</p><pre>${{esc(JSON.stringify(selected.candidate||selected.errors,null,2))}}</pre>`;load()}}
function load(){{if(!selected)return;worker.postMessage({{type:'page',pack:selected.pack,page,size:FIELD_PAGE_SIZE,request:++request}})}}
worker.onmessage=e=>{{const m=e.data;if(m.type!=='page'||m.request!==request)return;document.getElementById('fields').innerHTML=m.rows.map(row=>{{const table=row.object_url?`<a class="table-link" href="${{esc(row.object_url)}}" target="_blank" rel="noopener">${{esc(row.object_name)}}</a>`:esc(row.object_name);return `<article class="field-card"><div><span class="field-name">${{esc(row.field_name)}}</span> · ${{table}}</div><div>${{esc(row.field_comment||'—')}}</div><div><span class="badge">${{esc(row.sample_role)}}</span><span class="badge">类型提示 ${{esc(row.data_type||'未知')}}</span><span class="badge">证据 ${{esc(row.evidence_id)}}</span></div></article>`}}).join('')||'<div class="muted">没有字段</div>';const pages=Math.max(1,Math.ceil(m.total/FIELD_PAGE_SIZE));document.getElementById('pager').innerHTML=m.total>FIELD_PAGE_SIZE?`<button data-delta="-1" ${{page===0?'disabled':''}}>上一页</button><span>${{page+1}} / ${{pages}}</span><button data-delta="1" ${{page+1>=pages?'disabled':''}}>下一页</button>`:''}};
document.addEventListener('click',e=>{{const item=e.target.closest('[data-index]');if(item){{select(Number(item.dataset.index));return}}const nav=e.target.closest('[data-delta]');if(nav&&!nav.disabled){{page+=Number(nav.dataset.delta);load()}}}});
</script></body></html>"""


def _prompt_instruction() -> str:
    return (
        "仅依据每个 Pack 内的 Evidence ID 审阅字段概念候选。"
        "逐 Pack 输出一行 JSON，不得调用工具或引入 Pack 外事实。"
        "无法可靠判断时使用 ABSTAIN；字段类型只是一项非权威提示。"
    )


def _response_contract() -> dict[str, object]:
    return {
        "required": [
            "pack_id",
            "pack_hash",
            "action",
            "evidence_ids",
            "counterevidence_ids",
            "rationale",
        ],
        "action_enum": sorted(ALLOWED_ACTIONS),
        "additional_action_fields": {
            "RENAME": ["candidate_label"],
            "SPLIT": ["groups", "undecided_evidence_ids"],
            "PARENT_CHILD": ["parent_label", "child_label", "member_evidence_ids"],
            "FACET": ["base_label", "dimension", "value", "member_evidence_ids"],
            "ABSTAIN": ["missing_evidence"],
        },
    }


def _signal_tokens(row: dict[str, object]) -> set[str]:
    text = _combined_text(row).upper()
    tokens = set(_WORD.findall(text.replace("_", " ")))
    compact_chinese = "".join(re.findall(r"[\u4e00-\u9fff]", text))
    tokens.update(
        f"ZH:{compact_chinese[index:index + 2]}"
        for index in range(max(0, len(compact_chinese) - 1))
    )
    return tokens


def _combined_text(row: dict[str, object]) -> str:
    return " ".join(
        str(row.get(key) or "")
        for key in ("field_name", "field_comment", "object_name")
    )


def _equivalent_candidate_label(left: str, right: str) -> bool:
    """Treat punctuation/unit-marker formatting variants as duplicate labels."""

    def normalized(value: str) -> str:
        text = unicodedata.normalize("NFKC", value).casefold()
        return "".join(character for character in text if character.isalnum())

    left_value = normalized(left)
    right_value = normalized(right)
    return bool(left_value) and left_value == right_value


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _estimate_tokens(value: object, chars_per_token: float) -> int:
    return max(1, math.ceil(len(_canonical_json(value)) / chars_per_token))


def _error_row(
    line_number: int,
    error_code: str,
    message: str,
    *,
    value: dict[str, object] | None = None,
    raw: str | None = None,
) -> dict[str, object]:
    return {
        "line_number": line_number,
        "pack_id": str(value.get("pack_id") or "") if value else None,
        "error_code": error_code,
        "message": message,
        "raw": raw,
    }


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        rows.append(value)
    return rows


def _read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(_canonical_json(row) + "\n" for row in rows), encoding="utf-8"
    )


def _output_entries(root: Path, paths: list[Path]) -> list[dict[str, object]]:
    result = []
    for path in paths:
        row_count = None
        if path.suffix == ".jsonl":
            row_count = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line)
        result.append(
            {
                "relative_path": path.relative_to(root).as_posix(),
                "content_sha256": _sha256_path(path),
                "row_count": row_count,
                "status": "SUCCESS",
            }
        )
    return result


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _pretty_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _json_for_script(value: object) -> str:
    return _canonical_json(value).replace("<", "\\u003c").replace(
        ">", "\\u003e"
    ).replace("&", "\\u0026")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mapping(value: dict[str, object], key: str) -> dict[str, object]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise ValueError(f"{key} must be a mapping")
    return item


def _positive_int(value: dict[str, object], key: str, default: int) -> int:
    result = int(value.get(key, default))
    if result <= 0:
        raise ValueError(f"{key} must be positive")
    return result


def _positive_float(value: dict[str, object], key: str, default: float) -> float:
    result = float(value.get(key, default))
    if result <= 0 or not math.isfinite(result):
        raise ValueError(f"{key} must be finite and positive")
    return result


def _ratio(value: dict[str, object], key: str, default: float) -> float:
    result = float(value.get(key, default))
    if not 0 <= result <= 1 or not math.isfinite(result):
        raise ValueError(f"{key} must be between 0 and 1")
    return result
