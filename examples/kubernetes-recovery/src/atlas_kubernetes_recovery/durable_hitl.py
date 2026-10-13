"""Durable host boundary for human approval authorization and audit."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol, Self, cast
from uuid import uuid4

from psycopg import AsyncConnection, DatabaseError
from psycopg_pool import AsyncConnectionPool, PoolTimeout
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from atlas_agents import ApprovalDecision, ApprovalDecisionType, ExecutionIdentity


class DurableApprovalError(RuntimeError):
    """Base class for safe durable approval failures."""


class ApprovalNotFoundError(DurableApprovalError):
    """Report an unknown approval without disclosing adjacent records."""


class ApprovalAuthorizationError(DurableApprovalError):
    """Reject an identity or scope that cannot decide the request."""


class ApprovalExpiredError(DurableApprovalError):
    """Reject a decision after the approval deadline."""


class ApprovalConflictError(DurableApprovalError):
    """Reject a conflicting decision after one winner was persisted."""


class ApprovalPersistenceError(DurableApprovalError):
    """Hide infrastructure details when durable persistence fails."""


class DurableApprovalState(StrEnum):
    """Represent durable host-owned approval states."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RESUMED = "resumed"
    EXPIRED = "expired"


class ResumeOutcome(StrEnum):
    """Classify a resume attempt without claiming external exactly-once."""

    COMPLETED = "completed"
    REJECTED = "rejected"
    ALREADY_CONSUMED = "already_consumed"
    FAILED = "failed"
    OUTCOME_UNKNOWN = "outcome_unknown"


class TrustedApprovalPrincipal(BaseModel):
    """Carry identity and authorization established by a trusted host."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    subject: str
    tenant_id: str
    permissions: frozenset[str] = Field(default_factory=frozenset)
    tool_names: frozenset[str] = Field(default_factory=frozenset)

    @field_validator("subject", "tenant_id")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        """Reject empty security identifiers."""
        if not value.strip():
            raise ValueError("A identidade e o tenant devem ser informados.")
        return value


class DurableApprovalRecord(BaseModel):
    """Persist one scoped request without retaining its bearer token."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    approval_request_id: str
    execution_id: str
    tenant_id: str
    agent_id: str
    tool_call_id: str
    tool_name: str
    backend: str
    token_digest: str = Field(repr=False, exclude=True)
    state: DurableApprovalState = DurableApprovalState.PENDING
    requested_at: datetime
    expires_at: datetime
    revision: int = Field(default=1, gt=0)
    decision_id: str | None = None
    decision: ApprovalDecisionType | None = None
    decided_by: str | None = None
    decided_at: datetime | None = None
    resumed_at: datetime | None = None
    resume_outcome: ResumeOutcome | None = None

    @field_validator("requested_at", "expires_at", "decided_at", "resumed_at")
    @classmethod
    def validate_timestamp(cls, value: datetime | None) -> datetime | None:
        """Require timezone-aware durable timestamps."""
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Os timestamps HITL devem possuir fuso horário.")
        return value

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Self:
        """Keep request, decision, and resume facts internally coherent."""
        if self.expires_at <= self.requested_at:
            raise ValueError("A expiração HITL deve ocorrer após a solicitação.")
        decision_fields = (
            self.decision_id,
            self.decision,
            self.decided_by,
            self.decided_at,
        )
        has_decision = all(value is not None for value in decision_fields)
        if any(value is not None for value in decision_fields) and not has_decision:
            raise ValueError("A decisão HITL persistida está incompleta.")
        if self.state is DurableApprovalState.PENDING and has_decision:
            raise ValueError("Uma aprovação pendente não pode possuir decisão.")
        if (
            self.state
            in {
                DurableApprovalState.APPROVED,
                DurableApprovalState.REJECTED,
                DurableApprovalState.RESUMED,
            }
            and not has_decision
        ):
            raise ValueError("O estado HITL exige uma decisão persistida.")
        if self.state is DurableApprovalState.RESUMED and (
            self.resumed_at is None or self.resume_outcome is None
        ):
            raise ValueError("Uma retomada deve possuir timestamp e resultado.")
        return self


