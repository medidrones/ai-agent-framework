"""Provider-neutral coordination contracts for durable execution recovery."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol, Self

from pydantic import Field, field_validator, model_validator

from atlas_agents._models import _FrozenModel, _non_empty, _timezone_aware
from atlas_agents.agents import ExecutionStatus
from atlas_agents.approvals import (
    ApprovalDecision,
    ApprovalDecisionType,
    ExecutionSuspension,
    InvalidCheckpointError,
    ResumeToken,
    UnsupportedCheckpointVersionError,
)
from atlas_agents.execution import is_terminal
from atlas_agents.observability import ObservabilityManager, SpanStatus
from atlas_agents.runtime.checkpoint import ExecutionCheckpoint, ExecutionMode
from atlas_agents.runtime.lease import (
    CheckpointLease,
    CheckpointLeaseConflictError,
    CheckpointLeaseLostError,
    CheckpointLeaseManager,
    CheckpointLeaseNotFoundError,
)
from atlas_agents.runtime.restorer import ExecutionStateRestorer
from atlas_agents.runtime.runtime import AgentRuntime
from atlas_agents.runtime.stream_items import RuntimeResultItem, RuntimeSuspensionItem


class RecoveryDecision(StrEnum):
    """Classify whether one durable candidate may be recovered now."""

    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    ALREADY_OWNED = "already_owned"
    AWAITING_APPROVAL = "awaiting_approval"
    TERMINAL = "terminal"
    UNSUPPORTED = "unsupported"


class RecoveryOutcome(StrEnum):
    """Describe the terminal result of one coordinator attempt."""

    RECOVERED = "recovered"
    STARTED = "started"
    SKIPPED = "skipped"
    CONFLICT = "conflict"
    FAILED = "failed"
    BLOCKED = "blocked"


class RecoveryCandidate(_FrozenModel):
    """Describe a checkpoint without exposing its serialized payload or token."""

    execution_id: str
    checkpoint_id: str
    agent_id: str
    checkpoint_version: int = Field(gt=0)
    status: ExecutionStatus
    discovered_at: datetime
    tenant_id: str | None = None

    @field_validator("execution_id", "checkpoint_id", "agent_id")
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        """Reject empty recovery identifiers."""
        return _non_empty(value)

    @field_validator("discovered_at")
    @classmethod
    def validate_discovered_at(cls, value: datetime) -> datetime:
        """Require a timezone-aware discovery timestamp."""
        return _timezone_aware(value, label="da descoberta")


class RecoveryPolicy(_FrozenModel):
    """Bound one host-triggered recovery batch without scheduling it."""

    owner_id: str
    batch_size: int = Field(default=50, gt=0)
    max_attempts: int = Field(default=3, gt=0)
    lease_duration: timedelta = timedelta(seconds=30)
    recovery_timeout: timedelta = timedelta(seconds=120)
    tenant_id: str | None = None

    @field_validator("owner_id")
    @classmethod
    def validate_owner_id(cls, value: str) -> str:
        """Reject an empty worker identifier."""
        return _non_empty(value)

    @field_validator("lease_duration", "recovery_timeout")
    @classmethod
    def validate_durations(cls, value: timedelta) -> timedelta:
        """Require positive operational durations."""
        if value <= timedelta(0):
            raise ValueError("A duração de recovery deve ser positiva")
        return value


class RecoveryAttempt(_FrozenModel):
    """Identify one durably admitted recovery generation."""

    attempt_id: str
    execution_id: str
    checkpoint_id: str
    attempt_number: int = Field(gt=0)
    owner_id: str
    fencing_token: int = Field(gt=0)
    started_at: datetime

    @field_validator("attempt_id", "execution_id", "checkpoint_id", "owner_id")
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        """Reject empty attempt identifiers."""
        return _non_empty(value)

    @field_validator("started_at")
    @classmethod
    def validate_started_at(cls, value: datetime) -> datetime:
        """Require a timezone-aware start timestamp."""
        return _timezone_aware(value, label="da tentativa")


class RecoveryInvocationResult(_FrozenModel):
    """Separate a started continuation from a confirmed completion."""

    outcome: RecoveryOutcome
    reason_code: str | None = None

    @field_validator("reason_code")
    @classmethod
    def validate_reason_code(cls, value: str | None) -> str | None:
        """Reject empty explicit reason codes."""
        return None if value is None else _non_empty(value)

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        """Restrict invokers to execution outcomes they can confirm."""
        if self.outcome not in {
            RecoveryOutcome.RECOVERED,
            RecoveryOutcome.STARTED,
            RecoveryOutcome.BLOCKED,
            RecoveryOutcome.FAILED,
        }:
            raise ValueError("O resultado do invoker não é válido para recovery")
        return self


class RecoveryResumeRequest(_FrozenModel):
    """Carry one externally authorized HITL decision in memory only."""

    resume_token: ResumeToken
    decision: ApprovalDecision


class RecoveryAttemptResult(_FrozenModel):
    """Record one candidate in exactly one terminal batch category."""

    execution_id: str
    checkpoint_id: str
    outcome: RecoveryOutcome
    reason_code: str | None = None
    attempt_number: int | None = Field(default=None, gt=0)

    @field_validator("execution_id", "checkpoint_id")
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        """Reject empty result identifiers."""
        return _non_empty(value)


class RecoveryBatchResult(_FrozenModel):
    """Summarize one finite and host-triggered recovery pass."""

    discovered: int = Field(ge=0)
    recovered: int = Field(ge=0)
    started: int = Field(ge=0)
    skipped: int = Field(ge=0)
    conflicts: int = Field(ge=0)
    failed: int = Field(ge=0)
    blocked: int = Field(ge=0)
    results: tuple[RecoveryAttemptResult, ...]

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        """Keep aggregate counters equal to individual outcomes."""
        expected = {
            RecoveryOutcome.RECOVERED: self.recovered,
            RecoveryOutcome.STARTED: self.started,
            RecoveryOutcome.SKIPPED: self.skipped,
            RecoveryOutcome.CONFLICT: self.conflicts,
            RecoveryOutcome.FAILED: self.failed,
            RecoveryOutcome.BLOCKED: self.blocked,
        }
        if self.discovered != len(self.results):
            raise ValueError("A quantidade descoberta deve corresponder aos resultados")
        if any(
            sum(item.outcome is outcome for item in self.results) != count
            for outcome, count in expected.items()
        ):
            raise ValueError("Os contadores do lote não correspondem aos resultados")
        return self

    @classmethod
    def from_results(
        cls, results: tuple[RecoveryAttemptResult, ...]
    ) -> RecoveryBatchResult:
        """Build a consistent aggregate from individual results."""
        return cls(
            discovered=len(results),
            recovered=sum(
                item.outcome is RecoveryOutcome.RECOVERED for item in results
            ),
            started=sum(item.outcome is RecoveryOutcome.STARTED for item in results),
            skipped=sum(item.outcome is RecoveryOutcome.SKIPPED for item in results),
            conflicts=sum(item.outcome is RecoveryOutcome.CONFLICT for item in results),
            failed=sum(item.outcome is RecoveryOutcome.FAILED for item in results),
            blocked=sum(item.outcome is RecoveryOutcome.BLOCKED for item in results),
            results=results,
        )


class RecoveryCandidateRepository(Protocol):
    """Discover and load durable candidates without exposing resume tokens."""

    async def list_candidates(
        self, *, limit: int, tenant_id: str | None = None
    ) -> tuple[RecoveryCandidate, ...]:
        """Return a deterministic bounded candidate list."""
        ...

    async def load_checkpoint(
        self, candidate: RecoveryCandidate
    ) -> ExecutionCheckpoint:
        """Load and validate the authoritative candidate payload."""
        ...


class RecoveryEligibilityPolicy(Protocol):
    """Decide eligibility before and after ownership acquisition."""

    async def evaluate(
        self,
        *,
        candidate: RecoveryCandidate,
        checkpoint: ExecutionCheckpoint | None,
    ) -> RecoveryDecision:
        """Classify one candidate without producing side effects."""
        ...


class ExecutionRecoveryInvoker(Protocol):
    """Continue execution only through an explicitly authorized public API."""

    async def recover(
        self,
        *,
        candidate: RecoveryCandidate,
        checkpoint: ExecutionCheckpoint,
        lease: CheckpointLease,
    ) -> RecoveryInvocationResult:
        """Invoke one authorized continuation and report what was confirmed."""
        ...


class RecoveryResumeRequestResolver(Protocol):
    """Resolve decisions from a host-owned secure authorization source."""

    async def resolve(
        self,
        *,
        candidate: RecoveryCandidate,
        checkpoint: ExecutionCheckpoint,
    ) -> RecoveryResumeRequest | None:
        """Return a request only when a real decision is available."""
        ...


class RecoveryAttemptRecorder(Protocol):
    """Persist recovery admission and outcomes across process restarts."""

    async def begin_attempt(
        self,
        *,
        candidate: RecoveryCandidate,
        lease: CheckpointLease,
        max_attempts: int,
    ) -> RecoveryAttempt | None:
        """Admit one attempt or return None when its durable limit was reached."""
        ...

    async def complete_attempt(
        self,
        *,
        attempt: RecoveryAttempt,
        lease: CheckpointLease,
        outcome: RecoveryOutcome,
        reason_code: str | None,
    ) -> None:
        """Persist an outcome only for the current fencing generation."""
        ...


class ConservativeRecoveryEligibilityPolicy:
    """Fail closed until the host supplies a verifiable recovery authorization."""

    async def evaluate(
        self,
        *,
        candidate: RecoveryCandidate,
        checkpoint: ExecutionCheckpoint | None,
    ) -> RecoveryDecision:
        """Never manufacture approval or resume a terminal execution."""
        status = checkpoint.status if checkpoint is not None else candidate.status
        if is_terminal(status):
            return RecoveryDecision.TERMINAL
        if status is ExecutionStatus.WAITING_FOR_APPROVAL:
            return RecoveryDecision.AWAITING_APPROVAL
        return RecoveryDecision.UNSUPPORTED


class AuthorizedHITLRecoveryPolicy:
    """Admit only a pending HITL checkpoint with a real approval decision."""

    def __init__(self, resolver: RecoveryResumeRequestResolver) -> None:
        """Use the same explicit authorization source as the runtime invoker."""
        self._resolver = resolver

    async def evaluate(
        self,
        *,
        candidate: RecoveryCandidate,
        checkpoint: ExecutionCheckpoint | None,
    ) -> RecoveryDecision:
        """Fail closed before authoritative state is loaded under ownership."""
        status = checkpoint.status if checkpoint is not None else candidate.status
        if is_terminal(status):
            return RecoveryDecision.TERMINAL
        if checkpoint is None:
            return (
                RecoveryDecision.ELIGIBLE
                if status is ExecutionStatus.WAITING_FOR_APPROVAL
                else RecoveryDecision.UNSUPPORTED
            )
        if checkpoint.status is not ExecutionStatus.WAITING_FOR_APPROVAL:
            return RecoveryDecision.UNSUPPORTED
        request = await self._resolver.resolve(
            candidate=candidate, checkpoint=checkpoint
        )
        if request is None:
            return RecoveryDecision.AWAITING_APPROVAL
        if request.decision.decision is ApprovalDecisionType.REJECT:
            return RecoveryDecision.NOT_ELIGIBLE
        return RecoveryDecision.ELIGIBLE


class AgentRuntimeRecoveryInvoker:
    """Continue approved HITL checkpoints through the public runtime API."""

    def __init__(
        self,
        *,
        runtime: AgentRuntime,
        resolver: RecoveryResumeRequestResolver,
    ) -> None:
        """Inject runtime and host-owned authorization resolution."""
        self._runtime = runtime
        self._resolver = resolver

    async def recover(
        self,
        *,
        candidate: RecoveryCandidate,
        checkpoint: ExecutionCheckpoint,
        lease: CheckpointLease,
    ) -> RecoveryInvocationResult:
        """Resume with atomic authorization and fencing, never from metadata."""
        request = await self._resolver.resolve(
            candidate=candidate, checkpoint=checkpoint
        )
        if request is None:
            return RecoveryInvocationResult(
                outcome=RecoveryOutcome.BLOCKED,
                reason_code="approval_not_available",
            )
        if request.decision.decision is not ApprovalDecisionType.APPROVE:
            return RecoveryInvocationResult(
                outcome=RecoveryOutcome.BLOCKED,
                reason_code="approval_not_granted",
            )
        if checkpoint.execution_mode is ExecutionMode.RUN:
            outcome = await self._runtime.resume(
                resume_token=request.resume_token,
                decision=request.decision,
                lease=lease,
            )
            return RecoveryInvocationResult(
                outcome=(
                    RecoveryOutcome.STARTED
                    if isinstance(outcome, ExecutionSuspension)
                    else RecoveryOutcome.RECOVERED
                )
            )
        final_item: RuntimeResultItem | RuntimeSuspensionItem | None = None
        async for item in self._runtime.resume_stream(
            resume_token=request.resume_token,
            decision=request.decision,
            lease=lease,
        ):
            if isinstance(item, (RuntimeResultItem, RuntimeSuspensionItem)):
                final_item = item
        if final_item is None:
            return RecoveryInvocationResult(
                outcome=RecoveryOutcome.FAILED,
                reason_code="stream_without_final_outcome",
            )
        return RecoveryInvocationResult(
            outcome=(
                RecoveryOutcome.STARTED
                if isinstance(final_item, RuntimeSuspensionItem)
                else RecoveryOutcome.RECOVERED
            )
        )


class ExecutionRecoveryCoordinator:
    """Coordinate one bounded recovery pass without owning a scheduler."""

    def __init__(
        self,
        *,
        repository: RecoveryCandidateRepository,
        eligibility: RecoveryEligibilityPolicy,
        lease_manager: CheckpointLeaseManager,
        invoker: ExecutionRecoveryInvoker,
        attempt_recorder: RecoveryAttemptRecorder,
        policy: RecoveryPolicy,
        observability: ObservabilityManager | None = None,
        state_restorer: ExecutionStateRestorer | None = None,
    ) -> None:
        """Inject every recovery dependency explicitly."""
        self._repository = repository
        self._eligibility = eligibility
        self._lease_manager = lease_manager
        self._invoker = invoker
        self._attempt_recorder = attempt_recorder
        self._policy = policy
        self._observability = observability or ObservabilityManager()
        self._state_restorer = state_restorer or ExecutionStateRestorer()

    async def recover_once(self) -> RecoveryBatchResult:
        """Discover and process one finite batch sequentially."""
        started_at = self._observability.now()
        span = self._observability.start_span(
            "atlas.execution.recovery.batch",
            attributes={"atlas.recovery.owner": self._policy.owner_id},
        )
        try:
            candidates = await self._repository.list_candidates(
                limit=self._policy.batch_size,
                tenant_id=self._policy.tenant_id,
            )
            self._observability.record(
                "atlas.recovery.candidates", float(len(candidates))
            )
            collected = [
                await self._recover_candidate(candidate) for candidate in candidates
            ]
            results = tuple(collected)
            batch = RecoveryBatchResult.from_results(results)
            span.set_status(SpanStatus.OK)
            return batch
        except asyncio.CancelledError:
            span.set_status(SpanStatus.UNSET)
            raise
        except Exception as error:
            span.record_exception(error)
            span.set_status(SpanStatus.ERROR)
            raise
        finally:
            self._observability.record(
                "atlas.recovery.duration",
                self._observability.elapsed_since(started_at),
            )
            span.end()

    async def _recover_candidate(
        self, candidate: RecoveryCandidate
    ) -> RecoveryAttemptResult:
        try:
            precheck = await self._eligibility.evaluate(
                candidate=candidate, checkpoint=None
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            result = self._result(
                candidate, RecoveryOutcome.FAILED, "eligibility_check_failed"
            )
            self._observe(result)
            return result
        if precheck is not RecoveryDecision.ELIGIBLE:
            return self._classified(candidate, precheck)
        try:
            lease = await self._lease_manager.acquire(
                checkpoint_id=candidate.execution_id,
                owner_id=self._policy.owner_id,
                duration=self._policy.lease_duration,
            )
        except CheckpointLeaseConflictError:
            return self._result(candidate, RecoveryOutcome.CONFLICT, "lease_conflict")
        except CheckpointLeaseNotFoundError:
            return self._result(
                candidate, RecoveryOutcome.SKIPPED, "checkpoint_missing"
            )

        attempt: RecoveryAttempt | None = None
        try:
            attempt = await self._attempt_recorder.begin_attempt(
                candidate=candidate,
                lease=lease,
                max_attempts=self._policy.max_attempts,
            )
            if attempt is None:
                return self._result(
                    candidate, RecoveryOutcome.BLOCKED, "attempt_limit_reached"
                )
            checkpoint = await self._repository.load_checkpoint(candidate)
            self._state_restorer.restore(checkpoint)
            decision = await self._eligibility.evaluate(
                candidate=candidate, checkpoint=checkpoint
            )
            if decision is not RecoveryDecision.ELIGIBLE:
                result = self._classified(candidate, decision, attempt.attempt_number)
            else:
                invocation = await asyncio.wait_for(
                    self._invoker.recover(
                        candidate=candidate,
                        checkpoint=checkpoint,
                        lease=lease,
                    ),
                    timeout=self._policy.recovery_timeout.total_seconds(),
                )
                result = self._result(
                    candidate,
                    invocation.outcome,
                    invocation.reason_code,
                    attempt.attempt_number,
                )
            await self._attempt_recorder.complete_attempt(
                attempt=attempt,
                lease=lease,
                outcome=result.outcome,
                reason_code=result.reason_code,
            )
            self._observe(result)
            return result
        except (InvalidCheckpointError, UnsupportedCheckpointVersionError) as error:
            reason_code = (
                "unsupported_checkpoint_version"
                if isinstance(error, UnsupportedCheckpointVersionError)
                else "invalid_checkpoint"
            )
            if attempt is not None:
                await self._complete_best_effort(
                    attempt, lease, RecoveryOutcome.BLOCKED, reason_code
                )
            result = self._result(
                candidate,
                RecoveryOutcome.BLOCKED,
                reason_code,
                None if attempt is None else attempt.attempt_number,
            )
            self._observe(result)
            return result
        except asyncio.CancelledError:
            if attempt is not None:
                await self._complete_best_effort(
                    attempt, lease, RecoveryOutcome.FAILED, "cancelled"
                )
            raise
        except TimeoutError:
            if attempt is not None:
                await self._complete_best_effort(
                    attempt, lease, RecoveryOutcome.FAILED, "recovery_timeout"
                )
            result = self._result(
                candidate,
                RecoveryOutcome.FAILED,
                "recovery_timeout",
                None if attempt is None else attempt.attempt_number,
            )
            self._observe(result)
            return result
        except CheckpointLeaseLostError:
            result = self._result(
                candidate,
                RecoveryOutcome.CONFLICT,
                "lease_lost",
                None if attempt is None else attempt.attempt_number,
            )
            self._observe(result)
            return result
        except Exception:
            if attempt is not None:
                await self._complete_best_effort(
                    attempt, lease, RecoveryOutcome.FAILED, "recovery_failed"
                )
            result = self._result(
                candidate,
                RecoveryOutcome.FAILED,
                "recovery_failed",
                None if attempt is None else attempt.attempt_number,
            )
            self._observe(result)
            return result
        finally:
            with suppress(CheckpointLeaseLostError):
                await self._lease_manager.release(lease=lease)

    async def _complete_best_effort(
        self,
        attempt: RecoveryAttempt,
        lease: CheckpointLease,
        outcome: RecoveryOutcome,
        reason_code: str,
    ) -> None:
        try:
            await self._attempt_recorder.complete_attempt(
                attempt=attempt,
                lease=lease,
                outcome=outcome,
                reason_code=reason_code,
            )
        except Exception:
            return

    def _classified(
        self,
        candidate: RecoveryCandidate,
        decision: RecoveryDecision,
        attempt_number: int | None = None,
    ) -> RecoveryAttemptResult:
        outcome = (
            RecoveryOutcome.BLOCKED
            if decision is RecoveryDecision.UNSUPPORTED
            else RecoveryOutcome.CONFLICT
            if decision is RecoveryDecision.ALREADY_OWNED
            else RecoveryOutcome.SKIPPED
        )
        result = self._result(candidate, outcome, decision.value, attempt_number)
        self._observe(result)
        return result

    @staticmethod
    def _result(
        candidate: RecoveryCandidate,
        outcome: RecoveryOutcome,
        reason_code: str | None,
        attempt_number: int | None = None,
    ) -> RecoveryAttemptResult:
        return RecoveryAttemptResult(
            execution_id=candidate.execution_id,
            checkpoint_id=candidate.checkpoint_id,
            outcome=outcome,
            reason_code=reason_code,
            attempt_number=attempt_number,
        )

    def _observe(self, result: RecoveryAttemptResult) -> None:
        self._observability.increment(
            "atlas.recovery.attempts",
            attributes={"outcome": result.outcome.value},
        )
