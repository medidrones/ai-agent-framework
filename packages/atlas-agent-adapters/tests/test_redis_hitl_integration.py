from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from atlas_agents import (
    AgentContext,
    AgentDefinition,
    AgentInput,
    AgentResult,
    AgentRuntime,
    ApprovalDecision,
    ApprovalDecisionMismatchError,
    ApprovalDecisionType,
    ApprovalRequest,
    CheckpointNotFoundError,
    DefaultApprovalDecisionValidator,
    ExecutionIdentity,
    ExecutionStatus,
    ExecutionSuspension,
    FinishReason,
    ModelCapability,
    ModelDescriptor,
    ModelExecutionContext,
    ModelProvider,
    ModelProviderRegistry,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ModelUsage,
    TextContent,
    Tool,
    ToolApprovalMode,
    ToolCall,
    ToolDefinition,
    ToolExecutionContext,
    ToolExecutor,
    ToolOutput,
    ToolRegistry,
)
from atlas_agents.adapters.checkpoints.redis import RedisCheckpointStore
from atlas_agents.adapters.checkpoints.redis.store import RedisCheckpointClient

REDIS_URL = os.getenv("ATLAS_TEST_REDIS_URL")
pytestmark = pytest.mark.skipif(
    REDIS_URL is None,
    reason="ATLAS_TEST_REDIS_URL não configurada para o Redis real.",
)


class _Provider(ModelProvider):
    def __init__(self, *, completed_calls: int = 0) -> None:
        self.calls = completed_calls

    @property
    def provider_name(self) -> str:
        return "ds010-redis"

    async def list_models(self) -> tuple[ModelDescriptor, ...]:
        return (
            ModelDescriptor(
                provider=self.provider_name,
                model="model",
                capabilities=frozenset(
                    {ModelCapability.TEXT_GENERATION, ModelCapability.TOOL_CALLING}
                ),
            ),
        )

    async def generate(
        self, request: ModelRequest, context: ModelExecutionContext
    ) -> ModelResponse:
        del request, context
        self.calls += 1
        if self.calls == 1:
            return ModelResponse(
                model="model",
                tool_calls=(
                    ToolCall(
                        tool_call_id="call-ds010",
                        name="sensitive",
                        arguments={"customer_id": "123"},
                    ),
                ),
                finish_reason=FinishReason.TOOL_CALL,
                usage=ModelUsage(input_tokens=2, output_tokens=1, total_tokens=3),
            )
        return ModelResponse(
            model="model",
            content=(TextContent(text="Operação concluída."),),
            finish_reason=FinishReason.STOP,
            usage=ModelUsage(input_tokens=2, output_tokens=1, total_tokens=3),
        )

    def stream(
        self, request: ModelRequest, context: ModelExecutionContext
    ) -> AsyncIterator[ModelStreamEvent]:
        del request, context
        raise AssertionError("O teste DS-010 usa execução não incremental.")


class _Tool(Tool):
    def __init__(self) -> None:
        self.call_count = 0

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="sensitive",
            description="Atualiza um cliente.",
            parameters={
                "type": "object",
                "properties": {"customer_id": {"type": "string"}},
                "required": ["customer_id"],
                "additionalProperties": False,
            },
            approval_mode=ToolApprovalMode.REQUIRED,
        )

    async def execute(
        self, arguments: dict[str, object], context: ToolExecutionContext
    ) -> ToolOutput:
        del arguments, context
        self.call_count += 1
        return ToolOutput(content={"updated": True})


class _IdentityValidator(DefaultApprovalDecisionValidator):
    def validate(self, *, request: ApprovalRequest, decision: ApprovalDecision) -> None:
        super().validate(request=request, decision=decision)
        if decision.decided_by is None or decision.decided_by.subject != "approver":
            raise ApprovalDecisionMismatchError(
                "A identidade não pode decidir esta solicitação de aprovação."
            )


@pytest.fixture
async def redis_client() -> AsyncIterator[Redis]:
    assert REDIS_URL is not None
    client = Redis.from_url(REDIS_URL, decode_responses=False)
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


