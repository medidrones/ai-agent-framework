from __future__ import annotations

import asyncio
import json
import os
import statistics
import sys
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from psycopg_pool import AsyncConnectionPool

from atlas_agents import (
    CheckpointNotFoundError,
    CheckpointRetentionPolicy,
    CheckpointSaveError,
    ExecutionCheckpoint,
    PurgeEligibility,
    ResumeToken,
)
from atlas_agents.adapters.checkpoints.postgresql import (
    PostgreSQLCheckpointMigrator,
    PostgreSQLCheckpointRetentionRepository,
    PostgreSQLCheckpointStore,
    PostgreSQLCheckpointStoreError,
)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

DSN = os.getenv("ATLAS_TEST_POSTGRES_DSN")
pytestmark = pytest.mark.skipif(DSN is None, reason="PostgreSQL real não configurado")
ROOT = Path(__file__).parents[2]
FIXTURE = (
    ROOT / "atlas-agent-core/tests/fixtures/checkpoints/execution-checkpoint-v1.json"
)


def policy(*, consumed_days: int = 7) -> CheckpointRetentionPolicy:
    return CheckpointRetentionPolicy(
        policy_version="ds007-v1",
        active_ttl=timedelta(hours=1),
        hitl_ttl=timedelta(hours=2),
        consumed_retention=timedelta(days=consumed_days),
        expired_retention=timedelta(days=14),
        terminal_retention=timedelta(days=30),
        recovery_retention=timedelta(days=7),
    )


def checkpoint(
    *, execution_id: str, tenant_id: str | None = None
) -> ExecutionCheckpoint:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    now = datetime.now(UTC)
    payload["execution_id"] = execution_id
    payload["context"]["execution_id"] = execution_id
    payload["context"]["tenant_id"] = tenant_id
    payload["pending_approval"]["execution_id"] = execution_id
    payload["pending_approval"]["expires_at"] = (now + timedelta(hours=1)).isoformat()
    payload["created_at"] = now.isoformat()
    payload["updated_at"] = now.isoformat()
    for event in payload["events"]:
        event["execution_id"] = execution_id
    return ExecutionCheckpoint.model_validate(payload)


@pytest.fixture
async def postgres_pool() -> AsyncIterator[AsyncConnectionPool[Any]]:
    assert DSN is not None
    value = AsyncConnectionPool(DSN, min_size=1, max_size=8, open=False)
    await value.open(wait=True)
    await PostgreSQLCheckpointMigrator(value).migrate()
    statement = """TRUNCATE atlas_agent.execution_recovery_attempts,
        atlas_agent.checkpoint_leases, atlas_agent.checkpoint_tombstones,
        atlas_agent.checkpoints"""
    async with value.connection() as connection:
        await connection.execute(statement)
    try:
        yield value
    finally:
        async with value.connection() as connection:
            await connection.execute(statement)
        await value.close()


