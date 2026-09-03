"""End-to-end tests for the non-streaming multi-turn tool loop."""

import asyncio
import json
from collections.abc import AsyncIterator, Mapping
from decimal import Decimal
from typing import Never, cast

import pytest

from atlas_agents import (
    AgentContext,
    AgentDefinition,
    AgentEvent,
    AgentEventFactory,
    AgentEventType,
    AgentInput,
    AgentResult,
    AgentRuntime,
    ExecutionBudget,
    ExecutionIdentity,
    ExecutionLimits,
    ExecutionState,
    ExecutionStatus,
    FinishReason,
    MessageRole,
    ModelCapability,
    ModelDescriptor,
    ModelExecutionContext,
    ModelMessage,
    ModelProvider,
    ModelProviderRegistry,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ModelUnavailableError,
    ModelUsage,
    TextContent,
    ToolCall,
    ToolExecutionContext,
    ToolExecutionInvariantError,
    ToolExecutionRequest,
    ToolExecutor,
    ToolOutput,
    ToolRegistry,
    ToolUnavailableError,
)
from tests.tools.fakes import FakeTool, tool_definition


class SequencedProvider(ModelProvider):
    def __init__(
        self,
        responses: tuple[ModelResponse, ...],
        *,
        capabilities: frozenset[ModelCapability] | None = None,
        exceptions: dict[int, BaseException] | None = None,
    ) -> None:
        self._responses = responses
        self._capabilities = capabilities or frozenset(
            {ModelCapability.TEXT_GENERATION, ModelCapability.TOOL_CALLING}
        )
        self._exceptions = exceptions or {}
        self.requests: list[ModelRequest] = []
        self.contexts: list[ModelExecutionContext] = []
        self.generate_calls = 0
        self.stream_calls = 0

    @property
    def provider_name(self) -> str:
        return "sequence"

    async def list_models(self) -> tuple[ModelDescriptor, ...]:
        return (
            ModelDescriptor(
                provider="sequence",
                model="model",
                capabilities=self._capabilities,
            ),
        )

    async def generate(
        self,
        request: ModelRequest,
        context: ModelExecutionContext,
    ) -> ModelResponse:
        call_index = self.generate_calls
        self.generate_calls += 1
        self.requests.append(request)
        self.contexts.append(context)
        error = self._exceptions.get(call_index)
        if error is not None:
            raise error
        return self._responses[call_index]

    def stream(
        self,
        request: ModelRequest,
        context: ModelExecutionContext,
    ) -> AsyncIterator[ModelStreamEvent]:
        del request, context
        self.stream_calls += 1
        raise AssertionError("run() não pode usar stream()")


class ConcurrentToolProvider(ModelProvider):
    def __init__(self) -> None:
        self.turns_by_execution: dict[str, int] = {}
        self.contexts: list[ModelExecutionContext] = []

    @property
    def provider_name(self) -> str:
        return "concurrent"

    async def list_models(self) -> tuple[ModelDescriptor, ...]:
        return (
            ModelDescriptor(
                provider="concurrent",
                model="model",
                capabilities=frozenset(
                    {ModelCapability.TEXT_GENERATION, ModelCapability.TOOL_CALLING}
                ),
            ),
        )

    async def generate(
        self,
        request: ModelRequest,
        context: ModelExecutionContext,
    ) -> ModelResponse:
        del request
        await asyncio.sleep(0)
        turn = self.turns_by_execution.get(context.execution_id, 0)
        self.turns_by_execution[context.execution_id] = turn + 1
        self.contexts.append(context)
        if turn == 0:
            return _tool_response(_call(f"call-{context.execution_id}"))
        return _final_response(text=context.execution_id)

    def stream(
        self,
        request: ModelRequest,
        context: ModelExecutionContext,
    ) -> AsyncIterator[ModelStreamEvent]:
        del request, context
        raise AssertionError("run() não pode usar stream()")


