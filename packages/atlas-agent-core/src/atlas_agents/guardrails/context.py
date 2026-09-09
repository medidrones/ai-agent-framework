"""Restricted execution context passed to guardrails."""

from pydantic import Field, field_validator

from atlas_agents._models import _FrozenModel, _json_mapping, _non_empty
from atlas_agents.agents.context import ExecutionIdentity
from atlas_agents.guardrails.stage import GuardrailStage


class GuardrailContext(_FrozenModel):
    """Expose correlation and identity without mutable runtime services or state."""

    execution_id: str
    agent_id: str
    identity: ExecutionIdentity | None = None
    stage: GuardrailStage
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("execution_id", "agent_id")
    @classmethod
    def validate_ids(cls, value: str) -> str:
        """Reject empty execution and agent identifiers."""
        return _non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep metadata JSON-compatible and isolated."""
        return _json_mapping(value)
