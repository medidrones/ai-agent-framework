"""Provider-neutral model messages."""

from enum import StrEnum
from typing import Self

from pydantic import Field, field_validator, model_validator

from atlas_agents._models import _FrozenModel, _json_mapping, _non_empty
from atlas_agents.models.content import MessageContent


class MessageRole(StrEnum):
    """Identify the role of a message in a model conversation."""

    SYSTEM = "system"
    DEVELOPER = "developer"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ModelMessage(_FrozenModel):
    """Represent one immutable, potentially multimodal model message."""

    role: MessageRole
    content: tuple[MessageContent, ...] = ()
    name: str | None = None
    tool_call_id: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("name", "tool_call_id")
    @classmethod
    def validate_optional_identifiers(cls, value: str | None) -> str | None:
        """Reject optional identifiers when explicitly empty."""
        return None if value is None else _non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep message metadata JSON-compatible and isolated."""
        return _json_mapping(value)

    @model_validator(mode="after")
    def validate_tool_result(self) -> Self:
        """Require tool results to identify their originating call."""
        if self.role is MessageRole.TOOL and self.tool_call_id is None:
            msg = "Uma mensagem de ferramenta deve informar tool_call_id"
            raise ValueError(msg)
        return self
