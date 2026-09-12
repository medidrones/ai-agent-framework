"""Tests for explicit, atomic plugin activation and lifecycle management."""

import asyncio

import pytest

from atlas_agents import (
    EvaluatorContribution,
    GuardrailContribution,
    GuardrailRegistry,
    KnowledgeRetrieverContribution,
    MemoryStoreContribution,
    ModelProviderContribution,
    ModelProviderRegistry,
    ObservabilityContribution,
    PluginActivationError,
    PluginAlreadyActiveError,
    PluginCapability,
    PluginContributionConflictError,
    PluginContributionDescriptor,
    PluginDeactivationError,
    PluginManager,
    PluginNotActiveError,
    PluginProtocolError,
    PluginRegistrationError,
    PluginRollbackError,
    Tool,
    ToolContribution,
    ToolRegistry,
)
from tests.plugins.fakes import (
    FakeEntryPoint,
    FakeEvaluator,
    FakeGuardrail,
    FakeMemoryStore,
    FakePlugin,
    FakeProvider,
    FakeRetriever,
    FakeTool,
    FakeTracer,
)


def descriptor(
    capability: PluginCapability, identifier: str
) -> PluginContributionDescriptor:
    """Build one contribution descriptor."""
    return PluginContributionDescriptor(capability=capability, identifier=identifier)


class FakeEvaluatorRegistry:
    """Evaluator registry double matching the core structural boundary."""

    def __init__(self) -> None:
        self.values: dict[str, FakeEvaluator] = {}

    def register(self, evaluator: FakeEvaluator) -> None:
        if evaluator.evaluator_id in self.values:
            raise ValueError("duplicate")
        self.values[evaluator.evaluator_id] = evaluator

    def unregister(self, evaluator_id: str) -> FakeEvaluator:
        return self.values.pop(evaluator_id)

    def try_get(self, evaluator_id: str) -> FakeEvaluator | None:
        return self.values.get(evaluator_id)


class FailingToolRegistry(ToolRegistry):
    """Record mutation order and inject registration or rollback failures."""

    def __init__(
        self, *, fail_register: str | None = None, fail_unregister: str | None = None
    ) -> None:
        super().__init__()
        self.fail_register = fail_register
        self.fail_unregister = fail_unregister
        self.mutations: list[str] = []

    def register(self, tool: Tool) -> None:
        self.mutations.append(f"register:{tool.definition.name}")
        if tool.definition.name == self.fail_register:
            raise RuntimeError("registration failed")
        super().register(tool)

    def unregister(self, name: str) -> Tool:
        self.mutations.append(f"unregister:{name}")
        if name == self.fail_unregister:
            raise RuntimeError("rollback failed")
        removed = super().unregister(name)
        if not isinstance(removed, FakeTool):
            raise TypeError("Ferramenta inesperada")
        return removed


def tool_plugin(
    *names: str,
    required_atlas_version: str = ">=0.1,<1",
    activate_error: BaseException | None = None,
    deactivate_error: BaseException | None = None,
) -> FakePlugin:
    """Build a plugin whose descriptors and values are named tools."""
    return FakePlugin(
        descriptors=tuple(descriptor(PluginCapability.TOOL, name) for name in names),
        contributions=tuple(ToolContribution(FakeTool(name)) for name in names),
        required_atlas_version=required_atlas_version,
        activate_error=activate_error,
        deactivate_error=deactivate_error,
    )


@pytest.mark.asyncio
async def test_discover_load_register_do_not_activate_or_mutate_registries() -> None:
    tools = ToolRegistry()
    plugin = tool_plugin("weather")
    raw = FakeEntryPoint("acme", "acme:create_plugin", lambda: plugin)
    from atlas_agents import PluginDiscovery

    manager = PluginManager(
        atlas_version="0.1.0",
        tool_registry=tools,
        plugin_discovery=PluginDiscovery(lambda _group: (raw,)),
    )
    discovered = manager.discover()
    loaded = manager.load(discovered[0])
    manager.register_plugin(loaded)

    assert raw.load_calls == 1
    assert tools.tools() == ()
    assert plugin.describe_calls == 0
    assert plugin.activate_calls == 0


