"""Tests for the provider-neutral model error hierarchy."""

import pytest

from atlas_agents import (
    AtlasAgentError,
    DuplicateModelProviderError,
    InvalidModelDescriptorError,
    ModelAuthenticationError,
    ModelCapabilityMismatchError,
    ModelInvalidRequestError,
    ModelNotAvailableError,
    ModelNotFoundError,
    ModelPermissionError,
    ModelProviderError,
    ModelProviderNotRegisteredError,
    ModelProviderRegistryError,
    ModelRateLimitError,
    ModelResponseError,
    ModelSelectionError,
    ModelTimeoutError,
    ModelUnavailableError,
    NoMatchingModelError,
)


@pytest.mark.parametrize(
    "error_type",
    [
        ModelAuthenticationError,
        ModelPermissionError,
        ModelNotFoundError,
        ModelInvalidRequestError,
    ],
)
def test_permanent_model_errors_are_not_retryable(
    error_type: type[ModelProviderError],
) -> None:
    error = error_type("Falha permanente.", provider="fake", model="model")

    assert isinstance(error, AtlasAgentError)
    assert not error.retryable


@pytest.mark.parametrize(
    "error_type",
    [ModelRateLimitError, ModelTimeoutError, ModelUnavailableError],
)
def test_transient_model_errors_are_retryable_by_default(
    error_type: type[ModelProviderError],
) -> None:
    error = error_type("Falha temporária.", provider="fake")

    assert error.retryable


def test_model_response_error_allows_explicit_retry_semantics() -> None:
    error = ModelResponseError(
        "Resposta incompleta.",
        provider="fake",
        model="model",
        retryable=True,
    )

    assert error.provider == "fake"
    assert error.model == "model"
    assert error.retryable
    assert str(error) == "Resposta incompleta."


def test_model_error_rejects_empty_safe_context() -> None:
    with pytest.raises(ValueError, match="vazio"):
        ModelProviderError("Erro.", provider=" ")


def test_registry_and_selection_errors_are_local_atlas_errors() -> None:
    registry_errors = (
        DuplicateModelProviderError,
        InvalidModelDescriptorError,
        ModelProviderNotRegisteredError,
    )
    selection_errors = (
        ModelCapabilityMismatchError,
        ModelNotAvailableError,
        NoMatchingModelError,
    )

    assert all(issubclass(item, ModelProviderRegistryError) for item in registry_errors)
    assert all(issubclass(item, ModelSelectionError) for item in selection_errors)
    assert issubclass(ModelProviderRegistryError, AtlasAgentError)
    assert issubclass(ModelSelectionError, AtlasAgentError)
    assert not issubclass(ModelProviderRegistryError, ModelProviderError)
