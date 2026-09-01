"""Tests for the generic asynchronous agent contract."""

import inspect
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from atlas_agents import (
    Agent,
    AgentContext,
    AgentDefinition,
    AgentEvent,
    AgentEventType,
    AgentInput,
    AgentResult,
    ExecutionStatus,
    Usage,
)


class FakeAgent(Agent[AgentInput, str]):
    """Minimal typed agent implementation used only by contract tests."""

    def __init__(self) -> None:
        self._definition = AgentDefinition(
            agent_id="fake",
            name="Fake Agent",
            instructions="Echo the input.",
        )

    @property
    def definition(self) -> AgentDefinition:
        """Return the fake agent definition."""
        return self._definition

    async def run(
        self,
        input_data: AgentInput,
        context: AgentContext,
    ) -> AgentResult[str]:
        """Return the input message as a completed result."""
        return AgentResult[str](
            execution_id=context.execution_id,
            status=ExecutionStatus.COMPLETED,
            output=input_data.message,
            usage=Usage(),
        )

    async def stream(
        self,
        input_data: AgentInput,
        context: AgentContext,
    ) -> AsyncIterator[AgentEvent]:
        """Yield one creation event for the fake execution."""
        yield AgentEvent(
            event_id=f"event-{input_data.message}",
            execution_id=context.execution_id,
            sequence=0,
            event_type=AgentEventType.EXECUTION_CREATED,
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        )


async def test_fake_agent_implements_typed_run_contract() -> None:
    agent: Agent[AgentInput, str] = FakeAgent()
    context = AgentContext(execution_id="execution")

    result: AgentResult[str] = await agent.run(AgentInput(message="hello"), context)

    assert agent.definition.agent_id == "fake"
    assert result.output == "hello"


async def test_fake_agent_stream_is_an_async_generator() -> None:
    agent = FakeAgent()
    context = AgentContext(execution_id="execution")

    events = [event async for event in agent.stream(AgentInput(message="1"), context)]

    assert inspect.isasyncgenfunction(FakeAgent.stream)
    assert len(events) == 1
    assert events[0].event_type is AgentEventType.EXECUTION_CREATED
