"""Broker-neutral execution event publication contract."""

from typing import Protocol

from atlas_agents.adapters.events.models import MessageEnvelope


class ExecutionEventPublisher(Protocol):
    """Publish one versioned envelope through a caller-owned broker adapter."""

    async def publish(self, envelope: MessageEnvelope) -> None:
        """Publish or raise when durable handoff cannot be confirmed."""
        ...
