import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import JsonValue

from atlas_agents import ExecutionStatus
from atlas_agents.evaluation import (
    ContainsEvaluator,
    EvaluationCase,
    EvaluationCaseOutcome,
    EvaluationContext,
    EvaluationDataset,
    EvaluationExpectation,
    EvaluationMetric,
    EvaluationObservation,
    EvaluationReportOutcome,
    EvaluationResult,
    EvaluationResultStatus,
    EvaluationRunner,
    EvaluationScore,
    EvaluatorNotRegisteredError,
    EvaluatorRegistry,
    ExactMatchEvaluator,
    IncompatibleEvaluationMetricError,
    MetricDirection,
)


def expectation(
    evaluator_id: str,
    expected: JsonValue,
    expectation_id: str,
) -> EvaluationExpectation:
    return EvaluationExpectation(
        expectation_id=expectation_id,
        evaluator_id=evaluator_id,
        expected=expected,
    )


def case(
    case_id: str,
    *expectations: EvaluationExpectation,
) -> EvaluationCase:
    return EvaluationCase(
        case_id=case_id,
        name=f"Caso {case_id}",
        expectations=expectations,
    )


def dataset(*cases: EvaluationCase) -> EvaluationDataset:
    return EvaluationDataset(
        dataset_id="dataset",
        name="Conjunto",
        version="1",
        cases=cases,
    )


def observation(execution_id: str, output: JsonValue = "ok") -> EvaluationObservation:
    return EvaluationObservation(
        execution_id=execution_id,
        agent_id="agent",
        status=ExecutionStatus.COMPLETED,
        output=output,
    )


class RecordingExecutor:
    def __init__(
        self,
        observations: dict[str, EvaluationObservation],
        *,
        fail_case: str | None = None,
        cancel: bool = False,
    ) -> None:
        self.observations = observations
        self.fail_case = fail_case
        self.cancel = cancel
        self.calls: list[str] = []

    async def execute(self, evaluation_case: EvaluationCase) -> EvaluationObservation:
        self.calls.append(evaluation_case.case_id)
        if self.cancel:
            raise asyncio.CancelledError
        if evaluation_case.case_id == self.fail_case:
            raise RuntimeError("segredo do executor")
        return self.observations[evaluation_case.case_id]


class BrokenEvaluator:
    evaluator_id = "broken"
    metric = EvaluationMetric(
        metric_id="broken_metric",
        name="Falha operacional",
        description="Métrica que não foi produzida.",
        direction=MetricDirection.HIGHER_IS_BETTER,
        min_value=0,
        max_value=1,
    )

    async def evaluate(
        self,
        evaluation_case: EvaluationCase,
        evaluation_expectation: EvaluationExpectation,
        evaluation_observation: EvaluationObservation,
        evaluation_context: EvaluationContext,
    ) -> EvaluationResult:
        del (
            evaluation_case,
            evaluation_expectation,
            evaluation_observation,
            evaluation_context,
        )
        raise RuntimeError("segredo do evaluator")


class InformationalEvaluator:
    evaluator_id = "informational"
    metric = EvaluationMetric(
        metric_id="information",
        name="Informação",
        description="Métrica sem decisão automática.",
        direction=MetricDirection.NONE,
        min_value=0,
        max_value=1,
    )

    async def evaluate(
        self,
        evaluation_case: EvaluationCase,
        evaluation_expectation: EvaluationExpectation,
        evaluation_observation: EvaluationObservation,
        evaluation_context: EvaluationContext,
    ) -> EvaluationResult:
        del evaluation_case, evaluation_observation, evaluation_context
        return EvaluationResult(
            expectation_id=evaluation_expectation.expectation_id,
            evaluator_id=self.evaluator_id,
            metric=self.metric,
            score=EvaluationScore.from_metric(
                self.metric,
                value=0.5,
                threshold=None,
            ),
        )


class CancelledEvaluator(BrokenEvaluator):
    evaluator_id = "cancelled"

    async def evaluate(
        self,
        evaluation_case: EvaluationCase,
        evaluation_expectation: EvaluationExpectation,
        evaluation_observation: EvaluationObservation,
        evaluation_context: EvaluationContext,
    ) -> EvaluationResult:
        del (
            evaluation_case,
            evaluation_expectation,
            evaluation_observation,
            evaluation_context,
        )
        raise asyncio.CancelledError


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 12, tzinfo=UTC)

    def __call__(self) -> datetime:
        current = self.value
        self.value += timedelta(seconds=1)
        return current


