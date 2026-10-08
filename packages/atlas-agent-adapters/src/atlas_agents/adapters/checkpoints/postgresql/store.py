"""Transactional PostgreSQL implementation of the checkpoint store contract."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, Final

from psycopg import AsyncConnection, DatabaseError, errors
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool, PoolTimeout

from atlas_agents.adapters.checkpoints.postgresql.errors import (
    CheckpointConcurrencyConflictError,
    PostgreSQLCheckpointStoreError,
)
from atlas_agents.adapters.checkpoints.postgresql.models import (
    PostgreSQLCheckpointSnapshot,
)
from atlas_agents.approvals import (
    CheckpointNotFoundError,
    CheckpointSaveError,
    InvalidCheckpointError,
    ResumeToken,
)
from atlas_agents.runtime import (
    CheckpointLease,
    CheckpointLeaseLostError,
    CheckpointRetentionPolicy,
    ExecutionCheckpoint,
)

_INSERT_SQL: Final = """
INSERT INTO atlas_agent.checkpoints (
    token_digest,
    checkpoint_version,
    execution_id,
    agent_id,
    tenant_id,
    payload,
    checkpoint_created_at,
    expires_at,
    retention_class,
    retention_until,
    retention_policy_version
)
SELECT %s, %s, %s, %s, %s, %s, %s, %s,
       'waiting_for_approval', %s, %s
WHERE NOT EXISTS (
    SELECT 1 FROM atlas_agent.checkpoint_tombstones WHERE token_digest = %s
)
"""

_CONSUME_SQL: Final = """
WITH consumed AS (
    DELETE FROM atlas_agent.checkpoints
    WHERE token_digest = %s
      AND (expires_at IS NULL OR expires_at > clock_timestamp())
    RETURNING token_digest, execution_id, agent_id, tenant_id, payload
), tombstone AS (
    INSERT INTO atlas_agent.checkpoint_tombstones (
        token_digest, execution_id, agent_id, tenant_id,
        retention_until, retention_policy_version, fencing_token
    )
    SELECT token_digest, execution_id, agent_id, tenant_id,
           clock_timestamp() + %s, %s, NULL
    FROM consumed
)
SELECT payload FROM consumed
"""

_READ_SQL: Final = """
SELECT payload, revision
FROM atlas_agent.checkpoints
WHERE token_digest = %s
  AND (expires_at IS NULL OR expires_at > clock_timestamp())
"""

_COMPARE_AND_SWAP_SQL: Final = """
UPDATE atlas_agent.checkpoints
SET checkpoint_version = %s,
    payload = %s,
    expires_at = %s,
    retention_until = %s,
    retention_policy_version = %s,
    modified_at = CURRENT_TIMESTAMP,
    revision = revision + 1
WHERE token_digest = %s
  AND revision = %s
  AND execution_id = %s
  AND agent_id = %s
  AND tenant_id IS NOT DISTINCT FROM %s
  AND (expires_at IS NULL OR expires_at > clock_timestamp())
RETURNING payload, revision
"""

_COMPARE_AND_SWAP_LEASED_SQL: Final = """
UPDATE atlas_agent.checkpoints AS checkpoint
SET checkpoint_version = %s,
    payload = %s,
    expires_at = %s,
    retention_until = %s,
    retention_policy_version = %s,
    modified_at = CURRENT_TIMESTAMP,
    revision = revision + 1
WHERE checkpoint.token_digest = %s
  AND checkpoint.revision = %s
  AND checkpoint.execution_id = %s
  AND checkpoint.agent_id = %s
  AND checkpoint.tenant_id IS NOT DISTINCT FROM %s
  AND (checkpoint.expires_at IS NULL OR checkpoint.expires_at > clock_timestamp())
  AND EXISTS (
      SELECT 1
      FROM atlas_agent.checkpoint_leases AS lease
      WHERE lease.checkpoint_id = checkpoint.execution_id
        AND lease.checkpoint_id = %s
        AND lease.owner_id = %s
        AND lease.fencing_token = %s
        AND lease.expires_at > clock_timestamp()
  )
