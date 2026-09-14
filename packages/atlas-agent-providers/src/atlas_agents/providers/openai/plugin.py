"""Plugin entry point for explicit OpenAI provider composition."""

from openai import AsyncOpenAI
from packaging.version import Version
from pydantic import ValidationError

from atlas_agents.plugins import (
    ModelProviderContribution,
    Plugin,
    PluginCapability,
    PluginContext,
    PluginContributionDescriptor,
    PluginContributionValue,
    PluginManifest,
    PluginMetadata,
)
from atlas_agents.providers._version import __version__
from atlas_agents.providers.openai.config import (
    OpenAIPluginConfig,
    OpenAIProviderConfig,
)
from atlas_agents.providers.openai.provider import OpenAIModelProvider


def _atlas_compatibility_range() -> str:
    release = Version(__version__).release
    major, minor = release[0], release[1]
    return f">={major}.{minor}.0,<{major}.{minor + 1}.0"


class OpenAIPlugin(Plugin):
    """Create and own an OpenAI client only during explicit plugin activation."""

    def __init__(self) -> None:
        """Initialize without creating a client or reading configuration."""
        self._client: AsyncOpenAI | None = None

    @property
    def manifest(self) -> PluginManifest:
        """Return stable, secret-free plugin metadata."""
        return PluginManifest(
            metadata=PluginMetadata(
                plugin_id="openai",
                name="Provider oficial OpenAI",
                version=__version__,
                description="Integra o Atlas à API Responses da OpenAI.",
                author="Atlas Agent Framework",
                homepage="https://github.com/Medicode/ai-agent-framework",
            ),
            capabilities=(PluginCapability.MODEL_PROVIDER,),
            required_atlas_version=_atlas_compatibility_range(),
            optional_dependencies=("openai>=3.13.0,<4",),
        )

    def describe(
        self, context: PluginContext
    ) -> tuple[PluginContributionDescriptor, ...]:
        """Describe the provider without parsing secrets or creating resources."""
        del context
        return (
            PluginContributionDescriptor(
                capability=PluginCapability.MODEL_PROVIDER,
                identifier="openai",
            ),
        )

    async def activate(
        self, context: PluginContext
    ) -> tuple[PluginContributionValue, ...]:
        """Create a plugin-owned client from explicit host configuration."""
        if self._client is not None:
            raise RuntimeError("O plugin OpenAI já possui um cliente ativo.")
        try:
            config = OpenAIPluginConfig.model_validate(context.configuration)
        except ValidationError:
            raise ValueError(
                "A configuração explícita do plugin OpenAI é inválida."
            ) from None
        client_options: dict[str, object] = {
            "api_key": config.api_key.get_secret_value(),
            "max_retries": config.max_retries,
        }
        for name in ("base_url", "organization", "project", "timeout"):
            value = getattr(config, name)
            if value is not None:
                client_options[name] = value
        client = AsyncOpenAI(**client_options)  # type: ignore[arg-type]
        self._client = client
        provider = OpenAIModelProvider(
            client,
            config=OpenAIProviderConfig(store_responses=config.store_responses),
        )
        return (ModelProviderContribution(provider),)

    async def deactivate(self, context: PluginContext) -> None:
        """Close only the client created by this plugin."""
        del context
        client, self._client = self._client, None
        if client is not None:
            await client.close()


def create_plugin() -> OpenAIPlugin:
    """Create the plugin instance used by package entry-point discovery."""
    return OpenAIPlugin()
