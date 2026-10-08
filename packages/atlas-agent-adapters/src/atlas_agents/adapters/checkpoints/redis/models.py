"""Immutable models for Redis checkpoint persistence."""

from enum import StrEnum

from pydantic import Field

from atlas_agents.adapters.models import FrozenAdapterModel
from atlas_agents.runtime import ExecutionCheckpoint


class RedisCheckpointSnapshot(FrozenAdapterModel):
    """Carry one checkpoint and its independent storage revision."""

    checkpoint: ExecutionCheckpoint
    revision: int = Field(gt=0)


class RedisConsumeReconciliationStatus(StrEnum):
    """Classify the durable result of one identified consume attempt."""

    APPLIED = "applied"
    AVAILABLE = "available"
    NOT_APPLIED = "not_applied"
    UNKNOWN = "unknown"


class RedisConsumeReconciliation(FrozenAdapterModel):
    """Expose a safe durable reconciliation result without checkpoint data."""

    status: RedisConsumeReconciliationStatus
    state: str
