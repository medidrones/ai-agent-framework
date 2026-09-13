"""Runtime integration for OpenAI multi-turn tools and HITL resumption."""

from datetime import UTC, datetime

import pytest
from conftest import FakeClient, context, provider_with, request, response, usage

from atlas_agents import (
    AgentContext,
    AgentDefinition,
    AgentInput,
    AgentResult,
    AgentRuntime,
    ApprovalDecision,
    ApprovalDecisionType,
    ExecutionCheckpoint,
    ExecutionIdentity,
    ExecutionStatus,
    ExecutionSuspension,
    ModelProviderRegistry,
    ResumeToken,
    Tool,
    ToolApprovalMode,
    ToolDefinition,
    ToolExecutionContext,
    ToolExecutor,
    ToolOutput,
    ToolRegistry,
)


class RecordingTool(Tool):
    """Return a deterministic value and record actual executions."""

    def __init__(self, *, approval: ToolApprovalMode) -> None:
        self._definition = ToolDefinition(
            name="lookup",
            description="Consulta um valor.",
            parameters={
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
                "additionalProperties": False,
            },
            approval_mode=approval,
        )
        self.calls: list[dict[str, object]] = []

    @property
    def definition(self) -> ToolDefinition:
        """Return the immutable tool definition."""
        return self._definition

    async def execute(
        self,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolOutput:
        """Record valid arguments and return a deterministic output."""
        del context
        self.calls.append(arguments)
        return ToolOutput(content={"found": arguments["value"]})


class MemoryCheckpointStore:
    """Provide atomic single-use checkpoint behavior for one test process."""

    def __init__(self) -> None:
        self.values: dict[str, ExecutionCheckpoint] = {}

    async def save(
        self,
        *,
        resume_token: ResumeToken,
        checkpoint: ExecutionCheckpoint,
    ) -> None:
        """Save a checkpoint under its opaque token."""
        self.values[resume_token.value] = checkpoint

    async def consume(self, resume_token: ResumeToken) -> ExecutionCheckpoint:
        """Consume a checkpoint exactly once."""
        return self.values.pop(resume_token.value)


def tool_response() -> dict[str, object]:
    """Create the first provider turn requesting one Atlas tool."""
    return response(
        output=[
            {
                "type": "function_call",
                "call_id": "call-1",
                "name": "lookup",
                "arguments": '{"value":"abc"}',
            }
        ],
        usage=usage(),
    )


def final_response() -> dict[str, object]:
    """Create the provider's final text turn."""
    return response(
        output=[
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "Concluído."}],
            }
        ],
        usage=usage(),
    )


def runtime_with(
    tool: RecordingTool,
    *,
    checkpoint_store: MemoryCheckpointStore | None = None,
) -> tuple[AgentRuntime, FakeClient]:
    """Compose a real runtime with the OpenAI adapter and fake SDK transport."""
    provider, client = provider_with(tool_response(), final_response())
    model_registry = ModelProviderRegistry()
    model_registry.register(provider)
    tool_registry = ToolRegistry()
    tool_registry.register(tool)
    runtime = AgentRuntime(
        model_registry=model_registry,
        tool_registry=tool_registry,
        tool_executor=ToolExecutor(registry=tool_registry),
        checkpoint_store=checkpoint_store,
    )
    return runtime, client


def agent() -> AgentDefinition:
    """Create an agent explicitly restricted to the test tool."""
    return AgentDefinition(
        agent_id="assistant",
        name="Assistente",
        instructions="Use a ferramenta e responda.",
        tool_names=("lookup",),
    )


def agent_context() -> AgentContext:
    """Create a provider-neutral execution identity."""
    return AgentContext(
        execution_id="execution-1",
        identity=ExecutionIdentity(subject="user-private"),
        metadata={"private": "context"},
    )


def assert_local_tool_history(second_payload: dict[str, object]) -> None:
    """Assert stateless tool history and privacy in the second Responses call."""
    mapped_input = second_payload["input"]
    assert isinstance(mapped_input, list)
    item_types = [item["type"] for item in mapped_input]
    assert "function_call" in item_types
    assert "function_call_output" in item_types
    function_call = next(
        item for item in mapped_input if item["type"] == "function_call"
    )
    tool_output = next(
        item for item in mapped_input if item["type"] == "function_call_output"
    )
    assert function_call["call_id"] == "call-1"
    assert tool_output["call_id"] == "call-1"
    assert "previous_response_id" not in second_payload
    assert "conversation" not in second_payload
    assert "user" not in second_payload
    assert "execution-1" not in repr(second_payload)
    assert "user-private" not in repr(second_payload)


@pytest.mark.asyncio
async def test_real_runtime_executes_multi_turn_with_local_openai_history() -> None:
    tool = RecordingTool(approval=ToolApprovalMode.NOT_REQUIRED)
    runtime, raw_client = runtime_with(tool)

    result = await runtime.run(
        agent=agent(),
        input_data=AgentInput(message="Consulte abc."),
        context=agent_context(),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.COMPLETED
    assert result.output == "Concluído."
    assert tool.calls == [{"value": "abc"}]
    calls = raw_client.responses.calls
    assert len(calls) == 2
    assert_local_tool_history(calls[1])


@pytest.mark.asyncio
async def test_hitl_resume_reconstructs_history_without_openai_conversation_state() -> (
    None
):
    tool = RecordingTool(approval=ToolApprovalMode.REQUIRED)
    store = MemoryCheckpointStore()
    runtime, raw_client = runtime_with(tool, checkpoint_store=store)

    outcome = await runtime.run(
        agent=agent(),
        input_data=AgentInput(message="Consulte abc."),
        context=agent_context(),
    )
    assert isinstance(outcome, ExecutionSuspension)
    assert tool.calls == []

    result = await runtime.resume(
        resume_token=outcome.resume_token,
        decision=ApprovalDecision(
            approval_request_id=outcome.approval_request.approval_request_id,
            decision=ApprovalDecisionType.APPROVE,
            decided_at=datetime.now(UTC),
            decided_by=ExecutionIdentity(subject="manager"),
        ),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.COMPLETED
    assert tool.calls == [{"value": "abc"}]
    calls = raw_client.responses.calls
    assert len(calls) == 2
    assert_local_tool_history(calls[1])


def test_provider_helpers_remain_provider_neutral() -> None:
    """Keep helper imports referenced so strict test discovery checks them."""
    assert context().execution_id
    assert request().model
