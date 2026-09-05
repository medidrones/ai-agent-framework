"""Static definitions of provider-neutral agents."""

from pydantic import Field, field_validator

from atlas_agents._models import _FrozenModel, _json_mapping, _non_empty
from atlas_agents.memory.config import AgentMemoryConfig


class AgentDefinition(_FrozenModel):
    """Describe the immutable configuration that identifies an agent."""

    agent_id: str
    name: str
    description: str = ""
    instructions: str
    tool_names: tuple[str, ...] = ()
    memory: AgentMemoryConfig | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("agent_id", "name", "instructions")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        """Reject required text containing no meaningful characters."""
        return _non_empty(value)

    @field_validator("tool_names")
    @classmethod
    def validate_tool_names(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Require unique non-empty tool names while preserving declared order."""
        validated = tuple(_non_empty(name) for name in value)
        if len(set(validated)) != len(validated):
            msg = "Os nomes de ferramentas do agente não podem se repetir"
            raise ValueError(msg)
        return validated

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep metadata serializable and isolated from caller mutation."""
        return _json_mapping(value)
