"""Serializable workflow input and execution context contracts."""

from collections.abc import Mapping
from datetime import datetime
from typing import Self

from pydantic import Field, field_serializer, field_validator, model_validator

from atlas_agents._models import _FrozenModel, _timezone_aware
from atlas_agents.agents import ExecutionIdentity
from atlas_agents.orchestration.validation import (
    empty_json_mapping,
    freeze_json,
    freeze_json_mapping,
    thaw_json,
    validate_identifier,
)


class WorkflowInput(_FrozenModel):
    """Carry JSON input and correlation without infrastructure references."""

    correlation_id: str
    payload: object
    metadata: Mapping[str, object] = Field(default_factory=empty_json_mapping)

    @field_validator("correlation_id")
    @classmethod
    def validate_correlation_id(cls, value: str) -> str:
        """Validate the cross-boundary correlation identity."""
        return validate_identifier(value, label="de correlação")

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, value: object) -> object:
        """Freeze bounded JSON input."""
        return freeze_json(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: object) -> Mapping[str, object]:
        """Freeze bounded JSON metadata."""
        return freeze_json_mapping(value)

    @field_serializer("payload", "metadata")
    def serialize_json(self, value: object) -> object:
        """Serialize immutable containers as JSON values."""
        return thaw_json(value)


class WorkflowContext(_FrozenModel):
    """Carry trusted, serializable facts about one workflow execution."""

    workflow_execution_id: str
    workflow_id: str
    workflow_version: str
    correlation_id: str
    tenant_id: str | None = None
    identity: ExecutionIdentity | None = None
    created_at: datetime
    deadline_at: datetime | None = None
    metadata: Mapping[str, object] = Field(default_factory=empty_json_mapping)

    @field_validator(
        "workflow_execution_id", "workflow_id", "workflow_version", "correlation_id"
    )
    @classmethod
    def validate_required_id(cls, value: str) -> str:
        """Validate required workflow identities."""
        return validate_identifier(value, label="do contexto")

    @field_validator("tenant_id")
    @classmethod
    def validate_tenant_id(cls, value: str | None) -> str | None:
        """Validate an optional tenant identity without granting authority."""
        return None if value is None else validate_identifier(value, label="do tenant")

    @field_validator("created_at", "deadline_at")
    @classmethod
    def validate_timestamp(cls, value: datetime | None) -> datetime | None:
        """Require timezone-aware workflow timestamps."""
        return None if value is None else _timezone_aware(value, label="do workflow")

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: object) -> Mapping[str, object]:
        """Freeze bounded JSON metadata."""
        return freeze_json_mapping(value)

    @field_serializer("metadata")
    def serialize_metadata(self, value: Mapping[str, object]) -> object:
        """Serialize immutable metadata as a JSON object."""
        return thaw_json(value)

    @model_validator(mode="after")
    def validate_deadline(self) -> Self:
        """Reject a deadline that predates the context creation."""
        if self.deadline_at is not None and self.deadline_at < self.created_at:
            raise ValueError("O deadline não pode anteceder a criação do workflow")
        return self
