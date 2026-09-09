"""Provider-neutral errors for external knowledge retrieval."""

from atlas_agents.exceptions.base import AtlasAgentError


class KnowledgeError(AtlasAgentError):
    """Base error for knowledge contracts and coordination."""


class KnowledgeRetrievalError(KnowledgeError):
    """Report a controlled retriever failure without leaking backend details."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        """Initialize a safe failure with informational retryability."""
        super().__init__(message)
        self.retryable = retryable


class KnowledgeSourceNotFoundError(KnowledgeError):
    """Report that an explicitly requested source is unavailable."""


class KnowledgeProtocolError(KnowledgeError):
    """Report a retriever response that violates the public contract."""


class KnowledgeContextError(KnowledgeError):
    """Report invalid query building or context assembly."""


class KnowledgePolicyError(KnowledgeError):
    """Report invalid behavior from a retrieval selection policy."""
