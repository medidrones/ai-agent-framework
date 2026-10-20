"""Serializable workflow result contracts."""

from collections.abc import Mapping
from datetime import datetime
from typing import Self

from pydantic import Field, field_serializer, field_validator, model_validator

from atlas_agents._models import _FrozenModel, _timezone_aware
from atlas_agents.orchestration.types import (
    WorkflowResultKind,
    WorkflowStatus,
    is_workflow_terminal,
)
from atlas_agents.orchestration.validation import (
    empty_json_mapping,
    freeze_json,
    freeze_json_mapping,
    thaw_json,
    validate_identifier,
)


class WorkflowErrorInfo(_FrozenModel):
    """Represent a safe failure without retaining a Python exception."""

    code: str
    message: str
    retryable: bool = False
    details: Mapping[str, object] = Field(default_factory=empty_json_mapping)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        """Validate the stable failure code."""
        return validate_identifier(value, label="do erro")

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        """Require a bounded, non-empty public error message."""
        normalized = value.strip()
        if not normalized or len(normalized) > 4096:
            raise ValueError("A mensagem do erro é inválida")
        return normalized

    @field_validator("details")
    @classmethod
    def validate_details(cls, value: object) -> Mapping[str, object]:
        """Freeze safe structured error details."""
        return freeze_json_mapping(value)

    @field_serializer("details")
    def serialize_details(self, value: Mapping[str, object]) -> object:
        """Serialize immutable details as a JSON object."""
        return thaw_json(value)


class WorkflowNodeResult(_FrozenModel):
    """Represent one node execution attempt in a workflow result."""

    node_id: str
    node_execution_id: str
    attempt: int = Field(ge=1)
    status: WorkflowStatus
    agent_execution_id: str | None = None
    output: object | None = None
    error: WorkflowErrorInfo | None = None

    @field_validator("node_id", "node_execution_id")
    @classmethod
    def validate_required_id(cls, value: str) -> str:
        """Validate node and attempt identities."""
        return validate_identifier(value, label="da execução do nó")

    @field_validator("agent_execution_id")
    @classmethod
    def validate_agent_execution_id(cls, value: str | None) -> str | None:
        """Validate a distinct optional agent execution identity."""
        return (
            None
            if value is None
            else validate_identifier(value, label="da execução do agente")
        )

    @field_validator("output")
    @classmethod
    def validate_output(cls, value: object) -> object:
        """Freeze optional JSON node output."""
        return None if value is None else freeze_json(value)

    @field_serializer("output")
    def serialize_output(self, value: object) -> object:
        """Serialize immutable node output as JSON."""
        return thaw_json(value)


class WorkflowResult(_FrozenModel):
    """Represent a terminal workflow outcome or explicit state snapshot."""

    workflow_execution_id: str
    workflow_id: str
    workflow_version: str
    correlation_id: str
    status: WorkflowStatus
    result_kind: WorkflowResultKind
    output: object | None = None
    node_results: tuple[WorkflowNodeResult, ...] = ()
    error: WorkflowErrorInfo | None = None
    started_at: datetime
    completed_at: datetime | None = None
    metadata: Mapping[str, object] = Field(default_factory=empty_json_mapping)

    @field_validator(
        "workflow_execution_id", "workflow_id", "workflow_version", "correlation_id"
    )
    @classmethod
    def validate_required_id(cls, value: str) -> str:
        """Validate result identities and correlation."""
        return validate_identifier(value, label="do resultado")

    @field_validator("started_at", "completed_at")
    @classmethod
    def validate_timestamp(cls, value: datetime | None) -> datetime | None:
        """Require timezone-aware result timestamps."""
        return (
            None
            if value is None
            else _timezone_aware(value, label="do resultado do workflow")
        )

    @field_validator("output")
    @classmethod
    def validate_output(cls, value: object) -> object:
        """Freeze optional JSON output."""
        return None if value is None else freeze_json(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: object) -> Mapping[str, object]:
        """Freeze bounded result metadata."""
        return freeze_json_mapping(value)

    @field_serializer("output", "metadata")
    def serialize_json(self, value: object) -> object:
        """Serialize immutable result containers as JSON."""
        return thaw_json(value)

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        """Enforce explicit terminal versus snapshot result semantics."""
        terminal = is_workflow_terminal(self.status)
        if self.result_kind is WorkflowResultKind.TERMINAL and not terminal:
            raise ValueError("Um resultado terminal exige status terminal")
        if self.result_kind is WorkflowResultKind.SNAPSHOT and terminal:
            raise ValueError("Um snapshot não pode usar status terminal")
        if terminal and self.completed_at is None:
            raise ValueError("Um resultado terminal exige timestamp de conclusão")
        if not terminal and self.completed_at is not None:
            raise ValueError("Um snapshot não pode possuir timestamp de conclusão")
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("A conclusão não pode anteceder o início")
        if self.status is WorkflowStatus.FAILED and self.error is None:
            raise ValueError("Um workflow com falha exige erro estruturado")
        if self.status is WorkflowStatus.SUCCEEDED and self.error is not None:
            raise ValueError("Um workflow concluído não pode conter erro")
        return self
