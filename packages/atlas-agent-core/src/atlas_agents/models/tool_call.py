"""Tool contracts exposed only at the model boundary."""

from pydantic import Field, field_validator

from atlas_agents._models import _FrozenModel, _json_mapping, _non_empty


class ToolCall(_FrozenModel):
    """Represent a structured tool call requested by a model."""

    tool_call_id: str
    name: str
    arguments: dict[str, object]
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("tool_call_id", "name")
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        """Reject empty tool call identifiers and names."""
        return _non_empty(value)

    @field_validator("arguments", "metadata")
    @classmethod
    def validate_mappings(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep tool data JSON-compatible and isolated."""
        return _json_mapping(value)


class ModelToolDefinition(_FrozenModel):
    """Describe the model-facing view of an available tool."""

    name: str
    description: str
    parameters: dict[str, object]

    @field_validator("name", "description")
    @classmethod
    def validate_text(cls, value: str) -> str:
        """Reject empty tool names and descriptions."""
        return _non_empty(value)

    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep the parameter schema JSON-compatible and isolated."""
        return _json_mapping(value)
