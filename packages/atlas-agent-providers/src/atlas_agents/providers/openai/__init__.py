"""Official OpenAI Responses API integration for Atlas."""

try:
    import openai as _openai
except ModuleNotFoundError as error:
    if error.name != "openai":
        raise
    from atlas_agents.providers.errors import MissingProviderDependencyError

    raise MissingProviderDependencyError(
        "O suporte OpenAI exige o extra 'openai'. Instale com: "
        "pip install atlas-agent-providers[openai]"
    ) from None

del _openai

from atlas_agents.providers.openai.config import (  # noqa: E402
    OpenAIPluginConfig,
    OpenAIProviderConfig,
)
from atlas_agents.providers.openai.plugin import (  # noqa: E402
    OpenAIPlugin,
    create_plugin,
)
from atlas_agents.providers.openai.provider import OpenAIModelProvider  # noqa: E402

__all__ = [
    "OpenAIModelProvider",
    "OpenAIPlugin",
    "OpenAIPluginConfig",
    "OpenAIProviderConfig",
    "create_plugin",
]
