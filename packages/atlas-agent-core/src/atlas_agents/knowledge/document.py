"""Immutable provider-neutral knowledge document contracts."""

from typing import Self

from pydantic import Field, field_validator, model_validator

from atlas_agents._models import _FrozenModel, _json_mapping, _non_empty


class KnowledgeDocument(_FrozenModel):
    """Describe one logical external document without fetching its URI."""

    document_id: str
    source_id: str
    title: str | None = None
    uri: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("document_id", "source_id")
    @classmethod
    def validate_ids(cls, value: str) -> str:
        """Reject blank opaque identifiers."""
        return _non_empty(value)

    @field_validator("title", "uri")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        """Reject explicitly blank optional references."""
        return None if value is None else _non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep metadata JSON-compatible and isolated."""
        return _json_mapping(value)


class KnowledgeLocation(_FrozenModel):
    """Identify an optional human-readable position inside a document."""

    page: int | None = Field(default=None, ge=1)
    section: str | None = None
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, ge=0)

    @field_validator("page", "start_offset", "end_offset", mode="before")
    @classmethod
    def reject_boolean_numbers(cls, value: object) -> object:
        """Reject booleans even though Python treats them as integers."""
        if isinstance(value, bool):
            raise ValueError("Localizações numéricas não podem ser booleanas")
        return value

    @field_validator("section")
    @classmethod
    def validate_section(cls, value: str | None) -> str | None:
        """Reject an explicitly blank section."""
        return None if value is None else _non_empty(value)

    @model_validator(mode="after")
    def validate_offsets(self) -> Self:
        """Require ordered offsets when positional boundaries are present."""
        if self.end_offset is not None and self.start_offset is None:
            raise ValueError("O offset final exige um offset inicial")
        if (
            self.start_offset is not None
            and self.end_offset is not None
            and self.end_offset < self.start_offset
        ):
            raise ValueError("O offset final não pode anteceder o inicial")
        return self
