from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError
from redis.exceptions import ConnectionError as RedisConnectionError

from atlas_agents import (
    CheckpointLeaseLostError,
    CheckpointNotFoundError,
    CheckpointRetentionPolicy,
    CheckpointSaveError,
    ExecutionCheckpoint,
    InvalidCheckpointError,
    ResumeToken,
    UnsupportedCheckpointVersionError,
)
from atlas_agents.adapters.checkpoints.redis import (
    RedisCheckpointConcurrencyConflictError,
    RedisCheckpointKeyspace,
    RedisCheckpointOutcomeUnknownError,
    RedisCheckpointSnapshot,
    RedisCheckpointStore,
    RedisCheckpointStoreError,
    RedisConsumeReconciliationStatus,
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


def encoded(value: ExecutionCheckpoint | None = None) -> bytes:
    payload = value or checkpoint()
    return RedisCheckpointStore._serialize(payload).encode()


class FakeRedis:
    def __init__(self, *responses: object) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[object, ...]] = []
        self.close_calls = 0
        self.ping_error: BaseException | None = None

    async def eval(self, script: str, numkeys: int, *keys_and_args: object) -> object:
        self.calls.append((script, numkeys, *keys_and_args))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    async def ping(self) -> object:
        if self.ping_error is not None:
            raise self.ping_error
        return True

    async def aclose(self, close_connection_pool: bool | None = None) -> None:
        assert close_connection_pool is True
        self.close_calls += 1


def store(
    client: FakeRedis,
    *,
    retention: timedelta | None = None,
    retention_policy: CheckpointRetentionPolicy | None = None,
    owns_client: bool = False,
) -> RedisCheckpointStore:
    return RedisCheckpointStore(
        client,
        namespace="tenant-a:production",
        retention=retention,
        retention_policy=retention_policy,
        owns_client=owns_client,
    )


def read_result(value: ExecutionCheckpoint | None = None) -> list[object]:
    current = value or checkpoint()
    payload = RedisCheckpointStore._serialize(current)
    return [
        1,
        payload.encode(),
        b"1",
        current.execution_id.encode(),
        current.agent.agent_id.encode(),
        (current.context.tenant_id or "").encode(),
        RedisCheckpointStore._payload_digest(payload).encode(),
    ]


def test_keyspace_is_opaque_safe_and_namespace_isolated() -> None:
    token = ResumeToken(value="sensitive/resume:{token}")
    first = RedisCheckpointKeyspace("tenant-a")
    second = RedisCheckpointKeyspace("tenant-b")
    protected = RedisCheckpointKeyspace("tenant-a", token_hmac_key=b"k" * 32)

    first_key = first.checkpoint_key(token)
    assert token.value not in first_key
    assert "tenant-a" not in first_key
    assert first_key != second.checkpoint_key(token)
    assert first_key != protected.checkpoint_key(token)
    assert first_key.count("{") == first_key.count("}") == 1


@pytest.mark.parametrize("namespace", ["", " leading", "trailing ", "x\x00y"])
def test_invalid_namespace_is_rejected(namespace: str) -> None:
    with pytest.raises(ValueError, match="namespace"):
        RedisCheckpointKeyspace(namespace)


def test_invalid_hmac_key_and_retention_are_rejected() -> None:
    with pytest.raises(ValueError, match="HMAC"):
        RedisCheckpointKeyspace("namespace", token_hmac_key=b"short")
    with pytest.raises(ValueError, match="retenção"):
        store(FakeRedis(), retention=timedelta(0))
    with pytest.raises(ValueError, match="simultaneamente"):
        store(
            FakeRedis(),
            retention=timedelta(days=1),
            retention_policy=CheckpointRetentionPolicy(
                policy_version="v1",
                active_ttl=timedelta(days=1),
                hitl_ttl=timedelta(days=1),
                consumed_retention=timedelta(days=1),
                expired_retention=timedelta(days=1),
                terminal_retention=timedelta(days=1),
                recovery_retention=timedelta(days=1),
            ),
        )


