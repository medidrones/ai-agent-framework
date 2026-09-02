"""Explicit isolated registry for executable tools."""

from atlas_agents._models import _non_empty
from atlas_agents.models import ModelToolDefinition
from atlas_agents.tools.errors import DuplicateToolError, ToolNotRegisteredError
from atlas_agents.tools.tool import Tool


class ToolRegistry:
    """Store only tools and preserve their exact registration order."""

    def __init__(self) -> None:
        """Initialize registry state local to this instance."""
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool without silently replacing an existing name."""
        name = tool.definition.name
        if name in self._tools:
            raise DuplicateToolError(name)
        self._tools[name] = tool

    def unregister(self, name: str) -> Tool:
        """Remove and return a tool using exact name resolution."""
        exact_name = _non_empty(name)
        try:
            return self._tools.pop(exact_name)
        except KeyError as exc:
            raise ToolNotRegisteredError(exact_name) from exc

    def get(self, name: str) -> Tool:
        """Return a tool using exact name resolution or raise a registry error."""
        exact_name = _non_empty(name)
        try:
            return self._tools[exact_name]
        except KeyError as exc:
            raise ToolNotRegisteredError(exact_name) from exc

    def try_get(self, name: str) -> Tool | None:
        """Return a tool for an exact name, otherwise return none."""
        return self._tools.get(_non_empty(name))

    def tools(self) -> tuple[Tool, ...]:
        """Return an immutable snapshot in registration order."""
        return tuple(self._tools.values())

    def model_definitions(self) -> tuple[ModelToolDefinition, ...]:
        """Return model-facing definitions without implementations or policies."""
        return tuple(
            tool.definition.to_model_definition() for tool in self._tools.values()
        )
