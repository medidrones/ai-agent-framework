"""Deterministic report aggregation contracts and functions."""

from math import fsum

from atlas_agents.evaluation.errors import IncompatibleEvaluationMetricError
from atlas_agents.evaluation.metric import EvaluationMetric
from atlas_agents.evaluation.report import (
    EvaluationCaseOutcome,
    EvaluationCaseResult,
    EvaluationMetricSummary,
    EvaluationSummary,
)
from atlas_agents.evaluation.result import EvaluationResultStatus


def build_summary(case_results: tuple[EvaluationCaseResult, ...]) -> EvaluationSummary:
    """Aggregate case and metric results while preserving first metric order."""
    metric_definitions: dict[str, EvaluationMetric] = {}
    metric_values: dict[str, list[float]] = {}
    metric_passed: dict[str, int] = {}
    metric_failed: dict[str, int] = {}
    metric_unscored: dict[str, int] = {}
    evaluator_errors = 0

    for case_result in case_results:
        for result in case_result.evaluation_results:
            if result.status is EvaluationResultStatus.ERROR:
                evaluator_errors += 1
                continue
            if result.status is not EvaluationResultStatus.COMPLETED:
                continue
            current = metric_definitions.get(result.metric.metric_id)
            if current is not None and current != result.metric:
                raise IncompatibleEvaluationMetricError(
                    "A métrica "
                    f"'{result.metric.metric_id}' possui definições incompatíveis."
                )
            metric_definitions.setdefault(result.metric.metric_id, result.metric)
            if result.score is None:
                continue
            metric_values.setdefault(result.metric.metric_id, []).append(
                result.score.value
            )
            if result.score.passed is True:
                metric_passed[result.metric.metric_id] = (
                    metric_passed.get(result.metric.metric_id, 0) + 1
                )
            elif result.score.passed is False:
                metric_failed[result.metric.metric_id] = (
                    metric_failed.get(result.metric.metric_id, 0) + 1
                )
            else:
                metric_unscored[result.metric.metric_id] = (
                    metric_unscored.get(result.metric.metric_id, 0) + 1
                )

    summaries: list[EvaluationMetricSummary] = []
    for metric_id in metric_definitions:
        values = metric_values[metric_id]
        summaries.append(
            EvaluationMetricSummary(
                metric_id=metric_id,
                count=len(values),
                mean=fsum(values) / len(values) if values else None,
                min=min(values) if values else None,
                max=max(values) if values else None,
                passed_count=metric_passed.get(metric_id, 0),
                failed_count=metric_failed.get(metric_id, 0),
                unscored_count=metric_unscored.get(metric_id, 0),
            )
        )

    return EvaluationSummary(
        case_count=len(case_results),
        passed_case_count=sum(
            item.outcome is EvaluationCaseOutcome.PASSED for item in case_results
        ),
        failed_case_count=sum(
            item.outcome is EvaluationCaseOutcome.FAILED for item in case_results
        ),
        errored_case_count=sum(
            item.outcome is EvaluationCaseOutcome.ERROR for item in case_results
        ),
        unscored_case_count=sum(
            item.outcome is EvaluationCaseOutcome.UNSCORED for item in case_results
        ),
        execution_error_count=sum(
            item.execution_error is not None for item in case_results
        ),
        evaluator_error_count=evaluator_errors,
        metric_summaries=tuple(summaries),
    )
