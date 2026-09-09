"""Resolve agent-scoped guardrail pipelines without execution state."""

from typing import cast

from atlas_agents.guardrails.base import Guardrail
from atlas_agents.guardrails.config import AgentGuardrailConfig
from atlas_agents.guardrails.context import GuardrailContext
from atlas_agents.guardrails.errors import GuardrailStageMismatchError
from atlas_agents.guardrails.pipeline import GuardrailPipeline
from atlas_agents.guardrails.registry import GuardrailRegistry
from atlas_agents.guardrails.result import GuardrailPipelineResult
from atlas_agents.guardrails.stage import GuardrailStage


class GuardrailManager:
    """Validate configuration and evaluate isolated ordered pipelines."""

    def __init__(self, registry: GuardrailRegistry) -> None:
        """Receive an instance-local registry by explicit injection."""
        self._registry = registry

    def validate_config(self, config: AgentGuardrailConfig) -> None:
        """Resolve all IDs and verify stage consistency before execution."""
        for stage in GuardrailStage:
            for guardrail_id in config.ids_for(stage):
                guardrail = self._registry.get(guardrail_id)
                if guardrail.stage is not stage:
                    raise GuardrailStageMismatchError(
                        "O guardrail foi configurado em um estágio incompatível."
                    )

    async def evaluate[T](
        self,
        *,
        config: AgentGuardrailConfig,
        stage: GuardrailStage,
        value: T,
        context: GuardrailContext,
    ) -> GuardrailPipelineResult[T]:
        """Build and evaluate a fresh execution-local pipeline."""
        guardrails = tuple(
            cast(Guardrail[T], self._registry.get(guardrail_id))
            for guardrail_id in config.ids_for(stage)
        )
        return await GuardrailPipeline(stage=stage, guardrails=guardrails).evaluate(
            value=value,
            context=context,
        )
