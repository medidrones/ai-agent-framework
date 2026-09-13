from __future__ import annotations

import pytest
from config_test_support import (
    FakeAdapterFactory,
    FakeGuardrailFactory,
    FakeKnowledgeFactory,
    FakeMCPFactory,
    FakeMemoryFactory,
    FakeObservabilityFactory,
    FakeProviderFactory,
    FakeToolFactory,
)

from atlas_agents.config import (
    ComponentFactoryNotFoundError,
    ConfigurationFactoryRegistry,
    ConfigurationValidator,
    ConfigValidationError,
    DuplicateFactoryError,
    load_yaml,
)


def validate(source: str) -> tuple[str, ...]:
    return tuple(
        issue.code
        for issue in ConfigurationValidator().validate(load_yaml(source)).issues
    )


@pytest.mark.parametrize(
    ("section", "body", "expected"),
    [
        (
            "provider",
            "model:\n      provider: missing",
            "invalid_provider_reference",
        ),
        ("tool", "tools: [missing]", "invalid_tool_reference"),
        (
            "guardrail",
            "guardrails:\n      input: [missing]",
            "invalid_guardrail_reference",
        ),
        (
            "knowledge",
            "knowledge:\n      sources: [missing]",
            "invalid_knowledge_reference",
        ),
    ],
)
def test_missing_agent_references_are_collected(
    section: str, body: str, expected: str
) -> None:
    del section
    source = f"""
schema_version: 1
agents:
  assistant:
    name: Assistente
    instructions: Ajude.
    {body}
"""
    assert expected in validate(source)


@pytest.mark.parametrize("section", ["providers", "tools", "guardrails"])
def test_disabled_component_reference_is_rejected(section: str) -> None:
    agent_field = {
        "providers": "model: {provider: target}",
        "tools": "tools: [target]",
        "guardrails": "guardrails: {input: [target]}",
    }[section]
    source = f"""
schema_version: 1
{section}:
  target:
    type: fake
    enabled: false
agents:
  assistant:
    name: Assistente
    instructions: Ajude.
    {agent_field}
"""
    assert any(code.startswith("invalid_") for code in validate(source))


def test_enabled_references_validate_without_side_effects() -> None:
    source = """
schema_version: 1
providers:
  fake: {type: fake_provider}
tools:
  lookup: {type: fake_tool}
knowledge:
  company:
    type: fake_knowledge
    source_ids: [docs]
guardrails:
  safe: {type: fake_guardrail}
agents:
  assistant:
    name: Assistente
    instructions: Ajude.
    model: {provider: fake}
    tools: [lookup]
    knowledge: {sources: [docs]}
    guardrails: {input: [safe]}
"""
    result = ConfigurationValidator().validate(load_yaml(source))
    assert result.valid is True
    assert result.errors == ()


def test_plugin_activation_must_exactly_match_enabled_plugins() -> None:
    missing_order = load_yaml("schema_version: 1\nplugins:\n  acme: {enabled: true}\n")
    extra_order = load_yaml("schema_version: 1\nplugin_activation: [acme]\n")
    assert "invalid_plugin_activation" in tuple(
        issue.code for issue in ConfigurationValidator().validate(missing_order).issues
    )
    assert "invalid_plugin_activation" in tuple(
        issue.code for issue in ConfigurationValidator().validate(extra_order).issues
    )
    with pytest.raises(ConfigValidationError):
        load_yaml(
            "schema_version: 1\nplugins:\n  acme: {}\nplugin_activation: [acme, acme]\n"
        )


@pytest.mark.parametrize("section", ["memory", "knowledge", "observability"])
def test_runtime_singleton_sections_reject_multiple_enabled(section: str) -> None:
    source = f"""
schema_version: 1
{section}:
  one: {{type: fake}}
  two: {{type: fake}}
"""
    assert "multiple_runtime_subsystems" in validate(source)


def test_factory_registry_has_typed_registration_and_lookup() -> None:
    registry = ConfigurationFactoryRegistry()
    provider = FakeProviderFactory()
    tool = FakeToolFactory()
    memory = FakeMemoryFactory()
    knowledge = FakeKnowledgeFactory()
    guardrail = FakeGuardrailFactory()
    observability = FakeObservabilityFactory()
    mcp = FakeMCPFactory()
    adapter = FakeAdapterFactory()
    registry.register_provider_factory(provider)
    registry.register_tool_factory(tool)
    registry.register_memory_factory(memory)
    registry.register_knowledge_factory(knowledge)
    registry.register_guardrail_factory(guardrail)
    registry.register_observability_factory(observability)
    registry.register_mcp_factory(mcp)
    registry.register_adapter_factory(adapter)
    assert registry.get_provider_factory("fake_provider") is provider
    assert registry.get_tool_factory("fake_tool") is tool
    assert registry.get_memory_factory("fake_memory") is memory
    assert registry.get_knowledge_factory("fake_knowledge") is knowledge
    assert registry.get_guardrail_factory("fake_guardrail") is guardrail
    assert registry.get_observability_factory("fake_observability") is observability
    assert registry.get_mcp_factory("fake_mcp") is mcp
    assert registry.get_adapter_factory("fake_adapter") is adapter


@pytest.mark.parametrize(
    ("register", "factory"),
    [
        ("register_provider_factory", FakeProviderFactory),
        ("register_tool_factory", FakeToolFactory),
        ("register_memory_factory", FakeMemoryFactory),
        ("register_knowledge_factory", FakeKnowledgeFactory),
        ("register_guardrail_factory", FakeGuardrailFactory),
        ("register_observability_factory", FakeObservabilityFactory),
        ("register_mcp_factory", FakeMCPFactory),
        ("register_adapter_factory", FakeAdapterFactory),
    ],
)
def test_duplicate_factory_is_rejected(register: str, factory: type[object]) -> None:
    registry = ConfigurationFactoryRegistry()
    method = getattr(registry, register)
    first = factory()
    method(first)
    with pytest.raises(DuplicateFactoryError):
        method(factory())


def test_invalid_or_missing_factory_type_is_rejected() -> None:
    registry = ConfigurationFactoryRegistry()

    class InvalidFactory:
        type_name = " "

    with pytest.raises(DuplicateFactoryError):
        registry.register_provider_factory(InvalidFactory())  # type: ignore[arg-type]
    with pytest.raises(ComponentFactoryNotFoundError):
        registry.get_provider_factory("missing")
