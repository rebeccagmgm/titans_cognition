"""Deterministic P0/P1 field evidence preparation for frozen metadata facts.

This module is intentionally metadata-only.  It reads frozen JSON physical facts,
preserves their raw strings, and writes one non-semantic evidence pack per physical
column.  It never opens a database connection or calls a model provider.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unicodedata
from typing import Iterable, Mapping, Sequence

import yaml


BLOCK_NAMES = (
    "physical_identity",
    "raw_physical_fact",
    "preparation_disposition",
    "normalized_lexical_form",
    "tokens",
    "protected_phrases",
    "abbreviation_observations",
    "generic_attribute_observations",
    "technical_observations",
    "contextual_evidence",
    "candidate_qualifier_observations",
    "conflicts",
    "unresolved_items",
    "applied_rule_ids",
    "provenance",
    "evidence_status",
)

CURRENCY_BASIS_VALUES = (
    "ORIGINAL_CURRENCY",
    "LOCAL_CURRENCY",
    "UNDERLYING_CURRENCY",
    "SETTLEMENT_CURRENCY",
)

QUALIFIER_VALUES = {
    "position_side": ("LONG", "SHORT"),
    "trade_side": ("BUY", "SELL"),
    "cashflow_direction": ("PAY", "RECEIVE"),
    "variability": ("DYNAMIC", "FIXED"),
    "currency_basis": CURRENCY_BASIS_VALUES,
}

_NUMERIC_SUFFIX = re.compile(r"\d+$")
_LETTER_NUMBER_BOUNDARY = re.compile(r"(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])")
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_TOKEN_PATTERN = re.compile(r"[A-Za-z]+|\d+|[\u3400-\u9fff]+")
_SEPARATORS = re.compile(r"[_\-./\\:|]+")
_PUNCTUATION = re.compile(r"[()（）\[\]{}，,；;、]+")
_WHITESPACE = re.compile(r"\s+")
_SUSPICIOUS_MOJIBAKE = re.compile(r"(?:\ufffd|锟斤拷|Ã.|Â.|æ[^\u3400-\u9fff])")

_EVIDENCE_STATUSES = {
    "SUPPORT",
    "CONTRADICT",
    "CONTEXT_ONLY",
    "NOT_APPLICABLE",
    "NOT_OBSERVED",
}

_GENERIC_ATTRIBUTES = {
    "IDENTIFIER_SHAPE",
    "NUMERIC_SHAPE",
    "CODE_SHAPE",
    "NAME_VARIANT_OBSERVATION",
    "BUSINESS_OBJECT_STATE",
    "CLASSIFICATION",
    "MEASURE",
    "QUANTITY",
    "RATE",
    "TIME",
    "CURRENCY",
    "DESCRIPTION",
    "SOURCE_TARGET_TERM",
}

_TECHNICAL_CLASSES = {
    "TECHNICAL_IDENTIFIER",
    "AUDIT_ACTOR",
    "AUDIT_TIME",
    "INGESTION_METADATA",
    "BATCH_METADATA",
    "LINEAGE_METADATA",
    "EXTENSION_SLOT",
    "SOFT_DELETE",
    "VERSION_CONTROL",
    "UNRESOLVED_TECHNICAL",
}

_UNRESOLVED_CODES = {
    "NOT_OBSERVED",
    "UNRECOGNIZED_ABBREVIATION",
    "UNBOUND_ATTRIBUTE_OBSERVATION",
    "UNRESOLVED_PROTECTED_PHRASE",
    "UNRESOLVED_TECHNICAL",
    "SEMANTIC_LAYER_REQUIRED",
}


@dataclass(frozen=True)
class RuleDefinition:
    """One unique rule declared by the frozen preparation contract."""

    rule_id: str
    status: str


@dataclass(frozen=True)
class SourceArtifact:
    """Frozen physical-fact source and its required provenance fields."""

    path: Path
    display_path: str
    sha256: str
    locator: str
    evidence_role: str


@dataclass(frozen=True)
class FieldEvidenceConfig:
    """Validated configuration for a single bounded preparation run."""

    profile_path: Path
    profile_id: str
    profile_sha256: str
    schema_name: str
    object_types: tuple[str, ...]
    expected_object_count: int
    expected_physical_column_count: int
    physical_column_id_scope: str
    downstream_workset_id: str
    exclude_object_name_numeric_suffix: bool
    expected_prepared_count: int
    expected_excluded_count: int
    expected_deferred_count: int
    columns_source: SourceArtifact
    objects_source: SourceArtifact
    contract_path: Path
    contract_display_path: str
    contract_sha256: str
    schema_path: Path
    schema_display_path: str
    schema_id: str
    gold_set_path: Path
    gold_set_display_path: str
    gold_set_sha256: str
    rule_registry: tuple[RuleDefinition, ...]
    qualifier_values: Mapping[str, tuple[str, ...]]

    @property
    def columns_path(self) -> Path:
        return self.columns_source.path

    @property
    def objects_path(self) -> Path:
        return self.objects_source.path

    @property
    def rule_ids(self) -> frozenset[str]:
        return frozenset(item.rule_id for item in self.rule_registry)


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    return {str(key): item for key, item in value.items()}


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _nonnegative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _project_root(profile_path: Path) -> Path:
    for parent in (profile_path.parent, *profile_path.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


def _resolve_path(root: Path, value: object, label: str) -> tuple[Path, str]:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty path")
    display = value.replace("\\", "/")
    path = Path(value)
    return (path if path.is_absolute() else root / path).resolve(), display


def _collect_rules(value: object) -> list[RuleDefinition]:
    rules: list[RuleDefinition] = []

    def visit(node: object) -> None:
        if isinstance(node, dict):
            rule_id = node.get("rule_id")
            if isinstance(rule_id, str):
                rules.append(
                    RuleDefinition(
                        rule_id=rule_id, status=str(node.get("status", "UNSPECIFIED"))
                    )
                )
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return rules


def _load_source_artifact(
    root: Path,
    payload: object,
    label: str,
    expected_role: str,
) -> SourceArtifact:
    row = _mapping(payload, label)
    path, display = _resolve_path(root, row.get("path"), f"{label}.path")
    sha256 = str(row.get("sha256", "")).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError(f"{label}.sha256 must be a lower-case SHA-256")
    locator = str(row.get("locator", ""))
    role = str(row.get("evidence_role", ""))
    if not locator:
        raise ValueError(f"{label}.locator is required")
    if role != expected_role:
        raise ValueError(f"{label}.evidence_role must be {expected_role}")
    return SourceArtifact(path, display, sha256, locator, role)


def load_field_evidence_config(path: str | Path) -> FieldEvidenceConfig:
    """Load the profile and freeze its contract, rule, and enumeration boundaries."""

    profile_path = Path(path).resolve()
    source_text = profile_path.read_text(encoding="utf-8")
    payload = _mapping(yaml.safe_load(source_text), "profile")
    if payload.get("version") != "field-evidence-preparation-v1":
        raise ValueError(
            "field evidence profile version must be field-evidence-preparation-v1"
        )
    root = _project_root(profile_path)
    scope = _mapping(payload.get("scope"), "scope")
    workset = _mapping(scope.get("downstream_workset"), "scope.downstream_workset")
    sources = _mapping(payload.get("source_artifacts"), "source_artifacts")
    contract = _mapping(payload.get("contract"), "contract")
    schema = _mapping(payload.get("schema"), "schema")
    gold = _mapping(payload.get("gold_set"), "gold_set")
    qualifier_values = _mapping(payload.get("qualifier_values"), "qualifier_values")

    contract_path, contract_display = _resolve_path(
        root, contract.get("path"), "contract.path"
    )
    contract_hash = str(contract.get("sha256", "")).lower()
    if _sha256_path(contract_path) != contract_hash:
        raise ValueError("field evidence contract hash mismatch")
    contract_payload = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    rules = _collect_rules(contract_payload)
    expected_rule_count = _positive_int(
        contract.get("expected_unique_rule_ids"), "contract.expected_unique_rule_ids"
    )
    rule_ids = [item.rule_id for item in rules]
    if (
        len(rule_ids) != expected_rule_count
        or len(set(rule_ids)) != expected_rule_count
    ):
        duplicates = sorted(
            rule_id for rule_id, count in Counter(rule_ids).items() if count > 1
        )
        raise ValueError(
            "rule registry does not contain exactly "
            f"{expected_rule_count} unique ids; duplicates={duplicates}"
        )

    schema_path, schema_display = _resolve_path(root, schema.get("path"), "schema.path")
    schema_payload = json.loads(schema_path.read_text(encoding="utf-8"))
    if schema_payload.get("$id") != schema.get("schema_id"):
        raise ValueError("field evidence schema id mismatch")
    required_blocks = tuple(schema_payload.get("required", ()))
    expected_block_count = _positive_int(
        schema.get("expected_block_count"), "schema.expected_block_count"
    )
    if required_blocks != BLOCK_NAMES or len(required_blocks) != expected_block_count:
        raise ValueError(
            "field evidence schema must require the fixed 16 blocks in order"
        )

    parsed_qualifiers: dict[str, tuple[str, ...]] = {}
    for dimension, expected in QUALIFIER_VALUES.items():
        values = qualifier_values.get(dimension)
        if not isinstance(values, list) or not all(
            isinstance(item, str) for item in values
        ):
            raise ValueError(f"qualifier_values.{dimension} must be a string list")
        parsed = tuple(values)
        if parsed != expected:
            raise ValueError(
                f"qualifier_values.{dimension} must be complete and ordered: {expected}"
            )
        parsed_qualifiers[dimension] = parsed
    if set(qualifier_values) != set(QUALIFIER_VALUES):
        raise ValueError("qualifier_values contains an unknown or missing dimension")

    gold_path, gold_display = _resolve_path(root, gold.get("path"), "gold_set.path")
    gold_hash = str(gold.get("sha256", "")).lower()
    if gold_path.exists() and _sha256_path(gold_path) != gold_hash:
        raise ValueError("field evidence gold set hash mismatch")
    if gold.get("formal_gate_status") != "NOT_CLAIMED":
        raise ValueError("Suite A formal status must remain NOT_CLAIMED")

    object_types = scope.get("object_types")
    if not isinstance(object_types, list) or not object_types:
        raise ValueError("scope.object_types must be a non-empty list")
    expected_columns = _positive_int(
        scope.get("expected_physical_column_count"),
        "scope.expected_physical_column_count",
    )
    expected_prepared = _nonnegative_int(
        scope.get("expected_prepared_count"), "scope.expected_prepared_count"
    )
    expected_excluded = _nonnegative_int(
        scope.get("expected_excluded_count"), "scope.expected_excluded_count"
    )
    expected_deferred = _nonnegative_int(
        scope.get("expected_deferred_count"), "scope.expected_deferred_count"
    )
    if expected_prepared + expected_excluded + expected_deferred != expected_columns:
        raise ValueError("configured preparation disposition counts do not close")

    return FieldEvidenceConfig(
        profile_path=profile_path,
        profile_id=str(payload.get("profile_id", "")),
        profile_sha256=_sha256_text(source_text),
        schema_name=str(scope.get("schema_name", "")).upper(),
        object_types=tuple(str(item).upper() for item in object_types),
        expected_object_count=_positive_int(
            scope.get("expected_object_count"), "scope.expected_object_count"
        ),
        expected_physical_column_count=expected_columns,
        physical_column_id_scope=str(scope.get("physical_column_id_scope", "")),
        downstream_workset_id=str(workset.get("id", "")),
        exclude_object_name_numeric_suffix=bool(
            workset.get("exclude_object_name_numeric_suffix", False)
        ),
        expected_prepared_count=expected_prepared,
        expected_excluded_count=expected_excluded,
        expected_deferred_count=expected_deferred,
        columns_source=_load_source_artifact(
            root,
            sources.get("columns"),
            "source_artifacts.columns",
            "COLUMN_PHYSICAL_FACT",
        ),
        objects_source=_load_source_artifact(
            root,
            sources.get("objects"),
            "source_artifacts.objects",
            "OBJECT_PHYSICAL_FACT",
        ),
        contract_path=contract_path,
        contract_display_path=contract_display,
        contract_sha256=contract_hash,
        schema_path=schema_path,
        schema_display_path=schema_display,
        schema_id=str(schema.get("schema_id")),
        gold_set_path=gold_path,
        gold_set_display_path=gold_display,
        gold_set_sha256=gold_hash,
        rule_registry=tuple(rules),
        qualifier_values=parsed_qualifiers,
    )


def _suspicious_text(value: str) -> bool:
    return bool(_SUSPICIOUS_MOJIBAKE.search(value)) or any(
        unicodedata.category(char) == "Cc" and char not in "\t\r\n" for char in value
    )


def _normalize(value: str) -> tuple[str, tuple[str, ...], bool, bool]:
    rules = ["GEN-NORM-001", "GEN-NORM-002"]
    normalized = unicodedata.normalize("NFKC", value)
    if normalized != value:
        rules.append("GEN-NORM-003")
    if _CAMEL_BOUNDARY.search(normalized):
        normalized = _CAMEL_BOUNDARY.sub(" ", normalized)
    normalized = normalized.upper()
    rules.append("GEN-NORM-004")
    if normalized != normalized.strip() or re.search(r"\s{2,}", normalized):
        rules.append("GEN-NORM-005")
    if _PUNCTUATION.search(normalized):
        rules.append("GEN-NORM-006")
    if _SEPARATORS.search(normalized):
        rules.append("GEN-NORM-007")
    if re.search(r"[()（）\[\]{}]", value):
        rules.append("GEN-NORM-008")
    if _LETTER_NUMBER_BOUNDARY.search(normalized):
        rules.append("GEN-NORM-009")
    if re.search(r"(?:^|_)(?:LEG)?[IVX]+(?:_|$)", normalized):
        rules.append("GEN-NORM-010")
    review_required = _suspicious_text(value)
    if review_required:
        rules.append("GEN-NORM-011")
    normalized = _LETTER_NUMBER_BOUNDARY.sub(" ", normalized)
    normalized = _SEPARATORS.sub(" ", normalized)
    normalized = _PUNCTUATION.sub(" ", normalized)
    normalized = _WHITESPACE.sub(" ", normalized).strip()
    information_loss = any(
        rule in rules for rule in ("GEN-NORM-005", "GEN-NORM-006", "GEN-NORM-008")
    )
    return normalized, tuple(dict.fromkeys(rules)), information_loss, review_required


_PROTECTED_PHRASES = (
    ("SHORT_DYNAMIC_NOTIONAL", "TF-PHRASE-001", ("GEN-PROHIBIT-001",)),
    ("LONG_DYNAMIC_NOTIONAL", "TF-PHRASE-001", ("GEN-PROHIBIT-001",)),
    ("TARGET_CTPTY", "TF-PHRASE-002", ("GEN-PROHIBIT-002",)),
    ("SOURCE_CTPTY", "TF-PHRASE-002", ("GEN-PROHIBIT-002",)),
    ("UPDATED_DATETIME", "GEN-PHRASE-004", ("GEN-PROHIBIT-007",)),
    ("PUSH_BATCH_NO", "GEN-PHRASE-004", ("GEN-PROHIBIT-007",)),
    ("SHORT_NAME", "GEN-PHRASE-001", ("GEN-PROHIBIT-001",)),
    ("LONG_NAME", "GEN-PHRASE-001", ("GEN-PROHIBIT-001",)),
    ("SHORT_DESC", "GEN-PHRASE-001", ("GEN-PROHIBIT-001",)),
    ("LONG_DESC", "GEN-PHRASE-001", ("GEN-PROHIBIT-001",)),
    ("SOURCE_SYSTEM", "GEN-PHRASE-002", ("GEN-PROHIBIT-002", "GEN-PROHIBIT-007")),
    ("TARGET_ACCOUNT", "GEN-PHRASE-002", ("GEN-PROHIBIT-002",)),
    ("SOURCE_TYPE", "GEN-PHRASE-002", ("GEN-PROHIBIT-002",)),
    ("SOURCE_ID", "GEN-PHRASE-002", ("GEN-PROHIBIT-002",)),
    ("BUSINESS_TYPE", "GEN-PHRASE-003", ("GEN-PROHIBIT-003",)),
    ("CONTRACT_ID", "GEN-PHRASE-003", ("GEN-PROHIBIT-003",)),
    ("ORDER_ID", "GEN-PHRASE-003", ("GEN-PROHIBIT-003",)),
    ("TRADE_ID", "GEN-PHRASE-003", ("GEN-PROHIBIT-003",)),
    ("CREATED_BY", "GEN-PHRASE-004", ("GEN-PROHIBIT-007",)),
    ("LEG_ID", "GEN-PHRASE-003", ("GEN-PROHIBIT-003",)),
)


def _protected_spans(
    column_name: str,
) -> list[tuple[int, int, str, str, tuple[str, ...]]]:
    comparison = unicodedata.normalize("NFKC", column_name).upper()
    candidates: list[tuple[int, int, str, str, tuple[str, ...]]] = []
    for phrase, rule_id, suppressed in _PROTECTED_PHRASES:
        start = 0
        while True:
            index = comparison.find(phrase, start)
            if index < 0:
                break
            end = index + len(phrase)
            left_ok = index == 0 or not comparison[index - 1].isalnum()
            right_ok = end == len(comparison) or not comparison[end].isalnum()
            if left_ok and right_ok:
                candidates.append((index, end, phrase, rule_id, suppressed))
            start = index + 1
    selected: list[tuple[int, int, str, str, tuple[str, ...]]] = []
    occupied: set[int] = set()
    for candidate in sorted(
        candidates, key=lambda row: (row[0], -(row[1] - row[0]), row[2])
    ):
        start, end = candidate[:2]
        if any(position in occupied for position in range(start, end)):
            continue
        selected.append(candidate)
        occupied.update(range(start, end))
    return sorted(selected)


def _tokenize(
    physical_column_id: str,
    column_name: str,
    column_comment: str | None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], set[str]]:
    protected_spans = _protected_spans(column_name)
    tokens: list[dict[str, object]] = []
    protected: list[dict[str, object]] = []
    applied: set[str] = {
        "GEN-TOKEN-001",
        "GEN-TOKEN-002",
        "GEN-TOKEN-005",
        "GEN-TOKEN-006",
        "GEN-TOKEN-008",
    }

    segments: list[tuple[int, int, str, str]] = []
    for start, end, phrase, rule_id, suppressed in protected_spans:
        segments.append((start, end, phrase, "GEN-TOKEN-001"))
        protected.append(
            {
                "physical_column_id": physical_column_id,
                "phrase": phrase,
                "source_kind": "COLUMN_NAME",
                "source_span": [start, end],
                "source_ref": f"column_name:{physical_column_id}",
                "rule_id": rule_id,
                "suppressed_rule_ids": list(suppressed),
                "status": "CANDIDATE" if column_comment is not None else "UNRESOLVED",
            }
        )
        applied.add(rule_id)
        applied.update(suppressed)

    occupied = {
        position for start, end, *_ in protected_spans for position in range(start, end)
    }
    for match in _TOKEN_PATTERN.finditer(column_name):
        if any(position in occupied for position in range(match.start(), match.end())):
            continue
        raw = match.group(0)
        normalized = unicodedata.normalize("NFKC", raw).upper()
        pieces = _LETTER_NUMBER_BOUNDARY.sub(" ", normalized).split()
        if len(pieces) == 1:
            token_rule = (
                "GEN-TOKEN-007"
                if pieces[0]
                in {"ID", "NO", "NUM", "CODE", "TYPE", "STATUS", "DATE", "TIME", "AMT"}
                else "GEN-TOKEN-002"
            )
            segments.append((match.start(), match.end(), pieces[0], token_rule))
            applied.add(token_rule)
        else:
            cursor = match.start()
            for piece in pieces:
                piece_start = column_name.upper().find(piece, cursor, match.end())
                piece_end = piece_start + len(piece)
                segments.append((piece_start, piece_end, piece, "GEN-TOKEN-006"))
                cursor = piece_end
                applied.add("GEN-TOKEN-006")

    for index, (start, end, normalized, rule_id) in enumerate(sorted(segments), 1):
        tokens.append(
            {
                "physical_column_id": physical_column_id,
                "token_id": f"{physical_column_id}:TOKEN:{index:03d}",
                "raw_text": column_name[start:end],
                "normalized_text": normalized,
                "source_kind": "COLUMN_NAME",
                "source_span": [start, end],
                "source_ref": f"column_name:{physical_column_id}",
                "rule_id": rule_id,
            }
        )
    return tokens, protected, applied


_ABBREVIATIONS = {
    "AMT": ("AMOUNT", "GEN-ABBR-001"),
    "QTY": ("QUANTITY", "GEN-ABBR-001"),
    "CCY": ("CURRENCY", "GEN-ABBR-001"),
    "DT": ("DATE", "GEN-ABBR-001"),
    "ID": ("IDENTIFIER_SHAPE", "GEN-ABBR-002"),
    "NO": ("IDENTIFIER_SHAPE", "GEN-ABBR-002"),
    "NUM": ("NUMERIC_SHAPE", "GEN-ABBR-002"),
    "CODE": ("CODE_SHAPE", "GEN-ABBR-002"),
    "CTPTY": ("counterparty-candidate", "TF-ABBR-001"),
    "TRD": ("trade-candidate", "TF-ABBR-001"),
    "POS": ("position-candidate", "TF-ABBR-001"),
    "MARGIN": ("margin-candidate", "TF-ABBR-002"),
    "NOTIONAL": ("notional-candidate", "TF-ABBR-002"),
}

_COMMON_TOKENS = {
    "ACCOUNT",
    "AMOUNT",
    "BUSINESS",
    "CONTRACT",
    "CREATED",
    "CURRENCY",
    "DATA",
    "DATE",
    "DATETIME",
    "DESC",
    "DESCRIPTION",
    "DYNAMIC",
    "EVENT",
    "FIXED",
    "LEG",
    "LONG",
    "NAME",
    "ORDER",
    "POSITION",
    "PUSH",
    "RATE",
    "SHORT",
    "SOURCE",
    "STATUS",
    "SYSTEM",
    "TARGET",
    "TIME",
    "TOTAL",
    "TRADE",
    "TYPE",
    "UPDATED",
}


def _abbreviation_observations(
    physical_column_id: str,
    tokens: Sequence[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], set[str]]:
    observations: list[dict[str, object]] = []
    unresolved: list[dict[str, object]] = []
    applied: set[str] = set()
    for token in tokens:
        value = str(token["normalized_text"])
        if "_" in value or value.isdigit():
            continue
        definition = _ABBREVIATIONS.get(value)
        if definition:
            expansion, rule_id = definition
            observations.append(
                {
                    "physical_column_id": physical_column_id,
                    "token_id": token["token_id"],
                    "expansion_candidate": expansion,
                    "status": "CANDIDATE",
                    "source_kind": token["source_kind"],
                    "source_span": token["source_span"],
                    "source_ref": token["source_ref"],
                    "rule_id": rule_id,
                }
            )
            applied.add(rule_id)
        elif 2 <= len(value) <= 5 and value.isalpha() and value not in _COMMON_TOKENS:
            observations.append(
                {
                    "physical_column_id": physical_column_id,
                    "token_id": token["token_id"],
                    "expansion_candidate": None,
                    "status": "UNRECOGNIZED_ABBREVIATION",
                    "source_kind": token["source_kind"],
                    "source_span": token["source_span"],
                    "source_ref": token["source_ref"],
                    "rule_id": "GEN-ABBR-003",
                }
            )
            unresolved.append(
                {
                    "physical_column_id": physical_column_id,
                    "code": "UNRECOGNIZED_ABBREVIATION",
                    "reason": f"Token {value} is retained without an asserted expansion.",
                    "source_kind": token["source_kind"],
                    "source_span": token["source_span"],
                    "source_ref": token["source_ref"],
                    "rule_id": "GEN-UNKNOWN-002",
                    "required_next_evidence": [
                        "versioned abbreviation registry or semantic review"
                    ],
                }
            )
            applied.update(("GEN-ABBR-003", "GEN-UNKNOWN-002"))
    return observations, unresolved, applied


def _object_anchor(column_name: str, column_comment: str | None) -> str | None:
    text = f"{column_name} {column_comment or ''}".upper()
    anchors = (
        (r"(?:CTPTY|交易对手|客户)", "COUNTERPARTY_OR_CUSTOMER_CANDIDATE"),
        (r"(?:ORDER|委托|指令)", "ORDER_CANDIDATE"),
        (r"(?:TRADE|TRD|交易|成交)", "TRADE_CANDIDATE"),
        (r"(?:CONTRACT|合约|合同)", "CONTRACT_CANDIDATE"),
        (r"(?:POSITION|POS|持仓)", "POSITION_CANDIDATE"),
        (r"(?:MARGIN|保证金)", "MARGIN_CANDIDATE"),
        (r"(?:NOTIONAL|名义本金)", "NOTIONAL_CANDIDATE"),
    )
    for pattern, anchor in anchors:
        if re.search(pattern, text):
            return anchor
    return None


def _technical_observations(
    physical_column_id: str,
    column_name: str,
    object_name: str,
) -> tuple[list[dict[str, object]], set[str]]:
    name = unicodedata.normalize("NFKC", column_name).upper()
    context = unicodedata.normalize("NFKC", object_name).upper()
    result: tuple[str, str, str, list[str]] | None = None
    if re.search(r"(?:^|_)(?:CREATED_BY|UPDATED_BY)(?:_|$)", name):
        result = ("AUDIT_ACTOR", "CANDIDATE", "GEN-TECH-001", [])
    elif re.search(r"(?:CREATED_TIME|UPDATED_TIME|UPDATED_DATETIME)", name):
        result = ("AUDIT_TIME", "CANDIDATE", "GEN-TECH-002", [])
    elif re.search(r"(?:DELETED|DELETE_FLAG)", name):
        result = ("SOFT_DELETE", "CANDIDATE", "GEN-TECH-003", [])
    elif re.search(r"(?:VERSION|OPT_LOCK)", name):
        result = ("VERSION_CONTROL", "CANDIDATE", "GEN-TECH-004", [])
    elif re.search(r"(?:PUSH_BATCH_NO|BATCH_NO)", name):
        result = ("BATCH_METADATA", "CANDIDATE", "GEN-TECH-005", [])
    elif re.search(r"(?:SYNC|PUSH_STATUS|ETL_TIME|DATA_SOURCE|SOURCE_SYSTEM)", name):
        result = ("INGESTION_METADATA", "CANDIDATE", "GEN-TECH-006", [])
    elif re.search(r"(?:SOURCE|TARGET)", name) and re.search(
        r"(?:MAPPING|CONFIG|INGEST|ETL)", context
    ):
        result = (
            "LINEAGE_METADATA",
            "CANDIDATE",
            "GEN-TECH-007",
            ["explicit mapping or ingestion object context"],
        )
    elif re.search(r"(?:UUID|ROW_ID|SEQ_NO|PARTITION_DATE)", name):
        result = ("TECHNICAL_IDENTIFIER", "CANDIDATE", "GEN-TECH-008", [])
    elif name in {"ID", "NUM"} and re.search(r"(?:AUDIT|LOG)", context):
        result = (
            "TECHNICAL_IDENTIFIER",
            "UNRESOLVED",
            "GEN-TECH-008",
            ["declared constraint or semantic object identity"],
        )
    elif re.search(r"(?:^|_)(?:EXT|EXTENSION|RESERVED|REMARK\d+)(?:_|$)", name):
        result = (
            "EXTENSION_SLOT",
            "CANDIDATE",
            "GEN-TECH-009",
            ["explicit extension-slot context"],
        )
    if result is None and re.fullmatch(r"(?:SOURCE|TARGET|SEQ_NO|NUM)", name):
        result = (
            "UNRESOLVED_TECHNICAL",
            "UNRESOLVED",
            "GEN-TECH-010",
            ["technical or business context"],
        )
    if result is None:
        return [], set()
    technical_class, status, rule_id, required_context = result
    return [
        {
            "physical_column_id": physical_column_id,
            "technical_class": technical_class,
            "status": status,
            "required_context": required_context,
            "source_kind": "COLUMN_NAME",
            "source_span": [0, len(column_name)],
            "source_ref": f"column_name:{physical_column_id}",
            "rule_id": rule_id,
        }
    ], {rule_id, "GEN-PROHIBIT-007"}


def _generic_attribute_observations(
    physical_column_id: str,
    column_name: str,
    column_comment: str | None,
    technical: Sequence[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], set[str]]:
    technical_class = str(technical[0]["technical_class"]) if technical else None
    if technical_class in {
        "AUDIT_ACTOR",
        "AUDIT_TIME",
        "BATCH_METADATA",
        "SOFT_DELETE",
        "VERSION_CONTROL",
        "EXTENSION_SLOT",
    }:
        return [], [], set()

    name = unicodedata.normalize("NFKC", column_name).upper()
    comment = unicodedata.normalize("NFKC", column_comment or "")
    combined = f"{name} {comment}"
    anchor = _object_anchor(name, comment)
    found: list[tuple[str, str, str]] = []

    if re.search(
        r"(?:SHORT_NAME|LONG_NAME|SHORT_DESC|LONG_DESC|简称|短名|长名)", combined
    ):
        found.append(("NAME_VARIANT_OBSERVATION", "GEN-ATTR-001", "COLUMN_NAME"))
    if re.search(r"(?:^|_)(?:ID|NO)(?:_|$)|编号|主键", name) or re.search(
        r"编号|主键", comment
    ):
        source_kind = (
            "COLUMN_NAME"
            if re.search(r"(?:^|_)(?:ID|NO)(?:_|$)", name)
            else "COLUMN_COMMENT"
        )
        found.append(("IDENTIFIER_SHAPE", "GEN-ATTR-001", source_kind))
    if re.search(r"(?:^|_)NUM(?:_|$)", name):
        found.append(("NUMERIC_SHAPE", "GEN-ATTR-001", "COLUMN_NAME"))
    if re.search(r"(?:^|_)CODE(?:_|$)|代码", combined):
        source_kind = "COLUMN_NAME" if "CODE" in name else "COLUMN_COMMENT"
        found.append(("CODE_SHAPE", "GEN-ATTR-001", source_kind))
    if re.search(r"(?:^|_)STATUS(?:_|$)|状态", combined):
        source_kind = "COLUMN_NAME" if "STATUS" in name else "COLUMN_COMMENT"
        found.append(("BUSINESS_OBJECT_STATE", "GEN-ATTR-002", source_kind))
    if re.search(r"(?:^|_)TYPE(?:_|$)|类型|类别|方式|模式|标志|是否", combined):
        source_kind = "COLUMN_NAME" if "TYPE" in name else "COLUMN_COMMENT"
        found.append(("CLASSIFICATION", "GEN-ATTR-002", source_kind))
    if re.search(r"(?:AMT|AMOUNT|NOTIONAL|金额|本金)", combined):
        source_kind = (
            "COLUMN_NAME"
            if re.search(r"(?:AMT|AMOUNT|NOTIONAL)", name)
            else "COLUMN_COMMENT"
        )
        found.append(("MEASURE", "GEN-ATTR-003", source_kind))
    if re.search(r"(?:QTY|QUANTITY|数量|余额)", combined):
        source_kind = (
            "COLUMN_NAME" if re.search(r"(?:QTY|QUANTITY)", name) else "COLUMN_COMMENT"
        )
        found.append(("QUANTITY", "GEN-ATTR-003", source_kind))
    if re.search(r"(?:^|_)RATE(?:_|$)|比率|比例", combined):
        source_kind = "COLUMN_NAME" if "RATE" in name else "COLUMN_COMMENT"
        found.append(("RATE", "GEN-ATTR-003", source_kind))
    if re.search(r"(?:DATE|DATETIME|TIME|日期|时间)", combined):
        source_kind = (
            "COLUMN_NAME"
            if re.search(r"(?:DATE|DATETIME|TIME)", name)
            else "COLUMN_COMMENT"
        )
        found.append(("TIME", "GEN-ATTR-003", source_kind))
    comment_has_measure = bool(re.search(r"金额|本金", comment))
    if re.search(r"(?:^|_)(?:CURRENCY|CCY)(?:_|$)", name) or (
        "币种" in comment and not comment_has_measure
    ):
        source_kind = (
            "COLUMN_NAME"
            if re.search(r"(?:^|_)(?:CURRENCY|CCY)(?:_|$)", name)
            else "COLUMN_COMMENT"
        )
        found.append(("CURRENCY", "GEN-ATTR-003", source_kind))
    if re.search(r"(?:DESC|DESCRIPTION|备注|描述)", combined):
        source_kind = (
            "COLUMN_NAME"
            if re.search(r"(?:DESC|DESCRIPTION)", name)
            else "COLUMN_COMMENT"
        )
        found.append(("DESCRIPTION", "GEN-ATTR-003", source_kind))
    protected_source_target = any(
        phrase in name
        for phrase in (
            "SOURCE_TYPE",
            "SOURCE_ID",
            "SOURCE_SYSTEM",
            "TARGET_ACCOUNT",
            "SOURCE_CTPTY",
            "TARGET_CTPTY",
        )
    )
    if not protected_source_target and (
        re.search(r"(?:^|_)(?:SOURCE|TARGET)(?:_|$)", name)
        or re.search(r"来源|目标", comment)
    ):
        source_kind = (
            "COLUMN_NAME"
            if re.search(r"(?:^|_)(?:SOURCE|TARGET)(?:_|$)", name)
            else "COLUMN_COMMENT"
        )
        found.append(("SOURCE_TARGET_TERM", "GEN-ATTR-003", source_kind))

    observations: list[dict[str, object]] = []
    unresolved: list[dict[str, object]] = []
    applied: set[str] = set()
    for attribute, rule_id, source_kind in dict.fromkeys(found):
        status = "CANDIDATE" if anchor else "UNBOUND_ATTRIBUTE_OBSERVATION"
        source_value = (
            column_name if source_kind == "COLUMN_NAME" else (column_comment or "")
        )
        source_ref = (
            f"column_name:{physical_column_id}"
            if source_kind == "COLUMN_NAME"
            else f"column_comment:{physical_column_id}"
        )
        observations.append(
            {
                "physical_column_id": physical_column_id,
                "attribute": attribute,
                "object_anchor_candidate": anchor,
                "status": status,
                "source_kind": source_kind,
                "source_span": [0, len(source_value)],
                "source_ref": source_ref,
                "rule_id": rule_id,
            }
        )
        applied.add(rule_id)
        if status == "UNBOUND_ATTRIBUTE_OBSERVATION":
            unresolved.append(
                {
                    "physical_column_id": physical_column_id,
                    "code": "UNBOUND_ATTRIBUTE_OBSERVATION",
                    "reason": f"{attribute} has no field-level business object anchor.",
                    "source_kind": source_kind,
                    "source_span": [0, len(source_value)],
                    "source_ref": source_ref,
                    "rule_id": "GEN-UNKNOWN-003",
                    "required_next_evidence": ["semantic-layer object boundary"],
                }
            )
            applied.update(("GEN-ATTR-004", "GEN-UNKNOWN-003"))
    if observations:
        applied.update(("GEN-ATTR-005", "GEN-PROHIBIT-003"))
    return observations, unresolved, applied


def _qualifier_observations(
    physical_column_id: str,
    column_name: str,
    column_comment: str | None,
) -> tuple[list[dict[str, object]], set[str]]:
    comment = unicodedata.normalize("NFKC", column_comment or "")
    name = unicodedata.normalize("NFKC", column_name).upper()
    results: list[dict[str, object]] = []
    applied: set[str] = set()

    name_side = "SHORT" if "SHORT" in name else "LONG" if "LONG" in name else None
    comment_sides = []
    if "空头" in comment:
        comment_sides.append("SHORT")
    if "多头" in comment:
        comment_sides.append("LONG")
    for value in comment_sides:
        status = "CONFLICT" if name_side and name_side != value else "CANDIDATE"
        results.append(
            {
                "physical_column_id": physical_column_id,
                "dimension": "position_side",
                "value": value,
                "status": status,
                "evidence_ref": f"column_comment:{physical_column_id}",
                "source_kind": "COLUMN_COMMENT",
                "source_span": [0, len(column_comment or "")],
                "source_ref": f"column_comment:{physical_column_id}",
                "rule_id": "TF-CONTEXT-002",
            }
        )
        applied.add("TF-CONTEXT-002")

    qualifier_patterns = (
        ("trade_side", "BUY", ("买入", "买方"), "GEN-ATTR-002"),
        ("trade_side", "SELL", ("卖出", "卖方"), "GEN-ATTR-002"),
        ("cashflow_direction", "PAY", ("支付", "付出"), "GEN-ATTR-003"),
        ("cashflow_direction", "RECEIVE", ("收取", "收款"), "GEN-ATTR-003"),
        ("variability", "DYNAMIC", ("动态",), "GEN-ATTR-002"),
        ("variability", "FIXED", ("固定",), "GEN-ATTR-002"),
        ("currency_basis", "ORIGINAL_CURRENCY", ("原币", "原始币种"), "GEN-ATTR-003"),
        ("currency_basis", "LOCAL_CURRENCY", ("本币", "本地币种"), "GEN-ATTR-003"),
        ("currency_basis", "UNDERLYING_CURRENCY", ("标的币种",), "GEN-ATTR-003"),
        ("currency_basis", "SETTLEMENT_CURRENCY", ("结算币种",), "GEN-ATTR-003"),
    )
    for dimension, value, patterns, rule_id in qualifier_patterns:
        if any(pattern in comment for pattern in patterns):
            results.append(
                {
                    "physical_column_id": physical_column_id,
                    "dimension": dimension,
                    "value": value,
                    "status": "CANDIDATE",
                    "evidence_ref": f"column_comment:{physical_column_id}",
                    "source_kind": "COLUMN_COMMENT",
                    "source_span": [0, len(column_comment or "")],
                    "source_ref": f"column_comment:{physical_column_id}",
                    "rule_id": rule_id,
                }
            )
            applied.add(rule_id)
    return results, applied


def _conflict(
    physical_column_id: str,
    conflict_type: str,
    evidence_a: str,
    evidence_b: str,
    interpretations: Sequence[str],
    next_evidence: Sequence[str],
    rule_id: str,
    source_spans: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    key = "\x1f".join((physical_column_id, conflict_type, evidence_a, evidence_b))
    return {
        "conflict_id": f"conflict-{_sha256_text(key)[:20]}",
        "physical_column_id": physical_column_id,
        "conflict_type": conflict_type,
        "evidence_a": evidence_a,
        "evidence_b": evidence_b,
        "candidate_interpretations": list(interpretations),
        "prohibited_auto_resolution": True,
        "required_next_evidence": list(next_evidence),
        "review_status": "UNREVIEWED",
        "rule_ids": [rule_id, "GEN-CONFLICT-009"],
        "source_spans": [dict(item) for item in source_spans],
    }


def _conflicts(
    physical_column_id: str,
    column_name: str,
    column_comment: str | None,
) -> tuple[list[dict[str, object]], set[str]]:
    name = unicodedata.normalize("NFKC", column_name).upper()
    comment = unicodedata.normalize("NFKC", column_comment or "")
    results: list[dict[str, object]] = []
    applied: set[str] = set()
    if column_comment is None:
        results.append(
            _conflict(
                physical_column_id,
                "MISSING_INFORMATION",
                f"column_name:{physical_column_id}",
                f"column_comment:{physical_column_id}:NOT_OBSERVED",
                ["name-form observation", "no comment interpretation"],
                ["column comment or independent semantic evidence"],
                "GEN-CONFLICT-007",
                [
                    {
                        "source_kind": "COLUMN_NAME",
                        "source_span": [0, len(column_name)],
                        "source_ref": f"column_name:{physical_column_id}",
                    },
                    {
                        "source_kind": "COLUMN_COMMENT",
                        "source_span": [0, 0],
                        "source_ref": f"column_comment:{physical_column_id}",
                    },
                ],
            )
        )
        applied.update(("GEN-CONFLICT-007", "GEN-CONFLICT-009"))

    name_side = "SHORT" if "SHORT" in name else "LONG" if "LONG" in name else None
    comment_side = (
        "SHORT" if "空头" in comment else "LONG" if "多头" in comment else None
    )
    direction_conflict = bool(name_side and comment_side and name_side != comment_side)
    currency_only_conflict = bool(
        "NOTIONAL" in name
        and "币种" in comment
        and not re.search(r"本金|金额", comment)
    )
    if direction_conflict or currency_only_conflict:
        interpretations = []
        if name_side:
            interpretations.append(f"name-position-side:{name_side}")
        if comment_side:
            interpretations.append(f"comment-position-side:{comment_side}")
        if currency_only_conflict:
            interpretations.append("comment-currency-basis-only")
        results.append(
            _conflict(
                physical_column_id,
                "NAME_COMMENT_CONFLICT",
                f"column_name:{physical_column_id}",
                f"column_comment:{physical_column_id}",
                interpretations,
                ["semantic-layer object and expression adjudication"],
                "GEN-CONFLICT-001",
                [
                    {
                        "source_kind": "COLUMN_NAME",
                        "source_span": [0, len(column_name)],
                        "source_ref": f"column_name:{physical_column_id}",
                    },
                    {
                        "source_kind": "COLUMN_COMMENT",
                        "source_span": [0, len(column_comment or "")],
                        "source_ref": f"column_comment:{physical_column_id}",
                    },
                ],
            )
        )
        applied.update(
            (
                "GEN-CONFLICT-001",
                "TF-CONFLICT-001",
                "GEN-CONFLICT-009",
                "GEN-PROHIBIT-008",
            )
        )

    if re.search(r"(?:QTY|QUANTITY)", name) and "余额" in comment:
        results.append(
            _conflict(
                physical_column_id,
                "COMPETING_MEASURE_INTERPRETATION",
                f"column_name:{physical_column_id}",
                f"column_comment:{physical_column_id}",
                ["quantity-shape", "balance-shape"],
                ["semantic-layer measure definition"],
                "GEN-CONFLICT-006",
                [
                    {
                        "source_kind": "COLUMN_NAME",
                        "source_span": [0, len(column_name)],
                        "source_ref": f"column_name:{physical_column_id}",
                    },
                    {
                        "source_kind": "COLUMN_COMMENT",
                        "source_span": [0, len(column_comment or "")],
                        "source_ref": f"column_comment:{physical_column_id}",
                    },
                ],
            )
        )
        applied.update(("GEN-CONFLICT-006", "GEN-CONFLICT-009", "GEN-PROHIBIT-008"))
    return results, applied


def _abbreviation_conflicts(
    physical_column_id: str,
    tokens: Sequence[dict[str, object]],
    abbreviations: Sequence[dict[str, object]],
    contract_sha256: str,
) -> tuple[list[dict[str, object]], set[str]]:
    """Record every unknown abbreviation independently of other conflicts."""

    tokens_by_id = {str(token["token_id"]): token for token in tokens}
    conflicts: list[dict[str, object]] = []
    for observation in abbreviations:
        if observation["status"] != "UNRECOGNIZED_ABBREVIATION":
            continue
        token = tokens_by_id[str(observation["token_id"])]
        conflicts.append(
            _conflict(
                physical_column_id,
                "UNRECOGNIZED_ABBREVIATION",
                str(token["token_id"]),
                f"rule_registry:{contract_sha256}:GEN-ABBR-003:NO_MATCH",
                [
                    f"raw-acronym:{token['normalized_text']}",
                    "unresolved-domain-abbreviation",
                ],
                ["versioned abbreviation registry or semantic review"],
                "GEN-CONFLICT-008",
                [
                    {
                        "source_kind": token["source_kind"],
                        "source_span": token["source_span"],
                        "source_ref": token["source_ref"],
                    }
                ],
            )
        )
    applied = {"GEN-CONFLICT-008", "GEN-CONFLICT-009"} if conflicts else set()
    return conflicts, applied


def _normalized_forms(
    physical_column_id: str,
    column_name: str,
    column_comment: str | None,
    object_name: str,
    object_comment: str | None,
    asset_id: str,
) -> tuple[list[dict[str, object]], set[str]]:
    sources = (
        ("COLUMN_NAME", column_name, f"column_name:{physical_column_id}"),
        ("COLUMN_COMMENT", column_comment, f"column_comment:{physical_column_id}"),
        ("OBJECT_NAME", object_name, f"object_name:{asset_id}"),
        ("OBJECT_COMMENT", object_comment, f"object_comment:{asset_id}"),
    )
    forms: list[dict[str, object]] = []
    applied: set[str] = set()
    for source_kind, raw, source_ref in sources:
        if raw is None:
            continue
        normalized, rule_ids, information_loss, review_required = _normalize(raw)
        forms.append(
            {
                "physical_column_id": physical_column_id,
                "source_kind": source_kind,
                "raw_value": raw,
                "normalized_value": normalized,
                "source_span": [0, len(raw)],
                "source_ref": source_ref,
                "information_loss": information_loss,
                "review_required": review_required,
                "rule_ids": list(rule_ids),
            }
        )
        applied.update(rule_ids)
        for match in re.finditer(r"[（(]([^（）()]*)[）)]", raw):
            fragment = match.group(1)
            fragment_start, fragment_end = match.span(1)
            fragment_normalized, fragment_rules, fragment_loss, fragment_review = (
                _normalize(fragment)
            )
            fragment_rule_ids = tuple(dict.fromkeys((*fragment_rules, "GEN-NORM-008")))
            forms.append(
                {
                    "physical_column_id": physical_column_id,
                    "source_kind": source_kind,
                    "raw_value": fragment,
                    "normalized_value": fragment_normalized,
                    "source_span": [fragment_start, fragment_end],
                    "source_ref": source_ref,
                    "information_loss": fragment_loss,
                    "review_required": fragment_review,
                    "rule_ids": list(fragment_rule_ids),
                }
            )
            applied.update(fragment_rule_ids)
    return forms, applied


def _nullable(column: Mapping[str, object]) -> bool:
    value = column.get("nullable_declared")
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.upper() in {"Y", "YES", "TRUE"}:
        return True
    if isinstance(value, str) and value.upper() in {"N", "NO", "FALSE"}:
        return False
    raise ValueError(
        f"column {column.get('column_id')} has no boolean nullable declaration"
    )


def build_evidence_pack(
    column: Mapping[str, object],
    object_row: Mapping[str, object],
    config: FieldEvidenceConfig,
) -> dict[str, object]:
    """Build one P1 pack without producing a business concept or Reader output."""

    physical_column_id = str(column.get("column_id", ""))
    asset_id = str(column.get("asset_id", ""))
    if not physical_column_id or not asset_id or asset_id != object_row.get("asset_id"):
        raise ValueError("column/object physical identity join is incomplete")
    column_name = str(column.get("column_name", ""))
    data_type = str(column.get("data_type", ""))
    object_name = str(object_row.get("object_name", ""))
    object_type = str(object_row.get("object_type", "")).upper()
    schema_name = str(object_row.get("schema_name", "")).upper()
    column_comment_value = column.get("column_comment")
    object_comment_value = object_row.get("object_comment")
    column_comment = (
        column_comment_value if isinstance(column_comment_value, str) else None
    )
    object_comment = (
        object_comment_value if isinstance(object_comment_value, str) else None
    )
    if not column_name or not data_type or not object_name:
        raise ValueError(
            f"column {physical_column_id} is missing a required raw physical fact"
        )

    normalized_forms, normalization_rules = _normalized_forms(
        physical_column_id,
        column_name,
        column_comment,
        object_name,
        object_comment,
        asset_id,
    )
    tokens, protected, token_rules = _tokenize(
        physical_column_id, column_name, column_comment
    )
    abbreviations, abbreviation_unresolved, abbreviation_rules = (
        _abbreviation_observations(physical_column_id, tokens)
    )
    technical, technical_rules = _technical_observations(
        physical_column_id, column_name, object_name
    )
    generic, generic_unresolved, generic_rules = _generic_attribute_observations(
        physical_column_id, column_name, column_comment, technical
    )
    qualifiers, qualifier_rules = _qualifier_observations(
        physical_column_id, column_name, column_comment
    )
    conflicts, conflict_rules = _conflicts(
        physical_column_id, column_name, column_comment
    )
    abbreviation_conflicts, abbreviation_conflict_rules = _abbreviation_conflicts(
        physical_column_id,
        tokens,
        abbreviations,
        config.contract_sha256,
    )
    conflicts.extend(abbreviation_conflicts)
    conflict_rules.update(abbreviation_conflict_rules)

    excluded = config.exclude_object_name_numeric_suffix and bool(
        _NUMERIC_SUFFIX.search(object_name)
    )
    disposition = {
        "status": "EXCLUDED" if excluded else "PREPARED",
        "reason_code": "DOWNSTREAM_OBJECT_NAME_NUMERIC_SUFFIX" if excluded else None,
        "downstream_workset": config.downstream_workset_id if excluded else None,
    }

    unresolved = [*abbreviation_unresolved, *generic_unresolved]
    applied = {
        "GEN-ID-001",
        "GEN-CTX-001",
        "GEN-PROHIBIT-004",
        "GEN-PROHIBIT-005",
        "GEN-PROHIBIT-006",
        *normalization_rules,
        *token_rules,
        *abbreviation_rules,
        *technical_rules,
        *generic_rules,
        *qualifier_rules,
        *conflict_rules,
    }
    if column_comment is None:
        unresolved.append(
            {
                "physical_column_id": physical_column_id,
                "code": "NOT_OBSERVED",
                "reason": "Column comment is absent in the frozen physical fact.",
                "source_kind": "COLUMN_COMMENT",
                "source_span": [0, 0],
                "source_ref": f"column_comment:{physical_column_id}",
                "rule_id": "GEN-UNKNOWN-001",
                "required_next_evidence": [
                    "column comment or independent semantic evidence"
                ],
            }
        )
        applied.add("GEN-UNKNOWN-001")
    for phrase in protected:
        if phrase["status"] == "UNRESOLVED":
            unresolved.append(
                {
                    "physical_column_id": physical_column_id,
                    "code": "UNRESOLVED_PROTECTED_PHRASE",
                    "reason": (
                        f"Protected phrase {phrase['phrase']} lacks a column comment "
                        "disambiguator."
                    ),
                    "source_kind": phrase["source_kind"],
                    "source_span": phrase["source_span"],
                    "source_ref": phrase["source_ref"],
                    "rule_id": "GEN-UNKNOWN-004",
                    "required_next_evidence": [
                        "column comment or semantic-layer context"
                    ],
                }
            )
            applied.update(("GEN-PHRASE-005", "GEN-UNKNOWN-004"))
    for item in technical:
        if item["status"] == "UNRESOLVED":
            unresolved.append(
                {
                    "physical_column_id": physical_column_id,
                    "code": "UNRESOLVED_TECHNICAL",
                    "reason": (
                        f"{item['technical_class']} remains a technical-form "
                        "observation only."
                    ),
                    "source_kind": item["source_kind"],
                    "source_span": item["source_span"],
                    "source_ref": item["source_ref"],
                    "rule_id": "GEN-TECH-010",
                    "required_next_evidence": list(item["required_context"]),
                }
            )
            applied.add("GEN-TECH-010")
    unresolved.append(
        {
            "physical_column_id": physical_column_id,
            "code": "SEMANTIC_LAYER_REQUIRED",
            "reason": "P1 preparation does not adjudicate a business concept or Reader expression.",
            "source_kind": "COLUMN_NAME",
            "source_span": [0, len(column_name)],
            "source_ref": f"column_name:{physical_column_id}",
            "rule_id": "GEN-UNKNOWN-005",
            "required_next_evidence": ["P2 semantic candidate and P3 review decision"],
        }
    )
    applied.add("GEN-UNKNOWN-005")

    evidence_status = [
        {"status": "SUPPORT", "evidence_ref": f"column_name:{physical_column_id}"},
        {
            "status": "SUPPORT" if column_comment is not None else "NOT_OBSERVED",
            "evidence_ref": f"column_comment:{physical_column_id}",
        },
        {"status": "CONTEXT_ONLY", "evidence_ref": f"object_name:{asset_id}"},
        {
            "status": "CONTEXT_ONLY" if object_comment is not None else "NOT_OBSERVED",
            "evidence_ref": f"object_comment:{asset_id}",
        },
    ]
    if conflicts:
        evidence_status.extend(
            {"status": "CONTRADICT", "evidence_ref": str(item["conflict_id"])}
            for item in conflicts
        )

    pack: dict[str, object] = {
        "physical_identity": {
            "schema_name": schema_name,
            "object_name": object_name,
            "object_type": object_type,
            "physical_column_id": physical_column_id,
        },
        "raw_physical_fact": {
            "object_comment_raw": object_comment,
            "column_name_raw": column_name,
            "column_comment_raw": column_comment,
            "data_type_raw": data_type,
            "nullable": _nullable(column),
            "ordinal_position": int(column.get("ordinal_position", 0)),
        },
        "preparation_disposition": disposition,
        "normalized_lexical_form": normalized_forms,
        "tokens": tokens,
        "protected_phrases": protected,
        "abbreviation_observations": abbreviations,
        "generic_attribute_observations": generic,
        "technical_observations": technical,
        "contextual_evidence": [
            {
                "physical_column_id": physical_column_id,
                "context_id": f"object-context-{_sha256_text(asset_id)[:20]}",
                "context_type": "OBJECT",
                "status": "CONTEXT_ONLY",
                "source_ref": f"object_name:{asset_id}",
                "source_kind": "OBJECT_NAME",
                "source_span": [0, len(object_name)],
                "rule_id": "GEN-CTX-001",
            }
        ],
        "candidate_qualifier_observations": qualifiers,
        "conflicts": conflicts,
        "unresolved_items": unresolved,
        "applied_rule_ids": {"values": sorted(applied)},
        "provenance": {
            "source_artifacts": [
                {
                    "path": config.columns_source.display_path,
                    "sha256": config.columns_source.sha256,
                    "locator": f"physical_column_id={physical_column_id}",
                    "evidence_role": config.columns_source.evidence_role,
                },
                {
                    "path": config.objects_source.display_path,
                    "sha256": config.objects_source.sha256,
                    "locator": f"asset_id={asset_id}",
                    "evidence_role": config.objects_source.evidence_role,
                },
            ],
            "injected_source_manifest_id": None,
            "injected_source_manifest_sha256": None,
        },
        "evidence_status": evidence_status,
    }
    validate_evidence_pack(pack, config)
    return pack


def _walk_rows(value: object) -> Iterable[dict[str, object]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_rows(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_rows(child)


def validate_evidence_pack(
    pack: Mapping[str, object], config: FieldEvidenceConfig
) -> None:
    """Validate the invariants that matter even without a JSON Schema runtime."""

    if tuple(pack) != BLOCK_NAMES:
        raise ValueError("field evidence pack must contain exactly the fixed 16 blocks")
    identity = _mapping(pack["physical_identity"], "physical_identity")
    physical_column_id = str(identity.get("physical_column_id", ""))
    if not physical_column_id:
        raise ValueError("physical_identity.physical_column_id is required")
    if identity.get("schema_name") != config.schema_name:
        raise ValueError(f"pack {physical_column_id} is outside the configured schema")
    if identity.get("object_type") not in config.object_types:
        raise ValueError(f"pack {physical_column_id} has an unsupported object type")

    raw = _mapping(pack["raw_physical_fact"], "raw_physical_fact")
    if not isinstance(raw.get("column_name_raw"), str) or not raw.get(
        "column_name_raw"
    ):
        raise ValueError(f"pack {physical_column_id} lost its raw column name")
    if not isinstance(raw.get("nullable"), bool):
        raise ValueError(f"pack {physical_column_id} has no boolean nullable value")
    if (
        not isinstance(raw.get("ordinal_position"), int)
        or int(raw["ordinal_position"]) < 1
    ):
        raise ValueError(f"pack {physical_column_id} has an invalid ordinal position")

    disposition = _mapping(pack["preparation_disposition"], "preparation_disposition")
    if disposition.get("status") not in {"PREPARED", "EXCLUDED", "DEFERRED"}:
        raise ValueError(f"pack {physical_column_id} has an invalid disposition")
    normalized = pack["normalized_lexical_form"]
    if not isinstance(normalized, list) or not normalized:
        raise ValueError(f"pack {physical_column_id} has no normalized lexical form")

    for row in _walk_rows(pack):
        row_id = row.get("physical_column_id")
        if row_id is not None and row_id != physical_column_id:
            raise ValueError(
                f"pack {physical_column_id} contains cross-field derived evidence"
            )
    source_values = {
        "COLUMN_NAME": raw.get("column_name_raw"),
        "COLUMN_COMMENT": raw.get("column_comment_raw"),
        "OBJECT_NAME": identity.get("object_name"),
        "OBJECT_COMMENT": raw.get("object_comment_raw"),
    }
    asset_id = physical_column_id.rsplit(":COLUMN:", 1)[0]
    source_refs = {
        "COLUMN_NAME": f"column_name:{physical_column_id}",
        "COLUMN_COMMENT": f"column_comment:{physical_column_id}",
        "OBJECT_NAME": f"object_name:{asset_id}",
        "OBJECT_COMMENT": f"object_comment:{asset_id}",
    }
    cited_rules: set[str] = set()

    def validate_trace(row: Mapping[str, object], label: str) -> None:
        source_kind = row.get("source_kind")
        source_span = row.get("source_span")
        source_ref = row.get("source_ref")
        if source_kind not in source_values:
            raise ValueError(f"pack {physical_column_id} {label} has no source kind")
        if (
            not isinstance(source_span, list)
            or len(source_span) != 2
            or not all(isinstance(item, int) and item >= 0 for item in source_span)
        ):
            raise ValueError(f"pack {physical_column_id} {label} has no source span")
        start, end = source_span
        source_value = source_values[str(source_kind)]
        if source_value is None:
            if [start, end] != [0, 0]:
                raise ValueError(f"pack {physical_column_id} {label} spans absent text")
        elif end < start or end > len(str(source_value)):
            raise ValueError(
                f"pack {physical_column_id} {label} source span is out of range"
            )
        elif source_value and end == start:
            raise ValueError(
                f"pack {physical_column_id} {label} has an empty source span"
            )
        if not isinstance(source_ref, str) or not source_ref:
            raise ValueError(f"pack {physical_column_id} {label} has no source ref")
        if source_ref != source_refs[str(source_kind)]:
            raise ValueError(
                f"pack {physical_column_id} {label} source ref does not identify its source"
            )
        row_rule_ids = row.get("rule_ids")
        if row_rule_ids is None:
            row_rule_ids = [row.get("rule_id")]
        if (
            not isinstance(row_rule_ids, list)
            or not row_rule_ids
            or not all(isinstance(rule_id, str) for rule_id in row_rule_ids)
        ):
            raise ValueError(
                f"pack {physical_column_id} {label} has no rule provenance"
            )
        cited_rules.update(str(rule_id) for rule_id in row_rule_ids)

    traced_sections = (
        "normalized_lexical_form",
        "tokens",
        "protected_phrases",
        "abbreviation_observations",
        "generic_attribute_observations",
        "technical_observations",
        "contextual_evidence",
        "candidate_qualifier_observations",
        "unresolved_items",
    )
    for section in traced_sections:
        rows = pack[section]
        if not isinstance(rows, list):
            raise ValueError(f"pack {physical_column_id} {section} must be a list")
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise ValueError(
                    f"pack {physical_column_id} {section}[{index}] is invalid"
                )
            validate_trace(row, f"{section}[{index}]")
            source_value = source_values[str(row["source_kind"])]
            start, end = row["source_span"]
            if section == "normalized_lexical_form":
                if (
                    source_value is None
                    or row.get("raw_value") != str(source_value)[start:end]
                ):
                    raise ValueError(
                        f"pack {physical_column_id} normalized raw value does not match its source span"
                    )
                expected_normalized = _normalize(str(row["raw_value"]))[0]
                if row.get("normalized_value") != expected_normalized:
                    raise ValueError(
                        f"pack {physical_column_id} normalized value is not replayable"
                    )
            if (
                section == "tokens"
                and row.get("raw_text") != str(source_value)[start:end]
            ):
                raise ValueError(
                    f"pack {physical_column_id} token raw text is not replayable"
                )

    conflict_rows = pack["conflicts"]
    if not isinstance(conflict_rows, list):
        raise ValueError(f"pack {physical_column_id} conflicts must be a list")
    for index, row in enumerate(conflict_rows):
        if not isinstance(row, dict):
            raise ValueError(f"pack {physical_column_id} conflicts[{index}] is invalid")
        source_spans = row.get("source_spans")
        if not isinstance(source_spans, list) or not source_spans:
            raise ValueError(f"pack {physical_column_id} conflict has no source spans")
        for source_index, source_span in enumerate(source_spans):
            if not isinstance(source_span, dict):
                raise ValueError(
                    f"pack {physical_column_id} conflict source span is invalid"
                )
            traced = {"physical_column_id": physical_column_id, **source_span}
            traced["rule_ids"] = list(row.get("rule_ids", ()))
            validate_trace(traced, f"conflicts[{index}].source_spans[{source_index}]")

    column_name = str(raw["column_name_raw"])
    column_comment = raw.get("column_comment_raw")
    object_name = str(identity["object_name"])
    object_comment = raw.get("object_comment_raw")
    expected_normalized, _ = _normalized_forms(
        physical_column_id,
        column_name,
        column_comment if isinstance(column_comment, str) else None,
        object_name,
        object_comment if isinstance(object_comment, str) else None,
        asset_id,
    )
    expected_tokens, expected_protected, _ = _tokenize(
        physical_column_id,
        column_name,
        column_comment if isinstance(column_comment, str) else None,
    )
    expected_abbreviations, _, _ = _abbreviation_observations(
        physical_column_id, expected_tokens
    )
    expected_technical, _ = _technical_observations(
        physical_column_id, column_name, object_name
    )
    expected_generic, _, _ = _generic_attribute_observations(
        physical_column_id,
        column_name,
        column_comment if isinstance(column_comment, str) else None,
        expected_technical,
    )
    expected_qualifiers, _ = _qualifier_observations(
        physical_column_id,
        column_name,
        column_comment if isinstance(column_comment, str) else None,
    )
    expected_conflicts, _ = _conflicts(
        physical_column_id,
        column_name,
        column_comment if isinstance(column_comment, str) else None,
    )
    expected_abbreviation_conflicts, _ = _abbreviation_conflicts(
        physical_column_id,
        expected_tokens,
        expected_abbreviations,
        config.contract_sha256,
    )
    expected_conflicts.extend(expected_abbreviation_conflicts)
    expected_context = [
        {
            "physical_column_id": physical_column_id,
            "context_id": f"object-context-{_sha256_text(asset_id)[:20]}",
            "context_type": "OBJECT",
            "status": "CONTEXT_ONLY",
            "source_ref": f"object_name:{asset_id}",
            "source_kind": "OBJECT_NAME",
            "source_span": [0, len(object_name)],
            "rule_id": "GEN-CTX-001",
        }
    ]
    replay_sections = {
        "normalized_lexical_form": expected_normalized,
        "tokens": expected_tokens,
        "protected_phrases": expected_protected,
        "abbreviation_observations": expected_abbreviations,
        "generic_attribute_observations": expected_generic,
        "technical_observations": expected_technical,
        "contextual_evidence": expected_context,
        "candidate_qualifier_observations": expected_qualifiers,
        "conflicts": expected_conflicts,
    }
    for section, expected_rows in replay_sections.items():
        if pack[section] != expected_rows:
            raise ValueError(
                f"pack {physical_column_id} {section} failed deterministic replay"
            )

    for row in pack["generic_attribute_observations"]:  # type: ignore[index]
        if row.get("attribute") not in _GENERIC_ATTRIBUTES:
            raise ValueError(
                f"pack {physical_column_id} has an invalid generic attribute"
            )
    for row in pack["technical_observations"]:  # type: ignore[index]
        if row.get("technical_class") not in _TECHNICAL_CLASSES:
            raise ValueError(
                f"pack {physical_column_id} has an invalid technical class"
            )
    for row in pack["candidate_qualifier_observations"]:  # type: ignore[index]
        dimension = str(row.get("dimension"))
        if dimension not in config.qualifier_values:
            raise ValueError(
                f"pack {physical_column_id} has an invalid qualifier dimension"
            )
        if row.get("value") not in config.qualifier_values[dimension]:
            raise ValueError(
                f"pack {physical_column_id} has an incomplete qualifier value"
            )
    for row in pack["unresolved_items"]:  # type: ignore[index]
        if row.get("code") not in _UNRESOLVED_CODES:
            raise ValueError(
                f"pack {physical_column_id} has an invalid unresolved code"
            )
    for row in pack["evidence_status"]:  # type: ignore[index]
        if row.get("status") not in _EVIDENCE_STATUSES:
            raise ValueError(
                f"pack {physical_column_id} has an invalid evidence status"
            )

    applied = _mapping(pack["applied_rule_ids"], "applied_rule_ids").get("values")
    if (
        not isinstance(applied, list)
        or not applied
        or len(applied) != len(set(applied))
    ):
        raise ValueError(f"pack {physical_column_id} has invalid applied rule ids")
    unknown_rules = set(applied) - config.rule_ids
    if unknown_rules:
        raise ValueError(
            f"pack {physical_column_id} cites unknown rules: {sorted(unknown_rules)}"
        )
    if cited_rules - set(applied):
        raise ValueError(
            f"pack {physical_column_id} omits item rules from applied_rule_ids: "
            f"{sorted(cited_rules - set(applied))}"
        )

    provenance = _mapping(pack["provenance"], "provenance")
    artifacts = provenance.get("source_artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 2:
        raise ValueError(
            f"pack {physical_column_id} must cite both physical source artifacts"
        )
    roles = {row.get("evidence_role") for row in artifacts if isinstance(row, dict)}
    if roles != {"COLUMN_PHYSICAL_FACT", "OBJECT_PHYSICAL_FACT"}:
        raise ValueError(
            f"pack {physical_column_id} has incomplete physical provenance"
        )
    for artifact in artifacts:
        if not isinstance(artifact, dict) or not all(
            artifact.get(key) for key in ("path", "sha256", "locator", "evidence_role")
        ):
            raise ValueError(
                f"pack {physical_column_id} has incomplete source provenance"
            )
    expected_provenance = {
        "source_artifacts": [
            {
                "path": config.columns_source.display_path,
                "sha256": config.columns_source.sha256,
                "locator": f"physical_column_id={physical_column_id}",
                "evidence_role": config.columns_source.evidence_role,
            },
            {
                "path": config.objects_source.display_path,
                "sha256": config.objects_source.sha256,
                "locator": f"asset_id={asset_id}",
                "evidence_role": config.objects_source.evidence_role,
            },
        ],
        "injected_source_manifest_id": None,
        "injected_source_manifest_sha256": None,
    }
    if provenance != expected_provenance:
        raise ValueError(
            f"pack {physical_column_id} provenance does not match the frozen sources"
        )

    forbidden_keys = {
        "business_concept",
        "formal_qualifier",
        "reader_concept",
        "reader_expression",
        "semantic_decision",
    }
    for row in _walk_rows(pack):
        if forbidden_keys.intersection(row):
            raise ValueError(
                f"pack {physical_column_id} crossed the P1 semantic boundary"
            )


def _load_json_rows(path: Path, label: str) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(
        isinstance(row, dict) for row in payload
    ):
        raise ValueError(f"{label} must be a JSON row list")
    return payload


def _verify_source(source: SourceArtifact) -> None:
    if not source.path.is_file():
        raise ValueError(f"missing frozen source artifact: {source.display_path}")
    actual = _sha256_path(source.path)
    if actual != source.sha256:
        raise ValueError(
            f"frozen source hash mismatch for {source.display_path}: expected "
            f"{source.sha256}, got {actual}"
        )


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _run_field_evidence_in_directory(
    config_or_path: FieldEvidenceConfig | str | Path,
    output_dir: str | Path,
) -> dict[str, object]:
    """Build a deterministic P1 result inside a private staging directory."""

    config = (
        config_or_path
        if isinstance(config_or_path, FieldEvidenceConfig)
        else load_field_evidence_config(config_or_path)
    )
    _verify_source(config.columns_source)
    _verify_source(config.objects_source)
    objects = _load_json_rows(config.objects_path, "objects")
    columns = _load_json_rows(config.columns_path, "columns")

    selected_objects = [
        row
        for row in objects
        if str(row.get("schema_name", "")).upper() == config.schema_name
        and str(row.get("object_type", "")).upper() in config.object_types
        and bool(row.get("in_panorama_scope", True))
        and not bool(row.get("is_boundary", False))
    ]
    if len(selected_objects) != config.expected_object_count:
        raise ValueError(
            f"scope drift: expected {config.expected_object_count} objects, got "
            f"{len(selected_objects)}"
        )
    objects_by_id: dict[str, dict[str, object]] = {}
    for row in selected_objects:
        asset_id = str(row.get("asset_id", ""))
        if not asset_id or asset_id in objects_by_id:
            raise ValueError(f"duplicate or missing object asset_id: {asset_id!r}")
        objects_by_id[asset_id] = row
    selected_columns = [
        row for row in columns if str(row.get("asset_id", "")) in objects_by_id
    ]
    if len(selected_columns) != config.expected_physical_column_count:
        raise ValueError(
            "scope drift: expected "
            f"{config.expected_physical_column_count} physical columns, got {len(selected_columns)}"
        )
    ids = [str(row.get("column_id", "")) for row in selected_columns]
    duplicate_ids = sorted(
        value for value, count in Counter(ids).items() if not value or count > 1
    )
    if duplicate_ids:
        raise ValueError(
            f"physical_column_id is missing or duplicated: {duplicate_ids[:10]}"
        )

    output = Path(output_dir)
    if not output.is_dir():
        raise ValueError(f"staging output directory does not exist: {output}")
    packs_path = output / "field-evidence-packs.jsonl"
    digest = hashlib.sha256()
    dispositions: Counter[str] = Counter()
    emitted_ids: set[str] = set()
    observed_rules: set[str] = set()
    with packs_path.open("w", encoding="utf-8", newline="\n") as handle:
        for column in sorted(selected_columns, key=lambda row: str(row["column_id"])):
            asset_id = str(column["asset_id"])
            pack = build_evidence_pack(column, objects_by_id[asset_id], config)
            physical_column_id = str(pack["physical_identity"]["physical_column_id"])
            if physical_column_id in emitted_ids:
                raise ValueError(
                    f"duplicate emitted physical_column_id: {physical_column_id}"
                )
            emitted_ids.add(physical_column_id)
            dispositions[str(pack["preparation_disposition"]["status"])] += 1
            observed_rules.update(
                str(rule_id) for rule_id in pack["applied_rule_ids"]["values"]
            )
            encoded = (_canonical_json(pack) + "\n").encode("utf-8")
            handle.write(encoded.decode("utf-8"))
            digest.update(encoded)

    expected_ids = set(ids)
    missing_ids = expected_ids - emitted_ids
    duplicate_emitted = len(selected_columns) - len(emitted_ids)
    counts = {
        "physical_objects": len(selected_objects),
        "physical_columns": len(selected_columns),
        "evidence_packs": len(emitted_ids),
        "unique_physical_column_ids": len(emitted_ids),
        "missing_physical_column_ids": len(missing_ids),
        "duplicate_physical_column_ids": duplicate_emitted,
        "PREPARED": dispositions["PREPARED"],
        "EXCLUDED": dispositions["EXCLUDED"],
        "DEFERRED": dispositions["DEFERRED"],
    }
    expected_dispositions = (
        config.expected_prepared_count,
        config.expected_excluded_count,
        config.expected_deferred_count,
    )
    actual_dispositions = (counts["PREPARED"], counts["EXCLUDED"], counts["DEFERRED"])
    if actual_dispositions != expected_dispositions:
        raise ValueError(
            f"preparation disposition drift: expected {expected_dispositions}, got "
            f"{actual_dispositions}"
        )
    if (
        counts["PREPARED"] + counts["EXCLUDED"] + counts["DEFERRED"]
        != config.expected_physical_column_count
        or missing_ids
        or duplicate_emitted
    ):
        raise ValueError("one-pack-per-physical-column invariant failed")

    rule_ids = [item.rule_id for item in config.rule_registry]
    observed_rule_ids = [rule_id for rule_id in rule_ids if rule_id in observed_rules]
    unobserved_rule_ids = [
        rule_id for rule_id in rule_ids if rule_id not in observed_rules
    ]
    rule_registry_hash = _sha256_text("\n".join(rule_ids) + "\n")
    schema_hash = _sha256_path(config.schema_path)
    provider_path = Path(__file__).resolve()
    provider_hash = _sha256_path(provider_path)
    packs_hash = digest.hexdigest()
    run_key = "\x1f".join(
        (
            config.profile_sha256,
            config.columns_source.sha256,
            config.objects_source.sha256,
            config.contract_sha256,
            schema_hash,
            provider_hash,
        )
    )
    manifest: dict[str, object] = {
        "schema_version": "field-evidence-run-manifest-v1",
        "run_id": f"tradeflow-field-evidence-{_sha256_text(run_key)[:20]}",
        "profile_id": config.profile_id,
        "profile_sha256": config.profile_sha256,
        "scope": {
            "schema_name": config.schema_name,
            "object_types": list(config.object_types),
            "physical_column_id_scope": config.physical_column_id_scope,
            "downstream_workset_id": config.downstream_workset_id,
        },
        "source_artifacts": [
            {
                "path": config.columns_source.display_path,
                "sha256": config.columns_source.sha256,
                "locator": config.columns_source.locator,
                "evidence_role": config.columns_source.evidence_role,
            },
            {
                "path": config.objects_source.display_path,
                "sha256": config.objects_source.sha256,
                "locator": config.objects_source.locator,
                "evidence_role": config.objects_source.evidence_role,
            },
        ],
        "contract": {
            "path": config.contract_display_path,
            "sha256": config.contract_sha256,
        },
        "schema": {
            "path": config.schema_display_path,
            "schema_id": config.schema_id,
            "sha256": schema_hash,
        },
        "provider": {
            "path": "src/titans_cognition/field_evidence.py",
            "sha256": provider_hash,
        },
        "gold_set": {
            "path": config.gold_set_display_path,
            "sha256": config.gold_set_sha256,
            "formal_gate_status": "NOT_CLAIMED",
        },
        "rule_registry": {
            "declared_count": len(rule_ids),
            "unique_count": len(set(rule_ids)),
            "ids": rule_ids,
            "sha256": rule_registry_hash,
            "coverage_status": "OBSERVED_APPLIED_RULES_ONLY",
            "observed_applied_count": len(observed_rule_ids),
            "observed_applied_ids": observed_rule_ids,
            "unobserved_ids": unobserved_rule_ids,
        },
        "block_registry": {"count": len(BLOCK_NAMES), "names": list(BLOCK_NAMES)},
        "qualifier_values": {
            key: list(values) for key, values in config.qualifier_values.items()
        },
        "counts": counts,
        "field_evidence_packs": {
            "path": "field-evidence-packs.jsonl",
            "sha256": packs_hash,
        },
        "field_evidence_packs_sha256": packs_hash,
        "controls": {
            "model_calls": 0,
            "business_rows_read": False,
            "external_egress": False,
            "database_writes": 0,
            "suite_a_formal_status": "NOT_CLAIMED",
        },
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def run_field_evidence(
    config_or_path: FieldEvidenceConfig | str | Path,
    output_dir: str | Path,
) -> dict[str, object]:
    """Atomically publish a deterministic, versioned P1 evidence result."""

    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError(f"output directory already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{destination.name}-",
        suffix=".staging",
        dir=destination.parent,
    ) as staging_name:
        staging = Path(staging_name)
        manifest = _run_field_evidence_in_directory(config_or_path, staging)
        if destination.exists():
            raise FileExistsError(f"output directory already exists: {destination}")
        staging.replace(destination)
        return manifest


def main(argv: Sequence[str] | None = None) -> int:
    """Run the bounded provider without changing the project's shared CLI."""

    parser = argparse.ArgumentParser(
        description="Prepare deterministic TRADEFLOW P1 field evidence"
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    manifest = run_field_evidence(args.config, args.output)
    print(
        json.dumps(
            {
                "run_id": manifest["run_id"],
                "counts": manifest["counts"],
                "field_evidence_packs_sha256": manifest["field_evidence_packs_sha256"],
                "controls": manifest["controls"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
