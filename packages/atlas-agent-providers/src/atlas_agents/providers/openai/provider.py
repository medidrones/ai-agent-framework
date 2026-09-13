"""Official asynchronous OpenAI model provider."""

import asyncio
import inspect
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import cast

from openai import AsyncOpenAI
from openai.types.responses.response_create_params import (
    ResponseCreateParamsNonStreaming,
    ResponseCreateParamsStreaming,
)

from atlas_agents.models import (
    ModelDescriptor,
    ModelExecutionContext,
    ModelProvider,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
)
from atlas_agents.providers.openai._errors import OpenAIErrorMapper
from atlas_agents.providers.openai._request import OpenAIRequestMapper
from atlas_agents.providers.openai._response import OpenAIResponseMapper
from atlas_agents.providers.openai._stream import OpenAIStreamMapper
from atlas_agents.providers.openai.config import OpenAIProviderConfig


class OpenAIModelProvider(ModelProvider):
    """Adapt Atlas model contracts to the OpenAI Responses API."""

    def __init__(
        self,
        client: AsyncOpenAI,
        *,
        config: OpenAIProviderConfig | None = None,
    ) -> None:
        """Use a caller-owned asynchronous client and explicit provider config."""
        self._client = client
        self._config = config or OpenAIProviderConfig()
        self._request_mapper = OpenAIRequestMapper(
            store_responses=self._config.store_responses
        )
        self._response_mapper = OpenAIResponseMapper()
        self._error_mapper = OpenAIErrorMapper()

    @property
    def provider_name(self) -> str:
        """Return the canonical provider identifier."""
        return "openai"

    async def list_models(self) -> tuple[ModelDescriptor, ...]:
        """Return the configured local catalog without a network call."""
        return self._config.models

    async def generate(
        self,
        request: ModelRequest,
        context: ModelExecutionContext,
    ) -> ModelResponse:
        """Generate without retaining vendor conversation state."""
        del context
        params = cast(
            "ResponseCreateParamsNonStreaming", self._request_mapper.map(request)
        )
        try:
            response = await self._client.responses.create(**params)
            return self._response_mapper.map(response, requested_model=request.model)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            from atlas_agents.exceptions import ModelProviderError

            if isinstance(exc, ModelProviderError):
                raise
            raise self._error_mapper.map(exc, model=request.model) from None

    def stream(
        self,
        request: ModelRequest,
        context: ModelExecutionContext,
    ) -> AsyncIterator[ModelStreamEvent]:
        """Stream incremental Atlas events from one Responses API invocation."""
        del context
        return self._stream(request)

    async def _stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        params = cast(
            "ResponseCreateParamsStreaming", self._request_mapper.map(request)
        )
        params["stream"] = True
        provider_stream: object | None = None
        mapper = OpenAIStreamMapper(requested_model=request.model)
        try:
            provider_stream = await self._client.responses.create(**params)
            async for provider_event in cast("AsyncIterator[object]", provider_stream):
                for event in mapper.map(provider_event):
                    yield event
        except asyncio.CancelledError:
            raise
        except GeneratorExit:
            raise
        except Exception as exc:
            from atlas_agents.exceptions import ModelProviderError

            if isinstance(exc, ModelProviderError):
                raise
            raise self._error_mapper.map(exc, model=request.model) from None
        finally:
            if provider_stream is not None:
                close = getattr(provider_stream, "close", None)
                if callable(close):
                    with suppress(Exception):
                        result = close()
                        if inspect.isawaitable(result):
                            await result
