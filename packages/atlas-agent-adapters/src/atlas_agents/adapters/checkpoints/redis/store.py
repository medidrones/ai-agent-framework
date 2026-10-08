"""Redis implementation of the Atlas checkpoint persistence contract."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol, Self, cast
from uuid import uuid4

from redis.asyncio import Redis
from redis.exceptions import RedisError

from atlas_agents.adapters.checkpoints.redis.errors import (
    RedisCheckpointConcurrencyConflictError,
    RedisCheckpointOutcomeUnknownError,
    RedisCheckpointStoreError,
)
from atlas_agents.adapters.checkpoints.redis.keyspace import RedisCheckpointKeyspace
from atlas_agents.adapters.checkpoints.redis.models import (
    RedisCheckpointSnapshot,
    RedisConsumeReconciliation,
    RedisConsumeReconciliationStatus,
)
from atlas_agents.adapters.checkpoints.redis.scripts import (
    ACQUIRE_LEASE_SCRIPT,
    COMPARE_AND_SWAP_LEASED_SCRIPT,
    COMPARE_AND_SWAP_SCRIPT,
    CONSUME_LEASED_SCRIPT,
    CONSUME_SCRIPT,
    READ_SCRIPT,
    RECONCILE_SCRIPT,
    RELEASE_LEASE_SCRIPT,
    RENEW_LEASE_SCRIPT,
    SAVE_SCRIPT,
)
from atlas_agents.approvals import (
    CheckpointNotFoundError,
    CheckpointSaveError,
    InvalidCheckpointError,
    ResumeToken,
    UnsupportedCheckpointVersionError,
)
from atlas_agents.runtime import (
    CheckpointLease,
    CheckpointLeaseConflictError,
    CheckpointLeaseLostError,
    CheckpointLeaseNotFoundError,
    CheckpointRetentionPolicy,
    ExecutionCheckpoint,
)

_STORAGE_SCHEMA_VERSION = 1
_DEFAULT_RETENTION = timedelta(days=30)


class RedisCheckpointClient(Protocol):
    """Describe the async Redis operations required by the store."""

    async def eval(self, script: str, numkeys: int, *keys_and_args: object) -> object:
        """Evaluate one static server-side script."""
        ...

    async def ping(self) -> object:
        """Check connectivity."""
        ...

    async def aclose(self, close_connection_pool: bool | None = None) -> None:
        """Close the client and, when requested, its connection pool."""
        ...


class RedisCheckpointStore:
    """Persist versioned checkpoints through atomic single-key Redis scripts.

    The store guarantees at-most-once checkpoint consumption while its
    tombstone remains retained. It does not claim exactly-once execution for
    external side effects or durability beyond the configured Redis service.
    """

    def __init__(
        self,
        client: RedisCheckpointClient,
        *,
        namespace: str,
        retention: timedelta | None = None,
        retention_policy: CheckpointRetentionPolicy | None = None,
        token_hmac_key: bytes | None = None,
        owns_client: bool = False,
    ) -> None:
        """Configure persistence without taking implicit client ownership."""
        if retention is not None and retention <= timedelta(0):
            raise ValueError("A retenção do checkpoint deve ser positiva.")
        if retention is not None and retention_policy is not None:
            raise ValueError(
                "Use retention ou retention_policy, mas não ambas simultaneamente."
            )
        self._client = client
        self._keyspace = RedisCheckpointKeyspace(
            namespace, token_hmac_key=token_hmac_key
        )
        self._retention = retention
        self._retention_policy = retention_policy
        self._owns_client = owns_client
        self._closed = False

    @classmethod
    def from_url(
        cls,
        url: str,
        *,
        namespace: str,
        retention: timedelta | None = None,
        retention_policy: CheckpointRetentionPolicy | None = None,
        token_hmac_key: bytes | None = None,
        socket_timeout: float | None = None,
        max_connections: int | None = None,
    ) -> Self:
        """Create an owned async client from an explicit host-provided URL."""
        if not url or url != url.strip():
            raise ValueError("A URL do Redis deve ser explícita e não vazia.")
        client = Redis.from_url(
            url,
            decode_responses=False,
            socket_timeout=socket_timeout,
            max_connections=max_connections,
        )
        return cls(
            cast(RedisCheckpointClient, client),
            namespace=namespace,
            retention=retention,
            retention_policy=retention_policy,
            token_hmac_key=token_hmac_key,
            owns_client=True,
        )

    async def __aenter__(self) -> Self:
        """Return this explicitly configured store."""
        return self

    async def __aexit__(self, *_: object) -> None:
        """Close only resources created by this adapter."""
        await self.aclose()

    async def aclose(self) -> None:
        """Close the owned client exactly once and preserve injected clients."""
        if self._owns_client and not self._closed:
            await self._client.aclose(close_connection_pool=True)
        self._closed = True

    async def ping(self) -> None:
        """Validate that the configured client can reach Redis."""
        try:
            await self._client.ping()
        except RedisError as error:
            raise RedisCheckpointStoreError(
                "O armazenamento Redis não está disponível."
            ) from error

    async def save(
        self,
        *,
        resume_token: ResumeToken,
        checkpoint: ExecutionCheckpoint,
    ) -> None:
        """Create one checkpoint without overwriting active data or tombstones."""
        payload = self._serialize(checkpoint)
        expires_at = self._expires_at(checkpoint)
        retention_until = self._active_retention_until(expires_at)
        try:
            result = await self._client.eval(
                SAVE_SCRIPT,
                1,
                self._keyspace.checkpoint_key(resume_token),
                str(_STORAGE_SCHEMA_VERSION),
                str(checkpoint.checkpoint_version),
                checkpoint.execution_id,
                checkpoint.agent.agent_id,
                checkpoint.context.tenant_id or "",
                payload,
                self._payload_digest(payload),
                str(self._timestamp_ms(expires_at)),
                str(self._timestamp_ms(retention_until)),
                self._policy_version,
            )
        except RedisError as error:
            raise RedisCheckpointStoreError(
                "Não foi possível salvar o checkpoint no Redis."
            ) from error
        values = self._result(result)
        if self._code(values) != 1:
            raise CheckpointSaveError(
                "Já existe um checkpoint ou tombstone para o token informado."
            )

    async def read(self, resume_token: ResumeToken) -> RedisCheckpointSnapshot:
        """Read one active checkpoint without changing its storage revision."""
        values = await self._read_values(resume_token)
        checkpoint = self._deserialize(values[1])
        self._validate_identity(checkpoint, values[3], values[4], values[5])
        return RedisCheckpointSnapshot(
            checkpoint=checkpoint,
            revision=self._integer(values[2]),
        )

    async def compare_and_swap(
        self,
        *,
        resume_token: ResumeToken,
        checkpoint: ExecutionCheckpoint,
        expected_revision: int,
    ) -> RedisCheckpointSnapshot:
        """Replace one active checkpoint only at the expected Redis revision."""
        if expected_revision <= 0:
            raise ValueError("A revisão esperada deve ser positiva.")
        payload = self._serialize(checkpoint)
        expires_at = self._expires_at(checkpoint)
        retention_until = self._active_retention_until(expires_at)
        try:
            result = await self._client.eval(
                COMPARE_AND_SWAP_SCRIPT,
                1,
                self._keyspace.checkpoint_key(resume_token),
                str(_STORAGE_SCHEMA_VERSION),
                str(expected_revision),
                checkpoint.execution_id,
                checkpoint.agent.agent_id,
                checkpoint.context.tenant_id or "",
                str(checkpoint.checkpoint_version),
                payload,
                self._payload_digest(payload),
                str(self._timestamp_ms(expires_at)),
                str(self._timestamp_ms(retention_until)),
                self._policy_version,
            )
        except RedisError as error:
            raise RedisCheckpointStoreError(
                "Não foi possível atualizar o checkpoint no Redis."
            ) from error
        values = self._result(result)
        code = self._code(values)
        if code == 1:
            return RedisCheckpointSnapshot(
                checkpoint=self._deserialize(values[1]),
                revision=self._integer(values[2]),
            )
        if code == -3:
            raise RedisCheckpointConcurrencyConflictError(
                checkpoint_id=checkpoint.execution_id,
                expected_revision=expected_revision,
                actual_revision=self._integer(values[1]),
            )
        if code == -4:
            raise InvalidCheckpointError(
                "A identidade do checkpoint não pode ser alterada."
            )
        self._raise_read_failure(values)
        raise AssertionError("A classificação do compare-and-swap deve falhar.")

    async def consume(self, resume_token: ResumeToken) -> ExecutionCheckpoint:
        """Atomically consume one checkpoint and retain a replay tombstone."""
        return await self._consume(
            resume_token=resume_token,
            expected_revision=None,
            expected_digest=None,
        )

    async def consume_authorized(
        self,
        *,
        resume_token: ResumeToken,
        authorize: Callable[[ExecutionCheckpoint], None],
    ) -> ExecutionCheckpoint:
        """Consume only the exact revision accepted by a synchronous validator."""
        values = await self._read_values(resume_token)
        checkpoint = self._deserialize(values[1])
        self._validate_identity(checkpoint, values[3], values[4], values[5])
        authorize(checkpoint)
        return await self._consume(
            resume_token=resume_token,
            expected_revision=self._integer(values[2]),
            expected_digest=self._text(values[6]),
        )

    async def consume_authorized_identified(
        self,
        *,
        resume_token: ResumeToken,
        operation_id: str,
        authorize: Callable[[ExecutionCheckpoint], None],
    ) -> ExecutionCheckpoint:
        """Authorize and consume using a stable identifier for reconciliation."""
        self._validate_operation_id(operation_id)
        values = await self._read_values(resume_token)
        checkpoint = self._deserialize(values[1])
        self._validate_identity(checkpoint, values[3], values[4], values[5])
        authorize(checkpoint)
        return await self._consume(
            resume_token=resume_token,
            expected_revision=self._integer(values[2]),
            expected_digest=self._text(values[6]),
            operation_id=operation_id,
        )

    async def reconcile_consumption(
        self, *, resume_token: ResumeToken, operation_id: str
    ) -> RedisConsumeReconciliation:
        """Classify whether one identified consume attempt changed durable state."""
        self._validate_operation_id(operation_id)
        try:
            result = await self._client.eval(
                RECONCILE_SCRIPT,
                1,
                self._keyspace.checkpoint_key(resume_token),
                operation_id,
            )
        except RedisError as error:
            raise RedisCheckpointOutcomeUnknownError(
                "Não foi possível reconciliar o resultado do consumo Redis."
            ) from error
        values = self._result(result)
        state = self._text(values[1])
        if self._code(values) == 1:
            status = RedisConsumeReconciliationStatus.APPLIED
        elif state == "active":
            status = RedisConsumeReconciliationStatus.AVAILABLE
        elif state == "consumed":
            status = RedisConsumeReconciliationStatus.NOT_APPLIED
        else:
            status = RedisConsumeReconciliationStatus.UNKNOWN
        return RedisConsumeReconciliation(status=status, state=state)

    async def acquire_lease(
        self,
        *,
        resume_token: ResumeToken,
        owner_id: str,
        duration: timedelta,
    ) -> CheckpointLease:
        """Acquire token-scoped Redis ownership with a monotonic fencing token."""
        self._validate_owner(owner_id)
        duration_ms = self._positive_duration_ms(duration)
        try:
            result = await self._client.eval(
                ACQUIRE_LEASE_SCRIPT,
                1,
                self._keyspace.checkpoint_key(resume_token),
                str(_STORAGE_SCHEMA_VERSION),
                owner_id,
                str(duration_ms),
            )
        except RedisError as error:
            raise RedisCheckpointStoreError(
                "Não foi possível adquirir o lease no Redis."
            ) from error
        values = self._result(result)
        code = self._code(values)
        if code == 1:
            return self._lease(values)
        if code == -5:
            raise CheckpointLeaseConflictError(
                "O checkpoint possui um lease ativo de outro owner."
            )
        if code == -1:
            self._raise_read_failure(values)
        raise CheckpointLeaseNotFoundError(
            "O checkpoint não está disponível para aquisição de lease."
        )

    async def renew_lease(
        self,
        *,
        resume_token: ResumeToken,
        lease: CheckpointLease,
        duration: timedelta,
    ) -> CheckpointLease:
        """Renew only the current unexpired Redis fencing generation."""
        duration_ms = self._positive_duration_ms(duration)
        values = await self._lease_command(
            RENEW_LEASE_SCRIPT,
            resume_token,
            "renovar",
            lease.checkpoint_id,
            lease.owner_id,
            str(lease.fencing_token),
            str(duration_ms),
        )
        if self._code(values) != 1:
            raise CheckpointLeaseLostError(
                "O lease expirou, foi liberado ou pertence a outra geração."
            )
        return self._lease(values)

    async def release_lease(
        self, *, resume_token: ResumeToken, lease: CheckpointLease
    ) -> None:
        """Release the current Redis lease while retaining its fencing generation."""
        values = await self._lease_command(
            RELEASE_LEASE_SCRIPT,
            resume_token,
            "liberar",
            lease.checkpoint_id,
            lease.owner_id,
            str(lease.fencing_token),
        )
        if self._code(values) != 1:
            raise CheckpointLeaseLostError(
                "O lease expirou, foi liberado ou pertence a outra geração."
            )

    async def compare_and_swap_leased(
        self,
        *,
        resume_token: ResumeToken,
        checkpoint: ExecutionCheckpoint,
        expected_revision: int,
        lease: CheckpointLease,
    ) -> RedisCheckpointSnapshot:
        """Replace a checkpoint only for the current Redis fencing generation."""
        if lease.checkpoint_id != checkpoint.execution_id:
            raise CheckpointLeaseLostError(
                "O lease não pertence ao checkpoint que seria atualizado."
            )
        if expected_revision <= 0:
            raise ValueError("A revisão esperada deve ser positiva.")
        payload = self._serialize(checkpoint)
        expires_at = self._expires_at(checkpoint)
        retention_until = self._active_retention_until(expires_at)
        try:
            result = await self._client.eval(
                COMPARE_AND_SWAP_LEASED_SCRIPT,
                1,
                self._keyspace.checkpoint_key(resume_token),
                str(_STORAGE_SCHEMA_VERSION),
                str(expected_revision),
                checkpoint.execution_id,
                checkpoint.agent.agent_id,
                checkpoint.context.tenant_id or "",
                str(checkpoint.checkpoint_version),
                payload,
                self._payload_digest(payload),
                str(self._timestamp_ms(expires_at)),
                str(self._timestamp_ms(retention_until)),
                self._policy_version,
                lease.owner_id,
                str(lease.fencing_token),
            )
        except RedisError as error:
            raise RedisCheckpointStoreError(
                "Não foi possível atualizar o checkpoint protegido no Redis."
            ) from error
        values = self._result(result)
        code = self._code(values)
        if code == 1:
            return RedisCheckpointSnapshot(
                checkpoint=self._deserialize(values[1]),
                revision=self._integer(values[2]),
            )
        if code == -3:
            raise RedisCheckpointConcurrencyConflictError(
                checkpoint_id=checkpoint.execution_id,
                expected_revision=expected_revision,
                actual_revision=self._integer(values[1]),
            )
        if code == -6:
            raise CheckpointLeaseLostError(
                "O lease expirou, foi liberado ou pertence a outra geração."
            )
        if code == -4:
            raise InvalidCheckpointError(
                "A identidade do checkpoint não pode ser alterada."
            )
        self._raise_read_failure(values)
        raise AssertionError(
            "A classificação do compare-and-swap protegido deve falhar."
        )

    async def consume_authorized_leased(
        self,
        *,
        resume_token: ResumeToken,
        lease: CheckpointLease,
        authorize: Callable[[ExecutionCheckpoint], None],
    ) -> ExecutionCheckpoint:
        """Authorize and consume only for the current Redis fencing generation."""
        values = await self._read_values(resume_token)
        checkpoint = self._deserialize(values[1])
        self._validate_identity(checkpoint, values[3], values[4], values[5])
        if lease.checkpoint_id != checkpoint.execution_id:
            raise CheckpointLeaseLostError(
                "O lease não pertence ao checkpoint que seria consumido."
            )
        authorize(checkpoint)
        return await self._consume_leased(
            resume_token=resume_token,
            checkpoint=checkpoint,
            revision=self._integer(values[2]),
            digest=self._text(values[6]),
            lease=lease,
            operation_id=uuid4().hex,
        )

    async def _consume(
        self,
        *,
        resume_token: ResumeToken,
        expected_revision: int | None,
        expected_digest: str | None,
        operation_id: str | None = None,
    ) -> ExecutionCheckpoint:
        key = self._keyspace.checkpoint_key(resume_token)
        operation_id = operation_id or uuid4().hex
        try:
            result = await self._client.eval(
                CONSUME_SCRIPT,
                1,
                key,
                str(_STORAGE_SCHEMA_VERSION),
                "" if expected_revision is None else str(expected_revision),
                expected_digest or "",
                str(self._duration_ms(self._consumed_retention)),
                operation_id,
            )
        except RedisError as error:
            await self._raise_reconciled_failure(key, operation_id, error)
        values = self._result(result)
        code = self._code(values)
        if code == 1:
            return self._deserialize(values[1])
        if code == -3:
            raise RedisCheckpointConcurrencyConflictError(
                checkpoint_id="unknown",
                expected_revision=expected_revision or 0,
                actual_revision=self._integer(values[1]),
            )
        self._raise_read_failure(values)
        raise AssertionError("A classificação do consumo deve falhar.")

    async def _consume_leased(
        self,
        *,
        resume_token: ResumeToken,
        checkpoint: ExecutionCheckpoint,
        revision: int,
        digest: str,
        lease: CheckpointLease,
        operation_id: str,
    ) -> ExecutionCheckpoint:
        key = self._keyspace.checkpoint_key(resume_token)
        try:
            result = await self._client.eval(
                CONSUME_LEASED_SCRIPT,
                1,
                key,
                str(_STORAGE_SCHEMA_VERSION),
                str(revision),
                digest,
                str(self._duration_ms(self._consumed_retention)),
                "reserved",
                operation_id,
                checkpoint.execution_id,
                lease.owner_id,
                str(lease.fencing_token),
            )
        except RedisError as error:
            await self._raise_reconciled_failure(key, operation_id, error)
        values = self._result(result)
        code = self._code(values)
        if code == 1:
            return self._deserialize(values[1])
        if code == -3:
            raise RedisCheckpointConcurrencyConflictError(
                checkpoint_id=checkpoint.execution_id,
                expected_revision=revision,
                actual_revision=self._integer(values[1]),
            )
        if code == -6:
            raise CheckpointLeaseLostError(
                "O lease expirou, foi liberado ou pertence a outra geração."
            )
        self._raise_read_failure(values)
        raise AssertionError("A classificação do consumo protegido deve falhar.")

    async def _lease_command(
        self,
        script: str,
        resume_token: ResumeToken,
        action: str,
        *arguments: object,
    ) -> list[object]:
        try:
            result = await self._client.eval(
                script,
                1,
                self._keyspace.checkpoint_key(resume_token),
                *arguments,
            )
        except RedisError as error:
            raise RedisCheckpointStoreError(
                f"Não foi possível {action} o lease no Redis."
            ) from error
        return self._result(result)

    async def _read_values(self, resume_token: ResumeToken) -> list[object]:
        try:
            result = await self._client.eval(
                READ_SCRIPT,
                1,
                self._keyspace.checkpoint_key(resume_token),
                str(_STORAGE_SCHEMA_VERSION),
            )
        except RedisError as error:
            raise RedisCheckpointStoreError(
                "Não foi possível ler o checkpoint no Redis."
            ) from error
        values = self._result(result)
        if self._code(values) != 1:
            self._raise_read_failure(values)
        if len(values) < 7:
            raise InvalidCheckpointError(
                "O checkpoint armazenado não possui um envelope válido."
            )
        return values

    async def _raise_reconciled_failure(
        self, key: str, operation_id: str, cause: RedisError
    ) -> None:
        try:
            result = await self._client.eval(RECONCILE_SCRIPT, 1, key, operation_id)
        except RedisError:
            raise RedisCheckpointOutcomeUnknownError(
                "O resultado do consumo Redis é desconhecido; reconcilie antes "
                "de tentar novamente."
            ) from cause
        if self._code(self._result(result)) == 1:
            raise RedisCheckpointOutcomeUnknownError(
                "O consumo foi aplicado no Redis, mas a resposta original foi perdida."
            ) from cause
        raise RedisCheckpointStoreError(
            "Não foi possível consumir o checkpoint no Redis."
        ) from cause

    @staticmethod
    def _result(value: object) -> list[object]:
        if not isinstance(value, (list, tuple)) or len(value) < 2:
            raise InvalidCheckpointError(
                "O Redis retornou um resultado incompatível com o contrato."
            )
        return list(value)

    @classmethod
    def _raise_read_failure(cls, values: list[object]) -> None:
        code = cls._code(values)
        if code == -1:
            raise UnsupportedCheckpointVersionError(
                "A versão do envelope Redis não é suportada."
            )
        if code == -2:
            raise InvalidCheckpointError(
                "O checkpoint armazenado não possui um payload válido."
            )
        raise CheckpointNotFoundError(
            "O token é desconhecido, expirou ou já foi consumido."
        )

    @staticmethod
    def _code(values: list[object]) -> int:
        return RedisCheckpointStore._integer(values[0])

    @staticmethod
    def _integer(value: object) -> int:
        if isinstance(value, bytes):
            value = value.decode("ascii")
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise InvalidCheckpointError("O envelope Redis contém um número inválido.")
        try:
            return int(value)
        except ValueError as error:
            raise InvalidCheckpointError(
                "O envelope Redis contém um número inválido."
            ) from error

    @staticmethod
    def _text(value: object) -> str:
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError as error:
                raise InvalidCheckpointError(
                    "O envelope Redis contém texto inválido."
                ) from error
        if not isinstance(value, str):
            raise InvalidCheckpointError("O envelope Redis contém texto inválido.")
        return value

    @classmethod
    def _deserialize(cls, payload: object) -> ExecutionCheckpoint:
        try:
            decoded = json.loads(cls._text(payload))
            return ExecutionCheckpoint.model_validate(decoded)
        except InvalidCheckpointError:
            raise
        except Exception as error:
            raise InvalidCheckpointError(
                "O checkpoint armazenado não possui um payload válido."
            ) from error

    @staticmethod
    def _serialize(checkpoint: ExecutionCheckpoint) -> str:
        return json.dumps(
            checkpoint.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def _payload_digest(payload: str) -> str:
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @classmethod
    def _validate_identity(
        cls,
        checkpoint: ExecutionCheckpoint,
        execution_id: object,
        agent_id: object,
        tenant_id: object,
    ) -> None:
        if (
            checkpoint.execution_id != cls._text(execution_id)
            or checkpoint.agent.agent_id != cls._text(agent_id)
            or (checkpoint.context.tenant_id or "") != cls._text(tenant_id)
        ):
            raise InvalidCheckpointError(
                "A identidade interna do checkpoint não corresponde à chave solicitada."
            )

    def _expires_at(self, checkpoint: ExecutionCheckpoint) -> datetime | None:
        candidates = [checkpoint.pending_approval.expires_at]
        if self._retention is not None:
            candidates.append(checkpoint.updated_at + self._retention)
        if self._retention_policy is not None:
            candidates.append(checkpoint.updated_at + self._retention_policy.hitl_ttl)
        return min((value for value in candidates if value is not None), default=None)

    def _active_retention_until(self, expires_at: datetime | None) -> datetime | None:
        if expires_at is None:
            return None
        retention = (
            self._retention_policy.expired_retention
            if self._retention_policy is not None
            else _DEFAULT_RETENTION
        )
        return expires_at + retention

    @property
    def _consumed_retention(self) -> timedelta:
        if self._retention_policy is not None:
            return self._retention_policy.consumed_retention
        return _DEFAULT_RETENTION

    @property
    def _policy_version(self) -> str:
        if self._retention_policy is not None:
            return self._retention_policy.policy_version
        return "compatibility-1x"

    @staticmethod
    def _timestamp_ms(value: datetime | None) -> int:
        if value is None:
            return 0
        return int(value.astimezone(UTC).timestamp() * 1000)

    @staticmethod
    def _duration_ms(value: timedelta) -> int:
        return max(1, int(value.total_seconds() * 1000))

    @classmethod
    def _positive_duration_ms(cls, value: timedelta) -> int:
        if value <= timedelta(0):
            raise ValueError("A duração do lease deve ser positiva.")
        return cls._duration_ms(value)

    @staticmethod
    def _validate_owner(value: str) -> None:
        if not value or value != value.strip() or len(value) > 128:
            raise ValueError("O identificador do owner deve ser explícito e válido.")

    @staticmethod
    def _validate_operation_id(value: str) -> None:
        if (
            not value
            or value != value.strip()
            or len(value) > 128
            or any(
                not (char.isascii() and (char.isalnum() or char in "-_."))
                for char in value
            )
        ):
            raise ValueError("O identificador da operação de consumo é inválido.")

    @classmethod
    def _lease(cls, values: list[object]) -> CheckpointLease:
        if len(values) < 6:
            raise InvalidCheckpointError(
                "O Redis retornou um lease incompatível com o contrato."
            )
        return CheckpointLease(
            checkpoint_id=cls._text(values[1]),
            owner_id=cls._text(values[2]),
            fencing_token=cls._integer(values[3]),
            acquired_at=datetime.fromtimestamp(cls._integer(values[4]) / 1000, UTC),
            expires_at=datetime.fromtimestamp(cls._integer(values[5]) / 1000, UTC),
        )
