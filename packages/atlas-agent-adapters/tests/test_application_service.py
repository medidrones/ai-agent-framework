from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

import pytest
from adapter_test_support import FakeRuntime, make_service, result, suspension
from pydantic import ValidationError

from atlas_agents.adapters import (
    AgentAccessDeniedError,
    AgentNotRegisteredError,
    AgentOperation,
    AgentRegistry,
    DuplicateAgentError,
    ExecuteAgentRequest,
    ExternalAgentInput,
    IdempotencyConflictError,
    InMemoryIdempotencyStore,
    RequestedExecutionBudget,
    RequestedExecutionLimits,
    ResumeExecutionRequest,
    SubjectExecutionIdentityMapper,
    TransportPrincipal,
)
from atlas_agents.agents import AgentDefinition, ExecutionIdentity, ExecutionStatus


def execute_request(**changes: object) -> ExecuteAgentRequest:
    values: dict[str, object] = {
        "request_id": "request-1",
        "agent_id": "agent-1",
        "input": ExternalAgentInput(message="Olá"),
        "principal": TransportPrincipal(
            subject="user-1",
            tenant="tenant-1",
            claims={"roles": ["admin"], "token": "SECRET"},
        ),
    }
    values.update(changes)
    return ExecuteAgentRequest(**values)  # type: ignore[arg-type]


def test_agent_registry_is_ordered_and_rejects_duplicates() -> None:
    registry = AgentRegistry()
    first = AgentDefinition(agent_id="a", name="A", instructions="A")
    second = AgentDefinition(agent_id="b", name="B", instructions="B")
    registry.register(first)
    registry.register(second)
    assert registry.agents() == (first, second)
    assert registry.try_get("a") is first
    with pytest.raises(DuplicateAgentError):
        registry.register(first)
    assert registry.unregister("a") is first
    with pytest.raises(AgentNotRegisteredError):
        registry.get("missing")


def test_identity_mapper_does_not_promote_claimed_roles_or_permissions() -> None:
    identity = SubjectExecutionIdentityMapper().map(
        TransportPrincipal(
            subject="user",
            tenant="tenant",
            claims={"roles": ["admin"], "permissions": ["all"]},
        )
    )
    assert identity.subject == "user"
    assert identity.roles == frozenset()
    assert identity.permissions == frozenset()
    assert identity.attributes == {"tenant": "tenant"}


@pytest.mark.asyncio
async def test_execute_maps_identity_and_clamps_limits_and_budget() -> None:
    runtime = FakeRuntime()
    response = await make_service(runtime).execute(
        execute_request(
            requested_limits=RequestedExecutionLimits(
                max_turns=500, timeout_seconds=120
            ),
            requested_budget=RequestedExecutionBudget(
                max_estimated_cost=Decimal("99"), currency="USD"
            ),
        )
    )
    assert response.status.value == "completed"
    assert response.output == {"answer": "ok"}
    assert response.usage is not None
    assert response.usage.input_tokens == 2
    assert runtime.last_context is not None
    assert runtime.last_context.identity == ExecutionIdentity(
        subject="user-1", attributes={"tenant": "tenant-1"}
    )
    assert runtime.last_limits is not None
    assert runtime.last_limits.max_turns == 5
    assert runtime.last_limits.timeout_seconds == 30
    assert runtime.last_budget is not None
    assert str(runtime.last_budget.max_estimated_cost) == "1"


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
async def test_access_policy_runs_before_runtime() -> None:
    runtime = FakeRuntime()
    with pytest.raises(AgentAccessDeniedError):
        await make_service(runtime, access_policy=DenyPolicy()).execute(
            execute_request()
        )
    assert runtime.run_calls == 0


@pytest.mark.asyncio
async def test_idempotency_replays_same_request_and_rejects_conflict() -> None:
    runtime = FakeRuntime()
    service = make_service(runtime)
    request = execute_request(idempotency_key="key-1")
    first = await service.execute(request)
    second = await service.execute(request)
    assert first == second
    assert runtime.run_calls == 1
    with pytest.raises(IdempotencyConflictError):
        await service.execute(
            execute_request(
                idempotency_key="key-1",
                input=ExternalAgentInput(message="Diferente"),
            )
        )


