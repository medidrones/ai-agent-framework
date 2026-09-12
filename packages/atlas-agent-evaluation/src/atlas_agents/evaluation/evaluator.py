"""Async evaluator, executor, registry, and context contracts."""

from collections.abc import Callable
from typing import Protocol

from pydantic import Field, JsonValue, field_validator

from atlas_agents import AgentContext
from atlas_agents.evaluation._models import (
    FrozenEvaluationModel,
    json_mapping,
    non_empty,
)
from atlas_agents.evaluation.case import EvaluationCase, EvaluationExpectation
from atlas_agents.evaluation.errors import (
    DuplicateEvaluatorError,
    EvaluatorNotRegisteredError,
)
from atlas_agents.evaluation.metric import EvaluationMetric
from atlas_agents.evaluation.observation import EvaluationObservation
from atlas_agents.evaluation.result import EvaluationResult


class EvaluationContext(FrozenEvaluationModel):
    """Carry immutable correlation facts for one evaluator invocation."""

    evaluation_run_id: str
    dataset_id: str
    case_id: str
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("evaluation_run_id", "dataset_id", "case_id")
    @classmethod
    def validate_ids(cls, value: str) -> str:
        """Reject blank evaluation correlation identifiers."""
        return non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        """Keep context metadata JSON-compatible and isolated."""
        return json_mapping(value)


class Evaluator(Protocol):
    """Evaluate one explicit expectation against an immutable observation."""

    @property
    def evaluator_id(self) -> str:
        """Return the stable evaluator identifier."""
        ...

    @property
    def metric(self) -> EvaluationMetric:
        """Return the metric definition emitted by this evaluator."""
        ...

    async def evaluate(
        self,
        case: EvaluationCase,
        expectation: EvaluationExpectation,
        observation: EvaluationObservation,
        context: EvaluationContext,
    ) -> EvaluationResult:
        """Measure the observation without mutating production artifacts."""
        ...


class EvaluationExecutor(Protocol):
    """Produce an immutable observation through an explicitly configured path."""

    async def execute(self, case: EvaluationCase) -> EvaluationObservation:
        """Execute or retrieve one case observation."""
        ...


type EvaluationContextFactory = Callable[[EvaluationCase], AgentContext]


class EvaluatorRegistry:
    """Store evaluators by exact identifier in deterministic registration order."""

    def __init__(self, evaluators: tuple[Evaluator, ...] = ()) -> None:
        """Initialize an isolated registry and register initial evaluators."""
        self._evaluators: dict[str, Evaluator] = {}
        for evaluator in evaluators:
            self.register(evaluator)

    @property
    def evaluators(self) -> tuple[Evaluator, ...]:
        """Return evaluators in registration order."""
        return tuple(self._evaluators.values())

    def register(self, evaluator: Evaluator) -> None:
        """Register one evaluator and reject duplicate IDs."""
        identifier = non_empty(evaluator.evaluator_id)
        if identifier in self._evaluators:
            raise DuplicateEvaluatorError(
                f"O evaluator '{identifier}' já está registrado."
            )
        self._evaluators[identifier] = evaluator

    def unregister(self, evaluator_id: str) -> Evaluator:
        """Remove and return an evaluator by exact identifier."""
        identifier = non_empty(evaluator_id)
        evaluator = self._evaluators.pop(identifier, None)
        if evaluator is None:
            raise EvaluatorNotRegisteredError(
                f"O evaluator '{identifier}' não está registrado."
            )
        return evaluator

    def get(self, evaluator_id: str) -> Evaluator:
        """Resolve an evaluator or raise a typed error."""
        identifier = non_empty(evaluator_id)
        evaluator = self._evaluators.get(identifier)
        if evaluator is None:
            raise EvaluatorNotRegisteredError(
                f"O evaluator '{identifier}' não está registrado."
            )
        return evaluator

    def try_get(self, evaluator_id: str) -> Evaluator | None:
        """Resolve an evaluator without raising when it is absent."""
        return self._evaluators.get(non_empty(evaluator_id))
