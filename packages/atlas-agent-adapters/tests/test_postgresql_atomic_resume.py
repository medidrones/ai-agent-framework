from __future__ import annotations

import asyncio
import json
import multiprocessing
import os
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from multiprocessing.queues import Queue
from multiprocessing.synchronize import Barrier
from pathlib import Path
from time import perf_counter
from typing import Any

import pytest
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

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
    ExecutionCheckpoint,
    ExecutionIdentity,
    ExecutionStatus,
    ExecutionSuspension,
    FinishReason,
    InvalidCheckpointError,
    ModelCapability,
    ModelDescriptor,
    ModelExecutionContext,
    ModelProvider,
    ModelProviderRegistry,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ModelUsage,
    ResumeToken,
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
from atlas_agents.adapters.checkpoints.postgresql import (
    PostgreSQLCheckpointMigrator,
    PostgreSQLCheckpointStore,
    PostgreSQLCheckpointStoreError,
)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

DSN = os.getenv("ATLAS_TEST_POSTGRES_DSN")
pytestmark = pytest.mark.skipif(
    DSN is None,
    reason="ATLAS_TEST_POSTGRES_DSN não configurada para o PostgreSQL real.",
)

ROOT = Path(__file__).parents[2]
FIXTURE = (
    ROOT
    / "atlas-agent-core"
    / "tests"
    / "fixtures"
    / "checkpoints"
    / "execution-checkpoint-v1.json"
)


def checkpoint(*, expires_at: datetime | None = None) -> ExecutionCheckpoint:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["pending_approval"]["expires_at"] = (
        None if expires_at is None else expires_at.isoformat()
    )
    return ExecutionCheckpoint.model_validate(payload)


def pool(*, max_size: int = 16) -> AsyncConnectionPool[Any]:
    assert DSN is not None
    return AsyncConnectionPool(DSN, min_size=1, max_size=max_size, open=False)


def allow_checkpoint(checkpoint: ExecutionCheckpoint) -> None:
    del checkpoint


@pytest.fixture
async def postgres_pool() -> AsyncIterator[AsyncConnectionPool[Any]]:
    value = pool()
    await value.open(wait=True)
    await PostgreSQLCheckpointMigrator(value).migrate()
    async with value.connection() as connection:
        await connection.execute("TRUNCATE atlas_agent.checkpoints")
    try:
        yield value
    finally:
        async with value.connection() as connection:
            await connection.execute("TRUNCATE atlas_agent.checkpoints")
        await value.close()


async def _wait_for_lock_waiter(value: AsyncConnectionPool[Any]) -> None:
    for _ in range(100):
        async with value.connection() as connection:
            cursor = await connection.execute(
                """
                SELECT count(*)
                FROM pg_stat_activity
                WHERE pid <> pg_backend_pid()
                  AND datname = current_database()
                  AND wait_event_type = 'Lock'
                  AND query ILIKE '%atlas_agent.checkpoints%'
                """
            )
            row = await cursor.fetchone()
        if row is not None and int(row[0]) >= 1:
            return
        await asyncio.sleep(0.02)
    raise AssertionError("O consumo não aguardou o lock PostgreSQL esperado.")


async def _process_consume(dsn: str, token_value: str) -> str:
    value = AsyncConnectionPool(dsn, min_size=1, max_size=1, open=False)
    await value.open(wait=True)
    try:
        await PostgreSQLCheckpointStore(value).consume_authorized(
            resume_token=ResumeToken(value=token_value),
            authorize=allow_checkpoint,
        )
        return "success"
    finally:
        await value.close()


def _process_consumer(
    dsn: str,
    token_value: str,
    barrier: Barrier,
    result_queue: Queue[Any],
) -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        barrier.wait(timeout=15)
        result_queue.put(asyncio.run(_process_consume(dsn, token_value)))
    except CheckpointNotFoundError:
        result_queue.put("rejected")
    except Exception as error:
        result_queue.put(type(error).__name__)


