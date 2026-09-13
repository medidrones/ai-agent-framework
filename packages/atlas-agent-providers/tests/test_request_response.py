"""Request, response, catalog, registry, and privacy tests."""

import json
from types import SimpleNamespace
from typing import cast

import httpx2
import pytest
from conftest import context, provider_with, request, response, usage
from openai import AsyncOpenAI

from atlas_agents.exceptions import ModelInvalidRequestError, ModelResponseError
from atlas_agents.models import (
    AudioContent,
    FinishReason,
    ImageContent,
    MessageRole,
    ModelCapability,
    ModelDescriptor,
    ModelMessage,
    ModelProviderRegistry,
    ModelRequest,
    ModelSelectionRequest,
    ModelToolDefinition,
    StructuredOutputDefinition,
    TextContent,
    ToolCall,
)
from atlas_agents.providers.openai import OpenAIModelProvider, OpenAIProviderConfig
from atlas_agents.providers.openai._response import OpenAIResponseMapper


@pytest.mark.asyncio
async def test_request_maps_all_roles_tools_schema_image_and_privacy() -> None:
    output: list[object] = [
        {
            "type": "message",
            "content": [
                {"type": "output_text", "text": "parte 1"},
                {"type": "output_text", "text": "parte 2"},
            ],
        }
    ]
    provider, client = provider_with(response(output=output, usage=usage()))
    model_request = ModelRequest(
        model="gpt-6-astra",
        messages=(
            ModelMessage(
                role=MessageRole.SYSTEM,
                content=(TextContent(text="sistema"),),
            ),
            ModelMessage(
                role=MessageRole.DEVELOPER,
                content=(TextContent(text="desenvolvedor"),),
            ),
            ModelMessage(
                role=MessageRole.USER,
                content=(
                    TextContent(text="usuário"),
                    ImageContent(uri="https://example.com/image.png", detail="high"),
                ),
            ),
            ModelMessage(
                role=MessageRole.ASSISTANT,
                content=(TextContent(text="vou consultar"),),
                tool_calls=(
                    ToolCall(
                        tool_call_id="call-1",
                        name="weather",
                        arguments={"city": "São Paulo"},
                    ),
                ),
            ),
            ModelMessage(
                role=MessageRole.TOOL,
                tool_call_id="call-1",
                content=(TextContent(text='{"temperature":24}'),),
            ),
        ),
        tools=(
            ModelToolDefinition(
                name="weather",
                description="Consulta clima",
                parameters={
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                },
            ),
        ),
        structured_output=StructuredOutputDefinition(
            name="forecast",
            description="Previsão",
            json_schema={"type": "object", "required": ["temperature"]},
            strict=True,
        ),
        temperature=0.4,
        max_output_tokens=100,
        metadata={"secret": "not-forwarded"},
    )

    result = await provider.generate(model_request, context())

    payload = client.responses.calls[0]
    assert payload["store"] is False
    assert payload["temperature"] == 0.4
    assert payload["max_output_tokens"] == 100
    assert payload["parallel_tool_calls"] is True
    assert "metadata" not in payload
    assert "previous_response_id" not in payload
    assert "conversation" not in payload
    assert "user" not in payload
    mapped_input = payload["input"]
    assert isinstance(mapped_input, list)
    assert [item["role"] for item in mapped_input[:4]] == [
        "system",
        "developer",
        "user",
        "assistant",
    ]
    assert mapped_input[2]["content"][1] == {
        "type": "input_image",
        "image_url": "https://example.com/image.png",
        "detail": "high",
    }
    assert mapped_input[4] == {
        "type": "function_call",
        "call_id": "call-1",
        "name": "weather",
        "arguments": '{"city":"São Paulo"}',
    }
    assert mapped_input[5]["type"] == "function_call_output"
    assert mapped_input[5]["call_id"] == "call-1"
    mapped_tools = cast("list[dict[str, object]]", payload["tools"])
    mapped_text = cast("dict[str, object]", payload["text"])
    assert mapped_tools[0]["strict"] is None
    assert mapped_text["format"] == {
        "type": "json_schema",
        "name": "forecast",
        "description": "Previsão",
        "schema": {"type": "object", "required": ["temperature"]},
        "strict": True,
    }
    assert all(isinstance(item, TextContent) for item in result.content)
    assert [item.text for item in result.content if isinstance(item, TextContent)] == [
        "parte 1",
        "parte 2",
    ]
    assert result.usage.cached_input_tokens == 3
    assert result.usage.reasoning_tokens == 2
    assert result.usage.estimated_cost is None
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "execution-secret" not in serialized
    assert "request-secret" not in serialized
    assert "not-forwarded" not in serialized


