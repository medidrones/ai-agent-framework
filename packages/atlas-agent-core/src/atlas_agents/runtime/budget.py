"""Immutable execution budget policy and violation facts."""

from decimal import Decimal

from pydantic import Field, field_validator

from atlas_agents._models import _FrozenModel, _trimmed_non_empty


class ExecutionBudget(_FrozenModel):
    """Configure an optional execution-scoped estimated monetary cost ceiling."""

    max_estimated_cost: Decimal | None = Field(default=None, ge=Decimal(0))
    currency: str | None = None

    @field_validator("max_estimated_cost", mode="before")
    @classmethod
    def reject_boolean_cost(cls, value: object) -> object:
        """Reject booleans as monetary values."""
        if isinstance(value, bool):
            raise ValueError("O budget não pode ser booleano")
        return value

    @field_validator("max_estimated_cost")
    @classmethod
    def validate_finite_cost(cls, value: Decimal | None) -> Decimal | None:
        """Reject non-finite monetary limits."""
        if value is not None and not value.is_finite():
            raise ValueError("O budget deve ser um valor finito")
        return value

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str | None) -> str | None:
        """Normalize an optional opaque currency identifier."""
        return None if value is None else _trimmed_non_empty(value)


class ExecutionBudgetViolation(_FrozenModel):
    """Describe one known estimated-cost budget violation."""

    limit: Decimal = Field(ge=Decimal(0))
    observed: Decimal = Field(ge=Decimal(0))
