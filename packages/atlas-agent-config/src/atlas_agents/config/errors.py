"""Safe errors for declarative configuration and composition."""

from __future__ import annotations


class ConfigError(Exception):
    """Base error carrying a stable code and safe configuration path."""

    code = "config_error"

    def __init__(self, message: str, *, path: str = "$") -> None:
        """Store safe public diagnostics without configuration values."""
        super().__init__(message)
        self.path = path


class ConfigParseError(ConfigError):
    """Report malformed or unsafe YAML or JSON."""

    code = "config_parse_error"


class UnsupportedConfigVersionError(ConfigError):
    """Reject a schema version that this package cannot interpret."""

    code = "unsupported_config_version"


class ConfigValidationError(ConfigError):
    """Report strict structural validation failures."""

    code = "config_validation_error"


class ConfigReferenceError(ConfigValidationError):
    """Report missing or disabled component references."""

    code = "config_reference_error"


class ConfigOverrideError(ConfigError):
    """Report an invalid deterministic override mapping."""

    code = "config_override_error"


class FactoryRegistryError(ConfigError):
    """Base factory registration and resolution error."""

    code = "factory_registry_error"


class DuplicateFactoryError(FactoryRegistryError):
    """Reject silent replacement of a registered factory type."""

    code = "duplicate_factory"


class ComponentFactoryNotFoundError(FactoryRegistryError):
    """Report a missing typed component factory."""

    code = "component_factory_not_found"


class ComponentBuildError(ConfigError):
    """Normalize a component factory failure without exposing its config."""

    code = "component_build_error"


class SecretResolutionError(ConfigError):
    """Report a missing or unavailable secret reference safely."""

    code = "secret_resolution_error"


class DuplicateComponentConfigError(ConfigParseError):
    """Reject duplicate mapping keys in source configuration."""

    code = "duplicate_component_config"


class ConfigSecurityError(ConfigError):
    """Report use of an explicitly forbidden configuration feature."""

    code = "config_security_error"


class CompositionBuildError(ConfigError):
    """Report a failed build after reverse cleanup."""

    code = "composition_build_error"


class CompositionCloseError(ConfigError):
    """Report resource cleanup failures after attempting every cleanup."""

    code = "composition_close_error"
