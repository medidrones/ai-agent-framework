"""Immutable observation model for runtime execution state."""

from datetime import datetime
from typing import Self

from pydantic import Field, field_validator, model_validator

from atlas_agents._models import (
    _FrozenModel,
    _json_mapping,
    _non_empty,
    _timezone_aware,
)
from atlas_agents.agents.errors import AgentErrorInfo
from atlas_agents.agents.result import Usage
from atlas_agents.agents.status import ExecutionStatus
from atlas_agents.events import AgentEvent
from atlas_agents.models import ModelMessage, ModelSelectionResult


class ExecutionSnapshot(_FrozenModel):
    """Represent an immutable and serializable observation of one execution."""

    execution_id: str
    agent_id: str
    status: ExecutionStatus
    messages: tuple[ModelMessage, ...] = ()
    model_selection: ModelSelectionResult | None = None
    usage: Usage = Usage()
    turn_count: int = Field(default=0, ge=0)
    tool_call_count: int = Field(default=0, ge=0)
    events: tuple[AgentEvent, ...] = ()
    output: object | None = None
    error: AgentErrorInfo | None = None
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("execution_id", "agent_id")
    @classmethod
    def validate_ids(cls, value: str) -> str:
        """Reject empty execution and agent identifiers."""
        return _non_empty(value)

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        """Require timezone-aware snapshot timestamps."""
        return _timezone_aware(value, label="do snapshot")

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep snapshot metadata serializable and isolated."""
        return _json_mapping(value)

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        """Keep timestamps and terminal output/error facts internally consistent."""
        if self.updated_at < self.created_at:
            msg = "O timestamp de atualização não pode preceder a criação"
            raise ValueError(msg)
        if self.status is ExecutionStatus.COMPLETED and self.error is not None:
            msg = "Um snapshot concluído não pode conter erro"
            raise ValueError(msg)
        if self.status is ExecutionStatus.FAILED and self.error is None:
            msg = "Um snapshot com falha deve conter um erro"
            raise ValueError(msg)
        return self
