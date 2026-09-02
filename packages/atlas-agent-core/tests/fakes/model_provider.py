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
        stream_events: tuple[ModelStreamEvent, ...] = (),
        stream_exception: BaseException | None = None,
        stream_exception_after: int | None = None,
    ) -> None:
        self._provider_name = provider_name
        self._descriptors = descriptors
        self.response = response
        self.generate_exception = generate_exception
        self.list_exception = list_exception
        self.stream_events = stream_events
        self.stream_exception = stream_exception
        self.stream_exception_after = stream_exception_after
        self.generate_calls = 0
        self.list_models_calls = 0
        self.stream_calls = 0
        self.stream_yields = 0
        self.stream_finalizations = 0
        self.requests: list[ModelRequest] = []
        self.contexts: list[ModelExecutionContext] = []
        self.stream_requests: list[ModelRequest] = []
        self.stream_contexts: list[ModelExecutionContext] = []

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
        self.stream_calls += 1
        self.stream_requests.append(request)
        self.stream_contexts.append(context)
        return self._configured_stream()

    async def _configured_stream(self) -> AsyncIterator[ModelStreamEvent]:
        try:
            for index, event in enumerate(self.stream_events):
                await asyncio.sleep(0)
                if (
                    self.stream_exception_after == index
                    and self.stream_exception is not None
                ):
                    raise self.stream_exception
                self.stream_yields += 1
                yield event
            if self.stream_exception is not None and (
                self.stream_exception_after is None
                or self.stream_exception_after >= len(self.stream_events)
            ):
                raise self.stream_exception
        finally:
            self.stream_finalizations += 1
