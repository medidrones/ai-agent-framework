"""Tests for registry, manager, and ordered pipeline behavior."""

from typing import cast

import pytest

from atlas_agents import (
    AgentGuardrailConfig,
    DuplicateGuardrailError,
    GuardrailContext,
    GuardrailDecision,
    GuardrailEvaluationError,
    GuardrailManager,
    GuardrailNotRegisteredError,
    GuardrailPipeline,
    GuardrailProtocolError,
    GuardrailRegistry,
    GuardrailResult,
    GuardrailStage,
    GuardrailStageMismatchError,
)
from tests.guardrails.fakes import FakeGuardrail


class MalformedGuardrail(FakeGuardrail):
    """Return deliberately invalid protocol values for fail-closed tests."""

    def __init__(self, mode: str) -> None:
        super().__init__("malformed", GuardrailStage.INPUT)
        self.mode = mode

    async def evaluate(
        self,
        value: object,
        context: GuardrailContext,
    ) -> GuardrailResult[object]:
        del context
        if self.mode == "type":
            return cast(GuardrailResult[object], object())
        return GuardrailResult.model_construct(
            guardrail_id=("other" if self.mode == "id" else self.guardrail_id),
            stage=(
                GuardrailStage.FINAL_OUTPUT
                if self.mode == "stage"
                else GuardrailStage.INPUT
            ),
            decision=GuardrailDecision.ALLOW,
            output=(None if self.mode == "output" else value),
        )


def _context(stage: GuardrailStage = GuardrailStage.INPUT) -> GuardrailContext:
    return GuardrailContext(execution_id="execution", agent_id="agent", stage=stage)


def test_registry_preserves_order_and_supports_full_api() -> None:
    first = FakeGuardrail("first", GuardrailStage.INPUT)
    second = FakeGuardrail("second", GuardrailStage.FINAL_OUTPUT)
    registry = GuardrailRegistry((first,))
    registry.register(second)

    assert registry.guardrails == (first, second)
    assert registry.get("first") is first
    assert registry.try_get("unknown") is None
    assert registry.unregister("first") is first
    with pytest.raises(GuardrailNotRegisteredError):
        registry.get("first")
    with pytest.raises(GuardrailNotRegisteredError):
        registry.unregister("unknown")
    with pytest.raises(DuplicateGuardrailError):
        registry.register(second)


async def test_pipeline_chains_in_order_and_empty_pipeline_allows() -> None:
    order: list[str] = []
    upper = FakeGuardrail(
        "upper",
        GuardrailStage.INPUT,
        decision=GuardrailDecision.TRANSFORM,
        transform=lambda value: str(value).upper(),
        order=order,
    )
    wrap = FakeGuardrail(
        "wrap",
        GuardrailStage.INPUT,
        decision=GuardrailDecision.TRANSFORM,
        transform=lambda value: f"[{value}]",
        order=order,
    )
    result = await GuardrailPipeline(
        stage=GuardrailStage.INPUT,
        guardrails=(upper, wrap),
    ).evaluate(value="abc", context=_context())
    empty = await GuardrailPipeline[str](stage=GuardrailStage.INPUT).evaluate(
        value="abc", context=_context()
    )

    assert order == ["upper", "wrap"]
    assert result.output == "[ABC]"
    assert result.decision is GuardrailDecision.TRANSFORM
    assert empty.output == "abc"
    assert empty.decision is GuardrailDecision.ALLOW


async def test_pipeline_short_circuits_reject_and_normalizes_exception() -> None:
    reject = FakeGuardrail(
        "reject",
        GuardrailStage.INPUT,
        decision=GuardrailDecision.REJECT,
    )
    skipped = FakeGuardrail("skipped", GuardrailStage.INPUT)
    result = await GuardrailPipeline(
        stage=GuardrailStage.INPUT,
        guardrails=(reject, skipped),
    ).evaluate(value="x", context=_context())

    assert result.decision is GuardrailDecision.REJECT
    assert skipped.values == []
    failing = FakeGuardrail(
        "failure", GuardrailStage.INPUT, exception=RuntimeError("secret")
    )
    with pytest.raises(GuardrailEvaluationError):
        await GuardrailPipeline(
            stage=GuardrailStage.INPUT, guardrails=(failing,)
        ).evaluate(value="x", context=_context())


async def test_pipeline_and_manager_reject_stage_mismatch_and_unknown_ids() -> None:
    final = FakeGuardrail("final", GuardrailStage.FINAL_OUTPUT)
    registry = GuardrailRegistry((final,))
    manager = GuardrailManager(registry)
    config = AgentGuardrailConfig(input_guardrails=("final",))

    with pytest.raises(GuardrailStageMismatchError):
        manager.validate_config(config)
    with pytest.raises(GuardrailStageMismatchError):
        GuardrailPipeline(stage=GuardrailStage.INPUT, guardrails=(final,))
    with pytest.raises(GuardrailStageMismatchError):
        await GuardrailPipeline[str](stage=GuardrailStage.INPUT).evaluate(
            value="x",
            context=_context(GuardrailStage.FINAL_OUTPUT),
        )
    with pytest.raises(GuardrailNotRegisteredError):
        GuardrailManager(GuardrailRegistry()).validate_config(
            AgentGuardrailConfig(input_guardrails=("unknown",))
        )
    with pytest.raises(GuardrailProtocolError):
        GuardrailPipeline(
            stage=GuardrailStage.INPUT,
            guardrails=(
                FakeGuardrail("same", GuardrailStage.INPUT),
                FakeGuardrail("same", GuardrailStage.INPUT),
            ),
        )


@pytest.mark.parametrize("mode", ["type", "id", "stage", "output"])
async def test_pipeline_fails_closed_for_malformed_results(mode: str) -> None:
    with pytest.raises(GuardrailProtocolError):
        await GuardrailPipeline(
            stage=GuardrailStage.INPUT,
            guardrails=(MalformedGuardrail(mode),),
        ).evaluate(value="content", context=_context())
