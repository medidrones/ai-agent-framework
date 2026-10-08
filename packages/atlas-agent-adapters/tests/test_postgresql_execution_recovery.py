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
    CheckpointLeaseLostError,
    ExecutionCheckpoint,
    ExecutionRecoveryCoordinator,
    ExecutionStatus,
    RecoveryCandidate,
    RecoveryDecision,
    RecoveryInvocationResult,
    RecoveryOutcome,
    RecoveryPolicy,
    ResumeToken,
)
from atlas_agents.adapters.checkpoints.postgresql import (
    PostgreSQLCheckpointLeaseManager,
    PostgreSQLCheckpointMigrator,
    PostgreSQLCheckpointStore,
    PostgreSQLRecoveryAttemptRecorder,
    PostgreSQLRecoveryCandidateRepository,
)

DSN = os.getenv("ATLAS_TEST_POSTGRES_DSN")
pytestmark = pytest.mark.skipif(DSN is None, reason="PostgreSQL real não configurado")
ROOT = Path(__file__).parents[2]
FIXTURE = (
    ROOT / "atlas-agent-core/tests/fixtures/checkpoints/execution-checkpoint-v1.json"
)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def checkpoint(*, execution_id: str = "execution-recovery") -> ExecutionCheckpoint:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["execution_id"] = execution_id
    payload["context"]["execution_id"] = execution_id
    payload["pending_approval"]["execution_id"] = execution_id
    payload["pending_approval"]["expires_at"] = (
        datetime.now(UTC) + timedelta(hours=1)
    ).isoformat()
    payload["transitions"] = [
        {
            "from_status": source,
            "to_status": target,
            "timestamp": "2026-01-01T00:00:00Z",
            "reason": None,
            "metadata": {},
        }
        for source, target in (
            ("created", "validating_input"),
            ("validating_input", "loading_context"),
            ("loading_context", "running"),
            ("running", "waiting_for_tool"),
            ("waiting_for_tool", "waiting_for_approval"),
        )
    ]
    for event in payload["events"]:
        event["execution_id"] = execution_id
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
        await connection.execute(
            """TRUNCATE atlas_agent.execution_recovery_attempts,
               atlas_agent.checkpoint_leases,
               atlas_agent.checkpoint_tombstones, atlas_agent.checkpoints"""
        )
    try:
        yield value
    finally:
        async with value.connection() as connection:
            await connection.execute(
                """TRUNCATE atlas_agent.execution_recovery_attempts,
                   atlas_agent.checkpoint_leases,
                   atlas_agent.checkpoint_tombstones, atlas_agent.checkpoints"""
            )
        await value.close()


class Eligible:
    async def evaluate(
        self,
        *,
        candidate: RecoveryCandidate,
        checkpoint: ExecutionCheckpoint | None,
    ) -> RecoveryDecision:
        del candidate, checkpoint
        return RecoveryDecision.ELIGIBLE


class ConsumingInvoker:
    def __init__(
        self,
        store: PostgreSQLCheckpointStore,
        token: ResumeToken,
        *,
        delay: float = 0,
    ) -> None:
        self.store = store
        self.token = token
        self.delay = delay
        self.calls = 0

    async def recover(
        self,
        *,
        candidate: RecoveryCandidate,
        checkpoint: ExecutionCheckpoint,
        lease: CheckpointLease,
    ) -> RecoveryInvocationResult:
        del candidate
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)

        def authorize(value: ExecutionCheckpoint) -> None:
            assert value.pending_approval.approval_request_id == (
                checkpoint.pending_approval.approval_request_id
            )

        await self.store.consume_authorized_leased(
            resume_token=self.token,
            lease=lease,
            authorize=authorize,
        )
        return RecoveryInvocationResult(outcome=RecoveryOutcome.RECOVERED)


async def save(
    value: AsyncConnectionPool[Any], execution_id: str, token_value: str
) -> tuple[PostgreSQLCheckpointStore, ResumeToken]:
    store = PostgreSQLCheckpointStore(value)
    token = ResumeToken(value=token_value)
    await store.save(
        resume_token=token, checkpoint=checkpoint(execution_id=execution_id)
    )
    return store, token


async def _process_recover(
    dsn: str, token_value: str, owner_id: str
) -> tuple[int, ...]:
    value = AsyncConnectionPool(dsn, min_size=1, max_size=2, open=False)
    await value.open(wait=True)
    try:
        token = ResumeToken(value=token_value)
        coordinator = ExecutionRecoveryCoordinator(
            repository=PostgreSQLRecoveryCandidateRepository(value),
            eligibility=Eligible(),
            lease_manager=PostgreSQLCheckpointLeaseManager(value),
            invoker=ConsumingInvoker(PostgreSQLCheckpointStore(value), token),
            attempt_recorder=PostgreSQLRecoveryAttemptRecorder(value),
            policy=RecoveryPolicy(owner_id=owner_id),
        )
        result = await coordinator.recover_once()
        return (
            result.recovered,
            result.conflicts,
            result.failed,
            result.blocked,
        )
    finally:
        await value.close()


