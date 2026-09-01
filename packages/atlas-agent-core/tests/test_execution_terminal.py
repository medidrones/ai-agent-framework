"""Tests for centralized terminal execution status detection."""

import pytest

from atlas_agents import ExecutionStatus, is_terminal
from atlas_agents.execution import TERMINAL_EXECUTION_STATUSES

TERMINAL_STATUSES = (
    ExecutionStatus.COMPLETED,
    ExecutionStatus.FAILED,
    ExecutionStatus.CANCELLED,
    ExecutionStatus.TIMED_OUT,
    ExecutionStatus.LIMIT_EXCEEDED,
    ExecutionStatus.BUDGET_EXCEEDED,
    ExecutionStatus.REJECTED,
)


@pytest.mark.parametrize("status", TERMINAL_STATUSES)
def test_terminal_statuses_are_centralized(status: ExecutionStatus) -> None:
    assert is_terminal(status)
    assert status in TERMINAL_EXECUTION_STATUSES


@pytest.mark.parametrize(
    "status",
    [ExecutionStatus.RUNNING, ExecutionStatus.WAITING_FOR_APPROVAL],
)
def test_processing_statuses_are_not_terminal(status: ExecutionStatus) -> None:
    assert not is_terminal(status)