def runtime(
    client: Redis,
    *,
    namespace: str,
    completed_provider_calls: int = 0,
    validator: _IdentityValidator | None = None,
) -> tuple[AgentRuntime, _Tool]:
    provider = _Provider(completed_calls=completed_provider_calls)
    models = ModelProviderRegistry()
    models.register(provider)
    tool = _Tool()
    tools = ToolRegistry()
    tools.register(tool)
    checkpoint_store = RedisCheckpointStore(
        cast(RedisCheckpointClient, client),
        namespace=namespace,
        token_hmac_key=b"hitl-hmac-key-material-at-least-32",
    )
    return (
        AgentRuntime(
            model_registry=models,
            tool_registry=tools,
            tool_executor=ToolExecutor(registry=tools),
            checkpoint_store=checkpoint_store,
            approval_decision_validator=validator,
        ),
        tool,
    )


async def suspend(value: AgentRuntime, execution_id: str) -> ExecutionSuspension:
    outcome = await value.run(
        agent=AgentDefinition(
            agent_id="assistant",
            name="Assistente",
            instructions="Execute a operação aprovada.",
            tool_names=("sensitive",),
        ),
        input_data=AgentInput(message="Atualize o cliente."),
        context=AgentContext(
            execution_id=execution_id,
            identity=ExecutionIdentity(subject="requester"),
        ),
    )
    assert isinstance(outcome, ExecutionSuspension)
    return outcome


def decision(
    outcome: ExecutionSuspension,
    *,
    identity: str = "approver",
    kind: ApprovalDecisionType = ApprovalDecisionType.APPROVE,
) -> ApprovalDecision:
    return ApprovalDecision(
        approval_request_id=outcome.approval_request.approval_request_id,
        decision=kind,
        decided_at=datetime.now(UTC),
        decided_by=ExecutionIdentity(subject=identity),
    )


async def test_hitl_resume_after_runtime_restart(redis_client: Redis) -> None:
    namespace = f"hitl-restart:{uuid4().hex}"
    first_runtime, first_tool = runtime(redis_client, namespace=namespace)
    suspension = await suspend(first_runtime, "redis-hitl-restart")
    assert first_tool.call_count == 0

    restarted_runtime, restarted_tool = runtime(
        redis_client,
        namespace=namespace,
        completed_provider_calls=1,
    )
    result = await restarted_runtime.resume(
        resume_token=suspension.resume_token,
        decision=decision(suspension),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.COMPLETED
    assert restarted_tool.call_count == 1
    with pytest.raises(CheckpointNotFoundError):
        await restarted_runtime.resume(
            resume_token=suspension.resume_token,
            decision=decision(suspension),
        )


async def test_invalid_identity_does_not_consume_or_execute_tool(
    redis_client: Redis,
) -> None:
    namespace = f"hitl-identity:{uuid4().hex}"
    agent_runtime, tool = runtime(
        redis_client,
        namespace=namespace,
        validator=_IdentityValidator(),
    )
    suspension = await suspend(agent_runtime, "redis-hitl-identity")

    with pytest.raises(ApprovalDecisionMismatchError):
        await agent_runtime.resume(
            resume_token=suspension.resume_token,
            decision=decision(suspension, identity="intruder"),
        )
    assert tool.call_count == 0

    result = await agent_runtime.resume(
        resume_token=suspension.resume_token,
        decision=decision(suspension),
    )
    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.COMPLETED
    assert tool.call_count == 1


async def test_rejection_consumes_once_without_tool_execution(
    redis_client: Redis,
) -> None:
    namespace = f"hitl-rejection:{uuid4().hex}"
    agent_runtime, tool = runtime(redis_client, namespace=namespace)
    suspension = await suspend(agent_runtime, "redis-hitl-rejection")

    result = await agent_runtime.resume(
        resume_token=suspension.resume_token,
        decision=decision(suspension, kind=ApprovalDecisionType.REJECT),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.REJECTED
    assert tool.call_count == 0
    with pytest.raises(CheckpointNotFoundError):
        await agent_runtime.resume(
            resume_token=suspension.resume_token,
            decision=decision(suspension),
        )


async def test_one_hundred_concurrent_approved_resumes_execute_tool_once(
    redis_client: Redis,
) -> None:
    namespace = f"hitl-contention:{uuid4().hex}"
    agent_runtime, tool = runtime(redis_client, namespace=namespace)
    suspension = await suspend(agent_runtime, "redis-hitl-contention")
    approved = decision(suspension)

    outcomes = await asyncio.gather(
        *(
            agent_runtime.resume(
                resume_token=suspension.resume_token,
                decision=approved,
            )
            for _ in range(100)
        ),
        return_exceptions=True,
    )

    assert sum(isinstance(item, AgentResult) for item in outcomes) == 1
    assert sum(isinstance(item, CheckpointNotFoundError) for item in outcomes) == 99
    assert tool.call_count == 1
