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
    effective_arguments: dict[str, object] | None = None
    effective_result: ToolExecutionResult | None = None

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

    @field_validator("effective_arguments")
    @classmethod
    def validate_effective_arguments(
        cls, value: dict[str, object] | None
    ) -> dict[str, object] | None:
        """Keep optional effective arguments JSON-compatible and isolated."""
        return None if value is None else _json_mapping(value)

    @model_validator(mode="after")
    def validate_result_identity(self) -> Self:
        """Require the stored result to preserve call identity exactly."""
        if (
            self.result.tool_call_id != self.tool_call_id
            or self.result.tool_name != self.tool_name
        ):
            msg = "O resultado deve pertencer à chamada de ferramenta registrada"
            raise ValueError(msg)
        effective_result = self.effective_result
        if effective_result is not None and (
            effective_result.tool_call_id != self.tool_call_id
            or effective_result.tool_name != self.tool_name
        ):
            msg = "O resultado efetivo deve pertencer à chamada registrada"
            raise ValueError(msg)
        return self

    @property
    def model_facing_result(self) -> ToolExecutionResult:
        """Return the guarded result used for model messages and replay."""
        return self.effective_result or self.result

    @property
    def guarded_arguments(self) -> dict[str, object]:
        """Return effective arguments while preserving old records."""
        return (
            self.effective_arguments
            if self.effective_arguments is not None
            else self.arguments
        )
