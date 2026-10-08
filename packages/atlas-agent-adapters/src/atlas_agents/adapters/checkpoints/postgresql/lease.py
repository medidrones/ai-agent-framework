"""PostgreSQL checkpoint lease and fencing implementation."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Final, cast

from psycopg import DatabaseError
from psycopg_pool import AsyncConnectionPool, PoolTimeout

from atlas_agents import (
    CheckpointLease,
    CheckpointLeaseConflictError,
    CheckpointLeaseLostError,
    CheckpointLeaseNotFoundError,
)
from atlas_agents.adapters.checkpoints.postgresql.errors import (
    PostgreSQLCheckpointStoreError,
)

_ACQUIRE_SQL: Final = """
INSERT INTO atlas_agent.checkpoint_leases (
    checkpoint_id, owner_id, fencing_token, acquired_at, expires_at
)
SELECT %s, %s, 1, clock_timestamp(),
       clock_timestamp() + (%s * INTERVAL '1 second')
WHERE EXISTS (
    SELECT 1 FROM atlas_agent.checkpoints
    WHERE execution_id = %s
      AND (expires_at IS NULL OR expires_at > clock_timestamp())
)
ON CONFLICT (checkpoint_id) DO UPDATE
SET owner_id = EXCLUDED.owner_id,
    fencing_token = atlas_agent.checkpoint_leases.fencing_token + 1,
    acquired_at = clock_timestamp(),
    expires_at = clock_timestamp() + (%s * INTERVAL '1 second')
WHERE (
    atlas_agent.checkpoint_leases.owner_id IS NULL
    OR atlas_agent.checkpoint_leases.expires_at <= clock_timestamp()
)
  AND EXISTS (
      SELECT 1 FROM atlas_agent.checkpoints
      WHERE execution_id = EXCLUDED.checkpoint_id
        AND (expires_at IS NULL OR expires_at > clock_timestamp())
  )
RETURNING checkpoint_id, owner_id, fencing_token, acquired_at, expires_at
"""

_LOCK_EXECUTION_SQL: Final = """
SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))
"""

_CHECK_ELIGIBILITY_SQL: Final = """
SELECT EXISTS (
    SELECT 1 FROM atlas_agent.checkpoints
    WHERE execution_id = %s
      AND (expires_at IS NULL OR expires_at > clock_timestamp())
)
"""

_RENEW_SQL: Final = """
UPDATE atlas_agent.checkpoint_leases
SET expires_at = GREATEST(
    expires_at,
    clock_timestamp() + (%s * INTERVAL '1 second')
)
WHERE checkpoint_id = %s
  AND owner_id = %s
  AND fencing_token = %s
  AND expires_at > clock_timestamp()
  AND EXISTS (
      SELECT 1 FROM atlas_agent.checkpoints
      WHERE execution_id = %s
        AND (expires_at IS NULL OR expires_at > clock_timestamp())
  )
RETURNING checkpoint_id, owner_id, fencing_token, acquired_at, expires_at
"""

_RELEASE_SQL: Final = """
UPDATE atlas_agent.checkpoint_leases
SET owner_id = NULL, acquired_at = NULL, expires_at = NULL
WHERE checkpoint_id = %s
  AND owner_id = %s
  AND fencing_token = %s
  AND expires_at > clock_timestamp()
