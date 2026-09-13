"""OpenAI streaming protocol, parity, cancellation, and cleanup tests."""

import asyncio
from collections.abc import AsyncGenerator
from typing import cast

import pytest
from conftest import FakeStream, context, provider_with, request, response, usage

from atlas_agents.exceptions import ModelProviderError
from atlas_agents.models import (
    FinishReason,
    ModelStreamEvent,
    ModelStreamEventType,
    TextContent,
)
from atlas_agents.runtime import ModelStreamAccumulator


def created() -> dict[str, object]:
    """Create a Responses stream start event."""
    return {
        "type": "response.created",
        "response": {"id": "resp-1", "model": "gpt-6-astra-2026-09-01"},
    }


def completed(*, tool_calls: bool = False) -> dict[str, object]:
    """Create a Responses stream completion event."""
    output: list[object] = []
    if tool_calls:
        output.append(
            {
                "type": "function_call",
                "call_id": "call-a",
                "name": "first",
                "arguments": '{"x":1}',
            }
        )
    return {
        "type": "response.completed",
        "response": response(output=output, usage=usage()),
    }


@pytest.mark.asyncio
async def test_text_stream_preserves_deltas_sequence_usage_and_accumulates() -> None:
    stream = FakeStream(
        [
            created(),
            {"type": "response.output_text.delta", "delta": "Hello"},
            {"type": "response.output_text.delta", "delta": " "},
            {"type": "response.output_text.delta", "delta": "world"},
            completed(),
        ]
    )
    provider, _ = provider_with(stream)
    events = [event async for event in provider.stream(request(), context())]
    assert [event.sequence for event in events] == list(range(1, len(events) + 1))
    assert [event.type for event in events] == [
        ModelStreamEventType.RESPONSE_STARTED,
        ModelStreamEventType.TEXT_DELTA,
        ModelStreamEventType.TEXT_DELTA,
        ModelStreamEventType.TEXT_DELTA,
        ModelStreamEventType.USAGE_UPDATED,
        ModelStreamEventType.RESPONSE_COMPLETED,
    ]
    assert [event.data["text"] for event in events[1:4]] == ["Hello", " ", "world"]
    assert all(event.response_id == "resp-1" for event in events)
    accumulator = ModelStreamAccumulator()
    for event in events:
        accumulator.consume(event)
    result = accumulator.finalize()
    assert isinstance(result.content[0], TextContent)
    assert result.content[0].text == "Hello world"
    assert result.usage.total_tokens == 13
    assert result.finish_reason is FinishReason.STOP
    assert stream.closed is True


@pytest.mark.asyncio
async def test_interleaved_tool_stream_uses_stable_call_identity() -> None:
    stream = FakeStream(
        [
            created(),
            {
                "type": "response.output_item.added",
                "item": {
                    "type": "function_call",
                    "id": "item-a",
                    "call_id": "call-a",
                    "name": "first",
                },
            },
            {
                "type": "response.output_item.added",
                "item": {
                    "type": "function_call",
                    "id": "item-b",
                    "call_id": "call-b",
                    "name": "second",
                },
            },
            {
                "type": "response.function_call_arguments.delta",
                "item_id": "item-a",
                "delta": '{"x"',
            },
            {
                "type": "response.function_call_arguments.delta",
                "item_id": "item-b",
                "delta": '{"y"',
            },
            {
                "type": "response.function_call_arguments.delta",
                "item_id": "item-a",
                "delta": ":1}",
            },
            {
                "type": "response.function_call_arguments.delta",
                "item_id": "item-b",
                "delta": ":2}",
            },
            {
                "type": "response.function_call_arguments.done",
                "item_id": "item-a",
                "arguments": '{"x":1}',
            },
            {
                "type": "response.function_call_arguments.done",
                "item_id": "item-b",
                "arguments": '{"y":2}',
            },
            completed(tool_calls=True),
        ]
    )
    provider, _ = provider_with(stream)
    events = [event async for event in provider.stream(request(), context())]
    starts = [
        event
        for event in events
        if event.type is ModelStreamEventType.TOOL_CALL_STARTED
    ]
    completed_calls = [
        event
        for event in events
        if event.type is ModelStreamEventType.TOOL_CALL_COMPLETED
    ]
    assert [event.data["tool_call_id"] for event in starts] == ["call-a", "call-b"]
    tool_call_data = [
        cast("dict[str, object]", event.data["tool_call"]) for event in completed_calls
    ]
    assert [item["arguments"] for item in tool_call_data] == [
        {"x": 1},
        {"y": 2},
    ]
    accumulator = ModelStreamAccumulator()
    for event in events:
        accumulator.consume(event)
    result = accumulator.finalize()
    assert [call.name for call in result.tool_calls] == ["first", "second"]
    assert result.finish_reason is FinishReason.TOOL_CALL


