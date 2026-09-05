"""End-to-end tests for the provider-agnostic single-turn agent runtime."""

import asyncio
from collections.abc import Mapping
from decimal import Decimal

import pytest

from atlas_agents import (
    AgentAttachment,
    AgentContext,
    AgentDefinition,
    AgentEvent,
    AgentEventFactory,
    AgentEventType,
    AgentInput,
    AgentResult,
    AgentRuntime,
    AudioContent,
    ExecutionBudget,
    ExecutionLimits,
    ExecutionState,
    ExecutionStatus,
    FinishReason,
    ImageContent,
    MessageRole,
    ModelAuthenticationError,
    ModelCapability,
    ModelDescriptor,
    ModelInvalidRequestError,
    ModelNotFoundError,
    ModelPermissionError,
    ModelProvider,
    ModelProviderError,
    ModelProviderNotRegisteredError,
    ModelProviderRegistry,
    ModelRateLimitError,
    ModelResponse,
    ModelResponseError,
    ModelSelectionRequest,
    ModelTimeoutError,
    ModelUnavailableError,
    ModelUsage,
    TextContent,
    ToolCall,
)
from tests.fakes import FakeModelProvider


def _agent() -> AgentDefinition:
    return AgentDefinition(
        agent_id="explainer",
        name="Explainer",
        instructions="Explain concepts clearly.",
    )


def _context(execution_id: str = "execution-1") -> AgentContext:
    return AgentContext(execution_id=execution_id, metadata={"private": "ignored"})


def _descriptor(
    *,
    provider: str = "fake",
    model: str = "fake-model",
    capabilities: frozenset[ModelCapability] | None = None,
) -> ModelDescriptor:
    return ModelDescriptor(
        provider=provider,
        model=model,
        capabilities=capabilities or frozenset({ModelCapability.TEXT_GENERATION}),
    )


def _response(
    finish_reason: FinishReason = FinishReason.STOP,
    *,
    content: tuple[TextContent | ImageContent | AudioContent, ...] | None = None,
    tool_calls: tuple[ToolCall, ...] = (),
    usage: ModelUsage | None = None,
) -> ModelResponse:
    return ModelResponse(
        response_id="response-1",
        model="fake-model-revision",
        content=(TextContent(text="Dependency inversion explained."),)
        if content is None
        else content,
        tool_calls=tool_calls,
        finish_reason=finish_reason,
        usage=usage
        if usage is not None
        else ModelUsage(
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
            cached_input_tokens=2,
            reasoning_tokens=3,
            estimated_cost=Decimal("0.05"),
        ),
    )


def _provider(
    *,
    provider_name: str = "fake",
    descriptor: ModelDescriptor | None = None,
    response: ModelResponse | None = None,
    generate_exception: BaseException | None = None,
    list_exception: Exception | None = None,
    list_delay_seconds: float = 0,
    generate_delay_seconds: float = 0,
) -> FakeModelProvider:
    return FakeModelProvider(
        provider_name=provider_name,
        descriptors=(descriptor or _descriptor(provider=provider_name),),
        response=response or _response(),
        generate_exception=generate_exception,
        list_exception=list_exception,
        list_delay_seconds=list_delay_seconds,
        generate_delay_seconds=generate_delay_seconds,
    )


def _runtime(*providers: FakeModelProvider) -> AgentRuntime:
    registry = ModelProviderRegistry()
    for provider in providers:
        registry.register(provider)
    return AgentRuntime(model_registry=registry)


async def _run(
    runtime: AgentRuntime,
    *,
    input_data: AgentInput | None = None,
    context: AgentContext | None = None,
    selection: ModelSelectionRequest | None = None,
    limits: ExecutionLimits | None = None,
    budget: ExecutionBudget | None = None,
) -> AgentResult[object]:
    result = await runtime.run(
        agent=_agent(),
        input_data=input_data or AgentInput(message="Explain dependency inversion."),
        context=context or _context(),
        model_selection=selection,
        limits=limits,
        budget=budget,
    )
    assert isinstance(result, AgentResult)
    return result


