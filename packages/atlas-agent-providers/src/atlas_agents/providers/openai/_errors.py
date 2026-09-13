"""Normalize OpenAI SDK failures to the Atlas model error hierarchy."""

import openai

from atlas_agents.exceptions import (
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


class OpenAIErrorMapper:
    """Map SDK exception classes while discarding unsafe response details."""

    def map(self, error: Exception, *, model: str | None) -> ModelProviderError:
        """Return one safe provider-neutral exception."""
        if isinstance(error, openai.AuthenticationError):
            return ModelAuthenticationError(
                "A autenticação com a OpenAI falhou.",
                provider="openai",
                model=model,
            )
        if isinstance(error, openai.PermissionDeniedError):
            return ModelPermissionError(
                "A OpenAI negou acesso ao recurso.", provider="openai", model=model
            )
        if isinstance(error, openai.NotFoundError):
            return ModelNotFoundError(
                "O modelo ou recurso solicitado não foi encontrado na OpenAI.",
                provider="openai",
                model=model,
            )
        if isinstance(error, openai.RateLimitError):
            return ModelRateLimitError(
                "O limite de requisições da OpenAI foi atingido.",
                provider="openai",
                model=model,
            )
        if isinstance(error, openai.APITimeoutError):
            return ModelTimeoutError(
                "A comunicação com a OpenAI excedeu o tempo limite.",
                provider="openai",
                model=model,
            )
        if isinstance(error, (openai.APIConnectionError, openai.InternalServerError)):
            return ModelUnavailableError(
                "A OpenAI está temporariamente indisponível.",
                provider="openai",
                model=model,
            )
        if isinstance(
            error,
            (openai.BadRequestError, openai.UnprocessableEntityError),
        ):
            return ModelInvalidRequestError(
                "A OpenAI rejeitou a requisição do modelo.",
                provider="openai",
                model=model,
            )
        if isinstance(error, openai.APIResponseValidationError):
            return ModelResponseError(
                "A OpenAI retornou uma resposta que não pôde ser validada.",
                provider="openai",
                model=model,
            )
        return ModelProviderError(
            "Falha inesperada ao acessar a OpenAI.",
            provider="openai",
            model=model,
        )
