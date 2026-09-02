"""Safe exception hierarchy for tool registries and implementations."""

from atlas_agents._models import _json_mapping, _non_empty
from atlas_agents.exceptions import AtlasAgentError


class ToolRegistryError(AtlasAgentError):
    """Base error for local tool registry operations."""


class DuplicateToolError(ToolRegistryError):
    """Report an attempt to overwrite a registered tool."""

    def __init__(self, tool_name: str) -> None:
        """Initialize the error with the duplicate exact name."""
        self.tool_name = _non_empty(tool_name)
        super().__init__(f"A ferramenta '{tool_name}' já está registrada.")


class ToolNotRegisteredError(ToolRegistryError):
    """Report a tool name absent from one registry."""

    def __init__(self, tool_name: str) -> None:
        """Initialize the error with the missing exact name."""
        self.tool_name = _non_empty(tool_name)
        super().__init__(f"A ferramenta '{tool_name}' não está registrada.")


class ToolExecutionInvariantError(AtlasAgentError):
    """Report an inconsistency introduced by execution orchestration."""


class ToolError(AtlasAgentError):
    """Base safe error deliberately raised by a tool implementation."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "tool_error",
        retryable: bool = False,
        details: dict[str, object] | None = None,
    ) -> None:
        """Store only normalized public data suitable for an execution result."""
        self.code = _non_empty(code)
        self.retryable = retryable
        self.details = _json_mapping(details or {})
        super().__init__(_non_empty(message))


class ToolUnavailableError(ToolError):
    """Report a temporary inability to execute a known tool."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        """Initialize a retryable availability failure."""
        super().__init__(
            message,
            code="tool_unavailable",
            retryable=True,
            details=details,
        )


class ToolInvalidOperationError(ToolError):
    """Report a valid request that cannot be applied by the tool."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        """Initialize a non-retryable operation failure."""
        super().__init__(
            message,
            code="tool_invalid_operation",
            retryable=False,
            details=details,
        )
