"""Bridge remote MCP tools into the Atlas Tool Runtime."""

from __future__ import annotations

import re
from contextlib import suppress
from typing import cast

from pydantic import BaseModel, ConfigDict, field_validator

from atlas_agents.approvals import ToolApprovalMode
from atlas_agents.mcp.client import MCPClient
from atlas_agents.mcp.errors import MCPConfigurationError, MCPError
from atlas_agents.mcp.models import MCPToolDescriptor
from atlas_agents.tools import (
    Tool,
    ToolDefinition,
    ToolError,
    ToolExecutionContext,
    ToolIdempotency,
    ToolOutput,
    ToolRegistry,
)


class MCPToolNamingPolicy(BaseModel):
    """Create deterministic model-safe aliases for remote tools."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    separator: str = "__"

    @field_validator("separator")
    @classmethod
    def validate_separator(cls, value: str) -> str:
        """Require a separator accepted by common model tool schemas."""
        if not value or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise ValueError("separator deve conter apenas caracteres seguros")
        return value

    def name(self, server_alias: str, remote_name: str) -> str:
        """Return one stable local alias without changing the remote name."""
        alias = self._component(server_alias)
        name = self._component(remote_name)
        return f"{alias}{self.separator}{name}"

    @staticmethod
    def _component(value: str) -> str:
        normalized = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip()).strip("_")
        if not normalized:
            raise MCPConfigurationError("O alias MCP não produz um nome local válido.")
        return normalized


class MCPRemoteTool(Tool):
    """Execute one discovered MCP tool through the normal Atlas boundary."""

    def __init__(
        self,
        *,
        client: MCPClient,
        server_id: str,
        descriptor: MCPToolDescriptor,
        local_tool_name: str,
        required_permissions: frozenset[str] = frozenset(),
    ) -> None:
        """Create one conservative local tool snapshot."""
        self._client = client
        self.server_id = server_id
        self.remote_tool_name = descriptor.name
        self.local_tool_name = local_tool_name
        self._definition = ToolDefinition(
            name=local_tool_name,
            description=descriptor.description,
            parameters=cast("dict[str, object]", descriptor.input_schema),
            required_permissions=required_permissions,
            idempotency=ToolIdempotency.UNSPECIFIED,
            approval_mode=ToolApprovalMode.POLICY_CONTROLLED,
            metadata={
                "integration": "mcp",
                "server_id": server_id,
                "remote_tool_name": descriptor.name,
            },
        )

    @property
    def definition(self) -> ToolDefinition:
        """Return the immutable local definition."""
        return self._definition

    async def execute(
        self,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolOutput:
        """Call only the preserved remote canonical name."""
        del context
        try:
            result = await self._client.call_tool(self.remote_tool_name, arguments)
        except MCPError as exc:
            code = (
                "mcp_transport_error"
                if "Transport" in type(exc).__name__
                or "Connection" in type(exc).__name__
                else "mcp_protocol_error"
            )
            raise ToolError(
                "A ferramenta MCP remota não pôde ser executada.", code=code
            ) from None
        if result.is_error:
            raise ToolError(
                "A ferramenta MCP remota retornou uma falha controlada.",
                code="mcp_remote_tool_error",
            )
        return ToolOutput(
            content={
                "structured_content": result.structured_content,
                "content": [item.model_dump(mode="json") for item in result.content],
            }
        )


class MCPToolImporter:
    """Explicitly import an allowlisted snapshot of remote tools."""

    def __init__(
        self,
        *,
        client: MCPClient,
        registry: ToolRegistry,
        server_alias: str,
        naming_policy: MCPToolNamingPolicy | None = None,
    ) -> None:
        """Configure explicit discovery and target registry."""
        self._client = client
        self._registry = registry
        self._server_alias = server_alias
        self._naming = naming_policy or MCPToolNamingPolicy()

    async def import_tools(
        self,
        *,
        include_names: frozenset[str] = frozenset(),
        exclude_names: frozenset[str] = frozenset(),
        import_all: bool = False,
        required_permissions: frozenset[str] = frozenset(),
    ) -> tuple[MCPRemoteTool, ...]:
        """Discover, preflight and atomically register selected tools."""
        if include_names and import_all:
            raise MCPConfigurationError(
                "Use include_names ou import_all, nunca ambos simultaneamente."
            )
        descriptors = await self._client.list_tools()
        selected = tuple(
            item
            for item in descriptors
            if (import_all or item.name in include_names)
            and item.name not in exclude_names
        )
        tools = tuple(
            MCPRemoteTool(
                client=self._client,
                server_id=self._server_alias,
                descriptor=descriptor,
                local_tool_name=self._naming.name(self._server_alias, descriptor.name),
                required_permissions=required_permissions,
            )
            for descriptor in selected
        )
        names = [tool.definition.name for tool in tools]
        if len(names) != len(set(names)) or any(
            self._registry.try_get(name) is not None for name in names
        ):
            raise MCPConfigurationError(
                "A importação MCP produziria colisão no ToolRegistry."
            )
        registered: list[str] = []
        try:
            for tool in tools:
                self._registry.register(tool)
                registered.append(tool.definition.name)
        except Exception:
            for name in reversed(registered):
                with suppress(Exception):
                    self._registry.unregister(name)
            raise MCPConfigurationError(
                "A importação MCP falhou e foi revertida."
            ) from None
        return tools
