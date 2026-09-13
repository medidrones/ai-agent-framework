"""Error normalization, plugin lifecycle, secret safety, and boundaries."""

import ast
import asyncio
from pathlib import Path
from typing import ClassVar

import httpx2
import openai
import pytest
from conftest import context, provider_with, request
from pydantic import SecretStr

from atlas_agents.exceptions import (
    ModelAuthenticationError,
    ModelInvalidRequestError,
    ModelNotFoundError,
    ModelPermissionError,
    ModelProviderError,
    ModelRateLimitError,
    ModelTimeoutError,
    ModelUnavailableError,
)
from atlas_agents.plugins import PluginCapability, PluginContext
from atlas_agents.providers.openai import (
    OpenAIPlugin,
    OpenAIPluginConfig,
    create_plugin,
)
from atlas_agents.providers.openai._errors import OpenAIErrorMapper


def sdk_status_error(error_type: type[openai.APIStatusError], status: int) -> Exception:
    """Build one SDK status error without credentials or network."""
    request_value = httpx2.Request("POST", "https://api.openai.com/v1/responses")
    response_value = httpx2.Response(status, request=request_value)
    return error_type("unsafe raw body", response=response_value, body=None)


@pytest.mark.parametrize(
    ("error", "expected", "retryable"),
    [
        (
            sdk_status_error(openai.AuthenticationError, 401),
            ModelAuthenticationError,
            False,
        ),
        (
            sdk_status_error(openai.PermissionDeniedError, 403),
            ModelPermissionError,
            False,
        ),
        (sdk_status_error(openai.NotFoundError, 404), ModelNotFoundError, False),
        (sdk_status_error(openai.RateLimitError, 429), ModelRateLimitError, True),
        (
            sdk_status_error(openai.BadRequestError, 400),
            ModelInvalidRequestError,
            False,
        ),
        (
            sdk_status_error(openai.UnprocessableEntityError, 422),
            ModelInvalidRequestError,
            False,
        ),
        (
            openai.APITimeoutError(
                request=httpx2.Request("POST", "https://api.openai.com")
            ),
            ModelTimeoutError,
            True,
        ),
        (
            openai.APIConnectionError(
                request=httpx2.Request("POST", "https://api.openai.com")
            ),
            ModelUnavailableError,
            True,
        ),
        (RuntimeError("sk-secret-example"), ModelProviderError, False),
    ],
)
def test_error_mapping_is_safe_and_retryability_is_preserved(
    error: Exception, expected: type[ModelProviderError], retryable: bool
) -> None:
    mapped = OpenAIErrorMapper().map(error, model="gpt-6-astra")
    assert type(mapped) is expected
    assert mapped.retryable is retryable
    assert "unsafe raw body" not in str(mapped)
    assert "sk-secret-example" not in str(mapped)


@pytest.mark.asyncio
async def test_generate_normalizes_unexpected_errors_and_preserves_cancellation() -> (
    None
):
    provider, _ = provider_with(RuntimeError("sk-secret-example"))
    with pytest.raises(ModelProviderError) as caught:
        await provider.generate(request(), context())
    assert "sk-secret-example" not in str(caught.value)
    assert caught.value.__cause__ is None

    cancelled, _ = provider_with(asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await cancelled.generate(request(), context())


class FakePluginClient:
    """Record plugin client options and close ownership."""

    instances: ClassVar[list["FakePluginClient"]] = []

    def __init__(self, **options: object) -> None:
        self.options = options
        self.closed = False
        self.responses = object()
        self.instances.append(self)

    async def close(self) -> None:
        """Record plugin cleanup."""
        self.closed = True


@pytest.mark.asyncio
async def test_plugin_is_side_effect_free_then_owns_and_closes_its_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import atlas_agents.providers.openai.plugin as plugin_module

    FakePluginClient.instances.clear()
    monkeypatch.setattr(plugin_module, "AsyncOpenAI", FakePluginClient)
    plugin = OpenAIPlugin()
    plugin_context = PluginContext.create(
        atlas_version="0.1.0",
        configuration={
            "api_key": "sk-secret-example",
            "base_url": "https://example.test/v1",
            "store_responses": False,
        },
    )
    assert plugin.manifest.capabilities == (PluginCapability.MODEL_PROVIDER,)
    assert plugin.describe(plugin_context)[0].identifier == "openai"
    assert FakePluginClient.instances == []

    contributions = await plugin.activate(plugin_context)
    client = FakePluginClient.instances[0]
    assert client.options["api_key"] == "sk-secret-example"
    assert contributions[0].identifier == "openai"
    safe_values = repr(plugin.manifest) + repr(plugin_context) + repr(contributions)
    assert "sk-secret-example" not in safe_values
    await plugin.deactivate(plugin_context)
    assert client.closed is True
    await plugin.deactivate(plugin_context)
    assert isinstance(create_plugin(), OpenAIPlugin)


@pytest.mark.asyncio
async def test_plugin_rejects_invalid_config_and_duplicate_activation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import atlas_agents.providers.openai.plugin as plugin_module

    monkeypatch.setattr(plugin_module, "AsyncOpenAI", FakePluginClient)
    plugin = OpenAIPlugin()
    invalid = PluginContext.create(atlas_version="0.1.0", configuration={})
    with pytest.raises(ValueError, match="configuração explícita") as caught:
        await plugin.activate(invalid)
    assert caught.value.__cause__ is None
    valid = PluginContext.create(
        atlas_version="0.1.0",
        configuration={
            "api_key": "secret",
            "organization": "org",
            "project": "project",
            "timeout": 10.0,
        },
    )
    await plugin.activate(valid)
    with pytest.raises(RuntimeError, match="ativo"):
        await plugin.activate(valid)
    await plugin.deactivate(valid)


def test_secret_config_repr_and_validation_are_safe() -> None:
    config = OpenAIPluginConfig(api_key=SecretStr("sk-secret-example"))
    assert "sk-secret-example" not in repr(config)
    with pytest.raises(ValueError, match="unexpected"):
        OpenAIPluginConfig.model_validate({"api_key": "x", "unexpected": True})


def test_provider_package_does_not_import_runtime_owners() -> None:
    root = Path(__file__).parents[1] / "src" / "atlas_agents" / "providers"
    forbidden = {
        "AgentRuntime",
        "ToolExecutor",
        "MemoryManager",
        "KnowledgeManager",
        "GuardrailManager",
        "EvaluationRunner",
    }
    imported: set[str] = set()
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported.update(alias.name for alias in node.names)
    assert imported.isdisjoint(forbidden)


def test_openai_sdk_is_absent_from_core_dependencies_and_imports() -> None:
    repository = Path(__file__).parents[3]
    core = repository / "packages" / "atlas-agent-core"
    assert "openai" not in (core / "pyproject.toml").read_text(encoding="utf-8").lower()
    for path in (core / "src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name.split(".")[0] != "openai" for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] != "openai"
