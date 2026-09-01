"""Public contracts for validated execution lifecycle management."""

from atlas_agents.execution.lifecycle import ALLOWED_TRANSITIONS, ExecutionLifecycle
from atlas_agents.execution.terminal import TERMINAL_EXECUTION_STATUSES, is_terminal
from atlas_agents.execution.transition import ExecutionTransition

__all__ = [
    "ALLOWED_TRANSITIONS",
    "TERMINAL_EXECUTION_STATUSES",
    "ExecutionLifecycle",
    "ExecutionTransition",
    "is_terminal",
]
