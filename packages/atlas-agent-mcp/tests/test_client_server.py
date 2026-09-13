from __future__ import annotations

from typing import cast

import pytest
from mcp_test_support import FunctionTool, InMemoryTransport

from atlas_agents.mcp import (
    AtlasMCPServer,
    MCPClient,
    MCPClientNotConnectedError,
    MCPClientState,
    MCPPromptArgument,
    MCPPromptDescriptor,
    MCPPromptMessage,
    MCPPromptResult,
    MCPResourceContent,
    MCPResourceDescriptor,
    MCPResourceTemplateDescriptor,
    MCPServerCapability,
    MCPServerConfig,
    MCPTextContent,
)
from atlas_agents.tools import ToolError, ToolExecutor, ToolRegistry


class ContentProvider:
    async def list_resources(self) -> tuple[MCPResourceDescriptor, ...]:
        return (
            MCPResourceDescriptor(
                uri="atlas://manual", name="manual", mime_type="text/plain"
            ),
        )

    async def list_resource_templates(
        self,
    ) -> tuple[MCPResourceTemplateDescriptor, ...]:
        return (
            MCPResourceTemplateDescriptor(
                uri_template="atlas://users/{id}", name="user"
            ),
        )

    async def read_resource(self, uri: str) -> tuple[MCPResourceContent, ...]:
        return (MCPResourceContent(uri=uri, text="conteúdo"),)

    async def list_prompts(self) -> tuple[MCPPromptDescriptor, ...]:
        return (
            MCPPromptDescriptor(
                name="review",
                arguments=(MCPPromptArgument(name="topic", required=True),),
            ),
        )

    async def get_prompt(self, name: str, arguments: dict[str, str]) -> MCPPromptResult:
        return MCPPromptResult(
            description=name,
            messages=(
                MCPPromptMessage(
                    role="user",
                    content=MCPTextContent(text=f"Revise {arguments['topic']}"),
                ),
            ),
        )


def make_server(
    *, expose: tuple[str, ...] = ("double",)
) -> tuple[AtlasMCPServer, FunctionTool]:
    registry = ToolRegistry()
    tool = FunctionTool(
        "double", lambda arguments: {"result": cast("int", arguments["value"]) * 2}
    )
    registry.register(tool)
    content = ContentProvider()
    return (
        AtlasMCPServer(
            config=MCPServerConfig(
                name="atlas-test", version="1.0.0", exposed_tool_names=expose
            ),
            tool_registry=registry,
            tool_executor=ToolExecutor(registry=registry),
            resource_provider=content,
            prompt_provider=content,
        ),
        tool,
    )


@pytest.mark.asyncio
async def test_client_lifecycle_negotiation_and_all_protocol_objects() -> None:
    server, tool = make_server()
    client = MCPClient(InMemoryTransport(server))
    with pytest.raises(MCPClientNotConnectedError):
        await client.list_tools()

    async with client:
        assert client.state is MCPClientState.CONNECTED
        assert client.protocol_version is not None
        assert client.server_info is not None
        assert MCPServerCapability.TOOLS in client.server_info.capabilities
        assert [item.name for item in await client.list_tools()] == ["double"]
        result = await client.call_tool("double", {"value": 4})
        assert result.is_error is False
        assert result.structured_content == {"result": 8}
        assert tool.calls == 1
        assert tool.contexts[0].identity is None

        assert (await client.list_resources())[0].uri == "atlas://manual"
        assert (await client.list_resource_templates())[
            0
        ].uri_template == "atlas://users/{id}"
        assert (await client.read_resource("custom://opaque"))[0].text == "conteúdo"
        assert (await client.list_prompts())[0].name == "review"
        prompt = await client.get_prompt("review", {"topic": "MCP"})
        assert prompt.messages[0].content == MCPTextContent(text="Revise MCP")

    assert client.state.value == "closed"
    assert client.server_info is None
    await client.close()


@pytest.mark.asyncio
async def test_empty_server_allowlist_exposes_no_tools() -> None:
    server, tool = make_server(expose=())
    async with MCPClient(InMemoryTransport(server)) as client:
        assert await client.list_tools() == ()
        result = await client.call_tool("double", {"value": 2})
        assert result.is_error is True
    assert tool.calls == 0


def raise_controlled(arguments: dict[str, object]) -> object:
    del arguments
    raise ToolError("Falha segura.", code="fixture_error")


@pytest.mark.asyncio
async def test_server_maps_controlled_tool_error_and_string_output() -> None:
    registry = ToolRegistry()
    registry.register(FunctionTool("failure", raise_controlled))
    registry.register(FunctionTool("text", lambda arguments: str(arguments["value"])))
    server = AtlasMCPServer(
        config=MCPServerConfig(
            name="errors",
            version="1.0",
            exposed_tool_names=("failure", "text"),
        ),
        tool_registry=registry,
        tool_executor=ToolExecutor(registry=registry),
    )
    async with MCPClient(InMemoryTransport(server)) as client:
        assert (await client.call_tool("failure", {"value": 1})).is_error is True
        text = await client.call_tool("text", {"value": 1})
        assert text.structured_content == "1"


@pytest.mark.asyncio
async def test_double_connect_is_rejected() -> None:
    server, _ = make_server()
    client = MCPClient(InMemoryTransport(server))
    await client.connect()
    with pytest.raises(Exception, match="já está conectado"):
        await client.connect()
    await client.close()
