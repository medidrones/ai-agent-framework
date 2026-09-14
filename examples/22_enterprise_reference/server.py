"""Local MCP fixture that simulates the enterprise order system."""

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
                name="order_status",
                description="Consulta o fixture local de pedidos.",
                parameters={
                    "type": "object",
                    "properties": {"order_id": {"type": "string"}},
                    "required": ["order_id"],
                    "additionalProperties": False,
                },
            ),
            lambda arguments: {
                "order_id": arguments["order_id"],
                "status": "delayed",
                "days_late": 3,
            },
        )
    )
    await AtlasMCPServer(
        config=MCPServerConfig(
            name="enterprise-fixture",
            version="1.0.0",
            exposed_tool_names=("order_status",),
        ),
        tool_registry=registry,
        tool_executor=ToolExecutor(registry=registry),
    ).run_stdio()


if __name__ == "__main__":
    asyncio.run(_run())
