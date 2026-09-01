"""Tests for explicit provider registration and catalog discovery."""

import asyncio
from collections.abc import AsyncIterator

import pytest
from pydantic import ValidationError

from atlas_agents import (
    DuplicateModelProviderError,
    FinishReason,
    InvalidModelDescriptorError,
    ModelCapability,
    ModelCatalogEntry,
    ModelDescriptor,
    ModelExecutionContext,
    ModelProvider,
    ModelProviderError,
    ModelProviderNotRegisteredError,
    ModelProviderRegistry,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ModelStreamEventType,
    ModelUsage,
)


def _descriptor(
    provider: str,
    model: str,
    *,
    capabilities: frozenset[ModelCapability] | None = None,
    context_window: int | None = None,
    max_output_tokens: int | None = None,
) -> ModelDescriptor:
    return ModelDescriptor(
        provider=provider,
        model=model,
        capabilities=(
            capabilities
            if capabilities is not None
            else frozenset({ModelCapability.TEXT_GENERATION})
        ),
        context_window=context_window,
        max_output_tokens=max_output_tokens,
    )


class RegistryFakeProvider(ModelProvider):
    def __init__(
        self,
        provider_name: str,
        descriptors: tuple[ModelDescriptor, ...] = (),
        *,
        discovery_error: BaseException | None = None,
    ) -> None:
        self._provider_name = provider_name
        self._descriptors = descriptors
        self._discovery_error = discovery_error
        self.list_models_calls = 0
        self.generate_calls = 0
        self.stream_calls = 0

    @property
    def provider_name(self) -> str:
        return self._provider_name

    async def list_models(self) -> tuple[ModelDescriptor, ...]:
        self.list_models_calls += 1
        if self._discovery_error is not None:
            raise self._discovery_error
        return self._descriptors

    async def generate(
        self,
        request: ModelRequest,
        context: ModelExecutionContext,
    ) -> ModelResponse:
        self.generate_calls += 1
        return ModelResponse(
            response_id=context.request_id,
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


def test_registry_starts_empty_and_preserves_registration_order() -> None:
    registry = ModelProviderRegistry()
    provider_b = RegistryFakeProvider(" provider-b ")
    provider_a = RegistryFakeProvider("provider-a")

    assert registry.providers() == ()
    registry.register(provider_b)
    registry.register(provider_a)

    assert registry.providers() == (provider_b, provider_a)
    assert registry.get("provider-b") is provider_b
    assert registry.try_get(" provider-a ") is provider_a
    assert registry.try_get("missing") is None


def test_registry_rejects_duplicate_without_overwriting() -> None:
    registry = ModelProviderRegistry()
    first = RegistryFakeProvider("provider")
    registry.register(first)

    with pytest.raises(DuplicateModelProviderError) as captured:
        registry.register(RegistryFakeProvider(" provider "))

    assert captured.value.provider_name == "provider"
    assert registry.providers() == (first,)


def test_registry_rejects_empty_provider_name() -> None:
    registry = ModelProviderRegistry()

    with pytest.raises(ValueError, match="vazio"):
        registry.register(RegistryFakeProvider(" "))


def test_registry_get_and_unregister_report_unknown_provider() -> None:
    registry = ModelProviderRegistry()

    with pytest.raises(ModelProviderNotRegisteredError):
        registry.get("missing")
    with pytest.raises(ModelProviderNotRegisteredError):
        registry.unregister("missing")


def test_registry_unregister_returns_provider_and_snapshot_is_external() -> None:
    registry = ModelProviderRegistry()
    provider = RegistryFakeProvider("provider")
    registry.register(provider)
    snapshot = registry.providers()

    removed = registry.unregister("provider")

    assert removed is provider
    assert snapshot == (provider,)
    assert registry.providers() == ()


async def test_catalog_preserves_provider_and_model_order() -> None:
    registry = ModelProviderRegistry()
    provider_b = RegistryFakeProvider(
        "provider-b",
        (
            _descriptor("provider-b", "model-z"),
            _descriptor("provider-b", "model-a"),
        ),
    )
    provider_a = RegistryFakeProvider(
        "provider-a",
        (_descriptor("provider-a", "model-1"),),
    )
    registry.register(provider_b)
    registry.register(provider_a)

    catalog = await registry.build_catalog()

    assert [
        (
            entry.provider_name,
            entry.descriptor.model,
            entry.registration_order,
            entry.model_order,
        )
        for entry in catalog
    ] == [
        ("provider-b", "model-z", 0, 0),
        ("provider-b", "model-a", 0, 1),
        ("provider-a", "model-1", 1, 0),
    ]
    assert await registry.descriptors() == tuple(entry.descriptor for entry in catalog)


async def test_catalog_accepts_empty_provider_and_empty_registry() -> None:
    registry = ModelProviderRegistry()
    registry.register(RegistryFakeProvider("empty"))

    assert await registry.build_catalog() == ()
    registry.unregister("empty")
    assert await registry.build_catalog() == ()


async def test_catalog_rejects_descriptor_from_another_provider() -> None:
    registry = ModelProviderRegistry()
    registry.register(
        RegistryFakeProvider(
            "provider-a",
            (_descriptor("provider-b", "model"),),
        )
    )

    with pytest.raises(InvalidModelDescriptorError, match="não coincide"):
        await registry.build_catalog()


async def test_catalog_rejects_duplicate_model_in_same_provider() -> None:
    registry = ModelProviderRegistry()
    descriptor = _descriptor("provider", "duplicate")
    registry.register(RegistryFakeProvider("provider", (descriptor, descriptor)))

    with pytest.raises(InvalidModelDescriptorError, match="mais de uma vez"):
        await registry.build_catalog()


async def test_catalog_fails_fast_with_provider_error() -> None:
    error = ModelProviderError("Falha de descoberta.", provider="broken")
    registry = ModelProviderRegistry()
    registry.register(RegistryFakeProvider("broken", discovery_error=error))
    untouched = RegistryFakeProvider("untouched")
    registry.register(untouched)

    with pytest.raises(ModelProviderError) as captured:
        await registry.build_catalog()

    assert captured.value is error
    assert untouched.list_models_calls == 0


async def test_catalog_propagates_cancellation() -> None:
    registry = ModelProviderRegistry()
    registry.register(
        RegistryFakeProvider("cancelled", discovery_error=asyncio.CancelledError())
    )

    with pytest.raises(asyncio.CancelledError):
        await registry.build_catalog()


def test_catalog_entry_is_serializable_immutable_and_validated() -> None:
    descriptor = _descriptor("provider", "model")
    entry = ModelCatalogEntry(
        provider_name="provider",
        descriptor=descriptor,
        registration_order=0,
        model_order=0,
    )

    assert entry.model_dump(mode="json")["descriptor"]["model"] == "model"
    with pytest.raises(ValidationError):
        entry.model_order = 1
    with pytest.raises(ValidationError, match="coincidir"):
        ModelCatalogEntry(
            provider_name="other",
            descriptor=descriptor,
            registration_order=0,
            model_order=0,
        )
