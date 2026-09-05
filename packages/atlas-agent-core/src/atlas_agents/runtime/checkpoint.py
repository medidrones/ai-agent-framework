"""Serializable checkpoints and storage abstraction for execution resumption."""

import math
from datetime import datetime
from enum import StrEnum
from typing import Protocol, Self

from pydantic import Field, field_validator, model_validator

from atlas_agents._models import (
    _FrozenModel,
    _json_mapping,
    _non_empty,
    _timezone_aware,
)
from atlas_agents.agents import (
    AgentContext,
    AgentDefinition,
    AgentInput,
    ExecutionStatus,
    Usage,
)
from atlas_agents.approvals import ApprovalDecision, ApprovalRequest, ResumeToken
from atlas_agents.events import AgentEvent
from atlas_agents.execution import ExecutionTransition
from atlas_agents.models import ModelMessage, ModelSelectionResult, ToolCall
from atlas_agents.runtime.budget import ExecutionBudget
from atlas_agents.runtime.limits import ExecutionLimits
from atlas_agents.runtime.tool_calls import ToolCallRecord

CURRENT_CHECKPOINT_VERSION = 1


class ExecutionMode(StrEnum):
    """Preserve the model transport used by a suspended execution."""

    RUN = "run"
    STREAM = "stream"


class ExecutionCheckpoint(_FrozenModel):
    """Persist only serializable Atlas contracts required for safe resumption."""

    checkpoint_version: int = Field(gt=0)
    execution_id: str
    execution_mode: ExecutionMode
    agent: AgentDefinition
    input_data: AgentInput
    context: AgentContext
    status: ExecutionStatus
    messages: tuple[ModelMessage, ...]
    model_selection: ModelSelectionResult
    usage: Usage
    has_model_usage: bool = False
    turn_count: int = Field(ge=0)
    tool_call_count: int = Field(ge=0)
    events: tuple[AgentEvent, ...]
    transitions: tuple[ExecutionTransition, ...]
    tool_call_records: tuple[ToolCallRecord, ...]
    pending_approval: ApprovalRequest
    pending_tool_calls: tuple[ToolCall, ...]
    approval_history: tuple[ApprovalDecision, ...] = ()
    limits: ExecutionLimits
    budget: ExecutionBudget
    remaining_timeout_seconds: float | None = Field(default=None, ge=0)
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("execution_id")
    @classmethod
    def validate_execution_id(cls, value: str) -> str:
        """Reject an empty execution identifier."""
        return _non_empty(value)

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        """Require timezone-aware checkpoint timestamps."""
        return _timezone_aware(value, label="do checkpoint")

    @field_validator("remaining_timeout_seconds")
    @classmethod
    def validate_remaining_timeout(cls, value: float | None) -> float | None:
        """Reject a non-finite remaining duration."""
        if value is not None and not math.isfinite(value):
            raise ValueError("O timeout restante deve ser finito")
        return value

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep checkpoint metadata JSON-compatible and isolated."""
        return _json_mapping(value)

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        """Validate identities, journals, pending work, and temporal facts."""
        if self.status is not ExecutionStatus.WAITING_FOR_APPROVAL:
            raise ValueError("O checkpoint deve aguardar aprovação")
        if self.context.execution_id != self.execution_id:
            raise ValueError("O contexto deve pertencer ao checkpoint")
        if self.pending_approval.execution_id != self.execution_id:
            raise ValueError("A aprovação pendente deve pertencer ao checkpoint")
        if self.pending_approval.agent_id != self.agent.agent_id:
            raise ValueError("A aprovação pendente deve pertencer ao agente")
        if not self.pending_tool_calls:
            raise ValueError("O checkpoint deve preservar a chamada pendente")
        pending_call = self.pending_tool_calls[0]
        subject = self.pending_approval.subject
        if (
            pending_call.tool_call_id != subject.tool_call_id
            or pending_call.name != subject.tool_name
        ):
            raise ValueError("A chamada pendente deve coincidir com a aprovação")
        if self.updated_at < self.created_at:
            raise ValueError("A atualização não pode anteceder a criação")
        if self.events:
            expected = tuple(range(1, len(self.events) + 1))
            if tuple(event.sequence for event in self.events) != expected:
                raise ValueError("Os eventos do checkpoint devem ser contínuos")
            if any(event.execution_id != self.execution_id for event in self.events):
                raise ValueError("Os eventos devem pertencer ao checkpoint")
        if not self.transitions or self.transitions[-1].to_status is not self.status:
            raise ValueError("O histórico deve terminar no status do checkpoint")
        return self


class CheckpointStore(Protocol):
    """Persist checkpoints and atomically consume single-use resume tokens."""

    async def save(
        self,
        *,
        resume_token: ResumeToken,
        checkpoint: ExecutionCheckpoint,
    ) -> None:
        """Persist one checkpoint under an opaque token."""
        ...

    async def consume(self, resume_token: ResumeToken) -> ExecutionCheckpoint:
        """Atomically return a checkpoint while invalidating its token."""
        ...
