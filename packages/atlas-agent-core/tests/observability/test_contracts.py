"""Tests for observability contracts and no-op implementations."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from atlas_agents import (
    AgentContext,
    NoOpMetricsRecorder,
    NoOpSpan,
    NoOpTracer,
    SpanKind,
    SpanStatus,
    TraceContext,
)


def test_trace_context_is_opaque_frozen_and_serializable() -> None:
    trace = TraceContext(
        trace_id="vendor-specific-trace",
        span_id="parent",
        trace_flags="sampled",
        trace_state="vendor=value",
    )

    assert trace.model_dump(mode="json")["trace_id"] == "vendor-specific-trace"
    assert (
        AgentContext(execution_id="execution", trace_context=trace).trace_context
        == trace
    )
    with pytest.raises(ValidationError):
        trace.trace_id = "changed"


@pytest.mark.parametrize(
    ("field", "value"),
    [("trace_id", " "), ("span_id", ""), ("trace_flags", " ")],
)
def test_trace_context_rejects_blank_values(field: str, value: str) -> None:
    data = {"trace_id": "trace", "span_id": "span", field: value}
    with pytest.raises(ValidationError):
        TraceContext.model_validate(data)


def test_span_enums_have_stable_values() -> None:
    assert [kind.value for kind in SpanKind] == ["internal", "client"]
    assert [status.value for status in SpanStatus] == ["unset", "ok", "error"]


def test_noop_implementations_accept_every_operation() -> None:
    span = NoOpSpan()
    span.set_attribute("atlas.outcome", "completed")
    span.add_event("event", {"atlas.operation": "test"})
    span.record_exception(RuntimeError("explicit"))
    span.set_status(SpanStatus.OK)
    span.end()
    span.end()
    tracer_span = NoOpTracer().start_span(
        "atlas.test",
        kind=SpanKind.CLIENT,
        parent=TraceContext(trace_id="trace", span_id="span"),
    )
    metrics = NoOpMetricsRecorder()
    metrics.increment("atlas.test", attributes={"outcome": "completed"})
    metrics.record("atlas.test.duration", 0.1)

    assert span.context is None
    assert tracer_span.context is None


def test_trace_context_does_not_require_datetime_or_w3c_format() -> None:
    trace = TraceContext(trace_id="opaque", span_id="also-opaque")
    dumped = trace.model_dump(mode="json")

    assert datetime.now(UTC).tzinfo is not None
    assert dumped == {
        "trace_id": "opaque",
        "span_id": "also-opaque",
        "trace_flags": None,
        "trace_state": None,
    }
