"""Atlas facade over the official MCP Python SDK client."""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from typing import TypeVar, cast

from pydantic import BaseModel, ConfigDict, Field

import mcp.types as sdk
from atlas_agents.mcp.errors import (
    MCPAuthenticationError,
    MCPClientNotConnectedError,
    MCPConnectionError,
    MCPError,
    MCPPromptError,
    MCPProtocolError,
    MCPResourceError,
    MCPResourceTooLargeError,
    MCPToolError,
    MCPTransportError,
)
from atlas_agents.mcp.mapping import (
    map_prompt,
    map_prompt_result,
    map_resource,
    map_resource_content,
    map_resource_template,
    map_server_info,
    map_tool,
    map_tool_result,
)
from atlas_agents.mcp.models import (
    MCPClientState,
    MCPPromptDescriptor,
    MCPPromptResult,
    MCPResourceContent,
    MCPResourceDescriptor,
    MCPResourceTemplateDescriptor,
    MCPServerInfo,
    MCPToolDescriptor,
    MCPToolResult,
)
from atlas_agents.mcp.transports import MCPTransport
from mcp.client import Client as SDKClient


class MCPClientConfig(BaseModel):
    """Configure optional defensive response-size limits."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    max_resource_bytes: int | None = Field(default=None, gt=0)
    max_tool_result_bytes: int | None = Field(default=None, gt=0)
    max_prompt_characters: int | None = Field(default=None, gt=0)


_T = TypeVar("_T")


class MCPClient:
    """Manage one explicit MCP SDK client lifecycle."""

    def __init__(
        self,
        transport: MCPTransport,
        *,
        config: MCPClientConfig | None = None,
    ) -> None:
        """Initialize isolated lifecycle and response-limit state."""
        self._transport = transport
        self._config = config or MCPClientConfig()
        self._client: SDKClient | None = None
        self._state = MCPClientState.DISCONNECTED
        self._server_info: MCPServerInfo | None = None
        self._lifecycle_lock = asyncio.Lock()

    @property
    def state(self) -> MCPClientState:
        """Return the current lifecycle state."""
        return self._state

    @property
    def server_info(self) -> MCPServerInfo | None:
        """Return safe negotiated server information when connected."""
        return self._server_info

    @property
    def protocol_version(self) -> str | None:
        """Return the SDK-negotiated protocol version when connected."""
        return None if self._server_info is None else self._server_info.protocol_version

    async def __aenter__(self) -> MCPClient:
        """Connect and return this facade."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Close transport resources on context exit."""
        del exc_type, exc_value, traceback
        await self.close()

    async def connect(self) -> None:
        """Open and negotiate through the official SDK exactly once."""
        async with self._lifecycle_lock:
            if self._state is MCPClientState.CONNECTED:
                raise MCPConnectionError("O cliente MCP já está conectado.")
            if self._state in {MCPClientState.CONNECTING, MCPClientState.CLOSING}:
                raise MCPConnectionError("O cliente MCP está mudando de estado.")
            self._state = MCPClientState.CONNECTING
            client: SDKClient | None = None
            try:
                client = self._transport.create_client()
                await client.__aenter__()
                info = map_server_info(client)
            except Exception as exc:
                self._state = MCPClientState.DISCONNECTED
                if client is not None:
                    await self._discard(client)
                raise self._normalize(exc, operation="connect") from None
            self._client = client
            self._server_info = info
            self._state = MCPClientState.CONNECTED

    async def close(self) -> None:
        """Close owned transport resources; repeated calls are safe."""
        async with self._lifecycle_lock:
            if self._state in {MCPClientState.DISCONNECTED, MCPClientState.CLOSED}:
                self._state = MCPClientState.CLOSED
                return
            if self._state is not MCPClientState.CONNECTED or self._client is None:
                raise MCPTransportError(
                    "O cliente MCP não pode ser fechado neste estado."
                )
            self._state = MCPClientState.CLOSING
            client, self._client = self._client, None
            try:
                await client.__aexit__(None, None, None)
            except Exception as exc:
                self._state = MCPClientState.CLOSED
                self._server_info = None
                raise self._normalize(exc, operation="close") from None
            self._server_info = None
            self._state = MCPClientState.CLOSED

    async def list_tools(self) -> tuple[MCPToolDescriptor, ...]:
        """List and map all current remote tools without registering them."""
        client = self._connected()
        try:
            return tuple(
                map_tool(cast("sdk.Tool", item))
                for item in await self._collect(client.list_tools, "tools")
            )
        except MCPError:
            raise
        except Exception as exc:
            raise self._normalize(exc, operation="tools") from None

    async def call_tool(self, name: str, arguments: dict[str, object]) -> MCPToolResult:
        """Invoke one remote canonical tool name with object arguments."""
        client = self._connected()
        try:
            result = map_tool_result(await client.call_tool(name, arguments))
            self._check_tool_size(result)
            return result
        except MCPError:
            raise
        except Exception as exc:
            raise self._normalize(exc, operation="tool") from None

    async def list_resources(self) -> tuple[MCPResourceDescriptor, ...]:
        """List and map all current static resources."""
        client = self._connected()
        try:
            return tuple(
                map_resource(cast("sdk.Resource", item))
                for item in await self._collect(client.list_resources, "resources")
            )
        except MCPError:
            raise
        except Exception as exc:
            raise self._normalize(exc, operation="resources") from None

    async def list_resource_templates(
        self,
    ) -> tuple[MCPResourceTemplateDescriptor, ...]:
        """List and map all current resource templates."""
        client = self._connected()
        try:
            return tuple(
                map_resource_template(cast("sdk.ResourceTemplate", item))
                for item in await self._collect(
                    client.list_resource_templates, "resource_templates"
                )
            )
        except MCPError:
            raise
        except Exception as exc:
            raise self._normalize(exc, operation="resources") from None

    async def read_resource(self, uri: str) -> tuple[MCPResourceContent, ...]:
        """Read one opaque resource URI without Knowledge integration."""
        client = self._connected()
        try:
            result = await client.read_resource(uri)
            contents = tuple(map_resource_content(item) for item in result.contents)
            self._check_resource_size(contents)
            return contents
        except MCPError:
            raise
        except Exception as exc:
            raise self._normalize(exc, operation="resource") from None

    async def list_prompts(self) -> tuple[MCPPromptDescriptor, ...]:
        """List remote prompts without applying them to an agent."""
        client = self._connected()
        try:
            return tuple(
                map_prompt(cast("sdk.Prompt", item))
                for item in await self._collect(client.list_prompts, "prompts")
            )
        except MCPError:
            raise
        except Exception as exc:
            raise self._normalize(exc, operation="prompts") from None

    async def get_prompt(
        self, name: str, arguments: dict[str, str] | None = None
    ) -> MCPPromptResult:
        """Retrieve one prompt as external content only."""
        client = self._connected()
        try:
            result = map_prompt_result(await client.get_prompt(name, arguments or {}))
            if self._config.max_prompt_characters is not None:
                size = sum(
                    len(message.content.text)
                    for message in result.messages
                    if hasattr(message.content, "text")
                    and message.content.text is not None
                )
                if size > self._config.max_prompt_characters:
                    raise MCPPromptError("O prompt MCP excede o limite configurado.")
            return result
        except MCPError:
            raise
        except Exception as exc:
            raise self._normalize(exc, operation="prompt") from None

    def _connected(self) -> SDKClient:
        if self._state is not MCPClientState.CONNECTED or self._client is None:
            raise MCPClientNotConnectedError("O cliente MCP não está conectado.")
        return self._client

    async def _collect(self, method: object, attribute: str) -> list[object]:
        values: list[object] = []
        cursor: str | None = None
        while True:
            result = await method(cursor=cursor, cache_mode="refresh")  # type: ignore[operator]
            values.extend(getattr(result, attribute))
            cursor = getattr(result, "next_cursor", None)
            if cursor is None:
                return values

    def _check_resource_size(self, contents: tuple[MCPResourceContent, ...]) -> None:
        limit = self._config.max_resource_bytes
        if limit is None:
            return
        size = sum(
            len((item.text or item.blob or "").encode("utf-8")) for item in contents
        )
        if size > limit:
            raise MCPResourceTooLargeError(
                "O recurso MCP excede o limite de tamanho configurado."
            )

    def _check_tool_size(self, result: MCPToolResult) -> None:
        limit = self._config.max_tool_result_bytes
        if limit is None:
            return
        payload = result.model_dump(mode="json")
        if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > limit:
            raise MCPToolError(
                "O resultado da ferramenta MCP excede o limite configurado."
            )

    @staticmethod
    async def _discard(client: SDKClient) -> None:
        with suppress(Exception):
            await client.__aexit__(None, None, None)

    @staticmethod
    def _normalize(error: Exception, *, operation: str) -> MCPError:
        name = type(error).__name__.lower()
        if "auth" in name or "oauth" in name:
            return MCPAuthenticationError("A autenticação com o servidor MCP falhou.")
        if operation == "connect":
            return MCPConnectionError("Não foi possível conectar ao servidor MCP.")
        if operation == "close":
            return MCPTransportError("Falha ao encerrar o transporte MCP.")
        if operation in {"tool", "tools"}:
            return MCPToolError("A operação de ferramenta MCP falhou.")
        if operation in {"resource", "resources"}:
            return MCPResourceError("A operação de recurso MCP falhou.")
        if operation in {"prompt", "prompts"}:
            return MCPPromptError("A operação de prompt MCP falhou.")
        return MCPProtocolError("A comunicação MCP falhou.")
