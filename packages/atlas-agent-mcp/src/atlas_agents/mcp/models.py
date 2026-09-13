"""Provider-neutral immutable MCP value objects."""

from enum import StrEnum
from typing import Annotated, Literal, Protocol, Self, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    TypeAdapter,
    field_validator,
    model_validator,
)

_JSON: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _text(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("O valor textual não pode ser vazio")
    return normalized


def _json_mapping(value: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return dict(cast("dict[str, JsonValue]", _JSON.validate_python(value)))


class MCPTransportType(StrEnum):
    """Identify supported modern MCP transports."""

    STDIO = "stdio"
    STREAMABLE_HTTP = "streamable_http"


class MCPClientState(StrEnum):
    """Represent the explicit client lifecycle."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CLOSING = "closing"
    CLOSED = "closed"


class MCPServerCapability(StrEnum):
    """Describe MCP server features relevant to Atlas."""

    TOOLS = "tools"
    RESOURCES = "resources"
    PROMPTS = "prompts"
    COMPLETIONS = "completions"


class MCPServerInfo(_FrozenModel):
    """Expose negotiated server information without SDK objects."""

    name: str | None = None
    version: str | None = None
    protocol_version: str
    capabilities: frozenset[MCPServerCapability] = frozenset()
    extensions: tuple[str, ...] = ()

    _validate_protocol = field_validator("protocol_version")(_text)


class MCPToolDescriptor(_FrozenModel):
    """Describe one remote MCP tool."""

    name: str
    description: str = "Ferramenta MCP remota."
    input_schema: dict[str, JsonValue]
    output_schema: dict[str, JsonValue] | None = None
    annotations: dict[str, JsonValue] = Field(default_factory=dict)

    _validate_name = field_validator("name")(_text)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        """Supply a useful description when the remote server omits it."""
        return value.strip() or "Ferramenta MCP remota."

    @field_validator("input_schema", "annotations")
    @classmethod
    def validate_mapping(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        """Keep mappings JSON-safe and isolated."""
        return _json_mapping(value)

    @field_validator("output_schema")
    @classmethod
    def validate_optional_mapping(
        cls, value: dict[str, JsonValue] | None
    ) -> dict[str, JsonValue] | None:
        """Keep an optional schema JSON-safe and isolated."""
        return None if value is None else _json_mapping(value)


class MCPTextContent(_FrozenModel):
    """Represent MCP text content."""

    type: Literal["text"] = "text"
    text: str


class MCPImageContent(_FrozenModel):
    """Represent MCP image content without exposing it in repr."""

    type: Literal["image"] = "image"
    data: str = Field(repr=False)
    mime_type: str

    _validate_mime = field_validator("mime_type")(_text)


class MCPEmbeddedResourceContent(_FrozenModel):
    """Represent content embedded in a tool or prompt result."""

    type: Literal["resource"] = "resource"
    uri: str
    mime_type: str | None = None
    text: str | None = None
    blob: str | None = Field(default=None, repr=False)

    _validate_uri = field_validator("uri")(_text)

    @model_validator(mode="after")
    def validate_payload(self) -> Self:
        """Require exactly one resource payload representation."""
        if (self.text is None) == (self.blob is None):
            raise ValueError("O recurso deve conter exatamente texto ou blob")
        return self


MCPContent = Annotated[
    MCPTextContent | MCPImageContent | MCPEmbeddedResourceContent,
    Field(discriminator="type"),
]


class MCPToolResult(_FrozenModel):
    """Carry a mapped remote tool outcome."""

    content: tuple[MCPContent, ...] = ()
    structured_content: JsonValue | None = None
    is_error: bool = False


class MCPResourceDescriptor(_FrozenModel):
    """Describe a static MCP resource with an opaque URI."""

    uri: str
    name: str
    description: str | None = None
    mime_type: str | None = None
    size: int | None = Field(default=None, ge=0)

    _validate_uri = field_validator("uri")(_text)
    _validate_name = field_validator("name")(_text)


class MCPResourceTemplateDescriptor(_FrozenModel):
    """Describe one MCP URI template."""

    uri_template: str
    name: str
    description: str | None = None
    mime_type: str | None = None

    _validate_uri = field_validator("uri_template")(_text)
    _validate_name = field_validator("name")(_text)


class MCPResourceContent(_FrozenModel):
    """Carry mapped resource contents."""

    uri: str
    mime_type: str | None = None
    text: str | None = None
    blob: str | None = Field(default=None, repr=False)

    _validate_uri = field_validator("uri")(_text)

    @model_validator(mode="after")
    def validate_payload(self) -> Self:
        """Require exactly one resource payload representation."""
        if (self.text is None) == (self.blob is None):
            raise ValueError("O recurso deve conter exatamente texto ou blob")
        return self


class MCPPromptArgument(_FrozenModel):
    """Describe one string argument accepted by an MCP prompt."""

    name: str
    description: str | None = None
    required: bool = False

    _validate_name = field_validator("name")(_text)


class MCPPromptDescriptor(_FrozenModel):
    """Describe one explicitly exposed MCP prompt."""

    name: str
    description: str | None = None
    arguments: tuple[MCPPromptArgument, ...] = ()

    _validate_name = field_validator("name")(_text)


class MCPPromptMessage(_FrozenModel):
    """Represent one external, non-authoritative prompt message."""

    role: Literal["user", "assistant"]
    content: MCPContent


class MCPPromptResult(_FrozenModel):
    """Carry a prompt without applying it to an Atlas agent."""

    description: str | None = None
    messages: tuple[MCPPromptMessage, ...]


class MCPResourceProvider(Protocol):
    """Supply explicitly selected resources to an Atlas MCP server."""

    async def list_resources(self) -> tuple[MCPResourceDescriptor, ...]:
        """List resources selected by the host."""
        ...

    async def list_resource_templates(
        self,
    ) -> tuple[MCPResourceTemplateDescriptor, ...]:
        """List authorized resource URI templates."""
        ...

    async def read_resource(self, uri: str) -> tuple[MCPResourceContent, ...]:
        """Read one authorized opaque URI."""
        ...


class MCPPromptProvider(Protocol):
    """Supply explicitly selected prompts to an Atlas MCP server."""

    async def list_prompts(self) -> tuple[MCPPromptDescriptor, ...]:
        """List prompts selected by the host."""
        ...

    async def get_prompt(self, name: str, arguments: dict[str, str]) -> MCPPromptResult:
        """Render one selected prompt without applying it to an agent."""
        ...
