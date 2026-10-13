"""Real PostgreSQL and Redis integration tests for DS-014."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

import pytest
from atlas_kubernetes_recovery.durable_hitl import (
    ApprovalConflictError,
    ApprovalPersistenceError,
    ApprovalSubmission,
    DurableApprovalService,
    DurableApprovalState,
    PostgreSQLDurableApprovalRepository,
    ResumeOutcome,
    TrustedApprovalPrincipal,
)
from atlas_kubernetes_recovery.runtime_support import build_runtime
from psycopg_pool import AsyncConnectionPool
from redis.asyncio import Redis

from atlas_agents import (
    AgentContext,
    AgentDefinition,
    AgentInput,
    AgentResult,
    ApprovalDecisionType,
    CheckpointNotFoundError,
    ExecutionIdentity,
    ExecutionSuspension,
    ResumeToken,
)
from atlas_agents.adapters.checkpoints.postgresql import (
    PostgreSQLCheckpointMigrator,
    PostgreSQLCheckpointStore,
)
from atlas_agents.adapters.checkpoints.redis import RedisCheckpointStore

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

POSTGRES_DSN = os.getenv("ATLAS_TEST_POSTGRES_DSN")
REDIS_URL = os.getenv("ATLAS_TEST_REDIS_URL")
_KEY = b"h" * 32

pytestmark = pytest.mark.skipif(
    POSTGRES_DSN is None,
    reason="ATLAS_TEST_POSTGRES_DSN não configurada para a DS-014.",
)


@pytest.fixture
async def approval_repository() -> AsyncIterator[PostgreSQLDurableApprovalRepository]:
    assert POSTGRES_DSN is not None
    pool = AsyncConnectionPool[Any](POSTGRES_DSN, min_size=1, max_size=24, open=False)
    await pool.open(wait=True)
    repository = PostgreSQLDurableApprovalRepository(pool)
    await repository.migrate()
    async with pool.connection() as connection:
        await connection.execute(
            "TRUNCATE atlas_agent.hitl_audit_events, "
            "atlas_agent.hitl_approvals RESTART IDENTITY"
        )
    try:
        yield repository
    finally:
        await pool.close()


def principal(subject: str = "human-a") -> TrustedApprovalPrincipal:
    return TrustedApprovalPrincipal(
        subject=subject,
        tenant_id="tenant-ds014",
        permissions=frozenset({"atlas:hitl:decide"}),
        tool_names=frozenset({"record_certification_effect"}),
    )


def submission(
    *,
    approval_request_id: str,
    execution_id: str,
    tool_call_id: str,
    decision_id: str = "decision-a",
    decision: ApprovalDecisionType = ApprovalDecisionType.APPROVE,
    actor: TrustedApprovalPrincipal | None = None,
) -> ApprovalSubmission:
    return ApprovalSubmission(
        decision_id=decision_id,
        approval_request_id=approval_request_id,
        execution_id=execution_id,
        tenant_id="tenant-ds014",
        tool_call_id=tool_call_id,
        tool_name="record_certification_effect",
        decision=decision,
        principal=actor or principal(),
        decided_at=datetime.now(UTC),
    )


async def register(
    service: DurableApprovalService,
    *,
    approval_request_id: str = "approval-a",
    execution_id: str = "execution-a",
    tool_call_id: str = "call-a",
    token: str = "opaque-token-a",  # noqa: S107
    backend: str = "postgresql",
) -> None:
    now = datetime.now(UTC)
    await service.register(
        approval_request_id=approval_request_id,
        execution_id=execution_id,
        tenant_id="tenant-ds014",
        agent_id="agent-ds014",
        tool_call_id=tool_call_id,
        tool_name="record_certification_effect",
        backend=backend,
        resume_token=token,
        requested_at=now,
        expires_at=now + timedelta(hours=1),
    )


async def test_postgresql_persists_decision_audit_and_resume_across_pool_restart(
    approval_repository: PostgreSQLDurableApprovalRepository,
) -> None:
    service = DurableApprovalService(approval_repository, token_hmac_key=_KEY)
    await register(service)
    command = submission(
        approval_request_id="approval-a",
        execution_id="execution-a",
        tool_call_id="call-a",
    )
    decision = await service.authorize(
        resume_token="opaque-token-a",  # noqa: S106
        submission=command,
    )
    assert decision.decision is ApprovalDecisionType.APPROVE
    resumed = await service.record_resume(
        approval_request_id="approval-a",
        outcome=ResumeOutcome.COMPLETED,
    )
    assert resumed.state is DurableApprovalState.RESUMED
    assert [
        event.event_type
        for event in await approval_repository.audit_events("approval-a")
    ] == ["approval.requested", "approval.decided", "approval.resumed"]


async def test_postgresql_linearizes_one_of_one_hundred_conflicting_decisions(
    approval_repository: PostgreSQLDurableApprovalRepository,
) -> None:
    service = DurableApprovalService(approval_repository, token_hmac_key=_KEY)
    await register(service)

    async def attempt(index: int) -> str:
        command = submission(
            approval_request_id="approval-a",
            execution_id="execution-a",
            tool_call_id="call-a",
            decision_id=f"decision-{index}",
            decision=(
                ApprovalDecisionType.APPROVE
                if index % 2 == 0
                else ApprovalDecisionType.REJECT
            ),
        )
        try:
            await service.authorize(
                resume_token="opaque-token-a",  # noqa: S106
                submission=command,
            )
            return "winner"
        except ApprovalConflictError:
            return "conflict"

    results = await asyncio.gather(*(attempt(index) for index in range(100)))
    assert results.count("winner") == 1
    assert results.count("conflict") == 99


async def test_audit_failure_rolls_back_the_decision(
    approval_repository: PostgreSQLDurableApprovalRepository,
) -> None:
    service = DurableApprovalService(approval_repository, token_hmac_key=_KEY)
    await register(service)
    pool = approval_repository._pool
    async with pool.connection() as connection:
        await connection.execute(
            """CREATE OR REPLACE FUNCTION atlas_agent.reject_ds014_audit()
               RETURNS trigger LANGUAGE plpgsql AS $$
               BEGIN RAISE EXCEPTION 'forced audit failure'; END; $$"""
        )
        await connection.execute(
            """CREATE TRIGGER reject_ds014_audit
               BEFORE INSERT ON atlas_agent.hitl_audit_events
               FOR EACH ROW EXECUTE FUNCTION atlas_agent.reject_ds014_audit()"""
        )
    try:
        with pytest.raises(ApprovalPersistenceError):
            await service.authorize(
                resume_token="opaque-token-a",  # noqa: S106
                submission=submission(
                    approval_request_id="approval-a",
                    execution_id="execution-a",
                    tool_call_id="call-a",
                ),
            )
        record = await approval_repository.get("approval-a")
        assert record is not None
        assert record.state is DurableApprovalState.PENDING
    finally:
        async with pool.connection() as connection:
            await connection.execute(
                "DROP TRIGGER IF EXISTS reject_ds014_audit "
                "ON atlas_agent.hitl_audit_events"
            )
            await connection.execute(
                "DROP FUNCTION IF EXISTS atlas_agent.reject_ds014_audit()"
            )


@pytest.mark.parametrize("backend", ["postgresql", "redis"])
@pytest.mark.parametrize(
    "decision_type",
    [ApprovalDecisionType.APPROVE, ApprovalDecisionType.REJECT],
)
async def test_real_runtime_durable_hitl_flow(
    approval_repository: PostgreSQLDurableApprovalRepository,
    backend: str,
    decision_type: ApprovalDecisionType,
) -> None:
    if REDIS_URL is None:
        pytest.skip("ATLAS_TEST_REDIS_URL não configurada para a DS-014.")
    assert POSTGRES_DSN is not None
    pool = approval_repository._pool
    await PostgreSQLCheckpointMigrator(pool).migrate()
    redis = Redis.from_url(REDIS_URL, decode_responses=False)
    await redis.flushdb()
    postgresql_store = PostgreSQLCheckpointStore(pool, token_hmac_key=_KEY)
    redis_store = RedisCheckpointStore(
        cast(Any, redis),
        namespace="atlas:ds014",
        token_hmac_key=_KEY,
    )
    store = postgresql_store if backend == "postgresql" else redis_store
    execution_id = f"ds014-{backend}-{decision_type.value}-{uuid4().hex}"
    runtime = build_runtime(
        checkpoint_store=store,
        redis_client=redis,
        request_tool=True,
    )
    try:
        suspended = await runtime.run(
            agent=AgentDefinition(
                agent_id="agent-ds014",
                name="Agente DS-014",
                instructions="Aguarde aprovação humana.",
                tool_names=("record_certification_effect",),
            ),
            input_data=AgentInput(message="Teste HITL durável."),
            context=AgentContext(
                execution_id=execution_id,
                tenant_id="tenant-ds014",
                identity=ExecutionIdentity(subject="requester-ds014"),
            ),
        )
        assert isinstance(suspended, ExecutionSuspension)
        request = suspended.approval_request
        service = DurableApprovalService(approval_repository, token_hmac_key=_KEY)
        await service.register(
            approval_request_id=request.approval_request_id,
            execution_id=execution_id,
            tenant_id="tenant-ds014",
            agent_id=request.agent_id,
            tool_call_id=request.subject.tool_call_id,
            tool_name=request.subject.tool_name,
            backend=backend,
            resume_token=suspended.resume_token.value,
            requested_at=request.requested_at,
            expires_at=request.requested_at + timedelta(hours=1),
        )
        command = submission(
            approval_request_id=request.approval_request_id,
            execution_id=execution_id,
            tool_call_id=request.subject.tool_call_id,
            decision=decision_type,
        )
        decision = await service.authorize(
            resume_token=suspended.resume_token.value,
            submission=command,
        )
        result = await runtime.resume(
            resume_token=suspended.resume_token,
            decision=decision,
        )
        assert isinstance(result, AgentResult)
        outcome = (
            ResumeOutcome.COMPLETED
            if decision_type is ApprovalDecisionType.APPROVE
            else ResumeOutcome.REJECTED
        )
        await service.record_resume(
            approval_request_id=request.approval_request_id,
            outcome=outcome,
        )
        with pytest.raises(CheckpointNotFoundError):
            await runtime.resume(
                resume_token=ResumeToken(value=suspended.resume_token.value),
                decision=decision,
            )
        effect_count = await redis.get(f"atlas:ds013:effect-count:{execution_id}")
        assert effect_count == (
            b"1" if decision_type is ApprovalDecisionType.APPROVE else None
        )
    finally:
        await redis.aclose()