class InvariantFailingExecutor(ToolExecutor):
    def prepare(
        self,
        request: ToolExecutionRequest,
        context: ToolExecutionContext,
    ) -> Never:
        del request, context
        raise ToolExecutionInvariantError("Invariante de teste.")


class TrackingRuntime(AgentRuntime):
    def __init__(
        self,
        *,
        model_registry: ModelProviderRegistry,
        tool_registry: ToolRegistry,
        tool_executor: ToolExecutor,
    ) -> None:
        super().__init__(
            model_registry=model_registry,
            tool_registry=tool_registry,
            tool_executor=tool_executor,
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


def _usage(
    input_tokens: int = 1,
    output_tokens: int = 1,
    cost: str | None = None,
) -> ModelUsage:
    return ModelUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        estimated_cost=None if cost is None else Decimal(cost),
    )


def _tool_response(
    *calls: ToolCall,
    usage: ModelUsage | None = None,
    content: tuple[TextContent, ...] = (),
) -> ModelResponse:
    return ModelResponse(
        model="model",
        content=content,
        tool_calls=calls,
        finish_reason=FinishReason.TOOL_CALL,
        usage=usage or _usage(),
    )


def _final_response(
    text: str = "Concluído.",
    *,
    finish_reason: FinishReason = FinishReason.STOP,
    usage: ModelUsage | None = None,
) -> ModelResponse:
    return ModelResponse(
        model="model",
        content=(TextContent(text=text),),
        finish_reason=finish_reason,
        usage=usage or _usage(),
    )


def _call(
    call_id: str = "call-1",
    name: str = "get_customer",
    customer_id: str = "123",
) -> ToolCall:
    return ToolCall(
        tool_call_id=call_id,
        name=name,
        arguments={"customer_id": customer_id},
    )


def _agent(*tool_names: str) -> AgentDefinition:
    return AgentDefinition(
        agent_id="assistant",
        name="Assistente",
        instructions="Ajude o usuário.",
        tool_names=tool_names,
    )


def _context(*permissions: str, execution_id: str = "execution-1") -> AgentContext:
    return AgentContext(
        execution_id=execution_id,
        identity=ExecutionIdentity(
            subject="user",
            permissions=frozenset(permissions),
        ),
    )


def _runtime(
    provider: ModelProvider,
    *tools: FakeTool,
) -> TrackingRuntime:
    model_registry = ModelProviderRegistry()
    model_registry.register(provider)
    tool_registry = ToolRegistry()
    for tool in tools:
        tool_registry.register(tool)
    return TrackingRuntime(
        model_registry=model_registry,
        tool_registry=tool_registry,
        tool_executor=ToolExecutor(registry=tool_registry),
    )


async def _run(
    runtime: TrackingRuntime,
    agent: AgentDefinition,
    *,
    context: AgentContext | None = None,
    limits: ExecutionLimits | None = None,
    budget: ExecutionBudget | None = None,
) -> AgentResult[object]:
    return await runtime.run(
        agent=agent,
        input_data=AgentInput(message="Consulte o cliente."),
        context=context or _context(),
        limits=limits,
        budget=budget,
    )


def _tool_payload(message: ModelMessage) -> dict[str, object]:
    content = message.content[0]
    assert isinstance(content, TextContent)
    return cast(dict[str, object], json.loads(content.text))


