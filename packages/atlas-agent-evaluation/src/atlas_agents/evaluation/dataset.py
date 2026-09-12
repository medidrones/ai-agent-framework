"""Versioned ordered evaluation dataset contracts."""

from typing import Self

from pydantic import Field, JsonValue, field_validator, model_validator

from atlas_agents.evaluation._models import (
    FrozenEvaluationModel,
    json_mapping,
    non_empty,
)
from atlas_agents.evaluation.case import EvaluationCase
from atlas_agents.evaluation.errors import DuplicateEvaluationCaseError


class EvaluationDataset(FrozenEvaluationModel):
    """Group ordered cases under a stable dataset identity and version."""

    dataset_id: str
    name: str
    version: str
    cases: tuple[EvaluationCase, ...] = ()
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("dataset_id", "name", "version")
    @classmethod
    def validate_text(cls, value: str) -> str:
        """Reject blank dataset identity fields."""
        return non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        """Keep metadata JSON-compatible and isolated."""
        return json_mapping(value)

    @model_validator(mode="after")
    def validate_case_ids(self) -> Self:
        """Reject duplicate cases while allowing an empty dataset."""
        identifiers = tuple(case.case_id for case in self.cases)
        if len(set(identifiers)) != len(identifiers):
            raise DuplicateEvaluationCaseError(
                "Os identificadores de casos não podem se repetir."
            )
        return self
