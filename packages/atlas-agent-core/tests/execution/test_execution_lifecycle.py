"""Tests for the declarative execution lifecycle state machine."""

from datetime import UTC, datetime
from inspect import signature

import pytest
from pydantic import ValidationError

from atlas_agents import (
    ExecutionLifecycle,
    ExecutionStatus,
    InvalidExecutionTransitionError,
)

VALID_TRANSITIONS = (
    (ExecutionStatus.CREATED, ExecutionStatus.VALIDATING_INPUT),
    (ExecutionStatus.VALIDATING_INPUT, ExecutionStatus.LOADING_CONTEXT),
    (ExecutionStatus.LOADING_CONTEXT, ExecutionStatus.RUNNING),
    (ExecutionStatus.LOADING_CONTEXT, ExecutionStatus.RETRIEVING_KNOWLEDGE),
    (ExecutionStatus.RETRIEVING_KNOWLEDGE, ExecutionStatus.RUNNING),
    (ExecutionStatus.RUNNING, ExecutionStatus.VALIDATING_OUTPUT),
    (ExecutionStatus.VALIDATING_OUTPUT, ExecutionStatus.COMPLETED),
    (ExecutionStatus.VALIDATING_OUTPUT, ExecutionStatus.UPDATING_MEMORY),
    (ExecutionStatus.UPDATING_MEMORY, ExecutionStatus.COMPLETED),
    (ExecutionStatus.RUNNING, ExecutionStatus.WAITING_FOR_TOOL),
    (ExecutionStatus.WAITING_FOR_TOOL, ExecutionStatus.EXECUTING_TOOL),
    (ExecutionStatus.WAITING_FOR_TOOL, ExecutionStatus.RUNNING),
    (ExecutionStatus.EXECUTING_TOOL, ExecutionStatus.RUNNING),
    (ExecutionStatus.EXECUTING_TOOL, ExecutionStatus.WAITING_FOR_TOOL),
    (ExecutionStatus.WAITING_FOR_TOOL, ExecutionStatus.WAITING_FOR_APPROVAL),
    (ExecutionStatus.WAITING_FOR_APPROVAL, ExecutionStatus.EXECUTING_TOOL),
    (ExecutionStatus.WAITING_FOR_APPROVAL, ExecutionStatus.RUNNING),
    (ExecutionStatus.VALIDATING_OUTPUT, ExecutionStatus.RUNNING),
    (ExecutionStatus.VALIDATING_OUTPUT, ExecutionStatus.REJECTED),
)

INVALID_TRANSITIONS = (
    (ExecutionStatus.CREATED, ExecutionStatus.COMPLETED),
    (ExecutionStatus.COMPLETED, ExecutionStatus.RUNNING),
    (ExecutionStatus.FAILED, ExecutionStatus.CREATED),
    (ExecutionStatus.CANCELLED, ExecutionStatus.RUNNING),
    (ExecutionStatus.RUNNING, ExecutionStatus.CREATED),
    (ExecutionStatus.VALIDATING_OUTPUT, ExecutionStatus.WAITING_FOR_TOOL),
    (ExecutionStatus.CREATED, ExecutionStatus.TIMED_OUT),
)

TERMINAL_STATUSES = (
    ExecutionStatus.COMPLETED,
    ExecutionStatus.FAILED,
    ExecutionStatus.CANCELLED,
    ExecutionStatus.TIMED_OUT,
    ExecutionStatus.LIMIT_EXCEEDED,
    ExecutionStatus.BUDGET_EXCEEDED,
    ExecutionStatus.REJECTED,
)

