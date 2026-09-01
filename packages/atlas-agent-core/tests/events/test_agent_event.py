"""Tests for immutable and serializable agent events."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from atlas_agents import AgentEvent, AgentEventType


def _event() -> AgentEvent:
    return AgentEvent(
        event_id="event-1",
        execution_id="execution-1",
        sequence=0,
        event_type=AgentEventType.EXECUTION_CREATED,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        data={"source": "test"},
    )


def test_agent_event_accepts_timezone_aware_timestamp() -> None:
    event = _event()

    assert event.timestamp.utcoffset() is not None
    assert event.model_dump(mode="json")["event_type"] == "execution_created"


def test_agent_event_rejects_negative_sequence() -> None:
    with pytest.raises(ValidationError):
        AgentEvent(
            event_id="event",
            execution_id="execution",
            sequence=-1,
            event_type=AgentEventType.EXECUTION_CREATED,
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        )


def test_agent_event_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        AgentEvent(
            event_id="event",
            execution_id="execution",
            sequence=0,
            event_type=AgentEventType.EXECUTION_STARTED,
            timestamp=datetime(2026, 1, 1),
        )


def test_agent_event_is_immutable() -> None:
    event = _event()

    with pytest.raises(ValidationError):
        event.sequence = 1


def test_agent_event_rejects_blank_identifiers() -> None:
    with pytest.raises(ValidationError):
        AgentEvent(
            event_id=" ",
            execution_id="execution",
            sequence=0,
            event_type=AgentEventType.EXECUTION_FAILED,
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        )


def test_agent_event_rejects_non_serializable_data() -> None:
    with pytest.raises(ValidationError):
        AgentEvent(
            event_id="event",
            execution_id="execution",
            sequence=0,
            event_type=AgentEventType.EXECUTION_CANCELLED,
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            data={"invalid": object()},
        )
