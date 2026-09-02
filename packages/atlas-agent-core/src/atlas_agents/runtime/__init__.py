"""Public contracts for runtime state and single-turn execution."""

from atlas_agents.runtime.errors import (
    AgentRuntimeError,
    ExecutionAlreadyTerminalError,
    ExecutionStateError,
    ExecutionStateInvariantError,
    InvalidModelStreamProtocolError,
    InvalidModelStreamSequenceError,
    ModelStreamIncompleteError,
    ModelStreamProtocolError,
    ModelStreamReportedError,
    RuntimeInputRejectedError,
)
from atlas_agents.runtime.model_request import ModelRequestBuilder
from atlas_agents.runtime.runtime import AgentRuntime
from atlas_agents.runtime.snapshot import ExecutionSnapshot
from atlas_agents.runtime.state import ExecutionState
from atlas_agents.runtime.stream_accumulator import ModelStreamAccumulator
from atlas_agents.runtime.stream_items import (
    RuntimeEventItem,
    RuntimeResultItem,
    RuntimeStreamItem,
)

__all__ = [
    "AgentRuntime",
    "AgentRuntimeError",
    "ExecutionAlreadyTerminalError",
    "ExecutionSnapshot",
    "ExecutionState",
    "ExecutionStateError",
    "ExecutionStateInvariantError",
    "InvalidModelStreamProtocolError",
    "InvalidModelStreamSequenceError",
    "ModelRequestBuilder",
    "ModelStreamAccumulator",
    "ModelStreamIncompleteError",
    "ModelStreamProtocolError",
    "ModelStreamReportedError",
    "RuntimeEventItem",
    "RuntimeInputRejectedError",
    "RuntimeResultItem",
    "RuntimeStreamItem",
]
