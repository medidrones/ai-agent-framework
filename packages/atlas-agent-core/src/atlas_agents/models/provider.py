"""Abstract interface implemented by model provider adapters."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from atlas_agents.models.capabilities import ModelDescriptor
from atlas_agents.models.context import ModelExecutionContext
from atlas_agents.models.request import ModelRequest
from atlas_agents.models.response import ModelResponse
from atlas_agents.models.streaming import ModelStreamEvent


class ModelProvider(ABC):
    """Define provider operations without depending on a concrete SDK."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the stable provider identifier."""

    @abstractmethod
    async def list_models(self) -> tuple[ModelDescriptor, ...]:
        """Return models available through this provider."""

    @abstractmethod
    async def generate(
        self,
        request: ModelRequest,
        context: ModelExecutionContext,
    ) -> ModelResponse:
        """Generate a complete model response."""

    @abstractmethod
    def stream(
        self,
        request: ModelRequest,
        context: ModelExecutionContext,
    ) -> AsyncIterator[ModelStreamEvent]:
        """Stream structured events for one model response."""
