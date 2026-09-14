"""FastAPI REST adapter factory."""

try:
    import fastapi as _fastapi
except ModuleNotFoundError as error:
    if error.name != "fastapi":
        raise
    from atlas_agents.adapters.optional import MissingAdapterDependencyError

    raise MissingAdapterDependencyError(
        "O adapter REST exige o extra 'rest'. Instale com: "
        "pip install atlas-agent-adapters[rest]"
    ) from None

del _fastapi

from atlas_agents.adapters.rest.app import (  # noqa: E402
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
