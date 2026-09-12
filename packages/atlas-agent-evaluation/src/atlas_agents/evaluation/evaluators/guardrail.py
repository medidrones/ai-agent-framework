"""Privacy-safe guardrail outcome evaluator."""

from pydantic import BaseModel, ConfigDict, ValidationError

from atlas_agents import GuardrailDecision, GuardrailStage
from atlas_agents.evaluation.case import EvaluationCase, EvaluationExpectation
from atlas_agents.evaluation.errors import EvaluationProtocolError
from atlas_agents.evaluation.evaluator import EvaluationContext
from atlas_agents.evaluation.evaluators._common import (
    ConfiguredEvaluator,
    binary_metric,
    expected_object,
)
from atlas_agents.evaluation.metric import EvaluationMetric
from atlas_agents.evaluation.observation import EvaluationObservation
from atlas_agents.evaluation.result import EvaluationResult


class _GuardrailExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: GuardrailStage
    decision: GuardrailDecision | None = None
    violation_code: str | None = None


class GuardrailOutcomeEvaluator(ConfiguredEvaluator):
    """Evaluate safe audit records by stage, decision, and violation code."""

    evaluator_id: str = "guardrail-outcome"
    metric: EvaluationMetric = binary_metric(
        "guardrail_outcome",
        "Resultado de guardrail",
        "Indica se registros seguros de guardrail atendem à expectativa.",
    )
    threshold: float | None = 1.0

    async def evaluate(
        self,
        case: EvaluationCase,
        expectation: EvaluationExpectation,
        observation: EvaluationObservation,
        context: EvaluationContext,
    ) -> EvaluationResult:
        """Match guardrail audit facts without requiring evaluated content."""
        del case, context
        try:
            expected = _GuardrailExpectation.model_validate(
                expected_object(expectation)
            )
        except ValidationError as exc:
            raise EvaluationProtocolError(
                "A expectativa de guardrail é inválida."
            ) from exc
        matched = any(
            record.stage is expected.stage
            and (expected.decision is None or record.decision is expected.decision)
            and (
                expected.violation_code is None
                or expected.violation_code in record.violation_codes
            )
            for record in observation.guardrail_records
        )
        return self.result(
            expectation,
            value=float(matched),
            finding_code=None if matched else "guardrail_outcome_mismatch",
        )
