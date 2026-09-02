"""Reusable test doubles for tool execution."""

import asyncio
from collections.abc import Callable

from atlas_agents import Tool, ToolDefinition, ToolExecutionContext, ToolOutput


class FakeTool(Tool):
    def __init__(
        self,
        definition: ToolDefinition,
        *,
        output: ToolOutput | None = None,
        exception: Exception | None = None,
        wait_event: asyncio.Event | None = None,
        dependency: Callable[[dict[str, object]], object] | None = None,
    ) -> None:
        self._definition = definition
        self.output = output or ToolOutput(content={"ok": True})
        self.exception = exception
        self.wait_event = wait_event
        self.dependency = dependency
        self.call_count = 0
        self.calls: list[tuple[dict[str, object], ToolExecutionContext]] = []

    @property
    def definition(self) -> ToolDefinition:
        return self._definition

    async def execute(
        self,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolOutput:
        self.call_count += 1
        self.calls.append((arguments, context))
        if self.wait_event is not None:
            await self.wait_event.wait()
        if self.exception is not None:
            raise self.exception
        if self.dependency is not None:
            return ToolOutput(content=self.dependency(arguments))
        return self.output


def tool_definition(
    *,
    name: str = "get_customer",
    permissions: frozenset[str] = frozenset(),
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description="Consulta um cliente pelo identificador.",
        parameters={
            "type": "object",
            "properties": {"customer_id": {"type": "string"}},
            "required": ["customer_id"],
            "additionalProperties": False,
        },
        required_permissions=permissions,
    )
