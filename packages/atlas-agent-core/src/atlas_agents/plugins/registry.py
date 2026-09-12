"""Instance-local registry for plugin implementations and safe state."""

from atlas_agents.plugins.contract import Plugin
from atlas_agents.plugins.contributions import PluginContributionDescriptor
from atlas_agents.plugins.errors import (
    DuplicatePluginError,
    PluginContractError,
    PluginManifestError,
    PluginNotFoundError,
)
from atlas_agents.plugins.manifest import PluginManifest
from atlas_agents.plugins.results import PluginInfo


class PluginRegistry:
    """Store plugins by canonical manifest ID without activating them."""

    def __init__(self) -> None:
        """Initialize isolated plugin and activation state."""
        self._plugins: dict[str, Plugin] = {}
        self._manifests: dict[str, PluginManifest] = {}
        self._active: dict[str, tuple[PluginContributionDescriptor, ...]] = {}

    def register(self, plugin: Plugin) -> None:
        """Register one valid plugin instance without side effects."""
        if not isinstance(plugin, Plugin):
            raise PluginContractError("O objeto registrado não implementa Plugin.")
        try:
            manifest = plugin.manifest
        except Exception as exc:
            raise PluginManifestError(
                f"Não foi possível ler o manifesto ({type(exc).__name__})."
            ) from exc
        if not isinstance(manifest, PluginManifest):
            raise PluginManifestError("O plugin não retornou um PluginManifest válido.")
        plugin_id = manifest.metadata.plugin_id
        if plugin_id in self._plugins:
            raise DuplicatePluginError(
                f"O plugin '{plugin_id}' já está registrado.", plugin_id=plugin_id
            )
        self._plugins[plugin_id] = plugin
        self._manifests[plugin_id] = manifest

    def unregister(self, plugin_id: str) -> Plugin:
        """Remove and return an inactive plugin."""
        if plugin_id in self._active:
            raise PluginContractError(
                f"O plugin ativo '{plugin_id}' deve ser desativado antes da remoção.",
                plugin_id=plugin_id,
            )
        try:
            plugin = self._plugins.pop(plugin_id)
            self._manifests.pop(plugin_id)
            return plugin
        except KeyError as exc:
            raise PluginNotFoundError(
                f"O plugin '{plugin_id}' não está registrado.", plugin_id=plugin_id
            ) from exc

    def get(self, plugin_id: str) -> Plugin:
        """Return one plugin implementation by canonical ID."""
        plugin = self.try_get(plugin_id)
        if plugin is None:
            raise PluginNotFoundError(
                f"O plugin '{plugin_id}' não está registrado.", plugin_id=plugin_id
            )
        return plugin

    def try_get(self, plugin_id: str) -> Plugin | None:
        """Return a plugin when registered, otherwise none."""
        return self._plugins.get(plugin_id)

    def plugins(self) -> tuple[Plugin, ...]:
        """Return an immutable snapshot in registration order."""
        return tuple(self._plugins.values())

    def manifest(self, plugin_id: str) -> PluginManifest:
        """Return the validated manifest snapshot stored at registration."""
        self.get(plugin_id)
        return self._manifests[plugin_id]

    def infos(self) -> tuple[PluginInfo, ...]:
        """Return safe plugin introspection records."""
        return tuple(self.info(plugin_id) for plugin_id in self._plugins)

    def info(self, plugin_id: str) -> PluginInfo:
        """Return safe state without exposing configuration or implementation."""
        self.get(plugin_id)
        descriptors = self._active.get(plugin_id, ())
        return PluginInfo(
            plugin_id=plugin_id,
            manifest=self._manifests[plugin_id],
            active=plugin_id in self._active,
            contribution_descriptors=descriptors,
        )

    def mark_active(
        self, plugin_id: str, descriptors: tuple[PluginContributionDescriptor, ...]
    ) -> None:
        """Record successful activation after all contribution registrations."""
        self.get(plugin_id)
        self._active[plugin_id] = descriptors

    def mark_inactive(self, plugin_id: str) -> None:
        """Remove activation state."""
        self.get(plugin_id)
        self._active.pop(plugin_id, None)

    def is_active(self, plugin_id: str) -> bool:
        """Report whether one registered plugin is active."""
        self.get(plugin_id)
        return plugin_id in self._active
