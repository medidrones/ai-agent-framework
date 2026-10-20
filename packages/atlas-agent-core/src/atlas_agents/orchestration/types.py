"""Enums shared by orchestration contracts."""

from enum import StrEnum


class WorkflowNodeKind(StrEnum):
    """Identify a declarative node capability without implementing it."""

    AGENT = "agent"
    TOOL = "tool"
    GATEWAY = "gateway"
    JOIN = "join"
    TERMINAL = "terminal"


class WorkflowStatus(StrEnum):
    """Represent the public lifecycle state of a workflow execution."""

    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class WorkflowResultKind(StrEnum):
    """Distinguish a terminal outcome from a non-terminal snapshot."""

    TERMINAL = "terminal"
    SNAPSHOT = "snapshot"


class WorkflowEventType(StrEnum):
    """Identify stable functional events emitted by a future orchestrator."""

    WORKFLOW_CREATED = "workflow_created"
    WORKFLOW_STARTED = "workflow_started"
    NODE_SCHEDULED = "node_scheduled"
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    WORKFLOW_WAITING = "workflow_waiting"
    WORKFLOW_RESUMED = "workflow_resumed"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    WORKFLOW_CANCELLED = "workflow_cancelled"


class WorkflowFailureAction(StrEnum):
    """Describe a future policy decision after a node failure."""

    FAIL_WORKFLOW = "fail_workflow"
    WAIT = "wait"
    CONTINUE = "continue"


TERMINAL_WORKFLOW_STATUSES = frozenset(
    {
        WorkflowStatus.SUCCEEDED,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELLED,
        WorkflowStatus.TIMED_OUT,
    }
)


def is_workflow_terminal(status: WorkflowStatus) -> bool:
    """Return whether a workflow status is terminal."""
    return status in TERMINAL_WORKFLOW_STATUSES
