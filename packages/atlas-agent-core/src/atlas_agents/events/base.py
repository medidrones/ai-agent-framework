"""Provider-neutral event snapshots produced by agents."""

from datetime import datetime

from pydantic import Field, field_validator

from atlas_agents._models import _FrozenModel, _json_mapping, _non_empty
from atlas_agents.events.types import AgentEventType


class AgentEvent(_FrozenModel):
    """Describe an immutable event associated with one agent execution."""

    event_id: str
    execution_id: str
    sequence: int = Field(ge=0)
    event_type: AgentEventType
    timestamp: datetime
    data: dict[str, object] = Field(default_factory=dict)

    @field_validator("event_id", "execution_id")
    @classmethod
    def validate_ids(cls, value: str) -> str:
        """Reject empty opaque identifiers."""
        return _non_empty(value)

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        """Require an explicit timezone on event timestamps."""
        if value.tzinfo is None or value.utcoffset() is None:
            msg = "O timestamp do evento deve possuir fuso horário"
            raise ValueError(msg)
        return value

    @field_validator("data")
    @classmethod
    def validate_data(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep event data serializable and isolated from caller mutation."""
        return _json_mapping(value)
