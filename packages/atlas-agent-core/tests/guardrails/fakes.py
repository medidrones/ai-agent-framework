"""Configurable guardrail doubles."""

import asyncio
from collections.abc import Callable

from atlas_agents import (
    GuardrailContext,
    GuardrailDecision,
    GuardrailEnforcement,
    GuardrailResult,
    GuardrailStage,
    GuardrailTransformation,
    GuardrailViolation,
)


class FakeGuardrail:
    def __init__(
        self,
        guardrail_id: str,
        stage: GuardrailStage,
        *,
        decision: GuardrailDecision = GuardrailDecision.ALLOW,
        transform: Callable[[object], object] | None = None,
        enforcement: GuardrailEnforcement = GuardrailEnforcement.EXECUTION,
        exception: Exception | None = None,
        delay: float = 0,
        order: list[str] | None = None,
    ) -> None:
        self._guardrail_id = guardrail_id
        self._stage = stage
        self.decision = decision
        self.transform = transform
        self.enforcement = enforcement
        self.exception = exception
        self.delay = delay
        self.order = order
        self.values: list[object] = []
        self.contexts: list[GuardrailContext] = []

    @property
    def guardrail_id(self) -> str:
        return self._guardrail_id

    @property
    def stage(self) -> GuardrailStage:
        return self._stage

    async def evaluate(
        self,
        value: object,
        context: GuardrailContext,
    ) -> GuardrailResult[object]:
        await asyncio.sleep(self.delay)
        if self.exception is not None:
            raise self.exception
        self.values.append(value)
        self.contexts.append(context)
        if self.order is not None:
            self.order.append(self.guardrail_id)
        if self.decision is GuardrailDecision.REJECT:
            return GuardrailResult(
                guardrail_id=self.guardrail_id,
                stage=self.stage,
                decision=self.decision,
                enforcement=self.enforcement,
                violations=(GuardrailViolation(code="blocked", message="Bloqueado."),),
            )
        if self.decision is GuardrailDecision.TRANSFORM:
            transformed = self.transform(value) if self.transform is not None else value
            return GuardrailResult(
                guardrail_id=self.guardrail_id,
                stage=self.stage,
                decision=self.decision,
                output=transformed,
                transformations=(
                    GuardrailTransformation(
                        kind="test",
                        description="Transformação de teste.",
                    ),
                ),
            )
        return GuardrailResult(
            guardrail_id=self.guardrail_id,
            stage=self.stage,
            decision=self.decision,
            output=value,
        )
