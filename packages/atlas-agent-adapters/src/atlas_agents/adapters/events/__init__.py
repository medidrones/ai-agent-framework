"""Provider-neutral event-driven adapter contracts and consumer."""

from atlas_agents.adapters.events.consumer import ExecutionCommandConsumer
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

__all__ = [
    "EventAdapterConfig",
    "EventPublicationMode",
    "ExecuteAgentCommand",
    "ExecutionCommandConsumer",
    "ExecutionEventPublisher",
    "MessageEnvelope",
    "MessagePrincipalResolver",
    "MessageProcessingResult",
    "ResumeExecutionCommand",
    "TrustedMessageContext",
]
