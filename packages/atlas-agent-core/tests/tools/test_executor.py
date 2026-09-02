"""Tests for the secure tool executor pipeline."""

import asyncio
from typing import cast

import pytest

from atlas_agents import (
    ExecutionIdentity,
    ToolArgumentValidationResult,
    ToolArgumentValidator,
    ToolExecutionContext,
    ToolExecutionInvariantError,
    ToolExecutionRequest,
    ToolExecutionStatus,
    ToolExecutor,
    ToolOutput,
    ToolRegistry,
    ToolUnavailableError,
)
from tests.tools.fakes import FakeTool, tool_definition


class SpyValidator:
    def __init__(self) -> None:
        self.call_count = 0

    def validate(
        self,
        *,
        schema: dict[str, object],
        arguments: dict[str, object],
    ) -> ToolArgumentValidationResult:
        del schema, arguments
        self.call_count += 1
        return ToolArgumentValidationResult(valid=True)


class InvalidOutputTool(FakeTool):
    async def execute(
        self,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolOutput:
        del arguments, context
        self.call_count += 1
        return cast(ToolOutput, object())


def _request(
    *,
    call_id: str = "call-1",
    name: str = "get_customer",
    arguments: dict[str, object] | None = None,
) -> ToolExecutionRequest:
    return ToolExecutionRequest(
        tool_call_id=call_id,
        tool_name=name,
        arguments=arguments or {"customer_id": "123"},
        idempotency_key="operation-1",
        metadata={"trace": "trace-1"},
    )


def _context(
    *,
    call_id: str = "call-1",
    permissions: frozenset[str] = frozenset(),
) -> ToolExecutionContext:
    identity = ExecutionIdentity(subject="user", permissions=permissions)
    return ToolExecutionContext(
        execution_id="execution-1",
        agent_id="agent-1",
        tool_call_id=call_id,
        identity=identity,
    )


def _executor(tool: FakeTool) -> ToolExecutor:
    registry = ToolRegistry()
    registry.register(tool)
    return ToolExecutor(registry=registry)


@pytest.mark.asyncio
async def test_executor_happy_path_preserves_identity_and_context() -> None:
    output = ToolOutput(content={"id": "123", "name": "Cliente"})
    tool = FakeTool(tool_definition(), output=output)
    request = _request()
    context = _context()

    result = await _executor(tool).execute(request, context)

    assert result.status is ToolExecutionStatus.SUCCEEDED
    assert result.output == output
    assert result.error is None
    assert result.tool_call_id is request.tool_call_id
    assert result.tool_name == request.tool_name
    assert result.metadata == request.metadata
    assert result.started_at.tzinfo is not None
    assert result.completed_at.tzinfo is not None
    assert result.completed_at >= result.started_at
    assert tool.call_count == 1
    assert tool.calls == [(request.arguments, context)]


@pytest.mark.asyncio
async def test_unknown_tool_is_a_normalized_failure_with_exact_lookup() -> None:
    registry = ToolRegistry()
    registry.register(FakeTool(tool_definition()))

    result = await ToolExecutor(registry=registry).execute(
        _request(name="Get_Customer"),
        _context(),
    )

    assert result.status is ToolExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == "tool_not_found"
    assert result.output is None


@pytest.mark.asyncio
async def test_permission_denial_precedes_validation_and_execution() -> None:
    tool = FakeTool(
        tool_definition(permissions=frozenset({"customer.read", "tenant.read"}))
    )
    registry = ToolRegistry()
    registry.register(tool)
    validator = SpyValidator()

    result = await ToolExecutor(
        registry=registry,
        validator=cast(ToolArgumentValidator, validator),
    ).execute(
        _request(arguments={}),
        _context(permissions=frozenset({"customer.read"})),
    )

    assert result.status is ToolExecutionStatus.DENIED
    assert result.error is not None
    assert result.error.code == "tool_permission_denied"
    assert result.error.details == {"missing_permissions": ["tenant.read"]}
    assert validator.call_count == 0
    assert tool.call_count == 0


@pytest.mark.asyncio
async def test_invalid_arguments_do_not_execute_tool() -> None:
    tool = FakeTool(tool_definition())

    result = await _executor(tool).execute(
        _request(arguments={"customer_id": 123, "unknown": True}),
        _context(),
    )

    assert result.status is ToolExecutionStatus.INVALID_ARGUMENTS
    assert result.error is not None
    assert result.error.code == "tool_invalid_arguments"
    assert len(cast(list[object], result.error.details["issues"])) == 2
    assert tool.call_count == 0


@pytest.mark.asyncio
async def test_known_tool_error_preserves_safe_code_and_retryability() -> None:
    tool = FakeTool(
        tool_definition(),
        exception=ToolUnavailableError(
            "O serviço necessário está indisponível.",
            details={"dependency": "customer_repository"},
        ),
    )

    result = await _executor(tool).execute(_request(), _context())

    assert result.status is ToolExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == "tool_unavailable"
    assert result.error.retryable
    assert result.error.details == {"dependency": "customer_repository"}
    assert tool.call_count == 1


@pytest.mark.asyncio
async def test_unexpected_error_does_not_leak_exception_details() -> None:
    sensitive_detail = "detalhe-interno-confidencial"
    tool = FakeTool(tool_definition(), exception=RuntimeError(sensitive_detail))

    result = await _executor(tool).execute(_request(), _context())

    assert result.status is ToolExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == "tool_execution_error"
    assert sensitive_detail not in result.error.message
    assert sensitive_detail not in str(result.model_dump(mode="json"))


@pytest.mark.asyncio
async def test_invalid_raw_output_is_rejected_at_executor_boundary() -> None:
    tool = InvalidOutputTool(tool_definition())

    result = await _executor(tool).execute(_request(), _context())

    assert result.status is ToolExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == "tool_invalid_output"


@pytest.mark.asyncio
async def test_request_context_mismatch_raises_invariant_error() -> None:
    tool = FakeTool(tool_definition())

    with pytest.raises(ToolExecutionInvariantError):
        await _executor(tool).execute(_request(), _context(call_id="call-2"))
    assert tool.call_count == 0


@pytest.mark.asyncio
async def test_cancelled_error_is_repropagated() -> None:
    wait_event = asyncio.Event()
    tool = FakeTool(tool_definition(), wait_event=wait_event)
    execution = asyncio.create_task(_executor(tool).execute(_request(), _context()))
    await asyncio.sleep(0)

    execution.cancel()

    with pytest.raises(asyncio.CancelledError):
        await execution
    assert tool.call_count == 1


@pytest.mark.asyncio
async def test_repeated_request_is_executed_without_fake_deduplication() -> None:
    tool = FakeTool(tool_definition())
    executor = _executor(tool)
    request = _request()
    context = _context()

    first = await executor.execute(request, context)
    second = await executor.execute(request, context)

    assert first.status is ToolExecutionStatus.SUCCEEDED
    assert second.status is ToolExecutionStatus.SUCCEEDED
    assert first.tool_call_id == second.tool_call_id == request.tool_call_id
    assert request.idempotency_key == "operation-1"
    assert tool.call_count == 2


@pytest.mark.asyncio
async def test_concurrent_calls_keep_execution_data_isolated() -> None:
    def dependency(arguments: dict[str, object]) -> object:
        return {"id": arguments["customer_id"]}

    tool = FakeTool(tool_definition(), dependency=dependency)
    executor = _executor(tool)
    requests = (
        _request(call_id="call-a", arguments={"customer_id": "a"}),
        _request(call_id="call-b", arguments={"customer_id": "b"}),
    )
    contexts = (_context(call_id="call-a"), _context(call_id="call-b"))

    results = await asyncio.gather(
        *(
            executor.execute(request, context)
            for request, context in zip(requests, contexts, strict=True)
        )
    )

    assert [result.tool_call_id for result in results] == ["call-a", "call-b"]
    assert [result.output for result in results] == [
        ToolOutput(content={"id": "a"}),
        ToolOutput(content={"id": "b"}),
    ]
    assert tool.call_count == 2
