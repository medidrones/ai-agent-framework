"""No-op observability implementations."""

from atlas_agents.observability.context import TraceContext
from atlas_agents.observability.span import (
    ObservabilityAttributes,
    ObservabilityAttributeValue,
    SpanKind,
    SpanStatus,
)


class NoOpSpan:
    """Accept span operations without retaining or exporting telemetry."""

    @property
    def context(self) -> TraceContext | None:
        """Return no invented propagation context."""
        return None

    def set_attribute(self, name: str, value: ObservabilityAttributeValue) -> None:
        """Ignore an attribute."""
        del name, value

    def add_event(
        self,
        name: str,
        attributes: ObservabilityAttributes | None = None,
    ) -> None:
        """Ignore an event."""
        del name, attributes

    def record_exception(self, error: BaseException) -> None:
        """Ignore an explicitly supplied exception."""
        del error

    def set_status(
        self,
        status: SpanStatus,
        description: str | None = None,
    ) -> None:
        """Ignore a status update."""
        del status, description

    def end(self) -> None:
        """End idempotently without side effects."""


class NoOpTracer:
    """Create no-op spans without inventing trace identifiers."""

    def start_span(
        self,
        name: str,
        *,
        kind: SpanKind = SpanKind.INTERNAL,
        parent: TraceContext | None = None,
        attributes: ObservabilityAttributes | None = None,
    ) -> NoOpSpan:
        """Return a fresh no-op span."""
        del name, kind, parent, attributes
        return NoOpSpan()


class NoOpMetricsRecorder:
    """Ignore all metric operations."""

    def increment(
        self,
        name: str,
        value: int | float = 1,
        *,
        attributes: ObservabilityAttributes | None = None,
    ) -> None:
        """Ignore a counter increment."""
        del name, value, attributes

    def record(
        self,
        name: str,
        value: int | float,
        *,
        attributes: ObservabilityAttributes | None = None,
    ) -> None:
        """Ignore a histogram measurement."""
        del name, value, attributes