async def test_runtime_executes_one_complete_text_turn() -> None:
    provider = _provider()

    result = await _run(_runtime(provider))

    assert result.status is ExecutionStatus.COMPLETED
    assert result.output == "Dependency inversion explained."
    assert result.error is None
    assert result.usage.input_tokens == 10
    assert result.usage.output_tokens == 20
    assert result.usage.total_tokens == 30
    assert result.usage.cached_input_tokens == 2
    assert result.usage.reasoning_tokens == 3
    assert result.usage.estimated_cost == Decimal("0.05")
    assert provider.generate_calls == 1
    assert provider.stream_calls == 0


async def test_happy_path_builds_request_context_lifecycle_and_event_order() -> None:
    provider = _provider()

    result = await _run(_runtime(provider))

    request = provider.requests[0]
    assert request.model == "fake-model"
    assert request.tools == ()
    assert request.structured_output is None
    assert request.temperature is None
    assert request.metadata == {}
    assert [message.role for message in request.messages] == [
        MessageRole.SYSTEM,
        MessageRole.USER,
    ]
    assert request.messages[0].content == (
        TextContent(text="Explain concepts clearly."),
    )
    assert request.messages[1].content == (
        TextContent(text="Explain dependency inversion."),
    )
    model_context = provider.contexts[0]
    assert model_context.execution_id == "execution-1"
    assert model_context.agent_id == "explainer"
    assert model_context.request_id
    assert model_context.metadata == {}

    expected_types = [
        AgentEventType.EXECUTION_CREATED,
        AgentEventType.EXECUTION_STARTED,
        AgentEventType.EXECUTION_STATUS_CHANGED,
        AgentEventType.INPUT_VALIDATION_STARTED,
        AgentEventType.INPUT_VALIDATION_COMPLETED,
        AgentEventType.EXECUTION_STATUS_CHANGED,
        AgentEventType.CONTEXT_LOADING_STARTED,
        AgentEventType.CONTEXT_LOADING_COMPLETED,
        AgentEventType.EXECUTION_STATUS_CHANGED,
        AgentEventType.MODEL_EXECUTION_STARTED,
        AgentEventType.MODEL_EXECUTION_COMPLETED,
        AgentEventType.EXECUTION_STATUS_CHANGED,
        AgentEventType.OUTPUT_VALIDATION_STARTED,
        AgentEventType.OUTPUT_VALIDATION_COMPLETED,
        AgentEventType.EXECUTION_STATUS_CHANGED,
        AgentEventType.EXECUTION_COMPLETED,
    ]
    assert [event.event_type for event in result.events] == expected_types
    assert [event.sequence for event in result.events] == list(range(1, 17))
    assert {event.execution_id for event in result.events} == {"execution-1"}
    transitions = [
        event.data["to_status"]
        for event in result.events
        if event.event_type is AgentEventType.EXECUTION_STATUS_CHANGED
    ]
    assert transitions == [
        "validating_input",
        "loading_context",
        "running",
        "validating_output",
        "completed",
    ]


@pytest.mark.parametrize(
    ("finish_reason", "expected_status", "expected_code"),
    [
        (FinishReason.LENGTH, ExecutionStatus.COMPLETED, None),
        (FinishReason.CONTENT_FILTER, ExecutionStatus.REJECTED, None),
        (FinishReason.CANCELLED, ExecutionStatus.CANCELLED, None),
        (
            FinishReason.ERROR,
            ExecutionStatus.FAILED,
            "model_error_finish_reason",
        ),
        (
            FinishReason.UNKNOWN,
            ExecutionStatus.FAILED,
            "model_unknown_finish_reason",
        ),
    ],
)
async def test_finish_reason_matrix(
    finish_reason: FinishReason,
    expected_status: ExecutionStatus,
    expected_code: str | None,
) -> None:
    provider = _provider(response=_response(finish_reason))

    result = await _run(_runtime(provider))

    assert result.status is expected_status
    assert provider.generate_calls == 1
    if finish_reason is FinishReason.LENGTH:
        assert result.output == "Dependency inversion explained."
        validation = next(
            event
            for event in result.events
            if event.event_type is AgentEventType.OUTPUT_VALIDATION_COMPLETED
        )
        assert validation.data["partial"] is True
    elif expected_code is not None:
        assert result.error is not None
        assert result.error.code == expected_code


async def test_tool_call_finish_fails_when_agent_has_no_tools() -> None:
    provider = _provider(
        response=_response(
            FinishReason.TOOL_CALL,
            tool_calls=(ToolCall(tool_call_id="call-1", name="search", arguments={}),),
        )
    )

    result = await _run(_runtime(provider))

    assert result.status is ExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == "unexpected_tool_call"
    assert provider.generate_calls == 1


