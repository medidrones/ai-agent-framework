"""Provider-neutral knowledge query and authorization context contracts."""

from pydantic import Field, field_validator

from atlas_agents._models import _FrozenModel, _json_mapping, _non_empty
from atlas_agents.agents.context import ExecutionIdentity


class KnowledgeQuery(_FrozenModel):
    """Request textual retrieval from an ordered set of logical sources."""

    text: str
    source_ids: tuple[str, ...] = ()
    filters: dict[str, object] = Field(default_factory=dict)
    limit: int = Field(default=8, gt=0)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        """Require an explicit non-empty textual query."""
        return _non_empty(value)

    @field_validator("source_ids")
    @classmethod
    def validate_source_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Preserve ordered unique opaque source identifiers."""
        validated = tuple(_non_empty(source_id) for source_id in value)
        if len(set(validated)) != len(validated):
            raise ValueError("As fontes da consulta não podem se repetir")
        return validated

    @field_validator("limit", mode="before")
    @classmethod
    def reject_boolean_limit(cls, value: object) -> object:
        """Reject booleans as retrieval limits."""
        if isinstance(value, bool):
            raise ValueError("O limite de conhecimento não pode ser booleano")
        return value

    @field_validator("filters", "metadata")
    @classmethod
    def validate_mappings(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep filters and metadata provider-neutral and JSON-compatible."""
        return _json_mapping(value)


class KnowledgeRetrievalContext(_FrozenModel):
    """Carry only formal execution facts required by a retriever adapter."""

    execution_id: str
    agent_id: str
    identity: ExecutionIdentity | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("execution_id", "agent_id")
    @classmethod
    def validate_ids(cls, value: str) -> str:
        """Reject blank execution and agent identifiers."""
        return _non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep explicitly supplied safe metadata isolated."""
        return _json_mapping(value)
