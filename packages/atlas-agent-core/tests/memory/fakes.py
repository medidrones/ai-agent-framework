"""Reusable memory store and policy test doubles."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime

from atlas_agents import (
    AgentDefinition,
    ExecutionSnapshot,
    MemoryCandidate,
    MemoryQuery,
    MemoryRecord,
    MemoryScope,
    MemorySearchResult,
    MemoryType,
    MemoryWriteRequest,
)


class FakeMemoryStore:
    def __init__(
        self,
        *,
        search_factory: Callable[[MemoryQuery], object] | None = None,
        search_error: Exception | None = None,
        write_error: Exception | None = None,
        search_wait_event: asyncio.Event | None = None,
        write_wait_event: asyncio.Event | None = None,
    ) -> None:
        self.records: dict[str, MemoryRecord] = {}
        self.search_factory = search_factory
        self.search_error = search_error
        self.write_error = write_error
        self.search_wait_event = search_wait_event
        self.write_wait_event = write_wait_event
        self.searches: list[MemoryQuery] = []
        self.writes: list[MemoryWriteRequest] = []
        self.search_started = asyncio.Event()
        self.write_started = asyncio.Event()

    async def get(
        self,
        memory_id: str,
        *,
        scope: MemoryScope,
    ) -> MemoryRecord | None:
        record = self.records.get(memory_id)
        return record if record is not None and record.scope == scope else None

    async def write(self, request: MemoryWriteRequest) -> MemoryRecord:
        self.writes.append(request)
        self.write_started.set()
        if self.write_wait_event is not None:
            await self.write_wait_event.wait()
        if self.write_error is not None:
            raise self.write_error
        now = datetime.now(UTC)
        record = MemoryRecord(
            memory_id=f"memory-{len(self.records) + 1}",
            memory_type=request.memory_type,
            scope=request.scope,
            content=request.content,
            created_at=now,
            updated_at=now,
            expires_at=request.expires_at,
            metadata=request.metadata,
        )
        self.records[record.memory_id] = record
        return record

    async def search(self, query: MemoryQuery) -> tuple[MemorySearchResult, ...]:
        self.searches.append(query)
        self.search_started.set()
        if self.search_wait_event is not None:
            await self.search_wait_event.wait()
        if self.search_error is not None:
            raise self.search_error
        if self.search_factory is not None:
            return self.search_factory(query)  # type: ignore[return-value]
        matches = (
            record
            for record in self.records.values()
            if record.scope == query.scope and record.memory_type is query.memory_type
        )
        ordered = sorted(
            matches, key=lambda item: (-item.updated_at.timestamp(), item.memory_id)
        )
        return tuple(
            MemorySearchResult(record=record) for record in ordered[: query.limit]
        )

    async def delete(self, memory_id: str, *, scope: MemoryScope) -> bool:
        record = self.records.get(memory_id)
        if record is None or record.scope != scope:
            return False
        del self.records[memory_id]
        return True


class FixedMemoryWritePolicy:
    def __init__(self, candidates: tuple[MemoryCandidate, ...]) -> None:
        self.candidates = candidates
        self.calls = 0

    def select(
        self,
        *,
        agent: AgentDefinition,
        snapshot: ExecutionSnapshot,
        output: object,
    ) -> tuple[MemoryCandidate, ...]:
        del agent
        self.calls += 1
        assert snapshot.output is None
        assert output is not None
        return self.candidates


def memory_record(
    *,
    memory_id: str,
    memory_type: MemoryType,
    scope: MemoryScope,
    content: str = "Contexto lembrado.",
    created_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> MemoryRecord:
    now = created_at or datetime.now(UTC)
    return MemoryRecord(
        memory_id=memory_id,
        memory_type=memory_type,
        scope=scope,
        content=content,
        created_at=now,
        updated_at=now,
        expires_at=expires_at,
    )
