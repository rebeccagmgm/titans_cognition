"""Loading and validating bounded Panorama and Deep Case scopes."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ScopeError(ValueError):
    """Raised when a scope configuration is invalid."""


def _canonical_name(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ScopeError("scope names must be non-empty strings")
    return value.strip().upper()


def _canonical_object_type(value: str) -> str:
    return _canonical_name(value).replace(" ", "_")


@dataclass(frozen=True)
class ScopeConfig:
    """Validated, immutable scope configuration."""

    scope_id: str
    source_label: str
    schemas: tuple[str, ...]
    object_types: tuple[str, ...]
    excluded_schema_suffixes: tuple[str, ...]
    excluded_schemas: tuple[str, ...]

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "ScopeConfig":
        try:
            include = data["include"]
            schemas = tuple(_canonical_name(item) for item in include["schemas"])
            object_types = tuple(
                _canonical_object_type(item) for item in include["object_types"]
            )
        except (KeyError, TypeError) as exc:
            raise ScopeError("scope must define include.schemas and include.object_types") from exc

        if not schemas:
            raise ScopeError("scope must include at least one schema")
        if not object_types:
            raise ScopeError("scope must include at least one object type")
        if len(set(schemas)) != len(schemas):
            raise ScopeError("scope schemas must be unique")
        if len(set(object_types)) != len(object_types):
            raise ScopeError("scope object types must be unique")

        exclude = data.get("exclude", {})
        excluded_suffixes = tuple(
            _canonical_name(item) for item in exclude.get("schema_suffixes", [])
        )
        excluded_schemas = tuple(
            _canonical_name(item) for item in exclude.get("schemas", [])
        )

        scope_id = data.get("scope_id")
        source_label = data.get("source_label")
        if not isinstance(scope_id, str) or not scope_id.strip():
            raise ScopeError("scope_id must be a non-empty string")
        if not isinstance(source_label, str) or not source_label.strip():
            raise ScopeError("source_label must be a non-empty string")

        return cls(
            scope_id=scope_id.strip(),
            source_label=source_label.strip(),
            schemas=schemas,
            object_types=object_types,
            excluded_schema_suffixes=excluded_suffixes,
            excluded_schemas=excluded_schemas,
        )

    def accepts_schema(self, schema_name: str) -> bool:
        """Return whether a schema is explicitly in scope and not excluded."""

        schema = _canonical_name(schema_name)
        if schema not in self.schemas:
            return False
        if schema in self.excluded_schemas:
            return False
        return not any(schema.endswith(suffix) for suffix in self.excluded_schema_suffixes)

    def accepts_object(self, schema_name: str, object_type: str) -> bool:
        """Return whether an object is within this scope."""

        return self.accepts_schema(schema_name) and (
            _canonical_object_type(object_type) in self.object_types
        )


def load_scope(path: str | Path) -> ScopeConfig:
    """Load and validate a UTF-8 YAML scope file."""

    scope_path = Path(path)
    try:
        data = yaml.safe_load(scope_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ScopeError(f"scope file not found: {scope_path}") from exc
    except yaml.YAMLError as exc:
        raise ScopeError(f"invalid YAML scope: {scope_path}") from exc

    if not isinstance(data, dict):
        raise ScopeError("scope YAML root must be a mapping")
    return ScopeConfig.from_mapping(data)
