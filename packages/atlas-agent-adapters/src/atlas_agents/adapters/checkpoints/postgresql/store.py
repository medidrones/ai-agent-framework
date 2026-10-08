"""Transactional PostgreSQL implementation of the checkpoint store contract."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Any, Final

from psycopg import DatabaseError, errors
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool, PoolTimeout

from atlas_agents.adapters.checkpoints.postgresql.errors import (
    PostgreSQLCheckpointStoreError,
)
from atlas_agents.approvals import (
    CheckpointNotFoundError,
    CheckpointSaveError,
    InvalidCheckpointError,
    ResumeToken,
)
from atlas_agents.runtime import ExecutionCheckpoint

_INSERT_SQL: Final = """
INSERT INTO atlas_agent.checkpoints (
    token_digest,
    checkpoint_version,
    execution_id,
    agent_id,
    tenant_id,
    payload,
    checkpoint_created_at,
    expires_at
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
"""

_CONSUME_SQL: Final = """
DELETE FROM atlas_agent.checkpoints
WHERE token_digest = %s
  AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
RETURNING payload
"""

_PURGE_SQL: Final = """
WITH expired AS (
    SELECT token_digest
    FROM atlas_agent.checkpoints
    WHERE expires_at IS NOT NULL
      AND expires_at <= CURRENT_TIMESTAMP
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
        token_hmac_key: bytes | None = None,
    ) -> None:
        """Configure persistence without opening or closing the supplied pool."""
        if retention is not None and retention <= timedelta(0):
            raise ValueError("A retenção do checkpoint deve ser positiva.")
        if token_hmac_key is not None and len(token_hmac_key) < 32:
            raise ValueError("A chave HMAC do token deve possuir ao menos 32 bytes.")
        self._pool = pool
        self._retention = retention
        self._token_hmac_key = token_hmac_key

    async def save(
        self,
        *,
        resume_token: ResumeToken,
        checkpoint: ExecutionCheckpoint,
    ) -> None:
        """Create one checkpoint without overwriting an existing token."""
        expires_at = self._expires_at(checkpoint)
        try:
            async with self._pool.connection() as connection:
                await connection.execute(
                    _INSERT_SQL,
                    (
                        self._token_digest(resume_token),
                        checkpoint.checkpoint_version,
                        checkpoint.execution_id,
                        checkpoint.agent.agent_id,
                        checkpoint.context.tenant_id,
                        Jsonb(checkpoint.model_dump(mode="json")),
                        checkpoint.created_at,
                        expires_at,
                    ),
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
                    _CONSUME_SQL, (self._token_digest(resume_token),)
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

    async def purge_expired(self, *, batch_size: int = 1_000) -> int:
        """Delete one bounded batch of expired checkpoints."""
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
        return min((value for value in candidates if value is not None), default=None)
