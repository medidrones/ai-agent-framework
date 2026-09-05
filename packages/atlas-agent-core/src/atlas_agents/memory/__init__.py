"""Storage-agnostic contracts and coordination for scoped agent memory."""

from atlas_agents.memory.config import AgentMemoryConfig
from atlas_agents.memory.errors import (
    AgentMemoryError,
    MemoryPolicyViolationError,
    MemoryScopeResolutionError,
    MemoryStoreOperationError,
    MemoryStoreProtocolError,
)
from atlas_agents.memory.manager import MemoryManager
from atlas_agents.memory.models import (
    MemoryCandidate,
    MemoryQuery,
    MemoryRecord,
    MemorySearchResult,
    MemoryWriteRequest,
)
from atlas_agents.memory.policy import (
    DefaultMemoryScopePolicy,
    MemoryScopePolicy,
    MemoryWritePolicy,
    NoMemoryWritePolicy,
)
from atlas_agents.memory.renderer import MemoryContextRenderer
from atlas_agents.memory.scope import MemoryScope
from atlas_agents.memory.selection import (
    DeterministicMemorySelectionPolicy,
    MemorySelectionPolicy,
)
from atlas_agents.memory.store import MemoryStore
from atlas_agents.memory.types import MemoryType

__all__ = [
    "AgentMemoryConfig",
    "AgentMemoryError",
    "DefaultMemoryScopePolicy",
    "DeterministicMemorySelectionPolicy",
    "MemoryCandidate",
    "MemoryContextRenderer",
    "MemoryManager",
    "MemoryPolicyViolationError",
    "MemoryQuery",
    "MemoryRecord",
    "MemoryScope",
    "MemoryScopePolicy",
    "MemoryScopeResolutionError",
    "MemorySearchResult",
    "MemorySelectionPolicy",
    "MemoryStore",
    "MemoryStoreOperationError",
    "MemoryStoreProtocolError",
    "MemoryType",
    "MemoryWritePolicy",
    "MemoryWriteRequest",
    "NoMemoryWritePolicy",
]
