"""Safe descriptor-first discovery and explicit Python entry-point loading."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from importlib import metadata as importlib_metadata
from typing import Protocol, Self

from pydantic import PrivateAttr, field_validator

from atlas_agents.plugins._models import FrozenPluginModel, non_empty
from atlas_agents.plugins.contract import Plugin
from atlas_agents.plugins.errors import (
    PluginContractError,
    PluginDiscoveryError,
    PluginLoadError,
)

PLUGIN_ENTRY_POINT_GROUP = "atlas_agents.plugins"


class _DistributionLike(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def version(self) -> str: ...


class _EntryPointLike(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def value(self) -> str: ...

    @property
    def group(self) -> str: ...

    @property
    def dist(self) -> _DistributionLike | None: ...

    def load(self) -> object: ...


type EntryPointsProvider = Callable[[str], Iterable[_EntryPointLike]]


def _installed_entry_points(group: str) -> Iterable[_EntryPointLike]:
    return importlib_metadata.entry_points(group=group)


class PluginEntryPoint(FrozenPluginModel):
    """Expose entry-point metadata without loading or leaking Python objects."""

    name: str
    group: str
    value: str
    distribution_name: str | None = None
    distribution_version: str | None = None
    _source: _EntryPointLike | None = PrivateAttr(default=None)

    @field_validator("name", "group", "value")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        """Reject blank entry-point identity fields."""
        return non_empty(value, field_name="entry_point")

    @field_validator("distribution_name", "distribution_version")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        """Normalize optional distribution fields."""
        return (
            non_empty(value, field_name="distribution") if value is not None else None
        )

    @classmethod
    def from_discovered(cls, source: _EntryPointLike) -> Self:
        """Create a public descriptor bound to one discovered entry point."""
        distribution = source.dist
        descriptor = cls(
            name=source.name,
            group=source.group,
            value=source.value,
            distribution_name=distribution.name if distribution is not None else None,
            distribution_version=(
                distribution.version if distribution is not None else None
            ),
        )
        descriptor._source = source
        return descriptor

    @property
    def identity(self) -> str:
        """Return a safe diagnostic identity."""
        distribution = self.distribution_name or "distribuição desconhecida"
        return f"{distribution}:{self.name}"


class PluginDiscovery:
    """Discover only Atlas plugin descriptors in deterministic order."""

    def __init__(
        self, entry_points_provider: EntryPointsProvider | None = None
    ) -> None:
        """Use the standard metadata provider unless one is injected."""
        self._entry_points_provider = entry_points_provider or _installed_entry_points

    def discover(self) -> tuple[PluginEntryPoint, ...]:
        """List descriptors without importing, instantiating, or activating plugins."""
        try:
            discovered = self._entry_points_provider(PLUGIN_ENTRY_POINT_GROUP)
            descriptors = tuple(
                PluginEntryPoint.from_discovered(entry_point)
                for entry_point in discovered
                if entry_point.group == PLUGIN_ENTRY_POINT_GROUP
            )
        except Exception as exc:
            raise PluginDiscoveryError(
                f"Não foi possível descobrir plugins ({type(exc).__name__})."
            ) from exc
        return tuple(
            sorted(
                descriptors,
                key=lambda item: (
                    item.distribution_name or "",
                    item.name,
                    item.value,
                ),
            )
        )


@dataclass(frozen=True, slots=True)
class PluginLoadResult:
    """Represent one explicit load attempt without raising to batch callers."""

    entry_point: PluginEntryPoint
    plugin: Plugin | None = None
    error: PluginLoadError | PluginContractError | None = None

    @property
    def success(self) -> bool:
        """Report whether the factory produced a valid plugin."""
        return self.plugin is not None and self.error is None


class PluginLoader:
    """Load exactly one previously discovered, trusted entry-point factory."""

    def load(self, entry_point: PluginEntryPoint) -> Plugin:
        """Load and invoke the canonical synchronous zero-argument factory once."""
        if entry_point.group != PLUGIN_ENTRY_POINT_GROUP or entry_point._source is None:
            raise PluginContractError(
                "O entry point não foi produzido pela descoberta de plugins do Atlas."
            )
        try:
            factory = entry_point._source.load()
        except Exception as exc:
            raise PluginLoadError(entry_point.identity, type(exc).__name__) from exc
        if not callable(factory):
            raise PluginContractError(
                f"O entry point '{entry_point.identity}' não expõe uma "
                "factory chamável."
            )
        try:
            plugin = factory()
        except Exception as exc:
            raise PluginLoadError(entry_point.identity, type(exc).__name__) from exc
        if not isinstance(plugin, Plugin):
            raise PluginContractError(
                f"A factory de '{entry_point.identity}' não retornou um Plugin."
            )
        return plugin

    def try_load(self, entry_point: PluginEntryPoint) -> PluginLoadResult:
        """Return a typed load result for an expected plugin failure."""
        try:
            return PluginLoadResult(
                entry_point=entry_point, plugin=self.load(entry_point)
            )
        except (PluginLoadError, PluginContractError) as exc:
            return PluginLoadResult(entry_point=entry_point, error=exc)
