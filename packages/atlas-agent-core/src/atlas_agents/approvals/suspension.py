"""Serializable public suspension and opaque resume token contracts."""

import secrets
from datetime import datetime
from typing import Self

from pydantic import Field, field_validator, model_validator

from atlas_agents._models import _FrozenModel, _non_empty, _timezone_aware
from atlas_agents.agents import ExecutionStatus
from atlas_agents.approvals.request import ApprovalRequest


class ResumeToken(_FrozenModel):
    """Carry an opaque capability-like identifier for one resume attempt."""

    value: str

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        """Reject empty token values."""
        return _non_empty(value)

    @classmethod
    def create(cls) -> "ResumeToken":
        """Create a cryptographically unpredictable opaque token."""
        return cls(value=secrets.token_urlsafe(32))


class ExecutionSuspension(_FrozenModel):
    """Return a resumable non-terminal approval boundary to the consumer."""

    execution_id: str
    status: ExecutionStatus = ExecutionStatus.WAITING_FOR_APPROVAL
    approval_request: ApprovalRequest
    resume_token: ResumeToken
    checkpoint_version: int = Field(gt=0)
    created_at: datetime

    @field_validator("execution_id")
    @classmethod
    def validate_execution_id(cls, value: str) -> str:
        """Reject an empty execution identifier."""
        return _non_empty(value)

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        """Require a timezone-aware suspension timestamp."""
        return _timezone_aware(value, label="da suspensão")

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        """Require a waiting status and matching execution identity."""
        if self.status is not ExecutionStatus.WAITING_FOR_APPROVAL:
            raise ValueError("Uma suspensão deve aguardar aprovação")
        if self.approval_request.execution_id != self.execution_id:
            raise ValueError("A solicitação deve pertencer à execução suspensa")
        return self
