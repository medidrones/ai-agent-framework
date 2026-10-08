"""Provider-neutral safety classification for failure recovery."""

from enum import StrEnum

from pydantic import field_validator, model_validator

from atlas_agents._models import _FrozenModel, _non_empty


class RecoveryFailureCategory(StrEnum):
    """Classify failures without assuming that every error is transient."""

    TRANSIENT_INFRASTRUCTURE = "transient_infrastructure"
    PERMANENT_INFRASTRUCTURE = "permanent_infrastructure"
    PROCESS_CRASH = "process_crash"
    AMBIGUOUS_COMMIT = "ambiguous_commit"
    STATE_CORRUPTION = "state_corruption"
    OWNERSHIP_LOSS = "ownership_loss"
    AUTHORIZATION_FAILURE = "authorization_failure"
    EXTERNAL_SIDE_EFFECT_UNKNOWN = "external_side_effect_unknown"
    CANCELLATION = "cancellation"
    DEADLINE_EXCEEDED = "deadline_exceeded"


class ExternalEffectStatus(StrEnum):
    """Describe only what durable evidence proves about an external effect."""

    NOT_EXECUTED = "not_executed"
    EXECUTED = "executed"
    UNKNOWN = "unknown"


class RecoverySafetyDecision(StrEnum):
    """Describe whether automatic continuation is safe."""

    SAFE_TO_RESUME = "safe_to_resume"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    BLOCKED = "blocked"
    TERMINAL = "terminal"


class RecoveryAssessment(_FrozenModel):
    """Expose an auditable recovery decision without sensitive payloads."""

    execution_id: str
    category: RecoveryFailureCategory
    decision: RecoverySafetyDecision
    reason_code: str

    @field_validator("execution_id", "reason_code")
    @classmethod
    def validate_text(cls, value: str) -> str:
        """Reject empty audit identifiers and reason codes."""
        return _non_empty(value)


class RecoverySafetyContext(_FrozenModel):
    """Carry trusted durable facts used by the fail-closed safety policy."""

    execution_id: str
    category: RecoveryFailureCategory
    external_effect: ExternalEffectStatus = ExternalEffectStatus.NOT_EXECUTED
    terminal: bool = False
    cancelled: bool = False
    deadline_exceeded: bool = False
    authorization_verified: bool = False
    ownership_verified: bool = False
    reconciliation_verified: bool = False
    idempotent_retry_verified: bool = False

    @field_validator("execution_id")
    @classmethod
    def validate_execution_id(cls, value: str) -> str:
        """Reject an empty execution identifier."""
        return _non_empty(value)

    @model_validator(mode="after")
    def validate_evidence(self) -> "RecoverySafetyContext":
        """Reject contradictory claims about an already reconciled effect."""
        if (
            self.reconciliation_verified
            and self.external_effect is ExternalEffectStatus.UNKNOWN
        ):
            raise ValueError(
                "A reconciliação não pode permanecer verificada com efeito desconhecido"
            )
        return self


class ConservativeRecoverySafetyPolicy:
    """Allow continuation only when durable safety evidence is sufficient."""

    def assess(self, context: RecoverySafetyContext) -> RecoveryAssessment:
        """Classify recovery deterministically and fail closed on uncertainty."""
        decision: RecoverySafetyDecision
        reason_code: str
        if context.terminal:
            decision, reason_code = RecoverySafetyDecision.TERMINAL, "terminal"
        elif (
            context.cancelled
            or context.category is RecoveryFailureCategory.CANCELLATION
        ):
            decision, reason_code = RecoverySafetyDecision.BLOCKED, "cancelled"
        elif (
            context.deadline_exceeded
            or context.category is RecoveryFailureCategory.DEADLINE_EXCEEDED
        ):
            decision, reason_code = RecoverySafetyDecision.BLOCKED, "deadline_exceeded"
        elif not context.authorization_verified:
            decision, reason_code = (
                RecoverySafetyDecision.BLOCKED,
                "authorization_not_verified",
            )
        elif not context.ownership_verified:
            decision, reason_code = (
                RecoverySafetyDecision.BLOCKED,
                "ownership_not_verified",
            )
        elif context.external_effect is ExternalEffectStatus.UNKNOWN:
            if context.idempotent_retry_verified:
                decision, reason_code = (
                    RecoverySafetyDecision.SAFE_TO_RESUME,
                    "idempotent_retry_verified",
                )
            else:
                decision, reason_code = (
                    RecoverySafetyDecision.RECONCILIATION_REQUIRED,
                    "external_effect_unknown",
                )
        elif context.external_effect is ExternalEffectStatus.EXECUTED:
            if not context.reconciliation_verified:
                decision, reason_code = (
                    RecoverySafetyDecision.RECONCILIATION_REQUIRED,
                    "external_effect_requires_reconciliation",
                )
            else:
                decision, reason_code = (
                    RecoverySafetyDecision.SAFE_TO_RESUME,
                    "external_effect_reconciled",
                )
        elif context.category in {
            RecoveryFailureCategory.PERMANENT_INFRASTRUCTURE,
            RecoveryFailureCategory.STATE_CORRUPTION,
            RecoveryFailureCategory.OWNERSHIP_LOSS,
            RecoveryFailureCategory.AUTHORIZATION_FAILURE,
            RecoveryFailureCategory.AMBIGUOUS_COMMIT,
            RecoveryFailureCategory.EXTERNAL_SIDE_EFFECT_UNKNOWN,
        }:
            decision, reason_code = (
                RecoverySafetyDecision.BLOCKED,
                context.category.value,
            )
        else:
            decision, reason_code = (
                RecoverySafetyDecision.SAFE_TO_RESUME,
                "durable_state_verified",
            )
        return RecoveryAssessment(
            execution_id=context.execution_id,
            category=context.category,
            decision=decision,
            reason_code=reason_code,
        )