async def test_save_uses_one_opaque_key_and_rejects_overwrite() -> None:
    client = FakeRedis([1, b"saved"], [0, b"exists"])
    value = store(client)
    token = ResumeToken(value="never-visible")

    await value.save(resume_token=token, checkpoint=checkpoint())
    with pytest.raises(CheckpointSaveError):
        await value.save(resume_token=token, checkpoint=checkpoint())

    assert all(call[1] == 1 for call in client.calls)
    assert token.value not in str(client.calls)


async def test_read_validates_payload_and_identity() -> None:
    expected = checkpoint()
    value = store(FakeRedis(read_result(expected)))

    snapshot = await value.read(ResumeToken(value="read"))

    assert snapshot == RedisCheckpointSnapshot(checkpoint=expected, revision=1)


@pytest.mark.parametrize(
    ("response", "error"),
    [
        ([0, b"missing"], CheckpointNotFoundError),
        ([-1, b"99"], UnsupportedCheckpointVersionError),
        ([-2, b"corrupted"], InvalidCheckpointError),
        ([1, b"not-json", b"1", b"e", b"a", b"", b"d"], InvalidCheckpointError),
    ],
)
async def test_read_rejects_invalid_storage(
    response: list[object], error: type[Exception]
) -> None:
    with pytest.raises(error):
        await store(FakeRedis(response)).read(ResumeToken(value="read"))


async def test_read_rejects_identifier_mismatch() -> None:
    response = read_result()
    response[3] = b"different-execution"
    with pytest.raises(InvalidCheckpointError, match="identidade interna"):
        await store(FakeRedis(response)).read(ResumeToken(value="read"))


async def test_compare_and_swap_returns_new_revision() -> None:
    expected = checkpoint()
    value = store(FakeRedis([1, encoded(expected), b"2"]))

    snapshot = await value.compare_and_swap(
        resume_token=ResumeToken(value="cas"),
        checkpoint=expected,
        expected_revision=1,
    )

    assert snapshot.revision == 2
    assert snapshot.checkpoint == expected


async def test_compare_and_swap_classifies_conflict_and_identity() -> None:
    expected = checkpoint()
    conflict = store(FakeRedis([-3, b"4"]))
    with pytest.raises(RedisCheckpointConcurrencyConflictError) as captured:
        await conflict.compare_and_swap(
            resume_token=ResumeToken(value="cas"),
            checkpoint=expected,
            expected_revision=3,
        )
    assert captured.value.actual_revision == 4
    assert "cas" not in str(captured.value)

    identity = store(FakeRedis([-4, b"identity"]))
    with pytest.raises(InvalidCheckpointError, match="identidade"):
        await identity.compare_and_swap(
            resume_token=ResumeToken(value="cas"),
            checkpoint=expected,
            expected_revision=1,
        )


async def test_compare_and_swap_rejects_non_positive_revision() -> None:
    with pytest.raises(ValueError, match="revisão esperada"):
        await store(FakeRedis()).compare_and_swap(
            resume_token=ResumeToken(value="cas"),
            checkpoint=checkpoint(),
            expected_revision=0,
        )


async def test_consume_returns_payload_and_classifies_replay() -> None:
    expected = checkpoint()
    value = store(FakeRedis([1, encoded(expected)], [0, b"consumed"]))

    assert await value.consume(ResumeToken(value="consume")) == expected
    with pytest.raises(CheckpointNotFoundError):
        await value.consume(ResumeToken(value="consume"))


async def test_authorization_failure_does_not_start_consume() -> None:
    client = FakeRedis(read_result())
    value = store(client)

    def reject(_: ExecutionCheckpoint) -> None:
        raise PermissionError("rejected")

    with pytest.raises(PermissionError):
        await value.consume_authorized(
            resume_token=ResumeToken(value="authorized"), authorize=reject
        )
    assert len(client.calls) == 1


async def test_authorized_consume_is_bound_to_revision_and_digest() -> None:
    expected = checkpoint()
    client = FakeRedis(read_result(expected), [1, encoded(expected)])
    value = store(client)

    assert (
        await value.consume_authorized(
            resume_token=ResumeToken(value="authorized"), authorize=lambda _: None
        )
        == expected
    )
    consume_args = client.calls[1]
    assert b"1" not in consume_args
    assert "1" in consume_args
    assert (
        RedisCheckpointStore._payload_digest(RedisCheckpointStore._serialize(expected))
        in consume_args
    )


