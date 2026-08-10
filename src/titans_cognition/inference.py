"""Conservative, evidence-linked V1B structural candidates.

The rules in this module are deliberately modest. A declared key can support
technical identity and declared grain; name/comment signals can only produce
weak role candidates with explicit limitations. Unknown is represented by an
Inference Result, never by a fake candidate.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import hashlib
import json
from typing import Iterable

from .deep import (
    CASE_ID,
    FEATURE_METHOD_ID,
    FEATURE_METHOD_VERSION,
    SIMILARITY_METHOD_ID,
    SIMILARITY_METHOD_VERSION,
    TradeflowDerived,
)
from .extract import PhysicalFacts


INFERENCE_METHOD_ID = "rules.tradeflow.conservative_structural"
INFERENCE_METHOD_VERSION = "v1"


@dataclass
class TradeflowInference:
    """V1B candidate, result, and evidence rows."""

    identity_candidates: list[dict[str, object]] = field(default_factory=list)
    grain_candidates: list[dict[str, object]] = field(default_factory=list)
    field_role_candidates: list[dict[str, object]] = field(default_factory=list)
    object_role_candidates: list[dict[str, object]] = field(default_factory=list)
    relation_candidates: list[dict[str, object]] = field(default_factory=list)
    inference_results: list[dict[str, object]] = field(default_factory=list)
    evidence_items: list[dict[str, object]] = field(default_factory=list)
    candidate_evidence: list[dict[str, object]] = field(default_factory=list)


def infer_tradeflow(
    facts: PhysicalFacts,
    derived: TradeflowDerived,
    *,
    case_id: str = CASE_ID,
) -> TradeflowInference:
    """Generate the bounded V1B structural inference loop."""

    run_id = _run_id(facts)
    selected_ids = {str(row["asset_id"]) for row in derived.sample_objects}
    objects = {
        str(row["asset_id"]): row
        for row in facts.objects
        if str(row.get("asset_id")) in selected_ids
    }
    columns_by_asset = _group(facts.columns, "asset_id")
    constraints_by_asset = _group(facts.constraints, "asset_id")
    evidence_items = _physical_evidence(facts, selected_ids, case_id)
    evidence_items.extend(
        _evidence(
            "FEATURE",
            _feature_source_id(
                str(row["left_asset_id"]),
                str(row["right_asset_id"]),
            ),
            row.get("feature_breakdown"),
            "SUCCESS",
            case_id,
        )
        for row in derived.structure_similarity
    )
    evidence_by_source = {str(row["source_id"]): row for row in evidence_items}
    result = TradeflowInference(evidence_items=evidence_items)

    for asset in sorted(selected_ids):
        constraints = _successful_key_constraints(constraints_by_asset.get(asset, []))
        identity_ids: list[str] = []
        grain_ids: list[str] = []
        for constraint in constraints:
            key_kind = str(constraint["constraint_type"])
            column_ids = list(constraint.get("column_ids", []))
            key_suffix = f"{asset}|{key_kind}|{'|'.join(column_ids)}"
            identity_id = _candidate_id(run_id, "IDENTITY", key_suffix)
            grain_id = _candidate_id(run_id, "GRAIN", key_suffix)
            identity_ids.append(identity_id)
            grain_ids.append(grain_id)
            result.identity_candidates.append(
                _envelope(
                    identity_id,
                    run_id,
                    case_id,
                    asset,
                    "DECLARED",
                    None,
                    "Declared PK/UK supports a technical identity candidate; business meaning is not validated.",
                    ["data_validation_status=NOT_PERFORMED"],
                    asset_id=asset,
                    column_ids=column_ids,
                    identity_kind="TECHNICAL",
                    declared_key_kind=key_kind,
                    identity_description=f"Declared {key_kind} columns for the physical object.",
                    data_validation_status="NOT_PERFORMED",
                    method_id="rule.identity.declared_key",
                    method_version="v1",
                )
            )
            result.grain_candidates.append(
                _envelope(
                    grain_id,
                    run_id,
                    case_id,
                    asset,
                    "DECLARED",
                    None,
                    "Declared key is a structural grain candidate; row-level uniqueness was not tested.",
                    ["business rows are out of V1 scope"],
                    asset_id=asset,
                    grain_column_ids=column_ids,
                    grain_kind="DECLARED_KEY",
                    grain_description="One row may be distinguished by the declared key columns; data validation is pending.",
                    data_validation_status="NOT_PERFORMED",
                    competing_candidate_ids=[],
                    method_id="rule.grain.declared_key",
                    method_version="v1",
                )
            )
            constraint_id = str(constraint["constraint_id"])
            _link(result, identity_id, evidence_by_source, constraint_id, "SUPPORTS", "STRONG", "Declared key columns directly support the technical identity candidate.")
            _link(result, grain_id, evidence_by_source, constraint_id, "SUPPORTS", "STRONG", "Declared key columns directly support the structural grain candidate.")

        result.inference_results.append(
            _inference_result(
                run_id,
                case_id,
                "IDENTITY",
                asset,
                identity_ids,
                evidence_grade="DECLARED" if identity_ids else "INSUFFICIENT",
                reason=(
                    "Declared technical key candidate(s) available; business identity and parent identity remain unproved."
                    if identity_ids
                    else "No declared PK/UK signal; V1 does not infer business identity from names alone."
                ),
                missing=([] if identity_ids else ["CONSTRAINT", "COMMENT", "ORACLE_DEPENDENCY"]),
                next_verification=(
                    "Human review and later controlled validation of business meaning."
                    if identity_ids
                    else "Obtain reviewed business evidence or a controlled validation fixture."
                ),
            )
        )
        result.inference_results.append(
            _inference_result(
                run_id,
                case_id,
                "GRAIN",
                asset,
                grain_ids,
                evidence_grade="DECLARED" if grain_ids else "INSUFFICIENT",
                reason=(
                    "Declared key gives a structural grain candidate; row-level uniqueness is explicitly not performed."
                    if grain_ids
                    else "No declared key; structural grain is ambiguous without business rows or stronger metadata."
                ),
                missing=([] if grain_ids else ["CONSTRAINT", "DEFINITION", "FEATURE"]),
                next_verification=(
                    "Review grain interpretation and validate on an approved controlled fixture."
                    if grain_ids
                    else "Obtain a reviewed grain description or approved controlled validation fixture."
                ),
            )
        )

        field_ids = _field_role_candidates(
            result,
            run_id,
            case_id,
            asset,
            columns_by_asset.get(asset, []),
            constraints,
            evidence_by_source,
        )
        result.inference_results.extend(
            _field_results(run_id, case_id, asset, columns_by_asset.get(asset, []), field_ids)
        )

        object_ids = _object_role_candidates(
            result,
            run_id,
            case_id,
            asset,
            objects[asset],
            evidence_by_source,
        )
        result.inference_results.append(
            _inference_result(
                run_id,
                case_id,
                "OBJECT_ROLE",
                asset,
                object_ids,
                evidence_grade="WEAK" if object_ids else "INSUFFICIENT",
                reason=(
                    "Role candidates are comment/name signals only and require review."
                    if object_ids
                    else "No bounded structural or comment role signal was strong enough to publish."
                ),
                missing=(
                    []
                    if object_ids
                    else (["DEFINITION", "ORACLE_DEPENDENCY"] if objects[asset].get("object_comment") else ["COMMENT", "DEFINITION", "ORACLE_DEPENDENCY"])
                ),
                next_verification="Review comments/DDL and a known business example before accepting a role.",
            )
        )

    relation_ids = _relation_candidates(result, run_id, case_id, facts, derived, evidence_by_source, selected_ids)
    result.inference_results.append(
        _inference_result(
            run_id,
            case_id,
            "RELATION",
            case_id,
            relation_ids,
            evidence_grade="WEAK" if relation_ids else "INSUFFICIENT",
            reason=(
                "Only explicitly declared or structural candidates are retained; no business relation is asserted."
                if relation_ids
                else "No declared FK/dependency or sufficiently supported structural relation was found in this sample."
            ),
            missing=[] if relation_ids else ["ORACLE_DEPENDENCY", "SQL_LINEAGE", "CONSTRAINT"],
            next_verification="Inspect approved SQL lineage or reviewed relationship evidence.",
        )
    )
    return result


def _field_role_candidates(
    result: TradeflowInference,
    run_id: str,
    case_id: str,
    asset: str,
    columns: list[dict[str, object]],
    constraints: list[dict[str, object]],
    evidence_by_source: dict[str, dict[str, object]],
) -> dict[str, list[str]]:
    key_columns = set().union(
        *(set(row.get("column_ids", [])) for row in constraints)
    ) if constraints else set()
    ids_by_column: dict[str, list[str]] = defaultdict(list)
    for column in columns:
        column_id = str(column["column_id"])
        roles: dict[str, dict[str, object]] = {}
        if column_id in key_columns:
            roles["IDENTIFIER"] = {
                "qualifier": "declared key membership; technical signal only",
                "sources": [column_id],
            }
        for role, token in (("STATUS", "STATUS"), ("TYPE_CODE", "TYPE"), ("AMOUNT", "AMT"), ("QUANTITY", "QTY")):
            if token in str(column.get("column_name", "")).upper().split("_"):
                roles.setdefault(
                    role,
                    {
                        "qualifier": "name-only signal; business meaning not established",
                        "sources": [column_id],
                    },
                )
        for role, keywords in _COMMENT_FIELD_ROLE_SIGNALS:
            if _contains_any(column.get("column_comment"), keywords):
                spec = roles.setdefault(
                    role,
                    {
                        "qualifier": "comment signal; business meaning not independently validated",
                        "sources": [],
                    },
                )
                spec["qualifier"] = (
                    f"{spec['qualifier']}; comment signal"
                    if "comment signal" not in str(spec["qualifier"])
                    else spec["qualifier"]
                )
                spec["sources"].append(f"{column_id}:COMMENT:COLUMN")
        for role, spec in roles.items():
            qualifier = str(spec["qualifier"])
            candidate_id = _candidate_id(run_id, "FIELD_ROLE", f"{column_id}|{role}")
            ids_by_column[column_id].append(candidate_id)
            result.field_role_candidates.append(
                _envelope(
                    candidate_id,
                    run_id,
                    case_id,
                    column_id,
                    "DECLARED" if role == "IDENTIFIER" else "WEAK",
                    None,
                    f"Candidate field role {role}; {qualifier}.",
                    ["business semantics not validated in V1"],
                    column_id=column_id,
                    field_role=role,
                    role_qualifier=qualifier,
                    method_id="rule.field_role.structural_signal",
                    method_version="v1",
                )
            )
            if role == "IDENTIFIER" and column_id in spec["sources"]:
                for constraint in constraints:
                    if column_id in constraint.get("column_ids", []):
                        _link(result, candidate_id, evidence_by_source, str(constraint["constraint_id"]), "SUPPORTS", "STRONG", "Column is explicitly part of a declared key.")
            if column_id in spec["sources"] and role != "IDENTIFIER":
                _link(result, candidate_id, evidence_by_source, column_id, "SUPPORTS", "WEAK", "The role is generated from a name token and requires review.")
            if f"{column_id}:COMMENT:COLUMN" in spec["sources"]:
                _link(result, candidate_id, evidence_by_source, f"{column_id}:COMMENT:COLUMN", "SUPPORTS", "WEAK", "The role is generated from a column comment and requires review.")
    return dict(ids_by_column)


def _field_results(
    run_id: str,
    case_id: str,
    asset: str,
    columns: list[dict[str, object]],
    candidate_ids_by_column: dict[str, list[str]],
) -> list[dict[str, object]]:
    return [
        _inference_result(
            run_id,
            case_id,
            "FIELD_ROLE",
            str(column["column_id"]),
            candidate_ids_by_column.get(str(column["column_id"]), []),
            evidence_grade=(
                "WEAK"
                if candidate_ids_by_column.get(str(column["column_id"]))
                else "INSUFFICIENT"
            ),
            reason=(
                "Field role candidate(s) are linked to physical column evidence."
                if candidate_ids_by_column.get(str(column["column_id"]))
                else "No bounded field-role signal was strong enough to publish."
            ),
            missing=[] if candidate_ids_by_column.get(str(column["column_id"])) else ["FEATURE", "COMMENT"],
            next_verification="Review the field-role candidate and its evidence before publishing an outcome.",
        )
        for column in columns
    ]


def _object_role_candidates(
    result: TradeflowInference,
    run_id: str,
    case_id: str,
    asset: str,
    object_row: dict[str, object],
    evidence_by_source: dict[str, dict[str, object]],
) -> list[str]:
    comment = object_row.get("object_comment")
    ids: list[str] = []
    for role, keywords in _COMMENT_OBJECT_ROLE_SIGNALS:
        if not _contains_any(comment, keywords):
            continue
        candidate_id = _candidate_id(run_id, "OBJECT_ROLE", f"{asset}|COMMENT|{role}")
        ids.append(candidate_id)
        result.object_role_candidates.append(
            _envelope(
                candidate_id,
                run_id,
                case_id,
                asset,
                "WEAK",
                None,
                f"Object comment contains a bounded {role} signal; business role is not independently validated.",
                ["single database comment is insufficient for a confirmed business role"],
                asset_id=asset,
                object_role=role,
                role_qualifier="object_comment_keyword",
                method_id="rule.object_role.comment_signal",
                method_version="v1.1",
            )
        )
        _link(
            result,
            candidate_id,
            evidence_by_source,
            f"{asset}:COMMENT:OBJECT",
            "SUPPORTS",
            "WEAK",
            "The role candidate is based on a table comment and requires review.",
        )
    return ids


_COMMENT_OBJECT_ROLE_SIGNALS = (
    ("EVENT_TRANSACTION", ("事件", "交易", "event", "transaction")),
    ("STATE_HISTORY", ("历史", "history")),
    ("SNAPSHOT", ("当前", "快照", "snapshot", "current")),
)

_COMMENT_FIELD_ROLE_SIGNALS = (
    ("IDENTIFIER", ("标识", "编号", "代码", "identifier")),
    ("STATUS", ("状态", "status")),
    ("TYPE_CODE", ("类型", "分类", "type")),
    ("AMOUNT", ("金额", "本金", "amount")),
    ("QUANTITY", ("数量", "手数", "quantity")),
    ("TIME", ("日期", "时间", "date", "time")),
)


def _contains_any(value: object, keywords: tuple[str, ...]) -> bool:
    text = str(value or "").casefold()
    return any(keyword.casefold() in text for keyword in keywords)


def _relation_candidates(
    result: TradeflowInference,
    run_id: str,
    case_id: str,
    facts: PhysicalFacts,
    derived: TradeflowDerived,
    evidence_by_source: dict[str, dict[str, object]],
    selected_ids: set[str],
) -> list[str]:
    ids: list[str] = []
    for constraint in facts.constraints:
        source = str(constraint.get("asset_id"))
        target = constraint.get("referenced_asset_id")
        if source not in selected_ids or not target:
            continue
        if str(constraint.get("constraint_type", "")).upper() != "FOREIGN_KEY":
            continue
        candidate_id = _candidate_id(run_id, "RELATION", f"FK|{constraint['constraint_id']}")
        ids.append(candidate_id)
        result.relation_candidates.append(
            _envelope(
                candidate_id,
                run_id,
                case_id,
                source,
                "DECLARED",
                None,
                "Declared foreign key supports a structural relation candidate.",
                ["business semantics not inferred"],
                source_id=source,
                predicate="REFERENCES",
                target_id=str(target),
                relation_level="OBJECT",
                epistemic_kind="STRUCTURAL",
                generation_origin="RULE",
                direction_is_resolved=True,
                relation_qualifiers=json.dumps({"constraint_id": constraint["constraint_id"]}, sort_keys=True),
                method_id="rule.relation.declared_fk",
                method_version="v1",
            )
        )
        _link(result, candidate_id, evidence_by_source, str(constraint["constraint_id"]), "SUPPORTS", "STRONG", "Declared foreign key fixes the structural direction.")

    # Structure similarity remains a derived observation for review and sample
    # selection.  V1B does not promote it to a Relation Candidate without an
    # explicit FK, Oracle dependency, SQL lineage, or human proposal.
    return ids


def _physical_evidence(
    facts: PhysicalFacts,
    selected_ids: set[str],
    case_id: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in facts.objects:
        if str(row.get("asset_id")) in selected_ids:
            asset_id = str(row["asset_id"])
            rows.append(
                _evidence(
                    "OBJECT",
                    asset_id,
                    _summary(row),
                    row.get("extraction_status", "SUCCESS"),
                    case_id,
                )
            )
            if row.get("object_comment"):
                rows.append(
                    _evidence(
                        "COMMENT",
                        f"{asset_id}:COMMENT:OBJECT",
                        row.get("object_comment"),
                        row.get("extraction_status", "SUCCESS"),
                        case_id,
                    )
                )
    for collection, kind, key in (
        (facts.columns, "COLUMN", "column_id"),
        (facts.constraints, "CONSTRAINT", "constraint_id"),
        (facts.indexes, "INDEX", "index_id"),
    ):
        for row in collection:
            if str(row.get("asset_id")) in selected_ids:
                rows.append(_evidence(kind, str(row[key]), _summary(row), row.get("extraction_status", "SUCCESS"), case_id))
                if kind == "COLUMN" and row.get("column_comment"):
                    rows.append(
                        _evidence(
                            "COMMENT",
                            f"{row[key]}:COMMENT:COLUMN",
                            row.get("column_comment"),
                            row.get("extraction_status", "SUCCESS"),
                            case_id,
                        )
                    )
    return rows


def _evidence(evidence_type: str, source_id: str, summary: object, status: object, case_id: str) -> dict[str, object]:
    return {
        "evidence_id": f"{case_id}:EVIDENCE:{hashlib.sha256(source_id.encode()).hexdigest()[:12]}",
        "evidence_type": evidence_type,
        "source_id": source_id,
        "locator": source_id,
        "summary": str(summary or "physical metadata fact"),
        "content_hash": hashlib.sha256(json.dumps(summary, sort_keys=True, default=str).encode()).hexdigest(),
        "source_status": str(status),
    }


def _link(result: TradeflowInference, candidate_id: str, evidence_by_source: dict[str, dict[str, object]], source_id: str, stance: str, strength: str, reason: str) -> None:
    evidence = evidence_by_source.get(source_id)
    if evidence is None:
        return
    result.candidate_evidence.append(
        {
            "candidate_id": candidate_id,
            "evidence_id": evidence["evidence_id"],
            "stance": stance,
            "strength": strength,
            "reason": reason,
        }
    )


def _envelope(candidate_id: str, run_id: str, case_id: str, subject_id: str, grade: str, score: float | None, explanation: str, limitations: list[str], **extra: object) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "run_id": run_id,
        "case_id": case_id,
        "subject_id": subject_id,
        "method_id": extra.pop("method_id", INFERENCE_METHOD_ID),
        "method_version": extra.pop("method_version", INFERENCE_METHOD_VERSION),
        "evidence_grade": grade,
        "raw_method_score": score,
        "explanation": explanation,
        "limitations": limitations,
        **extra,
    }


def _inference_result(run_id: str, case_id: str, task_type: str, subject_id: str, candidate_ids: list[str], *, evidence_grade: str, reason: str, missing: list[str], next_verification: str) -> dict[str, object]:
    outcome = "UNKNOWN" if not candidate_ids else "SINGLE_CANDIDATE" if len(candidate_ids) == 1 else "COMPETING"
    return {
        "inference_result_id": _candidate_id(run_id, "RESULT", f"{task_type}|{subject_id}"),
        "run_id": run_id,
        "case_id": case_id,
        "task_type": task_type,
        "subject_id": subject_id,
        "method_id": INFERENCE_METHOD_ID,
        "method_version": INFERENCE_METHOD_VERSION,
        "evaluation_eligibility": "EVALUABLE",
        "not_evaluable_reason": None,
        "outcome": outcome,
        "candidate_ids": candidate_ids,
        "evidence_grade": evidence_grade,
        "reason": reason,
        "missing_evidence_types": missing,
        "next_verification": next_verification,
    }


def _successful_key_constraints(rows: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    return [
        row
        for row in rows
        if str(row.get("constraint_type", "")).upper() in ("PRIMARY_KEY", "UNIQUE_KEY")
        and str(row.get("extraction_status", "SUCCESS")).upper() == "SUCCESS"
    ]


def _group(rows: list[dict[str, object]], key: str) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        if row.get(key) is not None:
            grouped[str(row[key])].append(row)
    return grouped


def _candidate_id(run_id: str, kind: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"{run_id}:{kind}:{digest}"


def _run_id(facts: PhysicalFacts) -> str:
    for row in facts.objects:
        value = row.get("run_id")
        if value:
            return str(value)
    raise ValueError("physical facts contain no run_id")


def _summary(row: dict[str, object]) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)


def _feature_source_id(left: str, right: str) -> str:
    return f"FEATURE:{hashlib.sha256(f'{left}|{right}'.encode()).hexdigest()[:12]}"
