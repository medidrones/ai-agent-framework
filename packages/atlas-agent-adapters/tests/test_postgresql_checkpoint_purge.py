from __future__ import annotations

import asyncio
import hashlib
import json
import os
import statistics
import sys
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from multiprocessing.queues import Queue
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from psycopg import sql
from psycopg_pool import AsyncConnectionPool

from atlas_agents import (
    CheckpointLease,
    CheckpointLeaseNotFoundError,
    CheckpointPurgeConfig,
    CheckpointPurgeCoordinator,
    CheckpointRetentionPolicy,
    CheckpointSaveError,
    ExecutionCheckpoint,
    PurgeAuthorization,
    PurgeOutcome,
    ResumeToken,
)
from atlas_agents.adapters.checkpoints.postgresql import (
    PostgreSQLCheckpointLeaseManager,
    PostgreSQLCheckpointMigrator,
    PostgreSQLCheckpointPurgeRepository,
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


def policy() -> CheckpointRetentionPolicy:
    return CheckpointRetentionPolicy(
        policy_version="ds008-v1",
        active_ttl=timedelta(hours=1),
        hitl_ttl=timedelta(hours=2),
        consumed_retention=timedelta(days=7),
        expired_retention=timedelta(days=14),
        terminal_retention=timedelta(days=30),
        recovery_retention=timedelta(days=7),
    )


def authorization(tenant_id: str | None = None) -> PurgeAuthorization:
    return PurgeAuthorization(principal_id="ds008-maintenance", tenant_id=tenant_id)


def digest(value: str) -> bytes:
    return hashlib.sha256(value.encode()).digest()


def checkpoint(execution_id: str) -> ExecutionCheckpoint:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    now = datetime.now(UTC)
    payload["execution_id"] = execution_id
    payload["context"]["execution_id"] = execution_id
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
    value = AsyncConnectionPool(DSN, min_size=1, max_size=12, open=False)
    await value.open(wait=True)
    await PostgreSQLCheckpointMigrator(value).migrate()
    statement = """TRUNCATE atlas_agent.checkpoint_purge_audit,
        atlas_agent.execution_recovery_attempts, atlas_agent.checkpoint_leases,
        atlas_agent.checkpoint_tombstones, atlas_agent.checkpoints"""
    async with value.connection() as connection:
        await connection.execute(statement)
    try:
        yield value
    finally:
        async with value.connection() as connection:
            await connection.execute(statement)
        await value.close()


async def insert_checkpoint(
    pool: AsyncConnectionPool[Any],
    value: str,
    *,
    tenant_id: str | None = None,
    due: bool = True,
    legal_hold: bool = False,
    checkpoint_version: int = 1,
    policy_version: str | None = "ds008-v1",
) -> None:
    retention_delta = timedelta(days=-1 if due else 1)
    async with pool.connection() as connection:
        await connection.execute(
            """INSERT INTO atlas_agent.checkpoints (
                    token_digest, checkpoint_version, execution_id, agent_id,
                    tenant_id, payload, checkpoint_created_at, expires_at,
                    retention_class, retention_until, retention_policy_version,
                    legal_hold
                ) VALUES (
                    %s, %s, %s, 'agent', %s, '{}'::jsonb,
                    clock_timestamp() - interval '30 days',
                    clock_timestamp() - interval '20 days', 'waiting_for_approval',
                    clock_timestamp() + %s, %s, %s
                )""",
            (
                digest(value),
                checkpoint_version,
                f"execution-{value}",
                tenant_id,
                retention_delta,
                policy_version,
                legal_hold,
            ),
        )


async def insert_tombstone(
    pool: AsyncConnectionPool[Any], value: str, *, due: bool = True
) -> None:
    retention_delta = timedelta(days=-1 if due else 1)
    async with pool.connection() as connection:
        await connection.execute(
            """INSERT INTO atlas_agent.checkpoint_tombstones (
                    token_digest, execution_id, agent_id, consumed_at,
                    retention_until, retention_policy_version
                ) VALUES (
                    %s, %s, 'agent', clock_timestamp() - interval '8 days',
                    clock_timestamp() + %s, 'ds008-v1'
                )""",
            (digest(value), f"execution-{value}", retention_delta),
        )


def coordinator(
    pool: AsyncConnectionPool[Any], *, batch_size: int = 100, dry_run: bool = False
) -> tuple[CheckpointPurgeCoordinator, CheckpointPurgeConfig]:
    repository = PostgreSQLCheckpointPurgeRepository(pool, policy=policy())
    return (
        CheckpointPurgeCoordinator(repository),
        CheckpointPurgeConfig(batch_size=batch_size, dry_run=dry_run),
    )


async def table_count(pool: AsyncConnectionPool[Any], table: str) -> int:
    async with pool.connection() as connection:
        cursor = await connection.execute(
            sql.SQL("SELECT count(*) FROM atlas_agent.{}").format(sql.Identifier(table))
        )
        row = await cursor.fetchone()
    assert row is not None
    return int(row[0])


async def test_empty_batch_is_valid(postgres_pool: AsyncConnectionPool[Any]) -> None:
    service, config = coordinator(postgres_pool)
    result = await service.purge_once(authorization=authorization(), config=config)
    assert result.discovered == 0


async def test_closed_pool_is_reported_as_controlled_error() -> None:
    assert DSN is not None
    pool = AsyncConnectionPool(DSN, open=False)
    await pool.open(wait=True)
    await pool.close()
    repository = PostgreSQLCheckpointPurgeRepository(pool, policy=policy())
    with pytest.raises(PostgreSQLCheckpointStoreError):
        await repository.purge_batch(
            purge_run_id=str(uuid4()),
            authorization=authorization(),
            config=CheckpointPurgeConfig(),
        )


async def test_batch_limit_and_deterministic_order(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    for value in ("c", "a", "b"):
        await insert_checkpoint(postgres_pool, value)
    service, config = coordinator(postgres_pool, batch_size=2, dry_run=True)
    first = await service.purge_once(authorization=authorization(), config=config)
    second = await service.purge_once(authorization=authorization(), config=config)
    assert first.discovered == 2
    assert [item.execution_id for item in first.results] == [
        item.execution_id for item in second.results
    ]
    assert first.purged == 0
    assert first.skipped == 2


async def test_eligible_checkpoint_is_atomically_replaced_by_tombstone_and_audit(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    await insert_checkpoint(postgres_pool, "eligible")
    service, config = coordinator(postgres_pool)
    result = await service.purge_once(authorization=authorization(), config=config)
    assert result.purged == 1
    assert await table_count(postgres_pool, "checkpoints") == 0
    assert await table_count(postgres_pool, "checkpoint_tombstones") == 1
    assert await table_count(postgres_pool, "checkpoint_purge_audit") == 1
    store = PostgreSQLCheckpointStore(postgres_pool, retention_policy=policy())
    with pytest.raises(CheckpointSaveError, match="replay"):
        await store.save(
            resume_token=ResumeToken(value="eligible"),
            checkpoint=checkpoint("reactivation-forbidden"),
        )


async def test_retention_legal_hold_lease_recovery_and_schema_fail_closed(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    await insert_checkpoint(postgres_pool, "retained", due=False)
    await insert_checkpoint(postgres_pool, "legal", legal_hold=True)
    await insert_checkpoint(postgres_pool, "lease")
    await insert_checkpoint(postgres_pool, "recovery")
    await insert_checkpoint(postgres_pool, "schema", checkpoint_version=999)
    await insert_checkpoint(postgres_pool, "policy", policy_version=None)
    async with postgres_pool.connection() as connection:
        await connection.execute(
            """INSERT INTO atlas_agent.checkpoint_leases
               (checkpoint_id, owner_id, fencing_token, acquired_at, expires_at)
               VALUES ('execution-lease', 'owner', 7, clock_timestamp(),
                       clock_timestamp() + interval '1 hour')"""
        )
        await connection.execute(
            """INSERT INTO atlas_agent.execution_recovery_attempts
               (attempt_id, execution_id, checkpoint_id, owner_id,
                fencing_token, attempt_number)
               VALUES (%s, 'execution-recovery', 'execution-recovery',
                       'owner', 3, 1)""",
            (uuid4(),),
        )
    service, config = coordinator(postgres_pool)
    result = await service.purge_once(authorization=authorization(), config=config)
    assert result.purged == 0
    assert result.blocked == 5
    assert {item.reason_code for item in result.results} == {
        "legal_hold",
        "active_lease",
        "active_recovery",
        "incompatible_checkpoint",
    }
    assert await table_count(postgres_pool, "checkpoints") == 6


async def test_tenant_scope_prevents_cross_tenant_deletion(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    await insert_checkpoint(postgres_pool, "tenant-a", tenant_id="tenant-a")
    await insert_checkpoint(postgres_pool, "tenant-b", tenant_id="tenant-b")
    service, config = coordinator(postgres_pool)
    result = await service.purge_once(
        authorization=authorization("tenant-a"), config=config
    )
    assert result.purged == 1
    async with postgres_pool.connection() as connection:
        cursor = await connection.execute(
            "SELECT tenant_id FROM atlas_agent.checkpoints"
        )
        assert await cursor.fetchall() == [("tenant-b",)]


async def test_two_workers_never_delete_the_same_checkpoint_twice(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    for index in range(20):
        await insert_checkpoint(postgres_pool, f"worker-{index:02}")
    first, config = coordinator(postgres_pool, batch_size=20)
    second, _ = coordinator(postgres_pool, batch_size=20)
    results = await asyncio.gather(
        first.purge_once(authorization=authorization(), config=config),
        second.purge_once(authorization=authorization(), config=config),
    )
    assert sum(result.purged for result in results) == 20
    assert await table_count(postgres_pool, "checkpoints") == 0
    assert await table_count(postgres_pool, "checkpoint_tombstones") == 20
    assert await table_count(postgres_pool, "checkpoint_purge_audit") == 20


async def test_active_lease_preserves_fencing_generation(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    await insert_checkpoint(postgres_pool, "fencing")
    async with postgres_pool.connection() as connection:
        await connection.execute(
            """INSERT INTO atlas_agent.checkpoint_leases
               (checkpoint_id, owner_id, fencing_token, acquired_at, expires_at)
               VALUES ('execution-fencing', 'owner', 9, clock_timestamp(),
                       clock_timestamp() + interval '1 hour')"""
        )
    service, config = coordinator(postgres_pool)
    result = await service.purge_once(authorization=authorization(), config=config)
    assert result.blocked == 1
    async with postgres_pool.connection() as connection:
        cursor = await connection.execute(
            "SELECT fencing_token FROM atlas_agent.checkpoint_leases"
        )
        assert await cursor.fetchone() == (9,)


async def test_purge_racing_lease_acquisition_is_linearizable(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    await insert_checkpoint(postgres_pool, "lease-race")
    service, config = coordinator(postgres_pool)
    lease_manager = PostgreSQLCheckpointLeaseManager(postgres_pool)

    purge_task = asyncio.create_task(
        service.purge_once(authorization=authorization(), config=config)
    )
    lease_task = asyncio.create_task(
        lease_manager.acquire(
            checkpoint_id="execution-lease-race",
            owner_id="worker",
            duration=timedelta(minutes=1),
        )
    )
    purge_result, lease_result = await asyncio.gather(
        purge_task, lease_task, return_exceptions=True
    )
    assert not (
        not isinstance(purge_result, BaseException)
        and purge_result.purged == 1
        and not isinstance(lease_result, BaseException)
    )
    assert not isinstance(lease_result, BaseException) or isinstance(
        lease_result, CheckpointLeaseNotFoundError
    )


async def test_purge_racing_lease_renewal_preserves_ownership(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    await insert_checkpoint(postgres_pool, "lease-renew")
    async with postgres_pool.connection() as connection:
        cursor = await connection.execute(
            """UPDATE atlas_agent.checkpoints
               SET expires_at = clock_timestamp() + interval '1 hour'
               WHERE execution_id = 'execution-lease-renew'
               RETURNING clock_timestamp()"""
        )
        now = (await cursor.fetchone())[0]
        await connection.execute(
            """INSERT INTO atlas_agent.checkpoint_leases
               (checkpoint_id, owner_id, fencing_token, acquired_at, expires_at)
               VALUES ('execution-lease-renew', 'owner', 11, %s,
                       %s + interval '30 minutes')""",
            (now, now),
        )
    lease = CheckpointLease(
        checkpoint_id="execution-lease-renew",
        owner_id="owner",
        fencing_token=11,
        acquired_at=now,
        expires_at=now + timedelta(minutes=30),
    )
    service, config = coordinator(postgres_pool)
    manager = PostgreSQLCheckpointLeaseManager(postgres_pool)
    purge_result, renewed = await asyncio.gather(
        service.purge_once(authorization=authorization(), config=config),
        manager.renew(lease=lease, duration=timedelta(hours=1)),
    )
    assert purge_result.purged == 0
    assert renewed.fencing_token == 11
    assert await table_count(postgres_pool, "checkpoints") == 1


async def test_concurrent_retention_change_is_never_overwritten_by_purge(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    await insert_checkpoint(postgres_pool, "retention-race")
    async with postgres_pool.connection() as updater:
        await updater.execute(
            """UPDATE atlas_agent.checkpoints
               SET retention_until = clock_timestamp() + interval '30 days'
               WHERE execution_id = 'execution-retention-race'"""
        )
        service, config = coordinator(postgres_pool)
        concurrent = await service.purge_once(
            authorization=authorization(), config=config
        )
        assert concurrent.discovered == 0
    after_commit = await service.purge_once(
        authorization=authorization(), config=config
    )
    assert after_commit.discovered == 0
    assert await table_count(postgres_pool, "checkpoints") == 1


async def test_concurrent_legal_hold_creation_is_respected(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    await insert_checkpoint(postgres_pool, "legal-race")
    async with postgres_pool.connection() as updater:
        await updater.execute(
            """UPDATE atlas_agent.checkpoints SET legal_hold = TRUE
               WHERE execution_id = 'execution-legal-race'"""
        )
        service, config = coordinator(postgres_pool)
        concurrent = await service.purge_once(
            authorization=authorization(), config=config
        )
        assert concurrent.discovered == 0
    after_commit = await service.purge_once(
        authorization=authorization(), config=config
    )
    assert after_commit.blocked == 1
    assert after_commit.results[0].reason_code == "legal_hold"
    assert await table_count(postgres_pool, "checkpoints") == 1


async def test_row_lock_skips_candidate_without_unsafe_deletion(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    await insert_checkpoint(postgres_pool, "locked")
    async with postgres_pool.connection() as blocker:
        await blocker.execute(
            """SELECT 1 FROM atlas_agent.checkpoints
               WHERE execution_id = 'execution-locked' FOR UPDATE"""
        )
        service, config = coordinator(postgres_pool)
        result = await service.purge_once(authorization=authorization(), config=config)
        assert result.discovered == 0
    assert await table_count(postgres_pool, "checkpoints") == 1


async def test_resume_race_cannot_reactivate_a_purged_checkpoint(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    token = ResumeToken(value="resume-race")
    store = PostgreSQLCheckpointStore(postgres_pool, retention_policy=policy())
    await store.save(
        resume_token=token,
        checkpoint=checkpoint("execution-resume-race"),
    )
    async with postgres_pool.connection() as connection:
        await connection.execute(
            """UPDATE atlas_agent.checkpoints
               SET retention_until = clock_timestamp() - interval '1 day'
               WHERE execution_id = 'execution-resume-race'"""
        )
    service, config = coordinator(postgres_pool)
    purge_result, consume_result = await asyncio.gather(
        service.purge_once(authorization=authorization(), config=config),
        store.consume(token),
        return_exceptions=True,
    )
    assert not isinstance(purge_result, BaseException)
    assert purge_result.purged == 0
    assert not isinstance(consume_result, BaseException)
    assert await table_count(postgres_pool, "checkpoints") == 0
    assert await table_count(postgres_pool, "checkpoint_tombstones") == 1


async def test_repeated_purge_is_idempotent_and_tombstone_window_is_explicit(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    await insert_checkpoint(postgres_pool, "idempotent")
    service, config = coordinator(postgres_pool)
    first = await service.purge_once(authorization=authorization(), config=config)
    second = await service.purge_once(authorization=authorization(), config=config)
    assert first.purged == 1
    assert second.discovered == 0
    async with postgres_pool.connection() as connection:
        cursor = await connection.execute(
            """SELECT retention_until > consumed_at
               FROM atlas_agent.checkpoint_tombstones"""
        )
        assert await cursor.fetchone() == (True,)


async def test_elapsed_tombstone_is_removed_only_after_replay_window(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    await insert_tombstone(postgres_pool, "elapsed")
    await insert_tombstone(postgres_pool, "protected", due=False)
    service, config = coordinator(postgres_pool)
    result = await service.purge_once(authorization=authorization(), config=config)
    assert result.purged == 1
    assert result.results[0].execution_id == "execution-elapsed"
    assert await table_count(postgres_pool, "checkpoint_tombstones") == 1


async def test_audit_failure_rolls_back_tombstone_and_delete(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    await insert_checkpoint(postgres_pool, "rollback")
    async with postgres_pool.connection() as connection:
        await connection.execute(
            """CREATE OR REPLACE FUNCTION atlas_agent.reject_purge_audit()
               RETURNS trigger LANGUAGE plpgsql AS $$
               BEGIN RAISE EXCEPTION 'audit unavailable'; END $$"""
        )
        await connection.execute(
            """CREATE TRIGGER reject_purge_audit
               BEFORE INSERT ON atlas_agent.checkpoint_purge_audit
               FOR EACH ROW EXECUTE FUNCTION atlas_agent.reject_purge_audit()"""
        )
    service, config = coordinator(postgres_pool)
    with pytest.raises(PostgreSQLCheckpointStoreError):
        await service.purge_once(authorization=authorization(), config=config)
    assert await table_count(postgres_pool, "checkpoints") == 1
    assert await table_count(postgres_pool, "checkpoint_tombstones") == 0
    async with postgres_pool.connection() as connection:
        await connection.execute(
            "DROP TRIGGER reject_purge_audit ON atlas_agent.checkpoint_purge_audit"
        )
        await connection.execute("DROP FUNCTION atlas_agent.reject_purge_audit()")


async def test_cancellation_rolls_back_and_propagates(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    await insert_checkpoint(postgres_pool, "cancelled")
    async with postgres_pool.connection() as connection:
        await connection.execute(
            """CREATE OR REPLACE FUNCTION atlas_agent.delay_purge_audit()
               RETURNS trigger LANGUAGE plpgsql AS $$
               BEGIN PERFORM pg_sleep(10); RETURN NEW; END $$"""
        )
        await connection.execute(
            """CREATE TRIGGER delay_purge_audit
               BEFORE INSERT ON atlas_agent.checkpoint_purge_audit
               FOR EACH ROW EXECUTE FUNCTION atlas_agent.delay_purge_audit()"""
        )
    service, config = coordinator(postgres_pool)
    task = asyncio.create_task(
        service.purge_once(authorization=authorization(), config=config)
    )
    await asyncio.sleep(0.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await table_count(postgres_pool, "checkpoints") == 1
    assert await table_count(postgres_pool, "checkpoint_tombstones") == 0
    async with postgres_pool.connection() as connection:
        await connection.execute(
            "DROP TRIGGER delay_purge_audit ON atlas_agent.checkpoint_purge_audit"
        )
        await connection.execute("DROP FUNCTION atlas_agent.delay_purge_audit()")


async def test_reconciliation_distinguishes_persisted_and_unknown_operations(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    await insert_checkpoint(postgres_pool, "reconcile")
    repository = PostgreSQLCheckpointPurgeRepository(postgres_pool, policy=policy())
    result = await repository.purge_batch(
        purge_run_id=str(uuid4()),
        authorization=authorization(),
        config=CheckpointPurgeConfig(dry_run=False),
    )
    persisted = result.results[0]
    candidates = [
        repository._candidate(
            (
                persisted.checkpoint_id,
                persisted.execution_id,
                "agent",
                None,
                "consumed",
                datetime.now(UTC) - timedelta(days=8),
                datetime.now(UTC) - timedelta(days=1),
                "ds008-v1",
                1,
                False,
            ),
            kind="tombstone",
        ),
        repository._candidate(
            (
                digest("unknown").hex(),
                "execution-unknown",
                "agent",
                None,
                "consumed",
                datetime.now(UTC) - timedelta(days=8),
                datetime.now(UTC) - timedelta(days=1),
                "ds008-v1",
                1,
                False,
            ),
            kind="tombstone",
        ),
    ]
    reconciled = await repository._reconcile(
        purge_run_id=result.purge_run_id,
        operation_ids=[persisted.operation_id, str(uuid4())],
        candidates=candidates,
    )
    assert reconciled[0].outcome is PurgeOutcome.PURGED
    assert reconciled[1].outcome is PurgeOutcome.OUTCOME_UNKNOWN


async def test_real_database_end_to_end_with_two_workers(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    for index in range(40):
        await insert_checkpoint(postgres_pool, f"eligible-{index:02}")
    for index in range(20):
        await insert_checkpoint(postgres_pool, f"active-{index:02}", due=False)
    for index in range(15):
        await insert_checkpoint(postgres_pool, f"retained-{index:02}", due=False)
    for index in range(10):
        await insert_checkpoint(postgres_pool, f"lease-{index:02}")
    for index in range(10):
        await insert_checkpoint(postgres_pool, f"legal-{index:02}", legal_hold=True)
    for index in range(5):
        await insert_checkpoint(postgres_pool, f"recovery-{index:02}")
    async with postgres_pool.connection() as connection:
        for index in range(10):
            execution_id = f"execution-lease-{index:02}"
            await connection.execute(
                """INSERT INTO atlas_agent.checkpoint_leases
                   (checkpoint_id, owner_id, fencing_token, acquired_at, expires_at)
                   VALUES (%s, 'owner', 1, clock_timestamp(),
                           clock_timestamp() + interval '1 hour')""",
                (execution_id,),
            )
        for index in range(5):
            execution_id = f"execution-recovery-{index:02}"
            await connection.execute(
                """INSERT INTO atlas_agent.execution_recovery_attempts
                   (attempt_id, execution_id, checkpoint_id, owner_id,
                    fencing_token, attempt_number)
                   VALUES (%s, %s, %s, 'owner', 1, 1)""",
                (uuid4(), execution_id, execution_id),
            )
    first, config = coordinator(postgres_pool, batch_size=100)
    second, _ = coordinator(postgres_pool, batch_size=100)
    results = await asyncio.gather(
        first.purge_once(authorization=authorization(), config=config),
        second.purge_once(authorization=authorization(), config=config),
    )
    assert sum(result.purged for result in results) == 40
    assert await table_count(postgres_pool, "checkpoints") == 60
    assert await table_count(postgres_pool, "checkpoint_tombstones") == 40
    assert await table_count(postgres_pool, "checkpoint_purge_audit") == 65


async def test_performance_baseline_for_one_hundred_records(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    for index in range(100):
        await insert_checkpoint(postgres_pool, f"performance-{index:03}")
    service, config = coordinator(postgres_pool, batch_size=100, dry_run=True)
    samples: list[float] = []
    for _ in range(5):
        started = time.perf_counter()
        result = await service.purge_once(authorization=authorization(), config=config)
        samples.append((time.perf_counter() - started) * 1_000)
        assert result.discovered == 100
    assert statistics.median(samples) < 5_000
    assert statistics.quantiles(samples, n=20)[18] < 5_000


def _multiprocess_worker(dsn: str, queue: Queue[int]) -> None:
    async def run() -> int:
        pool = AsyncConnectionPool(dsn, min_size=1, max_size=2, open=False)
        await pool.open(wait=True)
        try:
            service, config = coordinator(pool, batch_size=50)
            result = await service.purge_once(
                authorization=authorization(), config=config
            )
            return result.purged
        finally:
            await pool.close()

    queue.put(asyncio.run(run()))


async def test_two_independent_processes_do_not_duplicate_deletion(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    assert DSN is not None
    for index in range(30):
        await insert_checkpoint(postgres_pool, f"process-{index:02}")
    import multiprocessing

    context = multiprocessing.get_context("spawn")
    queue: Queue[int] = context.Queue()
    processes = [
        context.Process(target=_multiprocess_worker, args=(DSN, queue))
        for _ in range(2)
    ]
    for process in processes:
        process.start()
    for process in processes:
        await asyncio.to_thread(process.join, 30)
        assert process.exitcode == 0
    assert sum(queue.get(timeout=5) for _ in processes) == 30
    assert await table_count(postgres_pool, "checkpoints") == 0