async def test_connection_errors_are_safe_and_cancellation_is_preserved() -> None:
    failed = store(FakeRedis(RedisConnectionError("redis://user:secret@host")))
    with pytest.raises(RedisCheckpointStoreError) as captured:
        await failed.save(
            resume_token=ResumeToken(value="secret-token"), checkpoint=checkpoint()
        )
    assert "secret" not in str(captured.value)
    assert "redis://" not in str(captured.value)

    cancelled = store(FakeRedis(asyncio.CancelledError()))
    with pytest.raises(asyncio.CancelledError):
        await cancelled.read(ResumeToken(value="cancel"))


async def test_ambiguous_consume_is_reconciled_to_typed_outcome() -> None:
    applied = store(FakeRedis(RedisConnectionError("lost"), [1, b"applied"]))
    with pytest.raises(RedisCheckpointOutcomeUnknownError, match="foi aplicado"):
        await applied.consume(ResumeToken(value="ambiguous"))

    unresolved = store(
        FakeRedis(RedisConnectionError("lost"), RedisConnectionError("lost again"))
    )
    with pytest.raises(RedisCheckpointOutcomeUnknownError, match="desconhecido"):
        await unresolved.consume(ResumeToken(value="ambiguous"))


async def test_client_ownership_is_explicit_and_idempotent() -> None:
    injected = FakeRedis()
    value = store(injected)
    await value.aclose()
    assert injected.close_calls == 0

    owned = FakeRedis()
    value = store(owned, owns_client=True)
    await value.aclose()
    await value.aclose()
    assert owned.close_calls == 1


async def test_ping_wraps_only_redis_failures() -> None:
    client = FakeRedis()
    await store(client).ping()
    client.ping_error = RedisConnectionError("redis://secret")
    with pytest.raises(RedisCheckpointStoreError, match="não está disponível"):
        await store(client).ping()


async def test_owned_store_async_context_closes_client() -> None:
    client = FakeRedis()
    value = store(client, owns_client=True)

    async with value as entered:
        assert entered is value

    assert client.close_calls == 1


def test_from_url_rejects_empty_or_padded_values() -> None:
    for url in ("", " redis://localhost"):
        with pytest.raises(ValueError, match="URL do Redis"):
            RedisCheckpointStore.from_url(url, namespace="test")


async def test_cas_and_read_wrap_redis_failures() -> None:
    error = RedisConnectionError("redis://user:secret@host")
    with pytest.raises(RedisCheckpointStoreError, match="atualizar"):
        await store(FakeRedis(error)).compare_and_swap(
            resume_token=ResumeToken(value="cas"),
            checkpoint=checkpoint(),
            expected_revision=1,
        )
    with pytest.raises(RedisCheckpointStoreError, match="ler"):
        await store(FakeRedis(error)).read(ResumeToken(value="read"))


async def test_consume_conflict_and_unapplied_reconciliation_are_typed() -> None:
    with pytest.raises(RedisCheckpointConcurrencyConflictError):
        await store(FakeRedis(read_result(), [-3, b"2"])).consume_authorized(
            resume_token=ResumeToken(value="consume"),
            authorize=lambda _: None,
        )

    value = store(FakeRedis(RedisConnectionError("lost"), [0, b"active"]))
    with pytest.raises(RedisCheckpointStoreError, match="consumir"):
        await value.consume(ResumeToken(value="consume"))


async def test_short_read_envelope_is_rejected() -> None:
    with pytest.raises(InvalidCheckpointError, match="envelope válido"):
        await store(FakeRedis([1, b"payload"])).read(ResumeToken(value="short"))


@pytest.mark.parametrize(
    "value",
    [None, True, object(), "not-a-number"],
)
def test_invalid_numeric_envelope_values_are_rejected(value: object) -> None:
    with pytest.raises(InvalidCheckpointError, match="número inválido"):
        RedisCheckpointStore._integer(value)


