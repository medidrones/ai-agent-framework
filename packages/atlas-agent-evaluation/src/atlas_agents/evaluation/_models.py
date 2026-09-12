"""Shared immutable and JSON-safe evaluation model helpers."""

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime

from pydantic import BaseModel, ConfigDict, JsonValue, TypeAdapter

_JSON_MAPPING = TypeAdapter(dict[str, JsonValue])


class FrozenEvaluationModel(BaseModel):
    """Provide strict immutable value semantics to evaluation contracts."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )


def non_empty(value: str) -> str:
    """Normalize outer whitespace and reject blank public identifiers."""
    normalized = value.strip()
    if not normalized:
        raise ValueError("O valor não pode estar vazio")
    return normalized


def json_mapping(value: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    """Validate and isolate a JSON-compatible mapping."""
    return deepcopy(_JSON_MAPPING.validate_python(dict(value)))


def timezone_aware(value: datetime) -> datetime:
    """Reject timestamps without a usable timezone offset."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("O timestamp deve possuir fuso horário")
    return value