@pytest.mark.asyncio
async def test_incompatible_plugin_is_blocked_before_describe_and_activate() -> None:
    plugin = tool_plugin("weather", required_atlas_version=">=2")
    manager = PluginManager(atlas_version="0.1.0")
    manager.register_plugin(plugin)
    from atlas_agents import PluginCompatibilityError

    with pytest.raises(PluginCompatibilityError):
        await manager.activate("acme.test")
    assert plugin.describe_calls == 0
    assert plugin.activate_calls == 0


@pytest.mark.asyncio
async def test_descriptor_conflict_is_detected_before_activation() -> None:
    tools = ToolRegistry()
    tools.register(FakeTool("weather"))
    plugin = tool_plugin("weather")
    manager = PluginManager(atlas_version="0.1.0", tool_registry=tools)
    manager.register_plugin(plugin)

    with pytest.raises(PluginContributionConflictError) as captured:
        await manager.activate("acme.test")
    assert captured.value.identifier == "weather"
    assert plugin.activate_calls == 0
    assert len(tools.tools()) == 1


@pytest.mark.asyncio
async def test_undeclared_and_duplicate_descriptors_are_rejected() -> None:
    undeclared = FakePlugin(
        descriptors=(descriptor(PluginCapability.MODEL_PROVIDER, "fake"),)
    )
    duplicate = FakePlugin(
        descriptors=(
            descriptor(PluginCapability.TOOL, "weather"),
            descriptor(PluginCapability.TOOL, "weather"),
        )
    )
    for plugin in (undeclared, duplicate):
        manager = PluginManager(atlas_version="0.1.0")
        manager.register_plugin(plugin)
        with pytest.raises(PluginProtocolError):
            await manager.activate("acme.test")
        assert plugin.activate_calls == 0


@pytest.mark.asyncio
async def test_managed_contributions_register_only_on_activation() -> None:
    providers = ModelProviderRegistry()
    tools = ToolRegistry()
    guardrails = GuardrailRegistry()
    evaluators = FakeEvaluatorRegistry()
    provider = FakeProvider("acme")
    tool = FakeTool("weather")
    guardrail = FakeGuardrail("safe")
    evaluator = FakeEvaluator("quality")
    descriptors = (
        descriptor(PluginCapability.MODEL_PROVIDER, "acme"),
        descriptor(PluginCapability.TOOL, "weather"),
        descriptor(PluginCapability.GUARDRAIL, "safe"),
        descriptor(PluginCapability.EVALUATOR, "quality"),
    )
    plugin = FakePlugin(
        capabilities=(
            PluginCapability.MODEL_PROVIDER,
            PluginCapability.TOOL,
            PluginCapability.GUARDRAIL,
            PluginCapability.EVALUATOR,
        ),
        descriptors=descriptors,
        contributions=(
            ModelProviderContribution(provider),
            ToolContribution(tool),
            GuardrailContribution(guardrail),
            EvaluatorContribution(evaluator),
        ),
    )
    manager = PluginManager(
        atlas_version="0.1.0",
        model_provider_registry=providers,
        tool_registry=tools,
        guardrail_registry=guardrails,
        evaluator_registry=evaluators,
    )
    manager.register_plugin(plugin)

    result = await manager.activate("acme.test")

    assert result.activated is True
    assert result.registered_contributions == descriptors
    assert result.unregistered_contributions == ()
    assert providers.get("acme") is provider
    assert tools.get("weather") is tool
    assert guardrails.get("safe") is guardrail
    assert evaluators.try_get("quality") is evaluator
    assert manager.registry.info("acme.test").active is True


