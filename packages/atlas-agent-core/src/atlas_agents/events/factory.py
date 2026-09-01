"""Per-execution factory for consistently sequenced agent events."""

from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import uuid4

from atlas_agents._models import _non_empty
from atlas_agents.events.base import AgentEvent
from atlas_agents.events.types import AgentEventType
from atlas_agents.execution.transition import ExecutionTransition


class AgentEventFactory:
    """Create monotonic events for one execution without global state.

    Instances are execution-scoped and are not safe to share between threads or
    across executions.
    """

    def __init__(self, execution_id: str) -> None:
        """Initialize an independent sequence for one opaque execution ID."""
        self._execution_id = _non_empty(execution_id)
        self._sequence = 0

    @property
    def execution_id(self) -> str:
        """Return the opaque execution identifier owned by this factory."""
        return self._execution_id

    def create(
        self,
        event_type: AgentEventType,
        *,
        data: Mapping[str, object] | None = None,
        timestamp: datetime | None = None,
    ) -> AgentEvent:
        """Create the next event, starting at sequence one and incrementing by one."""
        next_sequence = self._sequence + 1
        event = AgentEvent(
            event_id=str(uuid4()),
            execution_id=self._execution_id,
            sequence=next_sequence,
            event_type=event_type,
            timestamp=timestamp if timestamp is not None else datetime.now(UTC),
            data=dict(data) if data is not None else {},
        )
        self._sequence = next_sequence
        return event

    def from_transition(self, transition: ExecutionTransition) -> AgentEvent:
        """Create a status-change event from an immutable transition snapshot."""
        data: dict[str, object] = {
            "from_status": transition.from_status.value,
            "to_status": transition.to_status.value,
            "reason": transition.reason,
        }
        return self.create(
            AgentEventType.EXECUTION_STATUS_CHANGED,
            data=data,
            timestamp=transition.timestamp,
        )
