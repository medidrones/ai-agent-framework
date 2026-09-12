"""Tests for fail-open manager and safe attribute policy."""

from atlas_agents import (
    ObservabilityManager,
    SafeAttributeBuilder,
    SpanKind,
    SpanStatus,
    TraceContext,
)
from tests.observability.fakes import FakeMetricsRecorder, FakeTracer


def test_manager_records_safe_spans_and_metrics_with_controlled_clock() -> None:
    values = iter((10.0, 12.5))
    tracer = FakeTracer()
    metrics = FakeMetricsRecorder()
    manager = ObservabilityManager(
        tracer=tracer,
        metrics=metrics,
        clock=lambda: next(values),
    )
    parent = TraceContext(trace_id="incoming", span_id="parent")
    started = manager.now()
    span = manager.start_span(
        "atlas.operation",
        kind=SpanKind.CLIENT,
        parent=parent,
        attributes={"atlas.execution.id": "execution", "secret": "hidden"},
    )
    span.set_attribute("atlas.outcome", "completed")
    span.set_attribute("secret", "hidden")
    span.add_event("completed", {"atlas.operation": "test", "secret": "hidden"})
    span.set_status(SpanStatus.OK)
    span.end()
    span.end()
    manager.increment(
        "atlas.operations",
        attributes={"outcome": "completed", "execution_id": "forbidden"},
    )
    manager.record("atlas.operation.duration", manager.elapsed_since(started))

    recorded = tracer.spans[0]
    assert recorded.parent == parent
    assert recorded.attributes == {
        "atlas.execution.id": "execution",
        "atlas.outcome": "completed",
    }
    assert recorded.events == [("completed", {"atlas.operation": "test"})]
    assert recorded.statuses == [(SpanStatus.OK, None)]
    assert recorded.end_count == 1
    assert metrics.calls[0].attributes == {"outcome": "completed"}
    assert metrics.calls[1].value == 2.5


def test_manager_absorbs_every_adapter_failure() -> None:
    tracer = FakeTracer(fail_operations=True)
    metrics = FakeMetricsRecorder(fail=True)
    manager = ObservabilityManager(tracer=tracer, metrics=metrics)
    span = manager.start_span("atlas.operation")

    assert span.context is not None
    span.set_attribute("atlas.outcome", "completed")
    span.add_event("event")
    span.record_exception(RuntimeError("explicit"))
    span.set_status(SpanStatus.ERROR)
    span.end()
    manager.increment("atlas.operation")
    manager.record("atlas.operation.duration", 1)
    assert span.ended


def test_manager_falls_back_when_span_creation_fails() -> None:
    manager = ObservabilityManager(tracer=FakeTracer(fail_start=True))
    span = manager.start_span("atlas.operation")

    assert span.context is None
    span.end()


def test_safe_attribute_builder_uses_explicit_whitelists_and_scalar_values() -> None:
    span = SafeAttributeBuilder.span(
        {
            "atlas.agent.id": "agent",
            "atlas.model.input_tokens": 10,
            "atlas.outcome": "completed",
            "metadata.secret": "secret",
            "atlas.tool.status": ["invalid"],
        }
    )
    metric = SafeAttributeBuilder.metric(
        {
            "mode": "run",
            "resumed": False,
            "execution_id": "high-cardinality",
            "trace_id": "high-cardinality",
            "user_id": "sensitive",
            "tool_call_id": "high-cardinality",
            "conversation_id": "sensitive",
        }
    )

    assert span == {
        "atlas.agent.id": "agent",
        "atlas.model.input_tokens": 10,
        "atlas.outcome": "completed",
    }
    assert metric == {"mode": "run", "resumed": False}
