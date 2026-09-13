"""Safe errors exposed by the Atlas MCP integration."""

from atlas_agents.exceptions import AtlasAgentError


class MCPError(AtlasAgentError):
    """Base error for normalized MCP failures."""


class MCPConfigurationError(MCPError):
    """Report invalid MCP configuration."""


class MCPTransportError(MCPError):
    """Report a transport-level failure."""


class MCPConnectionError(MCPTransportError):
    """Report a failure while opening an MCP connection."""


class MCPProtocolError(MCPError):
    """Report an invalid or failed MCP protocol exchange."""


class MCPVersionError(MCPProtocolError):
    """Report an unsupported negotiated protocol version."""


class MCPCapabilityError(MCPProtocolError):
    """Report use of a capability absent from the server."""


class MCPToolError(MCPError):
    """Report an MCP tool operation failure."""


class MCPResourceError(MCPError):
    """Report an MCP resource operation failure."""


class MCPResourceTooLargeError(MCPResourceError):
    """Report resource content larger than the configured limit."""


class MCPPromptError(MCPError):
    """Report an MCP prompt operation failure."""


class MCPMappingError(MCPError):
    """Report remote content that cannot cross the Atlas boundary."""


class MCPAuthenticationError(MCPConnectionError):
    """Report failed MCP transport authentication."""


class MCPAuthorizationError(MCPError):
    """Report authorization denied by an MCP peer."""


class MCPClientNotConnectedError(MCPError):
    """Report an operation attempted outside a connected lifecycle."""


class MCPInputRequiredUnsupportedError(MCPProtocolError):
    """Report an unconfigured MCP multi-round-trip input request."""