def _recovery_process_worker(
    dsn: str, token_value: str, owner_id: str, result_queue: Queue[Any]
) -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    result_queue.put(asyncio.run(_process_recover(dsn, token_value, owner_id)))


async def test_discovery_is_bounded_stable_and_tenant_scoped(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    await save(postgres_pool, "execution-b", "token-b")
    await save(postgres_pool, "execution-a", "token-a")
    repository = PostgreSQLRecoveryCandidateRepository(postgres_pool)

    first = await repository.list_candidates(limit=1, tenant_id="tenant-fixture-1")
    all_items = await repository.list_candidates(limit=10)
    none = await repository.list_candidates(limit=10, tenant_id="other")

    assert len(first) == 1
    assert [item.execution_id for item in all_items] == [
        "execution-a",
        "execution-b",
    ]
    assert none == ()
    loaded = await repository.load_checkpoint(all_items[0])
    assert loaded.execution_id == "execution-a"
    assert loaded.status is ExecutionStatus.WAITING_FOR_APPROVAL


async def test_two_coordinators_authorize_exactly_one_recovery(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    store, token = await save(postgres_pool, "execution-race", "token-race")
    repository = PostgreSQLRecoveryCandidateRepository(postgres_pool)
    candidates = await repository.list_candidates(limit=1)
    assert len(candidates) == 1
    invoker = ConsumingInvoker(store, token)

    def coordinator(owner: str) -> ExecutionRecoveryCoordinator:
        return ExecutionRecoveryCoordinator(
            repository=repository,
            eligibility=Eligible(),
            lease_manager=PostgreSQLCheckpointLeaseManager(postgres_pool),
            invoker=invoker,
            attempt_recorder=PostgreSQLRecoveryAttemptRecorder(postgres_pool),
            policy=RecoveryPolicy(owner_id=owner),
        )

    results = await asyncio.gather(
        coordinator("worker-b").recover_once(),
        coordinator("worker-c").recover_once(),
    )
    assert sum(result.recovered for result in results) == 1, [
        result.model_dump(mode="json") for result in results
    ]
    assert invoker.calls == 1


async def test_multiprocess_recovery_consumes_checkpoint_once(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    opaque_value = "token-process-race"
    await save(postgres_pool, "execution-process-race", opaque_value)
    assert DSN is not None
    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue()
    processes = [
        context.Process(
            target=_recovery_process_worker,
            args=(DSN, opaque_value, f"process-worker-{index}", result_queue),
        )
        for index in range(2)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=20)
        assert process.exitcode == 0

    outcomes = [result_queue.get(timeout=5) for _ in processes]
    assert sum(item[0] for item in outcomes) == 1
    assert all(item[2:] == (0, 0) for item in outcomes)
    async with postgres_pool.connection() as connection:
        cursor = await connection.execute(
            """SELECT outcome FROM atlas_agent.execution_recovery_attempts
               WHERE execution_id = %s""",
            ("execution-process-race",),
        )
        rows = await cursor.fetchall()
    assert rows == [(RecoveryOutcome.RECOVERED.value,)]


async def test_attempt_limit_survives_new_recorder_instance(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    await save(postgres_pool, "execution-limit", "token-limit")
    repository = PostgreSQLRecoveryCandidateRepository(postgres_pool)
    item = (await repository.list_candidates(limit=1))[0]
    manager = PostgreSQLCheckpointLeaseManager(postgres_pool)
    lease = await manager.acquire(
        checkpoint_id=item.execution_id,
        owner_id="worker",
        duration=timedelta(seconds=30),
    )
    first = await PostgreSQLRecoveryAttemptRecorder(postgres_pool).begin_attempt(
        candidate=item, lease=lease, max_attempts=1
    )
    second = await PostgreSQLRecoveryAttemptRecorder(postgres_pool).begin_attempt(
        candidate=item, lease=lease, max_attempts=1
    )
    assert first is not None
    assert second is None


async def test_incomplete_attempt_is_recovered_after_restart(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    store, token = await save(postgres_pool, "execution-restart", "token-restart")
    repository = PostgreSQLRecoveryCandidateRepository(postgres_pool)
    item = (await repository.list_candidates(limit=1))[0]
    manager = PostgreSQLCheckpointLeaseManager(postgres_pool)
    stale_process_lease = await manager.acquire(
        checkpoint_id=item.execution_id,
        owner_id="process-before-restart",
        duration=timedelta(seconds=30),
    )
    first = await PostgreSQLRecoveryAttemptRecorder(postgres_pool).begin_attempt(
        candidate=item,
        lease=stale_process_lease,
        max_attempts=2,
    )
    assert first is not None
    await manager.release(lease=stale_process_lease)

    restarted = ExecutionRecoveryCoordinator(
        repository=PostgreSQLRecoveryCandidateRepository(postgres_pool),
        eligibility=Eligible(),
        lease_manager=PostgreSQLCheckpointLeaseManager(postgres_pool),
        invoker=ConsumingInvoker(store, token),
        attempt_recorder=PostgreSQLRecoveryAttemptRecorder(postgres_pool),
        policy=RecoveryPolicy(owner_id="process-after-restart", max_attempts=2),
    )
    result = await restarted.recover_once()

    assert result.recovered == 1
    assert result.results[0].attempt_number == 2
    async with postgres_pool.connection() as connection:
        cursor = await connection.execute(
            """SELECT attempt_number, outcome
               FROM atlas_agent.execution_recovery_attempts
               WHERE execution_id = %s
               ORDER BY attempt_number""",
            (item.execution_id,),
        )
        rows = await cursor.fetchall()
    assert rows == [(1, None), (2, RecoveryOutcome.RECOVERED.value)]


async def test_stale_fencing_cannot_complete_attempt(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    await save(postgres_pool, "execution-stale", "token-stale")
    repository = PostgreSQLRecoveryCandidateRepository(postgres_pool)
    item = (await repository.list_candidates(limit=1))[0]
    manager = PostgreSQLCheckpointLeaseManager(postgres_pool)
    stale = await manager.acquire(
        checkpoint_id=item.execution_id,
        owner_id="old",
        duration=timedelta(milliseconds=30),
    )
    recorder = PostgreSQLRecoveryAttemptRecorder(postgres_pool)
    attempt = await recorder.begin_attempt(candidate=item, lease=stale, max_attempts=3)
    assert attempt is not None
    await asyncio.sleep(0.06)
    await manager.acquire(
        checkpoint_id=item.execution_id,
        owner_id="new",
        duration=timedelta(seconds=30),
    )
    with pytest.raises(CheckpointLeaseLostError):
        await recorder.complete_attempt(
            attempt=attempt,
            lease=stale,
            outcome=RecoveryOutcome.RECOVERED,
            reason_code=None,
        )


async def test_lease_expiration_during_recovery_prevents_consumption(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    store, token = await save(postgres_pool, "execution-expire", "token-expire")
    coordinator = ExecutionRecoveryCoordinator(
        repository=PostgreSQLRecoveryCandidateRepository(postgres_pool),
        eligibility=Eligible(),
        lease_manager=PostgreSQLCheckpointLeaseManager(postgres_pool),
        invoker=ConsumingInvoker(store, token, delay=0.06),
        attempt_recorder=PostgreSQLRecoveryAttemptRecorder(postgres_pool),
        policy=RecoveryPolicy(
            owner_id="expiring-worker",
            lease_duration=timedelta(milliseconds=30),
        ),
    )

    result = await coordinator.recover_once()

    assert result.conflicts == 1
    assert result.results[0].reason_code == "lease_lost"
    remaining = await PostgreSQLRecoveryCandidateRepository(
        postgres_pool
    ).list_candidates(limit=1)
    assert len(remaining) == 1


async def test_recovery_performance_baseline(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    samples: dict[str, list[float]] = {
        "discovery": [],
        "acquisition": [],
        "recovery": [],
    }
    repository = PostgreSQLRecoveryCandidateRepository(postgres_pool)
    manager = PostgreSQLCheckpointLeaseManager(postgres_pool)

    for index in range(30):
        execution_id = f"execution-performance-{index:02d}"
        store, token = await save(
            postgres_pool, execution_id, f"opaque-performance-{index:02d}"
        )
        started = time.perf_counter()
        candidates = await repository.list_candidates(limit=1)
        samples["discovery"].append((time.perf_counter() - started) * 1_000)
        assert candidates[0].execution_id == execution_id

        started = time.perf_counter()
        lease = await manager.acquire(
            checkpoint_id=execution_id,
            owner_id=f"benchmark-probe-{index}",
            duration=timedelta(seconds=30),
        )
        samples["acquisition"].append((time.perf_counter() - started) * 1_000)
        await manager.release(lease=lease)

        coordinator = ExecutionRecoveryCoordinator(
            repository=repository,
            eligibility=Eligible(),
            lease_manager=manager,
            invoker=ConsumingInvoker(store, token),
            attempt_recorder=PostgreSQLRecoveryAttemptRecorder(postgres_pool),
            policy=RecoveryPolicy(owner_id=f"benchmark-worker-{index}"),
        )
        started = time.perf_counter()
        result = await coordinator.recover_once()
        samples["recovery"].append((time.perf_counter() - started) * 1_000)
        assert result.recovered == 1

    summaries = {
        operation: (
            statistics.median(values),
            statistics.quantiles(values, n=20)[18],
            len(values),
        )
        for operation, values in samples.items()
    }
    assert all(count == 30 for _, _, count in summaries.values())
    assert all(median > 0 for median, _, _ in summaries.values())
    assert all(p95 >= median for median, p95, _ in summaries.values())
