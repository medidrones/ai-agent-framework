from __future__ import annotations

from collections.abc import Callable

from mcp.client import Client as SDKClient

from atlas_agents.mcp import AtlasMCPServer, MCPTransportType
from atlas_agents.tools import Tool, ToolDefinition, ToolExecutionContext, ToolOutput


class InMemoryTransport:
    def __init__(self, server: AtlasMCPServer) -> None:
        self._server = server

    @property
    def transport_type(self) -> MCPTransportType:
        return MCPTransportType.STDIO

    def create_client(self) -> SDKClient:
        return SDKClient(self._server._server)


class FunctionTool(Tool):
    def __init__(
        self,
        name: str,
        handler: Callable[[dict[str, object]], object],
        *,
        required_permissions: frozenset[str] = frozenset(),
    ) -> None:
        self._definition = ToolDefinition(
            name=name,
            description=f"Ferramenta {name}.",
            parameters={
                "type": "object",
                "properties": {"value": {"type": "integer"}},
                "required": ["value"],
                "additionalProperties": False,
            },
            required_permissions=required_permissions,
        )
        self._handler = handler
        self.calls = 0
        self.contexts: list[ToolExecutionContext] = []

    @property
    def definition(self) -> ToolDefinition:
        return self._definition

    async def execute(
        self,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolOutput:
        self.calls += 1
        self.contexts.append(context)
        return ToolOutput(content=self._handler(arguments))
