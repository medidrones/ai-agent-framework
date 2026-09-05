"""Normative tests for immutable human approval contracts."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import TypeAdapter, ValidationError

from atlas_agents import (
    ApprovalContext,
    ApprovalDecision,
    ApprovalDecisionMismatchError,
    ApprovalDecisionType,
    ApprovalKind,
    ApprovalNotRequired,
    ApprovalRequest,
    ApprovalRequired,
    ApprovalRequirement,
    DefaultApprovalDecisionValidator,
    ExecutionIdentity,
    ExecutionStatus,
    ExecutionSuspension,
    ResumeToken,
    ToolApprovalMode,
    ToolApprovalSubject,
)
from tests.tools.fakes import tool_definition


def _request() -> ApprovalRequest:
    requested_at = datetime(2026, 1, 1, tzinfo=UTC)
    return ApprovalRequest(
        approval_request_id="approval-1",
        execution_id="execution-1",
        agent_id="agent-1",
        summary="Autorizar consulta?",
        reason="A operação exige revisão.",
        requested_at=requested_at,
        expires_at=requested_at + timedelta(hours=1),
        subject=ToolApprovalSubject(
            tool_call_id="call-1",
            tool_name="lookup",
            argument_keys=("customer_id",),
        ),
    )


def test_approval_enums_have_stable_minimal_values() -> None:
    assert [item.value for item in ApprovalDecisionType] == ["approve", "reject"]
    assert [item.value for item in ApprovalKind] == ["tool_execution"]
    assert [item.value for item in ToolApprovalMode] == [
        "not_required",
        "policy_controlled",
        "required",
    ]


def test_decision_is_frozen_serializable_and_reuses_execution_identity() -> None:
    decision = ApprovalDecision(
        approval_request_id="approval-1",
        decision=ApprovalDecisionType.APPROVE,
        decided_at=datetime.now(UTC),
        decided_by=ExecutionIdentity(subject="manager"),
        metadata={"channel": "portal"},
    )

    assert decision.model_dump(mode="json")["decided_by"]["subject"] == "manager"
    with pytest.raises(ValidationError):
        decision.reason = "alterado"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"decided_at": datetime(2026, 1, 1)},
        {"metadata": {"unsafe": object()}},
    ],
)
def test_decision_rejects_unsafe_boundary_values(kwargs: dict[str, object]) -> None:
    values: dict[str, object] = {
        "approval_request_id": "approval-1",
        "decision": ApprovalDecisionType.APPROVE,
        "decided_at": datetime.now(UTC),
    }
    values.update(kwargs)

    with pytest.raises(ValidationError):
        ApprovalDecision.model_validate(values)


def test_request_exposes_only_safe_tool_subject_and_validates_expiration() -> None:
    request = _request()

    assert request.subject.argument_keys == ("customer_id",)
    assert "arguments" not in request.model_dump(mode="json")["subject"]
    invalid = request.model_dump()
    invalid["expires_at"] = request.requested_at - timedelta(seconds=1)
    with pytest.raises(ValidationError):
        ApprovalRequest.model_validate(invalid)


def test_requirement_union_is_discriminated_and_serializable() -> None:
    adapter: TypeAdapter[ApprovalRequirement] = TypeAdapter(ApprovalRequirement)
    required = ApprovalRequired(reason="Revisão.", summary="Autorizar?")

    assert adapter.dump_python(required)["type"] == "required"
    assert isinstance(
        adapter.validate_python({"type": "not_required"}), ApprovalNotRequired
    )


def test_default_validator_rejects_mismatched_request_identity() -> None:
    decision = ApprovalDecision(
        approval_request_id="other",
        decision=ApprovalDecisionType.APPROVE,
        decided_at=datetime.now(UTC),
    )

    with pytest.raises(ApprovalDecisionMismatchError):
        DefaultApprovalDecisionValidator().validate(
            request=_request(),
            decision=decision,
        )


def test_context_and_resume_token_are_opaque_immutable_contracts() -> None:
    context = ApprovalContext(
        execution_id="execution-1",
        agent_id="agent-1",
        tool_call_id="call-1",
    )
    first = ResumeToken.create()
    second = ResumeToken.create()

    assert context.metadata == {}
    assert first != second
    assert len(first.value) >= 32


def test_suspension_requires_waiting_status_and_matching_execution() -> None:
    suspension = ExecutionSuspension(
        execution_id="execution-1",
        approval_request=_request(),
        resume_token=ResumeToken(value="opaque-token"),
        checkpoint_version=1,
        created_at=datetime.now(UTC),
    )

    assert suspension.status is ExecutionStatus.WAITING_FOR_APPROVAL
    assert suspension.model_dump_json()
    with pytest.raises(ValidationError):
        ExecutionSuspension(
            execution_id="execution-1",
            status=ExecutionStatus.RUNNING,
            approval_request=_request(),
            resume_token=ResumeToken(value="opaque-token"),
            checkpoint_version=1,
            created_at=datetime.now(UTC),
        )


def test_tool_definition_defaults_to_no_approval_and_hides_mode_from_model() -> None:
    definition = tool_definition()

    assert definition.approval_mode is ToolApprovalMode.NOT_REQUIRED
    assert "approval_mode" not in definition.to_model_definition().model_dump()
