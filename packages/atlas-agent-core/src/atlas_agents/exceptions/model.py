"""Provider-neutral model error hierarchy."""

from typing import ClassVar

from atlas_agents._models import _non_empty
from atlas_agents.exceptions.base import AtlasAgentError


class ModelProviderError(AtlasAgentError):
    """Base error raised at the provider abstraction boundary."""

    retryable_by_default: ClassVar[bool] = False

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        model: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        """Initialize safe provider context without raw requests or secrets."""
        self.provider = _non_empty(provider)
        self.model = None if model is None else _non_empty(model)
        self.retryable = self.retryable_by_default if retryable is None else retryable
        super().__init__(_non_empty(message))


class ModelAuthenticationError(ModelProviderError):
    """Report invalid or missing provider authentication."""


class ModelPermissionError(ModelProviderError):
    """Report denied access to a provider or model."""


class ModelNotFoundError(ModelProviderError):
    """Report a model identifier unavailable through the provider."""


class ModelRateLimitError(ModelProviderError):
    """Report temporary provider throttling."""

    retryable_by_default = True


class ModelTimeoutError(ModelProviderError):
    """Report a provider operation that exceeded its time limit."""

    retryable_by_default = True


class ModelUnavailableError(ModelProviderError):
    """Report a temporarily unavailable provider or model."""

    retryable_by_default = True


class ModelInvalidRequestError(ModelProviderError):
    """Report a request rejected before model generation."""


class ModelResponseError(ModelProviderError):
    """Report an invalid or incomplete response from a provider."""
