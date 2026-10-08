from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from atlas_agents.runtime import (
    CheckpointRetentionCategory,
    CheckpointRetentionClassifier,
    CheckpointRetentionPolicy,
    CheckpointRetentionSubject,
    PurgeEligibility,
)

NOW = datetime(2026, 10, 8, 12, tzinfo=UTC)


def policy(**changes: object) -> CheckpointRetentionPolicy:
    values: dict[str, object] = {
        "policy_version": "ds007-v1",
        "active_ttl": timedelta(hours=1),
        "hitl_ttl": timedelta(hours=2),
        "consumed_retention": timedelta(days=7),
        "expired_retention": timedelta(days=14),
        "terminal_retention": timedelta(days=30),
        "recovery_retention": timedelta(days=7),
    }
    values.update(changes)
    return CheckpointRetentionPolicy.model_validate(values)


def subject(**changes: object) -> CheckpointRetentionSubject:
    values: dict[str, object] = {
        "checkpoint_id": "digest",
        "execution_id": "execution",
        "category": CheckpointRetentionCategory.CONSUMED,
        "evaluated_at": NOW,
        "retention_started_at": NOW - timedelta(days=8),
    }
    values.update(changes)
    return CheckpointRetentionSubject.model_validate(values)


def test_policy_rejects_non_positive_and_below_minimum_windows() -> None:
    with pytest.raises(ValidationError):
        policy(hitl_ttl=timedelta(0))
    with pytest.raises(ValidationError):
        policy(
            minimum_retention=timedelta(days=8),
            consumed_retention=timedelta(days=7),
        )


def test_expiration_boundary_is_inclusive_and_retention_blocks_deletion() -> None:
    result = CheckpointRetentionClassifier(policy()).classify(
        subject(
            category=CheckpointRetentionCategory.WAITING_FOR_APPROVAL,
            expires_at=NOW,
            retention_started_at=NOW,
        )
    )
    assert result.category is CheckpointRetentionCategory.EXPIRED
    assert result.eligibility is PurgeEligibility.BLOCKED_BY_RETENTION


def test_classifier_preserves_active_lease_and_recovery() -> None:
    classifier = CheckpointRetentionClassifier(policy())
    assert classifier.classify(subject(active_lease=True)).eligibility is (
        PurgeEligibility.BLOCKED_BY_LEASE
    )
    assert classifier.classify(subject(active_recovery=True)).eligibility is (
        PurgeEligibility.BLOCKED_BY_RECOVERY
    )


def test_classifier_fails_closed_for_incompatible_or_undefined_records() -> None:
    classifier = CheckpointRetentionClassifier(policy())
    assert classifier.classify(subject(compatible=False)).eligibility is (
        PurgeEligibility.BLOCKED_BY_INCOMPATIBLE_SCHEMA
    )
    assert (
        classifier.classify(
            subject(retention_started_at=None, stored_retention_until=None)
        ).eligibility
        is PurgeEligibility.BLOCKED_BY_POLICY
    )
    assert (
        CheckpointRetentionClassifier(policy(legal_hold=True))
        .classify(subject())
        .eligibility
        is PurgeEligibility.BLOCKED_BY_POLICY
    )


def test_policy_expansion_extends_but_reduction_never_shortens_deadline() -> None:
    stored = NOW + timedelta(days=20)
    reduced = CheckpointRetentionClassifier(
        policy(consumed_retention=timedelta(days=2))
    ).classify(subject(stored_retention_until=stored))
    expanded = CheckpointRetentionClassifier(
        policy(consumed_retention=timedelta(days=30))
    ).classify(subject(stored_retention_until=stored))
    assert reduced.effective_retention_until == stored
    assert expanded.effective_retention_until == NOW + timedelta(days=22)


def test_elapsed_retention_only_classifies_as_eligible() -> None:
    result = CheckpointRetentionClassifier(policy()).classify(subject())
    assert result.eligibility is PurgeEligibility.ELIGIBLE
    assert result.reason_code == "retention_elapsed"


def test_terminal_state_uses_its_dedicated_retention_window() -> None:
    result = CheckpointRetentionClassifier(policy()).classify(
        subject(
            category=CheckpointRetentionCategory.TERMINAL,
            retention_started_at=NOW - timedelta(days=20),
        )
    )
    assert result.eligibility is PurgeEligibility.BLOCKED_BY_RETENTION
    assert result.effective_retention_until == NOW + timedelta(days=10)
