"""Central definitions for terminal execution statuses."""

from atlas_agents.agents.status import ExecutionStatus

TERMINAL_EXECUTION_STATUSES: frozenset[ExecutionStatus] = frozenset(
    {
        ExecutionStatus.COMPLETED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.TIMED_OUT,
        ExecutionStatus.LIMIT_EXCEEDED,
        ExecutionStatus.BUDGET_EXCEEDED,
        ExecutionStatus.REJECTED,
    }
)


def is_terminal(status: ExecutionStatus) -> bool:
    """Return whether a status permanently ends an execution."""
    return status in TERMINAL_EXECUTION_STATUSES
