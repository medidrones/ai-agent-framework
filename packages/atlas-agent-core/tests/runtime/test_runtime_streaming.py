"""End-to-end tests for the provider-neutral streaming runtime."""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator, Mapping
from typing import cast

import pytest

from atlas_agents import (
    AgentContext,
    AgentDefinition,
    AgentEvent,
    AgentEventFactory,
    AgentEventType,
    AgentInput,
    AgentRuntime,
    ExecutionState,
    ExecutionStatus,
    FinishReason,
    ModelCapability,
    ModelDescriptor,
    ModelProviderRegistry,
    ModelRateLimitError,
    ModelResponse,
    ModelSelectionRequest,
    ModelStreamEvent,
    ModelStreamEventType,
    ModelUsage,
    RuntimeEventItem,
    RuntimeResultItem,
    RuntimeStreamItem,
    TextContent,
    ToolCall,
)
from tests.fakes import FakeModelProvider


def _agent() -> AgentDefinition:
    return AgentDefinition(
        agent_id="streamer",
        name="Streamer",
        instructions="Respond incrementally.",
    )


def _context(execution_id: str = "execution-stream-1") -> AgentContext:
    return AgentContext(execution_id=execution_id)


def _descriptor(
    *,
    provider: str = "fake",
    model: str = "model-a",
    streaming: bool = True,
) -> ModelDescriptor:
    capabilities = {ModelCapability.TEXT_GENERATION}
    if streaming:
        capabilities.add(ModelCapability.STREAMING)
    return ModelDescriptor(
        provider=provider,
        model=model,
        capabilities=frozenset(capabilities),
    )


def _unused_response() -> ModelResponse:
    return ModelResponse(
        model="unused",
        content=(TextContent(text="generate must not be called"),),
        finish_reason=FinishReason.STOP,
        usage=ModelUsage(),
    )


def _event(
    event_type: ModelStreamEventType,
    sequence: int,
    data: dict[str, object] | None = None,
) -> ModelStreamEvent:
    return ModelStreamEvent(
        type=event_type,
        sequence=sequence,
        response_id="response-1",
        data=data or {},
    )


def _text_stream(
    *,
    finish_reason: FinishReason = FinishReason.STOP,
    deltas: tuple[str, ...] = ("Olá, ", "mundo!"),
) -> tuple[ModelStreamEvent, ...]:
    events = [_event(ModelStreamEventType.RESPONSE_STARTED, 1, {"model": "model-a"})]
    events.extend(
        _event(ModelStreamEventType.TEXT_DELTA, index, {"text": delta})
        for index, delta in enumerate(deltas, start=2)
    )
    events.append(
        _event(
            ModelStreamEventType.USAGE_UPDATED,
            len(events) + 1,
            {
                "usage": {
                    "input_tokens": 2,
                    "output_tokens": 3,
                    "total_tokens": 5,
                }
            },
        )
    )
    events.append(
        _event(
            ModelStreamEventType.RESPONSE_COMPLETED,
            len(events) + 1,
            {"model": "model-a", "finish_reason": finish_reason.value},
        )
    )
    return tuple(events)


def _provider(
    *,
    provider_name: str = "fake",
    descriptor: ModelDescriptor | None = None,
    stream_events: tuple[ModelStreamEvent, ...] | None = None,
    stream_exception: BaseException | None = None,
    stream_exception_after: int | None = None,
) -> FakeModelProvider:
    return FakeModelProvider(
        provider_name=provider_name,
        descriptors=(descriptor or _descriptor(provider=provider_name),),
        response=_unused_response(),
        stream_events=_text_stream() if stream_events is None else stream_events,
        stream_exception=stream_exception,
        stream_exception_after=stream_exception_after,
    )


def _runtime(*providers: FakeModelProvider) -> AgentRuntime:
    registry = ModelProviderRegistry()
    for provider in providers:
        registry.register(provider)
    return AgentRuntime(model_registry=registry)


