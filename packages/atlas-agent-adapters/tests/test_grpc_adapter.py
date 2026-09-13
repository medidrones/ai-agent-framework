from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import grpc
import pytest
from adapter_test_support import FakeRuntime, make_service, result, suspension
from google.protobuf import timestamp_pb2

from atlas_agents.adapters.errors import InvalidExternalRequestError
from atlas_agents.adapters.grpc import (
    AnonymousGrpcPrincipalFactory,
    add_agent_execution_servicer,
)
from atlas_agents.adapters.grpc.mapping import (
    execute_from_proto,
    response_to_proto,
    resume_from_proto,
)
from atlas_agents.adapters.grpc.v1 import agent_execution_pb2 as pb
from atlas_agents.adapters.grpc.v1 import agent_execution_pb2_grpc as pb_grpc
from atlas_agents.adapters.models import (
    ExecuteAgentRequest,
    ExternalAgentInput,
    TransportPrincipal,
)
from atlas_agents.agents import ExecutionStatus


def request(*, agent_id: str = "agent-1") -> pb.ExecuteRequest:
    return pb.ExecuteRequest(
        request_id="request-1",
        agent_id=agent_id,
        input=pb.AgentInput(message="Olá"),
    )


def resume_request(
    decision: pb.ApprovalDecision = pb.APPROVAL_DECISION_APPROVE,
) -> pb.ResumeRequest:
    decided_at = timestamp_pb2.Timestamp()
    decided_at.FromDatetime(datetime.now(UTC))
    opaque_value = "test-" + "token"
    return pb.ResumeRequest(
        request_id="resume-1",
        agent_id="agent-1",
        resume_token=opaque_value,
        approval_request_id="approval-1",
        decision=decision,
        decided_at=decided_at,
    )


async def start_server(
    runtime: FakeRuntime,
) -> tuple[grpc.aio.Server, grpc.aio.Channel, pb_grpc.AgentExecutionServiceStub]:
    server = grpc.aio.server()
    add_agent_execution_servicer(
        server=server,
        service=make_service(runtime),
        principal_factory=AnonymousGrpcPrincipalFactory(),
    )
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    channel = grpc.aio.insecure_channel(f"127.0.0.1:{port}")
    stub = pb_grpc.AgentExecutionServiceStub(channel)  # type: ignore[no-untyped-call]
    return server, channel, stub


@pytest.mark.asyncio
async def test_grpc_unary_execute_and_runtime_failure_are_ok_responses() -> None:
    for status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED):
        runtime = FakeRuntime(result(status))
        server, channel, stub = await start_server(runtime)
        try:
            response = await stub.Execute(request())
            assert response.status == status.value
            assert runtime.run_calls == 1
        finally:
            await channel.close()
            await server.stop(None)


@pytest.mark.asyncio
async def test_grpc_unknown_agent_maps_to_not_found() -> None:
    server, channel, stub = await start_server(FakeRuntime())
    try:
        with pytest.raises(grpc.aio.AioRpcError) as caught:
            await stub.Execute(request(agent_id="unknown"))
        assert caught.value.code() is grpc.StatusCode.NOT_FOUND
    finally:
        await channel.close()
        await server.stop(None)


@pytest.mark.asyncio
async def test_grpc_stream_preserves_order_without_buffering() -> None:
    runtime = FakeRuntime()
    server, channel, stub = await start_server(runtime)
    try:
        call: AsyncIterator[pb.StreamItem] = stub.Stream(request())
        items = [item async for item in call]
        assert [item.sequence for item in items] == [0, 1]
        assert [item.type for item in items] == ["model_text_delta", "result"]
        assert runtime.stream_closed is True
    finally:
        await channel.close()
        await server.stop(None)


@pytest.mark.asyncio
async def test_grpc_resume_and_resume_stream_use_body_token() -> None:
    runtime = FakeRuntime()
    server, channel, stub = await start_server(runtime)
    try:
        response = await stub.Resume(resume_request())
        items = [item async for item in stub.ResumeStream(resume_request())]
        assert response.status == "completed"
        assert items[-1].type == "result"
        assert runtime.resume_calls == 2
    finally:
        await channel.close()
        await server.stop(None)


@pytest.mark.asyncio
async def test_grpc_invalid_request_is_invalid_argument() -> None:
    server, channel, stub = await start_server(FakeRuntime())
    try:
        with pytest.raises(grpc.aio.AioRpcError) as caught:
            await stub.Execute(pb.ExecuteRequest())
        assert caught.value.code() is grpc.StatusCode.INVALID_ARGUMENT
    finally:
        await channel.close()
        await server.stop(None)


def test_grpc_deadline_narrows_requested_runtime_timeout() -> None:
    value = request()
    value.requested_limits.timeout_seconds = 100
    mapped = execute_from_proto(
        value,
        principal=TransportPrincipal(subject="authenticated"),
        transport_timeout=2.5,
    )
    assert mapped.requested_limits is not None
    assert mapped.requested_limits.timeout_seconds == 2.5


def test_grpc_maps_all_requested_policy_and_attachment_fields() -> None:
    value = request()
    value.input.attachments.add(
        attachment_id="attachment-1",
        name="Arquivo",
        media_type="text/plain",
        uri="https://example.test/file",
    )
    value.context.session_id = "session-1"
    value.requested_limits.max_turns = 3
    value.requested_limits.max_tool_calls = 2
    value.requested_limits.max_input_tokens = 10
    value.requested_limits.max_output_tokens = 20
    value.requested_limits.max_total_tokens = 30
    value.requested_budget.max_estimated_cost = "0.5"
    value.requested_budget.currency = "USD"
    mapped = execute_from_proto(
        value, principal=TransportPrincipal(subject="authenticated")
    )
    assert mapped.input.attachments[0].uri == "https://example.test/file"
    assert mapped.context.session_id == "session-1"
    assert mapped.requested_limits is not None
    assert mapped.requested_limits.max_tool_calls == 2
    assert mapped.requested_budget is not None
    assert str(mapped.requested_budget.max_estimated_cost) == "0.5"


def test_grpc_resume_rejects_unspecified_decision() -> None:
    with pytest.raises(InvalidExternalRequestError, match="decisão"):
        resume_from_proto(
            resume_request(pb.APPROVAL_DECISION_UNSPECIFIED),
            principal=TransportPrincipal(subject="authenticated"),
        )


@pytest.mark.asyncio
async def test_grpc_maps_suspension_response_with_token_only_in_payload() -> None:
    application = await make_service(FakeRuntime(suspension())).execute(
        ExecuteAgentRequest(
            request_id="request-1",
            agent_id="agent-1",
            input=ExternalAgentInput(message="Olá"),
            principal=TransportPrincipal(subject="authenticated"),
        )
    )
    mapped = response_to_proto(application)
    assert mapped.status == "waiting_for_approval"
    assert mapped.suspension.resume_token == suspension().resume_token.value


def test_proto_v1_package_fields_and_unknown_decision_are_stable() -> None:
    descriptor = pb.DESCRIPTOR
    assert descriptor.package == "atlas.agent.v1"
    execute = descriptor.message_types_by_name["ExecuteRequest"]
    assert execute.fields_by_name["request_id"].number == 1
    assert execute.fields_by_name["agent_id"].number == 2
    assert pb.APPROVAL_DECISION_UNSPECIFIED == 0
