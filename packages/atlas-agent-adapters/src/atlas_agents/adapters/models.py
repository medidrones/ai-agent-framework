"""Wire-neutral immutable application DTOs for external adapters."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator


class FrozenAdapterModel(BaseModel):
    """Provide the common immutable and closed DTO boundary."""

    model_config = ConfigDict(frozen=True, extra="forbid")


def _required(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("O valor não pode ser vazio")
    return normalized


class TransportPrincipal(FrozenAdapterModel):
    """Represent a principal already authenticated by the host transport."""

    subject: str
    tenant: str | None = None
    authentication_method: str | None = None
    claims: dict[str, JsonValue] = Field(default_factory=dict, repr=False)

    _validate_subject = field_validator("subject")(_required)


class ExternalAttachment(FrozenAdapterModel):
    """Represent one URI-based attachment at the application boundary."""

    attachment_id: str
    name: str
    media_type: str
    uri: str
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    _validate_text = field_validator("attachment_id", "name", "media_type", "uri")(
        _required
    )


class ExternalAgentInput(FrozenAdapterModel):
    """Carry text and URI references without accepting Python objects."""

    message: str
    attachments: tuple[ExternalAttachment, ...] = ()
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class ExternalExecutionContext(FrozenAdapterModel):
    """Carry untrusted correlation context without identity fields."""

    session_id: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class RequestedExecutionLimits(FrozenAdapterModel):
    """Represent caller requests that a server policy must constrain."""

    max_turns: int | None = Field(default=None, gt=0)
    max_tool_calls: int | None = Field(default=None, gt=0)
    max_input_tokens: int | None = Field(default=None, gt=0)
    max_output_tokens: int | None = Field(default=None, gt=0)
    max_total_tokens: int | None = Field(default=None, gt=0)
    timeout_seconds: float | None = Field(default=None, gt=0)


class RequestedExecutionBudget(FrozenAdapterModel):
    """Represent a requested cost ceiling constrained by server policy."""

    max_estimated_cost: Decimal | None = Field(default=None, ge=Decimal(0))
    currency: str | None = None


class ExecuteAgentRequest(FrozenAdapterModel):
    """Coordinate one external execution without caller-controlled identity."""

    request_id: str
    agent_id: str
    input: ExternalAgentInput
    principal: TransportPrincipal = Field(repr=False, exclude=True)
    context: ExternalExecutionContext = ExternalExecutionContext()
    requested_limits: RequestedExecutionLimits | None = None
    requested_budget: RequestedExecutionBudget | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, repr=False, exclude=True)

    _validate_ids = field_validator("request_id", "agent_id")(_required)


class ResumeExecutionRequest(FrozenAdapterModel):
    """Coordinate a resume with an opaque bearer token kept out of repr."""

    request_id: str
    agent_id: str
    resume_token: str = Field(repr=False)
    approval_request_id: str
    decision: Literal["approve", "reject"]
    principal: TransportPrincipal = Field(repr=False, exclude=True)
    reason: str | None = None
    decided_at: datetime
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, repr=False, exclude=True)

    _validate_ids = field_validator(
        "request_id", "agent_id", "resume_token", "approval_request_id"
    )(_required)


class AdapterExecutionStatus(StrEnum):
    """Expose stable lowercase execution outcomes on external wires."""

    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    LIMIT_EXCEEDED = "limit_exceeded"
    BUDGET_EXCEEDED = "budget_exceeded"
    REJECTED = "rejected"
    WAITING_FOR_APPROVAL = "waiting_for_approval"


class AdapterErrorResponse(FrozenAdapterModel):
    """Expose a safe stable error without exception implementation details."""

    code: str
    message: str
    retryable: bool = False
    details: dict[str, JsonValue] = Field(default_factory=dict)


class UsageDTO(FrozenAdapterModel):
    """Expose provider-neutral usage accounting."""

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(ge=0)
    reasoning_tokens: int = Field(ge=0)
    estimated_cost: Decimal | None = Field(default=None, ge=Decimal(0))


class CitationDTO(FrozenAdapterModel):
    """Expose citation references without passage content."""

    citation_key: str
    source_id: str
    document_id: str
    passage_id: str
    title: str | None = None
    uri: str | None = None
    page: int | None = None
    section: str | None = None


class ApprovalSubjectDTO(FrozenAdapterModel):
    """Expose a safe approval subject without argument values."""

    tool_call_id: str
    tool_name: str
    argument_keys: tuple[str, ...] = ()


class ApprovalRequestDTO(FrozenAdapterModel):
    """Expose the facts needed by an external approval interface."""

    approval_request_id: str
    execution_id: str
    agent_id: str
    kind: str
    summary: str
    reason: str
    requested_at: datetime
    expires_at: datetime | None = None
    subject: ApprovalSubjectDTO


class ExecutionSuspensionDTO(FrozenAdapterModel):
    """Expose a resumable HITL boundary with a protected token field."""

    execution_id: str
    approval_request: ApprovalRequestDTO
    resume_token: str = Field(repr=False)
    checkpoint_version: int = Field(gt=0)
    created_at: datetime


class ExecuteAgentResponse(FrozenAdapterModel):
    """Expose one terminal or suspended execution outcome."""

    request_id: str
    execution_id: str
    status: AdapterExecutionStatus
    output: JsonValue | None = None
    error: AdapterErrorResponse | None = None
    usage: UsageDTO | None = None
    citations: tuple[CitationDTO, ...] = ()
    suspension: ExecutionSuspensionDTO | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class ExecutionStreamItem(FrozenAdapterModel):
    """Expose one versioned ordered stream item without Python class names."""

    type: str
    sequence: int = Field(ge=0)
    execution_id: str
    data: dict[str, JsonValue] = Field(default_factory=dict)


class ReadinessResponse(FrozenAdapterModel):
    """Describe readiness without invoking external providers."""

    ready: bool
    checks: dict[str, bool] = Field(default_factory=dict)
