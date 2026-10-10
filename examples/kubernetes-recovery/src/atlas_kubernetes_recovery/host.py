"""Technical host for real Kubernetes lifecycle and recovery certification."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, ConfigDict, field_validator
from redis.asyncio import Redis

from atlas_agents import (
    AgentContext,
    AgentDefinition,
    AgentInput,
    AgentResult,
    AgentRuntimeRecoveryInvoker,
    ApprovalDecision,
    ApprovalDecisionType,
    AuthorizedHITLRecoveryPolicy,
    CheckpointNotFoundError,
    CheckpointStore,
    ExecutionCheckpoint,
    ExecutionIdentity,
    ExecutionLimits,
    ExecutionRecoveryCoordinator,
    ExecutionStatus,
    ExecutionSuspension,
    RecoveryCandidate,
    RecoveryDecision,
    RecoveryPolicy,
    RecoveryResumeRequest,
    ResumeToken,
)
from atlas_agents.adapters.checkpoints.postgresql import (
    PostgreSQLCheckpointLeaseManager,
    PostgreSQLCheckpointMigrator,
    PostgreSQLCheckpointStore,
    PostgreSQLRecoveryAttemptRecorder,
    PostgreSQLRecoveryCandidateRepository,
)
from atlas_agents.adapters.checkpoints.redis import RedisCheckpointStore
from atlas_kubernetes_recovery.config import HostConfiguration
from atlas_kubernetes_recovery.runtime_support import build_runtime


class CheckpointBackend(StrEnum):
    """Backends certified by the host."""

    POSTGRESQL = "postgresql"
    REDIS = "redis"


class ApprovalState(StrEnum):
    """Host-owned durable authorization state."""

    PENDING = "pending"
    APPROVE = "approve"
    REJECT = "reject"


class ApprovalRecord(BaseModel):
    """Persist the opaque resume capability outside the Atlas checkpoint."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    execution_id: str
    backend: CheckpointBackend
    resume_token: ResumeToken
    approval_request_id: str
    state: ApprovalState
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        """Require an unambiguous audit timestamp."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("O timestamp de aprovação deve possuir fuso horário")
        return value

    def decision(self) -> ApprovalDecision | None:
        """Build a real decision only after an explicit host transition."""
        if self.state is ApprovalState.PENDING:
            return None
        return ApprovalDecision(
            approval_request_id=self.approval_request_id,
            decision=(
                ApprovalDecisionType.APPROVE
                if self.state is ApprovalState.APPROVE
                else ApprovalDecisionType.REJECT
            ),
            decided_at=datetime.now(UTC),
            decided_by=ExecutionIdentity(subject="ds013-certification-owner"),
            reason="Decisão explícita do cenário técnico DS-013.",
        )


class FileDecisionResolver:
    """Resolve HITL decisions from a private volume owned by the host."""

    def __init__(self, directory: Path) -> None:
        """Use a private directory mounted from the authorization volume."""
        self._directory = directory

    async def resolve(
        self, *, candidate: RecoveryCandidate, checkpoint: ExecutionCheckpoint
    ) -> RecoveryResumeRequest | None:
        """Return only a matching explicitly recorded decision."""
        del checkpoint
        record = self.load(candidate.execution_id)
        if record is None or record.backend is not CheckpointBackend.POSTGRESQL:
            return None
        decision = record.decision()
        if decision is None:
            return None
        return RecoveryResumeRequest(
            resume_token=record.resume_token,
            decision=decision,
        )

    def load(self, execution_id: str) -> ApprovalRecord | None:
        """Read one validated record without exposing its token."""
        path = self._directory / f"{execution_id}.json"
        if not path.is_file():
            return None
        return ApprovalRecord.model_validate_json(path.read_text(encoding="utf-8"))


class ApprovedOnlyHITLRecoveryPolicy:
    """Avoid consuming recovery attempts before a durable decision exists."""

    def __init__(self, resolver: FileDecisionResolver) -> None:
        """Delegate authoritative checks to the public Atlas HITL policy."""
        self._resolver = resolver
        self._delegate = AuthorizedHITLRecoveryPolicy(resolver)

    async def evaluate(
        self,
        *,
        candidate: RecoveryCandidate,
        checkpoint: ExecutionCheckpoint | None,
    ) -> RecoveryDecision:
        """Fail closed during discovery until an approval is durable."""
        if checkpoint is None:
            record = self._resolver.load(candidate.execution_id)
            if record is None or record.backend is not CheckpointBackend.POSTGRESQL:
                return RecoveryDecision.AWAITING_APPROVAL
            if record.state is ApprovalState.PENDING:
                return RecoveryDecision.AWAITING_APPROVAL
            if record.state is ApprovalState.REJECT:
                return RecoveryDecision.NOT_ELIGIBLE
        return await self._delegate.evaluate(
            candidate=candidate,
            checkpoint=checkpoint,
        )


class CertificationHost:
    """Own infrastructure clients and finite recovery passes for one pod."""

    def __init__(self, configuration: HostConfiguration) -> None:
        """Keep all infrastructure dependencies explicit and pod-scoped."""
        self.configuration = configuration
        self.ready = False
        self.shutting_down = False
        self.started_at = datetime.now(UTC)
        self.recovery_attempts = 0
        self.recovery_success = 0
        self.recovery_failures = 0
        self._pool: AsyncConnectionPool[Any] | None = None
        self._redis: Redis | None = None
        self._postgresql_store: PostgreSQLCheckpointStore | None = None
        self._redis_store: RedisCheckpointStore | None = None
        self._resolver = FileDecisionResolver(configuration.approval_directory)

    async def start(self) -> None:
        """Initialize explicit dependencies before announcing readiness."""
        self.configuration.approval_directory.mkdir(parents=True, exist_ok=True)
        self.configuration.approval_directory.chmod(0o700)
        pool = AsyncConnectionPool(
            self.configuration.postgresql_dsn.get_secret_value(),
            min_size=1,
            max_size=8,
            open=False,
        )
        await pool.open(wait=True)
        await PostgreSQLCheckpointMigrator(pool).migrate()
        redis_client = Redis.from_url(
            self.configuration.redis_url.get_secret_value(),
            decode_responses=False,
        )
        await redis_client.ping()
        key = self.configuration.token_hmac_key.get_secret_value().encode("utf-8")
        self._pool = pool
        self._redis = redis_client
        self._postgresql_store = PostgreSQLCheckpointStore(pool, token_hmac_key=key)
        self._redis_store = RedisCheckpointStore(
            cast(Any, redis_client),
            namespace="atlas:ds013",
            token_hmac_key=key,
        )
        self.ready = True
        self._event("atlas.worker.started")

    async def close(self) -> None:
        """Stop accepting work and release caller-owned resources."""
        self.shutting_down = True
        self.ready = False
        self._event("atlas.worker.shutdown")
        if self._pool is not None:
            await self._pool.close()
        if self._redis is not None:
            await self._redis.aclose()

    async def dependencies_ready(self) -> bool:
        """Check readiness dependencies without changing liveness."""
        if not self.ready or self._pool is None or self._redis is None:
            return False
        try:
            async with self._pool.connection(timeout=1) as connection:
                await connection.execute("SELECT 1")
            return bool(await asyncio.wait_for(self._redis.ping(), timeout=1))
        except Exception:
            return False

    async def seed(
        self,
        *,
        backend: CheckpointBackend,
        execution_id: str,
        state: ApprovalState = ApprovalState.PENDING,
        tenant_id: str = "tenant-ds013",
    ) -> dict[str, object]:
        """Create a real suspended execution and durable host authorization record."""
        store = self._store(backend)
        runtime = build_runtime(
            checkpoint_store=store,
            redis_client=self._redis_required(),
            request_tool=True,
        )
        outcome = await runtime.run(
            agent=AgentDefinition(
                agent_id="ds013-agent",
                name="Agente de certificação DS-013",
                instructions="Execute somente a ferramenta falsa após aprovação.",
                tool_names=("record_certification_effect",),
            ),
            input_data=self._agent_input(),
            context=AgentContext(
                execution_id=execution_id,
                tenant_id=tenant_id,
                identity=ExecutionIdentity(subject="ds013-requester"),
            ),
        )
        if not isinstance(outcome, ExecutionSuspension):
            raise RuntimeError("O cenário DS-013 deveria suspender para aprovação.")
        record = ApprovalRecord(
            execution_id=execution_id,
            backend=backend,
            resume_token=outcome.resume_token,
            approval_request_id=outcome.approval_request.approval_request_id,
            state=state,
            created_at=datetime.now(UTC),
        )
        self._write_record(record)
        return {
            "execution_id": execution_id,
            "backend": backend.value,
            "status": ExecutionStatus.WAITING_FOR_APPROVAL.value,
            "decision": state.value,
            "tenant_id": tenant_id,
        }

    async def runtime_control(self, *, cancellation: bool) -> dict[str, object]:
        """Exercise runtime-owned deadline or caller cancellation inside the pod."""
        runtime = build_runtime(
            checkpoint_store=self._postgresql_store_required(),
            redis_client=self._redis_required(),
            request_tool=False,
            model_delay_seconds=1,
        )
        execution_id = f"runtime-control-{uuid4().hex}"
        task = asyncio.create_task(
            runtime.run(
                agent=AgentDefinition(
                    agent_id="ds013-runtime-control",
                    name="Controle de runtime DS-013",
                    instructions="Valide deadline e cancelamento sem efeitos externos.",
                ),
                input_data=self._agent_input(),
                context=AgentContext(
                    execution_id=execution_id,
                    tenant_id="tenant-ds013",
                    identity=ExecutionIdentity(subject="ds013-control"),
                ),
                limits=ExecutionLimits(timeout_seconds=10 if cancellation else 0.05),
            )
        )
        if cancellation:
            await asyncio.sleep(0.05)
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            status = ExecutionStatus.CANCELLED
        else:
            outcome = await task
            status = outcome.status
        return {"execution_id": execution_id, "status": status.value}

    async def arm_crash_after_effect(self, execution_id: str) -> dict[str, object]:
        """Request one deterministic process crash after the external fake effect."""
        marker = f"atlas:ds013:crash-after-effect:{execution_id}"
        await self._redis_required().set(marker, "armed", ex=300)
        return {"execution_id": execution_id, "crash_after_effect": True}

    async def arm_delay_after_effect(
        self, execution_id: str, seconds: float
    ) -> dict[str, object]:
        """Delay one recovery after its idempotent effect for lease fault injection."""
        if seconds <= 0 or seconds > 30:
            raise ValueError("O atraso deve estar entre zero e trinta segundos.")
        marker = f"atlas:ds013:delay-after-effect:{execution_id}"
        await self._redis_required().set(marker, str(seconds), ex=300)
        return {"execution_id": execution_id, "delay_after_effect": seconds}

    async def decide(
        self, *, execution_id: str, state: ApprovalState
    ) -> dict[str, object]:
        """Record an explicit approval or rejection without fabricating identity."""
        if state is ApprovalState.PENDING:
            raise ValueError("A decisão deve ser approve ou reject.")
        record = self._resolver.load(execution_id)
        if record is None:
            raise LookupError("A execução não possui aprovação pendente.")
        updated = record.model_copy(update={"state": state})
        self._write_record(updated)
        return {
            "execution_id": execution_id,
            "backend": record.backend.value,
            "decision": state.value,
        }

    async def recover_once(self) -> None:
        """Run one finite PostgreSQL pass and reconcile Redis decisions."""
        if not self.ready or self.shutting_down:
            return
        self.recovery_attempts += 1
        try:
            await self._recover_postgresql()
            await self._recover_direct_decisions()
        except asyncio.CancelledError:
            raise
        except Exception:
            self.recovery_failures += 1
            self._event("atlas.recovery.failed")

    async def status(self) -> dict[str, object]:
        """Return non-sensitive runtime and effect counters."""
        records: list[dict[str, object]] = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(
                self.configuration.approval_directory.glob("*.result.json")
            )
        ]
        return {
            "pod": self.configuration.pod_name,
            "namespace": self.configuration.namespace,
            "ready": await self.dependencies_ready(),
            "shutting_down": self.shutting_down,
            "recovery_attempts": self.recovery_attempts,
            "recovery_success": self.recovery_success,
            "recovery_failures": self.recovery_failures,
            "results": records,
        }

    async def _recover_postgresql(self) -> None:
        if self._pool is None or self._postgresql_store is None:
            return
        runtime = build_runtime(
            checkpoint_store=self._postgresql_store,
            redis_client=self._redis_required(),
            request_tool=False,
        )
        coordinator = ExecutionRecoveryCoordinator(
            repository=PostgreSQLRecoveryCandidateRepository(self._pool),
            eligibility=ApprovedOnlyHITLRecoveryPolicy(self._resolver),
            lease_manager=PostgreSQLCheckpointLeaseManager(self._pool),
            invoker=AgentRuntimeRecoveryInvoker(
                runtime=runtime,
                resolver=self._resolver,
            ),
            attempt_recorder=PostgreSQLRecoveryAttemptRecorder(self._pool),
            policy=RecoveryPolicy(
                owner_id=self.configuration.pod_name,
                batch_size=50,
                max_attempts=5,
                lease_duration=timedelta(seconds=self.configuration.lease_seconds),
                recovery_timeout=timedelta(seconds=30),
                tenant_id="tenant-ds013",
            ),
        )
        result = await coordinator.recover_once()
        for item in result.results:
            if item.outcome.value == "recovered":
                self._write_result(item.execution_id, "postgresql", "recovered")
                self.recovery_success += 1
                self._event("atlas.recovery.completed", item.execution_id)

    async def _recover_direct_decisions(self) -> None:
        for path in sorted(self.configuration.approval_directory.glob("*.json")):
            if path.name.endswith(".result.json"):
                continue
            record = ApprovalRecord.model_validate_json(
                path.read_text(encoding="utf-8")
            )
            decision = record.decision()
            if decision is None or self._result_path(record.execution_id).exists():
                continue
            if (
                record.backend is CheckpointBackend.POSTGRESQL
                and record.state is ApprovalState.APPROVE
            ):
                continue
            runtime = build_runtime(
                checkpoint_store=self._store(record.backend),
                redis_client=self._redis_required(),
                request_tool=False,
            )
            try:
                outcome = await runtime.resume(
                    resume_token=record.resume_token,
                    decision=decision,
                )
            except CheckpointNotFoundError:
                continue
            if isinstance(outcome, AgentResult):
                self._write_result(
                    record.execution_id,
                    record.backend.value,
                    outcome.status.value,
                )
                self.recovery_success += 1
                self._event("atlas.recovery.completed", record.execution_id)

    def _write_record(self, record: ApprovalRecord) -> None:
        path = self.configuration.approval_directory / f"{record.execution_id}.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(path)

    def _write_result(self, execution_id: str, backend: str, outcome: str) -> None:
        path = self._result_path(execution_id)
        payload = {
            "execution_id": execution_id,
            "backend": backend,
            "outcome": outcome,
            "worker": self.configuration.pod_name,
            "completed_at": datetime.now(UTC).isoformat(),
        }
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        temporary.chmod(0o600)
        temporary.replace(path)

    def _result_path(self, execution_id: str) -> Path:
        return self.configuration.approval_directory / f"{execution_id}.result.json"

    def _store(self, backend: CheckpointBackend) -> CheckpointStore:
        store = (
            self._postgresql_store
            if backend is CheckpointBackend.POSTGRESQL
            else self._redis_store
        )
        if store is None:
            raise RuntimeError("O backend de checkpoint ainda não foi inicializado.")
        return store

    def _redis_required(self) -> Redis:
        if self._redis is None:
            raise RuntimeError("O cliente Redis ainda não foi inicializado.")
        return self._redis

    def _postgresql_store_required(self) -> PostgreSQLCheckpointStore:
        if self._postgresql_store is None:
            raise RuntimeError("O store PostgreSQL ainda não foi inicializado.")
        return self._postgresql_store

    @staticmethod
    def _agent_input() -> AgentInput:
        return AgentInput(message="Execute o efeito técnico de certificação.")

    def _event(self, name: str, execution_id: str | None = None) -> None:
        payload = {
            "event": name,
            "pod": self.configuration.pod_name,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if execution_id is not None:
            payload["execution_id"] = execution_id
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        logging.getLogger(__name__).info("%s", serialized)
        audit_path = (
            self.configuration.approval_directory
            / f"lifecycle-{self.configuration.pod_name}.jsonl"
        )
        try:
            with audit_path.open("a", encoding="utf-8") as stream:
                stream.write(f"{serialized}\n")
            audit_path.chmod(0o600)
        except OSError:
            logging.getLogger(__name__).warning(
                '{"event":"atlas.observability.audit_write_failed"}'
            )
