"""Provider-agnostic primitives for building and running AI agents."""

from importlib.metadata import version as _distribution_version

from atlas_agents.agents import (
    Agent,
    AgentAttachment,
    AgentContext,
    AgentDefinition,
    AgentErrorInfo,
    AgentInput,
    AgentResult,
    ExecutionIdentity,
    ExecutionStatus,
    Usage,
)
from atlas_agents.events import AgentEvent, AgentEventType

__version__: str = _distribution_version("atlas-agent-core")

__all__ = [
    "Agent",
    "AgentAttachment",
    "AgentContext",
    "AgentDefinition",
    "AgentErrorInfo",
    "AgentEvent",
    "AgentEventType",
    "AgentInput",
    "AgentResult",
    "ExecutionIdentity",
    "ExecutionStatus",
    "Usage",
    "__version__",
]
