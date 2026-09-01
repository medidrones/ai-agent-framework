"""Tests for model requirements, filtering, and deterministic selection."""

from collections.abc import AsyncIterator

import pytest
from pydantic import ValidationError

from atlas_agents import (
    DeterministicModelSelectionStrategy,
    FinishReason,
    ModelCandidate,
    ModelCapability,
    ModelCapabilityMismatchError,
    ModelDescriptor,
    ModelExecutionContext,
    ModelNotAvailableError,
    ModelProvider,
    ModelProviderNotRegisteredError,
    ModelProviderRegistry,
    ModelRequest,
    ModelResponse,
    ModelSelectionRequest,
    ModelSelectionResult,
    ModelSelectionStrategy,
    ModelStreamEvent,
    ModelStreamEventType,
    ModelUsage,
    NoMatchingModelError,
)


def _descriptor(
    provider: str,
    model: str,
    capabilities: frozenset[ModelCapability],
    *,
    context_window: int | None = None,
    max_output_tokens: int | None = None,
) -> ModelDescriptor:
    return ModelDescriptor(
        provider=provider,
        model=model,
        capabilities=capabilities,
        context_window=context_window,
        max_output_tokens=max_output_tokens,
    )


class SelectionFakeProvider(ModelProvider):
    def __init__(
        self,
        provider_name: str,
        descriptors: tuple[ModelDescriptor, ...],
    ) -> None:
        self._provider_name = provider_name
        self._descriptors = descriptors
        self.generate_calls = 0
        self.stream_calls = 0

    @property
    def provider_name(self) -> str:
        return self._provider_name

    async def list_models(self) -> tuple[ModelDescriptor, ...]:
        return self._descriptors

    async def generate(
        self,
        request: ModelRequest,
        context: ModelExecutionContext,
    ) -> ModelResponse:
        del context
        self.generate_calls += 1
        return ModelResponse(
            model=request.model,
            finish_reason=FinishReason.STOP,
            usage=ModelUsage(),
        )

    async def stream(
        self,
        request: ModelRequest,
        context: ModelExecutionContext,
    ) -> AsyncIterator[ModelStreamEvent]:
        self.stream_calls += 1
        yield ModelStreamEvent(
            type=ModelStreamEventType.RESPONSE_COMPLETED,
            sequence=1,
            response_id=context.request_id,
            data={"model": request.model},
        )


class LastCandidateStrategy(ModelSelectionStrategy):
    def select(
        self,
        candidates: tuple[ModelCandidate, ...],
        request: ModelSelectionRequest,
    ) -> ModelCandidate:
        del request
        return candidates[-1]


def _registry(*providers: SelectionFakeProvider) -> ModelProviderRegistry:
    registry = ModelProviderRegistry()
    for provider in providers:
        registry.register(provider)
    return registry


def test_selection_request_empty_is_valid_immutable_and_serializable() -> None:
    request = ModelSelectionRequest()

    assert request.required_capabilities == frozenset()
    assert request.preferred_capabilities == frozenset()
    assert request.model_dump(mode="json")["provider"] is None
    with pytest.raises(ValidationError):
        request.provider = "other"


def test_selection_request_normalizes_provider_and_isolates_metadata() -> None:
    metadata: dict[str, object] = {"trace": "opaque"}
    request = ModelSelectionRequest(
        provider=" provider ",
        model="model",
        required_capabilities=frozenset({ModelCapability.TEXT_GENERATION}),
        preferred_capabilities=frozenset({ModelCapability.STREAMING}),
        minimum_context_window=100,
        minimum_max_output_tokens=10,
        metadata=metadata,
    )
    metadata["trace"] = "changed"

    assert request.provider == "provider"
    assert request.metadata == {"trace": "opaque"}
    assert isinstance(request.required_capabilities, frozenset)


@pytest.mark.parametrize("field", ["provider", "model"])
def test_selection_request_rejects_empty_optional_identifiers(field: str) -> None:
    with pytest.raises(ValidationError):
        ModelSelectionRequest.model_validate({field: " "})


@pytest.mark.parametrize(
    "field",
    ["minimum_context_window", "minimum_max_output_tokens"],
)
@pytest.mark.parametrize("value", [0, -1])
def test_selection_request_rejects_non_positive_constraints(
    field: str,
    value: int,
) -> None:
    with pytest.raises(ValidationError):
        ModelSelectionRequest.model_validate({field: value})


