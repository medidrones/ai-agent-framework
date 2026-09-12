"""Opt-in evaluator backed by a provider-neutral judge contract."""

from pydantic import Field, JsonValue

from atlas_agents.evaluation.case import EvaluationCase, EvaluationExpectation
from atlas_agents.evaluation.evaluator import EvaluationContext
from atlas_agents.evaluation.evaluators._common import ConfiguredEvaluator
from atlas_agents.evaluation.judge import EvaluationJudge, JudgeRequest
from atlas_agents.evaluation.metric import EvaluationMetric, MetricDirection
from atlas_agents.evaluation.observation import EvaluationObservation
from atlas_agents.evaluation.result import (
    EvaluationFinding,
    EvaluationFindingSeverity,
    EvaluationResult,
    EvaluationScore,
)


class JudgeEvaluator(ConfiguredEvaluator):
    """Delegate explicit candidate scoring to an injected judge."""

    evaluator_id: str = "judge"
    metric: EvaluationMetric = EvaluationMetric(
        metric_id="judge_score",
        name="Score do judge",
        description="Score atribuído por um judge provider-neutral injetado.",
        direction=MetricDirection.HIGHER_IS_BETTER,
        min_value=0,
        max_value=1,
    )
    threshold: float | None = 0.5
    judge: EvaluationJudge
    criteria: str
    rubric: str | None = None
    judge_metadata: dict[str, JsonValue] = Field(default_factory=dict)

    async def evaluate(
        self,
        case: EvaluationCase,
        expectation: EvaluationExpectation,
        observation: EvaluationObservation,
        context: EvaluationContext,
    ) -> EvaluationResult:
        """Map an injected judge response without treating it as ground truth."""
        del case
        response = await self.judge.judge(
            JudgeRequest(
                criteria=self.criteria,
                candidate=observation.output,
                reference=expectation.expected,
                rubric=self.rubric,
                metadata=self.judge_metadata,
            ),
            context,
        )
        score = EvaluationScore.from_metric(
            self.metric,
            value=response.score,
            threshold=self.threshold,
        )
        return EvaluationResult(
            expectation_id=expectation.expectation_id,
            evaluator_id=self.evaluator_id,
            metric=self.metric,
            score=score,
            findings=(
                EvaluationFinding(
                    code="judge_reason",
                    message=response.reason,
                    severity=EvaluationFindingSeverity.INFO,
                ),
            ),
            metadata=response.metadata,
        )
