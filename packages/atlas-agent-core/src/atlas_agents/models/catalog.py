"""Immutable snapshots of models discovered from registered providers."""

from typing import Self

from pydantic import Field, field_validator, model_validator

from atlas_agents._models import _FrozenModel, _trimmed_non_empty
from atlas_agents.models.capabilities import ModelDescriptor


class ModelCatalogEntry(_FrozenModel):
    """Associate one descriptor with deterministic discovery ordering."""

    provider_name: str
    descriptor: ModelDescriptor
    registration_order: int = Field(ge=0)
    model_order: int = Field(ge=0)

    @field_validator("provider_name")
    @classmethod
    def validate_provider_name(cls, value: str) -> str:
        """Normalize only external provider identifier whitespace."""
        return _trimmed_non_empty(value)

    @model_validator(mode="after")
    def validate_descriptor_provider(self) -> Self:
        """Require the descriptor to belong to the catalog provider."""
        if self.descriptor.provider != self.provider_name:
            msg = "O provider do descriptor deve coincidir com a entrada do catálogo"
            raise ValueError(msg)
        return self
