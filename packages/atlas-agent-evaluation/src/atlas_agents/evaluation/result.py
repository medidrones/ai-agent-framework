"""Immutable evaluator result and finding contracts."""

import math
from enum import StrEnum
from typing import Self

from pydantic import Field, JsonValue, field_validator, model_validator

from atlas_agents.evaluation._models import (
    FrozenEvaluationModel,
    json_mapping,
    non_empty,
)
from atlas_agents.evaluation.metric import EvaluationMetric


class EvaluationFindingSeverity(StrEnum):
    """Classify findings independently from production guardrails."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class EvaluationResultStatus(StrEnum):
    """Describe whether one evaluator completed, failed, or skipped."""

    COMPLETED = "completed"
    ERROR = "error"
    SKIPPED = "skipped"


class EvaluationErrorInfo(FrozenEvaluationModel):
    """Expose a safe operational error without retaining exceptions."""

    code: str
    message: str
    retryable: bool = False

    @field_validator("code", "message")
    @classmethod
    def validate_text(cls, value: str) -> str:
        """Reject blank error information."""
        return non_empty(value)


class EvaluationFinding(FrozenEvaluationModel):
    """Describe one privacy-conscious quality finding."""

    code: str
    message: str
    severity: EvaluationFindingSeverity = EvaluationFindingSeverity.INFO
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("code", "message")
    @classmethod
    def validate_text(cls, value: str) -> str:
        """Reject blank finding descriptors."""
        return non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        """Keep finding metadata JSON-compatible and isolated."""
        return json_mapping(value)


class EvaluationScore(FrozenEvaluationModel):
    """Hold one finite numeric score and optional pass decision."""

    value: float
    passed: bool | None = None
    threshold: float | None = None

    @field_validator("value", "threshold")
    @classmethod
    def validate_finite(cls, value: float | None) -> float | None:
        """Reject NaN and infinity in scores and thresholds."""
        if value is not None and not math.isfinite(value):
            raise ValueError("Scores e thresholds devem ser finitos")
        return value

    @classmethod
    def from_metric(
        cls,
        metric: EvaluationMetric,
        *,
        value: float,
        threshold: float | None = None,
    ) -> "EvaluationScore":
        """Build a score using the metric's centralized threshold semantics."""
        passed = metric.evaluate_threshold(value, threshold)
        return cls(value=value, passed=passed, threshold=threshold)


class EvaluationResult(FrozenEvaluationModel):
    """Represent one evaluator invocation without affecting production output."""

    expectation_id: str
    evaluator_id: str
    metric: EvaluationMetric
    status: EvaluationResultStatus = EvaluationResultStatus.COMPLETED
    score: EvaluationScore | None = None
    findings: tuple[EvaluationFinding, ...] = ()
    error: EvaluationErrorInfo | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("expectation_id", "evaluator_id")
    @classmethod
    def validate_ids(cls, value: str) -> str:
        """Reject blank result identifiers."""
        return non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        """Keep result metadata JSON-compatible and isolated."""
        return json_mapping(value)

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        """Keep score and error mutually consistent with operational status."""
        if self.status is EvaluationResultStatus.COMPLETED:
            if self.score is None or self.error is not None:
                raise ValueError("Um resultado concluído exige score e não aceita erro")
            self.metric.validate_value(self.score.value)
            expected_passed = self.metric.evaluate_threshold(
                self.score.value,
                self.score.threshold,
            )
            if self.score.passed is not expected_passed:
                raise ValueError("A decisão do score não corresponde à métrica")
        elif self.status is EvaluationResultStatus.ERROR:
            if self.score is not None or self.error is None:
                raise ValueError("Um resultado com erro não pode conter score")
        elif self.score is not None or self.error is not None:
            raise ValueError("Um resultado ignorado não aceita score ou erro")
        return self