async def test_two_turn_tool_loop_preserves_history_capability_and_identity() -> None:
    provider = SequencedProvider(
        (
            _tool_response(
                _call(),
                content=(TextContent(text="Vou consultar."),),
                usage=_usage(10, 5, "0.10"),
            ),
            _final_response(usage=_usage(20, 10, "0.20")),
        )
    )
    tool = FakeTool(tool_definition(), output=ToolOutput(content={"name": "Ana"}))
    runtime = _runtime(provider, tool)

    result = await _run(runtime, _agent("get_customer"))

    assert result.status is ExecutionStatus.COMPLETED
    assert result.output == "Concluído."
    assert result.usage.input_tokens == 30
    assert result.usage.output_tokens == 15
    assert result.usage.estimated_cost == Decimal("0.30")
    assert provider.generate_calls == 2
    assert provider.stream_calls == 0
    assert len({context.request_id for context in provider.contexts}) == 2
    assert [tool.name for tool in provider.requests[0].tools] == ["get_customer"]
    assert [message.role for message in provider.requests[1].messages] == [
        MessageRole.SYSTEM,
        MessageRole.USER,
        MessageRole.ASSISTANT,
        MessageRole.TOOL,
    ]
    assistant_call = provider.requests[1].messages[2]
    assert assistant_call.content == (TextContent(text="Vou consultar."),)
    assert assistant_call.tool_calls == (_call(),)
    tool_message = provider.requests[1].messages[3]
    assert tool_message.tool_call_id == "call-1"
    assert _tool_payload(tool_message) == {
        "error": None,
        "output": {"name": "Ana"},
        "status": "succeeded",
    }
    assert runtime.observed_state is not None
    assert runtime.observed_state.turn_count == 2
    assert runtime.observed_state.tool_call_count == 1
    assert len(runtime.observed_state.tool_calls) == 1
    event_types = [event.event_type for event in result.events]
    assert event_types.index(AgentEventType.TOOL_REQUESTED) < event_types.index(
        AgentEventType.TOOL_EXECUTION_STARTED
    )
    assert event_types.index(AgentEventType.TOOL_EXECUTION_STARTED) < event_types.index(
        AgentEventType.TOOL_EXECUTION_COMPLETED
    )
    assert [event.sequence for event in result.events] == list(
        range(1, len(result.events) + 1)
    )


async def test_multiple_tools_execute_sequentially_in_model_order() -> None:
    first_call = _call("call-a", "first")
    second_call = _call("call-b", "second")
    provider = SequencedProvider(
        (_tool_response(first_call, second_call), _final_response())
    )
    first = FakeTool(tool_definition(name="first"))
    second = FakeTool(tool_definition(name="second"))
    runtime = _runtime(provider, first, second)

    result = await _run(runtime, _agent("second", "first"))

    assert result.status is ExecutionStatus.COMPLETED
    assert [definition.name for definition in provider.requests[0].tools] == [
        "second",
        "first",
    ]
    assert runtime.observed_state is not None
    assert runtime.observed_state.tool_call_count == 2
    assert [record.tool_call_id for record in runtime.observed_state.tool_calls] == [
        "call-a",
        "call-b",
    ]
    tool_messages = [
        message
        for message in provider.requests[1].messages
        if message.role is MessageRole.TOOL
    ]
    assert [message.tool_call_id for message in tool_messages] == ["call-a", "call-b"]
    execution_events = [
        event.data["tool_call_id"]
        for event in result.events
        if event.event_type
        in {
            AgentEventType.TOOL_EXECUTION_STARTED,
            AgentEventType.TOOL_EXECUTION_COMPLETED,
        }
    ]
    assert execution_events == ["call-a", "call-a", "call-b", "call-b"]


@pytest.mark.parametrize(
    ("arguments", "permissions", "expected_status"),
    [
        ({"customer_id": "123"}, (), "denied"),
        ({"customer_id": 123}, ("customer.read",), "invalid_arguments"),
    ],
)
async def test_non_executable_tool_results_return_to_model_without_counting(
    arguments: dict[str, object],
    permissions: tuple[str, ...],
    expected_status: str,
) -> None:
    call = ToolCall(tool_call_id="call-1", name="get_customer", arguments=arguments)
    provider = SequencedProvider((_tool_response(call), _final_response()))
    tool = FakeTool(tool_definition(permissions=frozenset({"customer.read"})))
    runtime = _runtime(provider, tool)

    result = await _run(runtime, _agent("get_customer"), context=_context(*permissions))

    assert result.status is ExecutionStatus.COMPLETED
    assert tool.call_count == 0
    assert runtime.observed_state is not None
    assert runtime.observed_state.tool_call_count == 0
    payload = _tool_payload(provider.requests[1].messages[-1])
    assert payload["status"] == expected_status