async def _collect(
    runtime: AgentRuntime,
    *,
    context: AgentContext | None = None,
    selection: ModelSelectionRequest | None = None,
) -> list[RuntimeStreamItem]:
    return [
        item
        async for item in runtime.stream(
            agent=_agent(),
            input_data=AgentInput(message="Explique streaming."),
            context=context or _context(),
            model_selection=selection,
        )
    ]


def _result(items: list[RuntimeStreamItem]) -> RuntimeResultItem:
    assert isinstance(items[-1], RuntimeResultItem)
    return items[-1]


def _events(items: list[RuntimeStreamItem]) -> list[AgentEvent]:
    return [item.event for item in items if isinstance(item, RuntimeEventItem)]


async def test_streams_incrementally_and_emits_exactly_one_final_result() -> None:
    provider = _provider()

    items = await _collect(_runtime(provider))
    result = _result(items).result
    events = _events(items)

    assert result.status is ExecutionStatus.COMPLETED
    assert result.output == "Olá, mundo!"
    assert result.usage.total_tokens == 5
    assert provider.stream_calls == 1
    assert provider.generate_calls == 0
    assert sum(isinstance(item, RuntimeResultItem) for item in items) == 1
    assert [
        event.data["text"]
        for event in events
        if event.event_type is AgentEventType.MODEL_TEXT_DELTA
    ] == [
        "Olá, ",
        "mundo!",
    ]
    assert [event.sequence for event in events] == list(range(1, len(events) + 1))
    assert tuple(events) == result.events


async def test_stream_items_are_serializable_discriminated_models() -> None:
    items = await _collect(_runtime(_provider()))

    assert items[0].model_dump(mode="json")["type"] == "event"
    assert items[-1].model_dump(mode="json")["type"] == "result"


async def test_provider_is_pulled_only_when_consumer_requests_next_item() -> None:
    provider = _provider()
    iterator = _runtime(provider).stream(
        agent=_agent(),
        input_data=AgentInput(message="Controle de fluxo."),
        context=_context(),
    )

    while True:
        item = await anext(iterator)
        if (
            isinstance(item, RuntimeEventItem)
            and item.event.event_type is AgentEventType.MODEL_STREAM_STARTED
        ):
            break
    assert provider.stream_yields == 1

    next_item = await anext(iterator)
    assert isinstance(next_item, RuntimeEventItem)
    assert next_item.event.event_type is AgentEventType.MODEL_TEXT_DELTA
    assert provider.stream_yields == 2
    await cast(AsyncGenerator[RuntimeStreamItem, None], iterator).aclose()


@pytest.mark.parametrize(
    ("finish_reason", "expected_status", "expected_code"),
    [
        (FinishReason.LENGTH, ExecutionStatus.COMPLETED, None),
        (
            FinishReason.CONTENT_FILTER,
            ExecutionStatus.REJECTED,
            "model_content_filtered",
        ),
        (
            FinishReason.CANCELLED,
            ExecutionStatus.CANCELLED,
            "model_response_cancelled",
        ),
        (FinishReason.ERROR, ExecutionStatus.FAILED, "model_error_finish_reason"),
        (
            FinishReason.UNKNOWN,
            ExecutionStatus.FAILED,
            "model_unknown_finish_reason",
        ),
    ],
)
async def test_applies_same_finish_policy_as_non_streaming_runtime(
    finish_reason: FinishReason,
    expected_status: ExecutionStatus,
    expected_code: str | None,
) -> None:
    items = await _collect(
        _runtime(_provider(stream_events=_text_stream(finish_reason=finish_reason)))
    )
    result = _result(items).result

    assert result.status is expected_status
    if expected_code is None:
        assert result.error is None
    elif expected_status is ExecutionStatus.FAILED:
        assert result.error is not None
        assert result.error.code == expected_code
    else:
        assert result.error is None
        assert expected_code in {event.data.get("code") for event in result.events}


async def test_rejects_empty_completed_text() -> None:
    items = await _collect(_runtime(_provider(stream_events=_text_stream(deltas=()))))
    error = _result(items).result.error

    assert error is not None
    assert error.code == "model_empty_text_response"


