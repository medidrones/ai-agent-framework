"""Structural citation evaluator without factual groundedness claims."""

from pydantic import BaseModel, ConfigDict, Field, ValidationError

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


class _CitationExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minimum_count: int = Field(default=0, ge=0)
    required_citation_ids: tuple[str, ...] = ()
    allowed_citation_ids: tuple[str, ...] | None = None
    forbid_unknown: bool = False


class CitationEvaluator(ConfiguredEvaluator):
    """Evaluate citation count and identifiers, not factual correctness."""

    evaluator_id: str = "citation-validity"
    metric: EvaluationMetric = binary_metric(
        "citation_validity",
        "Estrutura de citações",
        "Indica se as citações estruturadas atendem à expectativa.",
    )
    threshold: float | None = 1.0

    async def evaluate(
        self,
        case: EvaluationCase,
        expectation: EvaluationExpectation,
        observation: EvaluationObservation,
        context: EvaluationContext,
    ) -> EvaluationResult:
        """Check only public citation structure and stable local identifiers."""
        del case, context
        try:
            expected = _CitationExpectation.model_validate(expected_object(expectation))
        except ValidationError as exc:
            raise EvaluationProtocolError(
                "A expectativa de citações é inválida."
            ) from exc
        identifiers = {item.citation_key for item in observation.citations}
        matched = len(observation.citations) >= expected.minimum_count
        matched = matched and set(expected.required_citation_ids) <= identifiers
        if expected.forbid_unknown and expected.allowed_citation_ids is not None:
            matched = matched and identifiers <= set(expected.allowed_citation_ids)
        return self.result(
            expectation,
            value=float(matched),
            finding_code=None if matched else "citation_mismatch",
        )