RETURNING checkpoint.payload, checkpoint.revision
"""

_CONSUME_AUTHORIZED_LEASED_SQL: Final = """
WITH consumed AS (
    DELETE FROM atlas_agent.checkpoints AS checkpoint
    WHERE checkpoint.token_digest = %s
      AND (checkpoint.expires_at IS NULL OR checkpoint.expires_at > clock_timestamp())
      AND EXISTS (
          SELECT 1
          FROM atlas_agent.checkpoint_leases AS lease
          WHERE lease.checkpoint_id = checkpoint.execution_id
            AND lease.checkpoint_id = %s
            AND lease.owner_id = %s
            AND lease.fencing_token = %s
            AND lease.expires_at > clock_timestamp()
      )
    RETURNING checkpoint.token_digest, checkpoint.execution_id,
              checkpoint.agent_id, checkpoint.tenant_id, checkpoint.payload
), tombstone AS (
    INSERT INTO atlas_agent.checkpoint_tombstones (
        token_digest, execution_id, agent_id, tenant_id,
        retention_until, retention_policy_version, fencing_token
    )
    SELECT token_digest, execution_id, agent_id, tenant_id,
           clock_timestamp() + %s, %s, %s
    FROM consumed
)
SELECT payload FROM consumed
"""

_CLEAR_CONSUMED_LEASE_SQL: Final = """
UPDATE atlas_agent.checkpoint_leases
SET owner_id = NULL, acquired_at = NULL, expires_at = NULL
WHERE checkpoint_id = %s
  AND owner_id = %s
  AND fencing_token = %s
"""

_LEASE_VALID_SQL: Final = """
SELECT EXISTS (
    SELECT 1
    FROM atlas_agent.checkpoint_leases
    WHERE checkpoint_id = %s
      AND owner_id = %s
      AND fencing_token = %s
      AND expires_at > clock_timestamp()
)
"""

_INSPECT_CONFLICT_SQL: Final = """
SELECT execution_id,
       agent_id,
       tenant_id,
       revision,
       (expires_at IS NOT NULL AND expires_at <= clock_timestamp()) AS expired
