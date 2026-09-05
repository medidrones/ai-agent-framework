"""Discriminated approval policy outcomes."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, field_validator

from atlas_agents._models import (
    _FrozenModel,
    _json_mapping,
    _non_empty,
    _timezone_aware,
)


class ApprovalNotRequired(_FrozenModel):
    """Signal that a policy permits execution without human approval."""

    type: Literal["not_required"] = "not_required"


class ApprovalRequired(_FrozenModel):
    """Describe why a tool call must be approved before execution."""

    type: Literal["required"] = "required"
    reason: str
    summary: str
    expires_at: datetime | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("reason", "summary")
    @classmethod
    def validate_descriptions(cls, value: str) -> str:
        """Reject empty approval descriptions."""
        return _non_empty(value)

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at(cls, value: datetime | None) -> datetime | None:
        """Require a timezone-aware expiration when provided."""
        if value is None:
            return None
        return _timezone_aware(value, label="da exigência de aprovação")

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep requirement metadata JSON-compatible and isolated."""
        return _json_mapping(value)


ApprovalRequirement = Annotated[
    ApprovalNotRequired | ApprovalRequired,
    Field(discriminator="type"),
]