@pytest.mark.parametrize("finish_reason", [FinishReason.STOP, FinishReason.LENGTH])
async def test_success_finish_without_text_fails(finish_reason: FinishReason) -> None:
    provider = _provider(
        response=_response(
            finish_reason,
            content=(ImageContent(uri="memory://image", media_type="image/png"),),
        )
    )

    result = await _run(_runtime(provider))

    assert result.status is ExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == "model_empty_text_response"
    assert result.usage.total_tokens == 30


async def test_empty_or_unsupported_input_is_rejected_without_model_call() -> None:
    provider = _provider()
    empty_result = await _run(
        _runtime(provider),
        input_data=AgentInput(message=" "),
    )
    unsupported_result = await _run(
        _runtime(provider),
        input_data=AgentInput(
            message="",
            attachments=(
                AgentAttachment(
                    attachment_id="doc-1",
                    name="document.pdf",
                    media_type="application/pdf",
                    uri="memory://document",
                ),
            ),
        ),
        context=_context("execution-2"),
    )

    assert empty_result.status is ExecutionStatus.REJECTED
    assert unsupported_result.status is ExecutionStatus.REJECTED
    assert provider.generate_calls == 0
    assert empty_result.events[-1].data["code"] == "empty_agent_input"
    assert unsupported_result.events[-1].data["code"] == "unsupported_attachment"


async def test_image_and_audio_attachments_derive_capabilities_and_content() -> None:
    capabilities = frozenset(
        {
            ModelCapability.TEXT_GENERATION,
            ModelCapability.VISION,
            ModelCapability.AUDIO_INPUT,
        }
    )
    provider = _provider(descriptor=_descriptor(capabilities=capabilities))
    input_data = AgentInput(
        message="Describe these inputs.",
        attachments=(
            AgentAttachment(
                attachment_id="image-1",
                name="image.png",
                media_type="image/png",
                uri="memory://image",
            ),
            AgentAttachment(
                attachment_id="audio-1",
                name="audio.wav",
                media_type="audio/wav",
                uri="memory://audio",
            ),
        ),
    )

    result = await _run(_runtime(provider), input_data=input_data)

    assert result.status is ExecutionStatus.COMPLETED
    user_content = provider.requests[0].messages[1].content
    assert isinstance(user_content[1], ImageContent)
    assert isinstance(user_content[2], AudioContent)


async def test_capability_selection_chooses_compatible_provider() -> None:
    incompatible = _provider(provider_name="text-only")
    compatible = _provider(
        provider_name="vision",
        descriptor=_descriptor(
            provider="vision",
            capabilities=frozenset(
                {ModelCapability.TEXT_GENERATION, ModelCapability.VISION}
            ),
        ),
    )
    image_input = AgentInput(
        message="Describe.",
        attachments=(
            AgentAttachment(
                attachment_id="image",
                name="image.png",
                media_type="image/png",
                uri="memory://image",
            ),
        ),
    )

    result = await _run(
        _runtime(incompatible, compatible),
        input_data=image_input,
    )

    assert result.status is ExecutionStatus.COMPLETED
    assert incompatible.generate_calls == 0
    assert compatible.generate_calls == 1


async def test_explicit_incompatible_selection_fails_without_fallback_or_turn() -> None:
    explicit = _provider(provider_name="explicit")
    fallback = _provider(
        provider_name="fallback",
        descriptor=_descriptor(
            provider="fallback",
            capabilities=frozenset(
                {ModelCapability.TEXT_GENERATION, ModelCapability.VISION}
            ),
        ),
    )
    image_input = AgentInput(
        message="Describe.",
        attachments=(
            AgentAttachment(
                attachment_id="image",
                name="image.png",
                media_type="image/png",
                uri="memory://image",
            ),
        ),
    )

    result = await _run(
        _runtime(explicit, fallback),
        input_data=image_input,
        selection=ModelSelectionRequest(provider="explicit", model="fake-model"),
    )

    assert result.status is ExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == "model_capability_mismatch"
    assert explicit.generate_calls == 0
    assert fallback.generate_calls == 0
    assert AgentEventType.MODEL_EXECUTION_STARTED not in {
        event.event_type for event in result.events
    }


