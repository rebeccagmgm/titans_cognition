"""Canonical physical-fact extraction from provider-neutral metadata records."""

from dataclasses import dataclass, field
from typing import Iterable, Protocol

from .scope import ScopeConfig


def normalize_identifier(value: str) -> str:
    """Normalize an Oracle unquoted identifier while preserving raw values elsewhere."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError("identifiers must be non-empty strings")
    return value.strip().upper()


def asset_id(source_label: str, schema_name: str, object_type: str, object_name: str) -> str:
    """Build the stable physical asset identifier defined by the result contract."""

    canonical_type = normalize_identifier(object_type).replace(" ", "_")
    return ":".join(
        (
            source_label.strip(),
            normalize_identifier(schema_name),
            canonical_type,
            normalize_identifier(object_name),
        )
    )


def column_id(parent_asset_id: str, column_name: str) -> str:
    """Build the stable physical column identifier."""

    return f"{parent_asset_id}:COLUMN:{normalize_identifier(column_name)}"


@dataclass(frozen=True)
class ColumnMetadata:
    """Provider-neutral physical column metadata."""

    column_name: str
    ordinal_position: int
    data_type: str
    data_length: int | None = None
    data_precision: int | None = None
    data_scale: int | None = None
    nullable_declared: bool | None = None
    default_expression: str | None = None
    column_comment: str | None = None


@dataclass(frozen=True)
class ConstraintMetadata:
    """Provider-neutral database constraint metadata."""

    constraint_name: str
    constraint_type: str
    column_names: tuple[str, ...] = ()
    referenced_asset_id: str | None = None
    referenced_column_names: tuple[str, ...] = ()
    declared_status: str | None = None
    search_condition: str | None = None
    extraction_status: str = "SUCCESS"


@dataclass(frozen=True)
class IndexMetadata:
    """Provider-neutral database index metadata."""

    index_name: str
    is_unique: bool
    index_type: str | None = None
    column_names: tuple[str, ...] = ()
    expressions: tuple[str, ...] = ()
    declared_status: str | None = None


@dataclass(frozen=True)
class DefinitionMetadata:
    """Provider-neutral object definition metadata."""

    definition_type: str
    definition_text: str | None = None
    extraction_status: str = "SUCCESS"
    error_category: str | None = None


@dataclass(frozen=True)
class DependencyMetadata:
    """Provider-neutral Oracle dependency metadata."""

    target_schema_name: str
    target_object_name: str
    dependency_type: str
    target_object_type: str = "TABLE"
    target_is_boundary: bool = False


@dataclass(frozen=True)
class ObjectMetadata:
    """Provider-neutral physical object metadata and extraction state."""

    schema_name: str
    object_name: str
    object_type: str
    object_comment: str | None = None
    columns: tuple[ColumnMetadata, ...] = ()
    constraints: tuple[ConstraintMetadata, ...] = ()
    indexes: tuple[IndexMetadata, ...] = ()
    definitions: tuple[DefinitionMetadata, ...] = ()
    dependencies: tuple[DependencyMetadata, ...] = ()
    is_boundary: bool = False
    boundary_for_case_ids: tuple[str, ...] = ()
    extraction_status: str = "SUCCESS"
    error_category: str | None = None


class MetadataProvider(Protocol):
    """Boundary for a read-only metadata source."""

    def iter_objects(self, scope: ScopeConfig) -> Iterable[ObjectMetadata]:
        """Yield provider-neutral objects without reading business rows."""


@dataclass
class PhysicalFacts:
    """Canonical fact rows and explicit extraction failures."""

    objects: list[dict[str, object]] = field(default_factory=list)
    columns: list[dict[str, object]] = field(default_factory=list)
    constraints: list[dict[str, object]] = field(default_factory=list)
    indexes: list[dict[str, object]] = field(default_factory=list)
    object_definitions: list[dict[str, object]] = field(default_factory=list)
    dependencies: list[dict[str, object]] = field(default_factory=list)
    failures: list[dict[str, object]] = field(default_factory=list)


def extract_facts(
    scope: ScopeConfig,
    objects: Iterable[ObjectMetadata],
    run_id: str,
) -> PhysicalFacts:
    """Normalize provider records into V1A object and column facts.

    Out-of-scope records are ignored by design. In-scope failures remain visible as
    object rows and failure rows; they are never converted into inferred values.
    """

    if not run_id.strip():
        raise ValueError("run_id must be non-empty")

    result = PhysicalFacts()
    for raw_object in objects:
        if not raw_object.is_boundary and not scope.accepts_object(
            raw_object.schema_name, raw_object.object_type
        ):
            continue

        normalized_schema = normalize_identifier(raw_object.schema_name)
        normalized_name = normalize_identifier(raw_object.object_name)
        normalized_type = normalize_identifier(raw_object.object_type).replace(" ", "_")
        current_asset_id = asset_id(
            scope.source_label,
            normalized_schema,
            normalized_type,
            normalized_name,
        )
        status = normalize_identifier(raw_object.extraction_status)
        object_row = {
            "run_id": run_id,
            "asset_id": current_asset_id,
            "source_label": scope.source_label,
            "schema_name": normalized_schema,
            "object_name": normalized_name,
            "object_type": normalized_type,
            "in_panorama_scope": not raw_object.is_boundary,
            "deep_case_ids": [],
            "is_boundary": raw_object.is_boundary,
            "boundary_for_case_ids": list(raw_object.boundary_for_case_ids),
            "object_comment": raw_object.object_comment,
            "extraction_status": status,
        }
        result.objects.append(object_row)

        if status != "SUCCESS":
            result.failures.append(
                {
                    "run_id": run_id,
                    "stage": "panorama-extract",
                    "target_id": current_asset_id,
                    "failure_status": status,
                    "error_category": raw_object.error_category or "UNKNOWN",
                }
            )
            continue

        for raw_column in raw_object.columns:
            result.columns.append(
                {
                    "column_id": column_id(current_asset_id, raw_column.column_name),
                    "asset_id": current_asset_id,
                    "column_name": normalize_identifier(raw_column.column_name),
                    "ordinal_position": raw_column.ordinal_position,
                    "data_type": raw_column.data_type,
                    "data_length": raw_column.data_length,
                    "data_precision": raw_column.data_precision,
                    "data_scale": raw_column.data_scale,
                    "nullable_declared": raw_column.nullable_declared,
                    "default_expression": raw_column.default_expression,
                    "column_comment": raw_column.column_comment,
                }
            )

        for raw_constraint in raw_object.constraints:
            constraint_id = f"{current_asset_id}:CONSTRAINT:{normalize_identifier(raw_constraint.constraint_name)}"
            result.constraints.append(
                {
                    "constraint_id": constraint_id,
                    "asset_id": current_asset_id,
                    "constraint_name": normalize_identifier(raw_constraint.constraint_name),
                    "constraint_type": normalize_identifier(raw_constraint.constraint_type),
                    "column_ids": [
                        column_id(current_asset_id, name)
                        for name in raw_constraint.column_names
                    ],
                    "referenced_asset_id": raw_constraint.referenced_asset_id,
                    "referenced_column_ids": (
                        [
                            column_id(raw_constraint.referenced_asset_id, name)
                            for name in raw_constraint.referenced_column_names
                        ]
                        if raw_constraint.referenced_asset_id
                        else []
                    ),
                    "declared_status": raw_constraint.declared_status,
                    "search_condition": raw_constraint.search_condition,
                    "extraction_status": normalize_identifier(
                        raw_constraint.extraction_status
                    ),
                }
            )

        for raw_index in raw_object.indexes:
            result.indexes.append(
                {
                    "index_id": f"{current_asset_id}:INDEX:{normalize_identifier(raw_index.index_name)}",
                    "asset_id": current_asset_id,
                    "index_name": normalize_identifier(raw_index.index_name),
                    "is_unique": raw_index.is_unique,
                    "index_type": raw_index.index_type,
                    "column_ids": [
                        column_id(current_asset_id, name)
                        for name in raw_index.column_names
                    ],
                    "expressions": list(raw_index.expressions),
                    "declared_status": raw_index.declared_status,
                }
            )

        for raw_definition in raw_object.definitions:
            definition_status = normalize_identifier(raw_definition.extraction_status)
            result.object_definitions.append(
                {
                    "definition_id": f"{current_asset_id}:DEFINITION:{normalize_identifier(raw_definition.definition_type)}",
                    "asset_id": current_asset_id,
                    "definition_type": normalize_identifier(raw_definition.definition_type),
                    "definition_text": raw_definition.definition_text,
                    "extraction_status": definition_status,
                    "error_category": raw_definition.error_category,
                }
            )
            if definition_status != "SUCCESS":
                result.failures.append(
                    {
                        "run_id": run_id,
                        "stage": "panorama-extract",
                        "target_id": current_asset_id,
                        "failure_status": definition_status,
                        "error_category": raw_definition.error_category or "UNKNOWN",
                    }
                )

        for raw_dependency in raw_object.dependencies:
            target_asset_id = asset_id(
                scope.source_label,
                raw_dependency.target_schema_name,
                raw_dependency.target_object_type,
                raw_dependency.target_object_name,
            )
            result.dependencies.append(
                {
                    "dependency_id": f"{current_asset_id}:DEPENDENCY:{target_asset_id}",
                    "source_asset_id": current_asset_id,
                    "target_asset_id": target_asset_id,
                    "dependency_type": normalize_identifier(
                        raw_dependency.dependency_type
                    ),
                    "source_kind": "ORACLE_DICTIONARY",
                    "target_is_boundary": raw_dependency.target_is_boundary,
                }
            )

    return result
