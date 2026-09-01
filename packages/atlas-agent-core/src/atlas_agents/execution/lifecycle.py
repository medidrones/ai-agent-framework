"""Validated and encapsulated execution lifecycle state machine."""

from collections.abc import Mapping
from datetime import UTC, datetime
from types import MappingProxyType

from atlas_agents.agents.status import ExecutionStatus
from atlas_agents.exceptions import InvalidExecutionTransitionError
from atlas_agents.execution.terminal import is_terminal
from atlas_agents.execution.transition import ExecutionTransition

_FAILURE_AND_CANCELLATION = frozenset(
    {
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
    }
)
_PENDING_TERMINATIONS = frozenset(
    {
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.TIMED_OUT,
    }
)
_RESOURCE_TERMINATIONS = frozenset(
    {
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.TIMED_OUT,
        ExecutionStatus.LIMIT_EXCEEDED,
        ExecutionStatus.BUDGET_EXCEEDED,
    }
)

ALLOWED_TRANSITIONS: Mapping[ExecutionStatus, frozenset[ExecutionStatus]] = (
    MappingProxyType(
        {
            ExecutionStatus.CREATED: frozenset(
                {
                    ExecutionStatus.VALIDATING_INPUT,
                    *_FAILURE_AND_CANCELLATION,
                }
            ),
            ExecutionStatus.VALIDATING_INPUT: frozenset(
                {
                    ExecutionStatus.LOADING_CONTEXT,
                    ExecutionStatus.REJECTED,
                    *_PENDING_TERMINATIONS,
                }
            ),
            ExecutionStatus.LOADING_CONTEXT: frozenset(
                {
                    ExecutionStatus.RETRIEVING_KNOWLEDGE,
                    ExecutionStatus.RUNNING,
                    *_PENDING_TERMINATIONS,
                }
            ),
            ExecutionStatus.RETRIEVING_KNOWLEDGE: frozenset(
                {ExecutionStatus.RUNNING, *_PENDING_TERMINATIONS}
            ),
            ExecutionStatus.RUNNING: frozenset(
                {
                    ExecutionStatus.WAITING_FOR_TOOL,
                    ExecutionStatus.VALIDATING_OUTPUT,
                    *_RESOURCE_TERMINATIONS,
                }
            ),
            ExecutionStatus.WAITING_FOR_TOOL: frozenset(
                {
                    ExecutionStatus.EXECUTING_TOOL,
                    ExecutionStatus.WAITING_FOR_APPROVAL,
                    *_RESOURCE_TERMINATIONS,
                }
            ),
            ExecutionStatus.EXECUTING_TOOL: frozenset(
                {ExecutionStatus.RUNNING, *_RESOURCE_TERMINATIONS}
            ),
            ExecutionStatus.WAITING_FOR_APPROVAL: frozenset(
                {
                    ExecutionStatus.EXECUTING_TOOL,
                    ExecutionStatus.REJECTED,
                    *_PENDING_TERMINATIONS,
                }
            ),
            ExecutionStatus.VALIDATING_OUTPUT: frozenset(
                {
                    ExecutionStatus.UPDATING_MEMORY,
                    ExecutionStatus.COMPLETED,
                    *_PENDING_TERMINATIONS,
                }
            ),
            ExecutionStatus.UPDATING_MEMORY: frozenset(
                {ExecutionStatus.COMPLETED, *_PENDING_TERMINATIONS}
            ),
            ExecutionStatus.COMPLETED: frozenset(),
            ExecutionStatus.FAILED: frozenset(),
            ExecutionStatus.CANCELLED: frozenset(),
            ExecutionStatus.TIMED_OUT: frozenset(),
            ExecutionStatus.LIMIT_EXCEEDED: frozenset(),
            ExecutionStatus.BUDGET_EXCEEDED: frozenset(),
            ExecutionStatus.REJECTED: frozenset(),
        }
    )
)


class ExecutionLifecycle:
    """Control execution status through explicit, recorded transitions."""

    def __init__(
        self,
        *,
        initial_status: ExecutionStatus = ExecutionStatus.CREATED,
    ) -> None:
        """Initialize a lifecycle for a new or externally reconstructed status."""
        self._status = initial_status
        self._history: list[ExecutionTransition] = []

    @property
    def status(self) -> ExecutionStatus:
        """Return the current execution status without exposing a setter."""
        return self._status

    @property
    def history(self) -> tuple[ExecutionTransition, ...]:
        """Return an immutable snapshot of transitions in insertion order."""
        return tuple(self._history)

    @property
    def is_terminal(self) -> bool:
        """Return whether the current status permanently ends the lifecycle."""
        return is_terminal(self._status)

    def can_transition_to(self, status: ExecutionStatus) -> bool:
        """Return whether the declarative state machine allows a target status."""
        return status in ALLOWED_TRANSITIONS[self._status]

    def transition_to(
        self,
        status: ExecutionStatus,
        *,
        reason: str | None = None,
        metadata: Mapping[str, object] | None = None,
        timestamp: datetime | None = None,
    ) -> ExecutionTransition:
        """Validate, apply, and record one status transition."""
        if not self.can_transition_to(status):
            raise InvalidExecutionTransitionError(self._status, status)

        transition = ExecutionTransition(
            from_status=self._status,
            to_status=status,
            timestamp=timestamp if timestamp is not None else datetime.now(UTC),
            reason=reason,
            metadata=dict(metadata) if metadata is not None else {},
        )
        self._status = status
        self._history.append(transition)
        return transition
