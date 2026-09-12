"""Public provider-neutral observability contracts."""

from atlas_agents.observability.attributes import (
    SafeAttributeBuilder,
    safe_metric_attributes,
    safe_span_attributes,
)
from atlas_agents.observability.context import TraceContext
from atlas_agents.observability.errors import ObservabilityError
from atlas_agents.observability.manager import ObservabilityManager, SafeSpan
from atlas_agents.observability.metrics import MetricsRecorder
from atlas_agents.observability.noop import (
    NoOpMetricsRecorder,
    NoOpSpan,
    NoOpTracer,
)
from atlas_agents.observability.span import (
    ObservabilityAttributes,
    ObservabilityAttributeValue,
    Span,
    SpanKind,
    SpanStatus,
)
from atlas_agents.observability.tracing import Tracer

__all__ = [
    "MetricsRecorder",
    "NoOpMetricsRecorder",
    "NoOpSpan",
    "NoOpTracer",
    "ObservabilityAttributeValue",
    "ObservabilityAttributes",
    "ObservabilityError",
    "ObservabilityManager",
    "SafeAttributeBuilder",
    "SafeSpan",
    "Span",
    "SpanKind",
    "SpanStatus",
    "TraceContext",
    "Tracer",
    "safe_metric_attributes",
    "safe_span_attributes",
]
