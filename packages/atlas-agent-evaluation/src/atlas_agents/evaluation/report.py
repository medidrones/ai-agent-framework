"""Privacy-safe evaluation case and report contracts."""

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import Field, JsonValue, field_validator, model_validator

from atlas_agents.evaluation._models import (
    FrozenEvaluationModel,
    json_mapping,
    non_empty,
    timezone_aware,
)
from atlas_agents.evaluation.observation import EvaluationObservationSummary
from atlas_agents.evaluation.result import (
    EvaluationErrorInfo,
    EvaluationResult,
    EvaluationResultStatus,
)


class EvaluationCaseOutcome(StrEnum):
    """Classify one case independently from the production execution status."""

    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    UNSCORED = "unscored"


class EvaluationReportOutcome(StrEnum):
    """Classify a report using error, failure, pass, and unscored priority."""

    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    UNSCORED = "unscored"


class EvaluationMetricSummary(FrozenEvaluationModel):
    """Aggregate compatible completed results for one metric."""

    metric_id: str
    count: int = Field(ge=0)
    mean: float | None = None
    min: float | None = None
    max: float | None = None
    passed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    unscored_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        """Require score classifications to cover the metric count exactly."""
        if self.passed_count + self.failed_count + self.unscored_count != self.count:
            raise ValueError("As contagens da métrica devem totalizar count")
        return self


class EvaluationSummary(FrozenEvaluationModel):
    """Summarize mutually exclusive case outcomes and evaluator failures."""

    case_count: int = Field(ge=0)
    passed_case_count: int = Field(ge=0)
    failed_case_count: int = Field(ge=0)
    errored_case_count: int = Field(ge=0)
    unscored_case_count: int = Field(ge=0)
    execution_error_count: int = Field(ge=0)
    evaluator_error_count: int = Field(ge=0)
    metric_summaries: tuple[EvaluationMetricSummary, ...] = ()

    @model_validator(mode="after")
    def validate_case_counts(self) -> Self:
        """Require mutually exclusive case categories to cover the dataset."""
        classified = (
            self.passed_case_count
            + self.failed_case_count
            + self.errored_case_count
            + self.unscored_case_count
        )
        if classified != self.case_count:
            raise ValueError("As categorias de casos devem totalizar case_count")
        if self.execution_error_count > self.errored_case_count:
            raise ValueError("Erros de execução não podem exceder casos com erro")
        return self


class EvaluationCaseResult(FrozenEvaluationModel):
    """Persist one case outcome without retaining final production output."""

    case_id: str
    execution_id: str | None = None
    observation_summary: EvaluationObservationSummary | None = None
    evaluation_results: tuple[EvaluationResult, ...] = ()
    outcome: EvaluationCaseOutcome
    execution_error: EvaluationErrorInfo | None = None

    @field_validator("case_id")
    @classmethod
    def validate_case_id(cls, value: str) -> str:
        """Reject a blank case identifier."""
        return non_empty(value)

    @field_validator("execution_id")
    @classmethod
    def validate_execution_id(cls, value: str | None) -> str | None:
        """Reject an explicitly blank execution identifier."""
        return None if value is None else non_empty(value)

    @property
    def passed(self) -> bool | None:
        """Expose a compatibility convenience derived from the case outcome."""
        if self.outcome is EvaluationCaseOutcome.PASSED:
            return True
        if self.outcome is EvaluationCaseOutcome.FAILED:
            return False
        return None

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        """Require the declared outcome to match execution and evaluator facts."""
        if self.execution_error is not None or any(
            result.status is EvaluationResultStatus.ERROR
            for result in self.evaluation_results
        ):
            expected = EvaluationCaseOutcome.ERROR
        else:
            decisions = tuple(
                result.score.passed
                for result in self.evaluation_results
                if result.status is EvaluationResultStatus.COMPLETED
                and result.score is not None
                and result.score.passed is not None
            )
            if any(decision is False for decision in decisions):
                expected = EvaluationCaseOutcome.FAILED
            elif decisions:
                expected = EvaluationCaseOutcome.PASSED
            else:
                expected = EvaluationCaseOutcome.UNSCORED
        if self.outcome is not expected:
            raise ValueError("O outcome do caso não corresponde aos resultados")
        return self


class EvaluationReport(FrozenEvaluationModel):
    """Describe one reproducible evaluation run and its aggregate summary."""

    evaluation_run_id: str
    dataset_id: str
    dataset_version: str
    started_at: datetime
    completed_at: datetime
    case_results: tuple[EvaluationCaseResult, ...]
    summary: EvaluationSummary
    outcome: EvaluationReportOutcome
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("evaluation_run_id", "dataset_id", "dataset_version")
    @classmethod
    def validate_ids(cls, value: str) -> str:
        """Reject blank report correlation fields."""
        return non_empty(value)

    @field_validator("started_at", "completed_at")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        """Require timezone-aware report timestamps."""
        return timezone_aware(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        """Keep report metadata JSON-compatible and isolated."""
        return json_mapping(value)

    @model_validator(mode="after")
    def validate_timeline(self) -> Self:
        """Require completion to occur at or after report start."""
        if self.completed_at < self.started_at:
            raise ValueError("O relatório não pode terminar antes de iniciar")
        if self.summary.case_count != len(self.case_results):
            raise ValueError("O summary deve cobrir todos os casos do relatório")
        return self