async def test_empty_registry_returns_failed_result_without_invocation() -> None:
    result = await _run(AgentRuntime(model_registry=ModelProviderRegistry()))

    assert result.status is ExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == "no_matching_model"
    assert result.usage.total_tokens == 0


@pytest.mark.parametrize(
    ("error_type", "code", "retryable"),
    [
        (ModelAuthenticationError, "model_authentication_error", False),
        (ModelPermissionError, "model_permission_error", False),
        (ModelNotFoundError, "model_not_found", False),
        (ModelRateLimitError, "model_rate_limit", True),
        (ModelTimeoutError, "model_timeout", True),
        (ModelUnavailableError, "model_unavailable", True),
        (ModelInvalidRequestError, "model_invalid_request", False),
        (ModelResponseError, "model_response_error", False),
        (ModelProviderError, "model_provider_error", False),
    ],
)
async def test_provider_errors_are_normalized_without_retry(
    error_type: type[ModelProviderError],
    code: str,
    retryable: bool,
) -> None:
    provider = _provider(
        generate_exception=error_type(
            "Falha segura do provider",
            provider="fake",
            model="fake-model",
        )
    )

    result = await _run(_runtime(provider))

    assert result.status is ExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == code
    assert result.error.retryable is retryable
    assert result.error.details == {"provider": "fake", "model": "fake-model"}
    assert provider.generate_calls == 1
    assert result.usage.total_tokens == 0


async def test_selection_provider_and_unexpected_errors_become_safe_results() -> None:
    provider_error = _provider(
        list_exception=ModelUnavailableError(
            "Catálogo indisponível",
            provider="fake",
        )
    )
    unexpected_list_error = _provider(list_exception=ValueError("sensitive"))
    unexpected_generate_error = _provider(generate_exception=ValueError("sensitive"))

    provider_result = await _run(_runtime(provider_error))
    list_result = await _run(
        _runtime(unexpected_list_error), context=_context("execution-2")
    )
    generate_result = await _run(
        _runtime(unexpected_generate_error), context=_context("execution-3")
    )

    assert provider_result.error is not None
    assert provider_result.error.code == "model_unavailable"
    assert list_result.error is not None
    assert list_result.error.code == "runtime_error"
    assert generate_result.error is not None
    assert generate_result.error.code == "runtime_error"
    assert "sensitive" not in generate_result.error.message


class TrackingRuntime(AgentRuntime):
    """Capture the per-call state solely to assert cancellation cleanup."""

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


async def test_cancelled_error_marks_cancelled_and_is_repropagated() -> None:
    provider = _provider(generate_exception=asyncio.CancelledError())
    registry = ModelProviderRegistry()
    registry.register(provider)
    runtime = TrackingRuntime(model_registry=registry)

    with pytest.raises(asyncio.CancelledError):
        await _run(runtime)

    assert provider.generate_calls == 1
    assert runtime.observed_state is not None
    assert runtime.observed_state.status is ExecutionStatus.CANCELLED
    assert runtime.observed_state.turn_count == 1
    assert runtime.observed_state.events[-1].event_type is (
        AgentEventType.EXECUTION_CANCELLED
    )


async def test_state_observation_proves_turn_and_assistant_message_invariants() -> None:
    successful_provider = _provider()
    successful_registry = ModelProviderRegistry()
    successful_registry.register(successful_provider)
    successful_runtime = TrackingRuntime(model_registry=successful_registry)

    await _run(successful_runtime)

    assert successful_runtime.observed_state is not None
    assert successful_runtime.observed_state.turn_count == 1
    assert successful_runtime.observed_state.tool_call_count == 0
    assert len(successful_runtime.observed_state.messages) == 3
    assert successful_runtime.observed_state.messages[-1].role is MessageRole.ASSISTANT

    failing_provider = _provider(
        generate_exception=ModelRateLimitError(
            "Limite atingido",
            provider="fake",
            model="fake-model",
        )
    )
    failing_registry = ModelProviderRegistry()
    failing_registry.register(failing_provider)
    failing_runtime = TrackingRuntime(model_registry=failing_registry)
    await _run(failing_runtime, context=_context("execution-failed"))
    assert failing_runtime.observed_state is not None
    assert failing_runtime.observed_state.turn_count == 1

    selection_runtime = TrackingRuntime(model_registry=ModelProviderRegistry())
    await _run(selection_runtime, context=_context("execution-selection"))
    assert selection_runtime.observed_state is not None
    assert selection_runtime.observed_state.turn_count == 0


