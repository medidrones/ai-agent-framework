"""Read-only PostgreSQL retention and purge-eligibility classification."""

from __future__ import annotations

from typing import Any, Final

from psycopg import DatabaseError
from psycopg_pool import AsyncConnectionPool, PoolTimeout

from atlas_agents.adapters.checkpoints.postgresql.errors import (
    PostgreSQLCheckpointStoreError,
)
from atlas_agents.runtime import (
    CURRENT_CHECKPOINT_VERSION,
    CheckpointPurgeClassification,
    CheckpointRetentionCategory,
    CheckpointRetentionClassifier,
    CheckpointRetentionPolicy,
    CheckpointRetentionSubject,
)

_CLASSIFY_SQL: Final = """
WITH database_clock AS (
    SELECT clock_timestamp() AS evaluated_at
), candidates AS (
    SELECT encode(checkpoint.token_digest, 'hex') AS checkpoint_id,
           checkpoint.execution_id,
           checkpoint.retention_class AS category,
           checkpoint.expires_at AS retention_started_at,
           checkpoint.retention_until,
           checkpoint.expires_at,
           checkpoint.tenant_id,
           checkpoint.checkpoint_version = %s AS compatible,
           EXISTS (
               SELECT 1 FROM atlas_agent.checkpoint_leases AS lease, database_clock
               WHERE lease.checkpoint_id = checkpoint.execution_id
                 AND lease.owner_id IS NOT NULL
                 AND lease.expires_at > database_clock.evaluated_at
           ) AS active_lease,
           EXISTS (
               SELECT 1 FROM atlas_agent.execution_recovery_attempts AS attempt
               WHERE attempt.checkpoint_id = checkpoint.execution_id
                 AND attempt.completed_at IS NULL
           ) AS active_recovery,
           0 AS source_order
    FROM atlas_agent.checkpoints AS checkpoint
    WHERE (%s::text IS NULL OR checkpoint.tenant_id = %s::text)
    UNION ALL
    SELECT encode(tombstone.token_digest, 'hex'),
           tombstone.execution_id,
           'consumed',
           tombstone.consumed_at,
           tombstone.retention_until,
           NULL,
           tombstone.tenant_id,
           TRUE,
           FALSE,
           FALSE,
           1
    FROM atlas_agent.checkpoint_tombstones AS tombstone
    WHERE (%s::text IS NULL OR tombstone.tenant_id = %s::text)
)
SELECT candidates.*, database_clock.evaluated_at
FROM candidates CROSS JOIN database_clock
ORDER BY candidates.execution_id, candidates.source_order, candidates.checkpoint_id
LIMIT %s
"""


class PostgreSQLCheckpointRetentionRepository:
    """Classify durable records using PostgreSQL as the time authority."""

    def __init__(
        self,
        pool: AsyncConnectionPool[Any],
        *,
        policy: CheckpointRetentionPolicy,
    ) -> None:
        """Use an immutable policy and a caller-owned connection pool."""
        self._pool = pool
        self._classifier = CheckpointRetentionClassifier(policy)

    async def classify(
        self, *, limit: int, tenant_id: str | None = None
    ) -> tuple[CheckpointPurgeClassification, ...]:
        """Return a bounded, deterministic batch without deleting records."""
        if limit <= 0:
            raise ValueError("O limite da classificação deve ser positivo.")
        try:
            async with self._pool.connection() as connection:
                cursor = await connection.execute(
                    _CLASSIFY_SQL,
                    (
                        CURRENT_CHECKPOINT_VERSION,
                        tenant_id,
                        tenant_id,
                        tenant_id,
                        tenant_id,
                        limit,
                    ),
                )
                rows = await cursor.fetchall()
        except (DatabaseError, PoolTimeout) as error:
            raise PostgreSQLCheckpointStoreError(
                "Não foi possível classificar a retenção no PostgreSQL."
            ) from error
        return tuple(self._classify_row(row) for row in rows)

    def _classify_row(self, row: tuple[Any, ...]) -> CheckpointPurgeClassification:
        subject = CheckpointRetentionSubject(
            checkpoint_id=str(row[0]),
            execution_id=str(row[1]),
            category=CheckpointRetentionCategory(str(row[2])),
            retention_started_at=row[3],
            stored_retention_until=row[4],
            expires_at=row[5],
            tenant_id=row[6],
            compatible=bool(row[7]),
            active_lease=bool(row[8]),
            active_recovery=bool(row[9]),
            evaluated_at=row[11],
        )
        return self._classifier.classify(subject)
