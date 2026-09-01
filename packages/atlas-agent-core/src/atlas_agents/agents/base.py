"""Abstract public contract implemented by Atlas agents."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from atlas_agents.agents.context import AgentContext
from atlas_agents.agents.definition import AgentDefinition
from atlas_agents.agents.result import AgentResult
from atlas_agents.events import AgentEvent


class Agent[TInput, TOutput](ABC):
    """Define provider-neutral execution methods implemented by concrete agents."""

    @property
    @abstractmethod
    def definition(self) -> AgentDefinition:
        """Return the immutable definition associated with this agent."""
        raise NotImplementedError

    @abstractmethod
    async def run(
        self,
        input_data: TInput,
        context: AgentContext,
    ) -> AgentResult[TOutput]:
        """Run the agent and return a final or suspended result snapshot."""
        raise NotImplementedError

    @abstractmethod
    def stream(
        self,
        input_data: TInput,
        context: AgentContext,
    ) -> AsyncIterator[AgentEvent]:
        """Return an asynchronous iterator of events for one execution."""
        raise NotImplementedError
