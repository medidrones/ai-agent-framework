"""Restricted execution context supplied to a tool."""

from pydantic import Field, field_validator

from atlas_agents._models import _FrozenModel, _json_mapping, _non_empty
from atlas_agents.agents import ExecutionIdentity


class ToolExecutionContext(_FrozenModel):
    """Carry only explicit execution identity and correlation data to a tool."""

    execution_id: str
    agent_id: str
    tool_call_id: str
    identity: ExecutionIdentity | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("execution_id", "agent_id", "tool_call_id")
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        """Reject empty execution identifiers."""
        return _non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep metadata JSON-compatible and isolated."""
        return _json_mapping(value)