async def test_unknown_tool_returns_controlled_result_to_model() -> None:
    provider = SequencedProvider(
        (_tool_response(_call(name="unknown")), _final_response())
    )
    available = FakeTool(tool_definition())
    runtime = _runtime(provider, available)

    result = await _run(runtime, _agent("get_customer"))

    assert result.status is ExecutionStatus.COMPLETED
    assert available.call_count == 0
    assert runtime.observed_state is not None
    assert runtime.observed_state.tool_call_count == 0
    payload = _tool_payload(provider.requests[1].messages[-1])
    error = cast(dict[str, object], payload["error"])
    assert error["code"] == "tool_not_found"


async def test_registered_tool_outside_agent_allowlist_fails_execution() -> None:
    provider = SequencedProvider((_tool_response(_call(name="hidden")),))
    allowed = FakeTool(tool_definition())
    hidden = FakeTool(tool_definition(name="hidden"))
    runtime = _runtime(provider, allowed, hidden)

    result = await _run(runtime, _agent("get_customer"))

    assert result.status is ExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == "tool_not_available_for_agent"
    assert hidden.call_count == 0
    assert provider.generate_calls == 1


async def test_tool_failure_counts_and_can_be_recovered_by_model() -> None:
    provider = SequencedProvider((_tool_response(_call()), _final_response()))
    tool = FakeTool(
        tool_definition(),
        exception=ToolUnavailableError("Dependência temporariamente indisponível."),
    )
    runtime = _runtime(provider, tool)

    result = await _run(runtime, _agent("get_customer"))

    assert result.status is ExecutionStatus.COMPLETED
    assert runtime.observed_state is not None
    assert runtime.observed_state.tool_call_count == 1
    payload = _tool_payload(provider.requests[1].messages[-1])
    assert payload["error"] == {
        "code": "tool_unavailable",
        "message": "Dependência temporariamente indisponível.",
        "retryable": True,
    }


async def test_model_explicit_retry_with_new_call_id_executes_again() -> None:
    provider = SequencedProvider(
        (
            _tool_response(_call("call-1")),
            _tool_response(_call("call-2")),
            _final_response(),
        )
    )
    tool = FakeTool(
        tool_definition(),
        exception=ToolUnavailableError("Indisponível."),
    )
    runtime = _runtime(provider, tool)

    result = await _run(runtime, _agent("get_customer"))

    assert result.status is ExecutionStatus.COMPLETED
    assert tool.call_count == 2
    assert runtime.observed_state is not None
    assert runtime.observed_state.turn_count == 3
    assert runtime.observed_state.tool_call_count == 2


async def test_duplicate_call_reuses_result_without_incrementing_counter() -> None:
    provider = SequencedProvider(
        (
            _tool_response(_call()),
            _tool_response(_call()),
            _final_response(),
        )
    )
    tool = FakeTool(tool_definition())
    runtime = _runtime(provider, tool)

    result = await _run(runtime, _agent("get_customer"))

    assert result.status is ExecutionStatus.COMPLETED
    assert tool.call_count == 1
    assert runtime.observed_state is not None
    assert runtime.observed_state.tool_call_count == 1
    assert len(runtime.observed_state.tool_calls) == 1
    deduplicated = [
        event
        for event in result.events
        if event.event_type is AgentEventType.TOOL_EXECUTION_COMPLETED
        and event.data.get("deduplicated") is True
    ]
    assert len(deduplicated) == 1


