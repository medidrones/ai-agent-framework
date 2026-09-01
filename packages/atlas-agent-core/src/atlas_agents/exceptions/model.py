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


class ModelProviderRegistryError(AtlasAgentError):
    """Base error for local provider registry operations."""


class DuplicateModelProviderError(ModelProviderRegistryError):
    """Report an attempt to overwrite a registered provider."""

    def __init__(self, provider_name: str) -> None:
        """Initialize the error with the duplicate logical identifier."""
        self.provider_name = _non_empty(provider_name)
        super().__init__(f"O provider de modelos '{provider_name}' já está registrado.")


class ModelProviderNotRegisteredError(ModelProviderRegistryError):
    """Report a provider identifier absent from one registry."""

    def __init__(self, provider_name: str) -> None:
        """Initialize the error with the missing logical identifier."""
        self.provider_name = _non_empty(provider_name)
        super().__init__(
            f"O provider de modelos '{provider_name}' não está registrado."
        )


class InvalidModelDescriptorError(ModelProviderRegistryError):
    """Report a descriptor inconsistent with its registered provider."""

    def __init__(
        self,
        provider_name: str,
        model: str,
        reason: str,
    ) -> None:
        """Initialize safe descriptor identity and validation context."""
        self.provider_name = _non_empty(provider_name)
        self.model = _non_empty(model)
        self.reason = _non_empty(reason)
        super().__init__(
            f"O descriptor '{provider_name}/{model}' é inválido: {reason}."
        )


class ModelSelectionError(AtlasAgentError):
    """Base error for deterministic local model selection."""


class NoMatchingModelError(ModelSelectionError):
    """Report that no catalog entry satisfies a selection request."""

    def __init__(
        self,
        *,
        requested_provider: str | None,
        requested_model: str | None,
        required_capabilities: frozenset[str],
        minimum_context_window: int | None,
        minimum_max_output_tokens: int | None,
    ) -> None:
        """Store only safe, explicit selection requirements."""
        self.requested_provider = requested_provider
        self.requested_model = requested_model
        self.required_capabilities = required_capabilities
        self.minimum_context_window = minimum_context_window
        self.minimum_max_output_tokens = minimum_max_output_tokens
        super().__init__("Nenhum modelo disponível atende aos requisitos solicitados.")


class ModelNotAvailableError(ModelSelectionError):
    """Report an explicitly requested model absent from the catalog."""

    def __init__(self, *, provider_name: str | None, model: str) -> None:
        """Initialize the missing opaque model identity."""
        self.provider_name = provider_name
        self.model = _non_empty(model)
        scope = "qualquer provider" if provider_name is None else provider_name
        super().__init__(f"O modelo '{model}' não está disponível em {scope}.")


class ModelCapabilityMismatchError(ModelSelectionError):
    """Report missing capabilities on an explicitly requested model."""

    def __init__(
        self,
        *,
        provider_name: str,
        model: str,
        missing_capabilities: frozenset[str],
    ) -> None:
        """Initialize the explicit pair and its missing stable capabilities."""
        self.provider_name = _non_empty(provider_name)
        self.model = _non_empty(model)
        self.missing_capabilities = missing_capabilities
        missing = ", ".join(sorted(missing_capabilities))
        super().__init__(
            f"O modelo explícito '{provider_name}/{model}' não oferece: {missing}."
        )
