from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
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
    ApprovalDecisionType,
    CheckpointNotFoundError,
    CheckpointSaveError,
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


def pool() -> AsyncConnectionPool[Any]:
    assert DSN is not None
    return AsyncConnectionPool(DSN, min_size=1, max_size=12, open=False)


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


async def test_migration_is_idempotent_and_records_checksum(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    assert await PostgreSQLCheckpointMigrator(postgres_pool).migrate() == ()
    async with postgres_pool.connection() as connection:
        cursor = await connection.execute(
            """
            SELECT version, length(checksum)
            FROM atlas_agent.schema_migrations
            WHERE component = 'postgresql_checkpoint_store'
            """
        )
        row = await cursor.fetchone()
    assert row == (1, 64)


async def test_save_consume_and_replay_do_not_store_plain_token(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    token = ResumeToken(value="DS002-PLAIN-TOKEN-MUST-NOT-BE-STORED")
    expected = checkpoint()
    store = PostgreSQLCheckpointStore(
        postgres_pool,
        token_hmac_key=b"integration-key-material-value!!",
    )

    await store.save(resume_token=token, checkpoint=expected)
    async with postgres_pool.connection() as connection:
        cursor = await connection.execute(
            "SELECT token_digest, payload::text FROM atlas_agent.checkpoints"
        )
        digest, payload = await cursor.fetchone() or (b"", "")
    assert token.value.encode() not in bytes(digest)
    assert token.value not in payload
    assert await store.consume(token) == expected
    with pytest.raises(CheckpointNotFoundError):
        await store.consume(token)


async def test_save_is_create_only(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    token = ResumeToken(value="duplicate-token")
    store = PostgreSQLCheckpointStore(postgres_pool)
    await store.save(resume_token=token, checkpoint=checkpoint())

    with pytest.raises(CheckpointSaveError):
        await store.save(resume_token=token, checkpoint=checkpoint())


async def test_concurrent_consumers_have_exactly_one_winner(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    token = ResumeToken(value="concurrent-token")
    store = PostgreSQLCheckpointStore(postgres_pool)
    await store.save(resume_token=token, checkpoint=checkpoint())

    outcomes = await asyncio.gather(
        *(store.consume(token) for _ in range(12)),
        return_exceptions=True,
    )

    assert sum(isinstance(item, ExecutionCheckpoint) for item in outcomes) == 1
    assert sum(isinstance(item, CheckpointNotFoundError) for item in outcomes) == 11


async def test_expired_checkpoint_is_rejected_and_purged(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    token = ResumeToken(value="expired-token")
    store = PostgreSQLCheckpointStore(postgres_pool)
    await store.save(
        resume_token=token,
        checkpoint=checkpoint(expires_at=datetime.now(UTC) - timedelta(seconds=1)),
    )

    with pytest.raises(CheckpointNotFoundError):
        await store.consume(token)
    assert await store.purge_expired() == 1
    assert await store.purge_expired() == 0


async def test_corrupt_payload_is_consumed_but_rejected(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    token = ResumeToken(value="corrupt-token")
    store = PostgreSQLCheckpointStore(postgres_pool)
    await store.save(resume_token=token, checkpoint=checkpoint())
    async with postgres_pool.connection() as connection:
        await connection.execute(
            "UPDATE atlas_agent.checkpoints SET payload = %s",
            (Jsonb({"checkpoint_version": 1}),),
        )

    with pytest.raises(InvalidCheckpointError):
        await store.consume(token)
    with pytest.raises(CheckpointNotFoundError):
        await store.consume(token)


async def test_checkpoint_survives_application_pool_restart() -> None:
    token = ResumeToken(value="restart-token")
    expected = checkpoint()
    first = pool()
    await first.open(wait=True)
    await PostgreSQLCheckpointMigrator(first).migrate()
    async with first.connection() as connection:
        await connection.execute("TRUNCATE atlas_agent.checkpoints")
    await PostgreSQLCheckpointStore(first).save(
        resume_token=token,
        checkpoint=expected,
    )
    await first.close()

    second = pool()
    await second.open(wait=True)
    try:
        assert await PostgreSQLCheckpointStore(second).consume(token) == expected
    finally:
        await second.close()


async def test_cancelled_consume_rolls_back_without_losing_checkpoint(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    token = ResumeToken(value="cancelled-consume-token")
    expected = checkpoint()
    store = PostgreSQLCheckpointStore(postgres_pool)
    await store.save(resume_token=token, checkpoint=expected)

    blocker = await postgres_pool.getconn()
    try:
        await blocker.execute("BEGIN")
        await blocker.execute(
            "LOCK TABLE atlas_agent.checkpoints IN ACCESS EXCLUSIVE MODE"
        )
        consume_task = asyncio.create_task(store.consume(token))
        await asyncio.sleep(0.1)
        consume_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await consume_task
    finally:
        await blocker.rollback()
        await postgres_pool.putconn(blocker)

    assert await store.consume(token) == expected


async def test_database_failures_are_wrapped_without_leaking_credentials() -> None:
    token = ResumeToken(value="secret-resume-token")
    closed_pool = pool()
    store = PostgreSQLCheckpointStore(closed_pool)

    with pytest.raises(PostgreSQLCheckpointStoreError) as captured:
        await store.consume(token)

    message = str(captured.value)
    assert token.value not in message
    assert "atlas_test" not in message


class _Provider(ModelProvider):
    def __init__(self) -> None:
        self.calls = 0

    @property
    def provider_name(self) -> str:
        return "postgresql-integration"

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
                        tool_call_id="call-postgresql",
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
        raise AssertionError("O teste HITL não usa streaming.")


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


async def test_runtime_hitl_resumes_once_with_postgresql(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    provider = _Provider()
    models = ModelProviderRegistry()
    models.register(provider)
    tool = _Tool()
    tools = ToolRegistry()
    tools.register(tool)
    store = PostgreSQLCheckpointStore(postgres_pool)
    runtime = AgentRuntime(
        model_registry=models,
        tool_registry=tools,
        tool_executor=ToolExecutor(registry=tools),
        checkpoint_store=store,
    )
    outcome = await runtime.run(
        agent=AgentDefinition(
            agent_id="assistant",
            name="Assistente",
            instructions="Execute a operação aprovada.",
            tool_names=("sensitive",),
        ),
        input_data=AgentInput(message="Atualize o cliente."),
        context=AgentContext(
            execution_id="execution-postgresql",
            identity=ExecutionIdentity(subject="user"),
        ),
    )
    assert isinstance(outcome, ExecutionSuspension)
    decision = ApprovalDecision(
        approval_request_id=outcome.approval_request.approval_request_id,
        decision=ApprovalDecisionType.APPROVE,
        decided_at=datetime.now(UTC),
    )

    resumed, replay = await asyncio.gather(
        runtime.resume(resume_token=outcome.resume_token, decision=decision),
        runtime.resume(resume_token=outcome.resume_token, decision=decision),
        return_exceptions=True,
    )

    results = (resumed, replay)
    assert sum(isinstance(item, AgentResult) for item in results) == 1
    assert sum(isinstance(item, CheckpointNotFoundError) for item in results) == 1
    completed = next(item for item in results if isinstance(item, AgentResult))
    assert completed.status is ExecutionStatus.COMPLETED
    assert tool.call_count == 1
