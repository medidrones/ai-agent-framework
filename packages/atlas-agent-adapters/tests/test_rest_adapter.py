from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import cast

import httpx
import pytest
from adapter_test_support import FakeRuntime, make_service, result
from fastapi import Request

from atlas_agents.adapters import (
    AdapterError,
    AdapterUnavailableError,
    AgentOperation,
    IdempotencyConflictError,
    IdentityMappingError,
    InvalidExternalRequestError,
    TransportPrincipal,
)
from atlas_agents.adapters.models import ExecutionStreamItem
from atlas_agents.adapters.rest import RESTAdapterConfig, create_app
from atlas_agents.adapters.rest.app import _sse_events, _status
from atlas_agents.agents import ExecutionIdentity, ExecutionStatus


class PrincipalFactory:
    async def create(self, request: Request) -> TransportPrincipal:
        del request
        return TransportPrincipal(subject="authenticated-user", tenant="tenant")


def body(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "request_id": "request-1",
        "agent_id": "agent-1",
        "input": {"message": "Olá"},
    }
    value.update(changes)
    return value


def client(runtime: FakeRuntime, **kwargs: object) -> httpx.AsyncClient:
    app = create_app(
        service=make_service(runtime, **kwargs),  # type: ignore[arg-type]
        principal_factory=PrincipalFactory(),
        config=RESTAdapterConfig(max_request_bytes=4096),
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


@pytest.mark.asyncio
async def test_execute_success_uses_authenticated_principal() -> None:
    runtime = FakeRuntime()
    async with client(runtime) as http:
        response = await http.post("/v1/executions", json=body())
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert runtime.last_context is not None
    assert runtime.last_context.identity is not None
    assert runtime.last_context.identity.subject == "authenticated-user"


@pytest.mark.parametrize(
    "status",
    [ExecutionStatus.FAILED, ExecutionStatus.REJECTED, ExecutionStatus.TIMED_OUT],
)
@pytest.mark.asyncio
async def test_runtime_outcome_is_http_200(status: ExecutionStatus) -> None:
    async with client(FakeRuntime(result(status))) as http:
        response = await http.post("/v1/executions", json=body())
    assert response.status_code == 200
    assert response.json()["status"] == status.value


@pytest.mark.asyncio
async def test_malformed_and_identity_spoof_requests_never_reach_runtime() -> None:
    runtime = FakeRuntime()
    async with client(runtime) as http:
        malformed = await http.post("/v1/executions", json={"agent_id": "agent-1"})
        spoofed = await http.post(
            "/v1/executions",
            json=body(user_id="admin", roles=["superuser"]),
        )
    assert malformed.status_code == 422
    assert spoofed.status_code == 422
    assert runtime.run_calls == 0


class DenyPolicy:
    async def authorize(
        self,
        *,
        agent_id: str,
        identity: ExecutionIdentity,
        operation: AgentOperation,
    ) -> bool:
        del agent_id, identity, operation
        return False


@pytest.mark.asyncio
async def test_transport_authorization_is_403_before_runtime() -> None:
    runtime = FakeRuntime()
    async with client(runtime, access_policy=DenyPolicy()) as http:
        response = await http.post("/v1/executions", json=body())
    assert response.status_code == 403
    assert response.json()["code"] == "agent_access_denied"
    assert runtime.run_calls == 0


@pytest.mark.asyncio
async def test_unknown_agent_is_safe_404() -> None:
    runtime = FakeRuntime()
    async with client(runtime) as http:
        response = await http.post("/v1/executions", json=body(agent_id="unknown"))
    assert response.status_code == 404
    assert response.json()["code"] == "agent_not_registered"
    assert runtime.run_calls == 0


@pytest.mark.asyncio
async def test_sse_preserves_order_and_emits_final_result_once() -> None:
    runtime = FakeRuntime()
    async with client(runtime) as http:
        response = await http.post("/v1/executions/stream", json=body())
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    payloads = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert [item["sequence"] for item in payloads] == [0, 1]
    assert [item["type"] for item in payloads] == ["model_text_delta", "result"]
    assert runtime.stream_closed is True


@pytest.mark.asyncio
async def test_resume_token_is_only_in_request_body() -> None:
    runtime = FakeRuntime()
    async with client(runtime) as http:
        response = await http.post(
            "/v1/executions/resume",
            json={
                "request_id": "resume-1",
                "agent_id": "agent-1",
                "resume_token": "SECRET-RESUME-TOKEN",
                "approval_request_id": "approval-1",
                "decision": "approve",
                "decided_at": "2026-09-13T12:00:00Z",
            },
        )
    assert response.status_code == 200
    assert runtime.resume_calls == 1


@pytest.mark.asyncio
async def test_resume_stream_emits_final_item() -> None:
    runtime = FakeRuntime()
    async with client(runtime) as http:
        response = await http.post(
            "/v1/executions/resume/stream",
            json={
                "request_id": "resume-1",
                "agent_id": "agent-1",
                "resume_token": "test-token",
                "approval_request_id": "approval-1",
                "decision": "reject",
                "decided_at": "2026-09-13T12:00:00Z",
            },
        )
    assert response.status_code == 200
    assert '"type": "result"' in response.text


@pytest.mark.asyncio
async def test_rest_idempotency_conflict_is_http_409() -> None:
    runtime = FakeRuntime()
    async with client(runtime) as http:
        first = await http.post(
            "/v1/executions",
            json=body(),
            headers={"Idempotency-Key": "key-1"},
        )
        second = await http.post(
            "/v1/executions",
            json=body(input={"message": "Diferente"}),
            headers={"Idempotency-Key": "key-1"},
        )
    assert first.status_code == 200
    assert second.status_code == 409
    assert runtime.run_calls == 1


@pytest.mark.asyncio
async def test_health_readiness_and_openapi_are_local_and_versioned() -> None:
    runtime = FakeRuntime()
    async with client(runtime) as http:
        health = await http.get("/v1/health")
        readiness = await http.get("/v1/readiness")
        schema = (await http.get("/openapi.json")).json()
    assert health.json() == {"status": "ok"}
    assert readiness.json()["ready"] is True
    assert runtime.run_calls == 0
    expected = {
        "/v1/executions",
        "/v1/executions/stream",
        "/v1/executions/resume",
        "/v1/executions/resume/stream",
        "/v1/health",
        "/v1/readiness",
    }
    assert expected <= set(schema["paths"])
    assert all("{resume_token}" not in path for path in schema["paths"])


@pytest.mark.asyncio
async def test_content_length_limit_rejects_before_runtime() -> None:
    runtime = FakeRuntime()
    async with client(runtime) as http:
        encoded = json.dumps(body()).encode()
        response = await http.post(
            "/v1/executions",
            content=encoded,
            headers={"content-type": "application/json", "content-length": "99999"},
        )
    assert response.status_code == 400
    assert runtime.run_calls == 0


@pytest.mark.asyncio
async def test_invalid_content_length_is_a_safe_client_error() -> None:
    runtime = FakeRuntime()
    async with client(runtime) as http:
        response = await http.post(
            "/v1/executions",
            content=json.dumps(body()).encode(),
            headers={"content-type": "application/json", "content-length": "invalid"},
        )
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_external_request"
    assert runtime.run_calls == 0


@pytest.mark.asyncio
async def test_rest_disconnect_closes_upstream_stream() -> None:
    closed = False

    async def upstream() -> AsyncIterator[ExecutionStreamItem]:
        nonlocal closed
        try:
            yield ExecutionStreamItem(
                type="result", sequence=1, execution_id="execution-1"
            )
        finally:
            closed = True

    class DisconnectedRequest:
        async def is_disconnected(self) -> bool:
            return True

    iterator = upstream()
    first = ExecutionStreamItem(
        type="text_delta",
        sequence=0,
        execution_id="execution-1",
        data={"text": "Olá"},
    )
    response = _sse_events(cast("Request", DisconnectedRequest()), iterator, first)
    assert (await anext(response)).startswith("data: ")
    with pytest.raises(StopAsyncIteration):
        await anext(response)
    assert closed is True


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (IdentityMappingError("falha"), 401),
        (IdempotencyConflictError("falha"), 409),
        (InvalidExternalRequestError("falha"), 400),
        (AdapterUnavailableError("falha"), 503),
        (AdapterError("falha"), 500),
    ],
)
def test_rest_adapter_error_statuses_are_transport_specific(
    error: AdapterError, expected: int
) -> None:
    assert _status(error) == expected
