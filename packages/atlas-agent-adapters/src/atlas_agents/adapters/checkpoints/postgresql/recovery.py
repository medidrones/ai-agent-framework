"""PostgreSQL discovery and durable audit support for execution recovery."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final, cast
from uuid import uuid4

from psycopg import DatabaseError
from psycopg_pool import AsyncConnectionPool, PoolTimeout

from atlas_agents import (
    CheckpointLease,
    CheckpointLeaseLostError,
    CheckpointNotFoundError,
    ExecutionCheckpoint,
    ExecutionStatus,
    InvalidCheckpointError,
    RecoveryAttempt,
    RecoveryCandidate,
    RecoveryOutcome,
)
from atlas_agents.adapters.checkpoints.postgresql.errors import (
    PostgreSQLCheckpointStoreError,
)

_LIST_CANDIDATES_SQL: Final = """
SELECT checkpoint.execution_id,
       encode(checkpoint.token_digest, 'hex'),
       checkpoint.agent_id,
       checkpoint.checkpoint_version,
       checkpoint.payload ->> 'status',
       clock_timestamp(),
       checkpoint.tenant_id
FROM atlas_agent.checkpoints AS checkpoint
WHERE (checkpoint.expires_at IS NULL OR checkpoint.expires_at > clock_timestamp())
  AND (%s::text IS NULL OR checkpoint.tenant_id = %s::text)
  AND COALESCE(checkpoint.payload ->> 'status', '') NOT IN (
      'completed', 'failed', 'cancelled', 'timed_out',
      'limit_exceeded', 'budget_exceeded', 'rejected'
  )
ORDER BY checkpoint.checkpoint_created_at, checkpoint.execution_id,
         checkpoint.token_digest
LIMIT %s
"""

_LOAD_CHECKPOINT_SQL: Final = """
SELECT payload
FROM atlas_agent.checkpoints
WHERE execution_id = %s
  AND token_digest = decode(%s, 'hex')
  AND (expires_at IS NULL OR expires_at > clock_timestamp())
"""

_BEGIN_ATTEMPT_SQL: Final = """
WITH next_attempt AS (
    SELECT COALESCE(MAX(attempt_number), 0) + 1 AS attempt_number
    FROM atlas_agent.execution_recovery_attempts
    WHERE execution_id = %s AND checkpoint_id = %s
), current_lease AS (
    SELECT 1
    FROM atlas_agent.checkpoint_leases
    WHERE checkpoint_id = %s
      AND owner_id = %s
      AND fencing_token = %s
      AND expires_at > clock_timestamp()
)
INSERT INTO atlas_agent.execution_recovery_attempts (
    attempt_id, execution_id, checkpoint_id, owner_id, fencing_token,
    attempt_number, started_at
)
SELECT %s, %s, %s, %s, %s, next_attempt.attempt_number, clock_timestamp()
FROM next_attempt, current_lease
WHERE next_attempt.attempt_number <= %s
RETURNING attempt_id, execution_id, checkpoint_id, attempt_number,
          owner_id, fencing_token, started_at
"""

_COMPLETE_ATTEMPT_SQL: Final = """
UPDATE atlas_agent.execution_recovery_attempts AS attempt
SET completed_at = clock_timestamp(), outcome = %s, reason_code = %s
WHERE attempt.attempt_id = %s
  AND attempt.execution_id = %s
  AND attempt.completed_at IS NULL
  AND attempt.owner_id = %s
  AND attempt.fencing_token = %s
  AND (
    EXISTS (
      SELECT 1 FROM atlas_agent.checkpoint_leases AS lease
      WHERE lease.checkpoint_id = attempt.execution_id
        AND lease.owner_id = %s
        AND lease.fencing_token = %s
        AND lease.expires_at > clock_timestamp()
    )
    OR NOT EXISTS (
      SELECT 1 FROM atlas_agent.checkpoints AS checkpoint
      WHERE checkpoint.execution_id = attempt.execution_id
        AND checkpoint.token_digest = decode(attempt.checkpoint_id, 'hex')
    )
  )
RETURNING attempt_id
"""

_LEASE_VALID_SQL: Final = """
SELECT 1
FROM atlas_agent.checkpoint_leases
WHERE checkpoint_id = %s
  AND owner_id = %s
  AND fencing_token = %s
  AND expires_at > clock_timestamp()
