"""Pure local permission evaluation for tools."""

from typing import Self

from pydantic import model_validator

from atlas_agents._models import _FrozenModel
from atlas_agents.tools.context import ToolExecutionContext
from atlas_agents.tools.definition import ToolDefinition


class ToolPermissionDecision(_FrozenModel):
    """Represent whether all required opaque permissions are present."""

    allowed: bool
    missing_permissions: frozenset[str] = frozenset()

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        """Prevent an allowed decision from reporting missing permissions."""
        if self.allowed and self.missing_permissions:
            msg = "Uma autorização permitida não pode ter permissões ausentes"
            raise ValueError(msg)
        if not self.allowed and not self.missing_permissions:
            msg = "Uma autorização negada deve informar permissões ausentes"
            raise ValueError(msg)
        return self


class ToolPermissionEvaluator:
    """Evaluate the default all-required permission policy without I/O."""

    def evaluate(
        self,
        *,
        definition: ToolDefinition,
        context: ToolExecutionContext,
    ) -> ToolPermissionDecision:
        """Allow only when every required permission belongs to the identity."""
        granted = (
            frozenset() if context.identity is None else context.identity.permissions
        )
        missing = definition.required_permissions - granted
        return ToolPermissionDecision(
            allowed=not missing,
            missing_permissions=missing,
        )
