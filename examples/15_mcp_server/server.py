"""Expose one explicitly allowlisted Atlas tool through MCP stdio."""

import asyncio
import sys
from pathlib import Path

from atlas_agents import ToolDefinition, ToolExecutor, ToolRegistry
from atlas_agents.mcp import AtlasMCPServer, MCPServerConfig

sys.path.insert(0, str(Path(__file__).parents[1]))

from _support import LocalTool


async def _run() -> None:
    registry = ToolRegistry()
    registry.register(
        LocalTool(
            ToolDefinition(
                name="calculate_tax",
                description="Calcula dez por cento de imposto.",
                parameters={
                    "type": "object",
                    "properties": {"amount": {"type": "number"}},
                    "required": ["amount"],
                    "additionalProperties": False,
                },
            ),
            lambda arguments: {"tax": float(str(arguments["amount"])) * 0.1},
        )
    )
    server = AtlasMCPServer(
        config=MCPServerConfig(
            name="atlas-tax-example",
            version="1.0.0",
            exposed_tool_names=("calculate_tax",),
        ),
        tool_registry=registry,
        tool_executor=ToolExecutor(registry=registry),
    )
    await server.run_stdio()


if __name__ == "__main__":
    asyncio.run(_run())