async def test_tool_call_stream_is_reconstructed_then_rejected_by_current_policy() -> (
    None
):
    tool_call = ToolCall(
        tool_call_id="call-1",
        name="search",
        arguments={"query": "atlas"},
    )
    stream = (
        _event(ModelStreamEventType.RESPONSE_STARTED, 1, {"model": "model-a"}),
        _event(
            ModelStreamEventType.TOOL_CALL_STARTED,
            2,
            {"tool_call_id": "call-1", "name": "search"},
        ),
        _event(
            ModelStreamEventType.TOOL_CALL_ARGUMENT_DELTA,
            3,
            {"tool_call_id": "call-1", "delta": '{"query":"atlas"}'},
        ),
        _event(
            ModelStreamEventType.TOOL_CALL_COMPLETED,
            4,
            {"tool_call": tool_call.model_dump(mode="json")},
        ),
        _event(
            ModelStreamEventType.RESPONSE_COMPLETED,
            5,
            {"model": "model-a", "finish_reason": "tool_call"},
        ),
    )

    items = await _collect(_runtime(_provider(stream_events=stream)))
    error = _result(items).result.error

    assert error is not None
    assert error.code == "unsupported_tool_call"
    assert AgentEventType.MODEL_TOOL_CALL_ARGUMENT_DELTA in {
        event.event_type for event in _events(items)
    }


async def test_requires_streaming_capability_without_generate_fallback() -> None:
    provider = _provider(descriptor=_descriptor(streaming=False))

    items = await _collect(_runtime(provider))
    result = _result(items).result

    assert result.status is ExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == "no_matching_model"
    assert provider.stream_calls == 0
    assert provider.generate_calls == 0


async def test_selection_requires_streaming_for_automatic_and_explicit_models() -> None:
    plain = _provider(
        provider_name="plain",
        descriptor=_descriptor(provider="plain", streaming=False),
    )
    streaming = _provider(
        provider_name="streaming",
        descriptor=_descriptor(provider="streaming"),
    )
    runtime = _runtime(plain, streaming)

    successful = await _collect(runtime, context=_context("execution-selection-1"))
    incompatible = await _collect(
        runtime,
        context=_context("execution-selection-2"),
        selection=ModelSelectionRequest(provider="plain", model="model-a"),
    )

    assert _result(successful).result.status is ExecutionStatus.COMPLETED
    assert streaming.stream_calls == 1
    assert plain.stream_calls == 0
    assert _result(incompatible).result.status is ExecutionStatus.FAILED


@pytest.mark.parametrize(
    ("stream_events", "expected_code"),
    [
        (
            (_event(ModelStreamEventType.RESPONSE_STARTED, 2),),
            "model_stream_sequence_error",
        ),
        (
            (_event(ModelStreamEventType.TEXT_DELTA, 1, {"text": "x"}),),
            "invalid_model_stream_protocol",
        ),
        (
            (_event(ModelStreamEventType.RESPONSE_STARTED, 1),),
            "incomplete_model_stream",
        ),
        (
            (
                _event(ModelStreamEventType.RESPONSE_STARTED, 1),
                _event(ModelStreamEventType.ERROR, 2, {"message": "erro remoto"}),
            ),
            "model_stream_error",
        ),
    ],
)
async def test_maps_protocol_failures_to_stable_result_codes(
    stream_events: tuple[ModelStreamEvent, ...],
    expected_code: str,
) -> None:
    items = await _collect(_runtime(_provider(stream_events=stream_events)))
    result = _result(items).result

    assert result.status is ExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == expected_code


async def test_provider_failure_during_iteration_is_not_retried() -> None:
    provider = _provider(
        stream_exception=ModelRateLimitError("limite", provider="fake"),
        stream_exception_after=1,
    )

    items = await _collect(_runtime(provider))
    result = _result(items).result

    assert result.status is ExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == "model_rate_limit"
    assert result.usage.total_tokens == 0
    assert provider.stream_calls == 1
    assert provider.generate_calls == 0
    assert provider.stream_finalizations == 1


