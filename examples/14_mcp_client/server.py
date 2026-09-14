"""Local stdio MCP server used by the client example."""

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
                name="double",
                description="Duplica um inteiro localmente.",
                parameters={
                    "type": "object",
                    "properties": {"value": {"type": "integer"}},
                    "required": ["value"],
                    "additionalProperties": False,
                },
            ),
            lambda arguments: {"result": int(str(arguments["value"])) * 2},
        )
    )
    server = AtlasMCPServer(
        config=MCPServerConfig(
            name="atlas-example-mcp",
            version="1.0.0",
            exposed_tool_names=("double",),
        ),
        tool_registry=registry,
        tool_executor=ToolExecutor(registry=registry),
    )
    await server.run_stdio()


if __name__ == "__main__":
    asyncio.run(_run())
