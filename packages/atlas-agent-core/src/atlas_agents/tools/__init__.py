"""Provider-neutral contracts and secure execution boundary for tools."""

from atlas_agents.tools.context import ToolExecutionContext
from atlas_agents.tools.definition import ToolDefinition
from atlas_agents.tools.errors import (
    DuplicateToolError,
    ToolError,
    ToolExecutionInvariantError,
    ToolInvalidOperationError,
    ToolNotRegisteredError,
    ToolRegistryError,
    ToolUnavailableError,
)
from atlas_agents.tools.executor import ToolExecutor
from atlas_agents.tools.idempotency import ToolIdempotency
from atlas_agents.tools.permissions import (
    ToolPermissionDecision,
    ToolPermissionEvaluator,
)
from atlas_agents.tools.registry import ToolRegistry
from atlas_agents.tools.request import ToolExecutionRequest
from atlas_agents.tools.result import (
    ToolExecutionError,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolOutput,
)
from atlas_agents.tools.tool import Tool
from atlas_agents.tools.validation import (
    JsonSchemaToolArgumentValidator,
    ToolArgumentValidationIssue,
    ToolArgumentValidationResult,
    ToolArgumentValidator,
)

__all__ = [
    "DuplicateToolError",
    "JsonSchemaToolArgumentValidator",
    "Tool",
    "ToolArgumentValidationIssue",
    "ToolArgumentValidationResult",
    "ToolArgumentValidator",
    "ToolDefinition",
    "ToolError",
    "ToolExecutionContext",
    "ToolExecutionError",
    "ToolExecutionInvariantError",
    "ToolExecutionRequest",
    "ToolExecutionResult",
    "ToolExecutionStatus",
    "ToolExecutor",
    "ToolIdempotency",
    "ToolInvalidOperationError",
    "ToolNotRegisteredError",
    "ToolOutput",
    "ToolPermissionDecision",
    "ToolPermissionEvaluator",
    "ToolRegistry",
    "ToolRegistryError",
    "ToolUnavailableError",
]
