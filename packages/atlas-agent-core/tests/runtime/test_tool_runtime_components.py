"""Tests for execution-scoped tool records and model result mapping."""

import json
from datetime import UTC, datetime
from typing import cast

import pytest
from pydantic import ValidationError

from atlas_agents import (
    AgentContext,
    AgentDefinition,
    AgentInput,
    ExecutionState,
    ExecutionStateInvariantError,
    MessageRole,
    TextContent,
    ToolCallRecord,
    ToolExecutionError,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolOutput,
    ToolResultMessageMapper,
)


def _result(
    *,
    status: ToolExecutionStatus = ToolExecutionStatus.SUCCEEDED,
) -> ToolExecutionResult:
    now = datetime.now(UTC)
    error = (
        None
        if status is ToolExecutionStatus.SUCCEEDED
        else ToolExecutionError(
            code="tool_permission_denied",
            message="A ferramenta não foi autorizada.",
            retryable=False,
            details={"internal": "não enviar"},
        )
    )
    return ToolExecutionResult(
        tool_call_id="call-1",
        tool_name="search",
        status=status,
        output=(
            ToolOutput(content={"answer": 42}, metadata={"internal": True})
            if status is ToolExecutionStatus.SUCCEEDED
            else None
        ),
        error=error,
        started_at=now,
        completed_at=now,
        metadata={"trace": "internal"},
    )


def _record(result: ToolExecutionResult | None = None) -> ToolCallRecord:
    return ToolCallRecord(
        tool_call_id="call-1",
        tool_name="search",
        arguments={"q": "atlas"},
        result=result or _result(),
    )


def _state() -> ExecutionState:
    return ExecutionState(
        execution_id="execution-1",
        agent=AgentDefinition(
            agent_id="agent",
            name="Agent",
            instructions="Pesquise.",
            tool_names=("search",),
        ),
        input_data=AgentInput(message="Pesquise Atlas."),
        context=AgentContext(execution_id="execution-1"),
    )


@pytest.mark.parametrize(
    "status",
    [ToolExecutionStatus.SUCCEEDED, ToolExecutionStatus.DENIED],
)
def test_tool_result_mapper_emits_minimal_deterministic_json(
    status: ToolExecutionStatus,
) -> None:
    message = ToolResultMessageMapper().map(_result(status=status))
    content = message.content[0]
    assert isinstance(content, TextContent)
    payload = cast(dict[str, object], json.loads(content.text))

    assert message.role is MessageRole.TOOL
    assert message.tool_call_id == "call-1"
    assert content.text == json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    assert "metadata" not in payload
    if status is ToolExecutionStatus.SUCCEEDED:
        assert payload == {
            "error": None,
            "output": {"answer": 42},
            "status": "succeeded",
        }
    else:
        assert payload["output"] is None
        error = cast(dict[str, object], payload["error"])
        assert "details" not in error


def test_tool_call_record_validates_identity_and_isolates_arguments() -> None:
    arguments: dict[str, object] = {"q": "atlas"}
    record = ToolCallRecord(
        tool_call_id="call-1",
        tool_name="search",
        arguments=arguments,
        result=_result(),
    )
    arguments["q"] = "changed"

    assert record.arguments == {"q": "atlas"}
    assert record.model_dump_json()
    with pytest.raises(ValidationError):
        record.tool_name = "other"
    with pytest.raises(ValidationError, match="resultado"):
        ToolCallRecord(
            tool_call_id="other-call",
            tool_name="search",
            arguments={},
            result=_result(),
        )


def test_execution_state_records_and_exposes_tool_calls_immutably() -> None:
    state = _state()
    record = _record()

    state.record_tool_call(record)

    assert state.tool_calls == (record,)
    assert state.get_tool_call_record("call-1") is record
    assert state.get_tool_call_record("unknown") is None
    snapshot = state.snapshot()
    assert snapshot.tool_calls == (record,)
    assert snapshot.model_dump(mode="json")["tool_calls"][0]["tool_call_id"] == (
        "call-1"
    )
    with pytest.raises(ExecutionStateInvariantError, match="duas vezes"):
        state.record_tool_call(record)
    with pytest.raises(ExecutionStateInvariantError, match="não pode estar vazio"):
        state.get_tool_call_record(" ")
