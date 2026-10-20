"""Functional workflow event contracts."""

from collections.abc import Mapping
from datetime import datetime

from pydantic import Field, field_serializer, field_validator

from atlas_agents._models import _FrozenModel, _timezone_aware
from atlas_agents.orchestration.types import WorkflowEventType
from atlas_agents.orchestration.validation import (
    empty_json_mapping,
    freeze_json_mapping,
    thaw_json,
    validate_identifier,
)


class WorkflowEvent(_FrozenModel):
    """Represent a versioned functional fact from workflow execution."""

    event_id: str
    workflow_execution_id: str
    event_type: WorkflowEventType
    timestamp: datetime
    node_id: str | None = None
    correlation_id: str
    payload: Mapping[str, object] = Field(default_factory=empty_json_mapping)
    schema_version: int = Field(default=1, ge=1)

    @field_validator("event_id", "workflow_execution_id", "correlation_id")
    @classmethod
    def validate_required_id(cls, value: str) -> str:
        """Validate event identities and correlation."""
        return validate_identifier(value, label="do evento")

    @field_validator("node_id")
    @classmethod
    def validate_node_id(cls, value: str | None) -> str | None:
        """Validate an optional node identity."""
        return None if value is None else validate_identifier(value, label="do nó")

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        """Require a timezone-aware event timestamp."""
        return _timezone_aware(value, label="do evento do workflow")

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, value: object) -> Mapping[str, object]:
        """Freeze bounded JSON event payload."""
        return freeze_json_mapping(value)

    @field_serializer("payload")
    def serialize_payload(self, value: Mapping[str, object]) -> object:
        """Serialize immutable payload as a JSON object."""
        return thaw_json(value)
