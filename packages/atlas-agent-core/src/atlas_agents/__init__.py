"""Provider-agnostic primitives for building and running AI agents."""

from importlib.metadata import version as _distribution_version

__version__: str = _distribution_version("atlas-agent-core")

__all__ = ["__version__"]
