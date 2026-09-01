"""Minimal execution context passed to model providers."""

from pydantic import Field, field_validator

from atlas_agents._models import _FrozenModel, _json_mapping, _non_empty


class ModelExecutionContext(_FrozenModel):
    """Carry only correlation data required at the model boundary."""

    execution_id: str
    agent_id: str
    request_id: str
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("execution_id", "agent_id", "request_id")
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        """Reject empty correlation identifiers."""
        return _non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep context metadata JSON-compatible and isolated."""
        return _json_mapping(value)
