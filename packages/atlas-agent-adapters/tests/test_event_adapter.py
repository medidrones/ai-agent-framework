from __future__ import annotations

from datetime import UTC, datetime

import pytest
from adapter_test_support import FakeRuntime, make_service, result

from atlas_agents.adapters import TransportPrincipal
from atlas_agents.adapters.events import (
    EventAdapterConfig,
    EventPublicationMode,
    ExecutionCommandConsumer,
    MessageEnvelope,
    TrustedMessageContext,
)
from atlas_agents.adapters.events.models import TrustedContextPrincipalResolver
from atlas_agents.agents import ExecutionStatus


class Publisher:
    def __init__(self, *, fail: bool = False) -> None:
        self.events: list[MessageEnvelope] = []
        self.fail = fail

    async def publish(self, envelope: MessageEnvelope) -> None:
        if self.fail:
            raise RuntimeError("falha interna do broker")
        self.events.append(envelope)


def envelope(
    *,
    message_id: str = "message-1",
    message_type: str = "execution.execute",
    message: str = "Olá",
    extra: dict[str, object] | None = None,
) -> MessageEnvelope:
    payload: dict[str, object] = {
        "request_id": "request-1",
        "agent_id": "agent-1",
        "input": {"message": message},
    }
    if extra:
        payload.update(extra)
    return MessageEnvelope(
        message_id=message_id,
        message_type=message_type,
        schema_version=1,
        correlation_id="correlation-1",
        timestamp=datetime.now(UTC),
        payload=payload,  # type: ignore[arg-type]
    )


def context() -> TrustedMessageContext:
    return TrustedMessageContext(
        principal=TransportPrincipal(subject="broker-user", tenant="tenant")
    )


def consumer(
    runtime: FakeRuntime,
    publisher: Publisher,
    *,
    mode: EventPublicationMode = EventPublicationMode.TERMINAL_ONLY,
) -> ExecutionCommandConsumer:
    return ExecutionCommandConsumer(
        service=make_service(runtime),
        publisher=publisher,
        principal_resolver=TrustedContextPrincipalResolver(),
        config=EventAdapterConfig(publication_mode=mode),
        message_id_factory=lambda: "event-1",
    )


@pytest.mark.asyncio
async def test_terminal_only_execute_preserves_correlation_and_causation() -> None:
    runtime = FakeRuntime()
    publisher = Publisher()
    handled = await consumer(runtime, publisher).handle(envelope(), context())
    assert handled.acknowledge is True
    assert runtime.run_calls == 1
    assert len(publisher.events) == 1
    event = publisher.events[0]
    assert event.message_type == "execution.completed"
    assert event.correlation_id == "correlation-1"
    assert event.causation_id == "message-1"
    assert event.payload["request_id"] == "request-1"
    assert event.payload["execution_id"] == "execution-1"


@pytest.mark.asyncio
async def test_redelivery_replays_response_without_duplicate_runtime_call() -> None:
    runtime = FakeRuntime()
    publisher = Publisher()
    handler = consumer(runtime, publisher)
    command = envelope()
    assert (await handler.handle(command, context())).acknowledge is True
    assert (await handler.handle(command, context())).acknowledge is True
    assert runtime.run_calls == 1
    assert len(publisher.events) == 2


@pytest.mark.asyncio
async def test_same_message_id_with_different_payload_is_conflict() -> None:
    runtime = FakeRuntime()
    publisher = Publisher()
    handler = consumer(runtime, publisher)
    await handler.handle(envelope(message="Primeiro"), context())
    conflict = await handler.handle(envelope(message="Diferente"), context())
    assert conflict.acknowledge is False
    assert conflict.retryable is False
    assert conflict.error_code == "idempotency_conflict"
    assert runtime.run_calls == 1


@pytest.mark.asyncio
async def test_runtime_failure_is_acknowledged_and_published() -> None:
    runtime = FakeRuntime(result(ExecutionStatus.FAILED))
    publisher = Publisher()
    handled = await consumer(runtime, publisher).handle(envelope(), context())
    assert handled.acknowledge is True
    assert publisher.events[0].message_type == "execution.failed"


@pytest.mark.asyncio
async def test_publisher_failure_is_retryable_infrastructure_failure() -> None:
    runtime = FakeRuntime()
    publisher = Publisher(fail=True)
    handler = consumer(runtime, publisher)
    handled = await handler.handle(envelope(), context())
    assert handled.acknowledge is False
    assert handled.retryable is True
    assert handled.error_code == "adapter_unavailable"
    assert runtime.run_calls == 1


@pytest.mark.asyncio
async def test_stream_events_mode_publishes_ordered_items() -> None:
    runtime = FakeRuntime()
    publisher = Publisher()
    handled = await consumer(
        runtime, publisher, mode=EventPublicationMode.STREAM_EVENTS
    ).handle(envelope(), context())
    assert handled.acknowledge is True
    assert [event.payload["sequence"] for event in publisher.events] == [0, 1]
    assert all(event.message_type == "execution.stream" for event in publisher.events)


@pytest.mark.asyncio
async def test_payload_cannot_assert_identity_or_roles() -> None:
    runtime = FakeRuntime()
    publisher = Publisher()
    handled = await consumer(runtime, publisher).handle(
        envelope(extra={"user_id": "admin", "roles": ["superuser"]}), context()
    )
    assert handled.acknowledge is False
    assert handled.error_code == "invalid_external_request"
    assert runtime.run_calls == 0


@pytest.mark.asyncio
async def test_unknown_message_and_schema_are_non_retryable() -> None:
    runtime = FakeRuntime()
    publisher = Publisher()
    handler = consumer(runtime, publisher)
    unknown = await handler.handle(envelope(message_type="execution.cancel"), context())
    version = envelope().model_copy(update={"schema_version": 99})
    incompatible = await handler.handle(version, context())
    assert unknown.error_code == "unsupported_message_type"
    assert incompatible.error_code == "unsupported_schema_version"
    assert unknown.retryable is False
    assert incompatible.retryable is False


@pytest.mark.asyncio
async def test_resume_command_uses_trusted_context_and_publishes_result() -> None:
    runtime = FakeRuntime()
    publisher = Publisher()
    command = MessageEnvelope(
        message_id="resume-message",
        message_type="execution.resume",
        schema_version=1,
        correlation_id="correlation-1",
        timestamp=datetime.now(UTC),
        payload={
            "request_id": "resume-1",
            "agent_id": "agent-1",
            "resume_token": "test-token",
            "approval_request_id": "approval-1",
            "decision": "approve",
            "decided_at": datetime.now(UTC).isoformat(),
        },
    )
    handled = await consumer(runtime, publisher).handle(command, context())
    assert handled.acknowledge is True
    assert runtime.resume_calls == 1
    assert publisher.events[0].message_type == "execution.completed"


@pytest.mark.asyncio
async def test_unexpected_principal_resolution_failure_is_retryable() -> None:
    class BrokenResolver:
        def resolve(
            self, envelope: MessageEnvelope, context: TrustedMessageContext
        ) -> TransportPrincipal:
            del envelope, context
            raise RuntimeError("detalhe que não deve vazar")

    handler = ExecutionCommandConsumer(
        service=make_service(FakeRuntime()),
        publisher=Publisher(),
        principal_resolver=BrokenResolver(),
    )
    handled = await handler.handle(envelope(), context())
    assert handled.acknowledge is False
    assert handled.retryable is True
    assert handled.error_code == "adapter_unavailable"
