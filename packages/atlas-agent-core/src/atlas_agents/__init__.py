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
from atlas_agents.events import AgentEvent, AgentEventFactory, AgentEventType
from atlas_agents.exceptions import InvalidExecutionTransitionError
from atlas_agents.execution import ExecutionLifecycle, ExecutionTransition, is_terminal

__version__: str = _distribution_version("atlas-agent-core")

__all__ = [
    "Agent",
    "AgentAttachment",
    "AgentContext",
    "AgentDefinition",
    "AgentErrorInfo",
    "AgentEvent",
    "AgentEventFactory",
    "AgentEventType",
    "AgentInput",
    "AgentResult",
    "ExecutionIdentity",
    "ExecutionLifecycle",
    "ExecutionStatus",
    "ExecutionTransition",
    "InvalidExecutionTransitionError",
    "Usage",
    "__version__",
    "is_terminal",
]
