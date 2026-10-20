"""Declarative workflow definition contracts."""

from collections.abc import Mapping
from typing import Self

from packaging.version import InvalidVersion, Version
from pydantic import Field, field_serializer, field_validator, model_validator

from atlas_agents._models import _FrozenModel, _trimmed_non_empty
from atlas_agents.orchestration.types import WorkflowNodeKind
from atlas_agents.orchestration.validation import (
    empty_json_mapping,
    freeze_json_mapping,
    thaw_json,
    validate_identifier,
    validate_symbolic_reference,
)


class WorkflowNode(_FrozenModel):
    """Describe one logical workflow node without execution behavior."""

    node_id: str
    kind: WorkflowNodeKind
    agent_ref: str | None = None
    configuration: Mapping[str, object] = Field(default_factory=empty_json_mapping)

    @field_validator("node_id")
    @classmethod
    def validate_node_id(cls, value: str) -> str:
        """Validate the node identity."""
        return validate_identifier(value, label="do nó")

    @field_validator("agent_ref")
    @classmethod
    def validate_agent_ref(cls, value: str | None) -> str | None:
        """Validate an optional symbolic agent reference."""
        return None if value is None else validate_identifier(value, label="do agente")

    @field_validator("configuration")
    @classmethod
    def validate_configuration(cls, value: object) -> Mapping[str, object]:
        """Freeze bounded JSON configuration."""
        return freeze_json_mapping(value)

    @field_serializer("configuration")
    def serialize_configuration(self, value: Mapping[str, object]) -> object:
        """Serialize immutable configuration as a JSON object."""
        return thaw_json(value)


class WorkflowEdge(_FrozenModel):
    """Declare one directed connection between workflow nodes."""

    source_node_id: str
    target_node_id: str
    condition_ref: str | None = None

    @field_validator("source_node_id", "target_node_id")
    @classmethod
    def validate_node_reference(cls, value: str) -> str:
        """Validate an edge endpoint identifier."""
        return validate_identifier(value, label="referenciado pela conexão")

    @field_validator("condition_ref")
    @classmethod
    def validate_condition_ref(cls, value: str | None) -> str | None:
        """Allow only a symbolic, non-executable condition reference."""
        return None if value is None else validate_symbolic_reference(value)


class WorkflowDefinition(_FrozenModel):
    """Represent a versioned, declarative workflow definition."""

    workflow_id: str
    version: str
    name: str
    description: str | None = None
    nodes: tuple[WorkflowNode, ...] = Field(min_length=1)
    edges: tuple[WorkflowEdge, ...] = ()
    metadata: Mapping[str, object] = Field(default_factory=empty_json_mapping)

    @field_validator("workflow_id")
    @classmethod
    def validate_workflow_id(cls, value: str) -> str:
        """Validate the stable definition identity."""
        return validate_identifier(value, label="do workflow")

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        """Require a valid PEP 440 definition version."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("A versão do workflow não pode estar vazia")
        try:
            Version(normalized)
        except InvalidVersion as exc:
            raise ValueError("A versão do workflow é inválida") from exc
        return normalized

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Require a visible workflow name."""
        return _trimmed_non_empty(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        """Reject an explicitly empty description."""
        return None if value is None else _trimmed_non_empty(value)

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
    def validate_structure(self) -> Self:
        """Reject duplicate nodes and dangling edge references only."""
        node_ids = tuple(node.node_id for node in self.nodes)
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("Os identificadores dos nós devem ser únicos")
        known = set(node_ids)
        for edge in self.edges:
            if edge.source_node_id not in known:
                raise ValueError("A origem da conexão não existe no workflow")
            if edge.target_node_id not in known:
                raise ValueError("O destino da conexão não existe no workflow")
        return self
