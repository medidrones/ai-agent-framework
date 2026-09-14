"""Use an external MCP client to discover and call the Atlas MCP server."""

import asyncio
import sys
from pathlib import Path

from atlas_agents.mcp import MCPClient, StdioMCPTransport, StdioMCPTransportConfig


async def _run() -> None:
    server = Path(__file__).with_name("server.py")
    transport = StdioMCPTransport(
        StdioMCPTransportConfig(command=sys.executable, args=(str(server),))
    )
    async with MCPClient(transport) as client:
        tools = await client.list_tools()
        result = await client.call_tool("calculate_tax", {"amount": 100})
        print(f"Descoberta: {tools[0].name}")  # noqa: T201
        print(f"Resultado: {result.structured_content}")  # noqa: T201


if __name__ == "__main__":
    asyncio.run(_run())
