"""Provider-neutral model generation requests."""

from math import isfinite

from pydantic import Field, field_validator

from atlas_agents._models import _FrozenModel, _json_mapping, _non_empty
from atlas_agents.models.message import ModelMessage
from atlas_agents.models.structured_output import StructuredOutputDefinition
from atlas_agents.models.tool_call import ModelToolDefinition


class ModelRequest(_FrozenModel):
    """Describe a complete request to any compatible model provider."""

    model: str
    messages: tuple[ModelMessage, ...] = Field(min_length=1)
    tools: tuple[ModelToolDefinition, ...] = ()
    structured_output: StructuredOutputDefinition | None = None
    temperature: float | None = Field(default=None, ge=0)
    max_output_tokens: int | None = Field(default=None, gt=0)
    stop_sequences: tuple[str, ...] = ()
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        """Reject an empty model identifier."""
        return _non_empty(value)

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, value: float | None) -> float | None:
        """Reject non-finite temperatures while leaving provider ranges open."""
        if value is not None and not isfinite(value):
            msg = "A temperatura deve ser um número finito"
            raise ValueError(msg)
        return value

    @field_validator("stop_sequences")
    @classmethod
    def validate_stop_sequences(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Reject empty stop sequences."""
        return tuple(_non_empty(item) for item in value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep request metadata JSON-compatible and isolated."""
        return _json_mapping(value)
