"""Explicit, secret-safe configuration for the OpenAI provider and plugin."""

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from atlas_agents.models import ModelCapability, ModelDescriptor

_OPENAI_CAPABILITIES = frozenset(
    {
        ModelCapability.TEXT_GENERATION,
        ModelCapability.STREAMING,
        ModelCapability.STRUCTURED_OUTPUT,
        ModelCapability.TOOL_CALLING,
        ModelCapability.PARALLEL_TOOL_CALLING,
        ModelCapability.VISION,
    }
)


def default_openai_models() -> tuple[ModelDescriptor, ...]:
    """Return the documented static OpenAI Responses model catalog."""
    return tuple(
        ModelDescriptor(
            provider="openai",
            model=model,
            capabilities=_OPENAI_CAPABILITIES,
            context_window=1_050_000,
            max_output_tokens=128_000,
        )
        for model in (
            "gpt-6-astra",
            "gpt-5.6-sol",
            "gpt-5.6-terra",
            "gpt-5.6-luna",
        )
    )


class OpenAIProviderConfig(BaseModel):
    """Configure stateless Responses calls and the local model catalog."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    store_responses: bool = False
    models: tuple[ModelDescriptor, ...] = Field(default_factory=default_openai_models)

    @field_validator("models")
    @classmethod
    def validate_models(
        cls, value: tuple[ModelDescriptor, ...]
    ) -> tuple[ModelDescriptor, ...]:
        """Require an ordered, non-duplicated OpenAI-only catalog."""
        if not value:
            raise ValueError("models não pode ser vazio")
        if any(item.provider != "openai" for item in value):
            raise ValueError("todos os descriptors devem pertencer ao provider openai")
        if len({item.model for item in value}) != len(value):
            raise ValueError("models não pode conter identificadores duplicados")
        return value


class OpenAIPluginConfig(BaseModel):
    """Validate explicit client configuration without revealing credentials."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    api_key: SecretStr = Field(repr=False)
    base_url: str | None = None
    organization: str | None = None
    project: str | None = None
    timeout: float | None = Field(default=None, gt=0)
    max_retries: int = Field(default=2, ge=0)
    store_responses: bool = False
