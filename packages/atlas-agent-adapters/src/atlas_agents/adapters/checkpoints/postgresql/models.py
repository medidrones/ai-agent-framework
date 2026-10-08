"""Immutable optimistic-concurrency models for PostgreSQL checkpoints."""

from pydantic import Field

from atlas_agents.adapters.models import FrozenAdapterModel
from atlas_agents.runtime import ExecutionCheckpoint


class PostgreSQLCheckpointSnapshot(FrozenAdapterModel):
    """Carry one checkpoint and its independent storage revision."""

    checkpoint: ExecutionCheckpoint
    revision: int = Field(gt=0)
