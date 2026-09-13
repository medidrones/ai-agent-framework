"""Deterministic mapping override rules for raw configuration data."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

from atlas_agents.config.errors import ConfigOverrideError


def merge_config_overrides(
    base: Mapping[str, object], override: Mapping[str, object] | None = None
) -> dict[str, object]:
    """Deep-merge mappings while replacing scalars, lists, and nulls."""
    try:
        result = deepcopy(dict(base))
        if override is None:
            return result
        return _merge(result, override)
    except ConfigOverrideError:
        raise
    except Exception as error:
        raise ConfigOverrideError("Não foi possível aplicar os overrides.") from error


def _merge(
    base: dict[str, object], override: Mapping[str, object]
) -> dict[str, object]:
    result = deepcopy(base)
    for key, value in override.items():
        existing = result.get(key)
        if isinstance(existing, dict) and isinstance(value, Mapping):
            result[key] = _merge(existing, value)
        else:
            result[key] = deepcopy(value)
    return result
