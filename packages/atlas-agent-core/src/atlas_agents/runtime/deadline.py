"""Absolute monotonic deadline support for runtime-owned timeouts."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TypeVar

T = TypeVar("T")
MonotonicClock = Callable[[], float]


class ExecutionDeadlineExpiredError(Exception):
    """Signal that the runtime-owned absolute execution deadline expired."""


@dataclass(frozen=True)
class ExecutionDeadline:
    """Track one optional absolute deadline using a monotonic clock."""

    timeout_seconds: float | None
    started_at: float
    deadline_at: float | None
    _clock: MonotonicClock = field(repr=False, compare=False)

    @classmethod
    def start(
        cls,
        timeout_seconds: float | None,
        *,
        clock: MonotonicClock = time.monotonic,
    ) -> "ExecutionDeadline":
        """Start one deadline without relying on wall-clock timestamps."""
        started_at = clock()
        deadline_at = None if timeout_seconds is None else started_at + timeout_seconds
        return cls(timeout_seconds, started_at, deadline_at, clock)

    @property
    def elapsed_seconds(self) -> float:
        """Return elapsed monotonic time since this deadline started."""
        return max(0.0, self._clock() - self.started_at)

    @property
    def expired(self) -> bool:
        """Return whether the configured deadline has elapsed."""
        return self.deadline_at is not None and self._clock() >= self.deadline_at

    def remaining_seconds(self) -> float | None:
        """Return non-negative time remaining, or None for no deadline."""
        if self.deadline_at is None:
            return None
        return max(0.0, self.deadline_at - self._clock())

    def raise_if_expired(self) -> None:
        """Raise the internal signal when the absolute deadline has elapsed."""
        if self.expired:
            raise ExecutionDeadlineExpiredError

    async def wait_for(self, operation: Callable[[], Awaitable[T]]) -> T:
        """Await an operation against the unchanged absolute deadline."""
        remaining = self.remaining_seconds()
        if remaining is None:
            return await operation()
        if remaining <= 0:
            raise ExecutionDeadlineExpiredError
        timeout = asyncio.timeout(remaining)
        try:
            async with timeout:
                result = await operation()
        except TimeoutError as exc:
            if timeout.expired():
                raise ExecutionDeadlineExpiredError from exc
            raise
        self.raise_if_expired()
        return result
