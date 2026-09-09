"""Async-first generic guardrail protocol."""

from typing import Protocol

from atlas_agents.guardrails.context import GuardrailContext
from atlas_agents.guardrails.result import GuardrailResult
from atlas_agents.guardrails.stage import GuardrailStage


class Guardrail[T](Protocol):
    """Evaluate one typed value at a fixed runtime stage."""

    @property
    def guardrail_id(self) -> str:
        """Return the stable identifier used by agent configuration."""
        ...

    @property
    def stage(self) -> GuardrailStage:
        """Return the single stage supported by this implementation."""
        ...

    async def evaluate(self, value: T, context: GuardrailContext) -> GuardrailResult[T]:
        """Evaluate a value without owning the execution loop."""
        ...