async def test_database_clock_enforces_expiration_boundary(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    token = ResumeToken(value="ds007-boundary")
    store = PostgreSQLCheckpointStore(postgres_pool, retention_policy=policy())
    await store.save(
        resume_token=token,
        checkpoint=checkpoint(execution_id="expiration-boundary"),
    )
    async with postgres_pool.connection() as connection:
        await connection.execute(
            "UPDATE atlas_agent.checkpoints SET expires_at = clock_timestamp()"
        )
    with pytest.raises(CheckpointNotFoundError):
        await store.consume(token)


async def test_atomic_consumption_creates_payload_free_replay_tombstone(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    token = ResumeToken(value="DS007-SECRET-RESUME-TOKEN")
    store = PostgreSQLCheckpointStore(postgres_pool, retention_policy=policy())
    await store.save(
        resume_token=token,
        checkpoint=checkpoint(execution_id="consumed-tombstone", tenant_id="tenant-a"),
    )
    await store.consume(token)
    with pytest.raises(CheckpointNotFoundError):
        await store.consume(token)
    with pytest.raises(CheckpointSaveError):
        await store.save(
            resume_token=token,
            checkpoint=checkpoint(execution_id="reactivation-forbidden"),
        )
    async with postgres_pool.connection() as connection:
        cursor = await connection.execute(
            """SELECT execution_id, tenant_id, retention_policy_version,
                      retention_until > consumed_at,
                      row_to_json(tombstone)::text
               FROM atlas_agent.checkpoint_tombstones AS tombstone"""
        )
        row = await cursor.fetchone()
    assert row is not None
    assert row[:4] == ("consumed-tombstone", "tenant-a", "ds007-v1", True)
    assert "DS007-SECRET-RESUME-TOKEN" not in str(row[4])
    assert "payload" not in str(row[4])


async def test_authorization_failure_rolls_back_checkpoint_and_tombstone(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    token = ResumeToken(value="ds007-authorization-rollback")
    store = PostgreSQLCheckpointStore(postgres_pool, retention_policy=policy())
    await store.save(
        resume_token=token,
        checkpoint=checkpoint(execution_id="authorization-rollback"),
    )

    def deny(_: ExecutionCheckpoint) -> None:
        raise PermissionError("negado")

    with pytest.raises(PermissionError):
        await store.consume_authorized(resume_token=token, authorize=deny)
    async with postgres_pool.connection() as connection:
        cursor = await connection.execute(
            """SELECT (SELECT count(*) FROM atlas_agent.checkpoints),
                      (SELECT count(*) FROM atlas_agent.checkpoint_tombstones)"""
        )
        assert await cursor.fetchone() == (1, 0)


async def test_classifier_is_tenant_scoped_and_never_deletes(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    store = PostgreSQLCheckpointStore(postgres_pool, retention_policy=policy())
    for tenant in ("tenant-a", "tenant-b"):
        await store.save(
            resume_token=ResumeToken(value=f"token-{tenant}"),
            checkpoint=checkpoint(execution_id=f"execution-{tenant}", tenant_id=tenant),
        )
    async with postgres_pool.connection() as connection:
        await connection.execute(
            """UPDATE atlas_agent.checkpoints
               SET checkpoint_created_at = clock_timestamp() - interval '21 days',
                   expires_at = clock_timestamp() - interval '20 days',
                   retention_until = clock_timestamp() - interval '1 day'"""
        )
    classifications = await PostgreSQLCheckpointRetentionRepository(
        postgres_pool, policy=policy()
    ).classify(limit=10, tenant_id="tenant-a")
    assert len(classifications) == 1
    assert classifications[0].eligibility is PurgeEligibility.ELIGIBLE
    async with postgres_pool.connection() as connection:
        cursor = await connection.execute(
            "SELECT count(*) FROM atlas_agent.checkpoints"
        )
        assert (await cursor.fetchone())[0] == 2


async def test_active_lease_and_recovery_fail_closed(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    store = PostgreSQLCheckpointStore(postgres_pool, retention_policy=policy())
    await store.save(
        resume_token=ResumeToken(value="leased-retention"),
        checkpoint=checkpoint(execution_id="execution-lease"),
    )
    async with postgres_pool.connection() as connection:
        await connection.execute(
            """UPDATE atlas_agent.checkpoints
               SET checkpoint_created_at = clock_timestamp() - interval '21 days',
                   expires_at = clock_timestamp() - interval '20 days',
                   retention_until = clock_timestamp() - interval '1 day'"""
        )
        await connection.execute(
            """INSERT INTO atlas_agent.checkpoint_leases
               (checkpoint_id, owner_id, fencing_token, acquired_at, expires_at)
               VALUES ('execution-lease', 'owner', 1, clock_timestamp(),
                       clock_timestamp() + interval '1 hour')"""
        )
    repository = PostgreSQLCheckpointRetentionRepository(postgres_pool, policy=policy())
    result = await repository.classify(limit=10)
    assert result[0].eligibility is PurgeEligibility.BLOCKED_BY_LEASE
    async with postgres_pool.connection() as connection:
        await connection.execute(
            "DELETE FROM atlas_agent.checkpoint_leases WHERE checkpoint_id = %s",
            ("execution-lease",),
        )
        await connection.execute(
            """INSERT INTO atlas_agent.execution_recovery_attempts
               (attempt_id, execution_id, checkpoint_id, owner_id,
                fencing_token, attempt_number)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (uuid4(), "execution-lease", "execution-lease", "owner", 1, 1),
        )
    result = await repository.classify(limit=10)
    assert result[0].eligibility is PurgeEligibility.BLOCKED_BY_RECOVERY


async def test_ds007_policy_disables_legacy_physical_purge(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    store = PostgreSQLCheckpointStore(postgres_pool, retention_policy=policy())
    with pytest.raises(PostgreSQLCheckpointStoreError):
        await store.purge_expired()


async def test_retention_classification_performance_baseline(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    store = PostgreSQLCheckpointStore(postgres_pool, retention_policy=policy())
    for index in range(30):
        await store.save(
            resume_token=ResumeToken(value=f"performance-token-{index}"),
            checkpoint=checkpoint(execution_id=f"performance-{index}"),
        )
    repository = PostgreSQLCheckpointRetentionRepository(postgres_pool, policy=policy())
    samples: list[float] = []
    for _ in range(30):
        started = time.perf_counter()
        assert len(await repository.classify(limit=100)) == 30
        samples.append((time.perf_counter() - started) * 1_000)
    median = statistics.median(samples)
    p95 = statistics.quantiles(samples, n=20)[18]
    assert median < 500
    assert p95 < 500