class ApprovalSubmission(BaseModel):
    """Describe one authenticated and idempotent human decision command."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_id: str
    approval_request_id: str
    execution_id: str
    tenant_id: str
    tool_call_id: str
    tool_name: str
    decision: ApprovalDecisionType
    principal: TrustedApprovalPrincipal
    decided_at: datetime
    reason: str | None = None

    @field_validator("decided_at")
    @classmethod
    def validate_decided_at(cls, value: datetime) -> datetime:
        """Require an unambiguous command timestamp."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("O timestamp da decisão deve possuir fuso horário.")
        return value


class ApprovalAuditEvent(BaseModel):
    """Expose non-secret durable audit evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str
    approval_request_id: str
    execution_id: str
    tenant_id: str
    event_type: str
    actor_subject: str | None
    occurred_at: datetime
    details: dict[str, object] = Field(default_factory=dict)


class DurableApprovalRepository(Protocol):
    """Persist approval state and security audit facts transactionally."""

    async def create(self, record: DurableApprovalRecord) -> None:
        """Create one request and its audit event atomically."""
        ...

    async def get(self, approval_request_id: str) -> DurableApprovalRecord | None:
        """Read one request by its non-secret identifier."""
        ...

    async def decide(self, *, submission: ApprovalSubmission) -> DurableApprovalRecord:
        """Persist at most one compatible decision and audit event."""
        ...

    async def record_resume(
        self,
        *,
        approval_request_id: str,
        outcome: ResumeOutcome,
        occurred_at: datetime,
    ) -> DurableApprovalRecord:
        """Persist a resume outcome without reactivating the capability."""
        ...

    async def audit_events(
        self, approval_request_id: str
    ) -> tuple[ApprovalAuditEvent, ...]:
        """Return ordered durable audit evidence."""
        ...


class DurableApprovalService:
    """Authorize scoped decisions before Atlas consumes a resume token."""

    DECIDE_PERMISSION = "atlas:hitl:decide"

    def __init__(
        self,
        repository: DurableApprovalRepository,
        *,
        token_hmac_key: bytes,
    ) -> None:
        """Use an injected repository and a host-owned verifier key."""
        if len(token_hmac_key) < 32:
            raise ValueError("A chave HMAC do HITL deve possuir ao menos 32 bytes.")
        self._repository = repository
        self._token_hmac_key = token_hmac_key

    async def register(
        self,
        *,
        approval_request_id: str,
        execution_id: str,
        tenant_id: str,
        agent_id: str,
        tool_call_id: str,
        tool_name: str,
        backend: str,
        resume_token: str,
        requested_at: datetime,
        expires_at: datetime,
    ) -> DurableApprovalRecord:
        """Persist a scoped verifier after Atlas creates a suspension."""
        record = DurableApprovalRecord(
            approval_request_id=approval_request_id,
            execution_id=execution_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            backend=backend,
            token_digest=self._digest(resume_token),
            requested_at=requested_at,
            expires_at=expires_at,
        )
        await self._repository.create(record)
        return record

    async def authorize(
        self,
        *,
        resume_token: str,
        submission: ApprovalSubmission,
        now: datetime | None = None,
    ) -> ApprovalDecision:
        """Validate bearer, binding, identity, expiry, and decision atomically."""
        current = await self._repository.get(submission.approval_request_id)
        if current is None:
            raise ApprovalNotFoundError("A solicitação de aprovação não existe.")
        instant = now or datetime.now(UTC)
        self._validate_submission(current, submission, resume_token, instant)
        decided = await self._repository.decide(submission=submission)
        if decided.decision is None or decided.decided_at is None:
            raise ApprovalPersistenceError("A decisão durável não foi confirmada.")
        return ApprovalDecision(
            approval_request_id=decided.approval_request_id,
            decision=decided.decision,
            decided_at=decided.decided_at,
            decided_by=ExecutionIdentity(subject=submission.principal.subject),
            reason=submission.reason,
            metadata={"decision_id": submission.decision_id},
        )

    async def record_resume(
        self,
        *,
        approval_request_id: str,
        outcome: ResumeOutcome,
        occurred_at: datetime | None = None,
    ) -> DurableApprovalRecord:
        """Persist the outcome separately from best-effort telemetry."""
        return await self._repository.record_resume(
            approval_request_id=approval_request_id,
            outcome=outcome,
            occurred_at=occurred_at or datetime.now(UTC),
        )

    def _validate_submission(
        self,
        record: DurableApprovalRecord,
        submission: ApprovalSubmission,
        resume_token: str,
        now: datetime,
    ) -> None:
        if not hmac.compare_digest(record.token_digest, self._digest(resume_token)):
            raise ApprovalAuthorizationError("A credencial de retomada é inválida.")
        if now >= record.expires_at:
            raise ApprovalExpiredError("A solicitação de aprovação expirou.")
        if submission.principal.tenant_id != record.tenant_id:
            raise ApprovalAuthorizationError("A identidade não pertence ao tenant.")
        if self.DECIDE_PERMISSION not in submission.principal.permissions:
            raise ApprovalAuthorizationError("A identidade não pode decidir HITL.")
        if (
            submission.principal.tool_names
            and record.tool_name not in submission.principal.tool_names
        ):
            raise ApprovalAuthorizationError(
                "A identidade não pode aprovar a ferramenta."
            )
        expected = (
            record.approval_request_id,
            record.execution_id,
            record.tenant_id,
            record.tool_call_id,
            record.tool_name,
        )
        received = (
            submission.approval_request_id,
            submission.execution_id,
            submission.tenant_id,
            submission.tool_call_id,
            submission.tool_name,
        )
        if not hmac.compare_digest("\x00".join(expected), "\x00".join(received)):
            raise ApprovalAuthorizationError(
                "A decisão não corresponde ao escopo HITL."
            )

    def _digest(self, token: str) -> str:
        if not token:
            raise ApprovalAuthorizationError("A credencial de retomada é inválida.")
        return hmac.new(
            self._token_hmac_key,
            token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()


_SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS atlas_agent;

CREATE TABLE IF NOT EXISTS atlas_agent.hitl_approvals (
    approval_request_id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL UNIQUE,
    tenant_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    tool_call_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    backend TEXT NOT NULL CHECK (backend IN ('postgresql', 'redis')),
    token_digest CHAR(64) NOT NULL UNIQUE,
    state TEXT NOT NULL CHECK (
        state IN ('pending', 'approved', 'rejected', 'resumed', 'expired')
    ),
    requested_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revision BIGINT NOT NULL DEFAULT 1 CHECK (revision > 0),
    decision_id TEXT UNIQUE,
    decision TEXT CHECK (decision IN ('approve', 'reject')),
    decided_by TEXT,
    decided_at TIMESTAMPTZ,
    resumed_at TIMESTAMPTZ,
    resume_outcome TEXT CHECK (
        resume_outcome IN (
            'completed', 'rejected', 'already_consumed', 'failed', 'outcome_unknown'
        )
    ),
    CHECK (expires_at > requested_at),
    CHECK (
        (decision_id IS NULL AND decision IS NULL AND decided_by IS NULL
         AND decided_at IS NULL)
        OR
        (decision_id IS NOT NULL AND decision IS NOT NULL AND decided_by IS NOT NULL
         AND decided_at IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS atlas_agent.hitl_audit_events (
    sequence BIGSERIAL PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    approval_request_id TEXT NOT NULL
        REFERENCES atlas_agent.hitl_approvals(approval_request_id),
    execution_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor_subject TEXT,
    occurred_at TIMESTAMPTZ NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS hitl_audit_approval_sequence_idx
ON atlas_agent.hitl_audit_events (approval_request_id, sequence);
"""

