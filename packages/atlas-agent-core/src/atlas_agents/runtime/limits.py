"""Immutable execution limit policies and deterministic violation facts."""

import math
from enum import StrEnum

from pydantic import Field, field_validator

from atlas_agents._models import _FrozenModel


class ExecutionLimits(_FrozenModel):
    """Configure optional execution-scoped structural and token limits."""

    max_turns: int | None = Field(default=None, gt=0)
    max_tool_calls: int | None = Field(default=None, gt=0)
    max_input_tokens: int | None = Field(default=None, gt=0)
    max_output_tokens: int | None = Field(default=None, gt=0)
    max_total_tokens: int | None = Field(default=None, gt=0)
    timeout_seconds: float | None = Field(default=None, gt=0)

    @field_validator(
        "max_turns",
        "max_tool_calls",
        "max_input_tokens",
        "max_output_tokens",
        "max_total_tokens",
        "timeout_seconds",
        mode="before",
    )
    @classmethod
    def reject_boolean_limits(cls, value: object) -> object:
        """Reject booleans even though Python models them as integers."""
        if isinstance(value, bool):
            raise ValueError("Limites de execução não podem ser booleanos")
        return value

    @field_validator("timeout_seconds")
    @classmethod
    def validate_finite_timeout(cls, value: float | None) -> float | None:
        """Require a finite positive timeout when one is configured."""
        if value is not None and not math.isfinite(value):
            raise ValueError("O timeout da execução deve ser finito")
        return value


class ExecutionLimitReason(StrEnum):
    """Identify the stable reason for a structural or token limit violation."""

    MAX_TURNS = "max_turns"
    MAX_TOOL_CALLS = "max_tool_calls"
    MAX_INPUT_TOKENS = "max_input_tokens"
    MAX_OUTPUT_TOKENS = "max_output_tokens"
    MAX_TOTAL_TOKENS = "max_total_tokens"


class ExecutionLimitViolation(_FrozenModel):
    """Describe one deterministic execution limit violation."""

    reason: ExecutionLimitReason
    limit: int = Field(ge=0)
    observed: int = Field(ge=0)
