"""End-to-end tests for resumable human approval in run mode."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal

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
    ApprovalContext,
    ApprovalDecision,
    ApprovalDecisionMismatchError,
    ApprovalDecisionType,
    ApprovalRequired,
    ApprovalRequirement,
    CheckpointNotFoundError,
    ExecutionBudget,
    ExecutionCheckpoint,
    ExecutionIdentity,
    ExecutionLimits,
    ExecutionState,
    ExecutionStateRestorer,
    ExecutionStatus,
    ExecutionSuspension,
    FinishReason,
    InvalidCheckpointError,
    ModelDescriptor,
    ModelExecutionContext,
    ModelProviderRegistry,
    ModelRequest,
    ModelResponse,
    ModelUsage,
    TextContent,
    ToolApprovalMode,
    ToolCall,
    ToolDefinition,
    ToolExecutionRequest,
    ToolExecutor,
    ToolOutput,
    ToolRegistry,
    UnsupportedCheckpointVersionError,
)
from tests.approvals.fakes import FakeCheckpointStore, FixedApprovalPolicy
from tests.runtime.test_multi_turn_runtime import SequencedProvider
from tests.tools.fakes import FakeTool, tool_definition


class TrackingApprovalRuntime(AgentRuntime):
    def __init__(
        self,
        *,
        model_registry: ModelProviderRegistry,
        tool_registry: ToolRegistry,
        checkpoint_store: FakeCheckpointStore | None,
        approval_policy: FixedApprovalPolicy | ExpiringPolicy | None = None,
        clock: MutableClock | None = None,
    ) -> None:
        super().__init__(
            model_registry=model_registry,
            tool_registry=tool_registry,
            tool_executor=ToolExecutor(registry=tool_registry),
            checkpoint_store=checkpoint_store,
            approval_policy=approval_policy,
            clock=clock,
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


class MutableClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def __call__(self) -> datetime:
        return self.current


class ExpiringPolicy:
    def __init__(self, expires_at: datetime) -> None:
        self.expires_at = expires_at

    def evaluate_tool(
        self,
        *,
        tool: ToolDefinition,
        request: ToolExecutionRequest,
        context: ApprovalContext,
    ) -> ApprovalRequirement:
        del tool, request, context
        return ApprovalRequired(
            reason="A aprovação possui prazo.",
            summary="Autorizar operação com prazo?",
            expires_at=self.expires_at,
        )


class CountingProvider(SequencedProvider):
    def __init__(self, responses: tuple[ModelResponse, ...]) -> None:
        super().__init__(responses)
        self.list_models_calls = 0

    async def list_models(self) -> tuple[ModelDescriptor, ...]:
        self.list_models_calls += 1
        return await super().list_models()


class DelayedProvider(SequencedProvider):
    async def generate(
        self,
        request: ModelRequest,
        context: ModelExecutionContext,
    ) -> ModelResponse:
        await asyncio.sleep(0.03)
        return await super().generate(request, context)


def _call(call_id: str = "call-1", name: str = "sensitive") -> ToolCall:
    return ToolCall(
        tool_call_id=call_id,
        name=name,
        arguments={"customer_id": "123"},
    )


def _tool_response(
    *calls: ToolCall,
    input_tokens: int = 2,
    estimated_cost: Decimal | None = None,
) -> ModelResponse:
    return ModelResponse(
        model="model",
        tool_calls=calls,
        finish_reason=FinishReason.TOOL_CALL,
        usage=ModelUsage(
            input_tokens=input_tokens,
            output_tokens=1,
            total_tokens=input_tokens + 1,
            estimated_cost=estimated_cost,
        ),
    )


def _final_response(*, estimated_cost: Decimal | None = None) -> ModelResponse:
    return ModelResponse(
        model="model",
        content=(TextContent(text="Operação concluída."),),
        finish_reason=FinishReason.STOP,
        usage=ModelUsage(
            input_tokens=3,
            output_tokens=2,
            total_tokens=5,
            estimated_cost=estimated_cost,
        ),
    )


def _agent(*tool_names: str) -> AgentDefinition:
    return AgentDefinition(
        agent_id="assistant",
        name="Assistente",
        instructions="Ajude o usuário.",
        tool_names=tool_names,
    )


def _decision(
    suspension: ExecutionSuspension,
    decision: ApprovalDecisionType = ApprovalDecisionType.APPROVE,
) -> ApprovalDecision:
    return ApprovalDecision(
        approval_request_id=suspension.approval_request.approval_request_id,
        decision=decision,
        decided_at=datetime.now(UTC),
        decided_by=ExecutionIdentity(subject="manager"),
        reason="Decisão revisada.",
    )


def _runtime(
    provider: SequencedProvider,
    *tools: FakeTool,
    store: FakeCheckpointStore | None = None,
    policy: FixedApprovalPolicy | ExpiringPolicy | None = None,
    clock: MutableClock | None = None,
) -> tuple[TrackingApprovalRuntime, ModelProviderRegistry, ToolRegistry]:
    model_registry = ModelProviderRegistry()
    model_registry.register(provider)
    tool_registry = ToolRegistry()
    for tool in tools:
        tool_registry.register(tool)
    runtime = TrackingApprovalRuntime(
        model_registry=model_registry,
        tool_registry=tool_registry,
        checkpoint_store=store,
        approval_policy=policy,
        clock=clock,
    )
    return runtime, model_registry, tool_registry


async def _start(
    runtime: AgentRuntime, agent: AgentDefinition
) -> AgentResult[object] | ExecutionSuspension:
    return await runtime.run(
        agent=agent,
        input_data=AgentInput(message="Execute a operação."),
        context=AgentContext(
            execution_id="execution-1",
            identity=ExecutionIdentity(
                subject="user",
                permissions=frozenset({"customer.write"}),
            ),
        ),
    )


async def test_required_approval_suspends_and_approve_resumes_same_execution() -> None:
    provider = CountingProvider((_tool_response(_call()), _final_response()))
    store = FakeCheckpointStore()
    tool = FakeTool(
        tool_definition(name="sensitive", approval_mode=ToolApprovalMode.REQUIRED),
        output=ToolOutput(content={"updated": True}),
    )
    runtime, _, _ = _runtime(provider, tool, store=store)

    outcome = await _start(runtime, _agent("sensitive"))

    assert isinstance(outcome, ExecutionSuspension)
    assert outcome.status is ExecutionStatus.WAITING_FOR_APPROVAL
    assert tool.call_count == 0
    checkpoint = store.peek(outcome.resume_token)
    assert checkpoint.turn_count == 1
    assert checkpoint.tool_call_count == 0
    assert checkpoint.usage.total_tokens == 3
    assert checkpoint.model_dump_json()
    assert checkpoint.remaining_timeout_seconds is None
    assert checkpoint.pending_tool_calls == (_call(),)
    assert "resume_token" not in "".join(
        event.model_dump_json() for event in checkpoint.events
    )

    result = await runtime.resume(
        resume_token=outcome.resume_token,
        decision=_decision(outcome),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.COMPLETED
    assert result.output == "Operação concluída."
    assert result.usage.total_tokens == 8
    assert tool.call_count == 1
    assert provider.generate_calls == 2
    assert provider.list_models_calls == 1
    assert runtime.observed_state is not None
    assert runtime.observed_state.turn_count == 2
    assert runtime.observed_state.tool_call_count == 1
    assert len(runtime.observed_state.approval_history) == 1
    assert runtime.observed_state.pending_approval is None
    assert [event.sequence for event in result.events] == list(
        range(1, len(result.events) + 1)
    )
    types = [event.event_type for event in result.events]
    assert types.index(AgentEventType.EXECUTION_SUSPENDED) < types.index(
        AgentEventType.EXECUTION_RESUMED
    )
    assert types.index(AgentEventType.APPROVAL_GRANTED) < types.index(
        AgentEventType.TOOL_EXECUTION_STARTED
    )


async def test_rejection_returns_terminal_rejected_result_without_tool_execution() -> (
    None
):
    provider = SequencedProvider((_tool_response(_call()),))
    store = FakeCheckpointStore()
    tool = FakeTool(
        tool_definition(name="sensitive", approval_mode=ToolApprovalMode.REQUIRED)
    )
    runtime, _, _ = _runtime(provider, tool, store=store)
    outcome = await _start(runtime, _agent("sensitive"))
    assert isinstance(outcome, ExecutionSuspension)

    result = await runtime.resume(
        resume_token=outcome.resume_token,
        decision=_decision(outcome, ApprovalDecisionType.REJECT),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.REJECTED
    assert result.output is None
    assert result.error is not None
    assert result.error.code == "approval_rejected"
    assert tool.call_count == 0
    assert provider.generate_calls == 1


async def test_expired_approval_is_rejected_when_resume_is_attempted() -> None:
    requested_at = datetime(2026, 6, 1, tzinfo=UTC)
    clock = MutableClock(requested_at)
    provider = SequencedProvider((_tool_response(_call()),))
    store = FakeCheckpointStore()
    tool = FakeTool(
        tool_definition(
            name="sensitive",
            approval_mode=ToolApprovalMode.POLICY_CONTROLLED,
        )
    )
    runtime, _, _ = _runtime(
        provider,
        tool,
        store=store,
        policy=ExpiringPolicy(requested_at + timedelta(minutes=5)),
        clock=clock,
    )
    outcome = await _start(runtime, _agent("sensitive"))
    assert isinstance(outcome, ExecutionSuspension)
    clock.current = requested_at + timedelta(minutes=5)

    result = await runtime.resume(
        resume_token=outcome.resume_token,
        decision=_decision(outcome),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.REJECTED
    assert result.error is not None
    assert result.error.code == "approval_expired"
    assert tool.call_count == 0


@pytest.mark.parametrize("failure", ["missing_store", "save_error"])
async def test_required_approval_without_durable_checkpoint_fails(failure: str) -> None:
    provider = SequencedProvider((_tool_response(_call()),))
    store = None if failure == "missing_store" else FakeCheckpointStore(fail_save=True)
    tool = FakeTool(
        tool_definition(name="sensitive", approval_mode=ToolApprovalMode.REQUIRED)
    )
    runtime, _, _ = _runtime(provider, tool, store=store)

    result = await _start(runtime, _agent("sensitive"))

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == (
        "approval_checkpoint_store_required"
        if failure == "missing_store"
        else "checkpoint_save_failed"
    )
    assert tool.call_count == 0


@pytest.mark.parametrize("case", ["permission", "arguments"])
async def test_permission_and_validation_precede_approval_policy(case: str) -> None:
    provider = SequencedProvider((_tool_response(_call()), _final_response()))
    store = FakeCheckpointStore()
    policy = FixedApprovalPolicy(required=True)
    call = (
        _call()
        if case == "permission"
        else ToolCall(
            tool_call_id="call-1",
            name="sensitive",
            arguments={"customer_id": 123},
        )
    )
    provider = SequencedProvider((_tool_response(call), _final_response()))
    permissions = frozenset({"missing"}) if case == "permission" else frozenset()
    tool = FakeTool(
        tool_definition(
            name="sensitive",
            permissions=permissions,
            approval_mode=ToolApprovalMode.POLICY_CONTROLLED,
        )
    )
    runtime, _, _ = _runtime(provider, tool, store=store, policy=policy)

    result = await _start(runtime, _agent("sensitive"))

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.COMPLETED
    assert policy.call_count == 0
    assert store.save_calls == 0
    assert tool.call_count == 0


async def test_policy_controlled_not_required_executes_without_suspension() -> None:
    provider = SequencedProvider((_tool_response(_call()), _final_response()))
    policy = FixedApprovalPolicy(required=False)
    tool = FakeTool(
        tool_definition(
            name="sensitive",
            approval_mode=ToolApprovalMode.POLICY_CONTROLLED,
        )
    )
    runtime, _, _ = _runtime(provider, tool, policy=policy)

    result = await _start(runtime, _agent("sensitive"))

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.COMPLETED
    assert policy.call_count == 1
    assert tool.call_count == 1


async def test_mismatched_decision_consumes_token_and_replay_is_rejected() -> None:
    provider = SequencedProvider((_tool_response(_call()), _final_response()))
    store = FakeCheckpointStore()
    tool = FakeTool(
        tool_definition(name="sensitive", approval_mode=ToolApprovalMode.REQUIRED)
    )
    runtime, _, _ = _runtime(provider, tool, store=store)
    outcome = await _start(runtime, _agent("sensitive"))
    assert isinstance(outcome, ExecutionSuspension)
    mismatch = ApprovalDecision(
        approval_request_id="other",
        decision=ApprovalDecisionType.APPROVE,
        decided_at=datetime.now(UTC),
    )

    with pytest.raises(ApprovalDecisionMismatchError):
        await runtime.resume(resume_token=outcome.resume_token, decision=mismatch)
    with pytest.raises(CheckpointNotFoundError):
        await runtime.resume(
            resume_token=outcome.resume_token,
            decision=_decision(outcome),
        )
    assert tool.call_count == 0


async def test_two_sensitive_tools_suspend_and_resume_sequentially() -> None:
    first_call = _call("call-a", "first")
    second_call = _call("call-b", "second")
    provider = SequencedProvider(
        (_tool_response(first_call, second_call), _final_response())
    )
    store = FakeCheckpointStore()
    first = FakeTool(
        tool_definition(name="first", approval_mode=ToolApprovalMode.REQUIRED)
    )
    second = FakeTool(
        tool_definition(name="second", approval_mode=ToolApprovalMode.REQUIRED)
    )
    runtime, _, _ = _runtime(provider, first, second, store=store)

    first_suspension = await _start(runtime, _agent("first", "second"))
    assert isinstance(first_suspension, ExecutionSuspension)
    second_suspension = await runtime.resume(
        resume_token=first_suspension.resume_token,
        decision=_decision(first_suspension),
    )
    assert isinstance(second_suspension, ExecutionSuspension)
    result = await runtime.resume(
        resume_token=second_suspension.resume_token,
        decision=_decision(second_suspension),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.COMPLETED
    assert first.call_count == 1
    assert second.call_count == 1
    assert store.save_calls == 2
    assert runtime.observed_state is not None
    assert runtime.observed_state.turn_count == 2
    assert runtime.observed_state.tool_call_count == 2
    assert len(runtime.observed_state.approval_history) == 2


async def test_limits_are_rechecked_after_approval_without_resetting_counters() -> None:
    normal_call = _call("call-a", "normal")
    sensitive_call = _call("call-b", "sensitive")
    provider = SequencedProvider((_tool_response(normal_call, sensitive_call),))
    store = FakeCheckpointStore()
    normal = FakeTool(tool_definition(name="normal"))
    sensitive = FakeTool(
        tool_definition(name="sensitive", approval_mode=ToolApprovalMode.REQUIRED)
    )
    runtime, _, _ = _runtime(provider, normal, sensitive, store=store)

    outcome = await runtime.run(
        agent=_agent("normal", "sensitive"),
        input_data=AgentInput(message="Execute."),
        context=AgentContext(execution_id="execution-1"),
        limits=ExecutionLimits(max_tool_calls=1),
    )
    assert isinstance(outcome, ExecutionSuspension)
    result = await runtime.resume(
        resume_token=outcome.resume_token,
        decision=_decision(outcome),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.LIMIT_EXCEEDED
    assert normal.call_count == 1
    assert sensitive.call_count == 0
    assert runtime.observed_state is not None
    assert runtime.observed_state.tool_call_count == 1


@pytest.mark.parametrize("missing", ["provider", "tool"])
async def test_missing_provider_or_tool_after_resume_fails_without_fallback(
    missing: str,
) -> None:
    provider = SequencedProvider((_tool_response(_call()), _final_response()))
    store = FakeCheckpointStore()
    tool = FakeTool(
        tool_definition(name="sensitive", approval_mode=ToolApprovalMode.REQUIRED)
    )
    runtime, model_registry, tool_registry = _runtime(provider, tool, store=store)
    outcome = await _start(runtime, _agent("sensitive"))
    assert isinstance(outcome, ExecutionSuspension)
    if missing == "provider":
        model_registry.unregister("sequence")
    else:
        tool_registry.unregister("sensitive")

    provider_result = await runtime.resume(
        resume_token=outcome.resume_token,
        decision=_decision(outcome),
    )

    assert isinstance(provider_result, AgentResult)
    assert provider_result.status is ExecutionStatus.FAILED
    assert provider_result.error is not None
    assert provider_result.error.code == (
        "model_provider_not_registered"
        if missing == "provider"
        else "tool_not_found_after_resume"
    )
    assert tool.call_count == 0


async def test_checkpoint_version_and_corruption_are_rejected() -> None:
    provider = SequencedProvider((_tool_response(_call()), _final_response()))
    store = FakeCheckpointStore()
    tool = FakeTool(
        tool_definition(name="sensitive", approval_mode=ToolApprovalMode.REQUIRED)
    )
    runtime, _, _ = _runtime(provider, tool, store=store)
    outcome = await _start(runtime, _agent("sensitive"))
    assert isinstance(outcome, ExecutionSuspension)
    checkpoint = store.peek(outcome.resume_token)
    restorer = ExecutionStateRestorer()

    unsupported = checkpoint.model_copy(update={"checkpoint_version": 999})
    with pytest.raises(UnsupportedCheckpointVersionError):
        restorer.restore(unsupported)

    corrupted_values = checkpoint.__dict__.copy()
    corrupted_values["pending_tool_calls"] = ()
    corrupted = ExecutionCheckpoint.model_construct(**corrupted_values)
    with pytest.raises(InvalidCheckpointError):
        restorer.restore(corrupted)


async def test_turn_limit_is_preserved_after_resume() -> None:
    provider = SequencedProvider((_tool_response(_call()), _final_response()))
    store = FakeCheckpointStore()
    tool = FakeTool(
        tool_definition(name="sensitive", approval_mode=ToolApprovalMode.REQUIRED)
    )
    runtime, _, _ = _runtime(provider, tool, store=store)
    outcome = await runtime.run(
        agent=_agent("sensitive"),
        input_data=AgentInput(message="Execute."),
        context=AgentContext(execution_id="execution-1"),
        limits=ExecutionLimits(max_turns=1),
    )
    assert isinstance(outcome, ExecutionSuspension)

    result = await runtime.resume(
        resume_token=outcome.resume_token,
        decision=_decision(outcome),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.LIMIT_EXCEEDED
    assert tool.call_count == 1
    assert provider.generate_calls == 1


async def test_human_wait_does_not_consume_preserved_timeout() -> None:
    provider = DelayedProvider((_tool_response(_call()), _final_response()))
    store = FakeCheckpointStore()
    tool = FakeTool(
        tool_definition(name="sensitive", approval_mode=ToolApprovalMode.REQUIRED)
    )
    runtime, _, _ = _runtime(provider, tool, store=store)
    outcome = await runtime.run(
        agent=_agent("sensitive"),
        input_data=AgentInput(message="Execute."),
        context=AgentContext(execution_id="execution-1"),
        limits=ExecutionLimits(timeout_seconds=0.12),
    )
    assert isinstance(outcome, ExecutionSuspension)
    remaining = store.peek(outcome.resume_token).remaining_timeout_seconds
    assert remaining is not None
    assert 0 < remaining < 0.12
    await asyncio.sleep(0.15)

    result = await runtime.resume(
        resume_token=outcome.resume_token,
        decision=_decision(outcome),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.COMPLETED


async def test_timeout_continues_from_remaining_duration_after_resume() -> None:
    provider = SequencedProvider((_tool_response(_call()),))
    store = FakeCheckpointStore()
    tool = FakeTool(
        tool_definition(name="sensitive", approval_mode=ToolApprovalMode.REQUIRED),
        wait_event=asyncio.Event(),
    )
    runtime, _, _ = _runtime(provider, tool, store=store)
    outcome = await runtime.run(
        agent=_agent("sensitive"),
        input_data=AgentInput(message="Execute."),
        context=AgentContext(execution_id="execution-1"),
        limits=ExecutionLimits(timeout_seconds=0.05),
    )
    assert isinstance(outcome, ExecutionSuspension)

    result = await runtime.resume(
        resume_token=outcome.resume_token,
        decision=_decision(outcome),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.TIMED_OUT
    assert tool.call_count == 1


async def test_budget_is_preserved_and_enforced_after_resume() -> None:
    provider = SequencedProvider(
        (
            _tool_response(_call(), estimated_cost=Decimal("0.40")),
            _final_response(estimated_cost=Decimal("0.20")),
        )
    )
    store = FakeCheckpointStore()
    tool = FakeTool(
        tool_definition(name="sensitive", approval_mode=ToolApprovalMode.REQUIRED)
    )
    runtime, _, _ = _runtime(provider, tool, store=store)
    outcome = await runtime.run(
        agent=_agent("sensitive"),
        input_data=AgentInput(message="Execute."),
        context=AgentContext(execution_id="execution-1"),
        budget=ExecutionBudget(
            max_estimated_cost=Decimal("0.50"),
            currency="USD",
        ),
    )
    assert isinstance(outcome, ExecutionSuspension)
    checkpoint = store.peek(outcome.resume_token)
    assert checkpoint.usage.estimated_cost == Decimal("0.40")
    assert checkpoint.budget.max_estimated_cost == Decimal("0.50")

    result = await runtime.resume(
        resume_token=outcome.resume_token,
        decision=_decision(outcome),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.BUDGET_EXCEEDED
    assert result.usage.estimated_cost == Decimal("0.60")


async def test_same_token_can_be_consumed_by_only_one_concurrent_resume() -> None:
    provider = SequencedProvider((_tool_response(_call()), _final_response()))
    store = FakeCheckpointStore()
    tool = FakeTool(
        tool_definition(name="sensitive", approval_mode=ToolApprovalMode.REQUIRED)
    )
    runtime, _, _ = _runtime(provider, tool, store=store)
    outcome = await _start(runtime, _agent("sensitive"))
    assert isinstance(outcome, ExecutionSuspension)
    decision = _decision(outcome)

    results = await asyncio.gather(
        runtime.resume(resume_token=outcome.resume_token, decision=decision),
        runtime.resume(resume_token=outcome.resume_token, decision=decision),
        return_exceptions=True,
    )

    assert sum(isinstance(item, AgentResult) for item in results) == 1
    assert sum(isinstance(item, CheckpointNotFoundError) for item in results) == 1
    assert tool.call_count == 1
