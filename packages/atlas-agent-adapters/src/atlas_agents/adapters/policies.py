"""Identity, authorization, and execution policy boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from atlas_agents.adapters.errors import IdentityMappingError
from atlas_agents.adapters.models import (
    RequestedExecutionBudget,
    RequestedExecutionLimits,
    TransportPrincipal,
)
from atlas_agents.agents import AgentDefinition, ExecutionIdentity
from atlas_agents.runtime import ExecutionBudget, ExecutionLimits


class ExecutionIdentityMapper(Protocol):
    """Map only a trusted transport principal to an Atlas identity."""

    def map(self, principal: TransportPrincipal) -> ExecutionIdentity:
        """Return an identity without inspecting request payload fields."""
        ...


class SubjectExecutionIdentityMapper:
    """Map only verified subject and tenant, never generic claims or roles."""

    def map(self, principal: TransportPrincipal) -> ExecutionIdentity:
        """Create a least-privilege identity from trusted principal fields."""
        if not principal.subject:
            raise IdentityMappingError("A identidade autenticada é inválida.")
        attributes: dict[str, object] = {}
        if principal.tenant is not None:
            attributes["tenant"] = principal.tenant
        return ExecutionIdentity(subject=principal.subject, attributes=attributes)


class AgentOperation(StrEnum):
    """Identify external operations subject to agent authorization."""

    EXECUTE = "execute"
    RESUME = "resume"


class AgentAccessPolicy(Protocol):
    """Authorize a resolved identity before any runtime invocation."""

    async def authorize(
        self,
        *,
        agent_id: str,
        identity: ExecutionIdentity,
        operation: AgentOperation,
    ) -> bool:
        """Return whether the identity may perform the operation."""
        ...


class AllowAllAgentAccessPolicy:
    """Explicitly authorize all resolved identities for trusted deployments."""

    async def authorize(
        self,
        *,
        agent_id: str,
        identity: ExecutionIdentity,
        operation: AgentOperation,
    ) -> bool:
        """Authorize only because the host selected this policy explicitly."""
        del agent_id, identity, operation
        return True


@dataclass(frozen=True, slots=True)
class EffectiveExecutionPolicy:
    """Carry server-bounded policies passed to the core runtime."""

    limits: ExecutionLimits | None
    budget: ExecutionBudget | None


class ExecutionPolicyResolver(Protocol):
    """Constrain caller requests with server-owned maximums."""

    def resolve(
        self,
        *,
        agent: AgentDefinition,
        identity: ExecutionIdentity,
        requested_limits: RequestedExecutionLimits | None,
        requested_budget: RequestedExecutionBudget | None,
    ) -> EffectiveExecutionPolicy:
        """Return effective policies that cannot exceed server policy."""
        ...


def _minimum_int(requested: int | None, maximum: int | None) -> int | None:
    if requested is None:
        return maximum
    if maximum is None:
        return requested
    return min(requested, maximum)


def _minimum_float(requested: float | None, maximum: float | None) -> float | None:
    if requested is None:
        return maximum
    if maximum is None:
        return requested
    return min(requested, maximum)


class BoundedExecutionPolicyResolver:
    """Clamp every requested field to explicit server maximums."""

    def __init__(
        self,
        *,
        maximum_limits: ExecutionLimits,
        maximum_budget: ExecutionBudget | None = None,
    ) -> None:
        """Store immutable server-owned policy ceilings."""
        self._maximum_limits = maximum_limits
        self._maximum_budget = maximum_budget

    def resolve(
        self,
        *,
        agent: AgentDefinition,
        identity: ExecutionIdentity,
        requested_limits: RequestedExecutionLimits | None,
        requested_budget: RequestedExecutionBudget | None,
    ) -> EffectiveExecutionPolicy:
        """Clamp requested limits and cost without widening agent capabilities."""
        del agent, identity
        requested = requested_limits or RequestedExecutionLimits()
        maximum = self._maximum_limits
        limits = ExecutionLimits(
            max_turns=_minimum_int(requested.max_turns, maximum.max_turns),
            max_tool_calls=_minimum_int(
                requested.max_tool_calls, maximum.max_tool_calls
            ),
            max_input_tokens=_minimum_int(
                requested.max_input_tokens, maximum.max_input_tokens
            ),
            max_output_tokens=_minimum_int(
                requested.max_output_tokens, maximum.max_output_tokens
            ),
            max_total_tokens=_minimum_int(
                requested.max_total_tokens, maximum.max_total_tokens
            ),
            timeout_seconds=_minimum_float(
                requested.timeout_seconds, maximum.timeout_seconds
            ),
        )
        budget = self._resolve_budget(requested_budget)
        return EffectiveExecutionPolicy(limits=limits, budget=budget)

    def _resolve_budget(
        self, requested: RequestedExecutionBudget | None
    ) -> ExecutionBudget | None:
        maximum = self._maximum_budget
        if maximum is None:
            return None
        requested_cost = None if requested is None else requested.max_estimated_cost
        maximum_cost = maximum.max_estimated_cost
        cost: Decimal | None
        if requested_cost is None:
            cost = maximum_cost
        elif maximum_cost is None:
            cost = requested_cost
        else:
            cost = min(requested_cost, maximum_cost)
        currency = maximum.currency
        if requested is not None and requested.currency not in {None, currency}:
            cost = maximum_cost
        return ExecutionBudget(max_estimated_cost=cost, currency=currency)
