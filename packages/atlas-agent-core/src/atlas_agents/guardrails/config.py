"""Declarative agent-scoped guardrail configuration."""

from pydantic import field_validator

from atlas_agents._models import _FrozenModel, _non_empty
from atlas_agents.guardrails.errors import DuplicateGuardrailError
from atlas_agents.guardrails.stage import GuardrailStage


class AgentGuardrailConfig(_FrozenModel):
    """Declare ordered guardrail IDs with no implicit global policies."""

    input_guardrails: tuple[str, ...] = ()
    model_output_guardrails: tuple[str, ...] = ()
    tool_call_guardrails: tuple[str, ...] = ()
    tool_result_guardrails: tuple[str, ...] = ()
    final_output_guardrails: tuple[str, ...] = ()

    @field_validator("*")
    @classmethod
    def validate_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Require ordered unique non-empty identifiers per stage."""
        validated = tuple(_non_empty(item) for item in value)
        if len(set(validated)) != len(validated):
            raise DuplicateGuardrailError(
                "Os IDs de guardrail não podem se repetir no mesmo estágio."
            )
        return validated

    @property
    def enabled(self) -> bool:
        """Return whether the agent explicitly opted into any guardrail."""
        return any(self.ids_for(stage) for stage in GuardrailStage)

    def ids_for(self, stage: GuardrailStage) -> tuple[str, ...]:
        """Return configured IDs in exact execution order for one stage."""
        return {
            GuardrailStage.INPUT: self.input_guardrails,
            GuardrailStage.MODEL_OUTPUT: self.model_output_guardrails,
            GuardrailStage.TOOL_CALL: self.tool_call_guardrails,
            GuardrailStage.TOOL_RESULT: self.tool_result_guardrails,
            GuardrailStage.FINAL_OUTPUT: self.final_output_guardrails,
        }[stage]
