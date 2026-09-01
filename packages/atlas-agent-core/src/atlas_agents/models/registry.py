"""Explicit registry and deterministic selection of model providers."""

from atlas_agents._models import _trimmed_non_empty
from atlas_agents.exceptions import (
    DuplicateModelProviderError,
    InvalidModelDescriptorError,
    ModelCapabilityMismatchError,
    ModelNotAvailableError,
    ModelProviderNotRegisteredError,
    NoMatchingModelError,
)
from atlas_agents.models.capabilities import ModelDescriptor
from atlas_agents.models.catalog import ModelCatalogEntry
from atlas_agents.models.provider import ModelProvider
from atlas_agents.models.resolution import (
    matched_preferred_capabilities,
    matches_numeric_constraints,
    supports_required_capabilities,
)
from atlas_agents.models.selection import (
    ModelCandidate,
    ModelSelectionRequest,
    ModelSelectionResult,
)
from atlas_agents.models.strategy import (
    DeterministicModelSelectionStrategy,
    ModelSelectionStrategy,
)


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


class ModelProviderRegistry:
    """Store model providers locally and resolve descriptors deterministically."""

    def __init__(
        self,
        *,
        selection_strategy: ModelSelectionStrategy | None = None,
    ) -> None:
        """Initialize isolated registry state and an explicit selection strategy."""
        self._providers: dict[str, ModelProvider] = {}
        self._selection_strategy = (
            selection_strategy
            if selection_strategy is not None
            else DeterministicModelSelectionStrategy()
        )

    def register(self, provider: ModelProvider) -> None:
        """Register one provider without silently replacing an existing one."""
        provider_name = _trimmed_non_empty(provider.provider_name)
        if provider_name in self._providers:
            raise DuplicateModelProviderError(provider_name)
        self._providers[provider_name] = provider

    def unregister(self, provider_name: str) -> ModelProvider:
        """Remove and return a provider or report an unknown identifier."""
        normalized_name = _trimmed_non_empty(provider_name)
        try:
            return self._providers.pop(normalized_name)
        except KeyError as exc:
            raise ModelProviderNotRegisteredError(normalized_name) from exc

    def get(self, provider_name: str) -> ModelProvider:
        """Return a provider or report an unknown identifier."""
        normalized_name = _trimmed_non_empty(provider_name)
        try:
            return self._providers[normalized_name]
        except KeyError as exc:
            raise ModelProviderNotRegisteredError(normalized_name) from exc

    def try_get(self, provider_name: str) -> ModelProvider | None:
        """Return a provider when registered, otherwise return none."""
        return self._providers.get(_trimmed_non_empty(provider_name))

    def providers(self) -> tuple[ModelProvider, ...]:
        """Return an immutable snapshot preserving registration order."""
        return tuple(self._providers.values())

    async def descriptors(self) -> tuple[ModelDescriptor, ...]:
        """Discover and return descriptor snapshots in catalog order."""
        return tuple(entry.descriptor for entry in await self.build_catalog())

    async def build_catalog(self) -> tuple[ModelCatalogEntry, ...]:
        """Discover models sequentially and fail fast on invalid providers."""
        entries: list[ModelCatalogEntry] = []
        for registration_order, (provider_name, provider) in enumerate(
            self._providers.items()
        ):
            descriptors = await provider.list_models()
            seen_models: set[str] = set()
            for model_order, descriptor in enumerate(descriptors):
                if descriptor.provider != provider_name:
                    raise InvalidModelDescriptorError(
                        provider_name,
                        descriptor.model,
                        "o provider informado não coincide com o provider registrado",
                    )
                if descriptor.model in seen_models:
                    raise InvalidModelDescriptorError(
                        provider_name,
                        descriptor.model,
                        "o modelo foi informado mais de uma vez pelo mesmo provider",
                    )
                seen_models.add(descriptor.model)
                entries.append(
                    ModelCatalogEntry(
                        provider_name=provider_name,
                        descriptor=descriptor,
                        registration_order=registration_order,
                        model_order=model_order,
                    )
                )
        return tuple(entries)

    async def find_candidates(
        self,
        request: ModelSelectionRequest,
    ) -> tuple[ModelCandidate, ...]:
        """Filter catalog entries while preserving their natural stable order."""
        if request.provider is not None:
            self.get(request.provider)

        catalog = await self.build_catalog()
        explicitly_named = tuple(
            entry
            for entry in catalog
            if (request.provider is None or entry.provider_name == request.provider)
            and (request.model is None or entry.descriptor.model == request.model)
        )
        if request.model is not None and not explicitly_named:
            raise ModelNotAvailableError(
                provider_name=request.provider,
                model=request.model,
            )

        if request.provider is not None and request.model is not None:
            explicit_descriptor = explicitly_named[0].descriptor
            missing = request.required_capabilities - explicit_descriptor.capabilities
            if missing:
                raise ModelCapabilityMismatchError(
                    provider_name=request.provider,
                    model=request.model,
                    missing_capabilities=frozenset(item.value for item in missing),
                )

        candidates: list[ModelCandidate] = []
        for entry in explicitly_named:
            if not supports_required_capabilities(entry.descriptor, request):
                continue
            if not matches_numeric_constraints(entry.descriptor, request):
                continue
            preferred = matched_preferred_capabilities(entry.descriptor, request)
            candidates.append(
                ModelCandidate(
                    provider_name=entry.provider_name,
                    descriptor=entry.descriptor,
                    registration_order=entry.registration_order,
                    model_order=entry.model_order,
                    preferred_capability_matches=len(preferred),
                )
            )

        if not candidates:
            raise _no_matching_error(request)
        return tuple(candidates)

    async def select(
        self,
        request: ModelSelectionRequest,
    ) -> ModelSelectionResult:
        """Select one descriptor without generating or streaming model output."""
        candidates = await self.find_candidates(request)
        selected = self._selection_strategy.select(candidates, request)
        matched_preferred = matched_preferred_capabilities(
            selected.descriptor,
            request,
        )
        return ModelSelectionResult(
            provider_name=selected.provider_name,
            model=selected.descriptor.model,
            descriptor=selected.descriptor,
            matched_required_capabilities=request.required_capabilities,
            matched_preferred_capabilities=matched_preferred,
            preferred_capability_matches=len(matched_preferred),
            candidate_count=len(candidates),
        )
