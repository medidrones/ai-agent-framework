"""Evaluator for tools that were actually executed."""

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


class _ToolUsageExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_tool_names: tuple[str, ...] = ()
    forbidden_tool_names: tuple[str, ...] = ()
    minimum_executions: int | None = Field(default=None, ge=0)
    maximum_executions: int | None = Field(default=None, ge=0)


class ToolUsageEvaluator(ConfiguredEvaluator):
    """Evaluate actual non-deduplicated tool execution facts."""

    evaluator_id: str = "tool-usage"
    metric: EvaluationMetric = binary_metric(
        "tool_usage",
        "Uso de ferramentas",
        "Indica se as ferramentas realmente executadas atendem à expectativa.",
    )
    threshold: float | None = 1.0

    async def evaluate(
        self,
        case: EvaluationCase,
        expectation: EvaluationExpectation,
        observation: EvaluationObservation,
        context: EvaluationContext,
    ) -> EvaluationResult:
        """Check names and count without counting deduplicated replay as execution."""
        del case, context
        try:
            expected = _ToolUsageExpectation.model_validate(
                expected_object(expectation)
            )
        except ValidationError as exc:
            raise EvaluationProtocolError(
                "A expectativa de ferramentas é inválida."
            ) from exc
        executed = tuple(
            item for item in observation.tool_calls if not item.deduplicated
        )
        names = {item.tool_name for item in executed}
        matched = set(expected.required_tool_names) <= names
        matched = matched and not (set(expected.forbidden_tool_names) & names)
        count = len(executed)
        if expected.minimum_executions is not None:
            matched = matched and count >= expected.minimum_executions
        if expected.maximum_executions is not None:
            matched = matched and count <= expected.maximum_executions
        return self.result(
            expectation,
            value=float(matched),
            finding_code=None if matched else "tool_usage_mismatch",
        )
