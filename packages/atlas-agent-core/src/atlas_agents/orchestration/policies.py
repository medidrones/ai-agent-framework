"""Narrow async policy contracts reserved for future orchestration engines."""

from datetime import datetime
from typing import Protocol

from pydantic import Field, field_validator

from atlas_agents._models import _FrozenModel, _trimmed_non_empty
from atlas_agents.orchestration.context import WorkflowContext
from atlas_agents.orchestration.definitions import WorkflowDefinition, WorkflowNode
from atlas_agents.orchestration.results import WorkflowNodeResult
from atlas_agents.orchestration.types import WorkflowFailureAction


class WorkflowPolicyDecision(_FrozenModel):
    """Represent an explicit allow or deny policy decision."""

    allowed: bool
    reason: str

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        """Require a safe explanatory reason."""
        return _trimmed_non_empty(value)


class WorkflowRetryDecision(_FrozenModel):
    """Represent a bounded future retry policy decision."""

    retry: bool
    delay_seconds: float = Field(default=0, ge=0)
    reason: str

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        """Require a safe explanatory reason."""
        return _trimmed_non_empty(value)


class WorkflowRoutingPolicy(Protocol):
    """Select symbolic next nodes from completed node identities."""

    async def select_next_nodes(
        self,
        definition: WorkflowDefinition,
        context: WorkflowContext,
        completed_node_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        """Return candidate node identities without scheduling them."""
        ...


class WorkflowConcurrencyPolicy(Protocol):
    """Resolve a future maximum number of concurrent nodes."""

    async def max_parallel_nodes(
        self, definition: WorkflowDefinition, context: WorkflowContext
    ) -> int:
        """Return a positive implementation-defined concurrency limit."""
        ...


class WorkflowFailurePolicy(Protocol):
    """Choose the future high-level response to a node failure."""

    async def on_node_failure(
        self, result: WorkflowNodeResult, context: WorkflowContext
    ) -> WorkflowFailureAction:
        """Return an action without executing it."""
        ...


class WorkflowRetryPolicy(Protocol):
    """Decide whether a failed node attempt may be retried."""

    async def evaluate_retry(
        self, result: WorkflowNodeResult, context: WorkflowContext
    ) -> WorkflowRetryDecision:
        """Return a retry decision without scheduling the retry."""
        ...


class WorkflowDeadlinePolicy(Protocol):
    """Resolve an optional deadline for a future execution."""

    async def resolve_deadline(self, context: WorkflowContext) -> datetime | None:
        """Return a timezone-aware deadline or no deadline."""
        ...


class WorkflowBudgetPolicy(Protocol):
    """Authorize one node against an implementation-defined budget."""

    async def authorize_node(
        self, node: WorkflowNode, context: WorkflowContext
    ) -> WorkflowPolicyDecision:
        """Return a budget decision without executing the node."""
        ...


class WorkflowAuthorizationPolicy(Protocol):
    """Authorize one node using trusted execution context."""

    async def authorize_node(
        self, node: WorkflowNode, context: WorkflowContext
    ) -> WorkflowPolicyDecision:
        """Return an authorization decision; implementations should fail closed."""
        ...
