"""Shared OpenAI provider test doubles."""

from collections.abc import AsyncIterator
from typing import cast

from openai import AsyncOpenAI

from atlas_agents.models import (
    MessageRole,
    ModelExecutionContext,
    ModelMessage,
    ModelRequest,
    TextContent,
)
from atlas_agents.providers.openai import OpenAIModelProvider


class FakeStream:
    """Yield configured SDK-like events and record resource cleanup."""

    def __init__(self, events: list[object], error: Exception | None = None) -> None:
        self._events = events
        self._error = error
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[object]:
        for event in self._events:
            yield event
        if self._error is not None:
            raise self._error

    async def close(self) -> None:
        """Record transport cleanup."""
        self.closed = True


class FakeResponses:
    """Record Responses calls and return queued complete or streamed results."""

    def __init__(self, results: list[object]) -> None:
        self.results = results
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> object:
        """Return or raise the next configured result."""
        self.calls.append(dict(kwargs))
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


class FakeClient:
    """Expose only the Responses resource used by the provider."""

    def __init__(self, results: list[object]) -> None:
        self.responses = FakeResponses(results)


def provider_with(*results: object) -> tuple[OpenAIModelProvider, FakeClient]:
    """Create a provider around a deliberately minimal fake SDK client."""
    client = FakeClient(list(results))
    return OpenAIModelProvider(cast("AsyncOpenAI", client)), client


def context() -> ModelExecutionContext:
    """Create correlation data that must not be forwarded."""
    return ModelExecutionContext(
        execution_id="execution-secret",
        agent_id="agent-secret",
        request_id="request-secret",
        metadata={"private": "context"},
    )


def request() -> ModelRequest:
    """Create one minimal text request."""
    return ModelRequest(
        model="gpt-6-astra",
        messages=(
            ModelMessage(
                role=MessageRole.USER,
                content=(TextContent(text="Olá"),),
            ),
        ),
        metadata={"private": "request"},
    )


def response(
    *,
    output: list[object] | None = None,
    status: str = "completed",
    incomplete_reason: str | None = None,
    usage: object | None = None,
) -> dict[str, object]:
    """Create a realistic SDK-like Responses object as a dictionary."""
    return {
        "id": "resp-1",
        "model": "gpt-6-astra-2026-09-01",
        "status": status,
        "error": None,
        "incomplete_details": (
            {"reason": incomplete_reason} if incomplete_reason is not None else None
        ),
        "output": output or [],
        "usage": usage,
    }


def usage() -> dict[str, object]:
    """Create all supported token counters."""
    return {
        "input_tokens": 8,
        "output_tokens": 5,
        "total_tokens": 13,
        "input_tokens_details": {"cached_tokens": 3, "unknown": 99},
        "output_tokens_details": {"reasoning_tokens": 2},
        "future_field": "ignored",
    }
