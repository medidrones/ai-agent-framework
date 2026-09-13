from __future__ import annotations

import json
from collections.abc import ItemsView, Iterator, Mapping

import pytest

from atlas_agents.config import (
    AtlasConfig,
    ConfigOverrideError,
    MappingSecretResolver,
    RejectingSecretResolver,
    SecretReference,
    SecretResolutionError,
    SecretValue,
    configuration_fingerprint,
    load_yaml,
    merge_config_overrides,
)


def test_secret_value_repr_and_str_are_redacted() -> None:
    value = SecretValue("SUPER-SECRET")
    assert repr(value) == "SecretValue(********)"
    assert str(value) == "********"
    assert value.get_secret_value() == "SUPER-SECRET"
    assert "SUPER-SECRET" not in repr(value)


def test_secret_value_rejects_empty_value() -> None:
    with pytest.raises(ValueError, match="vazio"):
        SecretValue("")


@pytest.mark.asyncio
async def test_mapping_secret_resolver_resolves_only_explicit_mapping() -> None:
    resolver = MappingSecretResolver(
        {"openai/main": "key-value", "wrapped": SecretValue("wrapped-value")}
    )
    resolved = await resolver.resolve(
        SecretReference(secret_ref="openai/main")  # noqa: S106
    )
    wrapped = await resolver.resolve(
        SecretReference(secret_ref="wrapped")  # noqa: S106
    )
    assert resolved.get_secret_value() == "key-value"
    assert wrapped.get_secret_value() == "wrapped-value"
    with pytest.raises(SecretResolutionError, match="missing"):
        await resolver.resolve(SecretReference(secret_ref="missing"))  # noqa: S106


@pytest.mark.asyncio
async def test_resolvers_reject_unavailable_or_empty_secret_safely() -> None:
    reference = SecretReference(secret_ref="openai/main")  # noqa: S106
    with pytest.raises(SecretResolutionError) as missing:
        await RejectingSecretResolver().resolve(reference)
    with pytest.raises(SecretResolutionError) as empty:
        await MappingSecretResolver({"openai/main": ""}).resolve(reference)
    assert "key-value" not in str(missing.value)
    assert "key-value" not in str(empty.value)


def test_config_serialization_keeps_reference_not_resolved_value() -> None:
    config = load_yaml(
        """
schema_version: 1
providers:
  fake:
    type: fake_provider
    config:
      api_key:
        secret_ref: openai/main
"""
    )
    serialized = config.model_dump_json()
    assert "openai/main" in serialized
    assert "actual-secret" not in serialized
    assert isinstance(config.providers["fake"].config["api_key"], SecretReference)


def test_mapping_override_deep_merges_and_replaces_scalar_and_list() -> None:
    base = {
        "atlas": {"default_limits": {"max_turns": 10, "max_tool_calls": 4}},
        "agents": {"assistant": {"tools": ["one", "two"]}},
    }
    override = {
        "atlas": {"default_limits": {"max_turns": 3}},
        "agents": {"assistant": {"tools": ["replacement"]}},
    }
    merged = merge_config_overrides(base, override)
    assert merged["atlas"] == {"default_limits": {"max_turns": 3, "max_tool_calls": 4}}
    assert merged["agents"] == {"assistant": {"tools": ["replacement"]}}
    assert base["agents"] == {"assistant": {"tools": ["one", "two"]}}


def test_null_and_mapping_type_override_replace_explicitly() -> None:
    assert merge_config_overrides({"value": {"nested": 1}}, {"value": None}) == {
        "value": None
    }
    assert merge_config_overrides({"value": 1}, {"value": {"nested": 2}}) == {
        "value": {"nested": 2}
    }


def test_invalid_override_mapping_is_normalized() -> None:
    class BrokenMapping(Mapping[str, object]):
        def __getitem__(self, key: str) -> object:
            raise KeyError(key)

        def __iter__(self) -> Iterator[str]:
            return iter(())

        def __len__(self) -> int:
            return 0

        def items(self) -> ItemsView[str, object]:
            raise RuntimeError("broken")

    with pytest.raises(ConfigOverrideError):
        merge_config_overrides({}, BrokenMapping())


def test_loader_applies_override_before_validation() -> None:
    config = load_yaml(
        "schema_version: 1\natlas:\n  default_limits:\n    max_turns: 10\n",
        overrides={"atlas": {"default_limits": {"max_turns": 2}}},
    )
    assert config.atlas.default_limits.max_turns == 2


def test_configuration_fingerprint_is_stable_and_uses_only_references() -> None:
    first = load_yaml(
        """
schema_version: 1
providers:
  fake:
    type: fake_provider
    config:
      api_key: {secret_ref: openai/main}
"""
    )
    equivalent = AtlasConfig.model_validate(json.loads(first.model_dump_json()))
    changed = load_yaml(
        "schema_version: 1\natlas:\n  default_limits:\n    max_turns: 2\n"
    )
    assert configuration_fingerprint(first) == configuration_fingerprint(equivalent)
    assert configuration_fingerprint(first) != configuration_fingerprint(changed)
    assert "actual-secret" not in configuration_fingerprint(first)
