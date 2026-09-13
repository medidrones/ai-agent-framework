"""Optional idempotency contracts and a development in-memory store."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from atlas_agents.adapters.models import ExecuteAgentResponse


class IdempotencyState(StrEnum):
    """Represent the lifecycle of one reserved idempotency key."""

    PENDING = "pending"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    """Carry a fingerprint and optional completed response."""

    fingerprint: str
    state: IdempotencyState
    response: ExecuteAgentResponse | None = None


class IdempotencyStore(Protocol):
    """Reserve and complete keys without claiming distributed exactly-once."""

    async def get(self, key: str) -> IdempotencyRecord | None:
        """Return one current record."""
        ...

    async def reserve(
        self, key: str, fingerprint: str
    ) -> tuple[IdempotencyRecord, bool]:
        """Atomically reserve and report whether the record was created."""
        ...

    async def complete(
        self, key: str, fingerprint: str, response: ExecuteAgentResponse
    ) -> None:
        """Persist one completed response for replay."""
        ...

    async def fail(self, key: str, fingerprint: str) -> None:
        """Release a matching pending reservation after failure."""
        ...


class InMemoryIdempotencyStore:
    """Provide process-local idempotency for tests and development only."""

    def __init__(self) -> None:
        """Initialize isolated records protected by one async lock."""
        self._records: dict[str, IdempotencyRecord] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> IdempotencyRecord | None:
        """Return the immutable record when present."""
        async with self._lock:
            return self._records.get(key)

    async def reserve(
        self, key: str, fingerprint: str
    ) -> tuple[IdempotencyRecord, bool]:
        """Create one reservation without overwriting an existing key."""
        async with self._lock:
            existing = self._records.get(key)
            if existing is not None:
                return existing, False
            record = IdempotencyRecord(
                fingerprint=fingerprint, state=IdempotencyState.PENDING
            )
            self._records[key] = record
            return record, True

    async def complete(
        self, key: str, fingerprint: str, response: ExecuteAgentResponse
    ) -> None:
        """Complete only the matching reservation."""
        async with self._lock:
            current = self._records.get(key)
            if current is None or current.fingerprint != fingerprint:
                return
            self._records[key] = IdempotencyRecord(
                fingerprint=fingerprint,
                state=IdempotencyState.COMPLETED,
                response=response,
            )

    async def fail(self, key: str, fingerprint: str) -> None:
        """Remove only the matching pending reservation."""
        async with self._lock:
            current = self._records.get(key)
            if (
                current is not None
                and current.fingerprint == fingerprint
                and current.state is IdempotencyState.PENDING
            ):
                del self._records[key]
