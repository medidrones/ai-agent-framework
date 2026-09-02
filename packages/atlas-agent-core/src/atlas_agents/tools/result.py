"""Functional outputs and operational results of tool execution."""

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import Field, field_validator, model_validator

from atlas_agents._models import (
    _FrozenModel,
    _json_mapping,
    _json_value,
    _non_empty,
    _timezone_aware,
)


class ToolExecutionStatus(StrEnum):
    """Enumerate the small set of normalized tool execution outcomes."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"
    INVALID_ARGUMENTS = "invalid_arguments"
    CANCELLED = "cancelled"


class ToolOutput(_FrozenModel):
    """Carry a tool-specific value after validating its JSON compatibility."""

    content: object | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: object) -> object:
        """Reject raw domain or infrastructure objects at the boundary."""
        return _json_value(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep output metadata JSON-compatible and isolated."""
        return _json_mapping(value)


class ToolExecutionError(_FrozenModel):
    """Describe a safe normalized failure without retaining an exception."""

    code: str
    message: str
    retryable: bool = False
    details: dict[str, object] = Field(default_factory=dict)

    @field_validator("code", "message")
    @classmethod
    def validate_text(cls, value: str) -> str:
        """Reject empty error codes and messages."""
        return _non_empty(value)

    @field_validator("details")
    @classmethod
    def validate_details(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep safe details JSON-compatible and isolated."""
        return _json_mapping(value)


class ToolExecutionResult(_FrozenModel):
    """Represent the normalized operational result of one tool call."""

    tool_call_id: str
    tool_name: str
    status: ToolExecutionStatus
    output: ToolOutput | None = None
    error: ToolExecutionError | None = None
    started_at: datetime
    completed_at: datetime
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("tool_call_id", "tool_name")
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        """Reject empty call identifiers and tool names."""
        return _non_empty(value)

    @field_validator("started_at", "completed_at")
    @classmethod
    def validate_timestamps(cls, value: datetime, info: object) -> datetime:
        """Require timezone-aware execution timestamps."""
        field_name = getattr(info, "field_name", "tool_execution")
        return _timezone_aware(value, label=str(field_name))

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep result metadata JSON-compatible and isolated."""
        return _json_mapping(value)

    @model_validator(mode="after")
    def validate_result_invariants(self) -> Self:
        """Keep status, output, error, and timestamps mutually consistent."""
        if self.completed_at < self.started_at:
            msg = "O término da ferramenta não pode anteceder seu início"
            raise ValueError(msg)
        if self.status is ToolExecutionStatus.SUCCEEDED:
            if self.output is None or self.error is not None:
                msg = "Uma execução bem-sucedida exige output e não aceita erro"
                raise ValueError(msg)
        elif self.output is not None:
            msg = "Uma execução sem sucesso não pode conter output"
            raise ValueError(msg)
        if (
            self.status
            in {
                ToolExecutionStatus.FAILED,
                ToolExecutionStatus.DENIED,
                ToolExecutionStatus.INVALID_ARGUMENTS,
            }
            and self.error is None
        ):
            msg = "O status informado exige um erro estruturado"
            raise ValueError(msg)
        return self

    @property
    def duration_seconds(self) -> float:
        """Return the observed wall-clock duration in seconds."""
        return (self.completed_at - self.started_at).total_seconds()
