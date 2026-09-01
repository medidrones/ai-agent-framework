"""Immutable snapshots of validated execution status transitions."""

from datetime import datetime
from typing import Self

from pydantic import Field, field_validator, model_validator

from atlas_agents._models import (
    _FrozenModel,
    _json_mapping,
    _non_empty,
    _timezone_aware,
)
from atlas_agents.agents.status import ExecutionStatus


class ExecutionTransition(_FrozenModel):
    """Record one validated movement between two execution statuses."""

    from_status: ExecutionStatus
    to_status: ExecutionStatus
    timestamp: datetime
    reason: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        """Require an explicit timezone on transition timestamps."""
        return _timezone_aware(value, label="da transição")

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str | None) -> str | None:
        """Reject an explicitly provided empty transition reason."""
        return None if value is None else _non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep metadata serializable and isolated from caller mutation."""
        return _json_mapping(value)

    @model_validator(mode="after")
    def validate_distinct_statuses(self) -> Self:
        """Reject transitions that do not change execution status."""
        if self.from_status is self.to_status:
            msg = "Uma transição deve alterar o status da execução"
            raise ValueError(msg)
        return self
