"""Strongly typed plugin contribution declarations."""

from dataclasses import dataclass
from typing import Protocol

from pydantic import Field, JsonValue, field_validator

from atlas_agents.guardrails import Guardrail
from atlas_agents.knowledge import KnowledgeRetriever
from atlas_agents.memory import MemoryStore
from atlas_agents.models import ModelProvider
from atlas_agents.observability import MetricsRecorder, Tracer
from atlas_agents.plugins._models import FrozenPluginModel, json_mapping, non_empty
from atlas_agents.plugins.manifest import PluginCapability
from atlas_agents.tools import Tool


class EvaluatorExtension(Protocol):
    """Expose the stable identity needed by an evaluator registry."""

    @property
    def evaluator_id(self) -> str:
        """Return the stable evaluator identifier."""
        ...


class PluginContributionDescriptor(FrozenPluginModel):
    """Describe one contribution without exposing its implementation object."""

    capability: PluginCapability
    identifier: str
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("identifier")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        """Reject blank contribution identifiers."""
        return non_empty(value, field_name="identifier")

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        """Keep descriptor metadata JSON-safe and isolated."""
        return json_mapping(value)

    @property
    def identity(self) -> tuple[PluginCapability, str]:
        """Return the canonical descriptor identity."""
        return (self.capability, self.identifier)


class PluginContribution(Protocol):
    """Represent a typed contribution with a stable descriptor identity."""

    @property
    def capability(self) -> PluginCapability:
        """Return the contribution category."""
        ...

    @property
    def identifier(self) -> str:
        """Return the category-local stable identifier."""
        ...


@dataclass(frozen=True, slots=True)
class ModelProviderContribution:
    """Contribute one model provider."""

    provider: ModelProvider

    @property
    def capability(self) -> PluginCapability:
        """Return the model-provider category."""
        return PluginCapability.MODEL_PROVIDER

    @property
    def identifier(self) -> str:
        """Return the provider name."""
        return self.provider.provider_name


@dataclass(frozen=True, slots=True)
class ToolContribution:
    """Contribute one executable tool."""

    tool: Tool

    @property
    def capability(self) -> PluginCapability:
        """Return the tool category."""
        return PluginCapability.TOOL

    @property
    def identifier(self) -> str:
        """Return the tool definition name."""
        return self.tool.definition.name


@dataclass(frozen=True, slots=True)
class MemoryStoreContribution:
    """Expose a named memory store for explicit host composition."""

    store_id: str
    store: MemoryStore

    def __post_init__(self) -> None:
        """Normalize the host-facing store identifier."""
        object.__setattr__(
            self, "store_id", non_empty(self.store_id, field_name="store_id")
        )

    @property
    def capability(self) -> PluginCapability:
        """Return the memory-store category."""
        return PluginCapability.MEMORY_STORE

    @property
    def identifier(self) -> str:
        """Return the store identifier."""
        return self.store_id


@dataclass(frozen=True, slots=True)
class KnowledgeRetrieverContribution:
    """Expose a named retriever for explicit host composition."""

    retriever_id: str
    retriever: KnowledgeRetriever

    def __post_init__(self) -> None:
        """Normalize the host-facing retriever identifier."""
        object.__setattr__(
            self,
            "retriever_id",
            non_empty(self.retriever_id, field_name="retriever_id"),
        )

    @property
    def capability(self) -> PluginCapability:
        """Return the knowledge-retriever category."""
        return PluginCapability.KNOWLEDGE_RETRIEVER

    @property
    def identifier(self) -> str:
        """Return the retriever identifier."""
        return self.retriever_id


@dataclass(frozen=True, slots=True)
class GuardrailContribution:
    """Contribute one guardrail implementation."""

    guardrail: Guardrail[object]

    @property
    def capability(self) -> PluginCapability:
        """Return the guardrail category."""
        return PluginCapability.GUARDRAIL

    @property
    def identifier(self) -> str:
        """Return the guardrail identifier."""
        return self.guardrail.guardrail_id


@dataclass(frozen=True, slots=True)
class EvaluatorContribution:
    """Contribute one evaluator without coupling core to its distribution."""

    evaluator: EvaluatorExtension

    @property
    def capability(self) -> PluginCapability:
        """Return the evaluator category."""
        return PluginCapability.EVALUATOR

    @property
    def identifier(self) -> str:
        """Return the evaluator identifier."""
        return self.evaluator.evaluator_id


@dataclass(frozen=True, slots=True)
class ObservabilityContribution:
    """Expose tracing and/or metrics adapters for explicit host composition."""

    contribution_id: str
    tracer: Tracer | None = None
    metrics: MetricsRecorder | None = None

    def __post_init__(self) -> None:
        """Validate the identifier and require at least one adapter."""
        object.__setattr__(
            self,
            "contribution_id",
            non_empty(self.contribution_id, field_name="contribution_id"),
        )
        if self.tracer is None and self.metrics is None:
            raise ValueError(
                "A contribuição de observabilidade deve informar um adapter"
            )

    @property
    def capability(self) -> PluginCapability:
        """Return the observability category."""
        return PluginCapability.OBSERVABILITY

    @property
    def identifier(self) -> str:
        """Return the observability contribution identifier."""
        return self.contribution_id


type PluginContributionValue = (
    ModelProviderContribution
    | ToolContribution
    | MemoryStoreContribution
    | KnowledgeRetrieverContribution
    | GuardrailContribution
    | EvaluatorContribution
    | ObservabilityContribution
)


CONTRIBUTION_TYPES = (
    ModelProviderContribution,
    ToolContribution,
    MemoryStoreContribution,
    KnowledgeRetrieverContribution,
    GuardrailContribution,
    EvaluatorContribution,
    ObservabilityContribution,
)
