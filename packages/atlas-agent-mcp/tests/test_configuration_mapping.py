from __future__ import annotations

import pytest
from pydantic import ValidationError

from atlas_agents.mcp import (
    MCP_PROTOCOL_BASELINE,
    MCPClientConfig,
    MCPEmbeddedResourceContent,
    MCPMappingError,
    MCPResourceContent,
    StdioMCPTransport,
    StdioMCPTransportConfig,
    StreamableHTTPMCPTransport,
    StreamableHTTPMCPTransportConfig,
)
from atlas_agents.mcp.mapping import map_content


def test_protocol_baseline_and_transport_configurations_are_safe() -> None:
    assert MCP_PROTOCOL_BASELINE == "2026-07-28"
    stdio = StdioMCPTransportConfig(
        command="python", args=("server.py",), environment={"TOKEN": "SECRET-MCP-TOKEN"}
    )
    http = StreamableHTTPMCPTransportConfig(
        url="https://mcp.example.test/mcp",
        headers={"Authorization": "Bearer SECRET-MCP-TOKEN"},
    )
    assert "SECRET-MCP-TOKEN" not in repr(stdio)
    assert "SECRET-MCP-TOKEN" not in repr(http)
    assert StdioMCPTransport(stdio).create_client() is not None
    assert StreamableHTTPMCPTransport(http).create_client() is not None
    assert MCPClientConfig(max_resource_bytes=10)


@pytest.mark.parametrize(
    "command", ["", "tool && danger", "tool | danger", "tool\nnext"]
)
def test_stdio_rejects_shell_command_strings(command: str) -> None:
    with pytest.raises(ValidationError):
        StdioMCPTransportConfig(command=command)


@pytest.mark.parametrize(
    "url",
    ["", "file:///tmp/mcp", "http://remote.example/mcp", "https://u:p@host/mcp"],
)
def test_http_rejects_unsafe_endpoints(url: str) -> None:
    with pytest.raises(ValidationError):
        StreamableHTTPMCPTransportConfig(url=url)


def test_mapping_rejects_unknown_sdk_content_without_raw_exception() -> None:
    with pytest.raises(MCPMappingError) as caught:
        map_content(object())
    assert caught.value.__cause__ is None


@pytest.mark.parametrize("model", [MCPResourceContent, MCPEmbeddedResourceContent])
@pytest.mark.parametrize(
    ("text", "blob"),
    [(None, None), ("texto", "YmxvYg==")],
)
def test_resource_content_requires_exactly_one_payload(
    model: type[MCPResourceContent] | type[MCPEmbeddedResourceContent],
    text: str | None,
    blob: str | None,
) -> None:
    with pytest.raises(ValidationError):
        model(uri="memory://resource", text=text, blob=blob)
