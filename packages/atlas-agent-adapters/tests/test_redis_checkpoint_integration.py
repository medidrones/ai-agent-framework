from __future__ import annotations

import asyncio
import json
import multiprocessing
import os
from collections.abc import AsyncIterator, Awaitable
from datetime import UTC, datetime, timedelta
from multiprocessing.queues import Queue
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from atlas_agents import (
    CheckpointLeaseConflictError,
    CheckpointLeaseLostError,
    CheckpointNotFoundError,
    CheckpointSaveError,
    ExecutionCheckpoint,
    InvalidCheckpointError,
    ResumeToken,
    UnsupportedCheckpointVersionError,
)
from atlas_agents.adapters.checkpoints.redis import (
    RedisCheckpointConcurrencyConflictError,
    RedisCheckpointStore,
    RedisCheckpointStoreError,
    RedisConsumeReconciliationStatus,
)
from atlas_agents.adapters.checkpoints.redis.store import RedisCheckpointClient

REDIS_URL = os.getenv("ATLAS_TEST_REDIS_URL")
pytestmark = pytest.mark.skipif(
    REDIS_URL is None,
    reason="ATLAS_TEST_REDIS_URL não configurada para o Redis real.",
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


def store(client: Redis, *, namespace: str | None = None) -> RedisCheckpointStore:
    return RedisCheckpointStore(
        cast(RedisCheckpointClient, client),
        namespace=namespace or f"ds010:{uuid4().hex}",
        token_hmac_key=b"integration-hmac-key-material-32b",
    )


def _consume_in_process(
    redis_url: str,
    namespace: str,
    token_value: str,
    outcomes: Queue[str],
) -> None:
    async def consume() -> None:
        client = Redis.from_url(redis_url, decode_responses=False)
        value = store(client, namespace=namespace)
        try:
            await value.consume(ResumeToken(value=token_value))
        except CheckpointNotFoundError:
            outcomes.put("rejected")
        else:
            outcomes.put("consumed")
        finally:
            await client.aclose()

    asyncio.run(consume())


async def test_save_read_and_process_restart(redis_client: Redis) -> None:
    namespace = f"restart:{uuid4().hex}"
    token = ResumeToken(value="restart-token")
    expected = checkpoint()
    first = store(redis_client, namespace=namespace)
    await first.save(resume_token=token, checkpoint=expected)

    second = store(redis_client, namespace=namespace)
    snapshot = await second.read(token)

    assert snapshot.checkpoint == expected
    assert snapshot.revision == 1


async def test_save_does_not_overwrite_active_or_consumed(redis_client: Redis) -> None:
    value = store(redis_client)
    token = ResumeToken(value="protected-token")
    await value.save(resume_token=token, checkpoint=checkpoint())
    with pytest.raises(CheckpointSaveError):
        await value.save(resume_token=token, checkpoint=checkpoint())

    await value.consume(token)
    with pytest.raises(CheckpointSaveError):
        await value.save(resume_token=token, checkpoint=checkpoint())


async def test_concurrent_consumers_have_exactly_one_winner(
    redis_client: Redis,
) -> None:
    value = store(redis_client)
    token = ResumeToken(value="concurrent-consume")
    await value.save(resume_token=token, checkpoint=checkpoint())

    outcomes = await asyncio.gather(
        *(value.consume(token) for _ in range(20)), return_exceptions=True
    )

    assert sum(isinstance(item, ExecutionCheckpoint) for item in outcomes) == 1
    assert sum(isinstance(item, CheckpointNotFoundError) for item in outcomes) == 19


async def test_authorization_failure_preserves_checkpoint(redis_client: Redis) -> None:
    value = store(redis_client)
    token = ResumeToken(value="authorization-failure")
    expected = checkpoint()
    await value.save(resume_token=token, checkpoint=expected)

    def reject(_: ExecutionCheckpoint) -> None:
        raise PermissionError("Aprovação rejeitada.")

    with pytest.raises(PermissionError):
        await value.consume_authorized(resume_token=token, authorize=reject)

    assert await value.consume(token) == expected


async def test_authorized_concurrent_consumers_have_one_winner(
    redis_client: Redis,
) -> None:
    value = store(redis_client)
    token = ResumeToken(value="authorized-concurrency")
    await value.save(resume_token=token, checkpoint=checkpoint())

    outcomes = await asyncio.gather(
        *(
            value.consume_authorized(resume_token=token, authorize=lambda _: None)
            for _ in range(20)
        ),
        return_exceptions=True,
    )

    assert sum(isinstance(item, ExecutionCheckpoint) for item in outcomes) == 1
    assert (
        sum(
            isinstance(
                item,
                (CheckpointNotFoundError, RedisCheckpointConcurrencyConflictError),
            )
            for item in outcomes
        )
        == 19
    )


async def test_compare_and_swap_prevents_lost_update(redis_client: Redis) -> None:
    value = store(redis_client)
    token = ResumeToken(value="cas-concurrency")
    expected = checkpoint()
    await value.save(resume_token=token, checkpoint=expected)

    outcomes = await asyncio.gather(
        *(
            value.compare_and_swap(
                resume_token=token,
                checkpoint=expected,
                expected_revision=1,
            )
            for _ in range(12)
        ),
        return_exceptions=True,
    )

    assert sum(not isinstance(item, BaseException) for item in outcomes) == 1
    assert (
        sum(
            isinstance(item, RedisCheckpointConcurrencyConflictError)
            for item in outcomes
        )
        == 11
    )
    assert (await value.read(token)).revision == 2


async def test_update_and_consume_have_consistent_outcome(redis_client: Redis) -> None:
    value = store(redis_client)
    token = ResumeToken(value="update-consume-race")
    expected = checkpoint()
    await value.save(resume_token=token, checkpoint=expected)

    update, consumed = await asyncio.gather(
        value.compare_and_swap(
            resume_token=token,
            checkpoint=expected,
            expected_revision=1,
        ),
        value.consume(token),
        return_exceptions=True,
    )

    successful = sum(not isinstance(item, BaseException) for item in (update, consumed))
    assert successful in {1, 2}
    if not isinstance(update, BaseException) and not isinstance(
        consumed, BaseException
    ):
        assert consumed == update.checkpoint
        assert update.revision == 2
    else:
        assert isinstance(
            update if isinstance(update, BaseException) else consumed,
            (CheckpointNotFoundError, RedisCheckpointConcurrencyConflictError),
        )


async def test_logical_expiration_uses_redis_time_boundary(
    redis_client: Redis,
) -> None:
    value = store(redis_client)
    token = ResumeToken(value="expired")
    await value.save(
        resume_token=token,
        checkpoint=checkpoint(
            expires_at=datetime.now(UTC) + timedelta(milliseconds=80)
        ),
    )
    assert (await value.read(token)).revision == 1
    await asyncio.sleep(0.12)
    with pytest.raises(CheckpointNotFoundError):
        await value.consume(token)

    state = await cast(
        Awaitable[bytes | None],
        redis_client.hget(value._keyspace.checkpoint_key(token), "state"),
    )
    assert state == b"expired"


async def test_consumption_preserves_tombstone_and_native_ttl(
    redis_client: Redis,
) -> None:
    value = store(redis_client)
    token = ResumeToken(value="tombstone")
    await value.save(resume_token=token, checkpoint=checkpoint())
    await value.consume(token)

    key = value._keyspace.checkpoint_key(token)
    stored = await cast(Awaitable[dict[bytes, bytes]], redis_client.hgetall(key))
    assert stored[b"state"] == b"consumed"
    assert b"payload" not in stored
    assert b"consume_operation_id" in stored
    assert await redis_client.pttl(key) > 0


async def test_namespaces_do_not_collide(redis_client: Redis) -> None:
    token = ResumeToken(value="same-token")
    first = store(redis_client, namespace="tenant-a")
    second = store(redis_client, namespace="tenant-b")
    expected = checkpoint()

    await first.save(resume_token=token, checkpoint=expected)
    await second.save(resume_token=token, checkpoint=expected)

    assert first._keyspace.checkpoint_key(token) != second._keyspace.checkpoint_key(
        token
    )
    assert await first.consume(token) == expected
    assert await second.consume(token) == expected


async def test_unknown_schema_and_corrupted_payload_are_rejected(
    redis_client: Redis,
) -> None:
    value = store(redis_client)
    schema_token = ResumeToken(value="unknown-schema")
    await value.save(resume_token=schema_token, checkpoint=checkpoint())
    await cast(
        Awaitable[Any],
        redis_client.hset(
            value._keyspace.checkpoint_key(schema_token), "schema_version", "999"
        ),
    )
    with pytest.raises(UnsupportedCheckpointVersionError):
        await value.read(schema_token)

    corrupt_token = ResumeToken(value="corrupt")
    await value.save(resume_token=corrupt_token, checkpoint=checkpoint())
    await cast(
        Awaitable[Any],
        redis_client.hset(
            value._keyspace.checkpoint_key(corrupt_token), "payload", "not-json"
        ),
    )
    with pytest.raises(InvalidCheckpointError):
        await value.consume_authorized(
            resume_token=corrupt_token, authorize=lambda _: None
        )
    assert (
        await cast(
            Awaitable[bytes | None],
            redis_client.hget(value._keyspace.checkpoint_key(corrupt_token), "state"),
        )
        == b"active"
    )


async def test_serialization_round_trip_is_deterministic(redis_client: Redis) -> None:
    expected = checkpoint()
    first = RedisCheckpointStore._serialize(expected)
    second = RedisCheckpointStore._serialize(expected)
    assert first == second

    value = store(redis_client)
    token = ResumeToken(value="serialization")
    await value.save(resume_token=token, checkpoint=expected)
    restored = (await value.read(token)).checkpoint
    assert restored.model_dump(mode="json") == expected.model_dump(mode="json")


async def test_injected_client_is_not_closed(redis_client: Redis) -> None:
    value = store(redis_client)
    await value.aclose()
    assert await redis_client.ping()


async def test_unavailable_redis_is_a_controlled_error() -> None:
    value = RedisCheckpointStore.from_url(
        "redis://127.0.0.1:1/15",
        namespace="unavailable",
        socket_timeout=0.05,
        max_connections=1,
    )
    try:
        with pytest.raises(RedisCheckpointStoreError, match="não está disponível"):
            await value.ping()
    finally:
        await value.aclose()


async def test_one_hundred_consumers_have_one_linearized_winner(
    redis_client: Redis,
) -> None:
    value = store(redis_client)
    token = ResumeToken(value="one-hundred-consumers")
    await value.save(resume_token=token, checkpoint=checkpoint())

    outcomes = await asyncio.gather(
        *(value.consume(token) for _ in range(100)), return_exceptions=True
    )

    assert sum(isinstance(item, ExecutionCheckpoint) for item in outcomes) == 1
    assert sum(isinstance(item, CheckpointNotFoundError) for item in outcomes) == 99


async def test_identified_consume_reconciliation_distinguishes_attempts(
    redis_client: Redis,
) -> None:
    value = store(redis_client)
    token = ResumeToken(value="identified-reconciliation")
    expected = checkpoint()
    await value.save(resume_token=token, checkpoint=expected)

    consumed = await value.consume_authorized_identified(
        resume_token=token,
        operation_id="resume-attempt-one",
        authorize=lambda _: None,
    )
    own = await value.reconcile_consumption(
        resume_token=token, operation_id="resume-attempt-one"
    )
    different = await value.reconcile_consumption(
        resume_token=token, operation_id="resume-attempt-two"
    )

    assert consumed == expected
    assert own.status is RedisConsumeReconciliationStatus.APPLIED
    assert different.status is RedisConsumeReconciliationStatus.NOT_APPLIED


async def test_redis_lease_fencing_rejects_stale_owner_and_accepts_new_generation(
    redis_client: Redis,
) -> None:
    value = store(redis_client)
    token = ResumeToken(value="lease-fencing")
    expected = checkpoint()
    await value.save(resume_token=token, checkpoint=expected)

    first = await value.acquire_lease(
        resume_token=token,
        owner_id="worker-a",
        duration=timedelta(milliseconds=80),
    )
    with pytest.raises(CheckpointLeaseConflictError):
        await value.acquire_lease(
            resume_token=token,
            owner_id="worker-b",
            duration=timedelta(seconds=30),
        )

    await asyncio.sleep(0.12)
    second = await value.acquire_lease(
        resume_token=token,
        owner_id="worker-b",
        duration=timedelta(seconds=30),
    )
    assert second.fencing_token == first.fencing_token + 1

    with pytest.raises(CheckpointLeaseLostError):
        await value.consume_authorized_leased(
            resume_token=token,
            lease=first,
            authorize=lambda _: None,
        )

    assert (
        await value.consume_authorized_leased(
            resume_token=token,
            lease=second,
            authorize=lambda _: None,
        )
        == expected
    )


async def test_leased_compare_and_swap_requires_current_generation(
    redis_client: Redis,
) -> None:
    value = store(redis_client)
    token = ResumeToken(value="leased-cas")
    expected = checkpoint()
    await value.save(resume_token=token, checkpoint=expected)
    lease = await value.acquire_lease(
        resume_token=token,
        owner_id="worker-a",
        duration=timedelta(seconds=30),
    )

    result = await value.compare_and_swap_leased(
        resume_token=token,
        checkpoint=expected,
        expected_revision=1,
        lease=lease,
    )
    assert result.revision == 2

    await value.release_lease(resume_token=token, lease=lease)
    with pytest.raises(CheckpointLeaseLostError):
        await value.compare_and_swap_leased(
            resume_token=token,
            checkpoint=expected,
            expected_revision=2,
            lease=lease,
        )


async def test_independent_processes_have_one_consume_winner(
    redis_client: Redis,
) -> None:
    assert REDIS_URL is not None
    namespace = f"multiprocess:{uuid4().hex}"
    token_value = f"multiprocess-{uuid4().hex}"
    value = store(redis_client, namespace=namespace)
    await value.save(
        resume_token=ResumeToken(value=token_value), checkpoint=checkpoint()
    )

    context = multiprocessing.get_context("spawn")
    outcomes = context.Queue()
    processes = [
        context.Process(
            target=_consume_in_process,
            args=(REDIS_URL, namespace, token_value, outcomes),
        )
        for _ in range(10)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=20)
        assert process.exitcode == 0

    results = [outcomes.get(timeout=2) for _ in processes]
    assert results.count("consumed") == 1
    assert results.count("rejected") == 9
