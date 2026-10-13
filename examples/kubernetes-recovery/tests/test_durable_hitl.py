"""Contract tests for the DS-014 durable HITL boundary."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from atlas_kubernetes_recovery.durable_hitl import (
    ApprovalAuditEvent,
    ApprovalAuthorizationError,
    ApprovalConflictError,
    ApprovalExpiredError,
    ApprovalNotFoundError,
    ApprovalSubmission,
    DurableApprovalRecord,
    DurableApprovalService,
    DurableApprovalState,
    ResumeOutcome,
    TrustedApprovalPrincipal,
)
from pydantic import ValidationError

from atlas_agents import ApprovalDecisionType

_KEY = b"d" * 32
_TOKEN = "opaque-resume-token-with-enough-entropy"  # noqa: S105


class MemoryApprovalRepository:
    """Serialize commands like the PostgreSQL implementation for unit tests."""

    def __init__(self) -> None:
        self.records: dict[str, DurableApprovalRecord] = {}
        self.events: list[ApprovalAuditEvent] = []
        self._lock = asyncio.Lock()

    async def create(self, record: DurableApprovalRecord) -> None:
        async with self._lock:
            if record.approval_request_id in self.records:
                raise ApprovalConflictError("duplicated")
            self.records[record.approval_request_id] = record
            self._event(record, "approval.requested", None, record.requested_at)

    async def get(self, approval_request_id: str) -> DurableApprovalRecord | None:
        return self.records.get(approval_request_id)

    async def decide(self, *, submission: ApprovalSubmission) -> DurableApprovalRecord:
        async with self._lock:
            record = self.records.get(submission.approval_request_id)
            if record is None:
                raise ApprovalNotFoundError("missing")
            if record.state is not DurableApprovalState.PENDING:
                if (
                    record.decision_id == submission.decision_id
                    and record.decision is submission.decision
                    and record.decided_by == submission.principal.subject
                ):
                    return record
                raise ApprovalConflictError("conflict")
            state = (
                DurableApprovalState.APPROVED
                if submission.decision is ApprovalDecisionType.APPROVE
                else DurableApprovalState.REJECTED
            )
            updated = record.model_copy(
                update={
                    "state": state,
                    "decision_id": submission.decision_id,
                    "decision": submission.decision,
                    "decided_by": submission.principal.subject,
                    "decided_at": submission.decided_at,
                    "revision": record.revision + 1,
                }
            )
            self.records[record.approval_request_id] = updated
            self._event(
                updated,
                "approval.decided",
                submission.principal.subject,
                submission.decided_at,
            )
            return updated

    async def record_resume(
        self,
        *,
        approval_request_id: str,
        outcome: ResumeOutcome,
        occurred_at: datetime,
    ) -> DurableApprovalRecord:
        async with self._lock:
            record = self.records.get(approval_request_id)
            if record is None:
                raise ApprovalNotFoundError("missing")
            if record.state is DurableApprovalState.RESUMED:
                if record.resume_outcome is outcome:
                    return record
                raise ApprovalConflictError("conflict")
            if record.state not in {
                DurableApprovalState.APPROVED,
                DurableApprovalState.REJECTED,
            }:
                raise ApprovalConflictError("invalid state")
            updated = record.model_copy(
                update={
                    "state": DurableApprovalState.RESUMED,
                    "resumed_at": occurred_at,
                    "resume_outcome": outcome,
                    "revision": record.revision + 1,
                }
            )
            self.records[approval_request_id] = updated
            self._event(updated, "approval.resumed", record.decided_by, occurred_at)
            return updated

    async def audit_events(
        self, approval_request_id: str
    ) -> tuple[ApprovalAuditEvent, ...]:
        return tuple(
            event
            for event in self.events
            if event.approval_request_id == approval_request_id
        )

    def _event(
        self,
        record: DurableApprovalRecord,
        event_type: str,
        actor: str | None,
        occurred_at: datetime,
    ) -> None:
        self.events.append(
            ApprovalAuditEvent(
                event_id=f"event-{uuid4().hex}",
                approval_request_id=record.approval_request_id,
                execution_id=record.execution_id,
                tenant_id=record.tenant_id,
                event_type=event_type,
                actor_subject=actor,
                occurred_at=occurred_at,
            )
        )


def principal(
    *,
    tenant_id: str = "tenant-a",
    permissions: frozenset[str] = frozenset({"atlas:hitl:decide"}),
    tools: frozenset[str] = frozenset({"dangerous_tool"}),
) -> TrustedApprovalPrincipal:
    return TrustedApprovalPrincipal(
        subject="human-a",
        tenant_id=tenant_id,
        permissions=permissions,
        tool_names=tools,
    )


def submission(
    *,
    decision: ApprovalDecisionType = ApprovalDecisionType.APPROVE,
    identity: TrustedApprovalPrincipal | None = None,
    decision_id: str = "decision-a",
    approval_request_id: str = "approval-a",
    execution_id: str = "execution-a",
    tenant_id: str = "tenant-a",
    tool_call_id: str = "call-a",
    tool_name: str = "dangerous_tool",
) -> ApprovalSubmission:
    return ApprovalSubmission(
        decision_id=decision_id,
        approval_request_id=approval_request_id,
        execution_id=execution_id,
        tenant_id=tenant_id,
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        decision=decision,
        principal=identity or principal(),
        decided_at=datetime.now(UTC),
        reason="Decisão humana explícita.",
    )


async def registered(
    *, expires_at: datetime | None = None
) -> tuple[DurableApprovalService, MemoryApprovalRepository]:
    repository = MemoryApprovalRepository()
    service = DurableApprovalService(repository, token_hmac_key=_KEY)
    now = datetime.now(UTC)
    await service.register(
        approval_request_id="approval-a",
        execution_id="execution-a",
        tenant_id="tenant-a",
        agent_id="agent-a",
        tool_call_id="call-a",
        tool_name="dangerous_tool",
        backend="postgresql",
        resume_token=_TOKEN,
        requested_at=now,
        expires_at=expires_at or now + timedelta(hours=1),
    )
    return service, repository


def test_service_requires_a_host_owned_hmac_key() -> None:
    with pytest.raises(ValueError, match="HMAC"):
        DurableApprovalService(MemoryApprovalRepository(), token_hmac_key=b"short")


def test_record_rejects_naive_or_inverted_timestamps() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError, match="fuso horário"):
        DurableApprovalRecord(
            approval_request_id="approval-a",
            execution_id="execution-a",
            tenant_id="tenant-a",
            agent_id="agent-a",
            tool_call_id="call-a",
            tool_name="tool-a",
            backend="redis",
            token_digest="digest",  # noqa: S106
            requested_at=datetime.now(),
            expires_at=now,
        )
    with pytest.raises(ValidationError, match="após"):
        DurableApprovalRecord(
            approval_request_id="approval-a",
            execution_id="execution-a",
            tenant_id="tenant-a",
            agent_id="agent-a",
            tool_call_id="call-a",
            tool_name="tool-a",
            backend="redis",
            token_digest="digest",  # noqa: S106
            requested_at=now,
            expires_at=now,
        )


def test_registration_persists_only_a_verifier_and_audit_fact() -> None:
    async def scenario() -> None:
        service, repository = await registered()
        record = await repository.get("approval-a")
        assert record is not None
        assert record.token_digest != _TOKEN
        assert _TOKEN not in record.model_dump_json()
        events = await repository.audit_events("approval-a")
        assert [event.event_type for event in events] == ["approval.requested"]
        del service

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("changed", "value"),
    [
        ("approval_request_id", "approval-b"),
        ("execution_id", "execution-b"),
        ("tenant_id", "tenant-b"),
        ("tool_call_id", "call-b"),
        ("tool_name", "other_tool"),
    ],
)
def test_authorization_rejects_every_scope_mismatch(changed: str, value: str) -> None:
    async def scenario() -> None:
        service, _ = await registered()
        command = submission(**{changed: value})
        expected = (
            ApprovalNotFoundError
            if changed == "approval_request_id"
            else ApprovalAuthorizationError
        )
        with pytest.raises(expected):
            await service.authorize(resume_token=_TOKEN, submission=command)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "identity",
    [
        principal(tenant_id="tenant-b"),
        principal(permissions=frozenset()),
        principal(tools=frozenset({"other_tool"})),
    ],
)
def test_authorization_rejects_untrusted_principal_scope(
    identity: TrustedApprovalPrincipal,
) -> None:
    async def scenario() -> None:
        service, _ = await registered()
        with pytest.raises(ApprovalAuthorizationError):
            await service.authorize(
                resume_token=_TOKEN,
                submission=submission(identity=identity),
            )

    asyncio.run(scenario())


def test_authorization_rejects_unknown_token_without_leaking_it() -> None:
    async def scenario() -> None:
        service, _ = await registered()
        with pytest.raises(ApprovalAuthorizationError) as captured:
            await service.authorize(
                resume_token="wrong-secret-token",  # noqa: S106
                submission=submission(),
            )
        assert "wrong-secret-token" not in str(captured.value)

    asyncio.run(scenario())


def test_expired_request_fails_closed() -> None:
    async def scenario() -> None:
        service, _ = await registered()
        with pytest.raises(ApprovalExpiredError):
            await service.authorize(
                resume_token=_TOKEN,
                submission=submission(),
                now=datetime.now(UTC) + timedelta(hours=2),
            )

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "decision", [ApprovalDecisionType.APPROVE, ApprovalDecisionType.REJECT]
)
def test_approve_and_reject_are_durable_and_audited(
    decision: ApprovalDecisionType,
) -> None:
    async def scenario() -> None:
        service, repository = await registered()
        result = await service.authorize(
            resume_token=_TOKEN,
            submission=submission(decision=decision),
        )
        assert result.decision is decision
        stored = await repository.get("approval-a")
        assert stored is not None
        assert stored.state is (
            DurableApprovalState.APPROVED
            if decision is ApprovalDecisionType.APPROVE
            else DurableApprovalState.REJECTED
        )
        assert [
            event.event_type for event in await repository.audit_events("approval-a")
        ] == ["approval.requested", "approval.decided"]

    asyncio.run(scenario())


def test_identical_decision_retry_is_idempotent() -> None:
    async def scenario() -> None:
        service, repository = await registered()
        command = submission()
        first = await service.authorize(resume_token=_TOKEN, submission=command)
        second = await service.authorize(resume_token=_TOKEN, submission=command)
        assert first == second
        assert len(await repository.audit_events("approval-a")) == 2

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "conflicting",
    [
        submission(decision=ApprovalDecisionType.REJECT),
        submission(decision_id="decision-b"),
        submission(
            identity=TrustedApprovalPrincipal(
                subject="human-b",
                tenant_id="tenant-a",
                permissions=frozenset({"atlas:hitl:decide"}),
                tool_names=frozenset({"dangerous_tool"}),
            )
        ),
    ],
)
def test_conflicting_decision_is_rejected(conflicting: ApprovalSubmission) -> None:
    async def scenario() -> None:
        service, _ = await registered()
        await service.authorize(resume_token=_TOKEN, submission=submission())
        with pytest.raises(ApprovalConflictError):
            await service.authorize(resume_token=_TOKEN, submission=conflicting)

    asyncio.run(scenario())


def test_one_of_one_hundred_conflicting_commands_wins() -> None:
    async def scenario() -> None:
        service, repository = await registered()
        commands = [
            submission(
                decision=(
                    ApprovalDecisionType.APPROVE
                    if index % 2 == 0
                    else ApprovalDecisionType.REJECT
                ),
                decision_id=f"decision-{index}",
            )
            for index in range(100)
        ]

        async def attempt(command: ApprovalSubmission) -> str:
            try:
                await service.authorize(resume_token=_TOKEN, submission=command)
                return "winner"
            except ApprovalConflictError:
                return "conflict"

        results = await asyncio.gather(*(attempt(command) for command in commands))
        assert results.count("winner") == 1
        assert results.count("conflict") == 99
        assert len(await repository.audit_events("approval-a")) == 2

    asyncio.run(scenario())


def test_resume_outcome_is_durable_and_idempotent() -> None:
    async def scenario() -> None:
        service, repository = await registered()
        await service.authorize(resume_token=_TOKEN, submission=submission())
        first = await service.record_resume(
            approval_request_id="approval-a",
            outcome=ResumeOutcome.COMPLETED,
        )
        second = await service.record_resume(
            approval_request_id="approval-a",
            outcome=ResumeOutcome.COMPLETED,
        )
        assert first == second
        assert first.state is DurableApprovalState.RESUMED
        assert len(await repository.audit_events("approval-a")) == 3
        with pytest.raises(ApprovalConflictError):
            await service.record_resume(
                approval_request_id="approval-a",
                outcome=ResumeOutcome.FAILED,
            )

    asyncio.run(scenario())
