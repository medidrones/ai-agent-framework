"""Map official MCP SDK objects to stable Atlas value objects."""

from __future__ import annotations

from typing import cast

from pydantic import JsonValue, TypeAdapter, ValidationError

import mcp.types as sdk
from atlas_agents.mcp.errors import (
    MCPInputRequiredUnsupportedError,
    MCPMappingError,
)
from atlas_agents.mcp.models import (
    MCPContent,
    MCPEmbeddedResourceContent,
    MCPImageContent,
    MCPPromptArgument,
    MCPPromptDescriptor,
    MCPPromptMessage,
    MCPPromptResult,
    MCPResourceContent,
    MCPResourceDescriptor,
    MCPResourceTemplateDescriptor,
    MCPServerCapability,
    MCPServerInfo,
    MCPTextContent,
    MCPToolDescriptor,
    MCPToolResult,
)

_JSON: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)


def _json(value: object) -> JsonValue:
    try:
        return _JSON.validate_python(value)
    except ValidationError:
        raise MCPMappingError(
            "O servidor MCP retornou conteúdo não serializável."
        ) from None


def map_content(value: object) -> MCPContent:
    """Map one supported SDK content block."""
    if isinstance(value, sdk.TextContent):
        return MCPTextContent(text=value.text)
    if isinstance(value, sdk.ImageContent):
        return MCPImageContent(data=value.data, mime_type=value.mime_type)
    if isinstance(value, sdk.EmbeddedResource):
        resource = value.resource
        if isinstance(resource, sdk.TextResourceContents):
            return MCPEmbeddedResourceContent(
                uri=str(resource.uri), mime_type=resource.mime_type, text=resource.text
            )
        if isinstance(resource, sdk.BlobResourceContents):
            return MCPEmbeddedResourceContent(
                uri=str(resource.uri), mime_type=resource.mime_type, blob=resource.blob
            )
    raise MCPMappingError("O servidor MCP retornou um tipo de conteúdo não suportado.")


def map_capabilities(
    capabilities: sdk.ServerCapabilities,
) -> frozenset[MCPServerCapability]:
    """Map only capabilities that have an Atlas MCP representation."""
    values: set[MCPServerCapability] = set()
    for name, capability in (
        (MCPServerCapability.TOOLS, capabilities.tools),
        (MCPServerCapability.RESOURCES, capabilities.resources),
        (MCPServerCapability.PROMPTS, capabilities.prompts),
        (MCPServerCapability.COMPLETIONS, capabilities.completions),
    ):
        if capability is not None:
            values.add(name)
    return frozenset(values)


def map_server_info(client: object) -> MCPServerInfo:
    """Map negotiated connection properties from the SDK Client."""
    capabilities = cast("sdk.ServerCapabilities", client.server_capabilities)  # type: ignore[attr-defined]
    implementation = cast("sdk.Implementation | None", client.server_info)  # type: ignore[attr-defined]
    extensions = tuple(sorted((capabilities.extensions or {}).keys()))
    return MCPServerInfo(
        name=None if implementation is None else implementation.name,
        version=None if implementation is None else implementation.version,
        protocol_version=str(client.protocol_version),  # type: ignore[attr-defined]
        capabilities=map_capabilities(capabilities),
        extensions=extensions,
    )


def map_tool(value: sdk.Tool) -> MCPToolDescriptor:
    """Map one SDK tool descriptor."""
    annotations = (
        {} if value.annotations is None else value.annotations.model_dump(mode="json")
    )
    return MCPToolDescriptor(
        name=value.name,
        description=value.description or "Ferramenta MCP remota.",
        input_schema=cast("dict[str, JsonValue]", _json(value.input_schema)),
        output_schema=(
            None
            if value.output_schema is None
            else cast("dict[str, JsonValue]", _json(value.output_schema))
        ),
        annotations=cast("dict[str, JsonValue]", _json(annotations)),
    )


def map_tool_result(value: sdk.CallToolResult) -> MCPToolResult:
    """Map a complete tool result and reject unsupported input rounds."""
    if value.result_type != "complete":
        raise MCPInputRequiredUnsupportedError(
            "A ferramenta MCP solicitou entrada adicional sem handler configurado."
        )
    return MCPToolResult(
        content=tuple(map_content(item) for item in value.content),
        structured_content=_json(value.structured_content),
        is_error=value.is_error,
    )


def map_resource(value: sdk.Resource) -> MCPResourceDescriptor:
    """Map one static resource descriptor."""
    return MCPResourceDescriptor(
        uri=str(value.uri),
        name=value.name,
        description=value.description,
        mime_type=value.mime_type,
        size=value.size,
    )


def map_resource_template(value: sdk.ResourceTemplate) -> MCPResourceTemplateDescriptor:
    """Map one resource template descriptor."""
    return MCPResourceTemplateDescriptor(
        uri_template=value.uri_template,
        name=value.name,
        description=value.description,
        mime_type=value.mime_type,
    )


def map_resource_content(value: object) -> MCPResourceContent:
    """Map text or binary resource content."""
    if isinstance(value, sdk.TextResourceContents):
        return MCPResourceContent(
            uri=str(value.uri), mime_type=value.mime_type, text=value.text
        )
    if isinstance(value, sdk.BlobResourceContents):
        return MCPResourceContent(
            uri=str(value.uri), mime_type=value.mime_type, blob=value.blob
        )
    raise MCPMappingError("O servidor MCP retornou um recurso inválido.")


def map_prompt(value: sdk.Prompt) -> MCPPromptDescriptor:
    """Map one prompt descriptor."""
    return MCPPromptDescriptor(
        name=value.name,
        description=value.description,
        arguments=tuple(
            MCPPromptArgument(
                name=argument.name,
                description=argument.description,
                required=bool(argument.required),
            )
            for argument in value.arguments or []
        ),
    )


def map_prompt_result(value: sdk.GetPromptResult) -> MCPPromptResult:
    """Map a complete prompt result without applying it."""
    if value.result_type != "complete":
        raise MCPInputRequiredUnsupportedError(
            "O prompt MCP solicitou entrada adicional sem handler configurado."
        )
    return MCPPromptResult(
        description=value.description,
        messages=tuple(
            MCPPromptMessage(role=message.role, content=map_content(message.content))
            for message in value.messages
        ),
    )
