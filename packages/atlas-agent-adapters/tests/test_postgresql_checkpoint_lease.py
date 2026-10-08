from __future__ import annotations

import asyncio
import json
import multiprocessing
import os
import statistics
import sys
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from multiprocessing.queues import Queue
from pathlib import Path
from typing import Any

import pytest
from psycopg_pool import AsyncConnectionPool

from atlas_agents import (
    CheckpointLease,
    CheckpointLeaseConflictError,
    CheckpointLeaseLostError,
    CheckpointLeaseNotFoundError,
    CheckpointNotFoundError,
    ExecutionCheckpoint,
    ResumeToken,
)
from atlas_agents.adapters.checkpoints.postgresql import (
    CheckpointConcurrencyConflictError,
    PostgreSQLCheckpointLeaseManager,
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


def checkpoint() -> ExecutionCheckpoint:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["pending_approval"]["expires_at"] = (
        datetime.now(UTC) + timedelta(hours=1)
    ).isoformat()
    return ExecutionCheckpoint.model_validate(payload)


def changed(value: ExecutionCheckpoint, writer: str) -> ExecutionCheckpoint:
    return value.model_copy(update={"metadata": {"writer": writer}})


def pool(*, max_size: int = 12) -> AsyncConnectionPool[Any]:
    assert DSN is not None
    return AsyncConnectionPool(DSN, min_size=1, max_size=max_size, open=False)


@pytest.fixture
async def postgres_pool() -> AsyncIterator[AsyncConnectionPool[Any]]:
    value = pool()
    await value.open(wait=True)
    await PostgreSQLCheckpointMigrator(value).migrate()
    async with value.connection() as connection:
        await connection.execute(
            "TRUNCATE atlas_agent.checkpoint_leases, atlas_agent.checkpoints"
        )
    try:
        yield value
    finally:
        async with value.connection() as connection:
            await connection.execute(
                "TRUNCATE atlas_agent.checkpoint_leases, atlas_agent.checkpoints"
            )
        await value.close()


async def save_checkpoint(
    value: AsyncConnectionPool[Any], token_value: str
) -> tuple[PostgreSQLCheckpointStore, ResumeToken, ExecutionCheckpoint]:
    store = PostgreSQLCheckpointStore(value)
    token = ResumeToken(value=token_value)
    expected = checkpoint()
    await store.save(resume_token=token, checkpoint=expected)
    return store, token, expected


async def test_acquire_is_exclusive_and_uses_database_time(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    _, _, expected = await save_checkpoint(postgres_pool, "lease-exclusive")
    manager = PostgreSQLCheckpointLeaseManager(postgres_pool)

    outcomes = await asyncio.gather(
        manager.acquire(
            checkpoint_id=expected.execution_id,
            owner_id="worker-a",
            duration=timedelta(seconds=30),
        ),
        manager.acquire(
            checkpoint_id=expected.execution_id,
            owner_id="worker-b",
            duration=timedelta(seconds=30),
        ),
        return_exceptions=True,
    )

    leases = [item for item in outcomes if isinstance(item, CheckpointLease)]
    conflicts = [
        item for item in outcomes if isinstance(item, CheckpointLeaseConflictError)
    ]
    assert len(leases) == len(conflicts) == 1
    assert leases[0].fencing_token == 1
    assert leases[0].expires_at > leases[0].acquired_at


async def test_expiration_reacquires_with_monotonic_fencing(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    _, _, expected = await save_checkpoint(postgres_pool, "lease-expiration")
    manager = PostgreSQLCheckpointLeaseManager(postgres_pool)
    first = await manager.acquire(
        checkpoint_id=expected.execution_id,
        owner_id="worker-a",
        duration=timedelta(milliseconds=30),
    )
    await asyncio.sleep(0.06)

    second = await manager.acquire(
        checkpoint_id=expected.execution_id,
        owner_id="worker-b",
        duration=timedelta(seconds=30),
    )

    assert second.fencing_token == first.fencing_token + 1
    with pytest.raises(CheckpointLeaseLostError):
        await manager.renew(lease=first, duration=timedelta(seconds=30))
    with pytest.raises(CheckpointLeaseLostError):
        await manager.release(lease=first)


async def test_renew_is_conditional_and_never_regresses_expiration(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    _, _, expected = await save_checkpoint(postgres_pool, "lease-renew")
    manager = PostgreSQLCheckpointLeaseManager(postgres_pool)
    lease = await manager.acquire(
        checkpoint_id=expected.execution_id,
        owner_id="worker-a",
        duration=timedelta(seconds=10),
    )

    renewed = await asyncio.gather(
        manager.renew(lease=lease, duration=timedelta(seconds=20)),
        manager.renew(lease=lease, duration=timedelta(seconds=30)),
    )
    assert all(item.expires_at >= lease.expires_at for item in renewed)
    invalid_owner = lease.model_copy(update={"owner_id": "worker-b"})
    invalid_token = lease.model_copy(update={"fencing_token": lease.fencing_token + 1})
    with pytest.raises(CheckpointLeaseLostError):
        await manager.renew(lease=invalid_owner, duration=timedelta(seconds=30))
    with pytest.raises(CheckpointLeaseLostError):
        await manager.renew(lease=invalid_token, duration=timedelta(seconds=30))


async def test_release_retains_generation_and_double_release_is_controlled(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    _, _, expected = await save_checkpoint(postgres_pool, "lease-release")
    manager = PostgreSQLCheckpointLeaseManager(postgres_pool)
    first = await manager.acquire(
        checkpoint_id=expected.execution_id,
        owner_id="worker-a",
        duration=timedelta(seconds=30),
    )
    await manager.release(lease=first)
    with pytest.raises(CheckpointLeaseLostError):
        await manager.release(lease=first)

    second = await manager.acquire(
        checkpoint_id=expected.execution_id,
        owner_id="worker-b",
        duration=timedelta(seconds=30),
    )
    assert second.fencing_token == first.fencing_token + 1


async def test_fenced_compare_and_swap_rejects_stale_owner_and_revision(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    store, token, expected = await save_checkpoint(postgres_pool, "lease-cas")
    manager = PostgreSQLCheckpointLeaseManager(postgres_pool)
    stale = await manager.acquire(
        checkpoint_id=expected.execution_id,
        owner_id="worker-a",
        duration=timedelta(milliseconds=30),
    )
    await asyncio.sleep(0.06)
    current = await manager.acquire(
        checkpoint_id=expected.execution_id,
        owner_id="worker-b",
        duration=timedelta(seconds=30),
    )

    with pytest.raises(CheckpointLeaseLostError):
        await store.compare_and_swap_leased(
            resume_token=token,
            checkpoint=changed(expected, "stale"),
            expected_revision=1,
            lease=stale,
        )
    wrong_checkpoint = current.model_copy(update={"checkpoint_id": "other"})
    with pytest.raises(CheckpointLeaseLostError):
        await store.compare_and_swap_leased(
            resume_token=token,
            checkpoint=changed(expected, "wrong-checkpoint"),
            expected_revision=1,
            lease=wrong_checkpoint,
        )
    result = await store.compare_and_swap_leased(
        resume_token=token,
        checkpoint=changed(expected, "current"),
        expected_revision=1,
        lease=current,
    )
    assert result.revision == 2
    with pytest.raises(CheckpointConcurrencyConflictError):
        await store.compare_and_swap_leased(
            resume_token=token,
            checkpoint=changed(expected, "old-revision"),
            expected_revision=1,
            lease=current,
        )


async def test_fenced_consume_rejects_stale_owner_and_prevents_reactivation(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    store, token, expected = await save_checkpoint(postgres_pool, "lease-consume")
    manager = PostgreSQLCheckpointLeaseManager(postgres_pool)
    stale = await manager.acquire(
        checkpoint_id=expected.execution_id,
        owner_id="worker-a",
        duration=timedelta(milliseconds=30),
    )
    await asyncio.sleep(0.06)
    current = await manager.acquire(
        checkpoint_id=expected.execution_id,
        owner_id="worker-b",
        duration=timedelta(seconds=30),
    )

    with pytest.raises(CheckpointLeaseLostError):
        await store.consume_authorized_leased(
            resume_token=token,
            lease=stale,
            authorize=lambda _: None,
        )
    wrong_checkpoint = current.model_copy(update={"checkpoint_id": "other"})
    with pytest.raises(CheckpointLeaseLostError):
        await store.consume_authorized_leased(
            resume_token=token,
            lease=wrong_checkpoint,
            authorize=lambda _: None,
        )
    assert (
        await store.consume_authorized_leased(
            resume_token=token,
            lease=current,
            authorize=lambda _: None,
        )
        == expected
    )
    async with postgres_pool.connection() as connection:
        cursor = await connection.execute(
            """
            SELECT owner_id
            FROM atlas_agent.checkpoint_leases
            WHERE checkpoint_id = %s
            """,
            (expected.execution_id,),
        )
        row = await cursor.fetchone()
    assert row == (None,)
    with pytest.raises(CheckpointLeaseNotFoundError):
        await manager.acquire(
            checkpoint_id=expected.execution_id,
            owner_id="worker-c",
            duration=timedelta(seconds=30),
        )


async def test_authorization_failure_and_cancellation_roll_back_consumption(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    store, token, expected = await save_checkpoint(postgres_pool, "lease-rollback")
    manager = PostgreSQLCheckpointLeaseManager(postgres_pool)
    lease = await manager.acquire(
        checkpoint_id=expected.execution_id,
        owner_id="worker-a",
        duration=timedelta(seconds=30),
    )

    def cancel(_: ExecutionCheckpoint) -> None:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await store.consume_authorized_leased(
            resume_token=token,
            lease=lease,
            authorize=cancel,
        )
    assert await store.read(token)


async def test_missing_or_expired_checkpoint_cannot_be_leased(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    manager = PostgreSQLCheckpointLeaseManager(postgres_pool)
    with pytest.raises(CheckpointLeaseNotFoundError):
        await manager.acquire(
            checkpoint_id="missing",
            owner_id="worker-a",
            duration=timedelta(seconds=30),
        )


async def test_invalid_inputs_and_connection_failure_are_controlled(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    manager = PostgreSQLCheckpointLeaseManager(postgres_pool)
    with pytest.raises(ValueError, match="checkpoint"):
        await manager.acquire(
            checkpoint_id=" ", owner_id="worker-a", duration=timedelta(seconds=1)
        )
    with pytest.raises(ValueError, match="owner"):
        await manager.acquire(
            checkpoint_id="checkpoint",
            owner_id=" ",
            duration=timedelta(seconds=1),
        )
    with pytest.raises(ValueError, match="duração"):
        await manager.acquire(
            checkpoint_id="checkpoint",
            owner_id="worker-a",
            duration=timedelta(0),
        )

    closed = pool(max_size=1)
    broken = PostgreSQLCheckpointLeaseManager(closed)
    with pytest.raises(PostgreSQLCheckpointStoreError) as captured:
        await broken.acquire(
            checkpoint_id="checkpoint",
            owner_id="worker-a",
            duration=timedelta(seconds=1),
        )
    assert DSN is not None
    assert DSN not in str(captured.value)


async def _process_acquire(dsn: str, checkpoint_id: str, owner_id: str) -> str:
    value = AsyncConnectionPool(dsn, min_size=1, max_size=1, open=False)
    await value.open(wait=True)
    try:
        await PostgreSQLCheckpointLeaseManager(value).acquire(
            checkpoint_id=checkpoint_id,
            owner_id=owner_id,
            duration=timedelta(seconds=30),
        )
        return "success"
    except CheckpointLeaseConflictError:
        return "conflict"
    finally:
        await value.close()


def _process_worker(
    dsn: str, checkpoint_id: str, owner_id: str, result_queue: Queue[Any]
) -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    result_queue.put(asyncio.run(_process_acquire(dsn, checkpoint_id, owner_id)))


async def test_multiprocess_acquisition_has_exactly_one_owner(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    _, _, expected = await save_checkpoint(postgres_pool, "lease-multiprocess")
    assert DSN is not None
    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue()
    processes = [
        context.Process(
            target=_process_worker,
            args=(DSN, expected.execution_id, f"worker-{index}", result_queue),
        )
        for index in range(2)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=20)
        assert process.exitcode == 0
    outcomes = sorted(result_queue.get(timeout=5) for _ in processes)
    assert outcomes == ["conflict", "success"]


async def test_consumed_checkpoint_returns_not_found_before_lease_error(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    store, token, expected = await save_checkpoint(postgres_pool, "lease-consumed")
    manager = PostgreSQLCheckpointLeaseManager(postgres_pool)
    lease = await manager.acquire(
        checkpoint_id=expected.execution_id,
        owner_id="worker-a",
        duration=timedelta(seconds=30),
    )
    await store.consume_authorized_leased(
        resume_token=token, lease=lease, authorize=lambda _: None
    )
    with pytest.raises(CheckpointNotFoundError):
        await store.consume_authorized_leased(
            resume_token=token, lease=lease, authorize=lambda _: None
        )


async def test_lease_lifecycle_performance_baseline(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    _, _, expected = await save_checkpoint(postgres_pool, "lease-performance")
    manager = PostgreSQLCheckpointLeaseManager(postgres_pool)
    samples: dict[str, list[float]] = {
        "acquire": [],
        "renew": [],
        "release": [],
    }
    last_token = 0

    for index in range(30):
        started = time.perf_counter()
        lease = await manager.acquire(
            checkpoint_id=expected.execution_id,
            owner_id=f"worker-{index}",
            duration=timedelta(seconds=30),
        )
        samples["acquire"].append((time.perf_counter() - started) * 1_000)
        assert lease.fencing_token > last_token
        last_token = lease.fencing_token

        started = time.perf_counter()
        lease = await manager.renew(lease=lease, duration=timedelta(seconds=30))
        samples["renew"].append((time.perf_counter() - started) * 1_000)

        started = time.perf_counter()
        await manager.release(lease=lease)
        samples["release"].append((time.perf_counter() - started) * 1_000)

    summary = {
        operation: {
            "median_ms": round(statistics.median(values), 3),
            "p95_ms": round(statistics.quantiles(values, n=20)[18], 3),
            "samples": len(values),
        }
        for operation, values in samples.items()
    }
    assert all(item["samples"] == 30 for item in summary.values())
    assert all(item["median_ms"] > 0 for item in summary.values())
    assert all(item["p95_ms"] >= item["median_ms"] for item in summary.values())
