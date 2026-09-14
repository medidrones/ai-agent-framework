"""Demonstrate deterministic ALLOW, TRANSFORM, and REJECT decisions."""

import asyncio

from atlas_agents import (
    GuardrailContext,
    GuardrailDecision,
    GuardrailEnforcement,
    GuardrailPipeline,
    GuardrailResult,
    GuardrailStage,
    GuardrailTransformation,
    GuardrailViolation,
)


class TextGuardrail:
    """Apply a fixed decision at one public guardrail stage."""

    def __init__(self, decision: GuardrailDecision) -> None:
        """Store the deterministic decision."""
        self.decision = decision

    @property
    def guardrail_id(self) -> str:
        """Return a stable example identifier."""
        return f"example-{self.decision.value}"

    @property
    def stage(self) -> GuardrailStage:
        """Evaluate input values."""
        return GuardrailStage.INPUT

    async def evaluate(
        self,
        value: str,
        context: GuardrailContext,
    ) -> GuardrailResult[str]:
        """Return the configured valid guardrail result."""
        del context
        if self.decision is GuardrailDecision.REJECT:
            return GuardrailResult(
                guardrail_id=self.guardrail_id,
                stage=self.stage,
                decision=self.decision,
                enforcement=GuardrailEnforcement.EXECUTION,
                violations=(
                    GuardrailViolation(
                        code="prohibited_operation",
                        message="A operação solicitada não é permitida.",
                    ),
                ),
            )
        if self.decision is GuardrailDecision.TRANSFORM:
            return GuardrailResult(
                guardrail_id=self.guardrail_id,
                stage=self.stage,
                decision=self.decision,
                output=value.replace("secret", "[redacted]"),
                transformations=(
                    GuardrailTransformation(
                        kind="redaction",
                        description="Remove conteúdo sensível de demonstração.",
                    ),
                ),
            )
        return GuardrailResult(
            guardrail_id=self.guardrail_id,
            stage=self.stage,
            decision=self.decision,
            output=value,
        )


async def _run() -> None:
    context = GuardrailContext(
        execution_id="guardrail-example",
        agent_id="example-agent",
        stage=GuardrailStage.INPUT,
    )
    for decision in GuardrailDecision:
        result = await GuardrailPipeline(
            stage=GuardrailStage.INPUT,
            guardrails=(TextGuardrail(decision),),
        ).evaluate(value="request with secret", context=context)
        print(f"{decision.value.upper()}: saída={result.output!r}")  # noqa: T201
    print("REJECT é uma decisão de política, não uma falha técnica.")  # noqa: T201


if __name__ == "__main__":
    asyncio.run(_run())
