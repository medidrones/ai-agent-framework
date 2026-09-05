"""Immutable requests and safe subjects presented for human approval."""

from datetime import datetime
from typing import Self

from pydantic import Field, field_validator, model_validator

from atlas_agents._models import (
    _FrozenModel,
    _json_mapping,
    _non_empty,
    _timezone_aware,
)
from atlas_agents.approvals.types import ApprovalKind


class ToolApprovalSubject(_FrozenModel):
    """Describe a tool call without exposing its argument values."""

    tool_call_id: str
    tool_name: str
    argument_keys: tuple[str, ...] = ()

    @field_validator("tool_call_id", "tool_name")
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        """Reject empty tool call identifiers and names."""
        return _non_empty(value)

    @field_validator("argument_keys")
    @classmethod
    def validate_argument_keys(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Require unique safe keys while preserving their order."""
        validated = tuple(_non_empty(item) for item in value)
        if len(set(validated)) != len(validated):
            raise ValueError("As chaves de argumentos não podem se repetir")
        return validated


class ApprovalRequest(_FrozenModel):
    """Carry the safe facts needed by an external approval interface."""

    approval_request_id: str
    execution_id: str
    agent_id: str
    kind: ApprovalKind = ApprovalKind.TOOL_EXECUTION
    summary: str
    reason: str
    requested_at: datetime
    expires_at: datetime | None = None
    subject: ToolApprovalSubject
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator(
        "approval_request_id", "execution_id", "agent_id", "summary", "reason"
    )
    @classmethod
    def validate_text(cls, value: str) -> str:
        """Reject empty identifiers and human-facing descriptions."""
        return _non_empty(value)

    @field_validator("requested_at", "expires_at")
    @classmethod
    def validate_timestamps(cls, value: datetime | None) -> datetime | None:
        """Require timezone-aware request timestamps."""
        if value is None:
            return None
        return _timezone_aware(value, label="da solicitação de aprovação")

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep metadata JSON-compatible and isolated."""
        return _json_mapping(value)

    @model_validator(mode="after")
    def validate_expiration(self) -> Self:
        """Reject expiration timestamps preceding the request."""
        if self.expires_at is not None and self.expires_at < self.requested_at:
            raise ValueError("A expiração não pode anteceder a solicitação")
        return self
