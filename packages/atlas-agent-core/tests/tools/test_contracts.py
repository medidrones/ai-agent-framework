"""Tests for immutable tool boundary contracts."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from atlas_agents import (
    ExecutionIdentity,
    ToolDefinition,
    ToolExecutionContext,
    ToolExecutionError,
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolIdempotency,
    ToolOutput,
)


def test_tool_definition_isolates_runtime_data_and_converts_model_view() -> None:
    parameters: dict[str, object] = {"type": "object"}
    metadata: dict[str, object] = {"internal": "policy"}
    definition = ToolDefinition(
        name="get_customer",
        description="Consulta um cliente.",
        parameters=parameters,
        required_permissions=frozenset({"customer.read"}),
        idempotency=ToolIdempotency.IDEMPOTENT,
        metadata=metadata,
    )
    parameters["type"] = "array"
    metadata["internal"] = "changed"

    model_definition = definition.to_model_definition()

    assert definition.parameters == {"type": "object"}
    assert definition.metadata == {"internal": "policy"}
    assert model_definition.model_dump(mode="json") == {
        "name": "get_customer",
        "description": "Consulta um cliente.",
        "parameters": {"type": "object"},
    }
    assert "required_permissions" not in type(model_definition).model_fields
    assert "idempotency" not in type(model_definition).model_fields
    assert "metadata" not in type(model_definition).model_fields
    assert definition.model_dump(mode="json")["idempotency"] == "idempotent"
    with pytest.raises(ValidationError):
        definition.name = "other"


@pytest.mark.parametrize("field", ["name", "description"])
def test_tool_definition_rejects_empty_required_text(field: str) -> None:
    data: dict[str, object] = {
        "name": "tool",
        "description": "Descrição",
        "parameters": {},
    }
    data[field] = " "
    with pytest.raises(ValidationError):
        ToolDefinition.model_validate(data)


def test_tool_definition_rejects_empty_permission_and_non_json_data() -> None:
    with pytest.raises(ValidationError):
        ToolDefinition(
            name="tool",
            description="Descrição",
            parameters={},
            required_permissions=frozenset({" "}),
        )
    with pytest.raises(ValidationError):
        ToolDefinition(
            name="tool",
            description="Descrição",
            parameters={"bad": object()},
        )


def test_request_is_structured_immutable_and_isolated() -> None:
    arguments: dict[str, object] = {"customer_id": "123"}
    metadata: dict[str, object] = {"source": "model"}
    request = ToolExecutionRequest(
        tool_call_id="call-1",
        tool_name="get_customer",
        arguments=arguments,
        idempotency_key="operation-1",
        metadata=metadata,
    )
    arguments["customer_id"] = "changed"
    metadata["source"] = "changed"

    assert request.arguments == {"customer_id": "123"}
    assert request.metadata == {"source": "model"}
    assert request.idempotency_key == "operation-1"
    with pytest.raises(ValidationError):
        request.tool_name = "other"
    with pytest.raises(ValidationError):
        ToolExecutionRequest.model_validate(
            {"tool_call_id": "call", "tool_name": "tool", "arguments": "{}"}
        )


@pytest.mark.parametrize("field", ["tool_call_id", "tool_name", "idempotency_key"])
def test_request_rejects_empty_identifiers(field: str) -> None:
    data: dict[str, object] = {
        "tool_call_id": "call",
        "tool_name": "tool",
        "arguments": {},
        "idempotency_key": "key",
    }
    data[field] = ""
    with pytest.raises(ValidationError):
        ToolExecutionRequest.model_validate(data)


def test_context_reuses_execution_identity_without_service_locator() -> None:
    metadata: dict[str, object] = {"trace": "opaque"}
    identity = ExecutionIdentity(
        subject="user-1",
        permissions=frozenset({"customer.read"}),
    )
    context = ToolExecutionContext(
        execution_id="execution-1",
        agent_id="agent-1",
        tool_call_id="call-1",
        identity=identity,
        metadata=metadata,
    )
    metadata["trace"] = "changed"

    assert context.identity is identity
    assert context.metadata == {"trace": "opaque"}
    assert set(type(context).model_fields) == {
        "execution_id",
        "agent_id",
        "tool_call_id",
        "identity",
        "metadata",
    }
    with pytest.raises(ValidationError):
        context.agent_id = "other"


def test_tool_output_accepts_json_and_rejects_raw_objects() -> None:
    content: dict[str, object] = {"customer": {"id": "123"}}
    output = ToolOutput(content=content)
    content["customer"] = object()

    assert output.content == {"customer": {"id": "123"}}
    assert output.model_dump(mode="json")["content"] == {"customer": {"id": "123"}}
    with pytest.raises(ValidationError):
        ToolOutput(content=object())


def test_execution_result_enforces_status_and_timestamp_invariants() -> None:
    now = datetime.now(UTC)
    error = ToolExecutionError(code="failed", message="Falha segura.")
    succeeded = ToolExecutionResult(
        tool_call_id="call",
        tool_name="tool",
        status=ToolExecutionStatus.SUCCEEDED,
        output=ToolOutput(content=None),
        started_at=now,
        completed_at=now + timedelta(seconds=1),
    )
    assert succeeded.duration_seconds == 1

    with pytest.raises(ValidationError):
        ToolExecutionResult(
            tool_call_id="call",
            tool_name="tool",
            status=ToolExecutionStatus.FAILED,
            started_at=now,
            completed_at=now,
        )
    with pytest.raises(ValidationError):
        ToolExecutionResult(
            tool_call_id="call",
            tool_name="tool",
            status=ToolExecutionStatus.SUCCEEDED,
            output=ToolOutput(),
            error=error,
            started_at=now,
            completed_at=now,
        )
    with pytest.raises(ValidationError):
        ToolExecutionResult(
            tool_call_id="call",
            tool_name="tool",
            status=ToolExecutionStatus.FAILED,
            output=ToolOutput(),
            error=error,
            started_at=now,
            completed_at=now,
        )
    with pytest.raises(ValidationError):
        ToolExecutionResult(
            tool_call_id="call",
            tool_name="tool",
            status=ToolExecutionStatus.CANCELLED,
            started_at=now,
            completed_at=now - timedelta(seconds=1),
        )
    with pytest.raises(ValidationError):
        ToolExecutionResult(
            tool_call_id="call",
            tool_name="tool",
            status=ToolExecutionStatus.FAILED,
            error=error,
            started_at=now.replace(tzinfo=None),
            completed_at=now,
        )
