"""Deterministic exact textual output evaluator."""

from atlas_agents.evaluation.case import EvaluationCase, EvaluationExpectation
from atlas_agents.evaluation.evaluator import EvaluationContext
from atlas_agents.evaluation.evaluators._common import (
    ConfiguredEvaluator,
    binary_metric,
    expected_string,
)
from atlas_agents.evaluation.metric import EvaluationMetric
from atlas_agents.evaluation.observation import EvaluationObservation
from atlas_agents.evaluation.result import EvaluationResult


class ExactMatchEvaluator(ConfiguredEvaluator):
    """Compare final textual output with a literal expected string."""

    evaluator_id: str = "exact-output"
    metric: EvaluationMetric = binary_metric(
        "exact_match",
        "Correspondência exata",
        "Indica se a saída textual corresponde exatamente à expectativa.",
    )
    threshold: float | None = 1.0
    case_sensitive: bool = True
    strip: bool = False

    async def evaluate(
        self,
        case: EvaluationCase,
        expectation: EvaluationExpectation,
        observation: EvaluationObservation,
        context: EvaluationContext,
    ) -> EvaluationResult:
        """Return one for a literal match and zero otherwise."""
        del case, context
        expected = expected_string(expectation)
        output = observation.output
        if not isinstance(output, str):
            return self.result(
                expectation,
                value=0,
                finding_code="output_not_text",
                finding_message="A saída final não é textual.",
            )
        actual = output.strip() if self.strip else output
        target = expected.strip() if self.strip else expected
        if not self.case_sensitive:
            actual = actual.casefold()
            target = target.casefold()
        matched = actual == target
        return self.result(
            expectation,
            value=float(matched),
            finding_code=None if matched else "exact_match_failed",
        )
