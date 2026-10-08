import pytest
from pydantic import ValidationError

from atlas_agents.runtime.failure_recovery import (
    ConservativeRecoverySafetyPolicy,
    ExternalEffectStatus,
    RecoveryFailureCategory,
    RecoverySafetyContext,
    RecoverySafetyDecision,
)


def context(**changes: object) -> RecoverySafetyContext:
    values: dict[str, object] = {
        "execution_id": "execution-ds012",
        "category": RecoveryFailureCategory.PROCESS_CRASH,
        "authorization_verified": True,
        "ownership_verified": True,
    }
    values.update(changes)
    return RecoverySafetyContext.model_validate(values)


@pytest.mark.parametrize(
    ("changes", "expected", "reason"),
    [
        ({}, RecoverySafetyDecision.SAFE_TO_RESUME, "durable_state_verified"),
        ({"terminal": True}, RecoverySafetyDecision.TERMINAL, "terminal"),
        ({"cancelled": True}, RecoverySafetyDecision.BLOCKED, "cancelled"),
        (
            {"deadline_exceeded": True},
            RecoverySafetyDecision.BLOCKED,
            "deadline_exceeded",
        ),
        (
            {"authorization_verified": False},
            RecoverySafetyDecision.BLOCKED,
            "authorization_not_verified",
        ),
        (
            {"ownership_verified": False},
            RecoverySafetyDecision.BLOCKED,
            "ownership_not_verified",
        ),
        (
            {"external_effect": ExternalEffectStatus.UNKNOWN},
            RecoverySafetyDecision.RECONCILIATION_REQUIRED,
            "external_effect_unknown",
        ),
        (
            {
                "external_effect": ExternalEffectStatus.UNKNOWN,
                "idempotent_retry_verified": True,
            },
            RecoverySafetyDecision.SAFE_TO_RESUME,
            "idempotent_retry_verified",
        ),
        (
            {"external_effect": ExternalEffectStatus.EXECUTED},
            RecoverySafetyDecision.RECONCILIATION_REQUIRED,
            "external_effect_requires_reconciliation",
        ),
        (
            {
                "external_effect": ExternalEffectStatus.EXECUTED,
                "reconciliation_verified": True,
            },
            RecoverySafetyDecision.SAFE_TO_RESUME,
            "external_effect_reconciled",
        ),
    ],
)
def test_safety_policy_is_fail_closed(
    changes: dict[str, object],
    expected: RecoverySafetyDecision,
    reason: str,
) -> None:
    result = ConservativeRecoverySafetyPolicy().assess(context(**changes))
    assert result.decision is expected
    assert result.reason_code == reason


@pytest.mark.parametrize(
    "category",
    [
        RecoveryFailureCategory.PERMANENT_INFRASTRUCTURE,
        RecoveryFailureCategory.STATE_CORRUPTION,
        RecoveryFailureCategory.OWNERSHIP_LOSS,
        RecoveryFailureCategory.AUTHORIZATION_FAILURE,
        RecoveryFailureCategory.AMBIGUOUS_COMMIT,
        RecoveryFailureCategory.EXTERNAL_SIDE_EFFECT_UNKNOWN,
    ],
)
def test_unsafe_categories_do_not_receive_generic_retry(
    category: RecoveryFailureCategory,
) -> None:
    result = ConservativeRecoverySafetyPolicy().assess(context(category=category))
    assert result.decision is RecoverySafetyDecision.BLOCKED


def test_unknown_effect_cannot_be_claimed_as_reconciled() -> None:
    with pytest.raises(ValidationError):
        context(
            external_effect=ExternalEffectStatus.UNKNOWN,
            reconciliation_verified=True,
        )
