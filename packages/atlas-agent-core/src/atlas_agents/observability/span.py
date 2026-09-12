"""Provider-neutral span contracts."""

from collections.abc import Mapping
from enum import StrEnum
from typing import Protocol

from atlas_agents.observability.context import TraceContext

type ObservabilityAttributeValue = str | bool | int | float
type ObservabilityAttributes = Mapping[str, ObservabilityAttributeValue]


class SpanKind(StrEnum):
    """Describe the logical relationship represented by a span."""

    INTERNAL = "internal"
    CLIENT = "client"


class SpanStatus(StrEnum):
    """Describe the technical completion status of a span."""

    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


class Span(Protocol):
    """Receive synchronous tracing operations from the runtime."""

    @property
    def context(self) -> TraceContext | None:
        """Return a serializable propagation context when available."""
        ...

    def set_attribute(self, name: str, value: ObservabilityAttributeValue) -> None:
        """Set one provider-neutral scalar attribute."""
        ...

    def add_event(
        self,
        name: str,
        attributes: ObservabilityAttributes | None = None,
    ) -> None:
        """Add a structured, content-free operational event."""
        ...

    def record_exception(self, error: BaseException) -> None:
        """Optionally record an exception when explicitly requested by a host."""
        ...

    def set_status(
        self,
        status: SpanStatus,
        description: str | None = None,
    ) -> None:
        """Set the technical span status."""
        ...

    def end(self) -> None:
        """End the span idempotently."""
        ...
