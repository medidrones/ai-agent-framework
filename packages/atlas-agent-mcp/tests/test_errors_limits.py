from __future__ import annotations

from typing import Never, cast

import mcp.types as sdk
import pytest
from mcp.client import Client as SDKClient

from atlas_agents.mcp import (
    MCPAuthenticationError,
    MCPClient,
    MCPClientConfig,
    MCPClientState,
    MCPConnectionError,
    MCPEmbeddedResourceContent,
    MCPImageContent,
    MCPInputRequiredUnsupportedError,
    MCPPromptError,
    MCPProtocolError,
    MCPResourceContent,
    MCPResourceError,
    MCPResourceTooLargeError,
    MCPTextContent,
    MCPToolError,
    MCPToolResult,
    MCPTransportError,
    MCPTransportType,
)
from atlas_agents.mcp.mapping import (
    map_content,
    map_prompt_result,
    map_resource_content,
    map_tool_result,
)


class BrokenSDKClient:
    async def __aenter__(self) -> Never:
        raise OSError("SECRET-MCP-TOKEN")

    async def __aexit__(self, *args: object) -> None:
        del args


class BrokenTransport:
    @property
    def transport_type(self) -> MCPTransportType:
        return MCPTransportType.STDIO

    def create_client(self) -> SDKClient:
        return cast("SDKClient", BrokenSDKClient())


class FactoryFailureTransport(BrokenTransport):
    def create_client(self) -> SDKClient:
        raise OSError("SECRET-MCP-TOKEN")


class CloseFailureSDKClient:
    async def __aexit__(self, *args: object) -> Never:
        del args
        raise RuntimeError("SECRET-MCP-TOKEN")


class OperationFailureSDKClient:
    async def list_tools(self, **kwargs: object) -> Never:
        del kwargs
        raise RuntimeError("SECRET-MCP-TOKEN")

    async def call_tool(self, *args: object, **kwargs: object) -> Never:
        del args, kwargs
        raise RuntimeError("SECRET-MCP-TOKEN")

    async def list_resources(self, **kwargs: object) -> Never:
        del kwargs
        raise RuntimeError("SECRET-MCP-TOKEN")

    async def list_resource_templates(self, **kwargs: object) -> Never:
        del kwargs
        raise RuntimeError("SECRET-MCP-TOKEN")

    async def read_resource(self, *args: object, **kwargs: object) -> Never:
        del args, kwargs
        raise RuntimeError("SECRET-MCP-TOKEN")

    async def list_prompts(self, **kwargs: object) -> Never:
        del kwargs
        raise RuntimeError("SECRET-MCP-TOKEN")

    async def get_prompt(self, *args: object, **kwargs: object) -> Never:
        del args, kwargs
        raise RuntimeError("SECRET-MCP-TOKEN")


@pytest.mark.asyncio
@pytest.mark.parametrize("transport", [BrokenTransport(), FactoryFailureTransport()])
async def test_connection_failures_are_normalized_without_secret_or_cause(
    transport: BrokenTransport,
) -> None:
    client = MCPClient(transport)
    with pytest.raises(MCPConnectionError) as caught:
        await client.connect()
    assert "SECRET-MCP-TOKEN" not in str(caught.value)
    assert caught.value.__cause__ is None
    assert client.state is MCPClientState.DISCONNECTED


@pytest.mark.asyncio
async def test_close_failure_is_normalized_and_state_is_closed() -> None:
    client = MCPClient(BrokenTransport())
    client._state = MCPClientState.CONNECTED
    client._client = cast("SDKClient", CloseFailureSDKClient())
    with pytest.raises(MCPTransportError) as caught:
        await client.close()
    assert "SECRET-MCP-TOKEN" not in str(caught.value)
    assert caught.value.__cause__ is None
    assert client.state is MCPClientState.CLOSED


def test_error_normalizer_has_safe_auth_and_operation_categories() -> None:
    authentication_failure = type("OAuthFailure", (Exception,), {})
    assert isinstance(
        MCPClient._normalize(authentication_failure(), operation="connect"),
        MCPAuthenticationError,
    )
    assert isinstance(
        MCPClient._normalize(RuntimeError(), operation="tool"), MCPToolError
    )
    assert isinstance(
        MCPClient._normalize(RuntimeError(), operation="prompt"), MCPPromptError
    )
    assert isinstance(
        MCPClient._normalize(RuntimeError(), operation="other"), MCPProtocolError
    )


@pytest.mark.asyncio
async def test_all_operation_failures_are_normalized_without_raw_secret() -> None:
    client = MCPClient(BrokenTransport())
    client._state = MCPClientState.CONNECTED
    client._client = cast("SDKClient", OperationFailureSDKClient())
    operations = (
        (client.list_tools, MCPToolError),
        (client.list_resources, MCPResourceError),
        (client.list_resource_templates, MCPResourceError),
        (client.list_prompts, MCPPromptError),
    )
    for operation, expected in operations:
        with pytest.raises(expected) as caught:
            await operation()
        assert "SECRET-MCP-TOKEN" not in str(caught.value)
    with pytest.raises(MCPToolError):
        await client.call_tool("tool", {})
    with pytest.raises(MCPResourceError):
        await client.read_resource("x:test")
    with pytest.raises(MCPPromptError):
        await client.get_prompt("prompt")


def test_response_size_limits_are_enforced() -> None:
    client = MCPClient(BrokenTransport(), config=MCPClientConfig(max_resource_bytes=2))
    with pytest.raises(MCPResourceTooLargeError):
        client._check_resource_size((MCPResourceContent(uri="x:test", text="abc"),))

    tool_client = MCPClient(
        BrokenTransport(), config=MCPClientConfig(max_tool_result_bytes=2)
    )
    with pytest.raises(MCPToolError):
        tool_client._check_tool_size(
            MCPToolResult(content=(MCPTextContent(text="long"),))
        )


def test_all_supported_content_types_map_without_sdk_objects() -> None:
    image = map_content(sdk.ImageContent(data="AA==", mime_type="image/png"))
    assert image == MCPImageContent(data="AA==", mime_type="image/png")
    embedded_text = map_content(
        sdk.EmbeddedResource(
            resource=sdk.TextResourceContents(uri="x:text", text="value")
        )
    )
    embedded_blob = map_content(
        sdk.EmbeddedResource(
            resource=sdk.BlobResourceContents(uri="x:blob", blob="AA==")
        )
    )
    assert embedded_text == MCPEmbeddedResourceContent(uri="x:text", text="value")
    assert embedded_blob == MCPEmbeddedResourceContent(uri="x:blob", blob="AA==")
    assert (
        map_resource_content(sdk.BlobResourceContents(uri="x:blob", blob="AA==")).blob
        == "AA=="
    )


def test_input_required_results_are_rejected_without_auto_prompting() -> None:
    with pytest.raises(MCPInputRequiredUnsupportedError):
        map_tool_result(sdk.CallToolResult(content=[], result_type="input_required"))
    with pytest.raises(MCPInputRequiredUnsupportedError):
        map_prompt_result(
            sdk.GetPromptResult(messages=[], result_type="input_required")
        )
