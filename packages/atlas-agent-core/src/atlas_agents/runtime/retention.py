"""Provider-neutral checkpoint expiration and retention contracts."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol, Self

from pydantic import field_validator, model_validator

from atlas_agents._models import _FrozenModel, _non_empty, _timezone_aware


class CheckpointRetentionCategory(StrEnum):
    """Classify the durable lifecycle facts retained for a checkpoint."""

    ACTIVE = "active"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    CONSUMED = "consumed"
    EXPIRED = "expired"
    TERMINAL = "terminal"
    RECOVERY = "recovery"


class PurgeEligibility(StrEnum):
    """Classify eligibility without authorizing physical deletion."""

    NOT_ELIGIBLE = "not_eligible"
    ELIGIBLE = "eligible"
    BLOCKED_BY_LEASE = "blocked_by_lease"
    BLOCKED_BY_RECOVERY = "blocked_by_recovery"
    BLOCKED_BY_RETENTION = "blocked_by_retention"
    BLOCKED_BY_POLICY = "blocked_by_policy"


class CheckpointRetentionPolicy(_FrozenModel):
    """Define explicit finite TTL and retention windows owned by the host."""

    policy_version: str
    active_ttl: timedelta
    hitl_ttl: timedelta
    consumed_retention: timedelta
    expired_retention: timedelta
    terminal_retention: timedelta
    recovery_retention: timedelta
    minimum_retention: timedelta = timedelta(seconds=1)
    legal_hold: bool = False

    @field_validator("policy_version")
    @classmethod
    def validate_policy_version(cls, value: str) -> str:
        """Reject an empty policy version."""
        return _non_empty(value)

    @field_validator(
        "active_ttl",
        "hitl_ttl",
        "consumed_retention",
        "expired_retention",
        "terminal_retention",
        "recovery_retention",
        "minimum_retention",
    )
    @classmethod
    def validate_duration(cls, value: timedelta) -> timedelta:
        """Reject zero and negative temporal windows."""
        if value <= timedelta(0):
            raise ValueError("A duração da política deve ser positiva")
        return value

    @model_validator(mode="after")
    def validate_minimum_retention(self) -> Self:
        """Prevent untrusted configuration from reducing retention below policy."""
        windows = (
            self.consumed_retention,
            self.expired_retention,
            self.terminal_retention,
            self.recovery_retention,
        )
        if any(window < self.minimum_retention for window in windows):
            raise ValueError("A retenção não pode ser inferior ao mínimo")
        return self

    def retention_for(self, category: CheckpointRetentionCategory) -> timedelta:
        """Return the explicit retention window for one durable category."""
        if category is CheckpointRetentionCategory.CONSUMED:
            return self.consumed_retention
        if category is CheckpointRetentionCategory.TERMINAL:
            return self.terminal_retention
        if category is CheckpointRetentionCategory.RECOVERY:
            return self.recovery_retention
        return self.expired_retention


class CheckpointRetentionSubject(_FrozenModel):
    """Carry non-sensitive temporal facts for one classification decision."""

    checkpoint_id: str
    execution_id: str
    category: CheckpointRetentionCategory
    evaluated_at: datetime
    retention_started_at: datetime | None = None
    stored_retention_until: datetime | None = None
    expires_at: datetime | None = None
    tenant_id: str | None = None
    active_lease: bool = False
    active_recovery: bool = False
    compatible: bool = True
    legal_hold: bool = False

    @field_validator("checkpoint_id", "execution_id")
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        """Reject empty durable identifiers."""
        return _non_empty(value)

    @field_validator(
        "evaluated_at",
        "retention_started_at",
        "stored_retention_until",
        "expires_at",
    )
    @classmethod
    def validate_timestamps(cls, value: datetime | None) -> datetime | None:
        """Require timezone-aware temporal facts."""
        return None if value is None else _timezone_aware(value, label="da retenção")


class CheckpointPurgeClassification(_FrozenModel):
    """Report purge eligibility without deleting or mutating durable data."""

    checkpoint_id: str
    execution_id: str
    category: CheckpointRetentionCategory
    eligibility: PurgeEligibility
    evaluated_at: datetime
    effective_retention_until: datetime | None = None
    reason_code: str
    tenant_id: str | None = None

    @field_validator("checkpoint_id", "execution_id", "reason_code")
    @classmethod
    def validate_strings(cls, value: str) -> str:
        """Reject empty classification facts."""
        return _non_empty(value)

    @field_validator("evaluated_at", "effective_retention_until")
    @classmethod
    def validate_timestamps(cls, value: datetime | None) -> datetime | None:
        """Require timezone-aware classification timestamps."""
        return (
            None if value is None else _timezone_aware(value, label="da classificação")
        )


class CheckpointRetentionRepository(Protocol):
    """Classify durable records without performing physical deletion."""

    async def classify(
        self, *, limit: int, tenant_id: str | None = None
    ) -> tuple[CheckpointPurgeClassification, ...]:
        """Return a deterministic bounded classification batch."""
        ...


class CheckpointRetentionClassifier:
    """Apply explicit policy to PostgreSQL-authoritative temporal facts."""

    def __init__(self, policy: CheckpointRetentionPolicy) -> None:
        """Use one immutable policy snapshot for a classification pass."""
        self._policy = policy

    def classify(
        self, subject: CheckpointRetentionSubject
    ) -> CheckpointPurgeClassification:
        """Classify safely without authorizing or executing deletion."""
        category = self._effective_category(subject)
        retention_until = self._effective_retention_until(subject, category)
        eligibility, reason = self._decision(subject, category, retention_until)
        return CheckpointPurgeClassification(
            checkpoint_id=subject.checkpoint_id,
            execution_id=subject.execution_id,
            category=category,
            eligibility=eligibility,
            evaluated_at=subject.evaluated_at,
            effective_retention_until=retention_until,
            reason_code=reason,
            tenant_id=subject.tenant_id,
        )

    @staticmethod
    def _effective_category(
        subject: CheckpointRetentionSubject,
    ) -> CheckpointRetentionCategory:
        if (
            subject.category
            in {
                CheckpointRetentionCategory.ACTIVE,
                CheckpointRetentionCategory.WAITING_FOR_APPROVAL,
            }
            and subject.expires_at is not None
            and subject.evaluated_at >= subject.expires_at
        ):
            return CheckpointRetentionCategory.EXPIRED
        return subject.category

    def _effective_retention_until(
        self,
        subject: CheckpointRetentionSubject,
        category: CheckpointRetentionCategory,
    ) -> datetime | None:
        if subject.retention_started_at is None:
            return subject.stored_retention_until
        policy_deadline = subject.retention_started_at + self._policy.retention_for(
            category
        )
        if subject.stored_retention_until is None:
            return policy_deadline
        return max(subject.stored_retention_until, policy_deadline)

    def _decision(
        self,
        subject: CheckpointRetentionSubject,
        category: CheckpointRetentionCategory,
        retention_until: datetime | None,
    ) -> tuple[PurgeEligibility, str]:
        if not subject.compatible:
            return PurgeEligibility.BLOCKED_BY_POLICY, "incompatible_checkpoint"
        if self._policy.legal_hold or subject.legal_hold:
            return PurgeEligibility.BLOCKED_BY_POLICY, "legal_hold"
        if subject.active_lease:
            return PurgeEligibility.BLOCKED_BY_LEASE, "active_lease"
        if subject.active_recovery:
            return PurgeEligibility.BLOCKED_BY_RECOVERY, "active_recovery"
        if category in {
            CheckpointRetentionCategory.ACTIVE,
            CheckpointRetentionCategory.WAITING_FOR_APPROVAL,
        }:
            return PurgeEligibility.NOT_ELIGIBLE, "checkpoint_active"
        if retention_until is None:
            return PurgeEligibility.BLOCKED_BY_POLICY, "retention_undefined"
        if subject.evaluated_at < retention_until:
            return PurgeEligibility.BLOCKED_BY_RETENTION, "retention_active"
        return PurgeEligibility.ELIGIBLE, "retention_elapsed"
