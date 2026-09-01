"""Selection strategies applied after mandatory model filtering."""

from abc import ABC, abstractmethod

from atlas_agents.exceptions import NoMatchingModelError
from atlas_agents.models.selection import ModelCandidate, ModelSelectionRequest


def _no_matching_error(request: ModelSelectionRequest) -> NoMatchingModelError:
    return NoMatchingModelError(
        requested_provider=request.provider,
        requested_model=request.model,
        required_capabilities=frozenset(
            capability.value for capability in request.required_capabilities
        ),
        minimum_context_window=request.minimum_context_window,
        minimum_max_output_tokens=request.minimum_max_output_tokens,
    )


class ModelSelectionStrategy(ABC):
    """Choose one candidate after registry filtering has completed."""

    @abstractmethod
    def select(
        self,
        candidates: tuple[ModelCandidate, ...],
        request: ModelSelectionRequest,
    ) -> ModelCandidate:
        """Return one candidate or raise a model selection error."""


class DeterministicModelSelectionStrategy(ModelSelectionStrategy):
    """Rank candidates by preferences and stable catalog ordering."""

    def select(
        self,
        candidates: tuple[ModelCandidate, ...],
        request: ModelSelectionRequest,
    ) -> ModelCandidate:
        """Choose the highest preference count with deterministic tie-breakers."""
        if not candidates:
            raise _no_matching_error(request)
        return min(
            candidates,
            key=lambda candidate: (
                -candidate.preferred_capability_matches,
                candidate.registration_order,
                candidate.model_order,
                candidate.descriptor.model,
            ),
        )