async def test_duplicate_call_with_different_payload_fails() -> None:
    provider = SequencedProvider(
        (
            _tool_response(_call(customer_id="123")),
            _tool_response(_call(customer_id="456")),
        )
    )
    tool = FakeTool(tool_definition())
    runtime = _runtime(provider, tool)

    result = await _run(runtime, _agent("get_customer"))

    assert result.status is ExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == "tool_call_id_conflict"
    assert tool.call_count == 1
    assert runtime.observed_state is not None
    assert runtime.observed_state.tool_call_count == 1


async def test_turn_limit_stops_before_required_third_model_invocation() -> None:
    provider = SequencedProvider(
        (_tool_response(_call("call-1")), _tool_response(_call("call-2")))
    )
    tool = FakeTool(tool_definition())
    runtime = _runtime(provider, tool)

    result = await _run(
        runtime,
        _agent("get_customer"),
        limits=ExecutionLimits(max_turns=2),
    )

    assert result.status is ExecutionStatus.LIMIT_EXCEEDED
    assert result.error is not None
    assert result.error.code == "execution_max_turns_exceeded"
    assert provider.generate_calls == 2
    assert tool.call_count == 2


async def test_tool_limit_stops_partial_batch_before_second_execution() -> None:
    provider = SequencedProvider((_tool_response(_call("call-a"), _call("call-b")),))
    tool = FakeTool(tool_definition())
    runtime = _runtime(provider, tool)

    result = await _run(
        runtime,
        _agent("get_customer"),
        limits=ExecutionLimits(max_tool_calls=1),
    )

    assert result.status is ExecutionStatus.LIMIT_EXCEEDED
    assert result.output is None
    assert result.error is not None
    assert result.error.code == "execution_max_tool_calls_exceeded"
    assert tool.call_count == 1
    assert runtime.observed_state is not None
    assert runtime.observed_state.tool_call_count == 1


@pytest.mark.parametrize("policy", ["tokens", "budget"])
async def test_model_policy_violation_stops_before_tool_processing(policy: str) -> None:
    provider = SequencedProvider(
        (_tool_response(_call(), usage=_usage(10, 5, "1.00")),)
    )
    tool = FakeTool(tool_definition())
    runtime = _runtime(provider, tool)
    limits = ExecutionLimits(max_total_tokens=14) if policy == "tokens" else None
    budget = (
        ExecutionBudget(max_estimated_cost=Decimal("0.99"))
        if policy == "budget"
        else None
    )

    result = await _run(
        runtime,
        _agent("get_customer"),
        limits=limits,
        budget=budget,
    )

    expected = (
        ExecutionStatus.LIMIT_EXCEEDED
        if policy == "tokens"
        else ExecutionStatus.BUDGET_EXCEEDED
    )
    assert result.status is expected
    assert tool.call_count == 0
    assert runtime.observed_state is not None
    assert runtime.observed_state.tool_calls == ()


async def test_timeout_during_tool_uses_execution_deadline() -> None:
    provider = SequencedProvider((_tool_response(_call()),))
    tool = FakeTool(tool_definition(), wait_event=asyncio.Event())
    runtime = _runtime(provider, tool)

    result = await _run(
        runtime,
        _agent("get_customer"),
        limits=ExecutionLimits(timeout_seconds=0.2),
    )

    assert result.status is ExecutionStatus.TIMED_OUT
    assert tool.call_count == 1
    assert runtime.observed_state is not None
    assert runtime.observed_state.tool_call_count == 1


async def test_external_cancellation_during_tool_is_repropagated() -> None:
    provider = SequencedProvider((_tool_response(_call()),))
    wait_event = asyncio.Event()
    tool = FakeTool(tool_definition(), wait_event=wait_event)
    runtime = _runtime(provider, tool)
    execution = asyncio.create_task(_run(runtime, _agent("get_customer")))
    await tool.started_event.wait()

    execution.cancel()

    with pytest.raises(asyncio.CancelledError):
        await execution
    assert runtime.observed_state is not None
    assert runtime.observed_state.status is ExecutionStatus.CANCELLED
    assert runtime.observed_state.tool_call_count == 1


