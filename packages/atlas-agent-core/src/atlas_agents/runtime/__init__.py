"""Public contracts for runtime state and multi-turn execution."""

from atlas_agents.runtime.budget import ExecutionBudget, ExecutionBudgetViolation
from atlas_agents.runtime.checkpoint import (
    CURRENT_CHECKPOINT_VERSION,
    CheckpointStore,
    ExecutionCheckpoint,
    ExecutionMode,
)
from atlas_agents.runtime.enforcement import ExecutionLimitChecker
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
from atlas_agents.runtime.limits import (
    ExecutionLimitReason,
    ExecutionLimits,
    ExecutionLimitViolation,
)
from atlas_agents.runtime.model_request import ModelRequestBuilder
from atlas_agents.runtime.outcome import RuntimeOutcome
from atlas_agents.runtime.restorer import ExecutionStateRestorer
from atlas_agents.runtime.runtime import AgentRuntime
from atlas_agents.runtime.snapshot import ExecutionSnapshot
from atlas_agents.runtime.state import ExecutionState
from atlas_agents.runtime.stream_accumulator import ModelStreamAccumulator
from atlas_agents.runtime.stream_items import (
    RuntimeEventItem,
    RuntimeResultItem,
    RuntimeStreamItem,
    RuntimeSuspensionItem,
)
from atlas_agents.runtime.tool_calls import ToolCallRecord
from atlas_agents.runtime.tool_results import ToolResultMessageMapper

__all__ = [
    "CURRENT_CHECKPOINT_VERSION",
    "AgentRuntime",
    "AgentRuntimeError",
    "CheckpointStore",
    "ExecutionAlreadyTerminalError",
    "ExecutionBudget",
    "ExecutionBudgetViolation",
    "ExecutionCheckpoint",
    "ExecutionLimitChecker",
    "ExecutionLimitReason",
    "ExecutionLimitViolation",
    "ExecutionLimits",
    "ExecutionMode",
    "ExecutionSnapshot",
    "ExecutionState",
    "ExecutionStateError",
    "ExecutionStateInvariantError",
    "ExecutionStateRestorer",
    "InvalidModelStreamProtocolError",
    "InvalidModelStreamSequenceError",
    "ModelRequestBuilder",
    "ModelStreamAccumulator",
    "ModelStreamIncompleteError",
    "ModelStreamProtocolError",
    "ModelStreamReportedError",
    "RuntimeEventItem",
    "RuntimeInputRejectedError",
    "RuntimeOutcome",
    "RuntimeResultItem",
    "RuntimeStreamItem",
    "RuntimeSuspensionItem",
    "ToolCallRecord",
    "ToolResultMessageMapper",
]
