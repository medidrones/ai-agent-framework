"""Contract tests locking the complete declarative transition protocol."""

import pytest

from atlas_agents import ExecutionStatus
from atlas_agents.execution import ALLOWED_TRANSITIONS, TERMINAL_EXECUTION_STATUSES

FAILURE_AND_CANCELLATION = frozenset(
    {ExecutionStatus.FAILED, ExecutionStatus.CANCELLED}
)
PENDING_TERMINATIONS = frozenset(
    {
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.TIMED_OUT,
    }
)
RESOURCE_TERMINATIONS = frozenset(
    {
        *PENDING_TERMINATIONS,
        ExecutionStatus.LIMIT_EXCEEDED,
        ExecutionStatus.BUDGET_EXCEEDED,
    }
)


def test_allowed_transitions_match_the_public_protocol() -> None:
    expected = {
        ExecutionStatus.CREATED: frozenset(
            {ExecutionStatus.VALIDATING_INPUT, *FAILURE_AND_CANCELLATION}
        ),
        ExecutionStatus.VALIDATING_INPUT: frozenset(
            {
                ExecutionStatus.LOADING_CONTEXT,
                ExecutionStatus.REJECTED,
                *PENDING_TERMINATIONS,
            }
        ),
        ExecutionStatus.LOADING_CONTEXT: frozenset(
            {
                ExecutionStatus.RETRIEVING_KNOWLEDGE,
                ExecutionStatus.RUNNING,
                *PENDING_TERMINATIONS,
            }
        ),
        ExecutionStatus.RETRIEVING_KNOWLEDGE: frozenset(
            {ExecutionStatus.RUNNING, *PENDING_TERMINATIONS}
        ),
        ExecutionStatus.RUNNING: frozenset(
            {
                ExecutionStatus.WAITING_FOR_TOOL,
                ExecutionStatus.VALIDATING_OUTPUT,
                *RESOURCE_TERMINATIONS,
            }
        ),
        ExecutionStatus.WAITING_FOR_TOOL: frozenset(
            {
                ExecutionStatus.EXECUTING_TOOL,
                ExecutionStatus.WAITING_FOR_APPROVAL,
                ExecutionStatus.RUNNING,
                *RESOURCE_TERMINATIONS,
            }
        ),
        ExecutionStatus.EXECUTING_TOOL: frozenset(
            {
                ExecutionStatus.RUNNING,
                ExecutionStatus.WAITING_FOR_TOOL,
                *RESOURCE_TERMINATIONS,
            }
        ),
        ExecutionStatus.WAITING_FOR_APPROVAL: frozenset(
            {
                ExecutionStatus.EXECUTING_TOOL,
                ExecutionStatus.RUNNING,
                ExecutionStatus.REJECTED,
                *PENDING_TERMINATIONS,
            }
        ),
        ExecutionStatus.VALIDATING_OUTPUT: frozenset(
            {
                ExecutionStatus.UPDATING_MEMORY,
                ExecutionStatus.COMPLETED,
                ExecutionStatus.RUNNING,
                ExecutionStatus.REJECTED,
                *PENDING_TERMINATIONS,
            }
        ),
        ExecutionStatus.UPDATING_MEMORY: frozenset(
            {ExecutionStatus.COMPLETED, *PENDING_TERMINATIONS}
        ),
        ExecutionStatus.COMPLETED: frozenset(),
        ExecutionStatus.FAILED: frozenset(),
        ExecutionStatus.CANCELLED: frozenset(),
        ExecutionStatus.TIMED_OUT: frozenset(),
        ExecutionStatus.LIMIT_EXCEEDED: frozenset(),
        ExecutionStatus.BUDGET_EXCEEDED: frozenset(),
        ExecutionStatus.REJECTED: frozenset(),
    }

    assert dict(ALLOWED_TRANSITIONS) == expected


def test_transition_map_contains_every_execution_status() -> None:
    assert set(ALLOWED_TRANSITIONS) == set(ExecutionStatus)


@pytest.mark.parametrize("status", TERMINAL_EXECUTION_STATUSES)
def test_terminal_status_has_no_outgoing_transitions(
    status: ExecutionStatus,
) -> None:
    assert ALLOWED_TRANSITIONS[status] == frozenset()


@pytest.mark.parametrize("status", tuple(ExecutionStatus))
def test_transition_map_forbids_self_transitions(status: ExecutionStatus) -> None:
    assert status not in ALLOWED_TRANSITIONS[status]
