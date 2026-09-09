"""Pure extension point for deriving retrieval queries from agent input."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from atlas_agents.knowledge.errors import KnowledgeContextError
from atlas_agents.knowledge.query import KnowledgeQuery

if TYPE_CHECKING:
    from atlas_agents.agents import AgentContext, AgentDefinition, AgentInput


class KnowledgeQueryBuilder(Protocol):
    """Build one provider-neutral query without external I/O."""

    def build(
        self,
        *,
        agent: AgentDefinition,
        input_data: AgentInput,
        context: AgentContext,
    ) -> KnowledgeQuery:
        """Derive a query constrained by the agent configuration."""
        ...


class DefaultKnowledgeQueryBuilder:
    """Use the current user message and exact agent source allowlist."""

    def build(
        self,
        *,
        agent: AgentDefinition,
        input_data: AgentInput,
        context: AgentContext,
    ) -> KnowledgeQuery:
        """Build a deterministic query without rewriting or history expansion."""
        del context
        config = agent.knowledge
        if config is None or not config.enabled:
            raise KnowledgeContextError(
                "O agente não possui fontes de conhecimento habilitadas."
            )
        return KnowledgeQuery(
            text=input_data.message,
            source_ids=config.source_ids,
            limit=config.max_results,
        )
