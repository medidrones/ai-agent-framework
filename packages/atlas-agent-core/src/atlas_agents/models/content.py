"""Provider-neutral multimodal message content."""

from typing import Annotated, Literal

from pydantic import Field, field_validator

from atlas_agents._models import _FrozenModel, _json_mapping, _non_empty


class TextContent(_FrozenModel):
    """Represent a non-empty textual content item."""

    type: Literal["text"] = "text"
    text: str

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        """Reject text without meaningful characters."""
        return _non_empty(value)


class ImageContent(_FrozenModel):
    """Reference image content without loading or interpreting it."""

    type: Literal["image"] = "image"
    uri: str
    media_type: str | None = None
    detail: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("uri")
    @classmethod
    def validate_uri(cls, value: str) -> str:
        """Reject an empty opaque image reference."""
        return _non_empty(value)

    @field_validator("media_type", "detail")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        """Reject optional descriptors when explicitly empty."""
        return None if value is None else _non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep image metadata JSON-compatible and isolated."""
        return _json_mapping(value)


class AudioContent(_FrozenModel):
    """Reference audio content without loading or interpreting it."""

    type: Literal["audio"] = "audio"
    uri: str
    media_type: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("uri")
    @classmethod
    def validate_uri(cls, value: str) -> str:
        """Reject an empty opaque audio reference."""
        return _non_empty(value)

    @field_validator("media_type")
    @classmethod
    def validate_media_type(cls, value: str | None) -> str | None:
        """Reject an explicitly empty media type."""
        return None if value is None else _non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep audio metadata JSON-compatible and isolated."""
        return _json_mapping(value)


MessageContent = Annotated[
    TextContent | ImageContent | AudioContent,
    Field(discriminator="type"),
]