RETURNING fencing_token
"""


class PostgreSQLCheckpointLeaseManager:
    """Coordinate checkpoint ownership using PostgreSQL as time authority."""

    def __init__(self, pool: AsyncConnectionPool[Any]) -> None:
        """Use a caller-owned connection pool."""
        self._pool = pool

    async def acquire(
        self,
        *,
        checkpoint_id: str,
        owner_id: str,
        duration: timedelta,
    ) -> CheckpointLease:
        """Acquire an eligible checkpoint and issue a monotonic fencing token."""
        seconds = self._validate_inputs(checkpoint_id, owner_id, duration)
        try:
            async with self._pool.connection() as connection:
                await connection.execute(_LOCK_EXECUTION_SQL, (checkpoint_id,))
                cursor = await connection.execute(
                    _ACQUIRE_SQL,
                    (checkpoint_id, owner_id, seconds, checkpoint_id, seconds),
                )
                row = await cursor.fetchone()
                if row is not None:
                    return self._lease(row)
                eligibility = await connection.execute(
                    _CHECK_ELIGIBILITY_SQL, (checkpoint_id,)
                )
                eligible_row = await eligibility.fetchone()
                if eligible_row is None or not bool(eligible_row[0]):
                    raise CheckpointLeaseNotFoundError(
                        "O checkpoint não está disponível para aquisição de lease."
                    )
                raise CheckpointLeaseConflictError(
                    "O checkpoint possui um lease ativo de outro owner."
                )
        except (CheckpointLeaseConflictError, CheckpointLeaseNotFoundError):
            raise
        except (DatabaseError, PoolTimeout) as error:
            raise PostgreSQLCheckpointStoreError(
                "Não foi possível adquirir o lease no PostgreSQL."
            ) from error

    async def renew(
        self,
        *,
        lease: CheckpointLease,
        duration: timedelta,
    ) -> CheckpointLease:
        """Renew only the current, unexpired lease generation."""
        seconds = self._duration_seconds(duration)
        try:
            async with self._pool.connection() as connection:
                await connection.execute(_LOCK_EXECUTION_SQL, (lease.checkpoint_id,))
                cursor = await connection.execute(
                    _RENEW_SQL,
                    (
                        seconds,
                        lease.checkpoint_id,
                        lease.owner_id,
                        lease.fencing_token,
                        lease.checkpoint_id,
                    ),
                )
                row = await cursor.fetchone()
                if row is None:
                    raise CheckpointLeaseLostError(
                        "O lease expirou, foi liberado ou pertence a outra geração."
                    )
                return self._lease(row)
        except CheckpointLeaseLostError:
            raise
        except (DatabaseError, PoolTimeout) as error:
            raise PostgreSQLCheckpointStoreError(
                "Não foi possível renovar o lease no PostgreSQL."
            ) from error

    async def release(self, *, lease: CheckpointLease) -> None:
        """Release only the current lease while retaining its generation."""
        try:
            async with self._pool.connection() as connection:
                await connection.execute(_LOCK_EXECUTION_SQL, (lease.checkpoint_id,))
                cursor = await connection.execute(
                    _RELEASE_SQL,
                    (lease.checkpoint_id, lease.owner_id, lease.fencing_token),
                )
                if await cursor.fetchone() is None:
                    raise CheckpointLeaseLostError(
                        "O lease expirou, foi liberado ou pertence a outra geração."
                    )
        except CheckpointLeaseLostError:
            raise
        except (DatabaseError, PoolTimeout) as error:
            raise PostgreSQLCheckpointStoreError(
                "Não foi possível liberar o lease no PostgreSQL."
            ) from error

    @staticmethod
    def _lease(row: tuple[object, ...]) -> CheckpointLease:
        return CheckpointLease(
            checkpoint_id=str(row[0]),
            owner_id=str(row[1]),
            fencing_token=cast(int, row[2]),
            acquired_at=cast(datetime, row[3]),
            expires_at=cast(datetime, row[4]),
        )

    @staticmethod
    def _validate_inputs(
        checkpoint_id: str,
        owner_id: str,
        duration: timedelta,
    ) -> float:
        if not checkpoint_id.strip():
            raise ValueError("O identificador do checkpoint não pode ser vazio.")
        if not owner_id.strip():
            raise ValueError("O identificador do owner não pode ser vazio.")
        return PostgreSQLCheckpointLeaseManager._duration_seconds(duration)

    @staticmethod
    def _duration_seconds(duration: timedelta) -> float:
        seconds = duration.total_seconds()
        if seconds <= 0:
            raise ValueError("A duração do lease deve ser positiva.")
        return seconds
