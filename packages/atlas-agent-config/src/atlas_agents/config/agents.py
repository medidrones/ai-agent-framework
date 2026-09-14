"""Local agent registry used by declarative compositions."""

from atlas_agents.agents import AgentDefinition
from atlas_agents.config.errors import ConfigReferenceError, ConfigValidationError


class ConfiguredAgentRegistry:
    """Store configured agents without depending on transport adapters."""

    def __init__(self) -> None:
        """Initialize an empty composition-local registry."""
        self._agents: dict[str, AgentDefinition] = {}

    def register(self, agent: AgentDefinition) -> None:
        """Register one definition without allowing silent replacement."""
        if agent.agent_id in self._agents:
            raise ConfigValidationError("O agente já está registrado.")
        self._agents[agent.agent_id] = agent

    def get(self, agent_id: str) -> AgentDefinition:
        """Return one configured agent or raise a safe typed error."""
        agent = self.try_get(agent_id)
        if agent is None:
            raise ConfigReferenceError("O agente solicitado não está configurado.")
        return agent

    def try_get(self, agent_id: str) -> AgentDefinition | None:
        """Return one configured agent when present."""
        return self._agents.get(agent_id)

    def agents(self) -> tuple[AgentDefinition, ...]:
        """Return an immutable registration-order snapshot."""
        return tuple(self._agents.values())