class _Provider(ModelProvider):
    def __init__(self) -> None:
        self.calls = 0

    @property
    def provider_name(self) -> str:
        return "ds004-postgresql"

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
        self,
        request: ModelRequest,
        context: ModelExecutionContext,
    ) -> ModelResponse:
        del request, context
        self.calls += 1
        if self.calls == 1:
            return ModelResponse(
                model="model",
                tool_calls=(
                    ToolCall(
                        tool_call_id="call-ds004",
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
        self,
        request: ModelRequest,
        context: ModelExecutionContext,
    ) -> AsyncIterator[ModelStreamEvent]:
        del request, context
        raise AssertionError("Os testes DS-004 usam execução não incremental.")


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
        self,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolOutput:
        del arguments, context
        self.call_count += 1
        return ToolOutput(content={"updated": True})


class _IdentityValidator(DefaultApprovalDecisionValidator):
    def validate(
        self,
        *,
        request: ApprovalRequest,
        decision: ApprovalDecision,
    ) -> None:
        super().validate(request=request, decision=decision)
        if decision.decided_by is None or decision.decided_by.subject != "approver":
            raise ApprovalDecisionMismatchError(
                "A identidade não pode decidir esta solicitação de aprovação."
            )


def runtime(
    value: AsyncConnectionPool[Any],
    *,
    validator: _IdentityValidator | None = None,
) -> tuple[AgentRuntime, _Tool]:
    provider = _Provider()
    models = ModelProviderRegistry()
    models.register(provider)
    tool = _Tool()
    tools = ToolRegistry()
    tools.register(tool)
    return (
        AgentRuntime(
            model_registry=models,
            tool_registry=tools,
            tool_executor=ToolExecutor(registry=tools),
            checkpoint_store=PostgreSQLCheckpointStore(value),
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


async def test_ten_concurrent_consumers_have_one_winner(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    token = ResumeToken(value="ten-consumers-token")
    store = PostgreSQLCheckpointStore(postgres_pool)
    await store.save(resume_token=token, checkpoint=checkpoint())

    outcomes = await asyncio.gather(
        *(
            store.consume_authorized(
                resume_token=token,
                authorize=allow_checkpoint,
            )
            for _ in range(10)
        ),
        return_exceptions=True,
    )

    assert sum(isinstance(item, ExecutionCheckpoint) for item in outcomes) == 1
    assert sum(isinstance(item, CheckpointNotFoundError) for item in outcomes) == 9


async def test_authorization_failure_rolls_back_consumption(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    token = ResumeToken(value="authorization-rollback-token")
    expected = checkpoint()
    store = PostgreSQLCheckpointStore(postgres_pool)
    await store.save(resume_token=token, checkpoint=expected)

    def reject(checkpoint: ExecutionCheckpoint) -> None:
        del checkpoint
        raise ApprovalDecisionMismatchError("Decisão não autorizada.")

    with pytest.raises(ApprovalDecisionMismatchError):
        await store.consume_authorized(resume_token=token, authorize=reject)

    assert await store.consume(token) == expected


async def test_unknown_and_expired_tokens_do_not_reach_authorization(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    store = PostgreSQLCheckpointStore(postgres_pool)
    expired = ResumeToken(value="expired-authorized-token")
    await store.save(
        resume_token=expired,
        checkpoint=checkpoint(expires_at=datetime.now(UTC) - timedelta(seconds=1)),
    )
    calls = 0

    def authorize(checkpoint: ExecutionCheckpoint) -> None:
        nonlocal calls
        del checkpoint
        calls += 1

    for token in (expired, ResumeToken(value="unknown-authorized-token")):
        with pytest.raises(CheckpointNotFoundError):
            await store.consume_authorized(
                resume_token=token,
                authorize=authorize,
            )

    assert calls == 0


async def test_corrupt_payload_rolls_back_in_authorized_path(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    token = ResumeToken(value="corrupt-authorized-token")
    store = PostgreSQLCheckpointStore(postgres_pool)
    await store.save(resume_token=token, checkpoint=checkpoint())
    async with postgres_pool.connection() as connection:
        await connection.execute(
            "UPDATE atlas_agent.checkpoints SET payload = %s",
            (Jsonb({"checkpoint_version": 1}),),
        )

    with pytest.raises(InvalidCheckpointError):
        await store.consume_authorized(
            resume_token=token,
            authorize=allow_checkpoint,
        )

    async with postgres_pool.connection() as connection:
        cursor = await connection.execute(
            "SELECT count(*) FROM atlas_agent.checkpoints"
        )
        row = await cursor.fetchone()
    assert row == (1,)


async def test_cancelled_authorized_consume_rolls_back(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    token = ResumeToken(value="cancelled-authorized-token")
    expected = checkpoint()
    store = PostgreSQLCheckpointStore(postgres_pool)
    await store.save(resume_token=token, checkpoint=expected)
    blocker = await postgres_pool.getconn()
    try:
        await blocker.execute("BEGIN")
        await blocker.execute(
            "SELECT 1 FROM atlas_agent.checkpoints WHERE token_digest = %s FOR UPDATE",
            (store._token_digest(token),),
        )
        consume_task = asyncio.create_task(
            store.consume_authorized(
                resume_token=token,
                authorize=allow_checkpoint,
            )
        )
        await _wait_for_lock_waiter(postgres_pool)
        consume_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await consume_task
    finally:
        await blocker.rollback()
        await postgres_pool.putconn(blocker)

    assert await store.consume(token) == expected


async def test_consumption_survives_pool_restart() -> None:
    token = ResumeToken(value="committed-consumption-token")
    first = pool(max_size=2)
    await first.open(wait=True)
    await PostgreSQLCheckpointMigrator(first).migrate()
    async with first.connection() as connection:
        await connection.execute("TRUNCATE atlas_agent.checkpoints")
    first_store = PostgreSQLCheckpointStore(first)
    await first_store.save(resume_token=token, checkpoint=checkpoint())
    await first_store.consume_authorized(
        resume_token=token,
        authorize=allow_checkpoint,
    )
    await first.close()

    second = pool(max_size=2)
    await second.open(wait=True)
    try:
        with pytest.raises(CheckpointNotFoundError):
            await PostgreSQLCheckpointStore(second).consume(token)
    finally:
        await second.close()


async def test_identity_rejection_preserves_checkpoint_and_tool(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    agent_runtime, tool = runtime(postgres_pool, validator=_IdentityValidator())
    outcome = await suspend(agent_runtime, "identity-authorization")

    with pytest.raises(ApprovalDecisionMismatchError):
        await agent_runtime.resume(
            resume_token=outcome.resume_token,
            decision=decision(outcome, identity="intruder"),
        )

    assert tool.call_count == 0
    result = await agent_runtime.resume(
        resume_token=outcome.resume_token,
        decision=decision(outcome),
    )
    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.COMPLETED
    assert tool.call_count == 1


async def test_rejected_approval_consumes_once_without_running_tool(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    agent_runtime, tool = runtime(postgres_pool)
    outcome = await suspend(agent_runtime, "rejected-authorization")

    result = await agent_runtime.resume(
        resume_token=outcome.resume_token,
        decision=decision(outcome, kind=ApprovalDecisionType.REJECT),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.REJECTED
    assert tool.call_count == 0
    with pytest.raises(CheckpointNotFoundError):
        await agent_runtime.resume(
            resume_token=outcome.resume_token,
            decision=decision(outcome),
        )


async def test_ten_concurrent_runtime_resumes_execute_tool_once(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    agent_runtime, tool = runtime(postgres_pool)
    outcome = await suspend(agent_runtime, "ten-runtime-resumes")
    approved = decision(outcome)

    results = await asyncio.gather(
        *(
            agent_runtime.resume(
                resume_token=outcome.resume_token,
                decision=approved,
            )
            for _ in range(10)
        ),
        return_exceptions=True,
    )

    assert sum(isinstance(item, AgentResult) for item in results) == 1
    assert sum(isinstance(item, CheckpointNotFoundError) for item in results) == 9
    assert tool.call_count == 1


async def test_closed_pool_returns_safe_infrastructure_error() -> None:
    token = ResumeToken(value="secret-ds004-token")
    closed_pool = pool(max_size=2)
    store = PostgreSQLCheckpointStore(closed_pool)

    with pytest.raises(PostgreSQLCheckpointStoreError) as captured:
        await store.consume_authorized(
            resume_token=token,
            authorize=allow_checkpoint,
        )

    message = str(captured.value)
    assert token.value not in message
    assert "postgresql://" not in message


async def test_independent_processes_have_one_authorized_consumer(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    assert DSN is not None
    token = ResumeToken(value="multiprocess-authorized-token")
    store = PostgreSQLCheckpointStore(postgres_pool)
    await store.save(resume_token=token, checkpoint=checkpoint())
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(2)
    result_queue = context.Queue()
    processes = [
        context.Process(
            target=_process_consumer,
            args=(DSN, token.value, barrier, result_queue),
        )
        for _ in range(2)
    ]
    try:
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=20)
        assert all(not process.is_alive() for process in processes)
        assert all(process.exitcode == 0 for process in processes)
        outcomes = [result_queue.get(timeout=5) for _ in processes]
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
            process.close()
        result_queue.close()
        result_queue.join_thread()

    assert sorted(outcomes) == ["rejected", "success"]


async def test_atomic_consumption_performance_baseline(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    store = PostgreSQLCheckpointStore(postgres_pool)
    tokens = [ResumeToken(value=f"performance-token-{index}") for index in range(25)]
    expected = checkpoint()
    for token in tokens:
        await store.save(resume_token=token, checkpoint=expected)

    started = perf_counter()
    consumed = await asyncio.gather(
        *(
            store.consume_authorized(
                resume_token=token,
                authorize=allow_checkpoint,
            )
            for token in tokens
        )
    )
    elapsed = perf_counter() - started

    assert len(consumed) == 25
    assert elapsed < 30