@pytest.mark.asyncio
async def test_data_url_is_supported_and_storage_is_explicit() -> None:
    provider, client = provider_with(response())
    provider = OpenAIModelProvider(
        cast("AsyncOpenAI", client),
        config=OpenAIProviderConfig(store_responses=True),
    )
    await provider.generate(
        ModelRequest(
            model="gpt-6-astra",
            messages=(
                ModelMessage(
                    role=MessageRole.USER,
                    content=(ImageContent(uri="data:image/png;base64,AAAA"),),
                ),
            ),
        ),
        context(),
    )
    assert client.responses.calls[0]["store"] is True


@pytest.mark.parametrize(
    "model_request",
    [
        ModelRequest(
            model="gpt-6-astra",
            messages=(
                ModelMessage(role=MessageRole.USER, content=(TextContent(text="x"),)),
            ),
            stop_sequences=("stop",),
        ),
        ModelRequest(
            model="gpt-6-astra",
            messages=(
                ModelMessage(role=MessageRole.USER, content=(TextContent(text="x"),)),
            ),
            temperature=2.1,
        ),
        ModelRequest(
            model="gpt-6-astra",
            messages=(
                ModelMessage(
                    role=MessageRole.USER,
                    content=(ImageContent(uri="http://example.com/x.png"),),
                ),
            ),
        ),
        ModelRequest(
            model="gpt-6-astra",
            messages=(
                ModelMessage(
                    role=MessageRole.USER,
                    content=(AudioContent(uri="https://example.com/x.mp3"),),
                ),
            ),
        ),
    ],
)
@pytest.mark.asyncio
async def test_unsupported_request_features_are_provider_neutral(
    model_request: ModelRequest,
) -> None:
    provider, _ = provider_with(response())
    with pytest.raises(ModelInvalidRequestError):
        await provider.generate(model_request, context())


@pytest.mark.asyncio
async def test_mixed_text_and_multiple_tool_calls_preserve_order() -> None:
    provider, _ = provider_with(
        response(
            output=[
                {"type": "reasoning"},
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "consultando"}],
                },
                {
                    "type": "function_call",
                    "call_id": "call-a",
                    "name": "first",
                    "arguments": '{"value":1}',
                },
                {
                    "type": "function_call",
                    "call_id": "call-b",
                    "name": "second",
                    "arguments": '{"value":2}',
                },
            ],
            usage=usage(),
        )
    )
    result = await provider.generate(request(), context())
    assert result.finish_reason is FinishReason.TOOL_CALL
    assert isinstance(result.content[0], TextContent)
    assert result.content[0].text == "consultando"
    assert [call.tool_call_id for call in result.tool_calls] == ["call-a", "call-b"]
    assert result.model == "gpt-6-astra-2026-09-01"
    assert result.response_id == "resp-1"


@pytest.mark.parametrize("arguments", ["{bad", "[]", "null"])
@pytest.mark.asyncio
async def test_malformed_tool_arguments_are_rejected(arguments: str) -> None:
    provider, _ = provider_with(
        response(
            output=[
                {
                    "type": "function_call",
                    "call_id": "call-1",
                    "name": "tool",
                    "arguments": arguments,
                }
            ]
        )
    )
    with pytest.raises(ModelResponseError) as caught:
        await provider.generate(request(), context())
    assert caught.value.__cause__ is None


