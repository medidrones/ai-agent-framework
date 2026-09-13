"""Explicit local registry for immutable agent definitions."""

from atlas_agents.adapters.errors import AgentNotRegisteredError, DuplicateAgentError
from atlas_agents.agents import AgentDefinition


class AgentRegistry:
    """Resolve agent IDs deterministically without global mutable state."""

    def __init__(self) -> None:
        """Initialize an empty caller-owned registry."""
        self._agents: dict[str, AgentDefinition] = {}

    def register(self, agent: AgentDefinition) -> None:
        """Register one agent and reject silent replacement."""
        if agent.agent_id in self._agents:
            raise DuplicateAgentError("O agente já está registrado.")
        self._agents[agent.agent_id] = agent

    def get(self, agent_id: str) -> AgentDefinition:
        """Return one exact agent or a safe typed error."""
        agent = self.try_get(agent_id)
        if agent is None:
            raise AgentNotRegisteredError("O agente solicitado não está disponível.")
        return agent

    def try_get(self, agent_id: str) -> AgentDefinition | None:
        """Return one agent when present without raising."""
        return self._agents.get(agent_id)

    def unregister(self, agent_id: str) -> AgentDefinition:
        """Remove and return one registered agent."""
        agent = self.get(agent_id)
        del self._agents[agent_id]
        return agent

    def agents(self) -> tuple[AgentDefinition, ...]:
        """Return an immutable snapshot in registration order."""
        return tuple(self._agents.values())