async def test_find_candidates_filters_provider_and_model() -> None:
    text = frozenset({ModelCapability.TEXT_GENERATION})
    registry = _registry(
        SelectionFakeProvider(
            "provider-a",
            (
                _descriptor("provider-a", "common", text),
                _descriptor("provider-a", "other", text),
            ),
        ),
        SelectionFakeProvider(
            "provider-b",
            (_descriptor("provider-b", "common", text),),
        ),
    )

    provider_candidates = await registry.find_candidates(
        ModelSelectionRequest(provider="provider-b")
    )
    model_candidates = await registry.find_candidates(
        ModelSelectionRequest(model="common")
    )

    assert [candidate.provider_name for candidate in provider_candidates] == [
        "provider-b"
    ]
    assert [candidate.provider_name for candidate in model_candidates] == [
        "provider-a",
        "provider-b",
    ]


async def test_required_capabilities_accept_exact_and_superset_only() -> None:
    text = frozenset({ModelCapability.TEXT_GENERATION})
    text_tools = frozenset(
        {ModelCapability.TEXT_GENERATION, ModelCapability.TOOL_CALLING}
    )
    registry = _registry(
        SelectionFakeProvider(
            "provider",
            (
                _descriptor("provider", "missing", text),
                _descriptor("provider", "exact", text_tools),
                _descriptor(
                    "provider",
                    "superset",
                    text_tools | {ModelCapability.STREAMING},
                ),
            ),
        )
    )

    all_candidates = await registry.find_candidates(ModelSelectionRequest())
    filtered = await registry.find_candidates(
        ModelSelectionRequest(required_capabilities=text_tools)
    )

    assert len(all_candidates) == 3
    assert [candidate.descriptor.model for candidate in filtered] == [
        "exact",
        "superset",
    ]


@pytest.mark.parametrize(
    ("context_window", "minimum", "expected"),
    [(128_000, 100_000, True), (64_000, 100_000, False), (None, 100_000, False)],
)
async def test_context_window_constraint(
    context_window: int | None,
    minimum: int,
    expected: bool,
) -> None:
    registry = _registry(
        SelectionFakeProvider(
            "provider",
            (
                _descriptor(
                    "provider",
                    "model",
                    frozenset(),
                    context_window=context_window,
                ),
            ),
        )
    )
    request = ModelSelectionRequest(minimum_context_window=minimum)

    if expected:
        assert await registry.find_candidates(request)
    else:
        with pytest.raises(NoMatchingModelError):
            await registry.find_candidates(request)


@pytest.mark.parametrize(
    ("max_output_tokens", "minimum", "expected"),
    [(8_000, 8_000, True), (4_000, 8_000, False), (None, 8_000, False)],
)
async def test_max_output_tokens_constraint(
    max_output_tokens: int | None,
    minimum: int,
    expected: bool,
) -> None:
    registry = _registry(
        SelectionFakeProvider(
            "provider",
            (
                _descriptor(
                    "provider",
                    "model",
                    frozenset(),
                    max_output_tokens=max_output_tokens,
                ),
            ),
        )
    )
    request = ModelSelectionRequest(minimum_max_output_tokens=minimum)

    if expected:
        assert await registry.find_candidates(request)
    else:
        with pytest.raises(NoMatchingModelError):
            await registry.find_candidates(request)


async def test_unknown_limits_are_valid_without_numeric_requirement() -> None:
    registry = _registry(
        SelectionFakeProvider(
            "provider",
            (_descriptor("provider", "model", frozenset()),),
        )
    )

    candidates = await registry.find_candidates(ModelSelectionRequest())

    assert len(candidates) == 1


async def test_preferred_capability_count_controls_ranking_without_elimination() -> (
    None
):
    required = frozenset({ModelCapability.TEXT_GENERATION})
    registry = _registry(
        SelectionFakeProvider(
            "provider",
            (
                _descriptor("provider", "zero", required),
                _descriptor(
                    "provider",
                    "one",
                    required | {ModelCapability.STREAMING},
                ),
                _descriptor(
                    "provider",
                    "two",
                    required
                    | {ModelCapability.STREAMING, ModelCapability.TOOL_CALLING},
                ),
            ),
        )
    )
    request = ModelSelectionRequest(
        required_capabilities=required,
        preferred_capabilities=frozenset(
            {
                ModelCapability.TEXT_GENERATION,
                ModelCapability.STREAMING,
                ModelCapability.TOOL_CALLING,
            }
        ),
    )

    candidates = await registry.find_candidates(request)
    result = await registry.select(request)

    assert [item.preferred_capability_matches for item in candidates] == [0, 1, 2]
    assert result.model == "two"
    assert result.matched_required_capabilities == required
    assert result.matched_preferred_capabilities == frozenset(
        {ModelCapability.STREAMING, ModelCapability.TOOL_CALLING}
    )
    assert result.candidate_count == 3


