"""Consume a versioned command and publish a broker-neutral terminal event."""

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

from atlas_agents.adapters import TransportPrincipal
from atlas_agents.adapters.events import (
    ExecutionCommandConsumer,
    MessageEnvelope,
    TrustedContextPrincipalResolver,
    TrustedMessageContext,
)

sys.path.insert(0, str(Path(__file__).parents[1]))

from _adapter_support import build_execution_service
from _support import ScriptedModelProvider, agent, build_runtime, text_response


class InMemoryEventPublisher:
    """Represent the boundary that a RabbitMQ, Kafka, or cloud adapter implements."""

    def __init__(self) -> None:
        """Initialize an empty local publication log."""
        self.events: list[MessageEnvelope] = []

    async def publish(self, envelope: MessageEnvelope) -> None:
        """Confirm the simulated durable handoff."""
        self.events.append(envelope)


async def _run() -> None:
    definition = agent()
    runtime = build_runtime(ScriptedModelProvider((text_response("Processado."),)))
    publisher = InMemoryEventPublisher()
    consumer = ExecutionCommandConsumer(
        service=build_execution_service(runtime, definition),
        publisher=publisher,
        principal_resolver=TrustedContextPrincipalResolver(),
        message_id_factory=lambda: "event-1",
    )
    command = MessageEnvelope(
        message_id="command-1",
        message_type="execution.execute",
        schema_version=1,
        correlation_id="correlation-1",
        timestamp=datetime.now(UTC),
        payload={
            "request_id": "event-request-1",
            "agent_id": definition.agent_id,
            "input": {"message": "Execute a partir do broker."},
        },
    )
    result = await consumer.handle(
        command,
        TrustedMessageContext(
            principal=TransportPrincipal(
                subject="broker-user",
                authentication_method="broker",
            )
        ),
    )
    print(f"Confirmar mensagem: {result.acknowledge}")  # noqa: T201
    print(f"Evento publicado: {publisher.events[0].message_type}")  # noqa: T201


if __name__ == "__main__":
    asyncio.run(_run())
