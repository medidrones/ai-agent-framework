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


class ModelStreamProtocolError(AgentRuntimeError):
    """Base class for provider-neutral model stream protocol failures."""


class InvalidModelStreamSequenceError(ModelStreamProtocolError):
    """Report a gap, duplicate, or invalid initial model stream sequence."""

    def __init__(self, *, expected: int, received: int) -> None:
        """Initialize the error with expected and received sequence values."""
        self.expected = expected
        self.received = received
        super().__init__(
            "A sequência do stream de modelo é inválida: "
            f"esperado {expected}, recebido {received}."
        )


class InvalidModelStreamProtocolError(ModelStreamProtocolError):
    """Report an invalid event or inconsistent stream payload."""


class ModelStreamIncompleteError(ModelStreamProtocolError):
    """Report a provider iterator that ended without a terminal event."""


class ModelStreamReportedError(ModelStreamProtocolError):
    """Report an explicit ERROR terminal event emitted by a provider stream."""
