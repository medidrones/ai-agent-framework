"""Explicit isolation boundaries for memory operations."""

from typing import Self

from pydantic import field_validator, model_validator

from atlas_agents._models import _FrozenModel, _non_empty


class MemoryScope(_FrozenModel):
    """Identify the exact non-global boundary of one memory operation."""

    tenant_id: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    conversation_id: str | None = None
    agent_id: str | None = None
    execution_id: str | None = None

    @field_validator(
        "tenant_id",
        "user_id",
        "session_id",
        "conversation_id",
        "agent_id",
        "execution_id",
    )
    @classmethod
    def validate_optional_id(cls, value: str | None) -> str | None:
        """Reject empty identifiers and the unsupported global wildcard."""
        if value is None:
            return None
        validated = _non_empty(value)
        if validated == "*":
            raise ValueError("O escopo de memória não aceita wildcard global")
        return validated

    @model_validator(mode="after")
    def reject_global_scope(self) -> Self:
        """Require at least one explicit isolation identifier."""
        if not any(
            (
                self.tenant_id,
                self.user_id,
                self.session_id,
                self.conversation_id,
                self.agent_id,
                self.execution_id,
            )
        ):
            raise ValueError("O escopo de memória não pode ser global")
        return self
