"""Tests for the provider-neutral model error hierarchy."""

import pytest

from atlas_agents import (
    AtlasAgentError,
    ModelAuthenticationError,
    ModelInvalidRequestError,
    ModelNotFoundError,
    ModelPermissionError,
    ModelProviderError,
    ModelRateLimitError,
    ModelResponseError,
    ModelTimeoutError,
    ModelUnavailableError,
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