@pytest.mark.asyncio
async def test_output_item_done_can_finalize_call_once() -> None:
    stream = FakeStream(
        [
            created(),
            {
                "type": "response.output_item.added",
                "item": {
                    "type": "function_call",
                    "id": "item-a",
                    "call_id": "call-a",
                    "name": "first",
                },
            },
            {
                "type": "response.output_item.done",
                "item": {
                    "type": "function_call",
                    "id": "item-a",
                    "call_id": "call-a",
                    "name": "first",
                    "arguments": '{"x":1}',
                },
            },
            completed(tool_calls=True),
        ]
    )
    provider, _ = provider_with(stream)
    events = [event async for event in provider.stream(request(), context())]
    assert (
        sum(event.type is ModelStreamEventType.TOOL_CALL_COMPLETED for event in events)
        == 1
    )


@pytest.mark.asyncio
async def test_generate_and_stream_have_equivalent_semantics() -> None:
    complete = response(
        output=[
            {"type": "message", "content": [{"type": "output_text", "text": "ok"}]}
        ],
        usage=usage(),
    )
    provider, _ = provider_with(
        complete,
        FakeStream(
            [
                created(),
                {"type": "response.output_text.delta", "delta": "ok"},
                {"type": "response.completed", "response": complete},
            ]
        ),
    )
    generated = await provider.generate(request(), context())
    accumulator = ModelStreamAccumulator()
    async for event in provider.stream(request(), context()):
        accumulator.consume(event)
    streamed = accumulator.finalize()
    assert streamed.model == generated.model
    assert streamed.response_id == generated.response_id
    assert streamed.content == generated.content
    assert streamed.tool_calls == generated.tool_calls
    assert streamed.finish_reason == generated.finish_reason
    assert streamed.usage == generated.usage


@pytest.mark.asyncio
async def test_protocol_error_is_single_terminal_event() -> None:
    stream = FakeStream(
        [
            created(),
            {
                "type": "response.function_call_arguments.delta",
                "item_id": "missing",
                "delta": "{}",
            },
            {"type": "response.output_text.delta", "delta": "ignored"},
        ]
    )
    provider, _ = provider_with(stream)
    events = [event async for event in provider.stream(request(), context())]
    assert [event.type for event in events] == [
        ModelStreamEventType.RESPONSE_STARTED,
        ModelStreamEventType.ERROR,
    ]


@pytest.mark.asyncio
async def test_provider_failure_event_is_terminal() -> None:
    stream = FakeStream(
        [
            created(),
            {
                "type": "response.failed",
                "response": {"id": "resp-1", "model": "gpt-6-astra"},
            },
            {"type": "response.output_text.delta", "delta": "ignored"},
        ]
    )
    provider, _ = provider_with(stream)
    events = [event async for event in provider.stream(request(), context())]
    assert events[-1].type is ModelStreamEventType.ERROR


@pytest.mark.asyncio
async def test_transport_exception_is_normalized_and_stream_is_closed() -> None:
    stream = FakeStream([created()], RuntimeError("sk-secret-example"))
    provider, _ = provider_with(stream)
    with pytest.raises(ModelProviderError) as caught:
        _ = [event async for event in provider.stream(request(), context())]
    assert "sk-secret-example" not in str(caught.value)
    assert stream.closed is True


