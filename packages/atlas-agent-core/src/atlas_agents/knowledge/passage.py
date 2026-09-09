"""Immutable textual knowledge passage contracts."""

from pydantic import Field, field_validator

from atlas_agents._models import _FrozenModel, _json_mapping, _non_empty
from atlas_agents.knowledge.document import KnowledgeDocument, KnowledgeLocation


class KnowledgePassage(_FrozenModel):
    """Represent one textual retrieval unit from an external document."""

    passage_id: str
    document: KnowledgeDocument
    content: str
    location: KnowledgeLocation | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("passage_id", "content")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        """Reject blank identifiers and passage content."""
        return _non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep metadata JSON-compatible and isolated."""
        return _json_mapping(value)
