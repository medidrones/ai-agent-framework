"""Versioned provider-neutral messaging contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Protocol

from pydantic import Field, JsonValue, field_validator

from atlas_agents.adapters.models import (
    ExternalAgentInput,
    ExternalExecutionContext,
    FrozenAdapterModel,
    RequestedExecutionBudget,
    RequestedExecutionLimits,
    TransportPrincipal,
)


class EventPublicationMode(StrEnum):
    """Control broker volume explicitly."""

    TERMINAL_ONLY = "terminal_only"
    STREAM_EVENTS = "stream_events"


class EventAdapterConfig(FrozenAdapterModel):
    """Configure messaging behavior without connecting to a broker."""

    publication_mode: EventPublicationMode = EventPublicationMode.TERMINAL_ONLY
    schema_version: int = Field(default=1, ge=1)


class MessageEnvelope(FrozenAdapterModel):
    """Carry one versioned command or event with causal identifiers."""

    message_id: str
    message_type: str
    schema_version: int = Field(ge=1)
    correlation_id: str
    causation_id: str | None = None
    timestamp: datetime
    payload: dict[str, JsonValue]

    @field_validator("message_id", "message_type", "correlation_id")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        """Reject empty envelope identifiers."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("O identificador da mensagem não pode ser vazio")
        return normalized

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        """Require timezone-aware messaging timestamps."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("O timestamp da mensagem deve possuir fuso horário")
        return value


class ExecuteAgentCommand(FrozenAdapterModel):
    """Request agent execution without embedding trusted identity."""

    request_id: str
    agent_id: str
    input: ExternalAgentInput
    context: ExternalExecutionContext = ExternalExecutionContext()
    requested_limits: RequestedExecutionLimits | None = None
    requested_budget: RequestedExecutionBudget | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class ResumeExecutionCommand(FrozenAdapterModel):
    """Request checkpoint resume without identity assertions."""

    request_id: str
    agent_id: str
    resume_token: str = Field(repr=False)
    approval_request_id: str
    decision: str
    reason: str | None = None
    decided_at: datetime
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class TrustedMessageContext(FrozenAdapterModel):
    """Carry broker-authenticated principal separately from payload and headers."""

    principal: TransportPrincipal = Field(repr=False)
    allowed_headers: dict[str, str] = Field(default_factory=dict, repr=False)


class MessagePrincipalResolver(Protocol):
    """Resolve identity input from trusted broker delivery context only."""

    def resolve(
        self, envelope: MessageEnvelope, context: TrustedMessageContext
    ) -> TransportPrincipal:
        """Return a trusted principal without inspecting command payload."""
        ...


class TrustedContextPrincipalResolver:
    """Use the principal explicitly supplied by a broker-specific adapter."""

    def resolve(
        self, envelope: MessageEnvelope, context: TrustedMessageContext
    ) -> TransportPrincipal:
        """Return only the authenticated context principal."""
        del envelope
        return context.principal


class MessageProcessingResult(FrozenAdapterModel):
    """Tell a broker adapter whether processing should be acknowledged."""

    acknowledge: bool
    retryable: bool = False
    error_code: str | None = None
