"""Immutable requests, candidates, and results for model selection."""

from typing import Self

from pydantic import Field, field_validator, model_validator

from atlas_agents._models import (
    _FrozenModel,
    _json_mapping,
    _non_empty,
    _trimmed_non_empty,
)
from atlas_agents.models.capabilities import ModelCapability, ModelDescriptor


class ModelSelectionRequest(_FrozenModel):
    """Describe provider-neutral requirements for choosing one model."""

    provider: str | None = None
    model: str | None = None
    required_capabilities: frozenset[ModelCapability] = frozenset()
    preferred_capabilities: frozenset[ModelCapability] = frozenset()
    minimum_context_window: int | None = Field(default=None, gt=0)
    minimum_max_output_tokens: int | None = Field(default=None, gt=0)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str | None) -> str | None:
        """Normalize only external provider identifier whitespace."""
        return None if value is None else _trimmed_non_empty(value)

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str | None) -> str | None:
        """Reject an explicitly empty opaque model identifier."""
        return None if value is None else _non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep selection metadata JSON-compatible and isolated."""
        return _json_mapping(value)


class ModelCandidate(_FrozenModel):
    """Represent one eligible model and its explicit ranking facts."""

    provider_name: str
    descriptor: ModelDescriptor
    registration_order: int = Field(ge=0)
    model_order: int = Field(ge=0)
    preferred_capability_matches: int = Field(ge=0)

    @field_validator("provider_name")
    @classmethod
    def validate_provider_name(cls, value: str) -> str:
        """Normalize only external provider identifier whitespace."""
        return _trimmed_non_empty(value)

    @model_validator(mode="after")
    def validate_descriptor_provider(self) -> Self:
        """Require the descriptor to belong to the candidate provider."""
        if self.descriptor.provider != self.provider_name:
            msg = "O provider do descriptor deve coincidir com o candidato"
            raise ValueError(msg)
        return self


class ModelSelectionResult(_FrozenModel):
    """Describe the serializable outcome of deterministic model selection."""

    provider_name: str
    model: str
    descriptor: ModelDescriptor
    matched_required_capabilities: frozenset[ModelCapability]
    matched_preferred_capabilities: frozenset[ModelCapability]
    preferred_capability_matches: int = Field(ge=0)
    candidate_count: int = Field(gt=0)

    @field_validator("provider_name")
    @classmethod
    def validate_provider_name(cls, value: str) -> str:
        """Normalize only external provider identifier whitespace."""
        return _trimmed_non_empty(value)

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        """Reject an empty selected model identifier."""
        return _non_empty(value)

    @model_validator(mode="after")
    def validate_selection_facts(self) -> Self:
        """Require selected identity and match counts to describe the descriptor."""
        if self.descriptor.provider != self.provider_name:
            msg = "O provider do descriptor deve coincidir com o resultado"
            raise ValueError(msg)
        if self.descriptor.model != self.model:
            msg = "O modelo do descriptor deve coincidir com o resultado"
            raise ValueError(msg)
        if not self.matched_required_capabilities <= self.descriptor.capabilities:
            msg = "As capabilities obrigatórias devem existir no descriptor"
            raise ValueError(msg)
        if not self.matched_preferred_capabilities <= self.descriptor.capabilities:
            msg = "As capabilities preferidas devem existir no descriptor"
            raise ValueError(msg)
        if self.preferred_capability_matches != len(
            self.matched_preferred_capabilities
        ):
            msg = "A contagem de capabilities preferidas deve ser consistente"
            raise ValueError(msg)
        return self
