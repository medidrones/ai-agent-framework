"""Provider-neutral complete model responses."""

from typing import Self

from pydantic import Field, field_validator, model_validator

from atlas_agents._models import _FrozenModel, _json_mapping, _non_empty
from atlas_agents.models.content import MessageContent
from atlas_agents.models.finish_reason import FinishReason
from atlas_agents.models.tool_call import ToolCall
from atlas_agents.models.usage import ModelUsage


class ModelResponse(_FrozenModel):
    """Represent a complete response without leaking provider objects."""

    response_id: str | None = None
    model: str
    content: tuple[MessageContent, ...] = ()
    tool_calls: tuple[ToolCall, ...] = ()
    finish_reason: FinishReason
    usage: ModelUsage
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("response_id")
    @classmethod
    def validate_response_id(cls, value: str | None) -> str | None:
        """Reject an explicitly empty response identifier."""
        return None if value is None else _non_empty(value)

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        """Reject an empty model identifier."""
        return _non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep response metadata JSON-compatible and isolated."""
        return _json_mapping(value)

    @model_validator(mode="after")
    def validate_tool_call_finish(self) -> Self:
        """Require tool calls when the finish reason reports one."""
        if self.finish_reason is FinishReason.TOOL_CALL and not self.tool_calls:
            msg = "Uma resposta finalizada por tool call deve conter uma chamada"
            raise ValueError(msg)
        return self
