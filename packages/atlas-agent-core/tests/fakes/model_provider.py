"""Configurable model provider fake for runtime tests."""

import asyncio
from collections.abc import AsyncIterator

from atlas_agents import (
    ModelDescriptor,
    ModelExecutionContext,
    ModelProvider,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
)


class FakeModelProvider(ModelProvider):
    """Return configured descriptors, responses, or errors while recording calls."""

    def __init__(
        self,
        *,
        provider_name: str = "fake",
        descriptors: tuple[ModelDescriptor, ...],
        response: ModelResponse,
        generate_exception: BaseException | None = None,
        list_exception: Exception | None = None,
    ) -> None:
        self._provider_name = provider_name
        self._descriptors = descriptors
        self.response = response
        self.generate_exception = generate_exception
        self.list_exception = list_exception
        self.generate_calls = 0
        self.list_models_calls = 0
        self.stream_calls = 0
        self.requests: list[ModelRequest] = []
        self.contexts: list[ModelExecutionContext] = []

    @property
    def provider_name(self) -> str:
        return self._provider_name

    async def list_models(self) -> tuple[ModelDescriptor, ...]:
        self.list_models_calls += 1
        await asyncio.sleep(0)
        if self.list_exception is not None:
            raise self.list_exception
        return self._descriptors

    async def generate(
        self,
        request: ModelRequest,
        context: ModelExecutionContext,
    ) -> ModelResponse:
        self.generate_calls += 1
        self.requests.append(request)
        self.contexts.append(context)
        await asyncio.sleep(0)
        if self.generate_exception is not None:
            raise self.generate_exception
        return self.response

    def stream(
        self,
        request: ModelRequest,
        context: ModelExecutionContext,
    ) -> AsyncIterator[ModelStreamEvent]:
        del request, context
        self.stream_calls += 1
        return self._empty_stream()

    @staticmethod
    async def _empty_stream() -> AsyncIterator[ModelStreamEvent]:
        if False:
            yield  # pragma: no cover
