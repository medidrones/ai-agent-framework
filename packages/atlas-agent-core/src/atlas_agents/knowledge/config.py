"""Explicit per-agent external knowledge configuration."""

from pydantic import Field, field_validator

from atlas_agents._models import _FrozenModel, _non_empty


class AgentKnowledgeConfig(_FrozenModel):
    """Opt an agent into an ordered allowlist of knowledge sources."""

    source_ids: tuple[str, ...] = ()
    max_results: int = Field(default=8, gt=0)
    max_characters: int = Field(default=12_000, gt=0)

    @field_validator("source_ids")
    @classmethod
    def validate_source_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Require unique non-empty source identifiers in declared order."""
        validated = tuple(_non_empty(source_id) for source_id in value)
        if len(set(validated)) != len(validated):
            raise ValueError("As fontes de conhecimento do agente não podem se repetir")
        return validated

    @field_validator("max_results", "max_characters", mode="before")
    @classmethod
    def reject_boolean_limits(cls, value: object) -> object:
        """Reject booleans as numeric context assembly limits."""
        if isinstance(value, bool):
            raise ValueError("Limites de conhecimento não podem ser booleanos")
        return value

    @property
    def enabled(self) -> bool:
        """Return whether at least one source was explicitly allowed."""
        return bool(self.source_ids)
