"""FastAPI REST adapter factory."""

from atlas_agents.adapters.rest.app import (
    AnonymousRESTPrincipalFactory,
    RESTAdapterConfig,
    RESTPrincipalFactory,
    create_app,
)

__all__ = [
    "AnonymousRESTPrincipalFactory",
    "RESTAdapterConfig",
    "RESTPrincipalFactory",
    "create_app",
]