FROM atlas_agent.checkpoints
WHERE token_digest = %s
"""

_PURGE_SQL: Final = """
WITH expired AS (
    SELECT token_digest
    FROM atlas_agent.checkpoints
    WHERE expires_at IS NOT NULL
      AND expires_at <= clock_timestamp()
    ORDER BY expires_at
    LIMIT %s
    FOR UPDATE SKIP LOCKED
)
DELETE FROM atlas_agent.checkpoints AS checkpoint
USING expired
WHERE checkpoint.token_digest = expired.token_digest
"""


class PostgreSQLCheckpointStore:
    """Persist and atomically consume checkpoints using a caller-owned pool.

    The store guarantees at-most-once resume authorization. It does not claim
    exactly-once execution for external tool side effects.
    """

    def __init__(
        self,
        pool: AsyncConnectionPool[Any],
        *,
        retention: timedelta | None = None,
        retention_policy: CheckpointRetentionPolicy | None = None,
        token_hmac_key: bytes | None = None,
    ) -> None:
        """Configure persistence without opening or closing the supplied pool."""
        if retention is not None and retention <= timedelta(0):
            raise ValueError("A retenção do checkpoint deve ser positiva.")
        if retention is not None and retention_policy is not None:
            raise ValueError(
                "Use retention ou retention_policy, mas não ambas simultaneamente."
            )
        if token_hmac_key is not None and len(token_hmac_key) < 32:
            raise ValueError("A chave HMAC do token deve possuir ao menos 32 bytes.")
        self._pool = pool
        self._retention = retention
        self._retention_policy = retention_policy
        self._token_hmac_key = token_hmac_key

    async def save(
        self,
        *,
        resume_token: ResumeToken,
        checkpoint: ExecutionCheckpoint,
    ) -> None:
        """Create one checkpoint without overwriting an existing token."""
        expires_at = self._expires_at(checkpoint)
        retention_until = self._retention_until(expires_at)
        try:
            async with self._pool.connection() as connection:
                token_digest = self._token_digest(resume_token)
                cursor = await connection.execute(
                    _INSERT_SQL,
                    (
                        token_digest,
                        checkpoint.checkpoint_version,
                        checkpoint.execution_id,
                        checkpoint.agent.agent_id,
                        checkpoint.context.tenant_id,
                        Jsonb(checkpoint.model_dump(mode="json")),
                        checkpoint.created_at,
                        expires_at,
                        retention_until,
                        self._policy_version,
                        token_digest,
                    ),
                )
                if cursor.rowcount != 1:
                    raise CheckpointSaveError(
                        "O token já foi consumido e permanece protegido contra replay."
                    )
        except errors.UniqueViolation as error:
            raise CheckpointSaveError(
                "Já existe um checkpoint para o token informado."
            ) from error
        except (DatabaseError, PoolTimeout) as error:
            raise PostgreSQLCheckpointStoreError(
                "Não foi possível salvar o checkpoint no PostgreSQL."
            ) from error

    async def consume(self, resume_token: ResumeToken) -> ExecutionCheckpoint:
        """Atomically delete and return one non-expired checkpoint."""
        try:
            async with self._pool.connection() as connection:
                cursor = await connection.execute(
                    _CONSUME_SQL,
                    (
                        self._token_digest(resume_token),
                        self._consumed_retention,
                        self._policy_version,
                    ),
                )
                row = await cursor.fetchone()
        except (DatabaseError, PoolTimeout) as error:
            raise PostgreSQLCheckpointStoreError(
                "Não foi possível consumir o checkpoint no PostgreSQL."
            ) from error
        if row is None:
            raise CheckpointNotFoundError(
                "O token é desconhecido, expirou ou já foi consumido."
            )
        try:
            return ExecutionCheckpoint.model_validate(row[0])
        except Exception as error:
            raise InvalidCheckpointError(
                "O checkpoint armazenado não possui um payload válido."
            ) from error

    async def consume_authorized(
        self,
        *,
        resume_token: ResumeToken,
        authorize: Callable[[ExecutionCheckpoint], None],
    ) -> ExecutionCheckpoint:
        """Consume one checkpoint only when authorization succeeds before commit."""
        try:
            async with self._pool.connection() as connection:
                cursor = await connection.execute(
                    _CONSUME_SQL,
                    (
                        self._token_digest(resume_token),
                        self._consumed_retention,
                        self._policy_version,
                    ),
                )
                row = await cursor.fetchone()
                if row is None:
                    raise CheckpointNotFoundError(
                        "O token é desconhecido, expirou ou já foi consumido."
                    )
                try:
                    checkpoint = ExecutionCheckpoint.model_validate(row[0])
                except Exception as error:
                    raise InvalidCheckpointError(
                        "O checkpoint armazenado não possui um payload válido."
                    ) from error
                authorize(checkpoint)
                return checkpoint
        except (DatabaseError, PoolTimeout) as error:
            raise PostgreSQLCheckpointStoreError(
                "Não foi possível consumir o checkpoint no PostgreSQL."
            ) from error

    async def read(self, resume_token: ResumeToken) -> PostgreSQLCheckpointSnapshot:
        """Read one active checkpoint without changing its storage revision."""
        try:
            async with self._pool.connection() as connection:
                cursor = await connection.execute(
                    _READ_SQL, (self._token_digest(resume_token),)
                )
                row = await cursor.fetchone()
        except (DatabaseError, PoolTimeout) as error:
            raise PostgreSQLCheckpointStoreError(
                "Não foi possível ler o checkpoint no PostgreSQL."
            ) from error
        if row is None:
            raise CheckpointNotFoundError(
                "O token é desconhecido, expirou ou já foi consumido."
            )
        try:
            return PostgreSQLCheckpointSnapshot(
                checkpoint=ExecutionCheckpoint.model_validate(row[0]),
                revision=int(row[1]),
            )
        except Exception as error:
            raise InvalidCheckpointError(
                "O checkpoint armazenado não possui um payload válido."
            ) from error

    async def compare_and_swap(
        self,
        *,
        resume_token: ResumeToken,
        checkpoint: ExecutionCheckpoint,
        expected_revision: int,
    ) -> PostgreSQLCheckpointSnapshot:
        """Replace one active checkpoint only at the expected revision."""
        if expected_revision <= 0:
            raise ValueError("A revisão esperada deve ser positiva.")
        token_digest = self._token_digest(resume_token)
        expires_at = self._expires_at(checkpoint)
        retention_until = self._retention_until(expires_at)
        try:
            async with self._pool.connection() as connection:
                cursor = await connection.execute(
                    _COMPARE_AND_SWAP_SQL,
                    (
                        checkpoint.checkpoint_version,
                        Jsonb(checkpoint.model_dump(mode="json")),
                        expires_at,
                        retention_until,
                        self._policy_version,
                        token_digest,
                        expected_revision,
                        checkpoint.execution_id,
                        checkpoint.agent.agent_id,
                        checkpoint.context.tenant_id,
                    ),
                )
                updated = await cursor.fetchone()
                if updated is not None:
                    return PostgreSQLCheckpointSnapshot(
                        checkpoint=ExecutionCheckpoint.model_validate(updated[0]),
                        revision=int(updated[1]),
                    )
                await self._raise_compare_and_swap_failure(
                    connection=connection,
                    token_digest=token_digest,
                    checkpoint=checkpoint,
                    expected_revision=expected_revision,
                )
        except (
            CheckpointConcurrencyConflictError,
            CheckpointNotFoundError,
            InvalidCheckpointError,
        ):
            raise
        except (DatabaseError, PoolTimeout) as error:
            raise PostgreSQLCheckpointStoreError(
                "Não foi possível atualizar o checkpoint no PostgreSQL."
            ) from error
        raise AssertionError("A classificação do compare-and-swap deve falhar.")

    async def compare_and_swap_leased(
        self,
        *,
        resume_token: ResumeToken,
        checkpoint: ExecutionCheckpoint,
        expected_revision: int,
        lease: CheckpointLease,
    ) -> PostgreSQLCheckpointSnapshot:
        """Replace a checkpoint only for the current lease and storage revision."""
        if expected_revision <= 0:
            raise ValueError("A revisão esperada deve ser positiva.")
        if lease.checkpoint_id != checkpoint.execution_id:
            raise CheckpointLeaseLostError(
                "O lease não pertence ao checkpoint que seria atualizado."
            )
        token_digest = self._token_digest(resume_token)
        expires_at = self._expires_at(checkpoint)
        retention_until = self._retention_until(expires_at)
        try:
            async with self._pool.connection() as connection:
                cursor = await connection.execute(
                    _COMPARE_AND_SWAP_LEASED_SQL,
                    (
                        checkpoint.checkpoint_version,
                        Jsonb(checkpoint.model_dump(mode="json")),
                        expires_at,
                        retention_until,
                        self._policy_version,
                        token_digest,
                        expected_revision,
                        checkpoint.execution_id,
                        checkpoint.agent.agent_id,
                        checkpoint.context.tenant_id,
                        lease.checkpoint_id,
                        lease.owner_id,
                        lease.fencing_token,
                    ),
                )
                updated = await cursor.fetchone()
                if updated is not None:
                    return PostgreSQLCheckpointSnapshot(
                        checkpoint=ExecutionCheckpoint.model_validate(updated[0]),
                        revision=int(updated[1]),
                    )
                if not await self._lease_is_valid(connection, lease):
                    raise CheckpointLeaseLostError(
                        "O lease expirou, foi liberado ou pertence a outra geração."
                    )
                await self._raise_compare_and_swap_failure(
                    connection=connection,
                    token_digest=token_digest,
                    checkpoint=checkpoint,
                    expected_revision=expected_revision,
                )
        except (
            CheckpointConcurrencyConflictError,
            CheckpointLeaseLostError,
            CheckpointNotFoundError,
            InvalidCheckpointError,
        ):
            raise
        except (DatabaseError, PoolTimeout) as error:
            raise PostgreSQLCheckpointStoreError(
                "Não foi possível atualizar o checkpoint no PostgreSQL."
            ) from error
        raise AssertionError("A classificação do compare-and-swap deve falhar.")

    async def consume_authorized_leased(
        self,
        *,
        resume_token: ResumeToken,
        lease: CheckpointLease,
        authorize: Callable[[ExecutionCheckpoint], None],
    ) -> ExecutionCheckpoint:
        """Authorize and consume atomically only for the current lease generation."""
        token_digest = self._token_digest(resume_token)
        try:
            async with self._pool.connection() as connection:
                cursor = await connection.execute(
                    _CONSUME_AUTHORIZED_LEASED_SQL,
                    (
                        token_digest,
                        lease.checkpoint_id,
                        lease.owner_id,
                        lease.fencing_token,
                        self._consumed_retention,
                        self._policy_version,
                        lease.fencing_token,
                    ),
                )
                row = await cursor.fetchone()
                if row is None:
                    checkpoint_cursor = await connection.execute(
                        _INSPECT_CONFLICT_SQL, (token_digest,)
                    )
                    checkpoint_row = await checkpoint_cursor.fetchone()
                    if checkpoint_row is None or bool(checkpoint_row[4]):
                        raise CheckpointNotFoundError(
                            "O token é desconhecido, expirou ou já foi consumido."
                        )
                    raise CheckpointLeaseLostError(
                        "O lease expirou, foi liberado ou pertence a outra geração."
                    )
                try:
                    checkpoint = ExecutionCheckpoint.model_validate(row[0])
                except Exception as error:
                    raise InvalidCheckpointError(
                        "O checkpoint armazenado não possui um payload válido."
                    ) from error
                await connection.execute(
                    _CLEAR_CONSUMED_LEASE_SQL,
                    (lease.checkpoint_id, lease.owner_id, lease.fencing_token),
                )
                authorize(checkpoint)
                return checkpoint
        except (
            CheckpointLeaseLostError,
            CheckpointNotFoundError,
            InvalidCheckpointError,
        ):
            raise
        except (DatabaseError, PoolTimeout) as error:
            raise PostgreSQLCheckpointStoreError(
                "Não foi possível consumir o checkpoint no PostgreSQL."
            ) from error

    async def purge_expired(self, *, batch_size: int = 1_000) -> int:
        """Delete one bounded batch of expired checkpoints."""
        if self._retention_policy is not None:
            raise PostgreSQLCheckpointStoreError(
                "O purge físico com políticas DS-007 permanece desabilitado "
                "até a DS-008."
            )
        if batch_size <= 0:
            raise ValueError("O tamanho do lote deve ser positivo.")
        try:
            async with self._pool.connection() as connection:
                cursor = await connection.execute(_PURGE_SQL, (batch_size,))
                return int(cursor.rowcount)
        except (DatabaseError, PoolTimeout) as error:
            raise PostgreSQLCheckpointStoreError(
                "Não foi possível remover checkpoints expirados do PostgreSQL."
            ) from error

    async def ping(self) -> None:
        """Validate that the configured pool can reach PostgreSQL."""
        try:
            async with self._pool.connection() as connection:
                await connection.execute("SELECT 1")
        except (DatabaseError, PoolTimeout) as error:
            raise PostgreSQLCheckpointStoreError(
                "O armazenamento PostgreSQL não está disponível."
            ) from error

    def _token_digest(self, resume_token: ResumeToken) -> bytes:
        value = resume_token.value.encode("utf-8")
        if self._token_hmac_key is not None:
            return hmac.digest(self._token_hmac_key, value, "sha256")
        return hashlib.sha256(value).digest()

    def _expires_at(self, checkpoint: ExecutionCheckpoint) -> datetime | None:
        candidates = [checkpoint.pending_approval.expires_at]
        if self._retention is not None:
            candidates.append(checkpoint.updated_at + self._retention)
        if self._retention_policy is not None:
            candidates.append(checkpoint.updated_at + self._retention_policy.hitl_ttl)
        return min((value for value in candidates if value is not None), default=None)

    def _retention_until(self, expires_at: datetime | None) -> datetime | None:
        if expires_at is None or self._retention_policy is None:
            return None
        return expires_at + self._retention_policy.expired_retention

    @property
    def _consumed_retention(self) -> timedelta:
        if self._retention_policy is not None:
            return self._retention_policy.consumed_retention
        return timedelta(days=30)

    @property
    def _policy_version(self) -> str:
        if self._retention_policy is not None:
            return self._retention_policy.policy_version
        return "compatibility-1x"

    async def _raise_compare_and_swap_failure(
        self,
        *,
        connection: AsyncConnection[Any],
        token_digest: bytes,
        checkpoint: ExecutionCheckpoint,
        expected_revision: int,
    ) -> None:
        cursor = await connection.execute(_INSPECT_CONFLICT_SQL, (token_digest,))
        row = await cursor.fetchone()
        if row is None or bool(row[4]):
            raise CheckpointNotFoundError(
                "O token é desconhecido, expirou ou já foi consumido."
            )
        execution_id, agent_id, tenant_id, actual_revision, _ = row
        if (
            execution_id != checkpoint.execution_id
            or agent_id != checkpoint.agent.agent_id
            or tenant_id != checkpoint.context.tenant_id
        ):
            raise InvalidCheckpointError(
                "A identidade do checkpoint não pode ser alterada."
            )
        raise CheckpointConcurrencyConflictError(
            checkpoint_id=str(execution_id),
            expected_revision=expected_revision,
            actual_revision=int(actual_revision),
        )

    @staticmethod
    async def _lease_is_valid(
        connection: AsyncConnection[Any], lease: CheckpointLease
    ) -> bool:
        cursor = await connection.execute(
            _LEASE_VALID_SQL,
            (lease.checkpoint_id, lease.owner_id, lease.fencing_token),
        )
        row = await cursor.fetchone()
        return row is not None and bool(row[0])
