"""Serializable plugin operation and introspection results."""

from pydantic import field_validator

from atlas_agents.plugins._models import FrozenPluginModel, non_empty
from atlas_agents.plugins.contributions import PluginContributionDescriptor
from atlas_agents.plugins.errors import PluginErrorInfo
from atlas_agents.plugins.manifest import PluginManifest


class PluginActivationResult(FrozenPluginModel):
    """Summarize activation without exposing implementation objects or secrets."""

    plugin_id: str
    activated: bool
    contributions: tuple[PluginContributionDescriptor, ...] = ()
    registered_contributions: tuple[PluginContributionDescriptor, ...] = ()
    unregistered_contributions: tuple[PluginContributionDescriptor, ...] = ()
    error: PluginErrorInfo | None = None

    @field_validator("plugin_id")
    @classmethod
    def validate_plugin_id(cls, value: str) -> str:
        """Reject blank plugin IDs."""
        return non_empty(value, field_name="plugin_id")


class PluginInfo(FrozenPluginModel):
    """Expose safe plugin state without configuration or implementation objects."""

    plugin_id: str
    manifest: PluginManifest
    active: bool = False
    contribution_descriptors: tuple[PluginContributionDescriptor, ...] = ()

    @field_validator("plugin_id")
    @classmethod
    def validate_plugin_id(cls, value: str) -> str:
        """Reject blank plugin IDs."""
        return non_empty(value, field_name="plugin_id")
