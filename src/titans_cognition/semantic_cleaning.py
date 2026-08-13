"""Corpus-driven semantic cleaning for field-derived concepts.

Business vocabulary is discovered from recurrence in the current corpus.  The
only fixed lexical rules are language-level identifier aliases; product names,
business objects and modifier vocabularies are never enumerated here.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Mapping, Sequence


METHOD_ID = "semantic_cleaning.corpus_recurrence.v1"
REVIEW_DECISIONS = frozenset(
    {
        "EQUIVALENT_ALIAS",
        "QUALIFIED_VARIANT",
        "RELATED_ATTRIBUTE",
        "CONFLICT",
        "DEFER",
    }
)


@dataclass(frozen=True)
class CleanedConcept:
    source_concept_id: str
    source_label: str
    family_label: str
    display_label: str
    attribute_kind: str | None
    qualifiers: tuple[tuple[str, str], ...]
    method: str
    evidence_labels: tuple[str, ...]


_IDENTIFIER_SUFFIX = re.compile(r"(?:ID|编号|编码)$", re.IGNORECASE)
_MIN_CORE_LENGTH = 3


def clean_concepts(
    concepts: Sequence[Mapping[str, object]],
) -> tuple[list[CleanedConcept], list[dict[str, object]]]:
    """Discover recurring semantic families and retain ambiguous decisions."""

    rows = [
        (str(row["concept_id"]), _normalize_label(row.get("label")))
        for row in concepts
        if _normalize_label(row.get("label"))
    ]
    labels = sorted({label for _, label in rows})
    cores = _discover_stable_cores(labels)
    cleaned: list[CleanedConcept] = []
    review: list[dict[str, object]] = []
    for concept_id, label in rows:
        family, evidence = _select_core(label, cores)
        prefix, suffix = _residual(label, family)
        attribute_kind = None
        display_label = label
        qualifiers: list[tuple[str, str]] = []

        if suffix and _IDENTIFIER_SUFFIX.fullmatch(suffix):
            attribute_kind = "IDENTIFIER"
            display_label = family + "ID"
        elif prefix:
            qualifiers.append(("semantic_modifier", prefix))
        elif suffix:
            qualifiers.append(("semantic_modifier", suffix))

        method = "IDENTITY" if family == label else "CORPUS_RECURRENT_CORE"
        cleaned.append(
            CleanedConcept(
                source_concept_id=concept_id,
                source_label=label,
                family_label=family,
                display_label=display_label,
                attribute_kind=attribute_kind,
                qualifiers=tuple(qualifiers),
                method=method,
                evidence_labels=tuple(evidence),
            )
        )
        if family != label and not attribute_kind:
            review.append(
                {
                    "review_type": "QUALIFIED_VARIANT",
                    "source_concept_id": concept_id,
                    "source_label": label,
                    "candidate_family_label": family,
                    "modifier": prefix or suffix,
                    "modifier_position": "PREFIX" if prefix else "SUFFIX",
                    "evidence_labels": evidence,
                    "status": "NEEDS_REVIEW",
                    "method_id": METHOD_ID,
                    "reason": "RECURRENT_CORE_WITH_UNTYPED_MODIFIER",
                }
            )
    return cleaned, review


def discover_same_name_comment_reviews(
    fields: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Queue identical physical names whose non-empty comments disagree."""

    by_name: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for field in fields:
        name = str(field.get("column_name") or "").strip().strip('"').upper()
        comment = _lossless_text(field.get("column_comment"))
        if name and comment:
            by_name[name][comment].append(str(field["column_id"]))
    reviews = []
    for name, comments in sorted(by_name.items()):
        if len(comments) <= 1:
            continue
        reviews.append(
            {
                "review_type": "SAME_PHYSICAL_NAME_DIFFERENT_COMMENT",
                "physical_name": name,
                "comment_variants": [
                    {"comment": comment, "source_refs": sorted(refs)}
                    for comment, refs in sorted(comments.items())
                ],
                "status": "NEEDS_REVIEW",
                "method_id": METHOD_ID,
                "allowed_decisions": [
                    "EQUIVALENT_ALIAS",
                    "QUALIFIED_VARIANT",
                    "RELATED_ATTRIBUTE",
                    "CONFLICT",
                ],
            }
        )
    return reviews


def build_review_batches(
    review_items: Sequence[Mapping[str, object]],
    *,
    batch_size: int = 20,
) -> list[dict[str, object]]:
    """Build compact, provider-neutral review packs without applying decisions."""

    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    by_type: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for item in review_items:
        by_type[str(item.get("review_type", "UNKNOWN"))].append(item)

    batches = []
    for review_type, items in sorted(by_type.items()):
        ordered = sorted(items, key=_review_sort_key)
        for offset in range(0, len(ordered), batch_size):
            rows = ordered[offset : offset + batch_size]
            batches.append(
                {
                    "batch_id": (
                        f"{review_type.lower()}-{offset // batch_size + 1:04d}"
                    ),
                    "review_type": review_type,
                    "decision_contract": {
                        "allowed_decisions": [
                            "EQUIVALENT_ALIAS",
                            "QUALIFIED_VARIANT",
                            "RELATED_ATTRIBUTE",
                            "CONFLICT",
                            "DEFER",
                        ],
                        "required_fields": [
                            "item_key",
                            "decision",
                            "rationale",
                        ],
                        "automatic_write_back": False,
                    },
                    "items": [_compact_review_item(row) for row in rows],
                }
            )
    return batches