async def test_preflight_finds_missing_evaluator_before_executor_call() -> None:
    evaluation_case = case("one", expectation("missing", "x", "e"))
    executor = RecordingExecutor({"one": observation("execution")})
    runner = EvaluationRunner(registry=EvaluatorRegistry())

    with pytest.raises(EvaluatorNotRegisteredError):
        await runner.run_dataset(dataset=dataset(evaluation_case), executor=executor)

    assert executor.calls == []


async def test_runner_preserves_case_expectation_and_duplicate_evaluator_order() -> (
    None
):
    first = case(
        "first",
        expectation("contains", "a", "one"),
        expectation("exact-output", "alpha", "two"),
        expectation("contains", "ph", "three"),
    )
    second = case("second", expectation("exact-output", "beta", "four"))
    executor = RecordingExecutor(
        {
            "first": observation("execution-1", "alpha"),
            "second": observation("execution-2", "beta"),
        }
    )
    runner = EvaluationRunner(
        registry=EvaluatorRegistry((ContainsEvaluator(), ExactMatchEvaluator())),
        clock=Clock(),
        id_factory=lambda: "generated-run",
    )

    report = await runner.run_dataset(dataset=dataset(first, second), executor=executor)

    assert executor.calls == ["first", "second"]
    assert [item.case_id for item in report.case_results] == ["first", "second"]
    assert [
        item.expectation_id for item in report.case_results[0].evaluation_results
    ] == ["one", "two", "three"]
    assert report.evaluation_run_id == "generated-run"
    assert report.outcome is EvaluationReportOutcome.PASSED
    assert report.summary.passed_case_count == 2


async def test_evaluate_existing_observation_does_not_mutate_it() -> None:
    evaluation_case = case(
        "one",
        expectation("exact-output", "ok", "expectation"),
    )
    observed = observation("execution", "ok")
    before = observed.model_dump_json()
    runner = EvaluationRunner(registry=EvaluatorRegistry((ExactMatchEvaluator(),)))

    result = await runner.evaluate_case(
        case=evaluation_case,
        observation=observed,
        evaluation_run_id="run",
        dataset_id="dataset",
    )

    assert result.outcome is EvaluationCaseOutcome.PASSED
    assert result.passed is True
    assert observed.model_dump_json() == before


async def test_evaluator_error_is_unscored_safe_and_next_evaluator_continues() -> None:
    evaluation_case = case(
        "one",
        expectation("broken", None, "broken"),
        expectation("exact-output", "ok", "exact"),
    )
    runner = EvaluationRunner(
        registry=EvaluatorRegistry((BrokenEvaluator(), ExactMatchEvaluator())),
        clock=Clock(),
    )
    report = await runner.evaluate_dataset(
        dataset=dataset(evaluation_case),
        observations={"one": observation("execution")},
        evaluation_run_id="run",
    )

    broken, exact = report.case_results[0].evaluation_results
    assert broken.status is EvaluationResultStatus.ERROR
    assert broken.score is None
    assert broken.error is not None
    assert exact.status is EvaluationResultStatus.COMPLETED
    assert report.case_results[0].outcome is EvaluationCaseOutcome.ERROR
    assert report.summary.evaluator_error_count == 1
    assert "segredo" not in report.model_dump_json()


async def test_executor_error_marks_case_and_continues_next_case() -> None:
    evaluation_cases = (
        case("bad", expectation("exact-output", "ok", "bad-e")),
        case("good", expectation("exact-output", "ok", "good-e")),
    )
    executor = RecordingExecutor(
        {"good": observation("execution-good")},
        fail_case="bad",
    )
    runner = EvaluationRunner(
        registry=EvaluatorRegistry((ExactMatchEvaluator(),)),
        clock=Clock(),
    )

    report = await runner.run_dataset(
        dataset=dataset(*evaluation_cases),
        executor=executor,
        evaluation_run_id="run",
    )

    assert executor.calls == ["bad", "good"]
    assert report.case_results[0].outcome is EvaluationCaseOutcome.ERROR
    assert report.case_results[0].observation_summary is None
    assert report.case_results[1].outcome is EvaluationCaseOutcome.PASSED
    assert report.summary.execution_error_count == 1
    assert report.outcome is EvaluationReportOutcome.ERROR
    assert "segredo do executor" not in report.model_dump_json()