@pytest.mark.parametrize("value", [object(), b"\xff"])
def test_invalid_text_envelope_values_are_rejected(value: object) -> None:
    with pytest.raises(InvalidCheckpointError, match="texto inválido"):
        RedisCheckpointStore._text(value)


def test_malformed_redis_result_is_rejected() -> None:
    for value in (None, [], [1], "invalid"):
        with pytest.raises(InvalidCheckpointError, match="resultado incompatível"):
            RedisCheckpointStore._result(value)


def test_snapshot_is_immutable() -> None:
    value = RedisCheckpointSnapshot(checkpoint=checkpoint(), revision=1)
    with pytest.raises(ValidationError):
        value.revision = 2


def test_serialization_matches_the_certified_logical_representation() -> None:
    expected = checkpoint()
    serialized = RedisCheckpointStore._serialize(expected)

    assert json.loads(serialized) == expected.model_dump(mode="json")
    assert "pickle" not in serialized.casefold()


def test_expiration_and_retention_boundaries_are_separate() -> None:
    policy = CheckpointRetentionPolicy(
        policy_version="redis-v1",
        active_ttl=timedelta(days=2),
        hitl_ttl=timedelta(days=1),
        consumed_retention=timedelta(days=7),
        expired_retention=timedelta(days=3),
        terminal_retention=timedelta(days=4),
        recovery_retention=timedelta(days=5),
    )
    expected = checkpoint(expires_at=datetime(2026, 1, 3, tzinfo=UTC))
    value = store(FakeRedis(), retention_policy=policy)

    expires_at = value._expires_at(expected)
    assert expires_at == expected.updated_at + timedelta(days=1)
    assert value._active_retention_until(expires_at) == expires_at + timedelta(days=3)
    assert value._consumed_retention == timedelta(days=7)


def test_leased_capability_is_available_after_redis_fencing_certification() -> None:
    value = store(FakeRedis())

    assert hasattr(value, "consume_authorized_leased")
    assert hasattr(value, "compare_and_swap_leased")


async def test_identified_consume_and_reconciliation_are_operation_scoped() -> None:
    expected = checkpoint()
    client = FakeRedis(
        read_result(expected),
        [1, encoded(expected)],
        [1, b"applied"],
        [0, b"consumed"],
        [0, b"active"],
    )
    value = store(client)
    token = ResumeToken(value="identified")

    assert (
        await value.consume_authorized_identified(
            resume_token=token,
            operation_id="resume-attempt-1",
            authorize=lambda _: None,
        )
        == expected
    )
    own = await value.reconcile_consumption(
        resume_token=token, operation_id="resume-attempt-1"
    )
    other = await value.reconcile_consumption(
        resume_token=token, operation_id="resume-attempt-2"
    )
    available = await value.reconcile_consumption(
        resume_token=token, operation_id="resume-attempt-3"
    )

    assert own.status is RedisConsumeReconciliationStatus.APPLIED
    assert other.status is RedisConsumeReconciliationStatus.NOT_APPLIED
    assert available.status is RedisConsumeReconciliationStatus.AVAILABLE


def test_invalid_consume_operation_identifier_is_rejected() -> None:
    value = store(FakeRedis())
    for operation_id in ("", " padded", "contains:secret", "x" * 129):
        with pytest.raises(ValueError, match="operação de consumo"):
            value._validate_operation_id(operation_id)


async def test_redis_lease_lifecycle_and_stale_generation_are_typed() -> None:
    expected = checkpoint()
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    lease_result = [
        1,
        expected.execution_id.encode(),
        b"worker-a",
        b"1",
        str(now_ms).encode(),
        str(now_ms + 30_000).encode(),
    ]
    value = store(FakeRedis(lease_result, [-6, b"lost"]))
    token = ResumeToken(value="lease")

    lease = await value.acquire_lease(
        resume_token=token,
        owner_id="worker-a",
        duration=timedelta(seconds=30),
    )
    assert lease.checkpoint_id == expected.execution_id
    assert lease.fencing_token == 1

    with pytest.raises(CheckpointLeaseLostError):
        await value.renew_lease(
            resume_token=token,
            lease=lease,
            duration=timedelta(seconds=30),
        )
