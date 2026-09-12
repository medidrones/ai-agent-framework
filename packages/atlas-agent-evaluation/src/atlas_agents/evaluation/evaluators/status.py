"""Execution status evaluator."""

from atlas_agents import ExecutionStatus
from atlas_agents.evaluation.case import EvaluationCase, EvaluationExpectation
from atlas_agents.evaluation.errors import EvaluationProtocolError
from atlas_agents.evaluation.evaluator import EvaluationContext
from atlas_agents.evaluation.evaluators._common import (
    ConfiguredEvaluator,
    binary_metric,
    expected_string,
)
from atlas_agents.evaluation.metric import EvaluationMetric
from atlas_agents.evaluation.observation import EvaluationObservation
from atlas_agents.evaluation.result import EvaluationResult


class ExecutionStatusEvaluator(ConfiguredEvaluator):
    """Compare the observed runtime status with an expected public status."""

    evaluator_id: str = "status"
    metric: EvaluationMetric = binary_metric(
        "execution_status",
        "Status de execução",
        "Indica se o status produtivo corresponde à expectativa.",
    )
    threshold: float | None = 1.0

    async def evaluate(
        self,
        case: EvaluationCase,
        expectation: EvaluationExpectation,
        observation: EvaluationObservation,
        context: EvaluationContext,
    ) -> EvaluationResult:
        """Return one when the exact public execution status matches."""
        del case, context
        try:
            expected = ExecutionStatus(expected_string(expectation))
        except ValueError as exc:
            raise EvaluationProtocolError(
                "A expectativa contém um status de execução desconhecido."
            ) from exc
        matched = observation.status is expected
        return self.result(
            expectation,
            value=float(matched),
            finding_code=None if matched else "status_mismatch",
        )