async def test_provider_failure_on_second_turn_preserves_tool_journal() -> None:
    provider = SequencedProvider(
        (_tool_response(_call()), _final_response()),
        exceptions={1: ModelUnavailableError("Indisponível.", provider="sequence")},
    )
    tool = FakeTool(tool_definition())
    runtime = _runtime(provider, tool)

    result = await _run(runtime, _agent("get_customer"))

    assert result.status is ExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == "model_unavailable"
    assert runtime.observed_state is not None
    assert runtime.observed_state.turn_count == 2
    assert runtime.observed_state.tool_call_count == 1
    assert len(runtime.observed_state.tool_calls) == 1


@pytest.mark.parametrize(
    ("finish_reason", "expected_status"),
    [
        (FinishReason.LENGTH, ExecutionStatus.COMPLETED),
        (FinishReason.CONTENT_FILTER, ExecutionStatus.REJECTED),
    ],
)
async def test_later_turn_preserves_terminal_finish_policies(
    finish_reason: FinishReason,
    expected_status: ExecutionStatus,
) -> None:
    provider = SequencedProvider(
        (_tool_response(_call()), _final_response(finish_reason=finish_reason))
    )
    runtime = _runtime(provider, FakeTool(tool_definition()))

    result = await _run(runtime, _agent("get_customer"))

    assert result.status is expected_status


async def test_agent_tool_requires_model_tool_calling_capability() -> None:
    provider = SequencedProvider(
        (_final_response(),),
        capabilities=frozenset({ModelCapability.TEXT_GENERATION}),
    )
    runtime = _runtime(provider, FakeTool(tool_definition()))

    result = await _run(runtime, _agent("get_customer"))

    assert result.status is ExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == "no_matching_model"
    assert provider.generate_calls == 0


async def test_agent_configuration_rejects_unregistered_declared_tool() -> None:
    provider = SequencedProvider((_final_response(),))
    runtime = _runtime(provider)

    result = await _run(runtime, _agent("missing"))

    assert result.status is ExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == "agent_tool_not_registered"
    assert provider.generate_calls == 0


async def test_concurrent_tool_loops_keep_execution_state_isolated() -> None:
    provider = ConcurrentToolProvider()
    tool = FakeTool(tool_definition())
    runtime = _runtime(provider, tool)

    first, second = await asyncio.gather(
        _run(runtime, _agent("get_customer"), context=_context(execution_id="first")),
        _run(runtime, _agent("get_customer"), context=_context(execution_id="second")),
    )

    assert first.status is ExecutionStatus.COMPLETED
    assert first.output == "first"
    assert second.status is ExecutionStatus.COMPLETED
    assert second.output == "second"
    assert provider.turns_by_execution == {"first": 2, "second": 2}
    assert tool.call_count == 2
    assert [event.sequence for event in first.events] == list(
        range(1, len(first.events) + 1)
    )
    assert [event.sequence for event in second.events] == list(
        range(1, len(second.events) + 1)
    )


async def test_internal_tool_executor_invariant_fails_agent_safely() -> None:
    provider = SequencedProvider((_tool_response(_call()),))
    model_registry = ModelProviderRegistry()
    model_registry.register(provider)
    tool_registry = ToolRegistry()
    tool_registry.register(FakeTool(tool_definition()))
    runtime = TrackingRuntime(
        model_registry=model_registry,
        tool_registry=tool_registry,
        tool_executor=InvariantFailingExecutor(registry=tool_registry),
    )

    result = await _run(runtime, _agent("get_customer"))

    assert result.status is ExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == "tool_execution_invariant"
    assert runtime.observed_state is not None
    assert runtime.observed_state.tool_call_count == 0
