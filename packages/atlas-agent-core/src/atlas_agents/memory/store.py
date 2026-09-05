"""Async storage abstraction for scoped memory records."""

from typing import Protocol

from atlas_agents.memory.models import (
    MemoryQuery,
    MemoryRecord,
    MemorySearchResult,
    MemoryWriteRequest,
)
from atlas_agents.memory.scope import MemoryScope


class MemoryStore(Protocol):
    """Persist and retrieve memories without exposing infrastructure details."""

    async def get(
        self,
        memory_id: str,
        *,
        scope: MemoryScope,
    ) -> MemoryRecord | None:
        """Return one exact-scope record when it exists."""
        ...

    async def write(self, request: MemoryWriteRequest) -> MemoryRecord:
        """Append one memory and return its definitive stored representation."""
        ...

    async def search(self, query: MemoryQuery) -> tuple[MemorySearchResult, ...]:
        """Search one type inside one exact scope in implementation-defined order."""
        ...

    async def delete(self, memory_id: str, *, scope: MemoryScope) -> bool:
        """Delete one exact-scope record and report whether it existed."""
        ...
