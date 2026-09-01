"""Structured, provider-neutral error information returned by agents."""

from pydantic import Field, field_validator

from atlas_agents._models import _FrozenModel, _json_mapping, _non_empty


class AgentErrorInfo(_FrozenModel):
    """Expose safe error details without leaking concrete exceptions or traces."""

    code: str
    message: str
    retryable: bool = False
    details: dict[str, object] = Field(default_factory=dict)

    @field_validator("code", "message")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        """Reject empty machine and human error descriptions."""
        return _non_empty(value)

    @field_validator("details")
    @classmethod
    def validate_details(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep error details serializable and isolated from caller mutation."""
        return _json_mapping(value)