@pytest.mark.asyncio
async def test_cancellation_is_preserved() -> None:
    provider, _ = provider_with(asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        _ = [event async for event in provider.stream(request(), context())]


@pytest.mark.asyncio
async def test_consumer_early_close_releases_stream() -> None:
    stream = FakeStream(
        [created(), {"type": "response.output_text.delta", "delta": "later"}]
    )
    provider, _ = provider_with(stream)
    iterator = cast(
        "AsyncGenerator[ModelStreamEvent, None]",
        provider.stream(request(), context()),
    )
    first = await anext(iterator)
    assert first.type is ModelStreamEventType.RESPONSE_STARTED
    await iterator.aclose()
    assert stream.closed is True


@pytest.mark.asyncio
async def test_concurrent_invocations_have_independent_sequences() -> None:
    provider, _ = provider_with(
        FakeStream([created(), completed()]),
        FakeStream([created(), completed()]),
    )

    async def collect() -> list[int]:
        return [event.sequence async for event in provider.stream(request(), context())]

    first, second = await asyncio.gather(collect(), collect())
    assert first == [1, 2, 3]
    assert second == [1, 2, 3]


@pytest.mark.asyncio
async def test_stream_synthesizes_start_and_maps_incomplete_refusal_without_usage() -> (
    None
):
    stream = FakeStream(
        [
            {"type": "response.refusal.delta", "delta": "refused"},
            {
                "type": "response.incomplete",
                "response": response(
                    status="incomplete", incomplete_reason="safety", usage=None
                ),
            },
        ]
    )
    provider, _ = provider_with(stream)
    events = [event async for event in provider.stream(request(), context())]
    assert [event.type for event in events] == [
        ModelStreamEventType.RESPONSE_STARTED,
        ModelStreamEventType.RESPONSE_COMPLETED,
    ]
    assert events[-1].data["finish_reason"] == FinishReason.CONTENT_FILTER.value


@pytest.mark.asyncio
async def test_stream_rejects_identity_and_unfinished_call() -> None:
    cases = [
        FakeStream([created(), created()]),
        FakeStream(
            [
                created(),
                {
                    "type": "response.completed",
                    "response": {
                        **response(usage=usage()),
                        "id": "changed",
                    },
                },
            ]
        ),
        FakeStream(
            [
                created(),
                {
                    "type": "response.output_item.added",
                    "item": {
                        "type": "function_call",
                        "id": "item-a",
                        "call_id": "call-a",
                        "name": "first",
                    },
                },
                completed(tool_calls=True),
            ]
        ),
    ]
    for stream in cases:
        provider, _ = provider_with(stream)
        events = [event async for event in provider.stream(request(), context())]
        assert events[-1].type is ModelStreamEventType.ERROR


@pytest.mark.asyncio
async def test_stream_ignores_non_function_items_and_rejects_invalid_tool_json() -> (
    None
):
    stream = FakeStream(
        [
            created(),
            {"type": "response.output_item.added", "item": {"type": "reasoning"}},
            {"type": "response.output_item.done", "item": {"type": "message"}},
            {
                "type": "response.output_item.added",
                "item": {
                    "type": "function_call",
                    "id": "item-a",
                    "call_id": "call-a",
                    "name": "first",
                },
            },
            {
                "type": "response.function_call_arguments.done",
                "item_id": "item-a",
                "arguments": "not-json",
            },
        ]
    )
    provider, _ = provider_with(stream)
    events = [event async for event in provider.stream(request(), context())]
    assert events[-1].type is ModelStreamEventType.ERROR


@pytest.mark.asyncio
async def test_stream_can_resolve_call_by_call_id_and_ignore_unknown_events() -> None:
    stream = FakeStream(
        [
            created(),
            {"type": "future.event"},
            {
                "type": "response.output_item.added",
                "item": {
                    "type": "function_call",
                    "id": "item-a",
                    "call_id": "call-a",
                    "name": "first",
                },
            },
            {
                "type": "response.output_item.done",
                "item": {
                    "type": "function_call",
                    "call_id": "call-a",
                    "name": "first",
                    "arguments": '{"x":1}',
                },
            },
            completed(tool_calls=True),
        ]
    )
    provider, _ = provider_with(stream)
    events = [event async for event in provider.stream(request(), context())]
    assert events[-1].type is ModelStreamEventType.RESPONSE_COMPLETED