_INSERT_APPROVAL_SQL = """
INSERT INTO atlas_agent.hitl_approvals (
    approval_request_id, execution_id, tenant_id, agent_id, tool_call_id,
    tool_name, backend, token_digest, state, requested_at, expires_at, revision,
    decision_id, decision, decided_by, decided_at, resumed_at, resume_outcome
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s)
ON CONFLICT DO NOTHING
"""

_SELECT_APPROVAL_SQL = """
SELECT approval_request_id, execution_id, tenant_id, agent_id, tool_call_id,
       tool_name, backend, token_digest, state, requested_at, expires_at,
       revision, decision_id, decision, decided_by, decided_at, resumed_at,
       resume_outcome
FROM atlas_agent.hitl_approvals
WHERE approval_request_id = %s
"""

_SELECT_APPROVAL_FOR_UPDATE_SQL = """
SELECT approval_request_id, execution_id, tenant_id, agent_id, tool_call_id,
       tool_name, backend, token_digest, state, requested_at, expires_at,
       revision, decision_id, decision, decided_by, decided_at, resumed_at,
       resume_outcome
FROM atlas_agent.hitl_approvals
WHERE approval_request_id = %s
FOR UPDATE
"""

_DECIDE_SQL = """
UPDATE atlas_agent.hitl_approvals
SET state = %s, decision_id = %s, decision = %s,
    decided_by = %s, decided_at = %s, revision = revision + 1
WHERE approval_request_id = %s AND state = 'pending'
  AND expires_at > clock_timestamp()
RETURNING approval_request_id, execution_id, tenant_id, agent_id, tool_call_id,
          tool_name, backend, token_digest, state, requested_at, expires_at,
          revision, decision_id, decision, decided_by, decided_at, resumed_at,
          resume_outcome
"""