async def test_registration_order_is_the_provider_tie_breaker() -> None:
    capabilities = frozenset({ModelCapability.TEXT_GENERATION})
    provider_a = SelectionFakeProvider(
        "provider-a",
        (_descriptor("provider-a", "model", capabilities),),
    )
    provider_b = SelectionFakeProvider(
        "provider-b",
        (_descriptor("provider-b", "model", capabilities),),
    )

    first = await _registry(provider_a, provider_b).select(ModelSelectionRequest())
    second = await _registry(provider_b, provider_a).select(ModelSelectionRequest())

    assert first.provider_name == "provider-a"
    assert second.provider_name == "provider-b"


async def test_provider_model_order_precedes_alphabetical_order() -> None:
    provider = SelectionFakeProvider(
        "provider",
        (
            _descriptor("provider", "model-z", frozenset()),
            _descriptor("provider", "model-a", frozenset()),
        ),
    )

    results = [
        await _registry(provider).select(ModelSelectionRequest()) for _ in range(20)
    ]

    assert {result.model for result in results} == {"model-z"}


async def test_registry_accepts_an_explicit_selection_strategy() -> None:
    provider = SelectionFakeProvider(
        "provider",
        (
            _descriptor("provider", "first", frozenset()),
            _descriptor("provider", "last", frozenset()),
        ),
    )
    registry = ModelProviderRegistry(selection_strategy=LastCandidateStrategy())
    registry.register(provider)

    result = await registry.select(ModelSelectionRequest())

    assert result.model == "last"


async def test_explicit_provider_model_never_falls_back_on_capability_mismatch() -> (
    None
):
    provider = SelectionFakeProvider(
        "provider",
        (
            _descriptor(
                "provider",
                "explicit",
                frozenset({ModelCapability.TEXT_GENERATION}),
            ),
            _descriptor(
                "provider",
                "fallback",
                frozenset(
                    {ModelCapability.TEXT_GENERATION, ModelCapability.TOOL_CALLING}
                ),
            ),
        ),
    )
    request = ModelSelectionRequest(
        provider="provider",
        model="explicit",
        required_capabilities=frozenset(
            {ModelCapability.TEXT_GENERATION, ModelCapability.TOOL_CALLING}
        ),
    )

    with pytest.raises(ModelCapabilityMismatchError) as captured:
        await _registry(provider).select(request)

    assert captured.value.missing_capabilities == frozenset({"tool_calling"})


async def test_explicit_unknown_provider_and_model_have_specific_errors() -> None:
    provider = SelectionFakeProvider(
        "provider",
        (_descriptor("provider", "available", frozenset()),),
    )
    registry = _registry(provider)

    with pytest.raises(ModelProviderNotRegisteredError):
        await registry.select(ModelSelectionRequest(provider="missing"))
    with pytest.raises(ModelNotAvailableError):
        await registry.select(
            ModelSelectionRequest(provider="provider", model="missing")
        )
    with pytest.raises(ModelNotAvailableError):
        await registry.select(ModelSelectionRequest(model="missing"))


async def test_valid_explicit_provider_and_model_select_exact_pair() -> None:
    provider = SelectionFakeProvider(
        "provider",
        (
            _descriptor("provider", "requested", frozenset()),
            _descriptor("provider", "other", frozenset()),
        ),
    )

    result = await _registry(provider).select(
        ModelSelectionRequest(provider="provider", model="requested")
    )

    assert result.provider_name == "provider"
    assert result.model == "requested"


async def test_explicit_pair_never_falls_back_on_numeric_constraint() -> None:
    provider = SelectionFakeProvider(
        "provider",
        (
            _descriptor(
                "provider",
                "requested",
                frozenset(),
                context_window=1_000,
            ),
            _descriptor(
                "provider",
                "other",
                frozenset(),
                context_window=100_000,
            ),
        ),
    )

    with pytest.raises(NoMatchingModelError):
        await _registry(provider).select(
            ModelSelectionRequest(
                provider="provider",
                model="requested",
                minimum_context_window=100_000,
            )
        )


