"""Immutable evaluation inputs, expectations, and cases."""

from typing import Self

from pydantic import Field, JsonValue, field_validator, model_validator

from atlas_agents import AgentInput
from atlas_agents.evaluation._models import (
    FrozenEvaluationModel,
    json_mapping,
    non_empty,
)
from atlas_agents.evaluation.errors import DuplicateExpectationError


class EvaluationInput(FrozenEvaluationModel):
    """Describe optional production input used when executing an evaluation case."""

    agent_input: AgentInput | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        """Keep metadata JSON-compatible and isolated."""
        return json_mapping(value)


class EvaluationExpectation(FrozenEvaluationModel):
    """Bind an explicit expected value to one configured evaluator."""

    expectation_id: str
    evaluator_id: str
    expected: JsonValue
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("expectation_id", "evaluator_id")
    @classmethod
    def validate_ids(cls, value: str) -> str:
        """Reject blank stable identifiers."""
        return non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        """Keep metadata JSON-compatible and isolated."""
        return json_mapping(value)


class EvaluationCase(FrozenEvaluationModel):
    """Describe one reproducible input and its ordered expectations."""

    case_id: str
    name: str
    input: EvaluationInput = EvaluationInput()
    expectations: tuple[EvaluationExpectation, ...] = ()
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("case_id", "name")
    @classmethod
    def validate_text(cls, value: str) -> str:
        """Reject blank case identifiers and names."""
        return non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        """Keep metadata JSON-compatible and isolated."""
        return json_mapping(value)

    @model_validator(mode="after")
    def validate_expectation_ids(self) -> Self:
        """Require unique expectation IDs while preserving order."""
        identifiers = tuple(item.expectation_id for item in self.expectations)
        if len(set(identifiers)) != len(identifiers):
            raise DuplicateExpectationError(
                "Os identificadores de expectativa não podem se repetir."
            )
        return self
