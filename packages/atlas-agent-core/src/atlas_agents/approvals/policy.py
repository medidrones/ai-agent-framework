"""Local policy contracts for deciding whether tools need approval."""

from typing import TYPE_CHECKING, Protocol

from pydantic import Field, field_validator

from atlas_agents._models import _FrozenModel, _json_mapping, _non_empty
from atlas_agents.agents import ExecutionIdentity
from atlas_agents.approvals.requirement import (
    ApprovalNotRequired,
    ApprovalRequirement,
)

if TYPE_CHECKING:
    from atlas_agents.tools import ToolDefinition, ToolExecutionRequest


class ApprovalContext(_FrozenModel):
    """Provide restricted execution facts to a local approval policy."""

    execution_id: str
    agent_id: str
    tool_call_id: str
    identity: ExecutionIdentity | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("execution_id", "agent_id", "tool_call_id")
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        """Reject empty approval context identifiers."""
        return _non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep context metadata JSON-compatible and isolated."""
        return _json_mapping(value)


class ApprovalPolicy(Protocol):
    """Decide locally whether one policy-controlled tool needs approval."""

    def evaluate_tool(
        self,
        *,
        tool: "ToolDefinition",
        request: "ToolExecutionRequest",
        context: ApprovalContext,
    ) -> ApprovalRequirement:
        """Return a deterministic requirement without performing I/O."""
        ...


class NoApprovalPolicy:
    """Preserve the default behavior by never requesting human approval."""

    def evaluate_tool(
        self,
        *,
        tool: "ToolDefinition",
        request: "ToolExecutionRequest",
        context: ApprovalContext,
    ) -> ApprovalRequirement:
        """Return the explicit not-required policy outcome."""
        del tool, request, context
        return ApprovalNotRequired()
