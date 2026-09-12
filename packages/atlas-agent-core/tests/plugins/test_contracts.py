"""Tests for plugin manifests, contexts, contributions, and diagnostics."""

from dataclasses import FrozenInstanceError

import pytest
from pydantic import JsonValue, ValidationError

from atlas_agents import (
    EvaluatorContribution,
    KnowledgeRetrieverContribution,
    MemoryStoreContribution,
    ModelProviderContribution,
    ObservabilityContribution,
    PluginActivationError,
    PluginCapability,
    PluginCompatibilityChecker,
    PluginCompatibilityError,
    PluginContext,
    PluginContributionDescriptor,
    PluginErrorInfo,
    PluginManifest,
    PluginManifestError,
    PluginMetadata,
    ToolContribution,
)
from tests.plugins.fakes import (
    FakeEvaluator,
    FakeMemoryStore,
    FakeProvider,
    FakeRetriever,
    FakeTool,
    FakeTracer,
)


def metadata(**overrides: object) -> PluginMetadata:
    """Build valid metadata with selected overrides."""
    values: dict[str, object] = {
        "plugin_id": "acme.tools",
        "name": "Acme Tools",
        "version": "1.2.0",
    }
    values.update(overrides)
    return PluginMetadata.model_validate(values)


def manifest(**overrides: object) -> PluginManifest:
    """Build a valid manifest with selected overrides."""
    values: dict[str, object] = {
        "metadata": metadata(),
        "capabilities": (PluginCapability.TOOL,),
        "required_atlas_version": ">=0.1,<1",
    }
    values.update(overrides)
    return PluginManifest.model_validate(values)


@pytest.mark.parametrize("field", ["plugin_id", "name"])
def test_metadata_rejects_blank_identity(field: str) -> None:
    with pytest.raises(ValidationError):
        metadata(**{field: " "})


def test_metadata_validates_version_and_json_metadata() -> None:
    with pytest.raises(ValidationError):
        metadata(version="not-a-version")
    with pytest.raises(ValidationError):
        metadata(metadata={"unsafe": object()})


def test_metadata_normalizes_optional_text_and_is_frozen() -> None:
    value = metadata(description=" descrição ", author=" autor ", homepage=" site ")
    assert value.description == "descrição"
    assert value.author == "autor"
    assert value.homepage == "site"
    with pytest.raises(ValidationError):
        value.name = "Outro"


def test_manifest_validates_capabilities_dependencies_and_specifier() -> None:
    with pytest.raises(ValidationError):
        manifest(capabilities=())
    with pytest.raises(ValidationError):
        manifest(capabilities=(PluginCapability.TOOL, PluginCapability.TOOL))
    with pytest.raises(ValidationError):
        manifest(required_atlas_version="invalid")
    with pytest.raises(ValidationError):
        manifest(optional_dependencies=("sdk>=1", "sdk>=1"))
    with pytest.raises(ValidationError):
        manifest(optional_dependencies=(" ",))


def test_context_isolates_configuration_and_hides_it_from_repr() -> None:
    configuration: dict[str, JsonValue] = {
        "api_key": "SECRET",
        "nested": {"enabled": True},
    }
    context = PluginContext.create(atlas_version="0.1.0", configuration=configuration)
    configuration["api_key"] = "changed"
    assert context.configuration["api_key"] == "SECRET"
    assert "SECRET" not in repr(context)
    with pytest.raises(ValidationError):
        PluginContext.create(atlas_version="invalid")
    with pytest.raises(ValueError, match="JSON"):
        PluginContext.create(atlas_version="0.1.0", configuration={"x": object()})  # type: ignore[dict-item]


def test_descriptor_is_serializable_frozen_and_has_identity() -> None:
    descriptor = PluginContributionDescriptor(
        capability=PluginCapability.TOOL,
        identifier="weather",
        metadata={"stable": True},
    )
    assert descriptor.identity == (PluginCapability.TOOL, "weather")
    assert descriptor.model_dump(mode="json")["capability"] == "tool"
    with pytest.raises(ValidationError):
        descriptor.identifier = "other"
    with pytest.raises(ValidationError):
        PluginContributionDescriptor(capability=PluginCapability.TOOL, identifier=" ")


def test_compatibility_checker_accepts_and_rejects_versions() -> None:
    checker = PluginCompatibilityChecker()
    checker.validate(manifest(), "0.1.0")
    with pytest.raises(PluginCompatibilityError):
        checker.validate(manifest(required_atlas_version=">=2"), "0.1.0")
    broken = PluginManifest.model_construct(
        metadata=metadata(),
        capabilities=(PluginCapability.TOOL,),
        required_atlas_version="invalid",
        optional_dependencies=(),
    )
    with pytest.raises(PluginManifestError):
        checker.validate(broken, "0.1.0")


def test_typed_contributions_expose_stable_identities() -> None:
    provider = ModelProviderContribution(FakeProvider("acme"))
    tool = ToolContribution(FakeTool("weather"))
    memory = MemoryStoreContribution("memory", FakeMemoryStore())
    knowledge = KnowledgeRetrieverContribution("docs", FakeRetriever())
    evaluator = EvaluatorContribution(FakeEvaluator("quality"))
    observability = ObservabilityContribution("trace", tracer=FakeTracer())

    assert (provider.capability, provider.identifier) == (
        PluginCapability.MODEL_PROVIDER,
        "acme",
    )
    assert tool.identifier == "weather"
    assert memory.identifier == "memory"
    assert knowledge.identifier == "docs"
    assert evaluator.identifier == "quality"
    assert observability.identifier == "trace"

    with pytest.raises(FrozenInstanceError):
        memory.store_id = "other"  # type: ignore[misc]
    with pytest.raises(ValueError, match="store_id"):
        MemoryStoreContribution(" ", FakeMemoryStore())
    with pytest.raises(ValueError, match="retriever_id"):
        KnowledgeRetrieverContribution(" ", FakeRetriever())
    with pytest.raises(ValueError, match="observabilidade"):
        ObservabilityContribution("trace")


def test_error_info_is_safe_and_serializable() -> None:
    error = PluginActivationError("Falha segura.", plugin_id="acme.tools")
    info = PluginErrorInfo.from_error(error)
    assert info.code == "plugin_activation_failed"
    assert info.operation == "activate"
    assert info.error_type == "PluginActivationError"
    assert info.model_dump(mode="json")["message"] == "Falha segura."