async def test_empty_registry_and_unsatisfied_requirements_report_no_match() -> None:
    with pytest.raises(NoMatchingModelError):
        await ModelProviderRegistry().select(ModelSelectionRequest())

    provider = SelectionFakeProvider(
        "provider",
        (_descriptor("provider", "model", frozenset()),),
    )
    with pytest.raises(NoMatchingModelError) as captured:
        await _registry(provider).select(
            ModelSelectionRequest(
                required_capabilities=frozenset({ModelCapability.TEXT_GENERATION}),
                metadata={"secret": "não deve aparecer no erro"},
            )
        )

    assert captured.value.required_capabilities == frozenset({"text_generation"})
    assert "secret" not in vars(captured.value)


async def test_selection_never_generates_or_streams_model_output() -> None:
    provider = SelectionFakeProvider(
        "provider",
        (_descriptor("provider", "model", frozenset()),),
    )

    await _registry(provider).select(ModelSelectionRequest())

    assert provider.generate_calls == 0
    assert provider.stream_calls == 0


def test_deterministic_strategy_handles_one_preferred_tie_and_zero_candidates() -> None:
    descriptor_a = _descriptor("provider-a", "z", frozenset())
    descriptor_b = _descriptor("provider-b", "a", frozenset())
    candidates = (
        ModelCandidate(
            provider_name="provider-a",
            descriptor=descriptor_a,
            registration_order=0,
            model_order=0,
            preferred_capability_matches=0,
        ),
        ModelCandidate(
            provider_name="provider-b",
            descriptor=descriptor_b,
            registration_order=1,
            model_order=0,
            preferred_capability_matches=1,
        ),
    )
    strategy = DeterministicModelSelectionStrategy()

    assert strategy.select((candidates[0],), ModelSelectionRequest()) is candidates[0]
    assert strategy.select(candidates, ModelSelectionRequest()) is candidates[1]
    tied = candidates[1].model_copy(update={"preferred_capability_matches": 0})
    assert (
        strategy.select((candidates[0], tied), ModelSelectionRequest()) is candidates[0]
    )
    with pytest.raises(NoMatchingModelError):
        strategy.select((), ModelSelectionRequest())


def test_candidate_and_selection_result_are_immutable_and_serializable() -> None:
    descriptor = _descriptor(
        "provider",
        "model",
        frozenset({ModelCapability.TEXT_GENERATION}),
    )
    candidate = ModelCandidate(
        provider_name="provider",
        descriptor=descriptor,
        registration_order=0,
        model_order=0,
        preferred_capability_matches=0,
    )
    result = ModelSelectionResult(
        provider_name="provider",
        model="model",
        descriptor=descriptor,
        matched_required_capabilities=frozenset({ModelCapability.TEXT_GENERATION}),
        matched_preferred_capabilities=frozenset(),
        preferred_capability_matches=0,
        candidate_count=1,
    )

    assert candidate.model_dump(mode="json")["descriptor"]["model"] == "model"
    assert result.model_dump(mode="json")["candidate_count"] == 1
    with pytest.raises(ValidationError):
        candidate.model_order = 1
    with pytest.raises(ValidationError):
        result.model = "other"


def test_candidate_and_result_reject_inconsistent_descriptor_facts() -> None:
    descriptor = _descriptor(
        "provider",
        "model",
        frozenset({ModelCapability.TEXT_GENERATION}),
    )
    with pytest.raises(ValidationError, match="candidato"):
        ModelCandidate(
            provider_name="other",
            descriptor=descriptor,
            registration_order=0,
            model_order=0,
            preferred_capability_matches=0,
        )

    base: dict[str, object] = {
        "provider_name": "provider",
        "model": "model",
        "descriptor": descriptor,
        "matched_required_capabilities": frozenset(),
        "matched_preferred_capabilities": frozenset(),
        "preferred_capability_matches": 0,
        "candidate_count": 1,
    }
    invalid_updates = (
        {"provider_name": "other"},
        {"model": "other"},
        {"matched_required_capabilities": {ModelCapability.TOOL_CALLING}},
        {"matched_preferred_capabilities": {ModelCapability.STREAMING}},
        {"preferred_capability_matches": 1},
    )
    for update in invalid_updates:
        with pytest.raises(ValidationError):
            ModelSelectionResult.model_validate(base | update)
