from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from atlas_agents import (
    AgentRuntime,
    AgentRuntimeRecoveryInvoker,
    ApprovalDecision,
    ApprovalDecisionType,
    AuthorizedHITLRecoveryPolicy,
    CheckpointLease,
    CheckpointLeaseConflictError,
    ConservativeRecoveryEligibilityPolicy,
    ExecutionCheckpoint,
    ExecutionIdentity,
    ExecutionRecoveryCoordinator,
    RecoveryAttempt,
    RecoveryAttemptResult,
    RecoveryBatchResult,
    RecoveryCandidate,
    RecoveryDecision,
    RecoveryEligibilityPolicy,
    RecoveryInvocationResult,
    RecoveryOutcome,
    RecoveryPolicy,
    RecoveryResumeRequest,
    ResumeToken,
)

FIXTURE = (
    Path(__file__).parents[1] / "fixtures/checkpoints/execution-checkpoint-v1.json"
)


def checkpoint() -> ExecutionCheckpoint:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["transitions"] = [
        {
            "from_status": source,
            "to_status": target,
            "timestamp": "2026-01-01T00:00:00Z",
            "reason": None,
            "metadata": {},
        }
        for source, target in (
            ("created", "validating_input"),
            ("validating_input", "loading_context"),
            ("loading_context", "running"),
            ("running", "waiting_for_tool"),
            ("waiting_for_tool", "waiting_for_approval"),
        )
    ]
    payload["pending_approval"]["expires_at"] = (
        datetime.now(UTC) + timedelta(hours=1)
    ).isoformat()
    return ExecutionCheckpoint.model_validate(payload)


def candidate(value: ExecutionCheckpoint | None = None) -> RecoveryCandidate:
    current = value or checkpoint()
    return RecoveryCandidate(
        execution_id=current.execution_id,
        checkpoint_id="opaque-checkpoint-key",
        agent_id=current.agent.agent_id,
        checkpoint_version=current.checkpoint_version,
        status=current.status,
        discovered_at=datetime.now(UTC),
        tenant_id=current.context.tenant_id,
    )


class Repository:
    def __init__(self, candidates: tuple[RecoveryCandidate, ...]) -> None:
        self.candidates = candidates
        self.loaded = checkpoint()

    async def list_candidates(
        self, *, limit: int, tenant_id: str | None = None
    ) -> tuple[RecoveryCandidate, ...]:
        del tenant_id
        return self.candidates[:limit]

    async def load_checkpoint(
        self, candidate: RecoveryCandidate
    ) -> ExecutionCheckpoint:
        del candidate
        return self.loaded


class Eligible:
    def __init__(self) -> None:
        self.evaluations = 0

    async def evaluate(
        self,
        *,
        candidate: RecoveryCandidate,
        checkpoint: ExecutionCheckpoint | None,
    ) -> RecoveryDecision:
        del candidate, checkpoint
        self.evaluations += 1
        return RecoveryDecision.ELIGIBLE


class Leases:
    def __init__(self, *, conflict: bool = False) -> None:
        self.conflict = conflict
        self.released = 0

    async def acquire(
        self, *, checkpoint_id: str, owner_id: str, duration: timedelta
    ) -> CheckpointLease:
        if self.conflict:
            raise CheckpointLeaseConflictError("conflito")
        acquired_at = datetime.now(UTC)
        return CheckpointLease(
            checkpoint_id=checkpoint_id,
            owner_id=owner_id,
            fencing_token=1,
            acquired_at=acquired_at,
            expires_at=acquired_at + duration,
        )

    async def renew(
        self, *, lease: CheckpointLease, duration: timedelta
    ) -> CheckpointLease:
        del duration
        return lease

    async def release(self, *, lease: CheckpointLease) -> None:
        del lease
        self.released += 1


class Recorder:
    def __init__(self, *, admitted: bool = True, fail_completion: bool = False) -> None:
        self.admitted = admitted
        self.fail_completion = fail_completion
        self.completed: list[RecoveryOutcome] = []

    async def begin_attempt(
        self,
        *,
        candidate: RecoveryCandidate,
        lease: CheckpointLease,
        max_attempts: int,
    ) -> RecoveryAttempt | None:
        del max_attempts
        if not self.admitted:
            return None
        return RecoveryAttempt(
            attempt_id="attempt-1",
            execution_id=candidate.execution_id,
            checkpoint_id=candidate.checkpoint_id,
            attempt_number=1,
            owner_id=lease.owner_id,
            fencing_token=lease.fencing_token,
            started_at=datetime.now(UTC),
        )

    async def complete_attempt(
        self,
        *,
        attempt: RecoveryAttempt,
        lease: CheckpointLease,
        outcome: RecoveryOutcome,
        reason_code: str | None,
    ) -> None:
        del attempt, lease, reason_code
        if self.fail_completion:
            raise RuntimeError("falha ao persistir resultado")
        self.completed.append(outcome)


