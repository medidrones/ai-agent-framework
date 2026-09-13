from __future__ import annotations

import sys
from pathlib import Path
from typing import cast

import httpx2
import pytest
from mcp_test_support import InMemoryTransport
from starlette.applications import Starlette
from test_client_server import make_server

from atlas_agents.mcp import (
    MCPClient,
    MCPTransportType,
    StdioMCPTransport,
    StdioMCPTransportConfig,
    StreamableHTTPMCPTransport,
    StreamableHTTPMCPTransportConfig,
)


@pytest.mark.asyncio
async def test_real_stdio_subprocess_discovery_call_and_shutdown() -> None:
    fixture = Path(__file__).parent / "fixtures" / "stdio_server.py"
    transport = StdioMCPTransport(
        StdioMCPTransportConfig(command=sys.executable, args=(str(fixture),))
    )
    async with MCPClient(transport) as client:
        assert [tool.name for tool in await client.list_tools()] == ["echo"]
        result = await client.call_tool("echo", {"value": 7})
        assert result.structured_content == {"value": 7}


@pytest.mark.asyncio
async def test_streamable_http_uses_modern_sdk_transport_in_process() -> None:
    server, _ = make_server()
    app = cast("Starlette", server.create_streamable_http_app())
    async with (
        app.router.lifespan_context(app),
        httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app),
            base_url="http://127.0.0.1:8000",
        ) as http_client,
    ):
        transport = StreamableHTTPMCPTransport(
            StreamableHTTPMCPTransportConfig(url="http://127.0.0.1:8000/mcp"),
            http_client=http_client,
        )
        async with MCPClient(transport) as client:
            assert [tool.name for tool in await client.list_tools()] == ["double"]
            assert (
                await client.call_tool("double", {"value": 6})
            ).structured_content == {"result": 12}


def test_server_app_and_in_memory_transport_do_not_require_legacy_sse() -> None:
    server, _ = make_server()
    assert server.create_streamable_http_app() is not None
    assert InMemoryTransport(server).transport_type is MCPTransportType.STDIO
