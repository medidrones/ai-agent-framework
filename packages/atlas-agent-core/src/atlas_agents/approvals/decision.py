"""Immutable human approval decisions."""

from datetime import datetime

from pydantic import Field, field_validator

from atlas_agents._models import (
    _FrozenModel,
    _json_mapping,
    _non_empty,
    _timezone_aware,
)
from atlas_agents.agents import ExecutionIdentity
from atlas_agents.approvals.types import ApprovalDecisionType


class ApprovalDecision(_FrozenModel):
    """Record one explicit approve or reject decision."""

    approval_request_id: str
    decision: ApprovalDecisionType
    decided_at: datetime
    decided_by: ExecutionIdentity | None = None
    reason: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("approval_request_id")
    @classmethod
    def validate_request_id(cls, value: str) -> str:
        """Reject an empty approval request identifier."""
        return _non_empty(value)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str | None) -> str | None:
        """Reject an explicitly empty decision reason."""
        return None if value is None else _non_empty(value)

    @field_validator("decided_at")
    @classmethod
    def validate_decided_at(cls, value: datetime) -> datetime:
        """Require a timezone-aware decision timestamp."""
        return _timezone_aware(value, label="da decisão de aprovação")

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep decision metadata JSON-compatible and isolated."""
        return _json_mapping(value)
