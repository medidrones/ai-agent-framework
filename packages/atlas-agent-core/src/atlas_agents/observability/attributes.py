"""Explicit privacy and cardinality policy for telemetry attributes."""

from collections.abc import Mapping

from atlas_agents.observability.span import (
    ObservabilityAttributes,
    ObservabilityAttributeValue,
)

_SPAN_ATTRIBUTE_NAMES = frozenset(
    {
        "atlas.agent.id",
        "atlas.approval.decision",
        "atlas.checkpoint.version",
        "atlas.error.code",
        "atlas.error.type",
        "atlas.execution.id",
        "atlas.execution.mode",
        "atlas.execution.resumed",
        "atlas.execution.status",
        "atlas.execution.tool_call_count",
        "atlas.execution.turn_count",
        "atlas.guardrail.count",
        "atlas.guardrail.decision",
        "atlas.guardrail.stage",
        "atlas.knowledge.result_count",
        "atlas.knowledge.selected_count",
        "atlas.knowledge.source_count",
        "atlas.memory.result_count",
        "atlas.memory.type",
        "atlas.model.estimated_cost",
        "atlas.model.finish_reason",
        "atlas.model.id",
        "atlas.model.input_tokens",
        "atlas.model.output_tokens",
        "atlas.model.provider",
        "atlas.model.request_id",
        "atlas.model.required_capability_count",
        "atlas.model.stream.event_count",
        "atlas.model.total_tokens",
        "atlas.model.turn",
        "atlas.operation",
        "atlas.outcome",
        "atlas.tool.call_id",
        "atlas.tool.idempotency",
        "atlas.tool.name",
        "atlas.tool.status",
    }
)

_METRIC_ATTRIBUTE_NAMES = frozenset(
    {
        "decision",
        "memory_type",
        "mode",
        "model",
        "operation",
        "outcome",
        "provider",
        "resumed",
        "stage",
        "status",
        "tool_name",
    }
)


class SafeAttributeBuilder:
    """Allow only reviewed scalar attributes for spans and metrics."""

    @staticmethod
    def span(
        attributes: Mapping[str, object] | None,
    ) -> dict[str, ObservabilityAttributeValue]:
        """Return whitelisted, scalar span attributes."""
        return _filter_attributes(attributes, _SPAN_ATTRIBUTE_NAMES)

    @staticmethod
    def metric(
        attributes: Mapping[str, object] | None,
    ) -> dict[str, ObservabilityAttributeValue]:
        """Return whitelisted, low-cardinality metric attributes."""
        return _filter_attributes(attributes, _METRIC_ATTRIBUTE_NAMES)


def _filter_attributes(
    attributes: Mapping[str, object] | None,
    allowed_names: frozenset[str],
) -> dict[str, ObservabilityAttributeValue]:
    if attributes is None:
        return {}
    return {
        name: value
        for name, value in attributes.items()
        if name in allowed_names and isinstance(value, (str, bool, int, float))
    }


def safe_span_attributes(
    attributes: Mapping[str, object] | None,
) -> ObservabilityAttributes:
    """Build safe span attributes with the default policy."""
    return SafeAttributeBuilder.span(attributes)


def safe_metric_attributes(
    attributes: Mapping[str, object] | None,
) -> ObservabilityAttributes:
    """Build safe low-cardinality metric attributes with the default policy."""
    return SafeAttributeBuilder.metric(attributes)
