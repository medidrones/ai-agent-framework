"""Tests for immutable guardrail contracts and invariants."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from atlas_agents import (
    AgentGuardrailConfig,
    DuplicateGuardrailError,
    GuardrailContext,
    GuardrailDecision,
    GuardrailEnforcement,
    GuardrailRecord,
    GuardrailResult,
    GuardrailSeverity,
    GuardrailStage,
    GuardrailTransformation,
    GuardrailViolation,
)


def test_enums_have_stable_provider_neutral_values() -> None:
    assert [stage.value for stage in GuardrailStage] == [
        "input",
        "model_output",
        "tool_call",
        "tool_result",
        "final_output",
    ]
    assert {item.value for item in GuardrailDecision} == {
        "allow",
        "transform",
        "reject",
    }
    assert {item.value for item in GuardrailEnforcement} == {
        "operation",
        "execution",
    }
    assert len(GuardrailSeverity) == 5


def test_violation_transformation_context_and_record_are_serializable() -> None:
    metadata: dict[str, object] = {"key": ["value"]}
    violation = GuardrailViolation(
        code="policy",
        message="Policy signal.",
        severity=GuardrailSeverity.HIGH,
        metadata=metadata,
    )
    transformation = GuardrailTransformation(
        kind="redaction",
        description="Literal redaction.",
        metadata=metadata,
    )
    context = GuardrailContext(
        execution_id="execution",
        agent_id="agent",
        stage=GuardrailStage.INPUT,
        metadata=metadata,
    )
    record = GuardrailRecord(
        stage=GuardrailStage.INPUT,
        guardrail_id="policy",
        decision=GuardrailDecision.TRANSFORM,
        violation_codes=(violation.code,),
        transformation_kinds=(transformation.kind,),
        timestamp=datetime.now(UTC),
    )
    metadata["key"] = []

    assert violation.metadata == {"key": ["value"]}
    assert context.model_dump(mode="json")["stage"] == "input"
    assert record.model_dump(mode="json")["timestamp"].endswith("Z")
    with pytest.raises(ValidationError):
        record.guardrail_id = "other"


@pytest.mark.parametrize(
    "data",
    [
        {"decision": GuardrailDecision.ALLOW},
        {
            "decision": GuardrailDecision.ALLOW,
            "output": "ok",
            "transformations": (GuardrailTransformation(kind="x", description="x"),),
        },
        {
            "decision": GuardrailDecision.ALLOW,
            "output": "ok",
            "enforcement": GuardrailEnforcement.OPERATION,
        },
        {"decision": GuardrailDecision.TRANSFORM, "output": "changed"},
        {
            "decision": GuardrailDecision.TRANSFORM,
            "output": "changed",
            "enforcement": GuardrailEnforcement.OPERATION,
            "transformations": (GuardrailTransformation(kind="x", description="x"),),
        },
        {"decision": GuardrailDecision.REJECT},
        {
            "decision": GuardrailDecision.REJECT,
            "output": "unsafe",
            "enforcement": GuardrailEnforcement.EXECUTION,
            "violations": (GuardrailViolation(code="x", message="x"),),
        },
    ],
)
def test_guardrail_result_rejects_inconsistent_decisions(
    data: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        GuardrailResult.model_validate(
            {
                "guardrail_id": "policy",
                "stage": GuardrailStage.INPUT,
                **data,
            }
        )


def test_agent_config_is_explicit_ordered_and_rejects_duplicates() -> None:
    empty = AgentGuardrailConfig()
    config = AgentGuardrailConfig(
        input_guardrails=("size", "redact"),
        final_output_guardrails=("final",),
    )

    assert not empty.enabled
    assert config.enabled
    assert config.ids_for(GuardrailStage.INPUT) == ("size", "redact")
    with pytest.raises(DuplicateGuardrailError):
        AgentGuardrailConfig(input_guardrails=("same", "same"))


def test_contracts_reject_empty_and_unsafe_values() -> None:
    with pytest.raises(ValidationError):
        GuardrailContext(execution_id=" ", agent_id="agent", stage=GuardrailStage.INPUT)
    with pytest.raises(ValidationError):
        GuardrailViolation(code="x", message="x", metadata={"bad": object()})
    with pytest.raises(ValidationError):
        GuardrailRecord(
            stage=GuardrailStage.INPUT,
            guardrail_id="x",
            decision=GuardrailDecision.ALLOW,
            timestamp=datetime.now(),
        )
