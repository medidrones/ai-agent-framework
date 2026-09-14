"""Optional official model-provider adapters for Atlas."""

from atlas_agents.providers._version import __version__
from atlas_agents.providers.errors import MissingProviderDependencyError

__all__ = [
    "MissingProviderDependencyError",
    "__version__",
]