PATHS_TO_STATUS: dict[ExecutionStatus, tuple[ExecutionStatus, ...]] = {
    ExecutionStatus.CREATED: (),
    ExecutionStatus.VALIDATING_INPUT: (ExecutionStatus.VALIDATING_INPUT,),
    ExecutionStatus.LOADING_CONTEXT: (
        ExecutionStatus.VALIDATING_INPUT,
        ExecutionStatus.LOADING_CONTEXT,
    ),
    ExecutionStatus.RETRIEVING_KNOWLEDGE: (
        ExecutionStatus.VALIDATING_INPUT,
        ExecutionStatus.LOADING_CONTEXT,
        ExecutionStatus.RETRIEVING_KNOWLEDGE,
    ),
    ExecutionStatus.RUNNING: (
        ExecutionStatus.VALIDATING_INPUT,
        ExecutionStatus.LOADING_CONTEXT,
        ExecutionStatus.RUNNING,
    ),
    ExecutionStatus.WAITING_FOR_TOOL: (
        ExecutionStatus.VALIDATING_INPUT,
        ExecutionStatus.LOADING_CONTEXT,
        ExecutionStatus.RUNNING,
        ExecutionStatus.WAITING_FOR_TOOL,
    ),
    ExecutionStatus.WAITING_FOR_APPROVAL: (
        ExecutionStatus.VALIDATING_INPUT,
        ExecutionStatus.LOADING_CONTEXT,
        ExecutionStatus.RUNNING,
        ExecutionStatus.WAITING_FOR_TOOL,
        ExecutionStatus.WAITING_FOR_APPROVAL,
    ),
    ExecutionStatus.EXECUTING_TOOL: (
        ExecutionStatus.VALIDATING_INPUT,
        ExecutionStatus.LOADING_CONTEXT,
        ExecutionStatus.RUNNING,
        ExecutionStatus.WAITING_FOR_TOOL,
        ExecutionStatus.EXECUTING_TOOL,
    ),
    ExecutionStatus.VALIDATING_OUTPUT: (
        ExecutionStatus.VALIDATING_INPUT,
        ExecutionStatus.LOADING_CONTEXT,
        ExecutionStatus.RUNNING,
        ExecutionStatus.VALIDATING_OUTPUT,
    ),
    ExecutionStatus.UPDATING_MEMORY: (
        ExecutionStatus.VALIDATING_INPUT,
        ExecutionStatus.LOADING_CONTEXT,
        ExecutionStatus.RUNNING,
        ExecutionStatus.VALIDATING_OUTPUT,
        ExecutionStatus.UPDATING_MEMORY,
    ),
    ExecutionStatus.COMPLETED: (
        ExecutionStatus.VALIDATING_INPUT,
        ExecutionStatus.LOADING_CONTEXT,
        ExecutionStatus.RUNNING,
        ExecutionStatus.VALIDATING_OUTPUT,
        ExecutionStatus.COMPLETED,
    ),
    ExecutionStatus.FAILED: (ExecutionStatus.FAILED,),
    ExecutionStatus.CANCELLED: (ExecutionStatus.CANCELLED,),
    ExecutionStatus.TIMED_OUT: (
        ExecutionStatus.VALIDATING_INPUT,
        ExecutionStatus.TIMED_OUT,
    ),
    ExecutionStatus.LIMIT_EXCEEDED: (
        ExecutionStatus.VALIDATING_INPUT,
        ExecutionStatus.LOADING_CONTEXT,
        ExecutionStatus.RUNNING,
        ExecutionStatus.LIMIT_EXCEEDED,
    ),
    ExecutionStatus.BUDGET_EXCEEDED: (
        ExecutionStatus.VALIDATING_INPUT,
        ExecutionStatus.LOADING_CONTEXT,
        ExecutionStatus.RUNNING,
        ExecutionStatus.BUDGET_EXCEEDED,
    ),
    ExecutionStatus.REJECTED: (
        ExecutionStatus.VALIDATING_INPUT,
        ExecutionStatus.REJECTED,
    ),
}


def _lifecycle_at(status: ExecutionStatus) -> ExecutionLifecycle:
    lifecycle = ExecutionLifecycle()
    for target in PATHS_TO_STATUS[status]:
        lifecycle.transition_to(target)
    return lifecycle


def test_lifecycle_always_starts_created_without_restore_shortcut() -> None:
    lifecycle = ExecutionLifecycle()

    assert lifecycle.status is ExecutionStatus.CREATED
    assert lifecycle.history == ()
    assert signature(ExecutionLifecycle).parameters == {}


@pytest.mark.parametrize(("current", "requested"), VALID_TRANSITIONS)
def test_lifecycle_accepts_declared_transition(
    current: ExecutionStatus,
    requested: ExecutionStatus,
) -> None:
    lifecycle = _lifecycle_at(current)

    transition = lifecycle.transition_to(requested)

    assert lifecycle.status is requested
    assert transition.from_status is current
    assert transition.to_status is requested


