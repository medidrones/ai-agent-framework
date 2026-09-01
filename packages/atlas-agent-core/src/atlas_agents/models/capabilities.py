"""Provider-neutral model capabilities and descriptors."""

from enum import StrEnum

from pydantic import Field, field_validator

from atlas_agents._models import (
    _FrozenModel,
    _json_mapping,
    _non_empty,
    _trimmed_non_empty,
)


class ModelCapability(StrEnum):
    """Identify a stable capability offered by a model."""

    TEXT_GENERATION = "text_generation"
    STREAMING = "streaming"
    STRUCTURED_OUTPUT = "structured_output"
    TOOL_CALLING = "tool_calling"
    PARALLEL_TOOL_CALLING = "parallel_tool_calling"
    VISION = "vision"
    AUDIO_INPUT = "audio_input"
    AUDIO_OUTPUT = "audio_output"
    JSON_MODE = "json_mode"


class ModelDescriptor(_FrozenModel):
    """Describe one model exposed through a provider."""

    provider: str
    model: str
    capabilities: frozenset[ModelCapability]
    context_window: int | None = Field(default=None, gt=0)
    max_output_tokens: int | None = Field(default=None, gt=0)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        """Trim external whitespace from a non-empty provider identifier."""
        return _trimmed_non_empty(value)

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        """Reject an empty opaque model identifier."""
        return _non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep descriptor metadata JSON-compatible and isolated."""
        return _json_mapping(value)
