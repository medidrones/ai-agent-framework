"""Evaluation metric definitions and threshold semantics."""

import math
from enum import StrEnum

from pydantic import field_validator, model_validator

from atlas_agents.evaluation._models import FrozenEvaluationModel, non_empty
from atlas_agents.evaluation.errors import EvaluationMetricError


class MetricDirection(StrEnum):
    """Define how numeric metric values should be interpreted."""

    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"
    NONE = "none"


class EvaluationMetric(FrozenEvaluationModel):
    """Describe one stable numeric metric and its optional bounds."""

    metric_id: str
    name: str
    description: str
    direction: MetricDirection = MetricDirection.NONE
    min_value: float | None = None
    max_value: float | None = None

    @field_validator("metric_id", "name", "description")
    @classmethod
    def validate_text(cls, value: str) -> str:
        """Reject blank metric descriptors."""
        return non_empty(value)

    @field_validator("min_value", "max_value")
    @classmethod
    def validate_finite_bound(cls, value: float | None) -> float | None:
        """Reject NaN and infinite bounds."""
        if value is not None and not math.isfinite(value):
            raise EvaluationMetricError("Os limites da métrica devem ser finitos.")
        return value

    @model_validator(mode="after")
    def validate_bounds(self) -> "EvaluationMetric":
        """Require increasing optional bounds."""
        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value > self.max_value
        ):
            raise EvaluationMetricError(
                "O limite mínimo não pode exceder o limite máximo."
            )
        return self

    def evaluate_threshold(self, value: float, threshold: float | None) -> bool | None:
        """Validate a score and evaluate its threshold according to direction."""
        self.validate_value(value)
        if threshold is None:
            return None
        self.validate_value(threshold, label="threshold")
        if self.direction is MetricDirection.HIGHER_IS_BETTER:
            return value >= threshold
        if self.direction is MetricDirection.LOWER_IS_BETTER:
            return value <= threshold
        return None

    def validate_value(self, value: float, *, label: str = "score") -> None:
        """Reject non-finite values and values outside metric bounds."""
        if not math.isfinite(value):
            raise EvaluationMetricError(f"O {label} deve ser finito.")
        if self.min_value is not None and value < self.min_value:
            raise EvaluationMetricError(f"O {label} está abaixo do limite mínimo.")
        if self.max_value is not None and value > self.max_value:
            raise EvaluationMetricError(f"O {label} está acima do limite máximo.")
