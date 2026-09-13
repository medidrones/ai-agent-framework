"""Stable JSON models for the REST v1 wire contract."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class WireModel(BaseModel):
    """Reject undeclared fields at the public REST boundary."""

    model_config = ConfigDict(extra="forbid")


class AttachmentV1(WireModel):
    """Represent a URI-based attachment."""

    attachment_id: str
    name: str
    media_type: str
    uri: str
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class AgentInputV1(WireModel):
    """Represent agent text and attachment input."""

    message: str
    attachments: list[AttachmentV1] = Field(default_factory=list)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class ExecutionContextV1(WireModel):
    """Represent caller correlation context without trusted identity."""

    session_id: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class RequestedLimitsV1(WireModel):
    """Represent requested execution ceilings."""

    max_turns: int | None = Field(default=None, gt=0)
    max_tool_calls: int | None = Field(default=None, gt=0)
    max_input_tokens: int | None = Field(default=None, gt=0)
    max_output_tokens: int | None = Field(default=None, gt=0)
    max_total_tokens: int | None = Field(default=None, gt=0)
    timeout_seconds: float | None = Field(default=None, gt=0)


class RequestedBudgetV1(WireModel):
    """Represent a requested monetary ceiling."""

    max_estimated_cost: Decimal | None = Field(default=None, ge=Decimal(0))
    currency: str | None = None


class ExecuteRequestV1(WireModel):
    """Define the REST v1 execution body without identity fields."""

    request_id: str
    agent_id: str
    input: AgentInputV1
    context: ExecutionContextV1 = Field(default_factory=ExecutionContextV1)
    requested_limits: RequestedLimitsV1 | None = None
    requested_budget: RequestedBudgetV1 | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class ResumeRequestV1(WireModel):
    """Define the REST v1 resume body with the bearer token outside the URL."""

    request_id: str
    agent_id: str
    resume_token: str = Field(repr=False)
    approval_request_id: str
    decision: str
    reason: str | None = None
    decided_at: datetime
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class ErrorV1(WireModel):
    """Expose one stable transport or execution error."""

    code: str
    message: str
    retryable: bool = False
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ExecuteResponseV1(WireModel):
    """Expose stable execution outcome fields as JSON."""

    request_id: str
    execution_id: str
    status: str
    output: JsonValue | None = None
    error: ErrorV1 | None = None
    usage: dict[str, JsonValue] | None = None
    citations: list[dict[str, JsonValue]] = Field(default_factory=list)
    suspension: dict[str, JsonValue] | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class StreamItemV1(WireModel):
    """Expose one ordered SSE item."""

    type: str
    sequence: int
    execution_id: str
    data: dict[str, JsonValue] = Field(default_factory=dict)


class HealthV1(WireModel):
    """Expose process liveness."""

    status: str


class ReadinessV1(WireModel):
    """Expose local application readiness."""

    ready: bool
    checks: dict[str, bool]
