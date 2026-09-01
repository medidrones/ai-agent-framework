"""Generic inputs and attachment references accepted by agents."""

from pydantic import Field, field_validator

from atlas_agents._models import _FrozenModel, _json_mapping, _non_empty


class AgentAttachment(_FrozenModel):
    """Reference content without resolving or retrieving the referenced URI."""

    attachment_id: str
    name: str
    media_type: str
    uri: str
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("attachment_id", "name", "media_type", "uri")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        """Reject empty attachment identifiers and descriptors."""
        return _non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep metadata serializable and isolated from caller mutation."""
        return _json_mapping(value)


class AgentInput(_FrozenModel):
    """Carry a generic message and opaque attachment references into an agent."""

    message: str
    attachments: tuple[AgentAttachment, ...] = ()
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep metadata serializable and isolated from caller mutation."""
        return _json_mapping(value)
