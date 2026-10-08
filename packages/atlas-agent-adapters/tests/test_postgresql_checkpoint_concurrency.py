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
from typing import Any

import pytest
from psycopg_pool import AsyncConnectionPool

from atlas_agents import (
    CheckpointNotFoundError,
    ExecutionCheckpoint,
    InvalidCheckpointError,
    ResumeToken,
)
from atlas_agents.adapters.checkpoints.postgresql import (
    CheckpointConcurrencyConflictError,
    PostgreSQLCheckpointMigrator,
    PostgreSQLCheckpointSnapshot,
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


def changed(value: ExecutionCheckpoint, writer: str) -> ExecutionCheckpoint:
    return value.model_copy(
        update={
            "metadata": {"writer": writer},
            "updated_at": datetime.now(UTC),
        }
    )


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


async def _wait_for_lock_waiters(
    value: AsyncConnectionPool[Any],
    *,
    expected: int,
) -> None:
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
        if row is not None and int(row[0]) >= expected:
            return
        await asyncio.sleep(0.02)
    raise AssertionError("As operações não aguardaram o lock PostgreSQL esperado.")


async def _process_compare_and_swap(
    dsn: str,
    token_value: str,
    payload: str,
) -> int:
    value = AsyncConnectionPool(dsn, min_size=1, max_size=1, open=False)
    await value.open(wait=True)
    try:
        snapshot = await PostgreSQLCheckpointStore(value).compare_and_swap(
            resume_token=ResumeToken(value=token_value),
            checkpoint=ExecutionCheckpoint.model_validate_json(payload),
            expected_revision=1,
        )
        return snapshot.revision
    finally:
        await value.close()


def _process_writer(
    dsn: str,
    token_value: str,
    payload: str,
    barrier: Barrier,
    result_queue: Queue[Any],
) -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        barrier.wait(timeout=15)
        revision = asyncio.run(_process_compare_and_swap(dsn, token_value, payload))
        result_queue.put(("success", revision))
    except CheckpointConcurrencyConflictError as error:
        result_queue.put(("conflict", error.actual_revision))
    except Exception as error:
        result_queue.put(("unexpected", type(error).__name__))


async def test_read_and_compare_and_swap_increment_revision(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    token = ResumeToken(value="cas-success-token")
    original = checkpoint()
    updated = changed(original, "writer-a")
    store = PostgreSQLCheckpointStore(postgres_pool)
    await store.save(resume_token=token, checkpoint=original)

    first = await store.read(token)
    second = await store.read(token)
    result = await store.compare_and_swap(
        resume_token=token,
        checkpoint=updated,
        expected_revision=first.revision,
    )

    assert first.revision == second.revision == 1
    assert result == PostgreSQLCheckpointSnapshot(checkpoint=updated, revision=2)
    assert await store.read(token) == result
    next_checkpoint = changed(updated, "writer-b")
    next_result = await store.compare_and_swap(
        resume_token=token,
        checkpoint=next_checkpoint,
        expected_revision=result.revision,
    )
    assert next_result == PostgreSQLCheckpointSnapshot(
        checkpoint=next_checkpoint,
        revision=3,
    )


async def test_concurrent_writers_have_one_winner_and_one_typed_conflict(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    token = ResumeToken(value="concurrent-cas-token")
    original = checkpoint()
    store = PostgreSQLCheckpointStore(postgres_pool)
    await store.save(resume_token=token, checkpoint=original)

    outcomes = await asyncio.gather(
        store.compare_and_swap(
            resume_token=token,
            checkpoint=changed(original, "writer-a"),
            expected_revision=1,
        ),
        store.compare_and_swap(
            resume_token=token,
            checkpoint=changed(original, "writer-b"),
            expected_revision=1,
        ),
        return_exceptions=True,
    )

    assert sum(isinstance(item, PostgreSQLCheckpointSnapshot) for item in outcomes) == 1
    assert (
        sum(isinstance(item, CheckpointConcurrencyConflictError) for item in outcomes)
        == 1
    )
    conflict = next(
        item
        for item in outcomes
        if isinstance(item, CheckpointConcurrencyConflictError)
    )
    assert conflict.expected_revision == 1
    assert conflict.actual_revision == 2
    persisted = await store.read(token)
    assert persisted.revision == 2
    assert persisted.checkpoint.metadata["writer"] in {"writer-a", "writer-b"}


async def test_stale_revision_does_not_overwrite_payload(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    token = ResumeToken(value="stale-cas-token")
    original = checkpoint()
    store = PostgreSQLCheckpointStore(postgres_pool)
    await store.save(resume_token=token, checkpoint=original)
    winner = await store.compare_and_swap(
        resume_token=token,
        checkpoint=changed(original, "winner"),
        expected_revision=1,
    )

    with pytest.raises(CheckpointConcurrencyConflictError) as captured:
        await store.compare_and_swap(
            resume_token=token,
            checkpoint=changed(original, "stale"),
            expected_revision=1,
        )

    assert captured.value.actual_revision == 2
    assert await store.read(token) == winner


async def test_consumed_and_unknown_checkpoints_cannot_be_updated(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    consumed_token = ResumeToken(value="consumed-cas-token")
    unknown_token = ResumeToken(value="unknown-cas-token")
    original = checkpoint()
    store = PostgreSQLCheckpointStore(postgres_pool)
    await store.save(resume_token=consumed_token, checkpoint=original)
    await store.consume(consumed_token)

    for token in (consumed_token, unknown_token):
        with pytest.raises(CheckpointNotFoundError):
            await store.compare_and_swap(
                resume_token=token,
                checkpoint=changed(original, "forbidden"),
                expected_revision=1,
            )


async def test_expired_checkpoint_cannot_be_reactivated(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    token = ResumeToken(value="expired-cas-token")
    original = checkpoint(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    store = PostgreSQLCheckpointStore(postgres_pool)
    await store.save(resume_token=token, checkpoint=original)

    with pytest.raises(CheckpointNotFoundError):
        await store.compare_and_swap(
            resume_token=token,
            checkpoint=changed(original, "forbidden"),
            expected_revision=1,
        )

    async with postgres_pool.connection() as connection:
        cursor = await connection.execute(
            "SELECT revision, payload FROM atlas_agent.checkpoints"
        )
        row = await cursor.fetchone()
    assert row is not None
    assert row[0] == 1
    assert row[1]["metadata"] == original.model_dump(mode="json")["metadata"]


async def test_identity_fields_cannot_be_changed(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    token = ResumeToken(value="identity-cas-token")
    original = checkpoint()
    store = PostgreSQLCheckpointStore(postgres_pool)
    await store.save(resume_token=token, checkpoint=original)
    invalid = original.model_copy(update={"execution_id": "other-execution"})

    with pytest.raises(InvalidCheckpointError, match="identidade"):
        await store.compare_and_swap(
            resume_token=token,
            checkpoint=invalid,
            expected_revision=1,
        )

    assert await store.read(token) == PostgreSQLCheckpointSnapshot(
        checkpoint=original,
        revision=1,
    )


async def test_database_failure_before_commit_rolls_back_payload_and_revision(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    token = ResumeToken(value="rollback-cas-token")
    original = checkpoint()
    store = PostgreSQLCheckpointStore(postgres_pool)
    await store.save(resume_token=token, checkpoint=original)
    async with postgres_pool.connection() as connection:
        await connection.execute(
            """
            CREATE OR REPLACE FUNCTION atlas_agent.ds003_reject_update()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'DS003 forced rollback';
            END;
            $$;
            CREATE TRIGGER ds003_reject_update
            BEFORE UPDATE ON atlas_agent.checkpoints
            FOR EACH ROW EXECUTE FUNCTION atlas_agent.ds003_reject_update();
            """
        )
    try:
        with pytest.raises(PostgreSQLCheckpointStoreError):
            await store.compare_and_swap(
                resume_token=token,
                checkpoint=changed(original, "rejected"),
                expected_revision=1,
            )
    finally:
        async with postgres_pool.connection() as connection:
            await connection.execute(
                """
                DROP TRIGGER IF EXISTS ds003_reject_update
                    ON atlas_agent.checkpoints;
                DROP FUNCTION IF EXISTS atlas_agent.ds003_reject_update();
                """
            )

    assert await store.read(token) == PostgreSQLCheckpointSnapshot(
        checkpoint=original,
        revision=1,
    )


async def test_update_and_consume_race_has_consistent_outcome(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    token = ResumeToken(value="update-consume-race-token")
    original = checkpoint()
    updated = changed(original, "race-writer")
    store = PostgreSQLCheckpointStore(postgres_pool)
    await store.save(resume_token=token, checkpoint=original)
    blocker = await postgres_pool.getconn()
    try:
        await blocker.execute("BEGIN")
        await blocker.execute(
            "SELECT 1 FROM atlas_agent.checkpoints WHERE token_digest = %s FOR UPDATE",
            (store._token_digest(token),),
        )
        update_task = asyncio.create_task(
            store.compare_and_swap(
                resume_token=token,
                checkpoint=updated,
                expected_revision=1,
            )
        )
        consume_task = asyncio.create_task(store.consume(token))
        await _wait_for_lock_waiters(postgres_pool, expected=2)
    finally:
        await blocker.rollback()
        await postgres_pool.putconn(blocker)

    update_outcome, consume_outcome = await asyncio.gather(
        update_task,
        consume_task,
        return_exceptions=True,
    )

    assert isinstance(consume_outcome, ExecutionCheckpoint)
    if isinstance(update_outcome, PostgreSQLCheckpointSnapshot):
        assert consume_outcome == updated
        assert update_outcome.revision == 2
    else:
        assert isinstance(update_outcome, CheckpointNotFoundError)
        assert consume_outcome == original
    with pytest.raises(CheckpointNotFoundError):
        await store.read(token)


async def test_cancelled_update_rolls_back_and_preserves_revision(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    token = ResumeToken(value="cancelled-cas-token")
    original = checkpoint()
    store = PostgreSQLCheckpointStore(postgres_pool)
    await store.save(resume_token=token, checkpoint=original)
    blocker = await postgres_pool.getconn()
    try:
        await blocker.execute("BEGIN")
        await blocker.execute(
            "SELECT 1 FROM atlas_agent.checkpoints WHERE token_digest = %s FOR UPDATE",
            (store._token_digest(token),),
        )
        update_task = asyncio.create_task(
            store.compare_and_swap(
                resume_token=token,
                checkpoint=changed(original, "cancelled"),
                expected_revision=1,
            )
        )
        await _wait_for_lock_waiters(postgres_pool, expected=1)
        update_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await update_task
    finally:
        await blocker.rollback()
        await postgres_pool.putconn(blocker)

    assert await store.read(token) == PostgreSQLCheckpointSnapshot(
        checkpoint=original,
        revision=1,
    )


async def test_update_survives_application_pool_restart() -> None:
    token = ResumeToken(value="restart-cas-token")
    original = checkpoint()
    updated = changed(original, "before-restart")
    first = pool()
    await first.open(wait=True)
    await PostgreSQLCheckpointMigrator(first).migrate()
    async with first.connection() as connection:
        await connection.execute("TRUNCATE atlas_agent.checkpoints")
    first_store = PostgreSQLCheckpointStore(first)
    await first_store.save(resume_token=token, checkpoint=original)
    await first_store.compare_and_swap(
        resume_token=token,
        checkpoint=updated,
        expected_revision=1,
    )
    await first.close()

    second = pool()
    await second.open(wait=True)
    try:
        assert await PostgreSQLCheckpointStore(second).read(
            token
        ) == PostgreSQLCheckpointSnapshot(checkpoint=updated, revision=2)
    finally:
        await second.close()


async def test_updates_to_distinct_checkpoints_do_not_interfere(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    first_token = ResumeToken(value="isolated-cas-token-a")
    second_token = ResumeToken(value="isolated-cas-token-b")
    original = checkpoint()
    store = PostgreSQLCheckpointStore(postgres_pool)
    await store.save(resume_token=first_token, checkpoint=original)
    await store.save(resume_token=second_token, checkpoint=original)

    first, second = await asyncio.gather(
        store.compare_and_swap(
            resume_token=first_token,
            checkpoint=changed(original, "writer-a"),
            expected_revision=1,
        ),
        store.compare_and_swap(
            resume_token=second_token,
            checkpoint=changed(original, "writer-b"),
            expected_revision=1,
        ),
    )

    assert first.revision == second.revision == 2
    assert first.checkpoint.metadata == {"writer": "writer-a"}
    assert second.checkpoint.metadata == {"writer": "writer-b"}


async def test_independent_processes_enforce_compare_and_swap(
    postgres_pool: AsyncConnectionPool[Any],
) -> None:
    assert DSN is not None
    token = ResumeToken(value="multiprocess-cas-token")
    original = checkpoint()
    store = PostgreSQLCheckpointStore(postgres_pool)
    await store.save(resume_token=token, checkpoint=original)
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(2)
    result_queue = context.Queue()
    processes = [
        context.Process(
            target=_process_writer,
            args=(
                DSN,
                token.value,
                changed(original, writer).model_dump_json(),
                barrier,
                result_queue,
            ),
        )
        for writer in ("process-a", "process-b")
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

    assert sorted(outcome[0] for outcome in outcomes) == ["conflict", "success"]
    assert await store.read(token) == PostgreSQLCheckpointSnapshot(
        checkpoint=(await store.read(token)).checkpoint,
        revision=2,
    )
