"""Public errors raised by runtime execution state operations."""

from atlas_agents.exceptions.base import AtlasAgentError


class ExecutionStateError(AtlasAgentError):
    """Base class for controlled execution state errors."""


class ExecutionStateInvariantError(ExecutionStateError):
    """Report an operation that would violate an execution state invariant."""


class ExecutionAlreadyTerminalError(ExecutionStateInvariantError):
    """Report an operational mutation attempted after terminal state."""
