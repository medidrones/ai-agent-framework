"""Expose explicitly selected Atlas objects through the official MCP server."""

from __future__ import annotations

import json
from typing import Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, field_validator

import mcp.types as sdk
from atlas_agents.mcp.models import (
    MCPEmbeddedResourceContent,
    MCPImageContent,
    MCPPromptMessage,
    MCPPromptProvider,
    MCPResourceContent,
    MCPResourceProvider,
    MCPTextContent,
)
from atlas_agents.tools import (
    ToolExecutionContext,
    ToolExecutionRequest,
    ToolExecutionStatus,
    ToolExecutor,
    ToolRegistry,
)
from mcp.server.lowlevel import Server as SDKServer
from mcp.server.stdio import stdio_server


class MCPServerConfig(BaseModel):
    """Configure an Atlas MCP server without business settings."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    version: str
    instructions: str | None = None
    exposed_tool_names: tuple[str, ...] = ()

    @field_validator("name", "version")
    @classmethod
    def validate_text(cls, value: str) -> str:
        """Normalize required server identity fields."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("O valor não pode ser vazio")
        return normalized

    @field_validator("exposed_tool_names")
    @classmethod
    def validate_exposed_tools(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Require a unique explicit exposure allowlist."""
        if len(value) != len(set(value)) or any(not item.strip() for item in value):
            raise ValueError("exposed_tool_names deve conter nomes únicos e válidos")
        return value


class MCPToolExecutionContextFactory(Protocol):
    """Build an authorized Atlas context without trusting MCP arguments."""

    def create(self, *, tool_name: str, tool_call_id: str) -> ToolExecutionContext:
        """Create a trusted Atlas execution context."""
        ...


class AnonymousMCPToolExecutionContextFactory:
    """Create a restricted anonymous context for explicitly exposed tools."""

    def create(self, *, tool_name: str, tool_call_id: str) -> ToolExecutionContext:
        """Create a context with no inferred execution identity."""
        del tool_name
        return ToolExecutionContext(
            execution_id=f"mcp-{uuid4()}",
            agent_id="mcp-client",
            tool_call_id=tool_call_id,
        )


class AtlasMCPServer:
    """Bridge MCP methods to Atlas registries and explicit content providers."""

    def __init__(
        self,
        *,
        config: MCPServerConfig,
        tool_registry: ToolRegistry,
        tool_executor: ToolExecutor,
        context_factory: MCPToolExecutionContextFactory | None = None,
        resource_provider: MCPResourceProvider | None = None,
        prompt_provider: MCPPromptProvider | None = None,
    ) -> None:
        """Build a fixed server surface from caller-owned dependencies."""
        self.config = config
        self._registry = tool_registry
        self._executor = tool_executor
        self._context_factory = (
            context_factory or AnonymousMCPToolExecutionContextFactory()
        )
        self._resource_provider = resource_provider
        self._prompt_provider = prompt_provider
        missing = [
            name
            for name in config.exposed_tool_names
            if tool_registry.try_get(name) is None
        ]
        if missing:
            raise ValueError("A allowlist MCP contém ferramenta não registrada.")
        self._server: SDKServer[object] = SDKServer(
            config.name,
            version=config.version,
            instructions=config.instructions,
            on_list_tools=self._list_tools,
            on_call_tool=self._call_tool,
            on_list_resources=(
                self._list_resources if resource_provider is not None else None
            ),
            on_list_resource_templates=(
                self._list_resource_templates if resource_provider is not None else None
            ),
            on_read_resource=(
                self._read_resource if resource_provider is not None else None
            ),
            on_list_prompts=(
                self._list_prompts if prompt_provider is not None else None
            ),
            on_get_prompt=(self._get_prompt if prompt_provider is not None else None),
        )

    def create_streamable_http_app(
        self,
        *,
        path: str = "/mcp",
        host: str = "127.0.0.1",
    ) -> object:
        """Create a dual-era Streamable HTTP app without starting a web server."""
        return self._server.streamable_http_app(
            streamable_http_path=path,
            host=host,
        )

    async def run_stdio(self) -> None:
        """Serve stdio through SDK-owned framing without writing diagnostics."""
        async with stdio_server() as (read_stream, write_stream):
            await self._server.run(
                read_stream,
                write_stream,
                self._server.create_initialization_options(),
            )

    async def _list_tools(
        self, context: object, params: sdk.PaginatedRequestParams | None
    ) -> sdk.ListToolsResult:
        del context, params
        tools: list[sdk.Tool] = []
        for name in self.config.exposed_tool_names:
            definition = self._registry.get(name).definition
            tools.append(
                sdk.Tool(
                    name=definition.name,
                    description=definition.description,
                    input_schema=definition.parameters,
                )
            )
        return sdk.ListToolsResult(tools=tools)

    async def _call_tool(
        self, context: object, params: sdk.CallToolRequestParams
    ) -> sdk.CallToolResult:
        del context
        if params.name not in self.config.exposed_tool_names:
            return sdk.CallToolResult(
                content=[sdk.TextContent(text="A ferramenta não está exposta.")],
                is_error=True,
            )
        call_id = f"mcp-call-{uuid4()}"
        request = ToolExecutionRequest(
            tool_call_id=call_id,
            tool_name=params.name,
            arguments=dict(params.arguments or {}),
        )
        execution_context = self._context_factory.create(
            tool_name=params.name,
            tool_call_id=call_id,
        )
        result = await self._executor.execute(request, execution_context)
        if result.status is not ToolExecutionStatus.SUCCEEDED:
            message = (
                "A ferramenta Atlas falhou."
                if result.error is None
                else result.error.message
            )
            return sdk.CallToolResult(
                content=[sdk.TextContent(text=message)],
                is_error=True,
            )
        if result.output is None:
            raise RuntimeError("Resultado Atlas bem-sucedido sem output.")
        content = result.output.content
        return sdk.CallToolResult(
            content=[
                sdk.TextContent(
                    text=(
                        content
                        if isinstance(content, str)
                        else json.dumps(content, ensure_ascii=False)
                    )
                )
            ],
            structured_content=content,
        )

    async def _list_resources(
        self, context: object, params: sdk.PaginatedRequestParams | None
    ) -> sdk.ListResourcesResult:
        del context, params
        provider = self._require_resource_provider()
        resources = await provider.list_resources()
        return sdk.ListResourcesResult(
            resources=[
                sdk.Resource(
                    uri=item.uri,
                    name=item.name,
                    description=item.description,
                    mime_type=item.mime_type,
                    size=item.size,
                )
                for item in resources
            ]
        )

    async def _list_resource_templates(
        self, context: object, params: sdk.PaginatedRequestParams | None
    ) -> sdk.ListResourceTemplatesResult:
        del context, params
        provider = self._require_resource_provider()
        templates = await provider.list_resource_templates()
        return sdk.ListResourceTemplatesResult(
            resource_templates=[
                sdk.ResourceTemplate(
                    uri_template=item.uri_template,
                    name=item.name,
                    description=item.description,
                    mime_type=item.mime_type,
                )
                for item in templates
            ]
        )

    async def _read_resource(
        self, context: object, params: sdk.ReadResourceRequestParams
    ) -> sdk.ReadResourceResult:
        del context
        provider = self._require_resource_provider()
        contents = await provider.read_resource(str(params.uri))
        return sdk.ReadResourceResult(
            contents=[self._resource_to_sdk(item) for item in contents]
        )

    async def _list_prompts(
        self, context: object, params: sdk.PaginatedRequestParams | None
    ) -> sdk.ListPromptsResult:
        del context, params
        provider = self._require_prompt_provider()
        prompts = await provider.list_prompts()
        return sdk.ListPromptsResult(
            prompts=[
                sdk.Prompt(
                    name=item.name,
                    description=item.description,
                    arguments=[
                        sdk.PromptArgument(
                            name=argument.name,
                            description=argument.description,
                            required=argument.required,
                        )
                        for argument in item.arguments
                    ],
                )
                for item in prompts
            ]
        )

    async def _get_prompt(
        self, context: object, params: sdk.GetPromptRequestParams
    ) -> sdk.GetPromptResult:
        del context
        provider = self._require_prompt_provider()
        result = await provider.get_prompt(params.name, dict(params.arguments or {}))
        return sdk.GetPromptResult(
            description=result.description,
            messages=[self._prompt_message_to_sdk(item) for item in result.messages],
        )

    @staticmethod
    def _resource_to_sdk(
        item: MCPResourceContent,
    ) -> sdk.TextResourceContents | sdk.BlobResourceContents:
        if item.text is not None:
            return sdk.TextResourceContents(
                uri=item.uri, mime_type=item.mime_type, text=item.text
            )
        return sdk.BlobResourceContents(
            uri=item.uri, mime_type=item.mime_type, blob=item.blob or ""
        )

    @staticmethod
    def _prompt_message_to_sdk(item: MCPPromptMessage) -> sdk.PromptMessage:
        content = item.content
        if isinstance(content, MCPTextContent):
            mapped: sdk.TextContent | sdk.ImageContent | sdk.EmbeddedResource = (
                sdk.TextContent(text=content.text)
            )
        elif isinstance(content, MCPImageContent):
            mapped = sdk.ImageContent(data=content.data, mime_type=content.mime_type)
        elif isinstance(content, MCPEmbeddedResourceContent):
            resource = AtlasMCPServer._resource_to_sdk(
                MCPResourceContent(
                    uri=content.uri,
                    mime_type=content.mime_type,
                    text=content.text,
                    blob=content.blob,
                )
            )
            mapped = sdk.EmbeddedResource(resource=resource)
        else:
            raise TypeError("Tipo de conteúdo MCP não suportado.")
        return sdk.PromptMessage(role=item.role, content=mapped)

    def _require_resource_provider(self) -> MCPResourceProvider:
        if self._resource_provider is None:
            raise RuntimeError("O servidor MCP não possui provider de recursos.")
        return self._resource_provider

    def _require_prompt_provider(self) -> MCPPromptProvider:
        if self._prompt_provider is None:
            raise RuntimeError("O servidor MCP não possui provider de prompts.")
        return self._prompt_provider
