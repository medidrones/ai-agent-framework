"""Tracing provider boundary."""

from typing import Protocol

from atlas_agents.observability.context import TraceContext
from atlas_agents.observability.span import ObservabilityAttributes, Span, SpanKind


class Tracer(Protocol):
    """Synchronously create logical spans without performing runtime I/O."""

    def start_span(
        self,
        name: str,
        *,
        kind: SpanKind = SpanKind.INTERNAL,
        parent: TraceContext | None = None,
        attributes: ObservabilityAttributes | None = None,
    ) -> Span:
        """Start one span under an explicit optional parent context."""
        ...
