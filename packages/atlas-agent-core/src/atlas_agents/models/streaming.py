"""Structured provider-neutral model streaming events."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field, field_validator

from atlas_agents._models import (
    _FrozenModel,
    _json_mapping,
    _non_empty,
    _timezone_aware,
)


class ModelStreamEventType(StrEnum):
    """Identify the small public protocol for model streaming."""

    RESPONSE_STARTED = "response_started"
    TEXT_DELTA = "text_delta"
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_ARGUMENT_DELTA = "tool_call_argument_delta"
    TOOL_CALL_COMPLETED = "tool_call_completed"
    USAGE_UPDATED = "usage_updated"
    RESPONSE_COMPLETED = "response_completed"
    ERROR = "error"


class ModelStreamEvent(_FrozenModel):
    """Represent one ordered event in a streamed model response."""

    type: ModelStreamEventType
    sequence: int = Field(ge=1)
    response_id: str | None = None
    data: dict[str, object] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("response_id")
    @classmethod
    def validate_response_id(cls, value: str | None) -> str | None:
        """Reject an explicitly empty response identifier."""
        return None if value is None else _non_empty(value)

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        """Require an explicit timezone on stream event timestamps."""
        return _timezone_aware(value, label="do evento de streaming")

    @field_validator("data")
    @classmethod
    def validate_data(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep stream event data JSON-compatible and isolated."""
        return _json_mapping(value)
