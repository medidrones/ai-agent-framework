"""Tests for descriptor-only discovery, explicit loading, and plugin registry."""

import pytest

from atlas_agents import (
    DuplicatePluginError,
    PluginContractError,
    PluginDiscovery,
    PluginDiscoveryError,
    PluginEntryPoint,
    PluginLoader,
    PluginLoadError,
    PluginManifestError,
    PluginNotFoundError,
    PluginRegistry,
)
from tests.plugins.fakes import FakeDistribution, FakeEntryPoint, FakePlugin


def test_discovery_targets_group_sorts_and_does_not_load() -> None:
    calls: list[str] = []
    entries = (
        FakeEntryPoint("z", "z.plugin:create", lambda: FakePlugin(), distribution=None),
        FakeEntryPoint(
            "a",
            "a.plugin:create",
            lambda: FakePlugin(),
            distribution=FakeDistribution("z-dist"),
        ),
        FakeEntryPoint(
            "b",
            "b.plugin:create",
            lambda: FakePlugin(),
            distribution=FakeDistribution("a-dist"),
        ),
        FakeEntryPoint(
            "ignored",
            "ignored:create",
            lambda: FakePlugin(),
            group="other.plugins",
        ),
    )

    def provider(_group: str) -> tuple[FakeEntryPoint, ...]:
        calls.append(_group)
        return entries

    discovered = PluginDiscovery(provider).discover()

    assert calls == ["atlas_agents.plugins"]
    assert [item.name for item in discovered] == ["z", "b", "a"]
    assert all(entry.load_calls == 0 for entry in entries)
    assert discovered[1].model_dump(mode="json") == {
        "name": "b",
        "group": "atlas_agents.plugins",
        "value": "b.plugin:create",
        "distribution_name": "a-dist",
        "distribution_version": "1.0.0",
    }


def test_discovery_normalizes_provider_failure() -> None:
    def provider(_group: str) -> tuple[FakeEntryPoint, ...]:
        raise OSError("sensitive details")

    with pytest.raises(PluginDiscoveryError) as captured:
        PluginDiscovery(provider).discover()
    assert "OSError" in str(captured.value)
    assert "sensitive details" not in str(captured.value)


def test_default_discovery_lists_descriptors_without_loading() -> None:
    assert isinstance(PluginDiscovery().discover(), tuple)


def discovered_entry(
    factory: object, *, load_error: Exception | None = None
) -> PluginEntryPoint:
    """Create one descriptor through the real discovery boundary."""
    entry = FakeEntryPoint("acme", "acme.plugin:create", factory, load_error=load_error)
    return PluginDiscovery(lambda _group: (entry,)).discover()[0]


def test_loader_calls_valid_factory_exactly_once() -> None:
    plugin = FakePlugin()
    calls = 0

    def factory() -> FakePlugin:
        nonlocal calls
        calls += 1
        return plugin

    loaded = PluginLoader().load(discovered_entry(factory))
    assert loaded is plugin
    assert calls == 1


@pytest.mark.parametrize("factory", [object(), lambda: object()])
def test_loader_rejects_invalid_factory_contract(factory: object) -> None:
    with pytest.raises(PluginContractError):
        PluginLoader().load(discovered_entry(factory))


def test_loader_normalizes_load_and_factory_exceptions() -> None:
    load_entry = discovered_entry(
        lambda: FakePlugin(), load_error=ImportError("SECRET")
    )
    with pytest.raises(PluginLoadError) as load_failure:
        PluginLoader().load(load_entry)
    assert load_failure.value.cause_type == "ImportError"
    assert "SECRET" not in str(load_failure.value)

    def failing_factory() -> FakePlugin:
        raise RuntimeError("SECRET")

    with pytest.raises(PluginLoadError) as factory_failure:
        PluginLoader().load(discovered_entry(failing_factory))
    assert factory_failure.value.cause_type == "RuntimeError"


def test_loader_rejects_descriptor_not_minted_by_discovery() -> None:
    descriptor = PluginEntryPoint(
        name="unsafe",
        group="atlas_agents.plugins",
        value="arbitrary.module:create",
    )
    with pytest.raises(PluginContractError):
        PluginLoader().load(descriptor)


def test_try_load_returns_failure_without_raw_traceback() -> None:
    result = PluginLoader().try_load(discovered_entry(lambda: object()))
    assert result.success is False
    assert result.plugin is None
    assert isinstance(result.error, PluginContractError)
    success = PluginLoader().try_load(discovered_entry(lambda: FakePlugin()))
    assert success.success is True
    assert isinstance(success.plugin, FakePlugin)


def test_loader_does_not_catch_process_control_exceptions() -> None:
    def interrupted() -> FakePlugin:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        PluginLoader().load(discovered_entry(interrupted))


def test_registry_registers_gets_lists_and_unregisters() -> None:
    plugin = FakePlugin()
    registry = PluginRegistry()
    registry.register(plugin)
    assert registry.get("acme.test") is plugin
    assert registry.try_get("missing") is None
    assert registry.plugins() == (plugin,)
    assert registry.info("acme.test").active is False
    assert registry.unregister("acme.test") is plugin
    with pytest.raises(PluginNotFoundError):
        registry.get("acme.test")


def test_registry_rejects_duplicate_id_and_invalid_object() -> None:
    registry = PluginRegistry()
    registry.register(FakePlugin())
    with pytest.raises(DuplicatePluginError):
        registry.register(FakePlugin())
    with pytest.raises(PluginContractError):
        registry.register(object())  # type: ignore[arg-type]

    malformed = FakePlugin()
    malformed._manifest = object()  # type: ignore[assignment]
    with pytest.raises(PluginManifestError):
        PluginRegistry().register(malformed)


def test_active_plugin_cannot_be_unregistered() -> None:
    registry = PluginRegistry()
    registry.register(FakePlugin())
    registry.mark_active("acme.test", ())
    assert registry.is_active("acme.test") is True
    assert registry.infos()[0].active is True
    with pytest.raises(PluginContractError):
        registry.unregister("acme.test")
    registry.mark_inactive("acme.test")
    assert registry.is_active("acme.test") is False
    with pytest.raises(PluginNotFoundError):
        registry.unregister("missing")
