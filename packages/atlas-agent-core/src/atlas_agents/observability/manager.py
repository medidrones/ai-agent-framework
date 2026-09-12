"""Fail-open observability coordination."""

import time
from collections.abc import Callable, Mapping
from contextlib import suppress

from atlas_agents.observability.attributes import SafeAttributeBuilder
from atlas_agents.observability.context import TraceContext
from atlas_agents.observability.metrics import MetricsRecorder
from atlas_agents.observability.noop import NoOpMetricsRecorder, NoOpSpan, NoOpTracer
from atlas_agents.observability.span import Span, SpanKind, SpanStatus
from atlas_agents.observability.tracing import Tracer

MonotonicClock = Callable[[], float]


class SafeSpan:
    """Isolate all failures raised by a tracing adapter."""

    def __init__(self, delegate: Span) -> None:
        """Wrap one adapter span without exposing it to the runtime."""
        self._delegate = delegate
        self._ended = False

    @property
    def context(self) -> TraceContext | None:
        """Return context or None when the adapter cannot provide it."""
        try:
            context = self._delegate.context
        except Exception:
            return None
        return context if isinstance(context, TraceContext) else None

    @property
    def ended(self) -> bool:
        """Return whether end was already requested."""
        return self._ended

    def set_attribute(self, name: str, value: object) -> None:
        """Set one allowed scalar attribute without propagating failures."""
        if self._ended:
            return
        attributes = SafeAttributeBuilder.span({name: value})
        if name not in attributes:
            return
        with suppress(Exception):
            self._delegate.set_attribute(name, attributes[name])

    def add_event(
        self,
        name: str,
        attributes: Mapping[str, object] | None = None,
    ) -> None:
        """Add a content-free event without propagating failures."""
        if self._ended:
            return
        with suppress(Exception):
            self._delegate.add_event(name, SafeAttributeBuilder.span(attributes))

    def record_exception(self, error: BaseException) -> None:
        """Delegate an explicitly requested exception without propagating failures."""
        if self._ended:
            return
        with suppress(Exception):
            self._delegate.record_exception(error)

    def set_status(
        self,
        status: SpanStatus,
        description: str | None = None,
    ) -> None:
        """Set status without propagating failures."""
        if self._ended:
            return
        with suppress(Exception):
            self._delegate.set_status(status, description)

    def end(self) -> None:
        """End the delegate at most once, even when it raises."""
        if self._ended:
            return
        self._ended = True
        with suppress(Exception):
            self._delegate.end()


class ObservabilityManager:
    """Provide safe spans, metrics, and a shared monotonic timer."""

    def __init__(
        self,
        *,
        tracer: Tracer | None = None,
        metrics: MetricsRecorder | None = None,
        clock: MonotonicClock = time.monotonic,
    ) -> None:
        """Initialize explicit adapters with safe no-op defaults."""
        self._tracer = tracer if tracer is not None else NoOpTracer()
        self._metrics = metrics if metrics is not None else NoOpMetricsRecorder()
        self._clock = clock

    def now(self) -> float:
        """Read the injected monotonic clock for duration measurements."""
        try:
            return self._clock()
        except Exception:
            return time.monotonic()

    def elapsed_since(self, started_at: float) -> float:
        """Return a non-negative duration from the same monotonic clock."""
        try:
            current = self._clock()
        except Exception:
            current = time.monotonic()
        return max(0.0, current - started_at)

    def start_span(
        self,
        name: str,
        *,
        kind: SpanKind = SpanKind.INTERNAL,
        parent: TraceContext | None = None,
        attributes: Mapping[str, object] | None = None,
    ) -> SafeSpan:
        """Start a safe span or transparently fall back to no-op."""
        safe_attributes = SafeAttributeBuilder.span(attributes)
        try:
            delegate = self._tracer.start_span(
                name,
                kind=kind,
                parent=parent,
                attributes=safe_attributes,
            )
        except Exception:
            delegate = NoOpSpan()
        return SafeSpan(delegate)

    def increment(
        self,
        name: str,
        value: int | float = 1,
        *,
        attributes: Mapping[str, object] | None = None,
    ) -> None:
        """Record a counter-like metric without propagating adapter failures."""
        with suppress(Exception):
            self._metrics.increment(
                name,
                value,
                attributes=SafeAttributeBuilder.metric(attributes),
            )

    def record(
        self,
        name: str,
        value: int | float,
        *,
        attributes: Mapping[str, object] | None = None,
    ) -> None:
        """Record a histogram-like metric without propagating adapter failures."""
        with suppress(Exception):
            self._metrics.record(
                name,
                value,
                attributes=SafeAttributeBuilder.metric(attributes),
            )
