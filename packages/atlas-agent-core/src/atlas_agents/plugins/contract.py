"""Plugin authoring contract."""

from abc import ABC, abstractmethod

from atlas_agents.plugins.contributions import (
    PluginContributionDescriptor,
    PluginContributionValue,
)
from atlas_agents.plugins.manifest import PluginContext, PluginManifest


class Plugin(ABC):
    """Declare and explicitly activate one trusted Atlas extension."""

    @property
    @abstractmethod
    def manifest(self) -> PluginManifest:
        """Return immutable identity, compatibility, and capability metadata."""

    @abstractmethod
    def describe(
        self, context: PluginContext
    ) -> tuple[PluginContributionDescriptor, ...]:
        """Describe enabled contributions synchronously and without side effects."""

    @abstractmethod
    async def activate(
        self, context: PluginContext
    ) -> tuple[PluginContributionValue, ...]:
        """Create resources and return contributions after successful preflight."""

    async def deactivate(self, _context: PluginContext) -> None:
        """Release resources created by activation."""
        return
