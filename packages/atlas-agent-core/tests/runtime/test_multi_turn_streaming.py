"""End-to-end tests for the streaming multi-turn tool loop."""

import json
from collections.abc import AsyncIterator, Mapping
from typing import cast

from atlas_agents import (
    AgentContext,
    AgentDefinition,
    AgentEvent,
    AgentEventFactory,
    AgentEventType,
    AgentInput,
    AgentRuntime,
    ExecutionIdentity,
    ExecutionState,
    ExecutionStatus,
    MessageRole,
    ModelCapability,
    ModelDescriptor,
    ModelExecutionContext,
    ModelProvider,
    ModelProviderRegistry,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ModelStreamEventType,
    RuntimeEventItem,
    RuntimeResultItem,
    ToolCall,
    ToolExecutor,
    ToolOutput,
    ToolRegistry,
)
from tests.tools.fakes import FakeTool, tool_definition


class SequencedStreamingProvider(ModelProvider):
    def __init__(self, turns: tuple[tuple[ModelStreamEvent, ...], ...]) -> None:
        self._turns = turns
        self.stream_calls = 0
        self.generate_calls = 0
        self.requests: list[ModelRequest] = []
        self.contexts: list[ModelExecutionContext] = []
        self.finalizations = 0

    @property
    def provider_name(self) -> str:
        return "stream-sequence"

    async def list_models(self) -> tuple[ModelDescriptor, ...]:
        return (
            ModelDescriptor(
                provider=self.provider_name,
                model="model",
                capabilities=frozenset(
                    {
                        ModelCapability.TEXT_GENERATION,
                        ModelCapability.STREAMING,
                        ModelCapability.TOOL_CALLING,
                    }
                ),
            ),
        )

    async def generate(
        self,
        request: ModelRequest,
        context: ModelExecutionContext,
    ) -> ModelResponse:
        del request, context
        self.generate_calls += 1
        raise AssertionError("stream() não pode usar generate()")

    def stream(
        self,
        request: ModelRequest,
        context: ModelExecutionContext,
    ) -> AsyncIterator[ModelStreamEvent]:
        index = self.stream_calls
        self.stream_calls += 1
        self.requests.append(request)
        self.contexts.append(context)
        return self._iterate(self._turns[index])

    async def _iterate(
        self,
        events: tuple[ModelStreamEvent, ...],
    ) -> AsyncIterator[ModelStreamEvent]:
        try:
            for event in events:
                yield event
        finally:
            self.finalizations += 1


class TrackingStreamingRuntime(AgentRuntime):
    def __init__(
        self,
        *,
        model_registry: ModelProviderRegistry,
        tool_registry: ToolRegistry,
    ) -> None:
        super().__init__(
            model_registry=model_registry,
            tool_registry=tool_registry,
            tool_executor=ToolExecutor(registry=tool_registry),
        )
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


def _event(
    event_type: ModelStreamEventType,
    sequence: int,
    *,
    response_id: str,
    data: dict[str, object] | None = None,
) -> ModelStreamEvent:
    return ModelStreamEvent(
        type=event_type,
        sequence=sequence,
        response_id=response_id,
        data=data or {},
    )


def _tool_turn(call: ToolCall) -> tuple[ModelStreamEvent, ...]:
    response_id = "response-tool"
    return (
        _event(
            ModelStreamEventType.RESPONSE_STARTED,
            1,
            response_id=response_id,
            data={"model": "model"},
        ),
        _event(
            ModelStreamEventType.TOOL_CALL_STARTED,
            2,
            response_id=response_id,
            data={"tool_call_id": call.tool_call_id, "name": call.name},
        ),
        _event(
            ModelStreamEventType.TOOL_CALL_ARGUMENT_DELTA,
            3,
            response_id=response_id,
            data={
                "tool_call_id": call.tool_call_id,
                "delta": json.dumps(call.arguments),
            },
        ),
        _event(
            ModelStreamEventType.TOOL_CALL_COMPLETED,
            4,
            response_id=response_id,
            data={"tool_call": call.model_dump(mode="json")},
        ),
        _event(
            ModelStreamEventType.RESPONSE_COMPLETED,
            5,
            response_id=response_id,
            data={"model": "model", "finish_reason": "tool_call"},
        ),
    )


def _text_turn() -> tuple[ModelStreamEvent, ...]:
    response_id = "response-final"
    return (
        _event(
            ModelStreamEventType.RESPONSE_STARTED,
            1,
            response_id=response_id,
            data={"model": "model"},
        ),
        _event(
            ModelStreamEventType.TEXT_DELTA,
            2,
            response_id=response_id,
            data={"text": "Cliente "},
        ),
        _event(
            ModelStreamEventType.TEXT_DELTA,
            3,
            response_id=response_id,
            data={"text": "encontrado."},
        ),
        _event(
            ModelStreamEventType.RESPONSE_COMPLETED,
            4,
            response_id=response_id,
            data={"model": "model", "finish_reason": "stop"},
        ),
    )


async def test_streaming_uses_stream_for_every_model_tool_turn() -> None:
    call = ToolCall(
        tool_call_id="call-1",
        name="get_customer",
        arguments={"customer_id": "123"},
    )
    provider = SequencedStreamingProvider((_tool_turn(call), _text_turn()))
    model_registry = ModelProviderRegistry()
    model_registry.register(provider)
    tool_registry = ToolRegistry()
    tool = FakeTool(
        tool_definition(),
        output=ToolOutput(content={"customer_id": "123"}),
    )
    tool_registry.register(tool)
    runtime = TrackingStreamingRuntime(
        model_registry=model_registry,
        tool_registry=tool_registry,
    )

    items = [
        item
        async for item in runtime.stream(
            agent=AgentDefinition(
                agent_id="assistant",
                name="Assistente",
                instructions="Consulte clientes.",
                tool_names=("get_customer",),
            ),
            input_data=AgentInput(message="Consulte o cliente 123."),
            context=AgentContext(
                execution_id="execution-stream",
                identity=ExecutionIdentity(subject="user"),
            ),
        )
    ]

    terminal = cast(RuntimeResultItem, items[-1]).result
    assert terminal.status is ExecutionStatus.COMPLETED
    assert terminal.output == "Cliente encontrado."
    assert provider.stream_calls == 2
    assert provider.generate_calls == 0
    assert provider.finalizations == 2
    assert len({context.request_id for context in provider.contexts}) == 2
    assert [message.role for message in provider.requests[1].messages] == [
        MessageRole.SYSTEM,
        MessageRole.USER,
        MessageRole.ASSISTANT,
        MessageRole.TOOL,
    ]
    assert provider.requests[1].messages[2].tool_calls == (call,)
    assert provider.requests[1].messages[3].tool_call_id == "call-1"
    assert runtime.observed_state is not None
    assert runtime.observed_state.turn_count == 2
    assert runtime.observed_state.tool_call_count == 1
    assert tool.call_count == 1
    assert [event.sequence for event in terminal.events] == list(
        range(1, len(terminal.events) + 1)
    )
    types = [event.event_type for event in terminal.events]
    assert AgentEventType.TOOL_REQUESTED in types
    assert AgentEventType.TOOL_EXECUTION_STARTED in types
    assert AgentEventType.TOOL_EXECUTION_COMPLETED in types
    stream_starts = sum(
        isinstance(item, RuntimeEventItem)
        and item.event.event_type is AgentEventType.MODEL_STREAM_STARTED
        for item in items
    )
    assert stream_starts == 2
