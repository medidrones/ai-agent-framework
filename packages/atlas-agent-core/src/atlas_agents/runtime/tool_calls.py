"""Immutable execution-scoped records of processed model tool calls."""

from typing import Self

from pydantic import field_validator, model_validator

from atlas_agents._models import _FrozenModel, _json_mapping, _non_empty
from atlas_agents.tools import ToolExecutionResult


class ToolCallRecord(_FrozenModel):
    """Preserve one controlled tool-call decision for local deduplication."""

    tool_call_id: str
    tool_name: str
    arguments: dict[str, object]
    result: ToolExecutionResult

    @field_validator("tool_call_id", "tool_name")
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        """Reject empty call identifiers and names."""
        return _non_empty(value)

    @field_validator("arguments")
    @classmethod
    def validate_arguments(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep arguments JSON-compatible and isolated."""
        return _json_mapping(value)

    @model_validator(mode="after")
    def validate_result_identity(self) -> Self:
        """Require the stored result to preserve call identity exactly."""
        if (
            self.result.tool_call_id != self.tool_call_id
            or self.result.tool_name != self.tool_name
        ):
            msg = "O resultado deve pertencer à chamada de ferramenta registrada"
            raise ValueError(msg)
        return self
