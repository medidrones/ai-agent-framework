"""Shared immutable models and validation helpers for plugins."""

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, JsonValue
from pydantic_core import PydanticSerializationError, to_jsonable_python


class FrozenPluginModel(BaseModel):
    """Provide value semantics and immutable field assignment."""

    model_config = ConfigDict(frozen=True, extra="forbid")


def non_empty(value: str, *, field_name: str) -> str:
    """Return a trimmed non-empty string."""
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} não pode ser vazio")
    return normalized


def json_mapping(value: Mapping[str, Any]) -> dict[str, JsonValue]:
    """Copy a mapping after validating that it is JSON-safe."""
    try:
        converted = to_jsonable_python(dict(value), fallback=lambda item: _reject(item))
    except (PydanticSerializationError, TypeError, ValueError) as exc:
        raise ValueError(
            "O mapping deve conter somente valores compatíveis com JSON"
        ) from exc
    if not isinstance(converted, dict) or not all(
        isinstance(key, str) for key in converted
    ):
        raise ValueError("O mapping deve usar chaves string")
    return converted


def _reject(value: object) -> object:
    raise TypeError(f"Tipo não serializável: {type(value).__name__}")