@pytest.mark.asyncio
async def test_unmanaged_contributions_remain_available_to_host() -> None:
    memory = MemoryStoreContribution("memory", FakeMemoryStore())
    retriever = KnowledgeRetrieverContribution("docs", FakeRetriever())
    telemetry = ObservabilityContribution("telemetry", tracer=FakeTracer())
    descriptors = (
        descriptor(PluginCapability.MEMORY_STORE, "memory"),
        descriptor(PluginCapability.KNOWLEDGE_RETRIEVER, "docs"),
        descriptor(PluginCapability.OBSERVABILITY, "telemetry"),
    )
    plugin = FakePlugin(
        capabilities=(
            PluginCapability.MEMORY_STORE,
            PluginCapability.KNOWLEDGE_RETRIEVER,
            PluginCapability.OBSERVABILITY,
        ),
        descriptors=descriptors,
        contributions=(memory, retriever, telemetry),
    )
    manager = PluginManager(atlas_version="0.1.0")
    manager.register_plugin(plugin)

    result = await manager.activate("acme.test")

    assert result.registered_contributions == ()
    assert result.unregistered_contributions == descriptors
    assert manager.get_contributions("acme.test") == (memory, retriever, telemetry)


@pytest.mark.asyncio
async def test_contribution_mismatch_and_undeclared_output_trigger_cleanup() -> None:
    mismatch = FakePlugin(
        descriptors=(descriptor(PluginCapability.TOOL, "weather"),),
        contributions=(ToolContribution(FakeTool("calculator")),),
    )
    extra = FakePlugin(
        descriptors=(descriptor(PluginCapability.TOOL, "weather"),),
        contributions=(ModelProviderContribution(FakeProvider()),),
    )
    for plugin in (mismatch, extra):
        tools = ToolRegistry()
        manager = PluginManager(atlas_version="0.1.0", tool_registry=tools)
        manager.register_plugin(plugin)
        with pytest.raises(PluginProtocolError):
            await manager.activate("acme.test")
        assert tools.tools() == ()
        assert plugin.deactivate_calls == 1
        assert manager.registry.info("acme.test").active is False


@pytest.mark.asyncio
async def test_invalid_activation_shape_is_rejected_and_cleaned_up() -> None:
    plugin = tool_plugin("weather")
    plugin.contribution_values = [ToolContribution(FakeTool())]  # type: ignore[assignment]
    manager = PluginManager(atlas_version="0.1.0")
    manager.register_plugin(plugin)
    with pytest.raises(PluginProtocolError):
        await manager.activate("acme.test")
    assert plugin.deactivate_calls == 1


@pytest.mark.asyncio
async def test_describe_failure_and_invalid_shape_do_not_activate() -> None:
    failed = FakePlugin(describe_error=RuntimeError("SECRET"))
    invalid = FakePlugin()
    invalid.descriptors = []  # type: ignore[assignment]
    for plugin in (failed, invalid):
        manager = PluginManager(atlas_version="0.1.0")
        manager.register_plugin(plugin)
        expected = PluginActivationError if plugin is failed else PluginProtocolError
        with pytest.raises(expected) as captured:
            await manager.activate("acme.test")
        assert "SECRET" not in str(captured.value)
        assert plugin.activate_calls == 0


@pytest.mark.asyncio
async def test_activation_failure_is_safe_and_does_not_mutate_registry() -> None:
    plugin = tool_plugin(
        "weather",
        activate_error=RuntimeError("SECRET"),
        deactivate_error=RuntimeError("CLEANUP_SECRET"),
    )
    tools = ToolRegistry()
    manager = PluginManager(atlas_version="0.1.0", tool_registry=tools)
    manager.register_plugin(plugin)
    with pytest.raises(PluginActivationError) as captured:
        await manager.activate("acme.test", configuration={"api_key": "SECRET"})
    assert "SECRET" not in str(captured.value)
    assert tools.tools() == ()
    assert plugin.deactivate_calls == 1