class Invoker:
    def __init__(
        self,
        outcome: RecoveryOutcome = RecoveryOutcome.RECOVERED,
        *,
        error: BaseException | None = None,
        delay: float = 0,
    ) -> None:
        self.outcome = outcome
        self.error = error
        self.delay = delay
        self.calls = 0

    async def recover(
        self,
        *,
        candidate: RecoveryCandidate,
        checkpoint: ExecutionCheckpoint,
        lease: CheckpointLease,
    ) -> RecoveryInvocationResult:
        del candidate, checkpoint, lease
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return RecoveryInvocationResult(outcome=self.outcome)


class Resolver:
    def __init__(self, request: RecoveryResumeRequest | None) -> None:
        self.request = request

    async def resolve(
        self,
        *,
        candidate: RecoveryCandidate,
        checkpoint: ExecutionCheckpoint,
    ) -> RecoveryResumeRequest | None:
        del candidate, checkpoint
        return self.request


class RuntimeStub:
    def __init__(self) -> None:
        self.lease: CheckpointLease | None = None

    async def resume(
        self,
        *,
        resume_token: ResumeToken,
        decision: ApprovalDecision,
        lease: CheckpointLease | None = None,
    ) -> object:
        del resume_token, decision
        self.lease = lease
        return object()


def coordinator(
    repository: Repository,
    *,
    eligibility: RecoveryEligibilityPolicy | None = None,
    leases: Leases | None = None,
    recorder: Recorder | None = None,
    invoker: Invoker | None = None,
) -> ExecutionRecoveryCoordinator:
    return ExecutionRecoveryCoordinator(
        repository=repository,
        eligibility=eligibility or Eligible(),
        lease_manager=leases or Leases(),
        invoker=invoker or Invoker(),
        attempt_recorder=recorder or Recorder(),
        policy=RecoveryPolicy(owner_id="worker-1"),
    )


async def test_empty_batch_is_valid() -> None:
    result = await coordinator(Repository(())).recover_once()
    assert result == RecoveryBatchResult.from_results(())


async def test_recovery_revalidates_after_lease_and_completes_attempt() -> None:
    item = candidate()
    eligibility = Eligible()
    leases = Leases()
    recorder = Recorder()
    invoker = Invoker()

    result = await coordinator(
        Repository((item,)),
        eligibility=eligibility,
        leases=leases,
        recorder=recorder,
        invoker=invoker,
    ).recover_once()

    assert result.recovered == 1
    assert eligibility.evaluations == 2
    assert invoker.calls == 1
    assert recorder.completed == [RecoveryOutcome.RECOVERED]
    assert leases.released == 1


async def test_conservative_policy_preserves_pending_hitl() -> None:
    item = candidate()
    invoker = Invoker()
    result = await coordinator(
        Repository((item,)),
        eligibility=ConservativeRecoveryEligibilityPolicy(),
        invoker=invoker,
    ).recover_once()
    assert result.skipped == 1
    assert result.results[0].reason_code == "awaiting_approval"
    assert invoker.calls == 0


async def test_lease_conflict_and_attempt_limit_do_not_invoke() -> None:
    item = candidate()
    invoker = Invoker()
    conflict = await coordinator(
        Repository((item,)), leases=Leases(conflict=True), invoker=invoker
    ).recover_once()
    limited = await coordinator(
        Repository((item,)), recorder=Recorder(admitted=False), invoker=invoker
    ).recover_once()
    assert conflict.conflicts == 1
    assert limited.blocked == 1
    assert invoker.calls == 0


async def test_one_failure_does_not_hide_or_stop_next_candidate() -> None:
    first = candidate()
    second = first.model_copy(update={"checkpoint_id": "second"})
    invoker = Invoker(error=RuntimeError("falha"))
    result = await coordinator(
        Repository((first, second)), invoker=invoker
    ).recover_once()
    assert result.failed == 2
    assert all(item.reason_code == "recovery_failed" for item in result.results)


