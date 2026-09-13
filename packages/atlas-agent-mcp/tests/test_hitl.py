from __future__ import annotations

from datetime import UTC, datetime

import pytest
from mcp_test_support import InMemoryTransport
from test_tools_runtime import SequenceProvider, remote_server

from atlas_agents import (
    AgentContext,
    AgentDefinition,
    AgentInput,
    AgentResult,
    AgentRuntime,
    ApprovalContext,
    ApprovalDecision,
    ApprovalDecisionType,
    ApprovalRequired,
    ApprovalRequirement,
    ExecutionCheckpoint,
    ExecutionIdentity,
    ExecutionStatus,
    ExecutionSuspension,
    ModelProviderRegistry,
    ResumeToken,
    ToolDefinition,
    ToolExecutionRequest,
    ToolExecutor,
    ToolRegistry,
)
from atlas_agents.mcp import MCPClient, MCPToolImporter


class RequiredPolicy:
    def evaluate_tool(
        self,
        *,
        tool: ToolDefinition,
        request: ToolExecutionRequest,
        context: ApprovalContext,
    ) -> ApprovalRequirement:
        del tool, request, context
        return ApprovalRequired(
            reason="A ferramenta remota exige decisão.",
            summary="Autorizar chamada MCP?",
        )


class MemoryCheckpointStore:
    def __init__(self) -> None:
        self.values: dict[str, ExecutionCheckpoint] = {}

    async def save(
        self, *, resume_token: ResumeToken, checkpoint: ExecutionCheckpoint
    ) -> None:
        self.values[resume_token.value] = checkpoint

    async def consume(self, resume_token: ResumeToken) -> ExecutionCheckpoint:
        return self.values.pop(resume_token.value)


async def prepare_runtime(
    client: MCPClient, store: MemoryCheckpointStore
) -> AgentRuntime:
    server_tool_registry = ToolRegistry()
    await MCPToolImporter(
        client=client, registry=server_tool_registry, server_alias="remote"
    ).import_tools(include_names=frozenset({"double"}))
    model_registry = ModelProviderRegistry()
    model_registry.register(SequenceProvider())
    return AgentRuntime(
        model_registry=model_registry,
        tool_registry=server_tool_registry,
        tool_executor=ToolExecutor(registry=server_tool_registry),
        approval_policy=RequiredPolicy(),
        checkpoint_store=store,
    )


def agent() -> AgentDefinition:
    return AgentDefinition(
        agent_id="agent",
        name="Agente",
        instructions="Use a ferramenta.",
        tool_names=("remote__double",),
    )


@pytest.mark.asyncio
async def test_approval_occurs_before_network_and_approved_resume_calls_once() -> None:
    server, (remote,) = remote_server("double")
    store = MemoryCheckpointStore()
    async with MCPClient(InMemoryTransport(server)) as client:
        runtime = await prepare_runtime(client, store)
        outcome = await runtime.run(
            agent=agent(),
            input_data=AgentInput(message="Calcule."),
            context=AgentContext(execution_id="execution"),
        )
        assert isinstance(outcome, ExecutionSuspension)
        assert remote.calls == 0
        result = await runtime.resume(
            resume_token=outcome.resume_token,
            decision=ApprovalDecision(
                approval_request_id=outcome.approval_request.approval_request_id,
                decision=ApprovalDecisionType.APPROVE,
                decided_at=datetime.now(UTC),
                decided_by=ExecutionIdentity(subject="reviewer"),
            ),
        )
    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.COMPLETED
    assert remote.calls == 1


@pytest.mark.asyncio
async def test_rejected_approval_never_calls_remote_server() -> None:
    server, (remote,) = remote_server("double")
    store = MemoryCheckpointStore()
    async with MCPClient(InMemoryTransport(server)) as client:
        runtime = await prepare_runtime(client, store)
        outcome = await runtime.run(
            agent=agent(),
            input_data=AgentInput(message="Calcule."),
            context=AgentContext(execution_id="execution-rejected"),
        )
        assert isinstance(outcome, ExecutionSuspension)
        result = await runtime.resume(
            resume_token=outcome.resume_token,
            decision=ApprovalDecision(
                approval_request_id=outcome.approval_request.approval_request_id,
                decision=ApprovalDecisionType.REJECT,
                decided_at=datetime.now(UTC),
                decided_by=ExecutionIdentity(subject="reviewer"),
            ),
        )
    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.REJECTED
    assert remote.calls == 0
