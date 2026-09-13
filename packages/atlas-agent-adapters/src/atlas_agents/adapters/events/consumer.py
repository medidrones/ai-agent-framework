"""Broker-neutral command handler over the shared execution service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from pydantic import JsonValue, ValidationError

from atlas_agents.adapters.errors import AdapterError, AdapterUnavailableError
from atlas_agents.adapters.events.models import (
    EventAdapterConfig,
    EventPublicationMode,
    ExecuteAgentCommand,
    MessageEnvelope,
    MessagePrincipalResolver,
    MessageProcessingResult,
    ResumeExecutionCommand,
    TrustedMessageContext,
)
from atlas_agents.adapters.events.publisher import ExecutionEventPublisher
from atlas_agents.adapters.models import (
    ExecuteAgentRequest,
    ExecuteAgentResponse,
    ResumeExecutionRequest,
    TransportPrincipal,
)
from atlas_agents.adapters.service import AgentExecutionService


class ExecutionCommandConsumer:
    """Handle execute and resume commands without owning broker lifecycle."""

    def __init__(
        self,
        *,
        service: AgentExecutionService,
        publisher: ExecutionEventPublisher,
        principal_resolver: MessagePrincipalResolver,
        config: EventAdapterConfig | None = None,
        message_id_factory: Callable[[], str] | None = None,
    ) -> None:
        """Store explicit dependencies and safe event configuration."""
        self._service = service
        self._publisher = publisher
        self._principal_resolver = principal_resolver
        self._config = config or EventAdapterConfig()
        self._message_id_factory = message_id_factory or (lambda: str(uuid4()))

    async def handle(
        self, envelope: MessageEnvelope, context: TrustedMessageContext
    ) -> MessageProcessingResult:
        """Process one delivery and report ack/retry semantics explicitly."""
        if envelope.schema_version != self._config.schema_version:
            return MessageProcessingResult(
                acknowledge=False,
                retryable=False,
                error_code="unsupported_schema_version",
            )
        try:
            principal = self._principal_resolver.resolve(envelope, context)
            if envelope.message_type == "execution.execute":
                execute_command = ExecuteAgentCommand.model_validate(envelope.payload)
                await self._execute(envelope, execute_command, principal)
            elif envelope.message_type == "execution.resume":
                resume_command = ResumeExecutionCommand.model_validate(envelope.payload)
                await self._resume(envelope, resume_command, principal)
            else:
                return MessageProcessingResult(
                    acknowledge=False,
                    retryable=False,
                    error_code="unsupported_message_type",
                )
        except ValidationError:
            return MessageProcessingResult(
                acknowledge=False,
                retryable=False,
                error_code="invalid_external_request",
            )
        except AdapterError as error:
            return MessageProcessingResult(
                acknowledge=False,
                retryable=error.retryable,
                error_code=error.code,
            )
        except Exception:
            return MessageProcessingResult(
                acknowledge=False,
                retryable=True,
                error_code="adapter_unavailable",
            )
        return MessageProcessingResult(acknowledge=True)

    async def _execute(
        self,
        envelope: MessageEnvelope,
        command: ExecuteAgentCommand,
        principal: TransportPrincipal,
    ) -> None:
        request = ExecuteAgentRequest(
            **command.model_dump(),
            principal=principal,
            idempotency_key=envelope.message_id,
        )
        if self._config.publication_mode is EventPublicationMode.TERMINAL_ONLY:
            await self._publish_terminal(envelope, await self._service.execute(request))
            return
        async for item in self._service.stream(request):
            await self._publish(
                source=envelope,
                message_type="execution.stream",
                payload=cast("dict[str, JsonValue]", item.model_dump(mode="json")),
            )

    async def _resume(
        self,
        envelope: MessageEnvelope,
        command: ResumeExecutionCommand,
        principal: TransportPrincipal,
    ) -> None:
        request = ResumeExecutionRequest(
            **command.model_dump(),
            principal=principal,
            idempotency_key=envelope.message_id,
        )
        if self._config.publication_mode is EventPublicationMode.TERMINAL_ONLY:
            await self._publish_terminal(envelope, await self._service.resume(request))
            return
        async for item in self._service.resume_stream(request):
            await self._publish(
                source=envelope,
                message_type="execution.stream",
                payload=cast("dict[str, JsonValue]", item.model_dump(mode="json")),
            )

    async def _publish_terminal(
        self, source: MessageEnvelope, response: ExecuteAgentResponse
    ) -> None:
        await self._publish(
            source=source,
            message_type=f"execution.{response.status.value}",
            payload=cast("dict[str, JsonValue]", response.model_dump(mode="json")),
        )

    async def _publish(
        self,
        *,
        source: MessageEnvelope,
        message_type: str,
        payload: dict[str, JsonValue],
    ) -> None:
        event = MessageEnvelope(
            message_id=self._message_id_factory(),
            message_type=message_type,
            schema_version=self._config.schema_version,
            correlation_id=source.correlation_id,
            causation_id=source.message_id,
            timestamp=datetime.now(UTC),
            payload=payload,
        )
        try:
            await self._publisher.publish(event)
        except Exception:
            raise AdapterUnavailableError(
                "Não foi possível publicar o evento de execução."
            ) from None
