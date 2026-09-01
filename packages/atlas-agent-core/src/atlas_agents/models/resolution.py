"""Pure filtering and capability resolution for model descriptors."""

from atlas_agents.models.capabilities import ModelCapability, ModelDescriptor
from atlas_agents.models.selection import ModelSelectionRequest


def supports_required_capabilities(
    descriptor: ModelDescriptor,
    request: ModelSelectionRequest,
) -> bool:
    """Return whether all mandatory capabilities are present."""
    return request.required_capabilities <= descriptor.capabilities


def matches_numeric_constraints(
    descriptor: ModelDescriptor,
    request: ModelSelectionRequest,
) -> bool:
    """Return whether known descriptor limits satisfy explicit minimums."""
    if request.minimum_context_window is not None and (
        descriptor.context_window is None
        or descriptor.context_window < request.minimum_context_window
    ):
        return False
    return not (
        request.minimum_max_output_tokens is not None
        and (
            descriptor.max_output_tokens is None
            or descriptor.max_output_tokens < request.minimum_max_output_tokens
        )
    )


def matched_preferred_capabilities(
    descriptor: ModelDescriptor,
    request: ModelSelectionRequest,
) -> frozenset[ModelCapability]:
    """Return preferred matches without double-counting required capabilities."""
    effective_preferred = request.preferred_capabilities - request.required_capabilities
    return effective_preferred & descriptor.capabilities
