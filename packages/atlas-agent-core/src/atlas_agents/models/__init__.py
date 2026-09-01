"""Provider-agnostic model abstraction contracts."""

from atlas_agents.models.capabilities import ModelCapability, ModelDescriptor
from atlas_agents.models.catalog import ModelCatalogEntry
from atlas_agents.models.content import (
    AudioContent,
    ImageContent,
    MessageContent,
    TextContent,
)
from atlas_agents.models.context import ModelExecutionContext
from atlas_agents.models.finish_reason import FinishReason
from atlas_agents.models.message import MessageRole, ModelMessage
from atlas_agents.models.provider import ModelProvider
from atlas_agents.models.registry import ModelProviderRegistry
from atlas_agents.models.request import ModelRequest
from atlas_agents.models.response import ModelResponse
from atlas_agents.models.selection import (
    ModelCandidate,
    ModelSelectionRequest,
    ModelSelectionResult,
)
from atlas_agents.models.strategy import (
    DeterministicModelSelectionStrategy,
    ModelSelectionStrategy,
)
from atlas_agents.models.streaming import ModelStreamEvent, ModelStreamEventType
from atlas_agents.models.structured_output import StructuredOutputDefinition
from atlas_agents.models.tool_call import ModelToolDefinition, ToolCall
from atlas_agents.models.usage import ModelUsage

__all__ = [
    "AudioContent",
    "DeterministicModelSelectionStrategy",
    "FinishReason",
    "ImageContent",
    "MessageContent",
    "MessageRole",
    "ModelCandidate",
    "ModelCapability",
    "ModelCatalogEntry",
    "ModelDescriptor",
    "ModelExecutionContext",
    "ModelMessage",
    "ModelProvider",
    "ModelProviderRegistry",
    "ModelRequest",
    "ModelResponse",
    "ModelSelectionRequest",
    "ModelSelectionResult",
    "ModelSelectionStrategy",
    "ModelStreamEvent",
    "ModelStreamEventType",
    "ModelToolDefinition",
    "ModelUsage",
    "StructuredOutputDefinition",
    "TextContent",
    "ToolCall",
]
