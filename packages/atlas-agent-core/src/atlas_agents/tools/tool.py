"""Executable tool contract."""

from abc import ABC, abstractmethod

from atlas_agents.tools.context import ToolExecutionContext
from atlas_agents.tools.definition import ToolDefinition
from atlas_agents.tools.result import ToolOutput


class Tool(ABC):
    """Define one explicitly constructed asynchronous tool implementation."""

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """Return the immutable definition associated with this implementation."""

    @abstractmethod
    async def execute(
        self,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolOutput:
        """Execute the known implementation with validated arguments."""