@pytest.mark.parametrize(
    ("provider_response", "expected"),
    [
        (response(), FinishReason.STOP),
        (
            response(status="incomplete", incomplete_reason="max_output_tokens"),
            FinishReason.LENGTH,
        ),
        (
            response(status="incomplete", incomplete_reason="content_filter"),
            FinishReason.CONTENT_FILTER,
        ),
        (response(status="cancelled"), FinishReason.CANCELLED),
        (response(status="queued"), FinishReason.UNKNOWN),
        (
            response(output=[{"type": "message", "content": [{"type": "refusal"}]}]),
            FinishReason.CONTENT_FILTER,
        ),
    ],
)
@pytest.mark.asyncio
async def test_finish_reason_mapping(
    provider_response: dict[str, object], expected: FinishReason
) -> None:
    provider, _ = provider_with(provider_response)
    assert (await provider.generate(request(), context())).finish_reason is expected


@pytest.mark.asyncio
async def test_catalog_and_registry_selection_are_local_and_honest() -> None:
    provider, client = provider_with()
    models = await provider.list_models()
    assert provider.provider_name == "openai"
    assert [item.model for item in models] == [
        "gpt-6-astra",
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
    ]
    assert client.responses.calls == []
    required = {
        ModelCapability.TEXT_GENERATION,
        ModelCapability.STREAMING,
        ModelCapability.STRUCTURED_OUTPUT,
        ModelCapability.TOOL_CALLING,
        ModelCapability.PARALLEL_TOOL_CALLING,
        ModelCapability.VISION,
    }
    assert all(item.capabilities == required for item in models)
    assert all(ModelCapability.AUDIO_INPUT not in item.capabilities for item in models)
    registry = ModelProviderRegistry()
    registry.register(provider)
    selected = await registry.select(
        ModelSelectionRequest(
            provider="openai",
            model="gpt-6-astra",
            required_capabilities=frozenset({ModelCapability.VISION}),
        )
    )
    assert selected.provider_name == "openai"


@pytest.mark.asyncio
async def test_sdk_object_fields_are_supported_without_raw_metadata() -> None:
    sdk_like = SimpleNamespace(
        id="resp-object",
        model="gpt-6-astra",
        status="completed",
        error=None,
        incomplete_details=None,
        output=[
            SimpleNamespace(
                type="message",
                content=[SimpleNamespace(type="output_text", text="ok")],
            )
        ],
        usage=None,
    )
    provider, _ = provider_with(sdk_like)
    result = await provider.generate(request(), context())
    assert isinstance(result.content[0], TextContent)
    assert result.content[0].text == "ok"
    assert result.metadata == {}
    assert result.usage.total_tokens == 0


@pytest.mark.asyncio
async def test_actual_sdk_responses_method_accepts_mapped_payload_without_network() -> (
    None
):
    captured: dict[str, object] = {}

    async def handler(http_request: httpx2.Request) -> httpx2.Response:
        captured["path"] = http_request.url.path
        captured["payload"] = json.loads((await http_request.aread()).decode())
        return httpx2.Response(
            200,
            json={
                "id": "resp-sdk",
                "object": "response",
                "created_at": 1,
                "status": "completed",
                "error": None,
                "incomplete_details": None,
                "instructions": None,
                "max_output_tokens": None,
                "model": "gpt-6-astra",
                "output": [
                    {
                        "id": "msg-sdk",
                        "type": "message",
                        "status": "completed",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "SDK válido",
                                "annotations": [],
                            }
                        ],
                    }
                ],
                "parallel_tool_calls": False,
                "previous_response_id": None,
                "temperature": None,
                "tool_choice": "auto",
                "tools": [],
                "top_p": None,
                "background": False,
                "usage": {
                    "input_tokens": 1,
                    "input_tokens_details": {
                        "cached_tokens": 0,
                        "cache_write_tokens": 0,
                    },
                    "output_tokens": 1,
                    "output_tokens_details": {"reasoning_tokens": 0},
                    "total_tokens": 2,
                },
            },
        )

    http_client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    client = AsyncOpenAI(
        api_key="sk-test-only",
        base_url="https://example.test/v1",
        max_retries=0,
        http_client=http_client,
    )
    try:
        provider = OpenAIModelProvider(client)
        result = await provider.generate(request(), context())
    finally:
        await client.close()
    assert captured["path"] == "/v1/responses"
    payload = cast("dict[str, object]", captured["payload"])
    assert payload["store"] is False
    assert result.response_id == "resp-sdk"
    assert isinstance(result.content[0], TextContent)
    assert result.content[0].text == "SDK válido"


