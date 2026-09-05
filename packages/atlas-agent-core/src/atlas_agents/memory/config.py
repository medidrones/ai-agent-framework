"""Explicit per-agent memory configuration."""

from pydantic import Field, field_validator

from atlas_agents._models import _FrozenModel
from atlas_agents.memory.types import MemoryType


class AgentMemoryConfig(_FrozenModel):
    """Opt an agent into specific memory reads and writes with safe limits."""

    read_types: frozenset[MemoryType] = frozenset()
    write_types: frozenset[MemoryType] = frozenset()
    max_records_per_type: int = Field(default=20, gt=0)
    max_characters: int = Field(default=8_000, gt=0)

    @field_validator("max_records_per_type", "max_characters", mode="before")
    @classmethod
    def reject_boolean_limits(cls, value: object) -> object:
        """Reject booleans as numeric memory limits."""
        if isinstance(value, bool):
            raise ValueError("Limites de memória não podem ser booleanos")
        return value

    @property
    def enabled(self) -> bool:
        """Return whether this configuration requests any memory operation."""
        return bool(self.read_types or self.write_types)
