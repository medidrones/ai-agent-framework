"""Provider-neutral structured output definitions."""

from pydantic import field_validator

from atlas_agents._models import _FrozenModel, _json_mapping, _non_empty


class StructuredOutputDefinition(_FrozenModel):
    """Describe a JSON Schema expected from a model response."""

    name: str
    description: str | None = None
    json_schema: dict[str, object]
    strict: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Reject an empty structured output name."""
        return _non_empty(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        """Reject an explicitly empty description."""
        return None if value is None else _non_empty(value)

    @field_validator("json_schema")
    @classmethod
    def validate_schema(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep the JSON Schema compatible and isolated."""
        return _json_mapping(value)
