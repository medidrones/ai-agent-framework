"""Transactional PostgreSQL checkpoint cleanup and purge implementation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, cast
from uuid import uuid4

from psycopg import AsyncConnection, DatabaseError
from psycopg_pool import AsyncConnectionPool, PoolClosed, PoolTimeout

from atlas_agents.adapters.checkpoints.postgresql.errors import (
    PostgreSQLCheckpointStoreError,
)
from atlas_agents.runtime import (
    CURRENT_CHECKPOINT_VERSION,
    CheckpointPurgeClassification,
    CheckpointPurgeConfig,
    CheckpointRetentionCategory,
    CheckpointRetentionClassifier,
    CheckpointRetentionPolicy,
    CheckpointRetentionSubject,
    PurgeAuthorization,
    PurgeBatchResult,
    PurgeEligibility,
    PurgeItemResult,
    PurgeOutcome,
)

_SET_TIMEOUTS_SQL: Final = """
SELECT set_config('statement_timeout', %s, true),
       set_config('lock_timeout', %s, true)
"""

_CHECKPOINT_CANDIDATES_SQL: Final = """
SELECT encode(checkpoint.token_digest, 'hex'), checkpoint.execution_id,
       checkpoint.agent_id, checkpoint.tenant_id, checkpoint.retention_class,
       checkpoint.expires_at, checkpoint.retention_until,
       checkpoint.retention_policy_version, checkpoint.checkpoint_version,
       checkpoint.legal_hold
FROM atlas_agent.checkpoints AS checkpoint
WHERE checkpoint.retention_until IS NOT NULL
  AND checkpoint.retention_until <= clock_timestamp()
  AND (%s::text IS NULL OR checkpoint.tenant_id = %s::text)
ORDER BY checkpoint.retention_until, checkpoint.execution_id,
         checkpoint.token_digest
LIMIT %s
FOR UPDATE SKIP LOCKED
"""

_TOMBSTONE_CANDIDATES_SQL: Final = """
SELECT encode(tombstone.token_digest, 'hex'), tombstone.execution_id,
       tombstone.agent_id, tombstone.tenant_id, 'consumed',
       tombstone.consumed_at, tombstone.retention_until,
       tombstone.retention_policy_version, %s, tombstone.legal_hold
FROM atlas_agent.checkpoint_tombstones AS tombstone
WHERE tombstone.retention_until <= clock_timestamp()
  AND (%s::text IS NULL OR tombstone.tenant_id = %s::text)
ORDER BY tombstone.retention_until, tombstone.execution_id,
         tombstone.token_digest
LIMIT %s
FOR UPDATE SKIP LOCKED
"""

_TRY_LOCK_EXECUTION_SQL: Final = """
SELECT pg_try_advisory_xact_lock(hashtextextended(%s, 0))
"""

_RUNTIME_GUARDS_SQL: Final = """
SELECT EXISTS (
           SELECT 1 FROM atlas_agent.checkpoint_leases
           WHERE checkpoint_id = %s
             AND owner_id IS NOT NULL
             AND expires_at > clock_timestamp()
       ),
       EXISTS (
           SELECT 1 FROM atlas_agent.execution_recovery_attempts
           WHERE checkpoint_id = %s AND completed_at IS NULL
       ),
       clock_timestamp()
"""

_CREATE_TOMBSTONE_SQL: Final = """
INSERT INTO atlas_agent.checkpoint_tombstones (
    token_digest, execution_id, agent_id, tenant_id, consumed_at,
    retention_until, retention_policy_version, fencing_token, legal_hold
)
SELECT decode(%s, 'hex'), %s, %s, %s, clock_timestamp(),
       clock_timestamp() + %s, %s,
       NULLIF(lease.fencing_token, 0), FALSE
FROM (SELECT 1) AS source
LEFT JOIN atlas_agent.checkpoint_leases AS lease ON lease.checkpoint_id = %s
ON CONFLICT (token_digest) DO UPDATE
SET retention_until = GREATEST(
        atlas_agent.checkpoint_tombstones.retention_until,
        EXCLUDED.retention_until
    ),
    fencing_token = GREATEST(
        atlas_agent.checkpoint_tombstones.fencing_token,
        EXCLUDED.fencing_token
    )
