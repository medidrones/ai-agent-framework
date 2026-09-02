"""Runtime definitions for provider-neutral tools."""

from pydantic import Field, field_validator

from atlas_agents._models import _FrozenModel, _json_mapping, _non_empty
from atlas_agents.models import ModelToolDefinition
from atlas_agents.tools.idempotency import ToolIdempotency


class ToolDefinition(_FrozenModel):
    """Describe a tool's model-facing schema and internal runtime semantics."""

    name: str
    description: str
    parameters: dict[str, object]
    required_permissions: frozenset[str] = frozenset()
    idempotency: ToolIdempotency = ToolIdempotency.UNSPECIFIED
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("name", "description")
    @classmethod
    def validate_text(cls, value: str) -> str:
        """Reject empty names and descriptions."""
        return _non_empty(value)

    @field_validator("required_permissions")
    @classmethod
    def validate_permissions(cls, value: frozenset[str]) -> frozenset[str]:
        """Reject empty opaque permission identifiers."""
        return frozenset(_non_empty(permission) for permission in value)

    @field_validator("parameters", "metadata")
    @classmethod
    def validate_mappings(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep schemas and metadata JSON-compatible and isolated."""
        return _json_mapping(value)

    def to_model_definition(self) -> ModelToolDefinition:
        """Return only the fields that may cross the model boundary."""
        return ModelToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )
