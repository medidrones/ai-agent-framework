"""Sequential deterministic evaluation orchestration."""

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import JsonValue

from atlas_agents.evaluation._models import non_empty
from atlas_agents.evaluation.case import EvaluationCase, EvaluationExpectation
from atlas_agents.evaluation.dataset import EvaluationDataset
from atlas_agents.evaluation.errors import (
    EvaluationProtocolError,
    EvaluatorNotRegisteredError,
    IncompatibleEvaluationMetricError,
)
from atlas_agents.evaluation.evaluator import (
    EvaluationContext,
    EvaluationExecutor,
    Evaluator,
    EvaluatorRegistry,
)
from atlas_agents.evaluation.metric import EvaluationMetric
from atlas_agents.evaluation.observation import (
    EvaluationObservation,
    EvaluationObservationSummary,
)
from atlas_agents.evaluation.report import (
    EvaluationCaseOutcome,
    EvaluationCaseResult,
    EvaluationReport,
    EvaluationReportOutcome,
)
from atlas_agents.evaluation.result import (
    EvaluationErrorInfo,
    EvaluationResult,
    EvaluationResultStatus,
)
from atlas_agents.evaluation.summary import build_summary

type EvaluationClock = Callable[[], datetime]
type EvaluationIdFactory = Callable[[], str]


class EvaluationRunner:
    """Evaluate observations or explicitly execute cases in stable sequence."""

    def __init__(
        self,
        *,
        registry: EvaluatorRegistry,
        clock: EvaluationClock | None = None,
        id_factory: EvaluationIdFactory | None = None,
    ) -> None:
        """Store isolated registry, clock, and run-ID factory dependencies."""
        self._registry = registry
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))

    def validate_dataset(self, dataset: EvaluationDataset) -> None:
        """Fail before execution when evaluators are missing or metrics conflict."""
        metrics: dict[str, EvaluationMetric] = {}
        for case in dataset.cases:
            for expectation in case.expectations:
                evaluator = self._registry.try_get(expectation.evaluator_id)
                if evaluator is None:
                    raise EvaluatorNotRegisteredError(
                        f"O evaluator '{expectation.evaluator_id}' não está registrado."
                    )
                current = metrics.get(evaluator.metric.metric_id)
                if current is not None and current != evaluator.metric:
                    raise IncompatibleEvaluationMetricError(
                        "A métrica "
                        f"'{evaluator.metric.metric_id}' possui definições "
                        "incompatíveis."
                    )
                metrics.setdefault(evaluator.metric.metric_id, evaluator.metric)

    async def evaluate_case(
        self,
        *,
        case: EvaluationCase,
        observation: EvaluationObservation,
        evaluation_run_id: str,
        dataset_id: str,
        metadata: Mapping[str, JsonValue] | None = None,
    ) -> EvaluationCaseResult:
        """Evaluate one existing observation without executing production code."""
        dataset = EvaluationDataset(
            dataset_id=dataset_id,
            name="Avaliação de caso único",
            version="ad-hoc",
            cases=(case,),
        )
        self.validate_dataset(dataset)
        return await self._evaluate_observation(
            case=case,
            observation=observation,
            evaluation_run_id=evaluation_run_id,
            dataset_id=dataset_id,
            metadata=metadata,
        )

    async def evaluate_dataset(
        self,
        *,
        dataset: EvaluationDataset,
        observations: Mapping[str, EvaluationObservation],
        evaluation_run_id: str | None = None,
        metadata: Mapping[str, JsonValue] | None = None,
    ) -> EvaluationReport:
        """Evaluate caller-provided observations in dataset order."""
        self.validate_dataset(dataset)

        async def observation_executor(case: EvaluationCase) -> EvaluationObservation:
            try:
                return observations[case.case_id]
            except KeyError as exc:
                raise EvaluationProtocolError(
                    "Não existe observation para o caso informado."
                ) from exc

        return await self._run_validated(
            dataset=dataset,
            executor=observation_executor,
            evaluation_run_id=evaluation_run_id,
            metadata=metadata,
        )

    async def run_dataset(
        self,
        *,
        dataset: EvaluationDataset,
        executor: EvaluationExecutor,
        evaluation_run_id: str | None = None,
        metadata: Mapping[str, JsonValue] | None = None,
    ) -> EvaluationReport:
        """Execute and evaluate cases sequentially after complete preflight."""
        self.validate_dataset(dataset)
        return await self._run_validated(
            dataset=dataset,
            executor=executor.execute,
            evaluation_run_id=evaluation_run_id,
            metadata=metadata,
        )

    async def _run_validated(
        self,
        *,
        dataset: EvaluationDataset,
        executor: Callable[[EvaluationCase], Awaitable[EvaluationObservation]],
        evaluation_run_id: str | None,
        metadata: Mapping[str, JsonValue] | None,
    ) -> EvaluationReport:
        run_id = non_empty(evaluation_run_id or self._id_factory())
        started_at = self._read_clock()
        case_results: list[EvaluationCaseResult] = []
        for case in dataset.cases:
            try:
                observation = await executor(case)
                if not isinstance(observation, EvaluationObservation):
                    raise EvaluationProtocolError(
                        "O executor não retornou uma EvaluationObservation."
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                case_results.append(
                    EvaluationCaseResult(
                        case_id=case.case_id,
                        outcome=EvaluationCaseOutcome.ERROR,
                        execution_error=EvaluationErrorInfo(
                            code="evaluation_execution_failed",
                            message="Não foi possível produzir a observation do caso.",
                        ),
                    )
                )
                continue
            case_results.append(
                await self._evaluate_observation(
                    case=case,
                    observation=observation,
                    evaluation_run_id=run_id,
                    dataset_id=dataset.dataset_id,
                    metadata=metadata,
                )
            )
        completed_at = self._read_clock()
        results = tuple(case_results)
        summary = build_summary(results)
        return EvaluationReport(
            evaluation_run_id=run_id,
            dataset_id=dataset.dataset_id,
            dataset_version=dataset.version,
            started_at=started_at,
            completed_at=completed_at,
            case_results=results,
            summary=summary,
            outcome=_report_outcome(results),
            metadata=dict(metadata or {}),
        )

    async def _evaluate_observation(
        self,
        *,
        case: EvaluationCase,
        observation: EvaluationObservation,
        evaluation_run_id: str,
        dataset_id: str,
        metadata: Mapping[str, JsonValue] | None,
    ) -> EvaluationCaseResult:
        context = EvaluationContext(
            evaluation_run_id=evaluation_run_id,
            dataset_id=dataset_id,
            case_id=case.case_id,
            metadata=dict(metadata or {}),
        )
        results: list[EvaluationResult] = []
        for expectation in case.expectations:
            evaluator = self._registry.get(expectation.evaluator_id)
            results.append(
                await _safe_evaluate(
                    evaluator=evaluator,
                    case=case,
                    expectation=expectation,
                    observation=observation,
                    context=context,
                )
            )
        completed = tuple(results)
        return EvaluationCaseResult(
            case_id=case.case_id,
            execution_id=observation.execution_id,
            observation_summary=EvaluationObservationSummary.from_observation(
                observation
            ),
            evaluation_results=completed,
            outcome=_case_outcome(completed),
        )

    def _read_clock(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("O relógio de evaluation deve retornar fuso horário")
        return value


async def _safe_evaluate(
    *,
    evaluator: Evaluator,
    case: EvaluationCase,
    expectation: EvaluationExpectation,
    observation: EvaluationObservation,
    context: EvaluationContext,
) -> EvaluationResult:
    try:
        result = await evaluator.evaluate(case, expectation, observation, context)
        if (
            result.expectation_id != expectation.expectation_id
            or result.evaluator_id != evaluator.evaluator_id
            or result.metric != evaluator.metric
        ):
            raise EvaluationProtocolError(
                "O evaluator retornou identidades ou métrica incompatíveis."
            )
        return result
    except asyncio.CancelledError:
        raise
    except Exception:
        return EvaluationResult(
            expectation_id=expectation.expectation_id,
            evaluator_id=evaluator.evaluator_id,
            metric=evaluator.metric,
            status=EvaluationResultStatus.ERROR,
            error=EvaluationErrorInfo(
                code="evaluator_execution_failed",
                message="O evaluator não conseguiu concluir a avaliação.",
            ),
        )


def _case_outcome(results: tuple[EvaluationResult, ...]) -> EvaluationCaseOutcome:
    if any(result.status is EvaluationResultStatus.ERROR for result in results):
        return EvaluationCaseOutcome.ERROR
    scores = [
        result.score
        for result in results
        if result.status is EvaluationResultStatus.COMPLETED
        and result.score is not None
        and result.score.passed is not None
    ]
    if any(score.passed is False for score in scores):
        return EvaluationCaseOutcome.FAILED
    if scores:
        return EvaluationCaseOutcome.PASSED
    return EvaluationCaseOutcome.UNSCORED


def _report_outcome(
    case_results: tuple[EvaluationCaseResult, ...],
) -> EvaluationReportOutcome:
    outcomes = {result.outcome for result in case_results}
    if EvaluationCaseOutcome.ERROR in outcomes:
        return EvaluationReportOutcome.ERROR
    if EvaluationCaseOutcome.FAILED in outcomes:
        return EvaluationReportOutcome.FAILED
    if EvaluationCaseOutcome.PASSED in outcomes:
        return EvaluationReportOutcome.PASSED
    return EvaluationReportOutcome.UNSCORED
