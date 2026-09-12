"""Minimal metrics recording boundary."""

from typing import Protocol

from atlas_agents.observability.span import ObservabilityAttributes


class MetricsRecorder(Protocol):
    """Record counter-like and histogram-like scalar measurements."""

    def increment(
        self,
        name: str,
        value: int | float = 1,
        *,
        attributes: ObservabilityAttributes | None = None,
    ) -> None:
        """Increment a logical counter."""
        ...

    def record(
        self,
        name: str,
        value: int | float,
        *,
        attributes: ObservabilityAttributes | None = None,
    ) -> None:
        """Record a logical histogram measurement."""
        ...