"""

_DELETE_CHECKPOINT_SQL: Final = """
DELETE FROM atlas_agent.checkpoints
WHERE token_digest = decode(%s, 'hex') AND execution_id = %s
"""

_DELETE_TOMBSTONE_SQL: Final = """
DELETE FROM atlas_agent.checkpoint_tombstones
WHERE token_digest = decode(%s, 'hex') AND execution_id = %s
"""

_INSERT_AUDIT_SQL: Final = """
INSERT INTO atlas_agent.checkpoint_purge_audit (
    audit_id, purge_run_id, operation_id, checkpoint_id, execution_id,
    tenant_id, record_kind, outcome, reason_code, policy_version
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

_RECONCILE_AUDIT_SQL: Final = """
SELECT operation_id::text, checkpoint_id, execution_id, outcome, reason_code,
       policy_version, tenant_id
FROM atlas_agent.checkpoint_purge_audit
WHERE purge_run_id = %s AND operation_id = ANY(%s::uuid[])
ORDER BY operation_id
"""


@dataclass(frozen=True, slots=True)
class _Candidate:
    checkpoint_id: str
    execution_id: str
    agent_id: str
    tenant_id: str | None
    category: CheckpointRetentionCategory
    retention_started_at: datetime
    retention_until: datetime
    policy_version: str | None
    checkpoint_version: int
    legal_hold: bool
    kind: str


class PostgreSQLCheckpointPurgeRepository:
    """Purge bounded batches under PostgreSQL locks and transactional audit."""

    def __init__(
        self,
        pool: AsyncConnectionPool[Any],
        *,
        policy: CheckpointRetentionPolicy,
    ) -> None:
        """Use one immutable policy snapshot and a caller-owned pool."""
        self._pool = pool
        self._policy = policy
        self._classifier = CheckpointRetentionClassifier(policy)

    async def purge_batch(
        self,
        *,
        purge_run_id: str,
        authorization: PurgeAuthorization,
        config: CheckpointPurgeConfig,
    ) -> PurgeBatchResult:
        """Discover, revalidate, mutate, and audit one bounded batch."""
        operation_ids: list[str] = []
        candidates: list[_Candidate] = []
        results: list[PurgeItemResult] = []
        ready_to_commit = False
        try:
            async with self._pool.connection() as connection:
                await connection.execute(
                    _SET_TIMEOUTS_SQL,
                    (
                        f"{config.statement_timeout.total_seconds()}s",
                        f"{config.lock_timeout.total_seconds()}s",
                    ),
                )
                candidates = await self._discover(
                    connection,
                    tenant_id=authorization.tenant_id,
                    limit=config.batch_size,
                )
                for candidate in candidates:
                    operation_id = str(uuid4())
                    operation_ids.append(operation_id)
                    result = await self._process_candidate(
                        connection,
                        purge_run_id=purge_run_id,
                        operation_id=operation_id,
                        candidate=candidate,
                        dry_run=config.dry_run,
                    )
                    results.append(result)
                ready_to_commit = True
            return self._result(purge_run_id, results)
        except (DatabaseError, PoolClosed, PoolTimeout) as error:
            if ready_to_commit and operation_ids:
                reconciled = await self._reconcile(
                    purge_run_id=purge_run_id,
                    operation_ids=operation_ids,
                    candidates=candidates,
                )
                return self._result(purge_run_id, reconciled)
            raise PostgreSQLCheckpointStoreError(
                "Não foi possível executar o purge de checkpoints no PostgreSQL."
            ) from error

    async def _discover(
        self,
        connection: AsyncConnection[Any],
        *,
        tenant_id: str | None,
        limit: int,
    ) -> list[_Candidate]:
        checkpoint_cursor = await connection.execute(
            _CHECKPOINT_CANDIDATES_SQL,
            (tenant_id, tenant_id, limit),
        )
        checkpoint_rows = await checkpoint_cursor.fetchall()
        candidates = [
            self._candidate(row, kind="checkpoint") for row in checkpoint_rows
        ]
        remaining = limit - len(candidates)
        if remaining <= 0:
            return candidates
        tombstone_cursor = await connection.execute(
            _TOMBSTONE_CANDIDATES_SQL,
            (
                CURRENT_CHECKPOINT_VERSION,
                tenant_id,
                tenant_id,
                remaining,
            ),
        )
        tombstone_rows = await tombstone_cursor.fetchall()
        candidates.extend(
            self._candidate(row, kind="tombstone") for row in tombstone_rows
        )
        candidates.sort(
            key=lambda item: (
                item.retention_until,
                item.execution_id,
                item.kind,
                item.checkpoint_id,
            )
        )
        return candidates

    async def _process_candidate(
        self,
        connection: AsyncConnection[Any],
        *,
        purge_run_id: str,
        operation_id: str,
        candidate: _Candidate,
        dry_run: bool,
    ) -> PurgeItemResult:
        lock_cursor = await connection.execute(
            _TRY_LOCK_EXECUTION_SQL, (candidate.execution_id,)
        )
        lock_row = await lock_cursor.fetchone()
        if lock_row is None or not bool(lock_row[0]):
            return await self._audit_result(
                connection,
                purge_run_id=purge_run_id,
                operation_id=operation_id,
                candidate=candidate,
                outcome=PurgeOutcome.BLOCKED,
                reason_code="concurrent_operation",
            )
        guard_cursor = await connection.execute(
            _RUNTIME_GUARDS_SQL,
            (candidate.execution_id, candidate.execution_id),
        )
        guard_row = await guard_cursor.fetchone()
        if guard_row is None:
            raise PostgreSQLCheckpointStoreError(
                "O PostgreSQL não retornou os guards transacionais do purge."
            )
        classification = self._classifier.classify(
            CheckpointRetentionSubject(
                checkpoint_id=candidate.checkpoint_id,
                execution_id=candidate.execution_id,
                category=candidate.category,
                evaluated_at=cast(datetime, guard_row[2]),
                retention_started_at=candidate.retention_started_at,
                stored_retention_until=candidate.retention_until,
                expires_at=(
                    candidate.retention_started_at
                    if candidate.kind == "checkpoint"
                    else None
                ),
                tenant_id=candidate.tenant_id,
                active_lease=bool(guard_row[0]),
                active_recovery=bool(guard_row[1]),
                compatible=(
                    candidate.checkpoint_version == CURRENT_CHECKPOINT_VERSION
                    and bool(candidate.policy_version)
                ),
                legal_hold=candidate.legal_hold,
            )
        )
        outcome = self._outcome(classification)
        reason_code = classification.reason_code
        if outcome is PurgeOutcome.PURGED and dry_run:
            outcome = PurgeOutcome.SKIPPED
            reason_code = "dry_run_eligible"
        elif outcome is PurgeOutcome.PURGED:
            await self._delete(connection, candidate)
        return await self._audit_result(
            connection,
            purge_run_id=purge_run_id,
            operation_id=operation_id,
            candidate=candidate,
            outcome=outcome,
            reason_code=reason_code,
        )

    async def _delete(
        self, connection: AsyncConnection[Any], candidate: _Candidate
    ) -> None:
        if candidate.kind == "checkpoint":
            await connection.execute(
                _CREATE_TOMBSTONE_SQL,
                (
                    candidate.checkpoint_id,
                    candidate.execution_id,
                    candidate.agent_id,
                    candidate.tenant_id,
                    self._policy.consumed_retention,
                    self._policy.policy_version,
                    candidate.execution_id,
                ),
            )
            cursor = await connection.execute(
                _DELETE_CHECKPOINT_SQL,
                (candidate.checkpoint_id, candidate.execution_id),
            )
        else:
            cursor = await connection.execute(
                _DELETE_TOMBSTONE_SQL,
                (candidate.checkpoint_id, candidate.execution_id),
            )
        if cursor.rowcount != 1:
            raise PostgreSQLCheckpointStoreError(
                "O candidato mudou durante a revalidação transacional."
            )

    async def _audit_result(
        self,
        connection: AsyncConnection[Any],
        *,
        purge_run_id: str,
        operation_id: str,
        candidate: _Candidate,
        outcome: PurgeOutcome,
        reason_code: str,
    ) -> PurgeItemResult:
        await connection.execute(
            _INSERT_AUDIT_SQL,
            (
                str(uuid4()),
                purge_run_id,
                operation_id,
                candidate.checkpoint_id,
                candidate.execution_id,
                candidate.tenant_id,
                candidate.kind,
                outcome.value,
                reason_code,
                self._policy.policy_version,
            ),
        )
        return PurgeItemResult(
            operation_id=operation_id,
            checkpoint_id=candidate.checkpoint_id,
            execution_id=candidate.execution_id,
            outcome=outcome,
            reason_code=reason_code,
            policy_version=self._policy.policy_version,
            tenant_id=candidate.tenant_id,
        )

    async def _reconcile(
        self,
        *,
        purge_run_id: str,
        operation_ids: list[str],
        candidates: list[_Candidate],
    ) -> list[PurgeItemResult]:
        try:
            async with self._pool.connection() as connection:
                cursor = await connection.execute(
                    _RECONCILE_AUDIT_SQL,
                    (purge_run_id, operation_ids),
                )
                rows = await cursor.fetchall()
        except (DatabaseError, PoolClosed, PoolTimeout) as error:
            raise PostgreSQLCheckpointStoreError(
                "O resultado do commit do purge é desconhecido e não pôde ser "
                "reconciliado."
            ) from error
        persisted = {
            str(row[0]): PurgeItemResult(
                operation_id=str(row[0]),
                checkpoint_id=str(row[1]),
                execution_id=str(row[2]),
                outcome=PurgeOutcome(str(row[3])),
                reason_code=str(row[4]),
                policy_version=str(row[5]),
                tenant_id=None if row[6] is None else str(row[6]),
            )
            for row in rows
        }
        candidate_by_operation = dict(zip(operation_ids, candidates, strict=True))
        return [
            persisted.get(operation_id)
            or PurgeItemResult(
                operation_id=operation_id,
                checkpoint_id=candidate_by_operation[operation_id].checkpoint_id,
                execution_id=candidate_by_operation[operation_id].execution_id,
                outcome=PurgeOutcome.OUTCOME_UNKNOWN,
                reason_code="commit_outcome_unknown",
                policy_version=self._policy.policy_version,
                tenant_id=candidate_by_operation[operation_id].tenant_id,
            )
            for operation_id in operation_ids
        ]

    @staticmethod
    def _candidate(row: tuple[object, ...], *, kind: str) -> _Candidate:
        return _Candidate(
            checkpoint_id=str(row[0]),
            execution_id=str(row[1]),
            agent_id=str(row[2]),
            tenant_id=None if row[3] is None else str(row[3]),
            category=CheckpointRetentionCategory(str(row[4])),
            retention_started_at=cast(datetime, row[5]),
            retention_until=cast(datetime, row[6]),
            policy_version=None if row[7] is None else str(row[7]),
            checkpoint_version=int(cast(int, row[8])),
            legal_hold=bool(row[9]),
            kind=kind,
        )

    @staticmethod
    def _outcome(classification: CheckpointPurgeClassification) -> PurgeOutcome:
        if classification.eligibility is PurgeEligibility.ELIGIBLE:
            return PurgeOutcome.PURGED
        if classification.eligibility is PurgeEligibility.NOT_ELIGIBLE:
            return PurgeOutcome.SKIPPED
        return PurgeOutcome.BLOCKED

    @staticmethod
    def _result(purge_run_id: str, results: list[PurgeItemResult]) -> PurgeBatchResult:
        return PurgeBatchResult(
            purge_run_id=purge_run_id,
            discovered=len(results),
            purged=sum(item.outcome is PurgeOutcome.PURGED for item in results),
            skipped=sum(item.outcome is PurgeOutcome.SKIPPED for item in results),
            blocked=sum(item.outcome is PurgeOutcome.BLOCKED for item in results),
            failed=sum(item.outcome is PurgeOutcome.FAILED for item in results),
            outcome_unknown=sum(
                item.outcome is PurgeOutcome.OUTCOME_UNKNOWN for item in results
            ),
            results=tuple(results),
        )
