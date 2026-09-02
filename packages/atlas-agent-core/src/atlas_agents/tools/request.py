"""Structured requests for tool execution."""

from pydantic import Field, field_validator

from atlas_agents._models import _FrozenModel, _json_mapping, _non_empty


class ToolExecutionRequest(_FrozenModel):
    """Represent one exact tool call without provider-specific payloads."""

    tool_call_id: str
    tool_name: str
    arguments: dict[str, object]
    idempotency_key: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("tool_call_id", "tool_name")
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        """Reject empty call identifiers and tool names."""
        return _non_empty(value)

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str | None) -> str | None:
        """Reject an explicitly empty idempotency key."""
        return None if value is None else _non_empty(value)

    @field_validator("arguments", "metadata")
    @classmethod
    def validate_mappings(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep request data JSON-compatible and isolated."""
        return _json_mapping(value)
