"""Logical external knowledge source descriptors."""

from pydantic import Field, field_validator

from atlas_agents._models import _FrozenModel, _json_mapping, _non_empty


class KnowledgeSource(_FrozenModel):
    """Describe a logical source independently from retrieval infrastructure."""

    source_id: str
    name: str
    description: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("source_id", "name")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        """Reject blank source identifiers and names."""
        return _non_empty(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        """Reject an explicitly blank description."""
        return None if value is None else _non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep metadata JSON-compatible and isolated."""
        return _json_mapping(value)