class VanishingProviderRegistry(ModelProviderRegistry):
    """Simulate an unsupported concurrent removal between select and get."""

    def get(self, provider_name: str) -> ModelProvider:
        raise ModelProviderNotRegisteredError(provider_name)


async def test_provider_disappearing_after_selection_is_normalized() -> None:
    provider = _provider()
    registry = VanishingProviderRegistry()
    registry.register(provider)

    result = await _run(AgentRuntime(model_registry=registry))

    assert result.status is ExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == "model_provider_not_registered"
    assert provider.generate_calls == 0


async def test_concurrent_executions_keep_independent_event_sequences() -> None:
    provider = _provider()
    runtime = _runtime(provider)

    first, second = await asyncio.gather(
        _run(runtime, context=_context("execution-a")),
        _run(runtime, context=_context("execution-b")),
    )

    assert provider.generate_calls == 2
    assert [event.sequence for event in first.events] == list(range(1, 17))
    assert [event.sequence for event in second.events] == list(range(1, 17))
    assert {event.execution_id for event in first.events} == {"execution-a"}
    assert {event.execution_id for event in second.events} == {"execution-b"}
    assert provider.contexts[0].request_id != provider.contexts[1].request_id


async def test_max_turns_one_allows_the_single_model_invocation() -> None:
    provider = _provider()

    result = await _run(_runtime(provider), limits=ExecutionLimits(max_turns=1))

    assert result.status is ExecutionStatus.COMPLETED
    assert provider.generate_calls == 1


@pytest.mark.parametrize(
    ("limits", "expected_code", "expected_reason"),
    [
        (
            ExecutionLimits(max_input_tokens=9),
            "execution_max_input_tokens_exceeded",
            "max_input_tokens",
        ),
        (
            ExecutionLimits(max_output_tokens=19),
            "execution_max_output_tokens_exceeded",
            "max_output_tokens",
        ),
        (
            ExecutionLimits(max_total_tokens=29),
            "execution_max_total_tokens_exceeded",
            "max_total_tokens",
        ),
    ],
)
async def test_token_limits_preserve_usage_and_skip_assistant_message(
    limits: ExecutionLimits,
    expected_code: str,
    expected_reason: str,
) -> None:
    provider = _provider()
    registry = ModelProviderRegistry()
    registry.register(provider)
    runtime = TrackingRuntime(model_registry=registry)

    result = await _run(runtime, limits=limits)

    assert result.status is ExecutionStatus.LIMIT_EXCEEDED
    assert result.output is None
    assert result.usage.total_tokens == 30
    assert result.error is not None
    assert result.error.code == expected_code
    assert result.events[-1].event_type is AgentEventType.EXECUTION_LIMIT_EXCEEDED
    assert result.events[-1].data == {
        "reason": expected_reason,
        "limit": next(value for value in limits.model_dump().values() if value),
        "observed": {
            "max_input_tokens": 10,
            "max_output_tokens": 20,
            "max_total_tokens": 30,
        }[expected_reason],
    }
    assert provider.generate_calls == 1
    assert runtime.observed_state is not None
    assert len(runtime.observed_state.messages) == 2


async def test_token_limit_wins_when_budget_is_also_exceeded() -> None:
    result = await _run(
        _runtime(_provider()),
        limits=ExecutionLimits(max_total_tokens=29),
        budget=ExecutionBudget(max_estimated_cost=Decimal("0.01")),
    )

    assert result.status is ExecutionStatus.LIMIT_EXCEEDED
    assert result.error is not None
    assert result.error.code == "execution_max_total_tokens_exceeded"


async def test_budget_enforcement_allows_equal_and_unknown_costs() -> None:
    equal = await _run(
        _runtime(_provider()),
        budget=ExecutionBudget(max_estimated_cost=Decimal("0.05")),
    )
    unknown_provider = _provider(
        response=_response(
            usage=ModelUsage(input_tokens=1, output_tokens=1, total_tokens=2)
        )
    )
    unknown = await _run(
        _runtime(unknown_provider),
        context=_context("execution-unknown-cost"),
        budget=ExecutionBudget(max_estimated_cost=Decimal("0")),
    )

    assert equal.status is ExecutionStatus.COMPLETED
    assert unknown.status is ExecutionStatus.COMPLETED
    assert unknown.usage.estimated_cost is None


