"""Async retrieval boundary and immutable result contracts."""

import math
from typing import Protocol

from pydantic import Field, field_validator

from atlas_agents._models import _FrozenModel, _json_mapping
from atlas_agents.knowledge.passage import KnowledgePassage
from atlas_agents.knowledge.query import KnowledgeQuery, KnowledgeRetrievalContext
from atlas_agents.knowledge.source import KnowledgeSource


class KnowledgeRetrievalResult(_FrozenModel):
    """Represent one ordered passage returned by a retriever."""

    passage: KnowledgePassage
    score: float | None = None
    rank: int | None = Field(default=None, gt=0)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("score")
    @classmethod
    def validate_score(cls, value: float | None) -> float | None:
        """Reject non-finite implementation-specific scores."""
        if value is not None and not math.isfinite(value):
            raise ValueError("O score de recuperação deve ser finito")
        return value

    @field_validator("rank", mode="before")
    @classmethod
    def reject_boolean_rank(cls, value: object) -> object:
        """Reject booleans as ranks."""
        if isinstance(value, bool):
            raise ValueError("O rank de recuperação não pode ser booleano")
        return value

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep result metadata JSON-compatible and isolated."""
        return _json_mapping(value)


class KnowledgeRetriever(Protocol):
    """Retrieve external passages without exposing search implementation details."""

    async def sources(self) -> tuple[KnowledgeSource, ...]:
        """Return logical source descriptors for introspection."""
        ...

    async def retrieve(
        self,
        query: KnowledgeQuery,
        context: KnowledgeRetrievalContext,
    ) -> tuple[KnowledgeRetrievalResult, ...]:
        """Retrieve ordered passages under explicit query and execution context."""
        ...
