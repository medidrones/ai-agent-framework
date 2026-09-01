"""Tests for immutable execution transition snapshots."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from atlas_agents import ExecutionStatus, ExecutionTransition


def test_transition_preserves_timestamp_reason_and_metadata() -> None:
    timestamp = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    metadata: dict[str, object] = {"attempt": 1}

    transition = ExecutionTransition(
        from_status=ExecutionStatus.RUNNING,
        to_status=ExecutionStatus.VALIDATING_OUTPUT,
        timestamp=timestamp,
        reason="Resposta produzida.",
        metadata=metadata,
    )
    metadata["attempt"] = 2

    assert transition.timestamp is timestamp
    assert transition.reason == "Resposta produzida."
    assert transition.metadata == {"attempt": 1}


def test_transition_rejects_equal_statuses() -> None:
    with pytest.raises(ValidationError):
        ExecutionTransition(
            from_status=ExecutionStatus.RUNNING,
            to_status=ExecutionStatus.RUNNING,
            timestamp=datetime(2026, 9, 1, tzinfo=UTC),
        )


def test_transition_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        ExecutionTransition(
            from_status=ExecutionStatus.CREATED,
            to_status=ExecutionStatus.VALIDATING_INPUT,
            timestamp=datetime(2026, 9, 1),
        )


def test_transition_rejects_blank_reason() -> None:
    with pytest.raises(ValidationError):
        ExecutionTransition(
            from_status=ExecutionStatus.CREATED,
            to_status=ExecutionStatus.VALIDATING_INPUT,
            timestamp=datetime(2026, 9, 1, tzinfo=UTC),
            reason=" ",
        )


def test_transition_is_immutable_and_serializable() -> None:
    transition = ExecutionTransition(
        from_status=ExecutionStatus.CREATED,
        to_status=ExecutionStatus.VALIDATING_INPUT,
        timestamp=datetime(2026, 9, 1, tzinfo=UTC),
    )

    with pytest.raises(ValidationError):
        transition.to_status = ExecutionStatus.FAILED

    serialized = transition.model_dump(mode="json")
    assert serialized["from_status"] == "created"
    assert serialized["to_status"] == "validating_input"
