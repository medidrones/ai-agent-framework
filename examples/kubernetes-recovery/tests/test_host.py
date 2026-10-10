"""Unit tests for the DS-013 technical host boundary."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from typing import cast

import pytest
from atlas_kubernetes_recovery.config import HostConfiguration
from atlas_kubernetes_recovery.host import (
    ApprovalRecord,
    ApprovalState,
    ApprovedOnlyHITLRecoveryPolicy,
    CertificationHost,
    CheckpointBackend,
    FileDecisionResolver,
)
from atlas_kubernetes_recovery.worker import CertificationHttpServer
from pydantic import SecretStr, ValidationError

from atlas_agents import (
    ApprovalDecisionType,
    ExecutionStatus,
    RecoveryCandidate,
    RecoveryDecision,
    ResumeToken,
)


def configuration(tmp_path: Path) -> HostConfiguration:
    """Create a valid configuration without opening infrastructure clients."""
    return HostConfiguration(
        pod_name="worker-a",
        namespace="atlas-ds013",
        postgresql_dsn=SecretStr("postgresql://user:password@postgresql/atlas"),
        redis_url=SecretStr("redis://:password@redis:6379/0"),
        token_hmac_key=SecretStr("x" * 32),
        approval_directory=tmp_path,
    )


def record(*, state: ApprovalState) -> ApprovalRecord:
    """Build one private authorization record."""
    return ApprovalRecord(
        execution_id="execution-a",
        backend=CheckpointBackend.POSTGRESQL,
        resume_token=ResumeToken(value="opaque-token"),
        approval_request_id="approval-a",
        state=state,
        created_at=datetime.now(UTC),
    )


def test_configuration_is_immutable_and_validates_secret_length(tmp_path: Path) -> None:
    value = configuration(tmp_path)
    assert value.pod_name == "worker-a"
    with pytest.raises(ValidationError):
        HostConfiguration(
            pod_name="worker-a",
            namespace="atlas-ds013",
            postgresql_dsn=SecretStr("postgresql://example"),
            redis_url=SecretStr("redis://example"),
            token_hmac_key=SecretStr("short"),
        )


def test_pending_record_does_not_fabricate_decision() -> None:
    assert record(state=ApprovalState.PENDING).decision() is None
    approved = record(state=ApprovalState.APPROVE).decision()
    rejected = record(state=ApprovalState.REJECT).decision()
    assert approved is not None
    assert approved.decision is ApprovalDecisionType.APPROVE
    assert rejected is not None
    assert rejected.decision is ApprovalDecisionType.REJECT


def test_file_resolver_rejects_missing_or_pending_record(tmp_path: Path) -> None:
    resolver = FileDecisionResolver(tmp_path)
    assert resolver.load("missing") is None
    value = record(state=ApprovalState.PENDING)
    path = tmp_path / "execution-a.json"
    path.write_text(value.model_dump_json(), encoding="utf-8")
    assert resolver.load("execution-a") == value


def test_recovery_policy_does_not_consume_attempt_before_approval(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        resolver = FileDecisionResolver(tmp_path)
        policy = ApprovedOnlyHITLRecoveryPolicy(resolver)
        candidate = RecoveryCandidate(
            execution_id="execution-a",
            checkpoint_id="checkpoint-a",
            agent_id="agent-a",
            checkpoint_version=1,
            status=ExecutionStatus.WAITING_FOR_APPROVAL,
            discovered_at=datetime.now(UTC),
            tenant_id="tenant-ds013",
        )
        assert (
            await policy.evaluate(candidate=candidate, checkpoint=None)
            is RecoveryDecision.AWAITING_APPROVAL
        )
        path = tmp_path / "execution-a.json"
        path.write_text(
            record(state=ApprovalState.APPROVE).model_dump_json(),
            encoding="utf-8",
        )
        assert (
            await policy.evaluate(candidate=candidate, checkpoint=None)
            is RecoveryDecision.ELIGIBLE
        )

    asyncio.run(scenario())


class _HttpHost:
    async def dependencies_ready(self) -> bool:
        return True

    async def status(self) -> dict[str, object]:
        return {"ready": True}

    async def seed(
        self,
        *,
        backend: CheckpointBackend,
        execution_id: str,
        state: ApprovalState,
        tenant_id: str,
    ) -> dict[str, object]:
        return {
            "backend": backend.value,
            "execution_id": execution_id,
            "decision": state.value,
            "tenant_id": tenant_id,
        }


def test_http_routes_validate_scenario_inputs() -> None:
    async def scenario() -> None:
        server = CertificationHttpServer(cast(CertificationHost, _HttpHost()))
        status, payload = await asyncio.wait_for(
            server._route("GET", "/ready"), timeout=1
        )
        assert status is HTTPStatus.OK
        assert payload == {"status": "ready"}

        status, payload = await asyncio.wait_for(
            server._route(
                "POST",
                "/seed?backend=redis&execution_id=execution-a&decision=pending",
            ),
            timeout=1,
        )
        assert status is HTTPStatus.CREATED
        assert payload == {
            "backend": "redis",
            "execution_id": "execution-a",
            "decision": "pending",
            "tenant_id": "tenant-ds013",
        }

        with pytest.raises(ValueError, match="execution_id"):
            await asyncio.wait_for(
                server._route("POST", "/seed?backend=redis&execution_id=../../escape"),
                timeout=1,
            )

    asyncio.run(scenario())


def test_observability_audit_failure_does_not_break_host(tmp_path: Path) -> None:
    host = CertificationHost(configuration(tmp_path / "missing" / "directory"))
    host._event("atlas.certification.observability_failure")
