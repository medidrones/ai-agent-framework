"""Event types emitted by the fundamental agent contract."""

from enum import StrEnum


class AgentEventType(StrEnum):
    """Identify the minimal lifecycle event represented by an agent event."""

    EXECUTION_CREATED = "execution_created"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_CANCELLED = "execution_cancelled"
