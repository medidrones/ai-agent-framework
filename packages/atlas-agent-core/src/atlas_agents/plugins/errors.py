"""Typed, secret-safe failures for plugin operations."""

from pydantic import field_validator

from atlas_agents.plugins._models import FrozenPluginModel, non_empty


class PluginError(Exception):
    """Base class for all plugin subsystem failures."""

    code = "plugin_error"
    operation = "plugin"

    def __init__(self, message: str, *, plugin_id: str | None = None) -> None:
        """Initialize a safe message and optional canonical plugin ID."""
        self.plugin_id = plugin_id
        super().__init__(message)


class PluginManifestError(PluginError):
    """Report invalid plugin manifest data."""

    code = "plugin_manifest_invalid"
    operation = "manifest"


class PluginContractError(PluginError):
    """Report an object that does not implement the plugin contract."""

    code = "plugin_contract_invalid"
    operation = "contract"


class PluginDiscoveryError(PluginError):
    """Report failure while enumerating Python entry points."""

    code = "plugin_discovery_failed"
    operation = "discover"


class PluginLoadError(PluginError):
    """Report a safely normalized entry-point load failure."""

    code = "plugin_load_failed"
    operation = "load"

    def __init__(self, entry_point: str, cause_type: str) -> None:
        """Record only safe entry-point identity and exception type."""
        self.entry_point = entry_point
        self.cause_type = cause_type
        super().__init__(
            f"Não foi possível carregar o entry point '{entry_point}' ({cause_type})."
        )


class PluginCompatibilityError(PluginError):
    """Report incompatibility with the active Atlas version."""

    code = "plugin_incompatible"
    operation = "validate"


class PluginRegistryError(PluginError):
    """Base class for plugin registry failures."""

    code = "plugin_registry_error"
    operation = "registry"


class DuplicatePluginError(PluginRegistryError):
    """Report duplicate canonical plugin IDs."""

    code = "plugin_duplicate"


class PluginNotFoundError(PluginRegistryError):
    """Report an unknown canonical plugin ID."""

    code = "plugin_not_found"


class PluginAlreadyActiveError(PluginError):
    """Report duplicate activation attempts."""

    code = "plugin_already_active"
    operation = "activate"


class PluginNotActiveError(PluginError):
    """Report deactivation or inspection of an inactive plugin."""

    code = "plugin_not_active"
    operation = "deactivate"


class PluginActivationError(PluginError):
    """Normalize unexpected plugin activation failures."""

    code = "plugin_activation_failed"
    operation = "activate"


class PluginProtocolError(PluginError):
    """Report disagreement between declared and activated contributions."""

    code = "plugin_protocol_error"
    operation = "activate"


class PluginContributionConflictError(PluginError):
    """Report an identifier conflict before activation side effects."""

    code = "plugin_contribution_conflict"
    operation = "preflight"

    def __init__(self, plugin_id: str, contribution_type: str, identifier: str) -> None:
        """Identify the conflicting contribution without implementation data."""
        self.contribution_type = contribution_type
        self.identifier = identifier
        super().__init__(
            f"O plugin '{plugin_id}' conflita em {contribution_type} '{identifier}'.",
            plugin_id=plugin_id,
        )


class PluginRegistrationError(PluginError):
    """Report contribution registration failure after successful rollback."""

    code = "plugin_registration_failed"
    operation = "register_contributions"


class PluginRollbackError(PluginError):
    """Report a critical incomplete contribution rollback."""

    code = "plugin_rollback_failed"
    operation = "rollback"


class PluginDeactivationError(PluginError):
    """Report resource cleanup or contribution removal failure."""

    code = "plugin_deactivation_failed"
    operation = "deactivate"


class PluginErrorInfo(FrozenPluginModel):
    """Expose a serializable failure summary without traceback or configuration."""

    code: str
    operation: str
    message: str
    error_type: str

    @field_validator("code", "operation", "message", "error_type")
    @classmethod
    def validate_text(cls, value: str) -> str:
        """Reject blank diagnostics."""
        return non_empty(value, field_name="diagnóstico")

    @classmethod
    def from_error(cls, error: PluginError) -> "PluginErrorInfo":
        """Create a safe public projection of a typed error."""
        return cls(
            code=error.code,
            operation=error.operation,
            message=str(error),
            error_type=type(error).__name__,
        )
