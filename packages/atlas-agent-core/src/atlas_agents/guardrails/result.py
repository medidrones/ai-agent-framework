"""Immutable guardrail results and privacy-safe audit records."""

from datetime import datetime
from typing import Self

from pydantic import Field, field_validator, model_validator

from atlas_agents._models import (
    _FrozenModel,
    _json_mapping,
    _non_empty,
    _timezone_aware,
)
from atlas_agents.guardrails.stage import (
    GuardrailDecision,
    GuardrailEnforcement,
    GuardrailSeverity,
    GuardrailStage,
)


class GuardrailViolation(_FrozenModel):
    """Describe a policy signal without carrying evaluated content."""

    code: str
    message: str
    severity: GuardrailSeverity = GuardrailSeverity.MEDIUM
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("code", "message")
    @classmethod
    def validate_text(cls, value: str) -> str:
        """Reject empty violation descriptors."""
        return _non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep violation metadata JSON-compatible and isolated."""
        return _json_mapping(value)


class GuardrailTransformation(_FrozenModel):
    """Describe a deterministic transformation without storing its content."""

    kind: str
    description: str
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("kind", "description")
    @classmethod
    def validate_text(cls, value: str) -> str:
        """Reject empty transformation descriptors."""
        return _non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep transformation metadata JSON-compatible and isolated."""
        return _json_mapping(value)


class GuardrailResult[T](_FrozenModel):
    """Return one explicit, typed guardrail decision."""

    guardrail_id: str
    stage: GuardrailStage
    decision: GuardrailDecision
    enforcement: GuardrailEnforcement | None = None
    violations: tuple[GuardrailViolation, ...] = ()
    transformations: tuple[GuardrailTransformation, ...] = ()
    output: T | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("guardrail_id")
    @classmethod
    def validate_guardrail_id(cls, value: str) -> str:
        """Reject an empty guardrail identifier."""
        return _non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep result metadata JSON-compatible and isolated."""
        return _json_mapping(value)

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        """Enforce explicit allow, transform, and reject invariants."""
        if self.decision is GuardrailDecision.ALLOW:
            if self.output is None or self.transformations:
                raise ValueError("ALLOW exige output e não aceita transformações")
            if self.enforcement is not None:
                raise ValueError("ALLOW não aceita enforcement")
        elif self.decision is GuardrailDecision.TRANSFORM:
            if self.output is None or not self.transformations:
                raise ValueError("TRANSFORM exige output e transformação")
            if self.enforcement is not None:
                raise ValueError("TRANSFORM não aceita enforcement")
        else:
            if self.output is not None or not self.violations:
                raise ValueError("REJECT exige violação e output ausente")
            if self.enforcement is None:
                raise ValueError("REJECT exige enforcement explícito")
        return self


class GuardrailPipelineResult[T](_FrozenModel):
    """Aggregate an ordered pipeline without exposing evaluated content in audit."""

    decision: GuardrailDecision
    output: T | None = None
    enforcement: GuardrailEnforcement | None = None
    guardrail_results: tuple[GuardrailResult[T], ...] = ()
    violations: tuple[GuardrailViolation, ...] = ()
    transformations: tuple[GuardrailTransformation, ...] = ()


class GuardrailRecord(_FrozenModel):
    """Persist privacy-safe facts needed for audit and deterministic resume."""

    stage: GuardrailStage
    guardrail_id: str
    decision: GuardrailDecision
    enforcement: GuardrailEnforcement | None = None
    violation_codes: tuple[str, ...] = ()
    transformation_kinds: tuple[str, ...] = ()
    timestamp: datetime

    @field_validator("guardrail_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        """Reject an empty recorded guardrail identifier."""
        return _non_empty(value)

    @field_validator("violation_codes", "transformation_kinds")
    @classmethod
    def validate_codes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Reject empty audit codes and kinds."""
        return tuple(_non_empty(item) for item in value)

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        """Require a timezone-aware audit timestamp."""
        return _timezone_aware(value, label="do registro de guardrail")
