"""Provider-neutral failures for memory coordination boundaries."""


class AgentMemoryError(Exception):
    """Base error for the Atlas memory abstraction."""


class MemoryStoreOperationError(AgentMemoryError):
    """Hide implementation-specific store failures behind a safe boundary."""


class MemoryStoreProtocolError(AgentMemoryError):
    """Report records that violate the memory store contract."""

    def __init__(self, message: str, *, code: str = "memory_store_violation") -> None:
        """Initialize a safe message and stable protocol violation code."""
        super().__init__(message)
        self.code = code


class MemoryScopeResolutionError(AgentMemoryError):
    """Report that no safe scope exists for an enabled memory type."""


class MemoryPolicyViolationError(AgentMemoryError):
    """Report invalid output from a memory selection or write policy."""