async def test_summary_classifies_pass_fail_error_unscored_and_metrics() -> None:
    cases = (
        case("passed", expectation("exact-output", "ok", "p")),
        case("failed", expectation("exact-output", "expected", "f")),
        case("error", expectation("broken", None, "e")),
        case("unscored", expectation("informational", None, "u")),
    )
    observations = {item.case_id: observation(f"exec-{item.case_id}") for item in cases}
    runner = EvaluationRunner(
        registry=EvaluatorRegistry(
            (ExactMatchEvaluator(), BrokenEvaluator(), InformationalEvaluator())
        ),
        clock=Clock(),
    )

    report = await runner.evaluate_dataset(
        dataset=dataset(*cases),
        observations=observations,
        evaluation_run_id="run",
    )

    summary = report.summary
    assert (
        summary.passed_case_count,
        summary.failed_case_count,
        summary.errored_case_count,
        summary.unscored_case_count,
    ) == (1, 1, 1, 1)
    exact = next(
        item for item in summary.metric_summaries if item.metric_id == "exact_match"
    )
    assert exact.count == 2
    assert exact.mean == 0.5
    assert exact.min == 0
    assert exact.max == 1
    assert exact.passed_count == 1
    assert exact.failed_count == 1


async def test_empty_dataset_produces_valid_unscored_report() -> None:
    executor = RecordingExecutor({})
    report = await EvaluationRunner(
        registry=EvaluatorRegistry(),
        clock=Clock(),
    ).run_dataset(
        dataset=dataset(),
        executor=executor,
        evaluation_run_id="run",
    )

    assert executor.calls == []
    assert report.case_results == ()
    assert report.summary.case_count == 0
    assert report.summary.metric_summaries == ()
    assert report.outcome is EvaluationReportOutcome.UNSCORED


async def test_cancellation_from_executor_and_evaluator_is_repropagated() -> None:
    execution_case = case("one")
    runner = EvaluationRunner(registry=EvaluatorRegistry(), clock=Clock())
    with pytest.raises(asyncio.CancelledError):
        await runner.run_dataset(
            dataset=dataset(execution_case),
            executor=RecordingExecutor({}, cancel=True),
        )

    evaluation_case = case(
        "cancelled",
        expectation("cancelled", None, "cancelled"),
    )
    cancelling_runner = EvaluationRunner(
        registry=EvaluatorRegistry((CancelledEvaluator(),)),
        clock=Clock(),
    )
    with pytest.raises(asyncio.CancelledError):
        await cancelling_runner.evaluate_dataset(
            dataset=dataset(evaluation_case),
            observations={"cancelled": observation("execution")},
        )


async def test_incompatible_metric_definitions_fail_preflight() -> None:
    other = InformationalEvaluator()
    object.__setattr__(
        other,
        "metric",
        EvaluationMetric(
            metric_id="exact_match",
            name="Incompatível",
            description="Outra definição.",
            direction=MetricDirection.NONE,
        ),
    )
    cases = (
        case("one", expectation("exact-output", "ok", "one")),
        case("two", expectation("informational", None, "two")),
    )
    executor = RecordingExecutor({"one": observation("one"), "two": observation("two")})
    runner = EvaluationRunner(
        registry=EvaluatorRegistry((ExactMatchEvaluator(), other))
    )

    with pytest.raises(IncompatibleEvaluationMetricError):
        await runner.run_dataset(dataset=dataset(*cases), executor=executor)
    assert executor.calls == []


async def test_independent_runners_do_not_share_registry_or_ids() -> None:
    evaluation_case = case("one", expectation("exact-output", "ok", "expectation"))
    first = EvaluationRunner(
        registry=EvaluatorRegistry((ExactMatchEvaluator(),)),
        clock=Clock(),
        id_factory=lambda: "first-run",
    )
    second = EvaluationRunner(
        registry=EvaluatorRegistry((ExactMatchEvaluator(),)),
        clock=Clock(),
        id_factory=lambda: "second-run",
    )
    observations = {"one": observation("execution")}

    first_report, second_report = await asyncio.gather(
        first.evaluate_dataset(
            dataset=dataset(evaluation_case), observations=observations
        ),
        second.evaluate_dataset(
            dataset=dataset(evaluation_case), observations=observations
        ),
    )

    assert first_report.evaluation_run_id == "first-run"
    assert second_report.evaluation_run_id == "second-run"