class TrackingStreamingRuntime(AgentRuntime):
    """Capture stream state to verify cleanup invariants."""

    def __init__(self, *, model_registry: ModelProviderRegistry) -> None:
        super().__init__(model_registry=model_registry)
        self.observed_state: ExecutionState | None = None

    def _record(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
        event_type: AgentEventType,
        data: Mapping[str, object] | None = None,
    ) -> AgentEvent:
        self.observed_state = state
        return AgentRuntime._record(self, state, factory, event_type, data)


def _tracking_runtime(provider: FakeModelProvider) -> TrackingStreamingRuntime:
    registry = ModelProviderRegistry()
    registry.register(provider)
    return TrackingStreamingRuntime(model_registry=registry)


class BlockingStreamingProvider(FakeModelProvider):
    """Wait indefinitely after starting so external task cancellation is testable."""

    def __init__(self) -> None:
        super().__init__(
            descriptors=(_descriptor(),),
            response=_unused_response(),
            stream_events=(),
        )
        self.waiting = asyncio.Event()

    async def _configured_stream(self) -> AsyncIterator[ModelStreamEvent]:
        try:
            self.stream_yields += 1
            yield _event(
                ModelStreamEventType.RESPONSE_STARTED,
                1,
                {"model": "model-a"},
            )
            self.waiting.set()
            await asyncio.Event().wait()
        finally:
            self.stream_finalizations += 1


async def test_cancelled_error_marks_state_and_is_repropagated() -> None:
    provider = _provider(stream_exception=asyncio.CancelledError())
    runtime = _tracking_runtime(provider)

    with pytest.raises(asyncio.CancelledError):
        await _collect(runtime)

    assert runtime.observed_state is not None
    assert runtime.observed_state.status is ExecutionStatus.CANCELLED
    assert runtime.observed_state.turn_count == 1
    assert provider.stream_finalizations == 1


async def test_external_task_cancellation_interrupts_waiting_provider() -> None:
    provider = BlockingStreamingProvider()
    runtime = _tracking_runtime(provider)
    task = asyncio.create_task(_collect(runtime))
    await provider.waiting.wait()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert runtime.observed_state is not None
    assert runtime.observed_state.status is ExecutionStatus.CANCELLED
    assert provider.stream_calls == 1
    assert provider.stream_finalizations == 1


async def test_early_consumer_close_closes_provider_and_cancels_internal_state() -> (
    None
):
    provider = _provider()
    runtime = _tracking_runtime(provider)
    iterator = runtime.stream(
        agent=_agent(),
        input_data=AgentInput(message="Pare cedo."),
        context=_context(),
    )
    while True:
        item = await anext(iterator)
        if (
            isinstance(item, RuntimeEventItem)
            and item.event.event_type is AgentEventType.MODEL_STREAM_STARTED
        ):
            break

    await cast(AsyncGenerator[RuntimeStreamItem, None], iterator).aclose()

    assert runtime.observed_state is not None
    assert runtime.observed_state.status is ExecutionStatus.CANCELLED
    assert provider.stream_finalizations == 1


async def test_concurrent_streams_keep_context_and_sequence_isolated() -> None:
    provider = _provider()
    runtime = _runtime(provider)

    first, second = await asyncio.gather(
        _collect(runtime, context=_context("execution-concurrent-1")),
        _collect(runtime, context=_context("execution-concurrent-2")),
    )

    assert _result(first).result.status is ExecutionStatus.COMPLETED
    assert _result(second).result.status is ExecutionStatus.COMPLETED
    assert provider.stream_calls == 2
    assert provider.generate_calls == 0
    assert (
        provider.stream_contexts[0].request_id != provider.stream_contexts[1].request_id
    )
    assert {context.execution_id for context in provider.stream_contexts} == {
        "execution-concurrent-1",
        "execution-concurrent-2",
    }


async def test_success_records_one_turn_and_one_final_assistant_message() -> None:
    provider = _provider()
    runtime = _tracking_runtime(provider)

    await _collect(runtime)

    assert runtime.observed_state is not None
    assert runtime.observed_state.turn_count == 1
    assert runtime.observed_state.tool_call_count == 0
    assert len(runtime.observed_state.messages) == 3
    assert runtime.observed_state.messages[-1].content == (
        TextContent(text="Olá, mundo!"),
    )
