"""Provider-neutral opt-in LLM-as-judge contracts."""

import math
from typing import Protocol, runtime_checkable

from pydantic import Field, JsonValue, field_validator

from atlas_agents.evaluation._models import (
    FrozenEvaluationModel,
    json_mapping,
    non_empty,
)
from atlas_agents.evaluation.evaluator import EvaluationContext


class JudgeRequest(FrozenEvaluationModel):
    """Carry explicitly opted-in untrusted data to an evaluation judge."""

    criteria: str
    candidate: JsonValue
    reference: JsonValue | None = None
    rubric: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("criteria")
    @classmethod
    def validate_criteria(cls, value: str) -> str:
        """Reject blank judging criteria."""
        return non_empty(value)

    @field_validator("rubric")
    @classmethod
    def validate_rubric(cls, value: str | None) -> str | None:
        """Reject an explicitly blank rubric."""
        return None if value is None else non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        """Keep judge metadata JSON-compatible and isolated."""
        return json_mapping(value)


class JudgeResponse(FrozenEvaluationModel):
    """Return a finite judge score and untrusted explanatory reason."""

    score: float
    reason: str
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("score")
    @classmethod
    def validate_score(cls, value: float) -> float:
        """Reject NaN and infinite judge scores."""
        if not math.isfinite(value):
            raise ValueError("O score do judge deve ser finito")
        return value

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        """Reject a blank judge reason."""
        return non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        """Keep judge metadata JSON-compatible and isolated."""
        return json_mapping(value)


@runtime_checkable
class EvaluationJudge(Protocol):
    """Judge an explicit request without requiring any model vendor SDK."""

    async def judge(
        self,
        request: JudgeRequest,
        context: EvaluationContext,
    ) -> JudgeResponse:
        """Return one provider-neutral judging response."""
        ...
