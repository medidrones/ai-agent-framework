"""End-to-end tests for HITL suspension and resume in streaming mode."""

from datetime import UTC, datetime
from typing import cast

import pytest

from atlas_agents import (
    AgentContext,
    AgentDefinition,
    AgentInput,
    AgentRuntime,
    ApprovalDecision,
    ApprovalDecisionType,
    ExecutionStatus,
    InvalidCheckpointError,
    ModelProviderRegistry,
    RuntimeEventItem,
    RuntimeResultItem,
    RuntimeStreamItem,
    RuntimeSuspensionItem,
    ToolApprovalMode,
    ToolCall,
    ToolExecutor,
    ToolRegistry,
)
from tests.approvals.fakes import FakeCheckpointStore
from tests.runtime.test_multi_turn_streaming import (
    SequencedStreamingProvider,
    _text_turn,
    _tool_turn,
)
from tests.tools.fakes import FakeTool, tool_definition


def _runtime() -> tuple[AgentRuntime, SequencedStreamingProvider, FakeTool]:
    call = ToolCall(
        tool_call_id="call-1",
        name="sensitive",
        arguments={"customer_id": "123"},
    )
    provider = SequencedStreamingProvider((_tool_turn(call), _text_turn()))
    model_registry = ModelProviderRegistry()
    model_registry.register(provider)
    tool_registry = ToolRegistry()
    tool = FakeTool(
        tool_definition(name="sensitive", approval_mode=ToolApprovalMode.REQUIRED)
    )
    tool_registry.register(tool)
    runtime = AgentRuntime(
        model_registry=model_registry,
        tool_registry=tool_registry,
        tool_executor=ToolExecutor(registry=tool_registry),
        checkpoint_store=FakeCheckpointStore(),
    )
    return runtime, provider, tool


def _agent() -> AgentDefinition:
    return AgentDefinition(
        agent_id="assistant",
        name="Assistente",
        instructions="Execute operações autorizadas.",
        tool_names=("sensitive",),
    )


def _decision(
    item: RuntimeSuspensionItem,
    decision: ApprovalDecisionType,
) -> ApprovalDecision:
    return ApprovalDecision(
        approval_request_id=(item.suspension.approval_request.approval_request_id),
        decision=decision,
        decided_at=datetime.now(UTC),
    )


async def _suspend(runtime: AgentRuntime) -> list[RuntimeStreamItem]:
    return [
        item
        async for item in runtime.stream(
            agent=_agent(),
            input_data=AgentInput(message="Execute."),
            context=AgentContext(execution_id="execution-stream-approval"),
        )
    ]


async def test_stream_suspends_without_result_and_resume_uses_only_stream() -> None:
    runtime, provider, tool = _runtime()

    initial_items = await _suspend(runtime)

    assert isinstance(initial_items[-1], RuntimeSuspensionItem)
    assert not any(isinstance(item, RuntimeResultItem) for item in initial_items)
    suspension_item = initial_items[-1]
    assert tool.call_count == 0
    resumed_items = [
        item
        async for item in runtime.resume_stream(
            resume_token=suspension_item.suspension.resume_token,
            decision=_decision(suspension_item, ApprovalDecisionType.APPROVE),
        )
    ]

    terminal = cast(RuntimeResultItem, resumed_items[-1]).result
    assert terminal.status is ExecutionStatus.COMPLETED
    assert provider.stream_calls == 2
    assert provider.generate_calls == 0
    assert tool.call_count == 1
    resumed_events = [
        item.event for item in resumed_items if isinstance(item, RuntimeEventItem)
    ]
    suspended_sequence = cast(RuntimeEventItem, initial_items[-2]).event.sequence
    assert resumed_events[0].sequence == suspended_sequence + 1
    assert [event.sequence for event in terminal.events] == list(
        range(1, len(terminal.events) + 1)
    )


async def test_stream_resume_rejection_emits_result_without_model_or_tool() -> None:
    runtime, provider, tool = _runtime()
    initial_items = await _suspend(runtime)
    suspension_item = cast(RuntimeSuspensionItem, initial_items[-1])

    resumed_items = [
        item
        async for item in runtime.resume_stream(
            resume_token=suspension_item.suspension.resume_token,
            decision=_decision(suspension_item, ApprovalDecisionType.REJECT),
        )
    ]

    terminal = cast(RuntimeResultItem, resumed_items[-1]).result
    assert terminal.status is ExecutionStatus.REJECTED
    assert terminal.error is not None
    assert terminal.error.code == "approval_rejected"
    assert provider.stream_calls == 1
    assert provider.generate_calls == 0
    assert tool.call_count == 0


async def test_stream_checkpoint_cannot_resume_through_run_transport() -> None:
    runtime, _, _ = _runtime()
    initial_items = await _suspend(runtime)
    suspension_item = cast(RuntimeSuspensionItem, initial_items[-1])

    with pytest.raises(InvalidCheckpointError):
        await runtime.resume(
            resume_token=suspension_item.suspension.resume_token,
            decision=_decision(suspension_item, ApprovalDecisionType.APPROVE),
        )
