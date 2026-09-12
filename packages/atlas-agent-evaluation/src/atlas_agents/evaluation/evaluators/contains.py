"""Deterministic textual containment evaluator."""

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


class ContainsEvaluator(ConfiguredEvaluator):
    """Check whether final textual output contains a literal fragment."""

    evaluator_id: str = "contains"
    metric: EvaluationMetric = binary_metric(
        "contains",
        "Contém fragmento",
        "Indica se a saída textual contém o fragmento esperado.",
    )
    threshold: float | None = 1.0
    case_sensitive: bool = True

    async def evaluate(
        self,
        case: EvaluationCase,
        expectation: EvaluationExpectation,
        observation: EvaluationObservation,
        context: EvaluationContext,
    ) -> EvaluationResult:
        """Return one when the expected literal fragment is present."""
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
        actual = output
        if not self.case_sensitive:
            actual = actual.casefold()
            expected = expected.casefold()
        matched = expected in actual
        return self.result(
            expectation,
            value=float(matched),
            finding_code=None if matched else "contains_failed",
        )
