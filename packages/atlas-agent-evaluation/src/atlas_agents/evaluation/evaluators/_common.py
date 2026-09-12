"""Shared helpers for deterministic built-in evaluators."""

from pydantic import JsonValue, TypeAdapter, ValidationError

from atlas_agents.evaluation._models import FrozenEvaluationModel
from atlas_agents.evaluation.case import EvaluationExpectation
from atlas_agents.evaluation.errors import EvaluationProtocolError
from atlas_agents.evaluation.metric import EvaluationMetric, MetricDirection
from atlas_agents.evaluation.result import (
    EvaluationFinding,
    EvaluationFindingSeverity,
    EvaluationResult,
    EvaluationScore,
)

_JSON_OBJECT = TypeAdapter(dict[str, JsonValue])


class ConfiguredEvaluator(FrozenEvaluationModel):
    """Provide immutable configuration and common result construction."""

    evaluator_id: str
    metric: EvaluationMetric
    threshold: float | None

    def result(
        self,
        expectation: EvaluationExpectation,
        *,
        value: float,
        finding_code: str | None = None,
        finding_message: str = "A expectativa não foi atendida.",
    ) -> EvaluationResult:
        """Build a normalized score and optional safe finding."""
        score = EvaluationScore.from_metric(
            self.metric,
            value=value,
            threshold=self.threshold,
        )
        findings = (
            (
                EvaluationFinding(
                    code=finding_code,
                    message=finding_message,
                    severity=EvaluationFindingSeverity.WARNING,
                ),
            )
            if finding_code is not None
            else ()
        )
        return EvaluationResult(
            expectation_id=expectation.expectation_id,
            evaluator_id=self.evaluator_id,
            metric=self.metric,
            score=score,
            findings=findings,
        )


def binary_metric(metric_id: str, name: str, description: str) -> EvaluationMetric:
    """Create a conventional binary higher-is-better metric."""
    return EvaluationMetric(
        metric_id=metric_id,
        name=name,
        description=description,
        direction=MetricDirection.HIGHER_IS_BETTER,
        min_value=0,
        max_value=1,
    )


def expected_string(expectation: EvaluationExpectation) -> str:
    """Require a direct string expectation."""
    if not isinstance(expectation.expected, str):
        raise EvaluationProtocolError("A expectativa deve ser uma string.")
    return expectation.expected


def expected_object(expectation: EvaluationExpectation) -> dict[str, JsonValue]:
    """Require a JSON object expectation."""
    try:
        return _JSON_OBJECT.validate_python(expectation.expected)
    except ValidationError as exc:
        raise EvaluationProtocolError("A expectativa deve ser um objeto JSON.") from exc
