"""Safe mappings from model and selection errors to public agent errors."""

from atlas_agents.agents import AgentErrorInfo
from atlas_agents.exceptions import (
    InvalidModelDescriptorError,
    ModelAuthenticationError,
    ModelCapabilityMismatchError,
    ModelInvalidRequestError,
    ModelNotAvailableError,
    ModelNotFoundError,
    ModelPermissionError,
    ModelProviderError,
    ModelProviderNotRegisteredError,
    ModelRateLimitError,
    ModelResponseError,
    ModelSelectionError,
    ModelTimeoutError,
    ModelUnavailableError,
    NoMatchingModelError,
)

_PROVIDER_ERROR_CODES: tuple[tuple[type[ModelProviderError], str], ...] = (
    (ModelAuthenticationError, "model_authentication_error"),
    (ModelPermissionError, "model_permission_error"),
    (ModelNotFoundError, "model_not_found"),
    (ModelRateLimitError, "model_rate_limit"),
    (ModelTimeoutError, "model_timeout"),
    (ModelUnavailableError, "model_unavailable"),
    (ModelInvalidRequestError, "model_invalid_request"),
    (ModelResponseError, "model_response_error"),
)


def model_provider_error_to_agent_error(error: ModelProviderError) -> AgentErrorInfo:
    """Normalize a safe provider error without exposing requests or credentials."""
    code = "model_provider_error"
    for error_type, candidate_code in _PROVIDER_ERROR_CODES:
        if isinstance(error, error_type):
            code = candidate_code
            break
    details: dict[str, object] = {"provider": error.provider}
    if error.model is not None:
        details["model"] = error.model
    return AgentErrorInfo(
        code=code,
        message=str(error),
        retryable=error.retryable,
        details=details,
    )


def model_selection_error_to_agent_error(error: ModelSelectionError) -> AgentErrorInfo:
    """Normalize deterministic model selection failures to stable public codes."""
    if isinstance(error, NoMatchingModelError):
        code = "no_matching_model"
    elif isinstance(error, ModelNotAvailableError):
        code = "model_not_available"
    elif isinstance(error, ModelCapabilityMismatchError):
        code = "model_capability_mismatch"
    else:
        code = "model_selection_error"
    return AgentErrorInfo(code=code, message=str(error))


def registry_error_to_agent_error(error: Exception) -> AgentErrorInfo:
    """Normalize registry failures that can occur while preparing an execution."""
    if isinstance(error, ModelProviderNotRegisteredError):
        code = "model_provider_not_registered"
    elif isinstance(error, InvalidModelDescriptorError):
        code = "invalid_model_descriptor"
    else:
        code = "model_registry_error"
    return AgentErrorInfo(code=code, message=str(error))
