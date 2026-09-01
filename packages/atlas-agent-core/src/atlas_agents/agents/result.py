"""Immutable results and usage accounting for agent executions."""

from decimal import Decimal
from typing import Self

from pydantic import Field, field_validator, model_validator

from atlas_agents._models import _FrozenModel, _non_empty
from atlas_agents.agents.errors import AgentErrorInfo
from atlas_agents.agents.status import ExecutionStatus
from atlas_agents.events import AgentEvent


class Usage(_FrozenModel):
    """Record provider-neutral token usage and optional estimated monetary cost."""

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    estimated_cost: Decimal | None = Field(default=None, ge=Decimal(0))

    @property
    def total_tokens(self) -> int:
        """Calculate total tokens without storing duplicated state."""
        return self.input_tokens + self.output_tokens


class AgentResult[TOutput](_FrozenModel):
    """Represent an immutable snapshot returned by an agent execution."""

    execution_id: str
    status: ExecutionStatus
    output: TOutput | None = None
    usage: Usage
    events: tuple[AgentEvent, ...] = ()
    error: AgentErrorInfo | None = None

    @field_validator("execution_id")
    @classmethod
    def validate_execution_id(cls, value: str) -> str:
        """Reject an empty execution identifier."""
        return _non_empty(value)

    @model_validator(mode="after")
    def validate_status_error_consistency(self) -> Self:
        """Enforce only the fundamental completed and failed invariants."""
        if self.status is ExecutionStatus.COMPLETED and self.error is not None:
            msg = "Um resultado concluído não pode conter erro"
            raise ValueError(msg)
        if self.status is ExecutionStatus.FAILED and self.error is None:
            msg = "Um resultado com falha deve conter um erro"
            raise ValueError(msg)
        return self
