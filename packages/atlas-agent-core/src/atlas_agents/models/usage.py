"""Usage reported for one provider model call."""

from decimal import Decimal
from typing import Self

from pydantic import Field, field_validator, model_validator

from atlas_agents._models import _FrozenModel, _json_mapping


class ModelUsage(_FrozenModel):
    """Record provider-reported usage without calculating prices."""

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    estimated_cost: Decimal | None = Field(default=None, ge=Decimal(0))
    metadata: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_total(self) -> Self:
        """Require total tokens to equal input plus output tokens."""
        if self.total_tokens != self.input_tokens + self.output_tokens:
            msg = "O total de tokens deve ser igual à soma de entrada e saída"
            raise ValueError(msg)
        return self

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep usage metadata JSON-compatible and isolated."""
        return _json_mapping(value)
