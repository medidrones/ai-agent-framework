"""Certification tests for the Atlas 1.0.1 checkpoint contract."""

import asyncio
import inspect
from pathlib import Path

import pytest
from pydantic import ValidationError

from atlas_agents import (
    ApprovalDecision,
    CheckpointStore,
    ExecutionCheckpoint,
    ExecutionSuspension,
    ResumeToken,
    ToolApprovalMode,
)
from tests.approvals.fakes import FakeCheckpointStore
from tests.runtime.test_human_approval import (
    _agent,
    _call,
    _decision,
    _final_response,
    _runtime,
    _start,
    _tool_response,
)
from tests.runtime.test_multi_turn_runtime import SequencedProvider
from tests.tools.fakes import FakeTool, tool_definition


class FailingConsumeStore(FakeCheckpointStore):
    """Expose the current pass-through semantics for storage failures."""

    async def consume(self, resume_token: ResumeToken) -> ExecutionCheckpoint:
        del resume_token
        raise RuntimeError("Falha de consumo simulada.")


class BlockingConsumeStore(FakeCheckpointStore):
    """Block consumption so cancellation propagation can be certified."""

    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()

    async def consume(self, resume_token: ResumeToken) -> ExecutionCheckpoint:
        del resume_token
        self.started.set()
        await asyncio.Event().wait()
        raise AssertionError("O consumo cancelado não deve prosseguir.")


async def _suspended(
    store: FakeCheckpointStore,
) -> tuple[ExecutionSuspension, FakeTool]:
    provider = SequencedProvider((_tool_response(_call()), _final_response()))
    tool = FakeTool(
        tool_definition(name="sensitive", approval_mode=ToolApprovalMode.REQUIRED)
    )
    runtime, _, _ = _runtime(provider, tool, store=store)
    outcome = await _start(runtime, _agent("sensitive"))
    assert isinstance(outcome, ExecutionSuspension)
    return outcome, tool


def test_checkpoint_store_signature_is_the_certified_minimal_contract() -> None:
    save = inspect.signature(CheckpointStore.save)
    consume = inspect.signature(CheckpointStore.consume)

    assert tuple(save.parameters) == ("self", "resume_token", "checkpoint")
    assert save.parameters["resume_token"].kind is inspect.Parameter.KEYWORD_ONLY
    assert save.parameters["checkpoint"].kind is inspect.Parameter.KEYWORD_ONLY
    assert tuple(consume.parameters) == ("self", "resume_token")
    assert inspect.iscoroutinefunction(CheckpointStore.save)
    assert inspect.iscoroutinefunction(CheckpointStore.consume)


def test_checkpoint_field_inventory_matches_the_version_one_baseline() -> None:
    assert tuple(ExecutionCheckpoint.model_fields) == (
        "checkpoint_version",
        "execution_id",
        "execution_mode",
        "agent",
        "input_data",
        "effective_input",
        "context",
        "trace_context",
        "status",
        "messages",
        "knowledge_context",
        "model_selection",
        "usage",
        "has_model_usage",
        "turn_count",
        "tool_call_count",
        "events",
        "transitions",
        "tool_call_records",
        "guardrail_records",
        "pending_approval",
        "pending_tool_calls",
        "approval_history",
        "limits",
        "budget",
        "remaining_timeout_seconds",
        "created_at",
        "updated_at",
        "metadata",
    )


async def test_checkpoint_v1_json_round_trip_is_deterministic_and_token_free() -> None:
    store = FakeCheckpointStore()
    suspension, _ = await _suspended(store)
    checkpoint = store.peek(suspension.resume_token)

    serialized = checkpoint.model_dump_json()
    restored = ExecutionCheckpoint.model_validate_json(serialized)

    assert restored == checkpoint
    assert restored.model_dump_json() == serialized
    assert suspension.resume_token.value not in serialized
    assert "resume_token" not in serialized
    with pytest.raises(ValidationError):
        checkpoint.checkpoint_version = 2


async def test_checkpoint_v1_rejects_unknown_and_invalid_serialized_data() -> None:
    store = FakeCheckpointStore()
    suspension, _ = await _suspended(store)
    checkpoint = store.peek(suspension.resume_token)
    serialized = checkpoint.model_dump(mode="json")

    with pytest.raises(ValidationError):
        ExecutionCheckpoint.model_validate({**serialized, "unknown": True})
    with pytest.raises(ValidationError):
        ExecutionCheckpoint.model_validate({**serialized, "checkpoint_version": 0})
    with pytest.raises(ValidationError):
        ExecutionCheckpoint.model_validate({**serialized, "pending_tool_calls": []})


def test_versioned_checkpoint_v1_fixture_remains_loadable() -> None:
    fixture = (
        Path(__file__).parents[1]
        / "fixtures"
        / "checkpoints"
        / "execution-checkpoint-v1.json"
    )

    checkpoint = ExecutionCheckpoint.model_validate_json(
        fixture.read_text(encoding="utf-8")
    )

    assert checkpoint.checkpoint_version == 1
    assert checkpoint.execution_id == "execution-fixture-1"
    assert checkpoint.pending_approval.approval_request_id == "approval-fixture-1"


async def test_consume_storage_failure_is_propagated_without_tool_execution() -> None:
    source = FakeCheckpointStore()
    suspension, tool = await _suspended(source)
    provider = SequencedProvider((_final_response(),))
    runtime, _, _ = _runtime(provider, tool, store=FailingConsumeStore())

    with pytest.raises(RuntimeError, match="Falha de consumo simulada"):
        await runtime.resume(
            resume_token=suspension.resume_token,
            decision=_decision_for(suspension),
        )

    assert tool.call_count == 0


async def test_cancelled_consume_preserves_cancelled_error_and_no_tool_runs() -> None:
    source = FakeCheckpointStore()
    suspension, tool = await _suspended(source)
    store = BlockingConsumeStore()
    provider = SequencedProvider((_final_response(),))
    runtime, _, _ = _runtime(provider, tool, store=store)
    task = asyncio.create_task(
        runtime.resume(
            resume_token=suspension.resume_token,
            decision=_decision_for(suspension),
        )
    )
    await store.started.wait()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert tool.call_count == 0


def _decision_for(suspension: ExecutionSuspension) -> ApprovalDecision:
    return _decision(suspension)
