"""Import one allowlisted remote MCP tool into the Atlas runtime."""

import asyncio
import sys
from pathlib import Path

from atlas_agents import ToolRegistry
from atlas_agents.mcp import (
    MCPClient,
    MCPToolImporter,
    StdioMCPTransport,
    StdioMCPTransportConfig,
)

sys.path.insert(0, str(Path(__file__).parents[1]))

from _support import (
    ScriptedModelProvider,
    agent,
    build_runtime,
    input_and_context,
    text_response,
    tool_response,
)


async def _run() -> None:
    server = Path(__file__).with_name("server.py")
    transport = StdioMCPTransport(
        StdioMCPTransportConfig(command=sys.executable, args=(str(server),))
    )
    async with MCPClient(transport) as client:
        registry = ToolRegistry()
        imported = await MCPToolImporter(
            client=client,
            registry=registry,
            server_alias="local",
        ).import_tools(include_names=frozenset({"double"}))
        provider = ScriptedModelProvider(
            (
                tool_response("local__double", {"value": 5}),
                text_response("O dobro de 5 é 10."),
            )
        )
        runtime = build_runtime(provider, tools=imported)
        input_data, context = input_and_context("Qual é o dobro de 5?")
        result = await runtime.run(
            agent=agent(tools=("local__double",)),
            input_data=input_data,
            context=context,
        )
        print(f"Ferramenta importada: {imported[0].definition.name}")  # noqa: T201
        print(result.output)  # noqa: T201


if __name__ == "__main__":
    asyncio.run(_run())