@pytest.mark.parametrize(("current", "requested"), INVALID_TRANSITIONS)
def test_lifecycle_rejects_undeclared_transition(
    current: ExecutionStatus,
    requested: ExecutionStatus,
) -> None:
    lifecycle = _lifecycle_at(current)
    history_before_attempt = lifecycle.history

    with pytest.raises(InvalidExecutionTransitionError) as captured:
        lifecycle.transition_to(requested)

    assert captured.value.current_status is current
    assert captured.value.requested_status is requested
    assert str(captured.value).startswith("Não é permitido")
    assert lifecycle.status is current
    assert lifecycle.history == history_before_attempt


@pytest.mark.parametrize("status", TERMINAL_STATUSES)
def test_terminal_status_cannot_transition(status: ExecutionStatus) -> None:
    lifecycle = _lifecycle_at(status)

    assert lifecycle.is_terminal
    with pytest.raises(InvalidExecutionTransitionError):
        lifecycle.transition_to(ExecutionStatus.CREATED)


@pytest.mark.parametrize("status", tuple(ExecutionStatus))
def test_transition_to_same_status_is_always_invalid(status: ExecutionStatus) -> None:
    lifecycle = _lifecycle_at(status)

    assert not lifecycle.can_transition_to(status)
    with pytest.raises(InvalidExecutionTransitionError):
        lifecycle.transition_to(status)


def test_lifecycle_records_ordered_immutable_history() -> None:
    lifecycle = ExecutionLifecycle()
    timestamps = (
        datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
        datetime(2026, 9, 1, 10, 1, tzinfo=UTC),
    )

    first = lifecycle.transition_to(
        ExecutionStatus.VALIDATING_INPUT,
        reason="Entrada recebida.",
        metadata={"source": "api"},
        timestamp=timestamps[0],
    )
    second = lifecycle.transition_to(
        ExecutionStatus.LOADING_CONTEXT,
        timestamp=timestamps[1],
    )
    history = lifecycle.history
    extended_snapshot = (*history, first)

    assert history == (first, second)
    assert lifecycle.history == (first, second)
    assert len(extended_snapshot) == 3
    assert first.reason == "Entrada recebida."
    assert first.metadata == {"source": "api"}
    assert tuple(item.timestamp for item in history) == timestamps


def test_lifecycle_uses_utc_timestamp_by_default() -> None:
    lifecycle = ExecutionLifecycle()

    transition = lifecycle.transition_to(ExecutionStatus.VALIDATING_INPUT)

    assert transition.timestamp.tzinfo is UTC
    assert transition.timestamp.utcoffset() is not None


def test_lifecycle_rejects_naive_timestamp_without_mutating_state() -> None:
    lifecycle = ExecutionLifecycle()

    with pytest.raises(ValidationError):
        lifecycle.transition_to(
            ExecutionStatus.VALIDATING_INPUT,
            timestamp=datetime(2026, 9, 1),
        )

    assert lifecycle.status is ExecutionStatus.CREATED
    assert lifecycle.history == ()


def test_lifecycle_status_has_no_public_setter() -> None:
    lifecycle = ExecutionLifecycle()

    with pytest.raises(AttributeError):
        object.__setattr__(lifecycle, "status", ExecutionStatus.COMPLETED)


@pytest.mark.parametrize(
    ("current", "terminal"),
    [
        (ExecutionStatus.RUNNING, ExecutionStatus.LIMIT_EXCEEDED),
        (ExecutionStatus.RUNNING, ExecutionStatus.BUDGET_EXCEEDED),
        (ExecutionStatus.WAITING_FOR_TOOL, ExecutionStatus.TIMED_OUT),
        (ExecutionStatus.EXECUTING_TOOL, ExecutionStatus.FAILED),
        (ExecutionStatus.WAITING_FOR_APPROVAL, ExecutionStatus.REJECTED),
        (ExecutionStatus.UPDATING_MEMORY, ExecutionStatus.CANCELLED),
    ],
)
def test_operational_states_reach_declared_terminal_statuses(
    current: ExecutionStatus,
    terminal: ExecutionStatus,
) -> None:
    lifecycle = _lifecycle_at(current)

    lifecycle.transition_to(terminal)

    assert lifecycle.status is terminal
    assert lifecycle.is_terminal
