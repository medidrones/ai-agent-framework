"""Public errors raised by runtime execution state operations."""

from atlas_agents.exceptions.base import AtlasAgentError


class ExecutionStateError(AtlasAgentError):
    """Base class for controlled execution state errors."""


class ExecutionStateInvariantError(ExecutionStateError):
    """Report an operation that would violate an execution state invariant."""


class ExecutionAlreadyTerminalError(ExecutionStateInvariantError):
    """Report an operational mutation attempted after terminal state."""


class AgentRuntimeError(AtlasAgentError):
    """Base class for errors raised by runtime orchestration components."""


class RuntimeInputRejectedError(AgentRuntimeError):
    """Describe a structurally valid input unsupported by the current runtime."""

    def __init__(self, *, code: str, message: str) -> None:
        """Initialize stable rejection facts safe for public events."""
        self.code = code
        super().__init__(message)