@pytest.mark.asyncio
async def test_idempotency_is_scoped_to_authenticated_principal() -> None:
    runtime = FakeRuntime()
    service = make_service(runtime)
    await service.execute(execute_request(idempotency_key="shared-key"))
    with pytest.raises(IdempotencyConflictError):
        await service.execute(
            execute_request(
                idempotency_key="shared-key",
                principal=TransportPrincipal(subject="other-user", tenant="tenant-1"),
            )
        )
    assert runtime.run_calls == 1


@pytest.mark.parametrize(
    "status",
    [
        ExecutionStatus.FAILED,
        ExecutionStatus.REJECTED,
        ExecutionStatus.TIMED_OUT,
        ExecutionStatus.LIMIT_EXCEEDED,
        ExecutionStatus.BUDGET_EXCEEDED,
    ],
)
@pytest.mark.asyncio
async def test_terminal_runtime_outcomes_remain_application_responses(
    status: ExecutionStatus,
) -> None:
    response = await make_service(FakeRuntime(result(status))).execute(
        execute_request()
    )
    assert response.status.value == status.value


@pytest.mark.asyncio
async def test_stream_preserves_sequence_filters_data_and_closes() -> None:
    runtime = FakeRuntime()
    items = [item async for item in make_service(runtime).stream(execute_request())]
    assert [item.sequence for item in items] == [0, 1]
    assert [item.type for item in items] == ["model_text_delta", "result"]
    assert items[0].data == {"text": "Olá"}
    assert runtime.stream_closed is True


@pytest.mark.asyncio
async def test_stream_consumer_close_reaches_runtime_generator() -> None:
    runtime = FakeRuntime()
    iterator = make_service(runtime).stream(execute_request())
    assert (await anext(iterator)).type == "model_text_delta"
    await cast("AsyncGenerator[object, None]", iterator).aclose()
    assert runtime.stream_closed is True


@pytest.mark.asyncio
async def test_suspension_and_resume_keep_token_out_of_repr() -> None:
    suspended = await make_service(FakeRuntime(suspension())).execute(execute_request())
    assert suspended.status.value == "waiting_for_approval"
    assert suspended.suspension is not None
    assert "SECRET-RESUME-TOKEN" not in repr(suspended.suspension)

    runtime = FakeRuntime()
    response = await make_service(runtime).resume(
        ResumeExecutionRequest(
            request_id="resume-1",
            agent_id="agent-1",
            resume_token="SECRET-RESUME-TOKEN",  # noqa: S106
            approval_request_id="approval-1",
            decision="approve",
            decided_at=datetime.now(UTC),
            principal=TransportPrincipal(subject="user-1"),
        )
    )
    assert response.status.value == "completed"
    assert runtime.resume_calls == 1
    assert runtime.last_decision is not None
    assert runtime.last_decision.decided_by is not None
    assert runtime.last_decision.decided_by.subject == "user-1"


@pytest.mark.asyncio
async def test_suspension_stream_and_resume_stream_are_mapped() -> None:
    suspended_runtime = FakeRuntime(suspension())
    items = [
        item async for item in make_service(suspended_runtime).stream(execute_request())
    ]
    assert items[-1].type == "suspension"
    result_payload = items[-1].data["result"]
    assert isinstance(result_payload, dict)
    assert result_payload["status"] == "waiting_for_approval"

    runtime = FakeRuntime()
    request = ResumeExecutionRequest(
        request_id="resume-stream",
        agent_id="agent-1",
        resume_token="test-token",  # noqa: S106
        approval_request_id="approval-1",
        decision="reject",
        decided_at=datetime.now(UTC),
        principal=TransportPrincipal(subject="user-1"),
    )
    resumed = [item async for item in make_service(runtime).resume_stream(request)]
    assert resumed[-1].type == "result"
    assert runtime.stream_closed is True


@pytest.mark.asyncio
async def test_in_memory_idempotency_reservation_can_fail_and_retry() -> None:
    store = InMemoryIdempotencyStore()
    record, created = await store.reserve("key", "fingerprint")
    same, second_created = await store.reserve("key", "fingerprint")
    assert created is True
    assert second_created is False
    assert same == record
    await store.fail("key", "other")
    assert await store.get("key") is not None
    await store.fail("key", "fingerprint")
    assert await store.get("key") is None


def test_application_request_rejects_undeclared_identity_fields() -> None:
    with pytest.raises(ValidationError):
        ExecuteAgentRequest.model_validate(
            {
                "request_id": "request",
                "agent_id": "agent-1",
                "input": {"message": "Olá"},
                "principal": {"subject": "trusted"},
                "user_id": "admin",
                "roles": ["superuser"],
            }
        )