@pytest.mark.asyncio
async def test_registration_failure_rolls_back_in_reverse_order() -> None:
    registry = FailingToolRegistry(fail_register="c")
    plugin = tool_plugin("a", "b", "c")
    manager = PluginManager(atlas_version="0.1.0", tool_registry=registry)
    manager.register_plugin(plugin)

    with pytest.raises(PluginRegistrationError):
        await manager.activate("acme.test")

    assert registry.tools() == ()
    assert registry.mutations == [
        "register:a",
        "register:b",
        "register:c",
        "unregister:b",
        "unregister:a",
    ]
    assert plugin.deactivate_calls == 1
    assert manager.registry.info("acme.test").active is False


@pytest.mark.asyncio
async def test_incomplete_rollback_raises_critical_error() -> None:
    registry = FailingToolRegistry(fail_register="b", fail_unregister="a")
    plugin = tool_plugin("a", "b")
    manager = PluginManager(atlas_version="0.1.0", tool_registry=registry)
    manager.register_plugin(plugin)
    with pytest.raises(PluginRollbackError):
        await manager.activate("acme.test")
    assert manager.registry.info("acme.test").active is False


@pytest.mark.asyncio
async def test_deactivation_unregisters_in_reverse_and_allows_reactivation() -> None:
    registry = FailingToolRegistry()
    plugin = tool_plugin("a", "b")
    manager = PluginManager(atlas_version="0.1.0", tool_registry=registry)
    manager.register_plugin(plugin)
    await manager.activate("acme.test")

    await manager.deactivate("acme.test")

    assert registry.mutations[-2:] == ["unregister:b", "unregister:a"]
    assert manager.registry.info("acme.test").active is False
    assert plugin.deactivate_calls == 1
    await manager.activate("acme.test")
    assert manager.registry.info("acme.test").active is True


@pytest.mark.asyncio
async def test_duplicate_activation_and_inactive_access_are_rejected() -> None:
    plugin = tool_plugin("weather")
    manager = PluginManager(atlas_version="0.1.0")
    manager.register_plugin(plugin)
    with pytest.raises(PluginNotActiveError):
        manager.get_contributions("acme.test")
    with pytest.raises(PluginNotActiveError):
        await manager.deactivate("acme.test")
    await manager.activate("acme.test")
    with pytest.raises(PluginAlreadyActiveError):
        await manager.activate("acme.test")


@pytest.mark.asyncio
async def test_activation_and_deactivation_preserve_cancellation() -> None:
    activation = tool_plugin("weather", activate_error=asyncio.CancelledError())
    manager = PluginManager(atlas_version="0.1.0")
    manager.register_plugin(activation)
    with pytest.raises(asyncio.CancelledError):
        await manager.activate("acme.test")
    assert activation.deactivate_calls == 1
    assert manager.registry.info("acme.test").active is False

    deactivation = tool_plugin("weather", deactivate_error=asyncio.CancelledError())
    tools = ToolRegistry()
    other = PluginManager(atlas_version="0.1.0", tool_registry=tools)
    other.register_plugin(deactivation)
    await other.activate("acme.test")
    with pytest.raises(asyncio.CancelledError):
        await other.deactivate("acme.test")
    assert tools.tools() == ()
    assert other.registry.info("acme.test").active is False


@pytest.mark.asyncio
async def test_deactivation_error_keeps_plugin_inactive() -> None:
    plugin = tool_plugin("weather", deactivate_error=RuntimeError("SECRET"))
    manager = PluginManager(atlas_version="0.1.0")
    manager.register_plugin(plugin)
    await manager.activate("acme.test")
    with pytest.raises(PluginDeactivationError) as captured:
        await manager.deactivate("acme.test")
    assert "SECRET" not in str(captured.value)
    assert manager.registry.info("acme.test").active is False


@pytest.mark.asyncio
async def test_unregister_failure_is_reported_after_cleanup() -> None:
    registry = FailingToolRegistry(fail_unregister="weather")
    plugin = tool_plugin("weather")
    manager = PluginManager(atlas_version="0.1.0", tool_registry=registry)
    manager.register_plugin(plugin)
    await manager.activate("acme.test")
    with pytest.raises(PluginDeactivationError):
        await manager.deactivate("acme.test")
    assert plugin.deactivate_calls == 1
    assert manager.registry.info("acme.test").active is False