@pytest.mark.parametrize(
    "invalid_response",
    [
        {"status": "failed", "error": {"message": "unsafe"}, "output": []},
        {"status": "completed", "error": None, "output": "invalid"},
        {
            "status": "completed",
            "error": None,
            "output": [{"type": "message", "content": "invalid"}],
        },
        {"status": "completed", "error": None, "output": [{"type": "web_search_call"}]},
    ],
)
def test_malformed_complete_responses_are_rejected(
    invalid_response: dict[str, object],
) -> None:
    with pytest.raises(ModelResponseError):
        OpenAIResponseMapper().map(invalid_response, requested_model="model")


@pytest.mark.parametrize(
    "invalid_usage",
    [
        {"input_tokens": "1", "output_tokens": 1, "total_tokens": 2},
        {"input_tokens": 1, "output_tokens": 1, "total_tokens": 3},
    ],
)
def test_invalid_usage_is_rejected(invalid_usage: dict[str, object]) -> None:
    with pytest.raises(ModelResponseError, match=r"tokens|usage"):
        OpenAIResponseMapper.map_usage(invalid_usage)


def test_unknown_usage_details_are_not_invented() -> None:
    mapped = OpenAIResponseMapper.map_usage(
        {
            "input_tokens": 1,
            "output_tokens": 2,
            "total_tokens": 3,
            "input_tokens_details": {"cached_tokens": "unknown"},
            "output_tokens_details": {"reasoning_tokens": None},
        }
    )
    assert mapped.cached_input_tokens == 0
    assert mapped.reasoning_tokens == 0


def test_provider_catalog_configuration_rejects_invalid_descriptors() -> None:
    capabilities = frozenset({ModelCapability.TEXT_GENERATION})
    openai_descriptor = ModelDescriptor(
        provider="openai", model="custom", capabilities=capabilities
    )
    with pytest.raises(ValueError, match="vazio"):
        OpenAIProviderConfig(models=())
    with pytest.raises(ValueError, match="openai"):
        OpenAIProviderConfig(
            models=(
                ModelDescriptor(
                    provider="other", model="custom", capabilities=capabilities
                ),
            )
        )
    with pytest.raises(ValueError, match="duplicados"):
        OpenAIProviderConfig(models=(openai_descriptor, openai_descriptor))


@pytest.mark.parametrize(
    "message",
    [
        ModelMessage(
            role=MessageRole.ASSISTANT,
            content=(ImageContent(uri="https://example.com/x.png"),),
        ),
        ModelMessage(
            role=MessageRole.USER,
            content=(ImageContent(uri="https://example.com/x.png", detail="huge"),),
        ),
        ModelMessage(
            role=MessageRole.TOOL,
            tool_call_id="call-1",
            content=(ImageContent(uri="https://example.com/x.png"),),
        ),
    ],
)
@pytest.mark.asyncio
async def test_role_specific_unsupported_content_is_rejected(
    message: ModelMessage,
) -> None:
    provider, _ = provider_with(response())
    with pytest.raises(ModelInvalidRequestError):
        await provider.generate(
            ModelRequest(model="gpt-6-astra", messages=(message,)), context()
        )
