"""Scope and write policy extension points for runtime memory integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from atlas_agents.memory.errors import MemoryScopeResolutionError
from atlas_agents.memory.models import MemoryCandidate
from atlas_agents.memory.scope import MemoryScope
from atlas_agents.memory.types import MemoryType

if TYPE_CHECKING:
    from atlas_agents.agents import AgentContext, AgentDefinition
    from atlas_agents.runtime.snapshot import ExecutionSnapshot


class MemoryScopePolicy(Protocol):
    """Resolve one safe exact scope for a memory type and execution context."""

    def scope_for(
        self,
        *,
        memory_type: MemoryType,
        agent: AgentDefinition,
        context: AgentContext,
    ) -> MemoryScope:
        """Return the scope or raise when a safe scope is unavailable."""
        ...


class DefaultMemoryScopePolicy:
    """Resolve conservative scopes from formal execution context fields."""

    def scope_for(
        self,
        *,
        memory_type: MemoryType,
        agent: AgentDefinition,
        context: AgentContext,
    ) -> MemoryScope:
        """Isolate working, conversation, and long-term memory safely."""
        common = {"tenant_id": context.tenant_id, "agent_id": agent.agent_id}
        if memory_type is MemoryType.WORKING:
            return MemoryScope(**common, execution_id=context.execution_id)
        if memory_type is MemoryType.CONVERSATION:
            if context.session_id is None:
                raise MemoryScopeResolutionError(
                    "A memória de conversa exige session_id no contexto."
                )
            return MemoryScope(
                **common,
                user_id=context.user_id,
                session_id=context.session_id,
            )
        stable_user = context.user_id
        if stable_user is None and context.identity is not None:
            stable_user = context.identity.subject
        if stable_user is None:
            raise MemoryScopeResolutionError(
                "A memória de longo prazo exige uma identidade estável."
            )
        return MemoryScope(**common, user_id=stable_user)


class MemoryWritePolicy(Protocol):
    """Select explicit append-oriented memory candidates from successful output."""

    def select(
        self,
        *,
        agent: AgentDefinition,
        snapshot: ExecutionSnapshot,
        output: object,
    ) -> tuple[MemoryCandidate, ...]:
        """Return candidates in deterministic write order."""
        ...


class NoMemoryWritePolicy:
    """Disable automatic memory creation unless a policy is injected."""

    def select(
        self,
        *,
        agent: AgentDefinition,
        snapshot: ExecutionSnapshot,
        output: object,
    ) -> tuple[MemoryCandidate, ...]:
        """Return no candidates without inspecting execution content."""
        del agent, snapshot, output
        return ()