async def test_cancellation_is_propagated_and_releases_lease() -> None:
    item = candidate()
    leases = Leases()
    with pytest.raises(asyncio.CancelledError):
        await coordinator(
            Repository((item,)),
            leases=leases,
            invoker=Invoker(error=asyncio.CancelledError()),
        ).recover_once()
    assert leases.released == 1


async def test_timeout_is_classified_and_attempt_is_completed() -> None:
    item = candidate()
    recorder = Recorder()
    result = await ExecutionRecoveryCoordinator(
        repository=Repository((item,)),
        eligibility=Eligible(),
        lease_manager=Leases(),
        invoker=Invoker(delay=0.03),
        attempt_recorder=recorder,
        policy=RecoveryPolicy(
            owner_id="worker-1", recovery_timeout=timedelta(milliseconds=5)
        ),
    ).recover_once()
    assert result.failed == 1
    assert result.results[0].reason_code == "recovery_timeout"
    assert recorder.completed == [RecoveryOutcome.FAILED]


async def test_invalid_checkpoint_is_blocked_without_invocation() -> None:
    item = candidate()
    repository = Repository((item,))
    repository.loaded = checkpoint().model_copy(update={"checkpoint_version": 999})
    invoker = Invoker()
    result = await coordinator(repository, invoker=invoker).recover_once()
    assert result.blocked == 1
    assert result.results[0].reason_code == "unsupported_checkpoint_version"
    assert invoker.calls == 0


async def test_failed_result_persistence_never_reports_recovered() -> None:
    item = candidate()
    result = await coordinator(
        Repository((item,)), recorder=Recorder(fail_completion=True)
    ).recover_once()
    assert result.failed == 1
    assert result.recovered == 0
    assert result.results[0].reason_code == "recovery_failed"


async def test_authorized_hitl_policy_and_invoker_use_external_decision() -> None:
    current = checkpoint()
    item = candidate(current)
    assert current.pending_approval is not None
    request = RecoveryResumeRequest(
        resume_token=ResumeToken(value="opaque-resume-value"),
        decision=ApprovalDecision(
            approval_request_id=current.pending_approval.approval_request_id,
            decision=ApprovalDecisionType.APPROVE,
            decided_at=datetime.now(UTC),
            decided_by=ExecutionIdentity(subject="approver"),
        ),
    )
    resolver = Resolver(request)
    policy = AuthorizedHITLRecoveryPolicy(resolver)
    assert (
        await policy.evaluate(candidate=item, checkpoint=None)
        is RecoveryDecision.ELIGIBLE
    )
    assert (
        await policy.evaluate(candidate=item, checkpoint=current)
        is RecoveryDecision.ELIGIBLE
    )
    runtime = RuntimeStub()
    invoker = AgentRuntimeRecoveryInvoker(
        runtime=cast(AgentRuntime, runtime), resolver=resolver
    )
    lease = await Leases().acquire(
        checkpoint_id=item.execution_id,
        owner_id="worker",
        duration=timedelta(seconds=30),
    )

    result = await invoker.recover(candidate=item, checkpoint=current, lease=lease)

    assert result.outcome is RecoveryOutcome.RECOVERED
    assert runtime.lease == lease


async def test_authorized_hitl_policy_waits_without_external_decision() -> None:
    current = checkpoint()
    item = candidate(current)
    policy = AuthorizedHITLRecoveryPolicy(Resolver(None))
    assert (
        await policy.evaluate(candidate=item, checkpoint=current)
        is RecoveryDecision.AWAITING_APPROVAL
    )


def test_policy_and_batch_invariants() -> None:
    with pytest.raises(ValidationError):
        RecoveryPolicy(owner_id="worker", batch_size=0)
    with pytest.raises(ValidationError):
        RecoveryPolicy(owner_id="worker", recovery_timeout=timedelta(0))
    result = RecoveryAttemptResult(
        execution_id="execution",
        checkpoint_id="checkpoint",
        outcome=RecoveryOutcome.SKIPPED,
    )
    with pytest.raises(ValidationError):
        RecoveryBatchResult(
            discovered=1,
            recovered=1,
            started=0,
            skipped=0,
            conflicts=0,
            failed=0,
            blocked=0,
            results=(result,),
        )
