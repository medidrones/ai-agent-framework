"""Deterministic observability test doubles."""

from dataclasses import dataclass, field

from atlas_agents import (
    ObservabilityAttributes,
    ObservabilityAttributeValue,
    SpanKind,
    SpanStatus,
    TraceContext,
)


@dataclass
class FakeSpan:
    name: str
    kind: SpanKind
    parent: TraceContext | None
    context: TraceContext | None
    attributes: dict[str, ObservabilityAttributeValue] = field(default_factory=dict)
    events: list[tuple[str, dict[str, ObservabilityAttributeValue]]] = field(
        default_factory=list
    )
    statuses: list[tuple[SpanStatus, str | None]] = field(default_factory=list)
    exceptions: list[BaseException] = field(default_factory=list)
    end_count: int = 0
    fail_operations: bool = False

    def set_attribute(self, name: str, value: ObservabilityAttributeValue) -> None:
        if self.fail_operations:
            raise RuntimeError("telemetry failure")
        self.attributes[name] = value

    def add_event(
        self,
        name: str,
        attributes: ObservabilityAttributes | None = None,
    ) -> None:
        if self.fail_operations:
            raise RuntimeError("telemetry failure")
        self.events.append((name, dict(attributes or {})))

    def record_exception(self, error: BaseException) -> None:
        if self.fail_operations:
            raise RuntimeError("telemetry failure")
        self.exceptions.append(error)

    def set_status(
        self,
        status: SpanStatus,
        description: str | None = None,
    ) -> None:
        if self.fail_operations:
            raise RuntimeError("telemetry failure")
        self.statuses.append((status, description))

    def end(self) -> None:
        self.end_count += 1
        if self.fail_operations:
            raise RuntimeError("telemetry failure")


class FakeTracer:
    def __init__(
        self,
        *,
        fail_start: bool = False,
        fail_operations: bool = False,
    ) -> None:
        self.fail_start = fail_start
        self.fail_operations = fail_operations
        self.spans: list[FakeSpan] = []

    def start_span(
        self,
        name: str,
        *,
        kind: SpanKind = SpanKind.INTERNAL,
        parent: TraceContext | None = None,
        attributes: ObservabilityAttributes | None = None,
    ) -> FakeSpan:
        if self.fail_start:
            raise RuntimeError("telemetry failure")
        index = len(self.spans) + 1
        span = FakeSpan(
            name=name,
            kind=kind,
            parent=parent,
            context=TraceContext(trace_id=f"trace-{index}", span_id=f"span-{index}"),
            attributes=dict(attributes or {}),
            fail_operations=self.fail_operations,
        )
        self.spans.append(span)
        return span


@dataclass(frozen=True)
class MetricCall:
    operation: str
    name: str
    value: int | float
    attributes: dict[str, ObservabilityAttributeValue]


class FakeMetricsRecorder:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[MetricCall] = []

    def increment(
        self,
        name: str,
        value: int | float = 1,
        *,
        attributes: ObservabilityAttributes | None = None,
    ) -> None:
        self._record("increment", name, value, attributes)

    def record(
        self,
        name: str,
        value: int | float,
        *,
        attributes: ObservabilityAttributes | None = None,
    ) -> None:
        self._record("record", name, value, attributes)

    def _record(
        self,
        operation: str,
        name: str,
        value: int | float,
        attributes: ObservabilityAttributes | None,
    ) -> None:
        if self.fail:
            raise RuntimeError("telemetry failure")
        self.calls.append(MetricCall(operation, name, value, dict(attributes or {})))
