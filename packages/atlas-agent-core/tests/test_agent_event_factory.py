"""Tests for per-execution monotonic agent event factories."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from atlas_agents import (
    AgentEventFactory,
    AgentEventType,
    ExecutionStatus,
    ExecutionTransition,
)


def test_factory_creates_event_with_sequence_starting_at_one() -> None:
    factory = AgentEventFactory("execution-1")

    event = factory.create(
        AgentEventType.EXECUTION_STARTED,
        data={"source": "test"},
    )

    assert factory.execution_id == "execution-1"
    assert event.execution_id == "execution-1"
    assert event.sequence == 1
    assert event.event_type is AgentEventType.EXECUTION_STARTED
    assert event.data == {"source": "test"}
    assert event.timestamp.tzinfo is UTC
    UUID(event.event_id)


def test_factory_increments_sequence_exactly_once_per_event() -> None:
    factory = AgentEventFactory("execution")

    events = [
        factory.create(AgentEventType.EXECUTION_CREATED),
        factory.create(AgentEventType.EXECUTION_STARTED),
        factory.create(AgentEventType.MODEL_EXECUTION_STARTED),
    ]

    assert [event.sequence for event in events] == [1, 2, 3]


def test_factories_keep_independent_sequences() -> None:
    factory_a = AgentEventFactory("execution-a")
    factory_b = AgentEventFactory("execution-b")

    first_a = factory_a.create(AgentEventType.EXECUTION_CREATED)
    first_b = factory_b.create(AgentEventType.EXECUTION_CREATED)
    second_a = factory_a.create(AgentEventType.EXECUTION_STARTED)

    assert first_a.sequence == 1
    assert first_b.sequence == 1
    assert second_a.sequence == 2


def test_factory_preserves_explicit_timezone_aware_timestamp() -> None:
    factory = AgentEventFactory("execution")
    timestamp = datetime(2026, 9, 1, 15, 0, tzinfo=UTC)

    event = factory.create(AgentEventType.EXECUTION_CREATED, timestamp=timestamp)

    assert event.timestamp is timestamp


def test_factory_rejects_blank_execution_id() -> None:
    with pytest.raises(ValueError, match="não pode estar vazio"):
        AgentEventFactory(" ")


def test_failed_event_creation_does_not_consume_sequence() -> None:
    factory = AgentEventFactory("execution")

    with pytest.raises(ValidationError):
        factory.create(
            AgentEventType.EXECUTION_CREATED,
            timestamp=datetime(2026, 9, 1),
        )

    event = factory.create(AgentEventType.EXECUTION_CREATED)
    assert event.sequence == 1


def test_factory_converts_transition_to_status_changed_event() -> None:
    timestamp = datetime(2026, 9, 1, 16, 0, tzinfo=UTC)
    transition = ExecutionTransition(
        from_status=ExecutionStatus.RUNNING,
        to_status=ExecutionStatus.VALIDATING_OUTPUT,
        timestamp=timestamp,
        reason="Resposta disponível.",
    )
    factory = AgentEventFactory("execution")

    event = factory.from_transition(transition)

    assert event.event_type is AgentEventType.EXECUTION_STATUS_CHANGED
    assert event.timestamp is timestamp
    assert event.data == {
        "from_status": "running",
        "to_status": "validating_output",
        "reason": "Resposta disponível.",
    }


def test_factory_event_is_immutable_and_serializable() -> None:
    event = AgentEventFactory("execution").create(AgentEventType.EXECUTION_TIMED_OUT)

    with pytest.raises(ValidationError):
        event.sequence = 2

    serialized = event.model_dump(mode="json")
    assert serialized["event_type"] == "execution_timed_out"
    assert serialized["sequence"] == 1