_RECORD_RESUME_SQL = """
UPDATE atlas_agent.hitl_approvals
SET state = 'resumed', resumed_at = %s, resume_outcome = %s,
    revision = revision + 1
WHERE approval_request_id = %s
  AND state IN ('approved', 'rejected')
RETURNING approval_request_id, execution_id, tenant_id, agent_id, tool_call_id,
          tool_name, backend, token_digest, state, requested_at, expires_at,
          revision, decision_id, decision, decided_by, decided_at, resumed_at,
          resume_outcome
"""


class PostgreSQLDurableApprovalRepository:
    """Store approvals and an append-only audit trail in PostgreSQL."""

    def __init__(self, pool: AsyncConnectionPool[Any]) -> None:
        """Use a caller-owned pool without changing its lifecycle."""
        self._pool = pool

    async def migrate(self) -> None:
        """Create the additive host-owned DS-014 schema idempotently."""
        try:
            async with self._pool.connection() as connection:
                await connection.execute(_SCHEMA_SQL)
        except (DatabaseError, PoolTimeout) as error:
            raise ApprovalPersistenceError(
                "Não foi possível preparar a persistência HITL."
            ) from error

    async def create(self, record: DurableApprovalRecord) -> None:
        """Create a request and its first audit event in one transaction."""
        try:
            async with self._pool.connection() as connection:
                cursor = await connection.execute(
                    _INSERT_APPROVAL_SQL, self._record_values(record)
                )
                if cursor.rowcount != 1:
                    raise ApprovalConflictError("A solicitação HITL já foi registrada.")
                await self._insert_audit(
                    connection,
                    record=record,
                    event_type="approval.requested",
                    actor_subject=None,
                    occurred_at=record.requested_at,
                    details={"backend": record.backend, "tool_name": record.tool_name},
                )
        except ApprovalConflictError:
            raise
        except (DatabaseError, PoolTimeout) as error:
            raise ApprovalPersistenceError(
                "Não foi possível persistir a solicitação HITL."
            ) from error

    async def get(self, approval_request_id: str) -> DurableApprovalRecord | None:
        """Read one durable approval without returning the bearer token."""
        try:
            async with self._pool.connection() as connection:
                cursor = await connection.execute(
                    _SELECT_APPROVAL_SQL, (approval_request_id,)
                )
                row = await cursor.fetchone()
        except (DatabaseError, PoolTimeout) as error:
            raise ApprovalPersistenceError(
                "Não foi possível consultar a solicitação HITL."
            ) from error
        return None if row is None else self._record(row)

    async def decide(self, *, submission: ApprovalSubmission) -> DurableApprovalRecord:
        """Linearize one decision and preserve idempotent retries."""
        state = (
            DurableApprovalState.APPROVED
            if submission.decision is ApprovalDecisionType.APPROVE
            else DurableApprovalState.REJECTED
        )
        try:
            async with self._pool.connection() as connection:
                cursor = await connection.execute(
                    _DECIDE_SQL,
                    (
                        state.value,
                        submission.decision_id,
                        submission.decision.value,
                        submission.principal.subject,
                        submission.decided_at,
                        submission.approval_request_id,
                    ),
                )
                row = await cursor.fetchone()
                if row is None:
                    existing = await self._select_for_update(
                        connection, submission.approval_request_id
                    )
                    if existing is None:
                        raise ApprovalNotFoundError(
                            "A solicitação de aprovação não existe."
                        )
                    if existing.expires_at <= datetime.now(UTC):
                        raise ApprovalExpiredError(
                            "A solicitação de aprovação expirou."
                        )
                    if not self._same_decision(existing, submission):
                        raise ApprovalConflictError(
                            "A solicitação já possui uma decisão incompatível."
                        )
                    return existing
                record = self._record(row)
                await self._insert_audit(
                    connection,
                    record=record,
                    event_type="approval.decided",
                    actor_subject=submission.principal.subject,
                    occurred_at=submission.decided_at,
                    details={
                        "decision": submission.decision.value,
                        "decision_id": submission.decision_id,
                    },
                )
                return record
        except (
            ApprovalConflictError,
            ApprovalExpiredError,
            ApprovalNotFoundError,
        ):
            raise
        except (DatabaseError, PoolTimeout) as error:
            raise ApprovalPersistenceError(
                "Não foi possível persistir a decisão HITL."
            ) from error

    async def record_resume(
        self,
        *,
        approval_request_id: str,
        outcome: ResumeOutcome,
        occurred_at: datetime,
    ) -> DurableApprovalRecord:
        """Record one final resume classification idempotently."""
        try:
            async with self._pool.connection() as connection:
                cursor = await connection.execute(
                    _RECORD_RESUME_SQL,
                    (occurred_at, outcome.value, approval_request_id),
                )
                row = await cursor.fetchone()
                if row is None:
                    existing = await self._select_for_update(
                        connection, approval_request_id
                    )
                    if existing is None:
                        raise ApprovalNotFoundError(
                            "A solicitação de aprovação não existe."
                        )
                    if (
                        existing.state is DurableApprovalState.RESUMED
                        and existing.resume_outcome is outcome
                    ):
                        return existing
                    raise ApprovalConflictError(
                        "A retomada não é válida para o estado HITL atual."
                    )
                record = self._record(row)
                await self._insert_audit(
                    connection,
                    record=record,
                    event_type="approval.resumed",
                    actor_subject=record.decided_by,
                    occurred_at=occurred_at,
                    details={"outcome": outcome.value},
                )
                return record
        except (ApprovalConflictError, ApprovalNotFoundError):
            raise
        except (DatabaseError, PoolTimeout) as error:
            raise ApprovalPersistenceError(
                "Não foi possível registrar a retomada HITL."
            ) from error

    async def audit_events(
        self, approval_request_id: str
    ) -> tuple[ApprovalAuditEvent, ...]:
        """Read the ordered durable audit stream."""
        try:
            async with self._pool.connection() as connection:
                cursor = await connection.execute(
                    """SELECT event_id, approval_request_id, execution_id, tenant_id,
                              event_type, actor_subject, occurred_at, details
                       FROM atlas_agent.hitl_audit_events
                       WHERE approval_request_id = %s
                       ORDER BY sequence""",
                    (approval_request_id,),
                )
                rows = await cursor.fetchall()
        except (DatabaseError, PoolTimeout) as error:
            raise ApprovalPersistenceError(
                "Não foi possível consultar a auditoria HITL."
            ) from error
        return tuple(
            ApprovalAuditEvent(
                event_id=str(row[0]),
                approval_request_id=str(row[1]),
                execution_id=str(row[2]),
                tenant_id=str(row[3]),
                event_type=str(row[4]),
                actor_subject=None if row[5] is None else str(row[5]),
                occurred_at=row[6],
                details=dict(row[7]),
            )
            for row in rows
        )

    async def _select_for_update(
        self, connection: AsyncConnection[Any], approval_request_id: str
    ) -> DurableApprovalRecord | None:
        cursor = await connection.execute(
            _SELECT_APPROVAL_FOR_UPDATE_SQL, (approval_request_id,)
        )
        row = await cursor.fetchone()
        return None if row is None else self._record(row)

    @staticmethod
    async def _insert_audit(
        connection: AsyncConnection[Any],
        *,
        record: DurableApprovalRecord,
        event_type: str,
        actor_subject: str | None,
        occurred_at: datetime,
        details: dict[str, object],
    ) -> None:
        from psycopg.types.json import Jsonb

        await connection.execute(
            """INSERT INTO atlas_agent.hitl_audit_events (
                   event_id, approval_request_id, execution_id, tenant_id,
                   event_type, actor_subject, occurred_at, details
               ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                f"audit-{uuid4().hex}",
                record.approval_request_id,
                record.execution_id,
                record.tenant_id,
                event_type,
                actor_subject,
                occurred_at,
                Jsonb(details),
            ),
        )

    @staticmethod
    def _record(row: Sequence[object]) -> DurableApprovalRecord:
        return DurableApprovalRecord(
            approval_request_id=str(row[0]),
            execution_id=str(row[1]),
            tenant_id=str(row[2]),
            agent_id=str(row[3]),
            tool_call_id=str(row[4]),
            tool_name=str(row[5]),
            backend=str(row[6]),
            token_digest=str(row[7]),
            state=DurableApprovalState(str(row[8])),
            requested_at=cast(datetime, row[9]),
            expires_at=cast(datetime, row[10]),
            revision=int(row[11]),
            decision_id=None if row[12] is None else str(row[12]),
            decision=(None if row[13] is None else ApprovalDecisionType(str(row[13]))),
            decided_by=None if row[14] is None else str(row[14]),
            decided_at=cast(datetime | None, row[15]),
            resumed_at=cast(datetime | None, row[16]),
            resume_outcome=(None if row[17] is None else ResumeOutcome(str(row[17]))),
        )

    @staticmethod
    def _record_values(record: DurableApprovalRecord) -> tuple[object, ...]:
        return (
            record.approval_request_id,
            record.execution_id,
            record.tenant_id,
            record.agent_id,
            record.tool_call_id,
            record.tool_name,
            record.backend,
            record.token_digest,
            record.state.value,
            record.requested_at,
            record.expires_at,
            record.revision,
            record.decision_id,
            None if record.decision is None else record.decision.value,
            record.decided_by,
            record.decided_at,
            record.resumed_at,
            None if record.resume_outcome is None else record.resume_outcome.value,
        )

    @staticmethod
    def _same_decision(
        record: DurableApprovalRecord, submission: ApprovalSubmission
    ) -> bool:
        return (
            record.decision_id == submission.decision_id
            and record.decision is submission.decision
            and record.decided_by == submission.principal.subject
        )