async def test_budget_violation_is_terminal_and_preserves_reported_usage() -> None:
    provider = _provider()
    registry = ModelProviderRegistry()
    registry.register(provider)
    runtime = TrackingRuntime(model_registry=registry)

    result = await _run(
        runtime,
        budget=ExecutionBudget(
            max_estimated_cost=Decimal("0.04"),
            currency="USD",
        ),
    )

    assert result.status is ExecutionStatus.BUDGET_EXCEEDED
    assert result.output is None
    assert result.usage.estimated_cost == Decimal("0.05")
    assert result.error is not None
    assert result.error.code == "execution_budget_exceeded"
    assert result.events[-1].event_type is AgentEventType.EXECUTION_BUDGET_EXCEEDED
    assert result.events[-1].data == {"limit": "0.04", "observed": "0.05"}
    assert runtime.observed_state is not None
    assert len(runtime.observed_state.messages) == 2


async def test_execution_override_replaces_runtime_default_limits() -> None:
    provider = _provider()
    registry = ModelProviderRegistry()
    registry.register(provider)
    runtime = AgentRuntime(
        model_registry=registry,
        limits=ExecutionLimits(max_total_tokens=1),
    )

    default_result = await _run(runtime)
    override_result = await _run(
        runtime,
        context=_context("execution-policy-override"),
        limits=ExecutionLimits(),
    )

    assert default_result.status is ExecutionStatus.LIMIT_EXCEEDED
    assert override_result.status is ExecutionStatus.COMPLETED


async def test_runtime_timeout_covers_provider_call_without_inventing_usage() -> None:
    provider = _provider(generate_delay_seconds=0.05)

    result = await _run(
        _runtime(provider),
        limits=ExecutionLimits(timeout_seconds=0.001),
    )

    assert result.status is ExecutionStatus.TIMED_OUT
    assert result.usage.total_tokens == 0
    assert result.error is not None
    assert result.error.code == "execution_timed_out"
    assert result.events[-1].event_type is AgentEventType.EXECUTION_TIMED_OUT
    assert result.events[-1].data["timeout_seconds"] == 0.001
    elapsed = result.events[-1].data["elapsed_seconds"]
    assert isinstance(elapsed, int | float)
    assert elapsed >= 0
    assert provider.generate_calls == 1


async def test_runtime_timeout_covers_model_selection() -> None:
    provider = _provider(list_delay_seconds=0.05)

    result = await _run(
        _runtime(provider),
        limits=ExecutionLimits(timeout_seconds=0.001),
    )

    assert result.status is ExecutionStatus.TIMED_OUT
    assert result.error is not None
    assert result.error.code == "execution_timed_out"
    assert provider.list_models_calls == 1
    assert provider.generate_calls == 0


async def test_provider_timeout_remains_failed_with_runtime_deadline_configured() -> (
    None
):
    provider = _provider(
        generate_exception=ModelTimeoutError("provider lento", provider="fake")
    )

    result = await _run(
        _runtime(provider),
        limits=ExecutionLimits(timeout_seconds=10),
    )

    assert result.status is ExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == "model_timeout"


async def test_external_cancellation_wins_before_configured_runtime_deadline() -> None:
    provider = _provider(generate_delay_seconds=1)
    registry = ModelProviderRegistry()
    registry.register(provider)
    runtime = TrackingRuntime(model_registry=registry)
    task = asyncio.create_task(
        _run(runtime, limits=ExecutionLimits(timeout_seconds=10))
    )
    await provider.generate_started.wait()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert runtime.observed_state is not None
    assert runtime.observed_state.status is ExecutionStatus.CANCELLED


async def test_concurrent_executions_keep_policy_scope_isolated() -> None:
    provider = _provider()
    runtime = _runtime(provider)

    limited, allowed = await asyncio.gather(
        _run(
            runtime,
            context=_context("execution-limited"),
            limits=ExecutionLimits(max_total_tokens=29),
        ),
        _run(
            runtime,
            context=_context("execution-allowed"),
            limits=ExecutionLimits(max_total_tokens=30),
        ),
    )

    assert limited.status is ExecutionStatus.LIMIT_EXCEEDED
    assert allowed.status is ExecutionStatus.COMPLETED
    assert provider.generate_calls == 2