def import_review_decisions(
    review_pack_dir: Path,
    responses_path: Path,
    output_path: Path,
    *,
    model_id: str,
) -> dict[str, int]:
    """Validate provider-neutral review responses without applying them.

    The import is an auditable staging step only.  It cannot mutate semantic
    families, expressions, physical facts, or human decisions.
    """

    if not model_id.strip():
        raise ValueError("model_id must not be empty")
    allowed_items: dict[str, str] = {}
    for pack_path in sorted(review_pack_dir.glob("*.json")):
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
        batch_id = str(pack.get("batch_id", pack_path.stem))
        for item in pack.get("items", []):
            item_key = str(item.get("item_key", "")).strip()
            if not item_key:
                raise ValueError(f"review pack has an empty item_key: {pack_path}")
            if item_key in allowed_items:
                raise ValueError(f"duplicate review item_key: {item_key}")
            allowed_items[item_key] = batch_id
    if not allowed_items:
        raise ValueError("review_pack_dir contains no review items")

    decisions = []
    seen: set[str] = set()
    for line_number, line in enumerate(
        responses_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        row = json.loads(line)
        item_key = str(row.get("item_key", "")).strip()
        decision = str(row.get("decision", "")).strip().upper()
        rationale = str(row.get("rationale", "")).strip()
        if item_key not in allowed_items:
            raise ValueError(
                f"response line {line_number} references unknown item_key: {item_key}"
            )
        if item_key in seen:
            raise ValueError(f"duplicate response item_key: {item_key}")
        if decision not in REVIEW_DECISIONS:
            raise ValueError(
                f"response line {line_number} has invalid decision: {decision}"
            )
        if not rationale:
            raise ValueError(f"response line {line_number} must include a rationale")
        seen.add(item_key)
        decisions.append(
            {
                "item_key": item_key,
                "batch_id": allowed_items[item_key],
                "decision": decision,
                "rationale": rationale,
                "reviewer_type": "MODEL_CANDIDATE",
                "model_id": model_id,
                "status": "IMPORTED_NOT_APPLIED",
                "automatic_write_back": False,
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in decisions
        ),
        encoding="utf-8",
    )
    return {
        "available_item_count": len(allowed_items),
        "imported_decision_count": len(decisions),
        "unreviewed_item_count": len(allowed_items) - len(decisions),
    }


def _review_sort_key(item: Mapping[str, object]) -> tuple[str, str]:
    return (
        str(item.get("candidate_family_label", item.get("physical_name", ""))),
        str(item.get("source_label", "")),
    )


def _compact_review_item(item: Mapping[str, object]) -> dict[str, object]:
    if item.get("review_type") == "SAME_PHYSICAL_NAME_DIFFERENT_COMMENT":
        physical_name = str(item["physical_name"])
        return {
            "item_key": f"physical-name:{physical_name}",
            "physical_name": physical_name,
            "comment_variants": item.get("comment_variants", []),
        }
    source_concept_id = str(item.get("source_concept_id", ""))
    return {
        "item_key": f"source-concept:{source_concept_id}",
        "source_concept_id": source_concept_id,
        "source_label": item.get("source_label"),
        "candidate_family_label": item.get("candidate_family_label"),
        "modifier": item.get("modifier"),
        "modifier_position": item.get("modifier_position"),
        "evidence_labels": item.get("evidence_labels", []),
    }


def _discover_stable_cores(labels: Sequence[str]) -> dict[str, tuple[str, ...]]:
    """Return recurrent boundary-aligned cores supported by at least two labels."""

    support: dict[str, set[str]] = defaultdict(set)
    label_set = set(labels)
    for label in labels:
        for other in labels:
            if label == other:
                continue
            if len(other) >= _MIN_CORE_LENGTH and (
                label.startswith(other) or label.endswith(other)
            ):
                support[other].update((label, other))

    # A core may be implicit when several labels share the same longest suffix.
    reversed_labels = [label[::-1] for label in labels]
    for index, left in enumerate(reversed_labels):
        for right in reversed_labels[index + 1 :]:
            length = 0
            for a, b in zip(left, right):
                if a != b:
                    break
                length += 1
            candidate = left[:length][::-1]
            if len(candidate) >= _MIN_CORE_LENGTH and _contains_cjk(candidate):
                members = {label for label in labels if label.endswith(candidate)}
                if len(members) >= 2:
                    support[candidate].update(members)

    # Prefer maximal cores; shorter nested fragments are only retained when
    # they are explicit labels in the corpus.
    return {
        core: tuple(sorted(members))
        for core, members in support.items()
        if len(members) >= 2
        and (
            core in label_set
            or not any(
                core != longer
                and len(longer) > len(core)
                and longer.endswith(core)
                and set(support[longer]) == set(members)
                for longer in support
            )
        )
    }


def _contains_cjk(value: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", value))


def _select_core(
    label: str,
    cores: Mapping[str, tuple[str, ...]],
) -> tuple[str, tuple[str, ...]]:
    candidates = [
        core
        for core in cores
        if label == core or label.startswith(core) or label.endswith(core)
    ]
    if not candidates:
        identifier_core = _IDENTIFIER_SUFFIX.sub("", label)
        if len(identifier_core) >= _MIN_CORE_LENGTH:
            sibling_labels = tuple(
                sorted(
                    value for value in cores.get(identifier_core, ()) if value != label
                )
            )
            if sibling_labels:
                return identifier_core, sibling_labels
        return label, (label,)
    core = max(candidates, key=lambda value: (len(value), value == label, value))
    return core, cores[core]


def _residual(label: str, core: str) -> tuple[str, str]:
    if label == core:
        return "", ""
    if label.endswith(core):
        return label[: -len(core)], ""
    if label.startswith(core):
        return "", label[len(core) :]
    return "", ""


def _normalize_label(value: object) -> str:
    text = re.sub(r"\s+", "", str(value or "").strip())
    return re.sub(r"(?i)id$", "ID", text)


def _lossless_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())
