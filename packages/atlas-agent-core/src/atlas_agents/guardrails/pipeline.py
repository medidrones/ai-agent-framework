"""Ordered fail-closed guardrail pipeline."""

import asyncio

from atlas_agents.guardrails.base import Guardrail
from atlas_agents.guardrails.context import GuardrailContext
from atlas_agents.guardrails.errors import (
    GuardrailEvaluationError,
    GuardrailProtocolError,
    GuardrailStageMismatchError,
)
from atlas_agents.guardrails.result import GuardrailPipelineResult, GuardrailResult
from atlas_agents.guardrails.stage import GuardrailDecision, GuardrailStage


class GuardrailPipeline[T]:
    """Evaluate configured guardrails in exact order and short-circuit rejects."""

    def __init__(
        self,
        *,
        stage: GuardrailStage,
        guardrails: tuple[Guardrail[T], ...] = (),
    ) -> None:
        """Validate and preserve the caller-declared guardrail order."""
        self._stage = stage
        self._guardrails = guardrails
        ids = tuple(guardrail.guardrail_id for guardrail in guardrails)
        if len(set(ids)) != len(ids):
            raise GuardrailProtocolError("O pipeline contém IDs duplicados.")
        if any(guardrail.stage is not stage for guardrail in guardrails):
            raise GuardrailStageMismatchError(
                "O pipeline contém guardrail de outro estágio."
            )

    async def evaluate(
        self,
        *,
        value: T,
        context: GuardrailContext,
    ) -> GuardrailPipelineResult[T]:
        """Chain transformations and stop at the first explicit rejection."""
        if context.stage is not self._stage:
            raise GuardrailStageMismatchError(
                "O contexto não corresponde ao estágio do pipeline."
            )
        current = value
        results: list[GuardrailResult[T]] = []
        for guardrail in self._guardrails:
            try:
                result = await guardrail.evaluate(current, context)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                raise GuardrailEvaluationError(
                    "O guardrail falhou durante a avaliação."
                ) from exc
            if not isinstance(result, GuardrailResult):
                raise GuardrailProtocolError(
                    "O guardrail retornou um resultado incompatível."
                )
            if result.guardrail_id != guardrail.guardrail_id:
                raise GuardrailProtocolError(
                    "O resultado não pertence ao guardrail avaliado."
                )
            if result.stage is not self._stage:
                raise GuardrailProtocolError(
                    "O resultado não corresponde ao estágio avaliado."
                )
            results.append(result)
            if result.decision is GuardrailDecision.REJECT:
                return GuardrailPipelineResult(
                    decision=GuardrailDecision.REJECT,
                    enforcement=result.enforcement,
                    guardrail_results=tuple(results),
                    violations=tuple(
                        violation for item in results for violation in item.violations
                    ),
                    transformations=tuple(
                        transformation
                        for item in results
                        for transformation in item.transformations
                    ),
                )
            if result.output is None:
                raise GuardrailProtocolError(
                    "O guardrail aceitou um valor sem produzir output."
                )
            current = result.output
        transformations = tuple(
            transformation
            for item in results
            for transformation in item.transformations
        )
        return GuardrailPipelineResult(
            decision=(
                GuardrailDecision.TRANSFORM
                if transformations
                else GuardrailDecision.ALLOW
            ),
            output=current,
            guardrail_results=tuple(results),
            violations=tuple(
                violation for item in results for violation in item.violations
            ),
            transformations=transformations,
        )