"""


class PostgreSQLRecoveryCandidateRepository:
    """Discover lightweight candidates and load payloads only after ownership."""

    def __init__(self, pool: AsyncConnectionPool[Any]) -> None:
        """Use a caller-owned pool."""
        self._pool = pool

    async def list_candidates(
        self, *, limit: int, tenant_id: str | None = None
    ) -> tuple[RecoveryCandidate, ...]:
        """List active non-terminal checkpoints in stable storage order."""
        if limit <= 0:
            raise ValueError("O limite de candidatos deve ser positivo.")
        try:
            async with self._pool.connection() as connection:
                cursor = await connection.execute(
                    _LIST_CANDIDATES_SQL, (tenant_id, tenant_id, limit)
                )
                rows = await cursor.fetchall()
            return tuple(self._candidate(row) for row in rows)
        except (DatabaseError, PoolTimeout) as error:
            raise PostgreSQLCheckpointStoreError(
                "Não foi possível descobrir candidatos de recovery no PostgreSQL."
            ) from error

    async def load_checkpoint(
        self, candidate: RecoveryCandidate
    ) -> ExecutionCheckpoint:
        """Load the exact active checkpoint represented by an opaque digest key."""
        try:
            async with self._pool.connection() as connection:
                cursor = await connection.execute(
                    _LOAD_CHECKPOINT_SQL,
                    (candidate.execution_id, candidate.checkpoint_id),
                )
                row = await cursor.fetchone()
        except (DatabaseError, PoolTimeout) as error:
            raise PostgreSQLCheckpointStoreError(
                "Não foi possível carregar o candidato de recovery no PostgreSQL."
            ) from error
        if row is None:
            raise CheckpointNotFoundError(
                "O checkpoint de recovery não existe ou não está mais ativo."
            )
        try:
            return ExecutionCheckpoint.model_validate(row[0])
        except Exception as error:
            raise InvalidCheckpointError(
                "O candidato de recovery possui checkpoint inválido."
            ) from error

    @staticmethod
    def _candidate(row: tuple[object, ...]) -> RecoveryCandidate:
        return RecoveryCandidate(
            execution_id=str(row[0]),
            checkpoint_id=str(row[1]),
            agent_id=str(row[2]),
            checkpoint_version=cast(int, row[3]),
            status=ExecutionStatus(str(row[4])),
            discovered_at=cast(datetime, row[5]),
            tenant_id=None if row[6] is None else str(row[6]),
        )


class PostgreSQLRecoveryAttemptRecorder:
    """Persist bounded recovery attempts under the current fencing generation."""

    def __init__(self, pool: AsyncConnectionPool[Any]) -> None:
        """Use a caller-owned pool."""
        self._pool = pool

    async def begin_attempt(
        self,
        *,
        candidate: RecoveryCandidate,
        lease: CheckpointLease,
        max_attempts: int,
    ) -> RecoveryAttempt | None:
        """Atomically admit an attempt when lease and durable limit are valid."""
        if max_attempts <= 0:
            raise ValueError("O limite de tentativas deve ser positivo.")
        attempt_id = str(uuid4())
        try:
            async with self._pool.connection() as connection:
                cursor = await connection.execute(
                    _BEGIN_ATTEMPT_SQL,
                    (
                        candidate.execution_id,
                        candidate.checkpoint_id,
                        candidate.execution_id,
                        lease.owner_id,
                        lease.fencing_token,
                        attempt_id,
                        candidate.execution_id,
                        candidate.checkpoint_id,
                        lease.owner_id,
                        lease.fencing_token,
                        max_attempts,
                    ),
                )
                row = await cursor.fetchone()
                if row is None:
                    lease_cursor = await connection.execute(
                        _LEASE_VALID_SQL,
                        (
                            candidate.execution_id,
                            lease.owner_id,
                            lease.fencing_token,
                        ),
                    )
                    if await lease_cursor.fetchone() is None:
                        raise CheckpointLeaseLostError(
                            "A tentativa não pode iniciar sem o lease vigente."
                        )
            return None if row is None else self._attempt(row)
        except CheckpointLeaseLostError:
            raise
        except (DatabaseError, PoolTimeout) as error:
            raise PostgreSQLCheckpointStoreError(
                "Não foi possível registrar a tentativa de recovery."
            ) from error

    async def complete_attempt(
        self,
        *,
        attempt: RecoveryAttempt,
        lease: CheckpointLease,
        outcome: RecoveryOutcome,
        reason_code: str | None,
    ) -> None:
        """Complete an attempt only while its ownership generation is current."""
        try:
            async with self._pool.connection() as connection:
                cursor = await connection.execute(
                    _COMPLETE_ATTEMPT_SQL,
                    (
                        outcome.value,
                        reason_code,
                        attempt.attempt_id,
                        attempt.execution_id,
                        lease.owner_id,
                        lease.fencing_token,
                        lease.owner_id,
                        lease.fencing_token,
                    ),
                )
                if await cursor.fetchone() is None:
                    raise CheckpointLeaseLostError(
                        "A tentativa não pode ser concluída sem o lease vigente."
                    )
        except CheckpointLeaseLostError:
            raise
        except (DatabaseError, PoolTimeout) as error:
            raise PostgreSQLCheckpointStoreError(
                "Não foi possível concluir a tentativa de recovery."
            ) from error

    @staticmethod
    def _attempt(row: tuple[object, ...]) -> RecoveryAttempt:
        return RecoveryAttempt(
            attempt_id=str(row[0]),
            execution_id=str(row[1]),
            checkpoint_id=str(row[2]),
            attempt_number=cast(int, row[3]),
            owner_id=str(row[4]),
            fencing_token=cast(int, row[5]),
            started_at=cast(datetime, row[6]),
        )
